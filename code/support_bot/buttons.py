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


def _create_button(content):
    """
    Button factory
    """
    if 'label' in content:
        return Button(content)


def get_kb_builder(menu: dict, msgid: int, path: str='') -> InlineKeyboardBuilder:
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


def _find_menu_item(bot, cbd: CallbackData) -> [dict, str]:
    """
    Find a button info in bot menu tree by callback data.
    """
    target = bot.menu
    pathlist = []
    for lvlcode in cbd.path.split('.'):
        if lvlcode:
            pathlist.append(lvlcode)
            target = target.get(lvlcode)

    pathlist.append(cbd.code)
    return target.get(cbd.code), '.'.join(pathlist)


async def button_handler(call: agtypes.CallbackQuery):
    """
    A callback for any button.
    """
    msg = call.message
    bot, chat = msg.bot, msg.chat
    cbd = CBD.unpack(call.data)
    menuitem, path = _find_menu_item(bot, cbd)

    if not cbd.path and not cbd.code:
        await edit_or_send_new_msg_with_keyboard(bot, chat.id, cbd, bot.menu)
        return

    if btn := _create_button(menuitem):
        if btn.mode == 'menu':
            await edit_or_send_new_msg_with_keyboard(bot, chat.id, cbd, menuitem, path)
        elif btn.mode == 'file':
            ...  # TODO
        elif btn.mode == 'answer':
            await msg.answer(menuitem.get('answer'))

    await call.answer()


async def edit_or_send_new_msg_with_keyboard(
        bot, chat_id: int, cbd: CallbackData, menu: dict, path: str='') -> agtypes.Message:
    """
    Shortcut to edit a message, or,
    if it's not possible, send a new message.
    """
    text = menu.get('answer') or '👀'
    try:
        markup = get_kb_builder(menu, cbd.msgid, path).as_markup()
        await bot.edit_message_text(chat_id=chat_id, message_id=cbd.msgid, text=text,
                                    reply_markup=markup)
    except TelegramBadRequest:
        await send_new_msg_with_keyboard(bot, chat_id, text, menu, path)


async def send_new_msg_with_keyboard(
        bot, chat_id: int, text: str, menu: dict | None, path: str='') -> agtypes.Message:
    """
    Shortcut to send a message with a keyboard.
    """
    sentmsg = await bot.send_message(chat_id, text=text, disable_web_page_preview=True)
    if menu:
        markup = get_kb_builder(menu, sentmsg.message_id, path).as_markup()
        await bot.edit_message_text(chat_id=chat_id, message_id=sentmsg.message_id, text=text,
                                    reply_markup=markup)
    return sentmsg
