from aiogram import Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message


async def start_handler(message: Message) -> None:
    """
    Reply to /start
    """
    await message.answer(f"Hello, {message.from_user.full_name}!")


def register_handlers(dp: Dispatcher) -> None:
    """
    Register all the handlers to the provided dispatcher
    """
    dp.message.register(start_handler, CommandStart())
