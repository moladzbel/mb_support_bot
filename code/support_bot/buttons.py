"""
Display menu with buttons according to menu.toml file,
handle buttons actions
"""
from pathlib import Path

import aiogram.types as agtypes
import toml
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .const import MSG_TEXT_LIMIT, AdminBtn
from .informing import handle_error, log


def load_toml(path: Path) -> dict | None:
    """
    Read toml file
    """
    if path.is_file():
        with open(path) as f:
            return toml.load(f)


class CBD(CallbackData, prefix='_'):
    """
    Callback Data
    """
    path: str  # separated inside by '.'
    code: str  # button identifier after the path
    msgid: int  # id of a message with this button


class Button:

    def __init__(self, content):
        self.content = content
        self._recognize_mode()

        empty_answer_allowed = self.mode in ('link', 'file')
        self.answer = _extract_answer(content, empty=empty_answer_allowed)

    def _recognize_mode(self) -> None:
        if 'link' in self.content:
            self.mode = 'link'
        elif 'file' in self.content:
            self.mode = 'file'
        elif any(['label' in v for v in self.content.values()]):
            self.mode = 'menu'
        elif 'answer' in self.content:
            self.mode = 'answer'

    def as_inline(self, callback_data : str=None) -> InlineKeyboardButton:
        if self.mode in ('file', 'answer', 'menu'):
            return InlineKeyboardButton(text=self.content['label'], callback_data=callback_data)
        elif self.mode == 'link':
            return InlineKeyboardButton(text=self.content['label'], url=self.content['link'])
        raise ValueError('Unexpected button mode')


def _extract_answer(menu: dict, empty: bool=False) -> str:
    answer = (menu.get('answer') or '')[:MSG_TEXT_LIMIT]
    if not empty:
        answer = answer or '👀'
    return answer


def _create_button(content):
    """
    Button factory
    """
    if 'label' in content:
        return Button(content)


def _get_kb_builder(menu: dict, msgid: int, path: str='') -> InlineKeyboardBuilder:
    """
    Constructs an InlineKeyboardBuilder object based on a given menu structure.
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


def _find_menu_item(menu: dict, cbd: CallbackData) -> [dict, str]:
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
async def user_btn_handler(call: agtypes.CallbackQuery):
    """
    A callback for any button shown to a user.
    """
    msg = call.message
    bot, chat = msg.bot, msg.chat
    cbd = CBD.unpack(call.data)
    menuitem, path = _find_menu_item(bot.menu, cbd)

    if not cbd.path and not cbd.code:  # main menu
        await edit_or_send_new_msg_with_keyboard(bot, chat.id, cbd, bot.menu)

    elif btn := _create_button(menuitem):
        if btn.mode == 'menu':
            await edit_or_send_new_msg_with_keyboard(bot, chat.id, cbd, menuitem, path)
        elif btn.mode == 'file':
            await send_file(bot, chat.id, menuitem)
        elif btn.mode == 'answer':
            await msg.answer(btn.answer)

    return await call.answer()


@log
@handle_error
async def admin_btn_handler(call: agtypes.CallbackQuery):
    """
    A callback for any button shown in admin group.
    """
    cbd = CBD.unpack(call.data)

    if cbd.code == AdminBtn.del_old_topics:
        await del_old_topics(call)

    return await call.answer()


async def del_old_topics(call: agtypes.CallbackQuery):
    """
    Admin action - delete topics older than 2 weeks,
    and delete their thread ids from DB
    """
    msg = call.message
    bot, db = msg.bot, msg.bot.db
    await msg.answer(bot.admin_menu[AdminBtn.del_old_topics]['answer'])

    i = 0
    for tguser in await db.get_old_tgusers():
        if tguser.thread_id:
            await bot.delete_forum_topic(bot.cfg['admin_group_id'], tguser.thread_id)
            await db.tguser_del_thread_id(tguser.user_id)
            i += 1

    emo = '😐' if i == 0 else '🫡'
    end = '' if i == 1 else 's'
    await msg.answer(f'Deleted {i} topic{end} {emo}')


async def send_file(bot, chat_id: int, menuitem: dict):
    """
    Shortcut for sending file on a button press.
    """
    fpath = bot.botdir / 'files' / menuitem['file']
    if fpath.is_file():
        doc = agtypes.FSInputFile(fpath)
        caption = _extract_answer(menuitem, empty=True)
        return await bot.send_document(chat_id, document=doc, caption=caption)

    raise FileNotFoundError(fpath)


async def edit_or_send_new_msg_with_keyboard(
        bot, chat_id: int, cbd: CallbackData, menu: dict, path: str='') -> agtypes.Message:
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
        bot, chat_id: int, text: str, menu: dict | None, path: str='') -> agtypes.Message:
    """
    Shortcut to send a message with a keyboard.
    """
    sentmsg = await bot.send_message(chat_id, text=text, disable_web_page_preview=True)
    if menu:
        markup = _get_kb_builder(menu, sentmsg.message_id, path).as_markup()
        await bot.edit_message_text(chat_id=chat_id, message_id=sentmsg.message_id, text=text,
                                    reply_markup=markup)
    return sentmsg
