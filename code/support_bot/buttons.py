"""
Display menu with buttons according to menu.toml file,
handle buttons actions
"""
from pathlib import Path
from typing import TYPE_CHECKING

import aiogram.types as agtypes
import toml
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .admin_actions import admin_broadcast_start, bot_settings, del_old_topics
from .const import MSG_TEXT_LIMIT, AdminBtn, ButtonMode, MenuMode
from .informing import handle_error, log
from .utils import may_use_admin_actions, save_for_destruction


if TYPE_CHECKING:
    from .bot import SupportBot


def load_toml(path: Path) -> dict | None:
    """
    Read toml file
    """
    if path.is_file():
        with open(path) as f:
            menu = toml.load(f)
        _validate_menu_modes(menu)
        return menu


def _validate_menu_modes(menu: dict) -> None:
    """
    Recursively check any 'menumode' entries against MenuMode at startup,
    so typos like menumode = "rows" fail loudly instead of silently falling
    back to the default layout.
    """
    for key, val in menu.items():
        if key == 'menumode':
            MenuMode.validate(val, raise_exc=True)
        elif isinstance(val, dict):
            _validate_menu_modes(val)


class CBD(CallbackData, prefix='_'):
    """
    Callback Data
    """
    path: str  # separated inside by '.'
    code: str  # button identifier after the path
    msgid: int  # id of a message with this button


class Button:
    """
    Wrapper over an inline keyboard button
    """
    def __init__(self, content: dict):
        self.content = content
        self._recognize_mode()

        empty_answer_allowed = self.mode in (ButtonMode.LINK, ButtonMode.FILE)
        self.answer = _extract_answer(content, empty=empty_answer_allowed)

    def _recognize_mode(self) -> None:
        self.mode = ButtonMode.ANSWER  # label-only buttons act on press via their handler
        if 'link' in self.content:
            self.mode = ButtonMode.LINK
        elif 'file' in self.content:
            self.mode = ButtonMode.FILE
        elif any([isinstance(v, dict) and 'label' in v for v in self.content.values()]):
            self.mode = ButtonMode.MENU
        elif 'subject' in self.content:
            self.mode = ButtonMode.SUBJECT
        elif 'answer' in self.content:
            self.mode = ButtonMode.ANSWER

    def as_inline(self, callback_data: str | None = None) -> InlineKeyboardButton:
        if self.mode in (ButtonMode.FILE, ButtonMode.ANSWER, ButtonMode.MENU, ButtonMode.SUBJECT):
            return InlineKeyboardButton(text=self.content['label'], callback_data=callback_data)
        elif self.mode == ButtonMode.LINK:
            return InlineKeyboardButton(text=self.content['label'], url=self.content['link'])
        raise ValueError('Unexpected button mode')


def _extract_answer(menu: dict, empty: bool=False) -> str:
    answer = (menu.get('answer') or '')[:MSG_TEXT_LIMIT]
    if not empty:
        answer = answer or '👀'
    return answer


def _create_button(content: dict) -> Button | None:
    """
    Button factory
    """
    if 'label' in content:
        return Button(content)


def _get_kb_builder(menu: dict, msgid: int, path: str='') -> InlineKeyboardBuilder:
    """
    Construct an InlineKeyboardBuilder object based on a given menu structure.
    Args:
        menu (dict): A dict with menu items to display.
        msgid (int): message_id to place into callback data.
        path (str, optional): A path to remember in callback data,
            to be able to find an answer for a menu item.
    """
    builder = InlineKeyboardBuilder()

    for key, val in menu.items():
        if btn := _create_button(val):
            cbd = CBD(path=path, code=key, msgid=msgid).pack()
            if menu.get('menumode') == MenuMode.ROW:
                builder.button(text=btn.content['label'], callback_data=cbd)
            else:
                builder.row(btn.as_inline(cbd))

    if path:  # build bottom row with navigation
        btns = []
        cbd = CBD(path='', code='', msgid=msgid).pack()
        btns.append(InlineKeyboardButton(text='🏠', callback_data=cbd))

        if '.' in path:
            spl = path.split('.')
            cbd = CBD(path='.'.join(spl[:-2]), code=spl[-2], msgid=msgid).pack()
            btns.append(InlineKeyboardButton(text='←', callback_data=cbd))

        builder.row(*btns)

    return builder


def _find_menu_item(menu: dict, cbd: CallbackData) -> tuple[dict, str]:
    """
    Find a button info in bot menu tree by callback data.
    """
    target = menu
    pathlist = []
    for lvlcode in cbd.path.split('.'):
        if lvlcode:
            pathlist.append(lvlcode)
            target = target.get(lvlcode)

    pathlist.append(cbd.code)
    return target.get(cbd.code), '.'.join(pathlist)


