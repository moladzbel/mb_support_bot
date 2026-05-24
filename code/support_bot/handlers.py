import aiogram.types as agtypes
from aiogram import Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import ReplyParameters

from .admin_actions import BroadcastForm, admin_broadcast_ask_confirm, admin_broadcast_finish
from .buttons import admin_btn_handler, send_new_msg_with_keyboard, user_btn_handler
from .informing import handle_error, log, save_admin_message, save_user_message
from .const import SendMode
from .filters import (
    ACommandFilter, AdminMessageForUser, BtnInAdminGroup, BtnInPrivateChat, BotMention,
    GroupChatCreatedFilter, InAdminGroup, NewChatMembersFilter, PrivateChatFilter,
)
from .utils import make_user_info, save_for_destruction


@log
@handle_error
async def cmd_start(msg: agtypes.Message, *args, **kwargs) -> None:
    """
    Reply to /start
    """
    bot, user, db = msg.bot, msg.chat, msg.bot.db
    sentmsg = await send_new_msg_with_keyboard(bot, user.id, bot.cfg['hello_msg'], bot.menu)

    new_user = False
    async with bot.user_lock(user.id):
        if not await db.tguser.get(user=user):  # save user if it's new
            thread_id = await _new_topic(msg)
            await db.tguser.add(user, msg, thread_id)
            new_user = True

    await save_user_message(msg, new_user=new_user, stat=False)
    await save_for_destruction(msg, bot)
    await save_for_destruction(sentmsg, bot)


async def _group_hello(msg: agtypes.Message):
    """
    Send group hello message to a group
    """
    group = msg.chat

    text = f'Hello!\nID of this group: <code>{group.id}</code>'
    if not group.is_forum:
        text += '\n\n❗ Please enable topics in the group settings. This will also change its ID.'
    await msg.bot.send_message(group.id, text)


async def _send_reply_preface(msg: agtypes.Message, thread_id: int) -> None:
    """
    If reply_as_reply is on and the user is replying to a message we have a
    mapping for (either an earlier bot relay of an admin message, or one of
    the user's own previous messages), send a marker bot message into the
    topic anchored to the corresponding admin-side message. Falls back to an
    unanchored marker if that admin-side message no longer exists.
    """
    bot, db = msg.bot, msg.bot.db
    if not (bot.cfg['reply_as_reply'] and msg.reply_to_message):
        return

    mapping = await db.msgmap.get_by_user_msg(msg.from_user.id, msg.reply_to_message.message_id)
    if not mapping:
        return

    await bot.send_message(
        bot.cfg['admin_group_id'],
        '<i>A reply to this message</i>',
        message_thread_id=thread_id,
        reply_parameters=ReplyParameters(message_id=mapping.admin_msg_id,
                                         allow_sending_without_reply=True),
    )


async def _new_topic(msg: agtypes.Message, tguser=None) -> int:
    """
    Create a new topic for the user
    """
    group_id = msg.bot.cfg['admin_group_id']
    user, bot = msg.chat, msg.bot

    response = await bot.create_forum_topic(group_id, user.full_name)
    thread_id = response.message_thread_id

    mode = bot.cfg['send_mode']
    text = await make_user_info(user, bot=bot, tguser=tguser)

    if mode == SendMode.ALL:
        text += '\n\n<i><b>Any</b> message in this topic will be sent to the user.</i>'
    elif mode == SendMode.ALL_EXCEPT_ADMINS:
        text += ('\n\n<i><b>Any</b> message in this topic will be sent '
                 'to the user, except replies to another admin.</i>')
    elif mode == SendMode.REPLY:
        text += ('\n\n<i>Only <b>replies</b> to a bot message '
                 'in this topic will be sent to the user.</i>')

    await bot.send_message(group_id, text, message_thread_id=thread_id)
    return thread_id


@log
@handle_error
async def added_to_group(msg: agtypes.Message, *args, **kwargs):
    """
    Report group ID when added to a group
    """
    for member in msg.new_chat_members:
        if member.id == msg.bot.id:
            await _group_hello(msg)
            break


@log
@handle_error
async def group_chat_created(msg: agtypes.Message, *args, **kwargs):
    """
    Report group ID when a group with the bot is created
    """
    await _group_hello(msg)


