import aiogram.types as agtypes
from aiogram import Dispatcher
from aiogram.filters import Command

from .informing import handle_error, log
from .filters import (
    ACommandFilter, GroupChatCreatedFilter, NewChatMembersFilter, PrivateChatFilter,
    ReplyToBotInGroupForwardedFilter,
)
from .utils import make_user_info


@log
@handle_error
async def cmd_start(msg: agtypes.Message) -> None:
    """
    Reply to /start
    """
    await msg.answer(msg.bot.cfg['hello_msg'], disable_web_page_preview=True)


async def _group_hello(msg: agtypes.Message):
    """
    Send group hello message to a group
    """
    group = msg.chat

    text = f'Hello everyone!\n\nID of this chat: <code>{group.id}</code>'
    if not group.is_forum:
        text += '\n\n❗ Please enable topics in the group settings'
    await msg.bot.send_message(group.id, text)


@log
@handle_error
async def added_to_group(msg: agtypes.Message):
    """
    Report group ID when added to a group
    """
    for member in msg.new_chat_members:
        if member.id == msg.bot.id:
            await _group_hello(msg)
            break


@log
@handle_error
async def group_chat_created(msg: agtypes.Message):
    """
    Report group ID when a group with the bot is created
    """
    await _group_hello(msg)


@log
@handle_error
async def user_message(msg: agtypes.Message) -> None:
    """
    Forward user message to internal admin group
    """
    group_id = msg.bot.cfg['admin_group_id']
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


@log
@handle_error
async def admin_message(msg: agtypes.Message) -> None:
    """
    Copy admin reply to a user
    """
    db = msg.bot.db

    user_id = await db.get_user_id(msg.message_thread_id)
    await msg.copy_to(user_id)


def register_handlers(dp: Dispatcher) -> None:
    """
    Register all the handlers to the provided dispatcher
    """
    dp.message.register(user_message, PrivateChatFilter(), ~ACommandFilter())
    dp.message.register(admin_message, ~ACommandFilter(), ReplyToBotInGroupForwardedFilter())
    dp.message.register(cmd_start, PrivateChatFilter(), Command('start'))
    dp.message.register(added_to_group, NewChatMembersFilter())
    dp.message.register(group_chat_created, GroupChatCreatedFilter())