@log
@handle_error
async def user_btn_handler(call: agtypes.CallbackQuery, *args, **kwargs):
    """
    A callback for any button shown to a user.
    """
    msg = call.message
    bot, chat = msg.bot, msg.chat
    cbd = CBD.unpack(call.data)
    menuitem, path = _find_menu_item(bot.menu, cbd)
    sentmsg = None

    if not cbd.path and not cbd.code:  # main menu
        sentmsg = await edit_or_send_new_msg_with_keyboard(bot, chat.id, cbd, bot.menu)

    elif btn := _create_button(menuitem):
        if btn.mode == ButtonMode.MENU:
            sentmsg = await edit_or_send_new_msg_with_keyboard(bot, chat.id, cbd, menuitem, path)
        elif btn.mode == ButtonMode.FILE:
            sentmsg = await send_file(bot, chat.id, menuitem)
        elif btn.mode == ButtonMode.ANSWER:
            sentmsg = await msg.answer(btn.answer)
        elif btn.mode == ButtonMode.SUBJECT:
            sentmsg = await set_subject(bot, chat, menuitem)

    await save_for_destruction(sentmsg, bot)

    return await call.answer()


@log
@handle_error
async def admin_btn_handler(call: agtypes.CallbackQuery, *args, **kwargs):
    """
    A callback for any button shown in admin group.
    """
    if not await may_use_admin_actions(call.message.bot, call.from_user):
        return await call.answer('Only group admins can do this', show_alert=True)

    cbd = CBD.unpack(call.data)

    if cbd.code == AdminBtn.DEL_OLD_TOPICS:
        await del_old_topics(call)
    elif cbd.code == AdminBtn.BROADCAST:
        await admin_broadcast_start(call, kwargs['dispatcher'])
    elif cbd.code == AdminBtn.SETTINGS:
        await bot_settings(call)

    return await call.answer()


async def send_file(bot: 'SupportBot', chat_id: int, menuitem: dict) -> agtypes.Message:
    """
    Shortcut for sending a file on a button press.
    """
    fpath = bot.botdir / 'files' / menuitem['file']
    if fpath.is_file():
        doc = agtypes.FSInputFile(fpath)
        caption = _extract_answer(menuitem, empty=True)
        return await bot.send_document(chat_id, document=doc, caption=caption)

    raise FileNotFoundError(fpath.resolve())


async def set_subject(bot: 'SupportBot', user: agtypes.Chat, menuitem: dict) -> agtypes.Message:
    """
    Set the chosen subject to the user and report that.
    """
    newsubj = menuitem['subject']
    group_id = bot.cfg.admin_group_id

    answer = (menuitem.get('answer') or '')[:MSG_TEXT_LIMIT]
    answer = answer or f'Please write your question about "{menuitem["label"]}"'
    usrmsg = await bot.send_message(user.id, text=answer)

    if tguser := await bot.db.tguser.get(user=user):
        if tguser.thread_id and tguser.subject != newsubj:
            await bot.db.tguser.update(user.id, subject=newsubj)
            answer = 'The user changed subject to <b>' + newsubj + '</b>'
            await bot.send_message(group_id, answer, message_thread_id=tguser.thread_id)

    return usrmsg


async def edit_or_send_new_msg_with_keyboard(
        bot: 'SupportBot', chat_id: int, cbd: CBD, menu: dict, path: str='') -> agtypes.Message:
    """
    Shortcut to edit a message, or,
    if it's not possible, send a new message.
    """
    text = _extract_answer(menu)
    try:
        markup = _get_kb_builder(menu, cbd.msgid, path).as_markup()
        return await bot.edit_message_text(chat_id=chat_id, message_id=cbd.msgid, text=text,
                                           reply_markup=markup)
    except TelegramBadRequest:
        return await send_new_msg_with_keyboard(bot, chat_id, text, menu, path)


async def send_new_msg_with_keyboard(
        bot: 'SupportBot', chat_id: int, text: str, menu: dict | None,
        path: str='') -> agtypes.Message:
    """
    Shortcut to send a message with a keyboard.
    """
    sentmsg = await bot.send_message(chat_id, text=text, disable_web_page_preview=True)
    if menu:
        markup = _get_kb_builder(menu, sentmsg.message_id, path).as_markup()
        await bot.edit_message_text(chat_id=chat_id, message_id=sentmsg.message_id, text=text,
                                    reply_markup=markup)
    return sentmsg


def build_confirm_menu(yes_answer: str='Confirmed', no_answer: str='Canceled') -> dict:
    """
    Shortcut to build typical confirmation keyboard
    """
    menu = {
        'yes': {'label': '✅ Yes', 'answer': yes_answer},
        'no': {'label': '🚫 No', 'answer': no_answer},
        'menumode': MenuMode.ROW,
    }
    return menu
