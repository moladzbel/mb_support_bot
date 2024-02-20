import aiogram.types as agtypes
from aiogram import Dispatcher
from aiogram.filters import Command

from .filters import NewChatMembersFilter, ACommandFilter, PrivateChatFilter
from .utils import make_user_info


async def cmd_start(msg: agtypes.Message) -> None:
    """
    Reply to /start
    """
    await msg.bot.log('cmd_start')

    await msg.answer(msg.bot.cfg['hello_msg'])


async def added_to_group(msg: agtypes.Message):
    """
    Report group ID when added to a group
    """
    await msg.bot.log('added_to_group')
    user = msg.chat

    for member in msg.new_chat_members:
        if member.id == msg.bot.id:
            await msg.reply(f'Beep boop. ID of this chat: <code>{user.id}</code>')


async def user_message(msg: agtypes.Message) -> None:
    """
    Forward user message to internal group
    """
    await msg.bot.log('user_message')
    group_id = msg.bot.cfg['internal_group_id']
    user = msg.chat
    db = msg.bot.db

    if thread_id := await db.get_thread_id(user):
        pass
    else:
        response = await msg.bot.create_forum_topic(group_id, user.full_name)
        thread_id = response.message_thread_id
        await db.set_thread_id(user, thread_id)
        await msg.bot.send_message(group_id, make_user_info(user), message_thread_id=thread_id)

    await msg.forward(group_id, message_thread_id=thread_id)


def register_handlers(dp: Dispatcher) -> None:
    """
    Register all the handlers to the provided dispatcher
    """
    dp.message.register(user_message, PrivateChatFilter(), ~ACommandFilter())
    dp.message.register(cmd_start, PrivateChatFilter(), Command('start'))
    dp.message.register(added_to_group, NewChatMembersFilter())
