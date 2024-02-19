import aiogram.types as agtypes
from aiogram import Dispatcher
from aiogram.enums.chat_type import ChatType
from aiogram.filters import CommandStart


async def cmd_start(msg: agtypes.Message) -> None:
    """
    Reply to /start
    """
    if msg.chat.type == ChatType.PRIVATE:
        await msg.answer(f"Hello, {msg.from_user.full_name}!")


async def added_to_group(msg: agtypes.Message):
    if getattr(msg, 'new_chat_members', None):
        for member in msg.new_chat_members:
            if member.id == msg.bot.id:
                await msg.reply(f'ID of this chat: <code>{msg.chat.id}</code>')


def register_handlers(dp: Dispatcher) -> None:
    """
    Register all the handlers to the provided dispatcher
    """
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(added_to_group)