@log
@handle_error
async def user_message(msg: agtypes.Message, *args, **kwargs) -> None:
    """
    Create topic and a user row in db if needed,
    then forward user message to internal admin group
    """
    group_id = msg.bot.cfg['admin_group_id']
    bot, user, db = msg.bot, msg.chat, msg.bot.db

    forwarded = None
    async with bot.user_lock(user.id):
        if tguser := await db.tguser.get(user=user):
            if thread_id := tguser.thread_id:
                try:
                    await _send_reply_preface(msg, thread_id)
                    forwarded = await msg.forward(group_id, message_thread_id=thread_id)
                except TelegramBadRequest as exc:  # the topic vanished for whatever reason
                    if 'thread not found' in exc.message.lower():
                        thread_id = await _new_topic(msg, tguser=tguser)
                        await _send_reply_preface(msg, thread_id)
                        forwarded = await msg.forward(group_id, message_thread_id=thread_id)
            else:
                thread_id = await _new_topic(msg, tguser=tguser)
                await _send_reply_preface(msg, thread_id)
                forwarded = await msg.forward(group_id, message_thread_id=thread_id)

            if tguser.first_replied:
                await db.tguser.update(user.id, user_msg=msg, thread_id=thread_id)
            else:
                if bot.cfg['first_reply']:
                    sentmsg = await bot.send_message(user.id, bot.cfg['first_reply'])
                    await save_for_destruction(sentmsg, bot)
                await db.tguser.update(user.id, user_msg=msg, thread_id=thread_id, first_replied=True)

        else:
            thread_id = await _new_topic(msg)
            if bot.cfg['first_reply']:
                sentmsg = await bot.send_message(user.id, bot.cfg['first_reply'])
                await save_for_destruction(sentmsg, bot)
            tguser = await db.tguser.add(user, msg, thread_id, first_replied=True)
            await _send_reply_preface(msg, thread_id)
            forwarded = await msg.forward(group_id, message_thread_id=thread_id)

        if forwarded:
            await db.msgmap.add(forwarded.message_id, user.id, msg.message_id)

    await save_user_message(msg)
    await save_for_destruction(msg, bot)


@log
@handle_error
async def admin_message(msg: agtypes.Message, *args, **kwargs) -> None:
    """
    Copy admin reply to a user. If reply_as_reply is on and the admin replied
    to a forwarded user message, anchor the copy to that user's original message.
    """
    bot, db = msg.bot, msg.bot.db

    tguser = await db.tguser.get(thread_id=msg.message_thread_id)
    if tguser is None:
        return

    reply_params = None
    if bot.cfg['reply_as_reply'] and msg.reply_to_message:
        if mapping := await db.msgmap.get(msg.reply_to_message.message_id):
            reply_params = ReplyParameters(message_id=mapping.user_msg_id,
                                           allow_sending_without_reply=True)

    copied = await msg.copy_to(tguser.user_id, reply_parameters=reply_params)
    await db.msgmap.add(msg.message_id, tguser.user_id, copied.message_id)

    await save_admin_message(msg, tguser)
    await save_for_destruction(copied, bot, chat_id=tguser.user_id)


@log
@handle_error
async def mention_in_admin_group(msg: agtypes.Message, *args, **kwargs):
    """
    Report group ID when a group with the bot is created
    """
    bot, group = msg.bot, msg.chat

    await send_new_msg_with_keyboard(bot, group.id, 'Choose:', bot.admin_menu)


def register_handlers(dp: Dispatcher) -> None:
    """
    Register all the handlers to the provided dispatcher
    """
    dp.message.register(user_message, PrivateChatFilter(), ~ACommandFilter())
    dp.message.register(admin_message, ~ACommandFilter(), AdminMessageForUser())
    dp.message.register(cmd_start, PrivateChatFilter(), Command('start'))

    dp.message.register(added_to_group, NewChatMembersFilter())
    dp.message.register(group_chat_created, GroupChatCreatedFilter())
    dp.message.register(mention_in_admin_group, BotMention(), InAdminGroup())

    dp.message.register(admin_broadcast_ask_confirm, BroadcastForm.message)
    dp.callback_query.register(admin_broadcast_finish, BroadcastForm.confirm, BtnInAdminGroup())

    dp.callback_query.register(user_btn_handler, BtnInPrivateChat())
    dp.callback_query.register(admin_btn_handler, BtnInAdminGroup())
