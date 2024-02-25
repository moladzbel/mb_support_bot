import logging

import aiogram.types as agtypes
from aiogram import Dispatcher
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command

from .filters import (
    ACommandFilter, NewChatMembersFilter, PrivateChatFilter, ReplyToBotInGroupForwardedFilter,
)
from .utils import make_user_info


def logg(func):
    """
    Log action name without user data,
    and possible exceptions
    """
    async def wrapper(msg: agtypes.Message):
        await msg.bot.log(func.__name__)

        try:
            return await func(msg)
        except TelegramForbiddenError as exc:
            await report_user_ban(msg)
        except TelegramBadRequest as exc:
            if 'not enough rights to create a topic' in exc.message:
                await report_cant_create_topic(msg)
        except Exception as exc:
            await msg.bot.log_error(exc)

    return wrapper


@logg
async def report_user_ban(msg: agtypes.Message) -> None:
    """
    Report when the user banned the bot
    """
    thread_id = msg.message_thread_id
    if user_id := await msg.bot.db.get_user_id(thread_id):
        group_id = msg.bot.cfg['admin_group_id']
        await msg.bot.send_message(
            group_id, 'The user banned the bot', message_thread_id=thread_id,
        )


@logg
async def report_cant_create_topic(msg: agtypes.Message) -> None:
    """
    Report when the bot can't create a topic
    """
    await msg.bot.send_message(
        msg.bot.cfg['admin_group_id'],
        ('The bot has not enough rights to create a topic.\n\n️️️❗ '
         'Make the bot admin, and give it a "Create topics" permission.'),
    )


@logg
async def cmd_start(msg: agtypes.Message) -> None:
    """
    Reply to /start
    """
    await msg.answer(msg.bot.cfg['hello_msg'])


@logg
async def added_to_group(msg: agtypes.Message):
    """
    Report group ID when added to a group
    """
    group = msg.chat

    for member in msg.new_chat_members:
        if member.id == msg.bot.id:
            text = f'Hello everyone!\n\nID of this chat: <code>{group.id}</code>'
            if not group.is_forum:
                text += '\n\n❗ Please enable topics in the group settings'
            await msg.bot.send_message(group.id, text)


@logg
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


@logg
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
