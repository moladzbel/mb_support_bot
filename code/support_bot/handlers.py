import aiogram.types as agtypes
from aiogram import Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command

from .informing import handle_error, log, save_admin_message, save_user_message
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

    text = f'Hello!\nID of this chat: <code>{group.id}</code>'
    if not group.is_forum:
        text += '\n\n❗ Please enable topics in the group settings'
    await msg.bot.send_message(group.id, text)


async def _new_topic(msg: agtypes.Message):
    """
    Create a new topic for the user
    """
    group_id = msg.bot.cfg['admin_group_id']
    user, bot, db = msg.chat, msg.bot, msg.bot.db

    response = await bot.create_forum_topic(group_id, user.full_name)
    thread_id = response.message_thread_id
    tguser = await db.set_tguser(user, thread_id)

    warn = '\n\n<i>Replies to any bot message in this topic will be sent to the user</i>'
    text = (await make_user_info(user, bot=bot)) + warn
    await bot.send_message(group_id, text, message_thread_id=thread_id)

    return tguser


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
    user, db = msg.chat, msg.bot.db
    tguser = await db.get_tguser(user=user) or await _new_topic(msg)

    try:
        await msg.forward(group_id, message_thread_id=tguser.thread_id)
    except TelegramBadRequest as exc:
        if 'message thread not found' in exc.message.lower():
            tguser = await _new_topic(msg)
            await msg.forward(group_id, message_thread_id=tguser.thread_id)

    await save_user_message(msg)


@log
@handle_error
async def admin_message(msg: agtypes.Message) -> None:
    """
    Copy admin reply to a user
    """
    db = msg.bot.db

    tguser = await db.get_tguser(thread_id=msg.message_thread_id)
    await msg.copy_to(tguser.user_id)

    await save_admin_message(msg, tguser)


def register_handlers(dp: Dispatcher) -> None:
    """
    Register all the handlers to the provided dispatcher
    """
    dp.message.register(user_message, PrivateChatFilter(), ~ACommandFilter())
    dp.message.register(admin_message, ~ACommandFilter(), ReplyToBotInGroupForwardedFilter())
    dp.message.register(cmd_start, PrivateChatFilter(), Command('start'))
    dp.message.register(added_to_group, NewChatMembersFilter())
    dp.message.register(group_chat_created, GroupChatCreatedFilter())
