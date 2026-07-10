from collections.abc import Awaitable
from typing import TYPE_CHECKING

import aiogram.types as agtypes
from aiogram import Dispatcher, F
from aiogram.enums.chat_type import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import ReactionTypeEmoji, ReplyParameters
from sqlalchemy.engine.row import Row as SaRow

from .admin_actions import (
    BroadcastForm, admin_broadcast_ask_confirm, admin_broadcast_cancel, admin_broadcast_finish,
)
from .buttons import (
    CBD, admin_btn_handler, build_ban_menu, send_new_msg_with_keyboard, user_btn_handler,
)
from .informing import handle_error, log, save_admin_message, save_user_message
from .const import SendMode
from .filters import (
    ACommandFilter, AdminMessageForUser, BtnInAdminGroup, BtnInPrivateChat, BotMention,
    GroupChatCreatedFilter, InAdminGroup, NewChatMembersFilter, PrivateChatFilter,
)
from .utils import make_user_info, may_use_admin_actions, save_for_destruction

if TYPE_CHECKING:
    from .bot import SupportBot


@log
@handle_error
async def cmd_start(msg: agtypes.Message, *args, **kwargs) -> None:
    """
    Reply to /start
    """
    bot, user, db = msg.bot, msg.chat, msg.bot.db
    sentmsg = await send_new_msg_with_keyboard(bot, user.id, bot.cfg.hello_msg, bot.menu)

    new_user = False
    async with bot.user_lock(user.id):
        if not await db.tguser.get(user=user):  # save user if it's new
            thread_id = await _new_topic(msg)
            await db.tguser.add(user, msg, thread_id)
            new_user = True

    await save_user_message(msg, new_user=new_user, stat=False)
    await save_for_destruction(msg, bot)
    await save_for_destruction(sentmsg, bot)


async def _group_hello(msg: agtypes.Message) -> None:
    """
    Send group hello message to a group
    """
    group = msg.chat

    text = f'Hello!\nID of this group: <code>{group.id}</code>'
    if not group.is_forum:
        text += '\n\n❗ Please enable topics in the group settings. This will also change its ID.'
    await msg.bot.send_message(group.id, text)


async def _send_into_topic(bot: 'SupportBot', group_id: int, thread_id: int,
                           coro: Awaitable[agtypes.Message]) -> agtypes.Message | None:
    """
    Run a send/forward coroutine targeting a topic and confirm Telegram placed
    the result in that topic. If the topic was deleted, Telegram may silently
    route the message to General instead of raising. Detect that case, delete
    the stray, and return None so the caller can recover.
    """
    try:
        sent = await coro
    except TelegramBadRequest as exc:
        if 'thread not found' in exc.message.lower():
            return None
        raise
    if sent.message_thread_id != thread_id:
        try:
            await bot.delete_message(group_id, sent.message_id)
        except TelegramBadRequest:
            pass
        return None
    return sent


async def _send_reply_preface(msg: agtypes.Message, thread_id: int) -> None:
    """
    If mirror_replies is on and the user is replying to a message we have a
    mapping for (either an earlier bot relay of an admin message, or one of
    the user's own previous messages), send a marker bot message into the
    topic anchored to the corresponding admin-side message. Falls back to an
    unanchored marker if that admin-side message no longer exists.
    """
    bot, db = msg.bot, msg.bot.db
    if not (bot.cfg.mirror_replies and msg.reply_to_message):
        return

    mapping = await db.msgmap.get_by_user_msg(msg.from_user.id, msg.reply_to_message.message_id)
    if not mapping:
        return

    group_id = bot.cfg.admin_group_id
    coro = bot.send_message(
        group_id,
        ' ㅤ ',
        message_thread_id=thread_id,
        reply_parameters=ReplyParameters(message_id=mapping.admin_msg_id,
                                         allow_sending_without_reply=True),
    )
    await _send_into_topic(bot, group_id, thread_id, coro)


async def _new_topic(msg: agtypes.Message, tguser: SaRow | None = None) -> int:
    """
    Create a new topic for the user
    """
    group_id = msg.bot.cfg.admin_group_id
    user, bot = msg.chat, msg.bot

    response = await bot.create_forum_topic(group_id, user.full_name)
    thread_id = response.message_thread_id

    mode = bot.cfg.send_mode
    text = await make_user_info(user, bot=bot, tguser=tguser)

    if mode == SendMode.ALL:
        text += '\n\n<i><b>Any</b> message in this topic will be sent to the user.</i>'
    elif mode == SendMode.ALL_EXCEPT_ADMINS:
        text += ('\n\n<i><b>Any</b> message in this topic will be sent '
                 'to the user, except replies to another admin.</i>')
    elif mode == SendMode.REPLY:
        text += ('\n\n<i>Only <b>replies</b> to a bot message '
                 'in this topic will be sent to the user.</i>')

    banned = bool(tguser and tguser.banned)
    sentmsg = await send_new_msg_with_keyboard(bot, group_id, text, build_ban_menu(banned),
                                               thread_id=thread_id)
    try:
        await bot.pin_chat_message(group_id, sentmsg.message_id, disable_notification=True)
    except TelegramBadRequest as exc:  # no "Pin messages" right must not break topic creation
        await bot.log_error(exc, traceback=False)

    return thread_id


@log
@handle_error
async def added_to_group(msg: agtypes.Message, *args, **kwargs) -> None:
    """
    Report group ID when added to a group
    """
    for member in msg.new_chat_members:
        if member.id == msg.bot.id:
            await _group_hello(msg)
            break


@log
@handle_error
async def group_chat_created(msg: agtypes.Message, *args, **kwargs) -> None:
    """
    Report group ID when a group with the bot is created
    """
    await _group_hello(msg)


async def _preface_and_forward(msg: agtypes.Message, thread_id: int) -> agtypes.Message | None:
    """
    Send the optional reply-context preface, then forward the user's message
    into the topic. Returns the forwarded Message, or None if the topic
    appears to be dead so the caller can recreate it and retry.
    """
    bot = msg.bot
    group_id = bot.cfg.admin_group_id

    await _send_reply_preface(msg, thread_id)
    coro = msg.forward(group_id, message_thread_id=thread_id)
    return await _send_into_topic(bot, group_id, thread_id, coro)


@log
@handle_error
async def user_message(msg: agtypes.Message, *args, **kwargs) -> None:
    """
    Create or reuse the user's row and admin-group topic,
    then forward the user message there.
    """
    bot, user, db = msg.bot, msg.chat, msg.bot.db

    async with bot.user_lock(user.id):
        tguser = await db.tguser.get(user=user)
        if tguser and tguser.banned:
            return
        thread_id = tguser.thread_id if tguser else None

        forwarded = None
        if thread_id:
            forwarded = await _preface_and_forward(msg, thread_id)
            if forwarded is None:  # topic was deleted
                thread_id = None

        if not thread_id:
            thread_id = await _new_topic(msg, tguser=tguser)
            forwarded = await _preface_and_forward(msg, thread_id)

        if (tguser is None or not tguser.first_replied) and bot.cfg.first_reply:
            sentmsg = await bot.send_message(user.id, bot.cfg.first_reply)
            await save_for_destruction(sentmsg, bot)

        if tguser:
            await db.tguser.update(user.id, user_msg=msg, thread_id=thread_id, first_replied=True)
        else:
            await db.tguser.add(user, msg, thread_id, first_replied=True)

        if forwarded:
            await db.msgmap.add(forwarded.message_id, user.id, msg.message_id)

    await save_user_message(msg)
    await save_for_destruction(msg, bot)


@log
@handle_error
async def admin_message(msg: agtypes.Message, *args, **kwargs) -> None:
    """
    Copy admin reply to a user. If mirror_replies is on and the admin replied
    to a forwarded user message, anchor the copy to that user's original message.
    """
    bot, db = msg.bot, msg.bot.db

    tguser = await db.tguser.get(thread_id=msg.message_thread_id)
    if tguser is None or tguser.banned:
        return

    reply_params = None
    if bot.cfg.mirror_replies and msg.reply_to_message:
        if mapping := await db.msgmap.get(msg.reply_to_message.message_id):
            reply_params = ReplyParameters(message_id=mapping.user_msg_id,
                                           allow_sending_without_reply=True)

    copied = await msg.copy_to(tguser.user_id, reply_parameters=reply_params)
    await db.msgmap.add(msg.message_id, tguser.user_id, copied.message_id)

    await save_admin_message(msg, tguser)
    await save_for_destruction(copied, bot, chat_id=tguser.user_id)


@log
@handle_error
async def user_edited_message(msg: agtypes.Message, *args, **kwargs) -> None:
    """
    When a user edits a message, its counterpart in the admin topic is a
    forward, which Telegram forbids editing. So mark the original forward
    with a reply, then copy the edited version into the topic.
    """
    bot, user, db = msg.bot, msg.chat, msg.bot.db

    mapping = await db.msgmap.get_by_user_msg(user.id, msg.message_id)
    if not mapping:
        return
    tguser = await db.tguser.get(user=user)
    if not (tguser and tguser.thread_id) or tguser.banned:
        return

    group_id, thread_id = bot.cfg.admin_group_id, tguser.thread_id
    coro = bot.send_message(
        group_id,
        '✏️ Edited to:',
        message_thread_id=thread_id,
        reply_parameters=ReplyParameters(message_id=mapping.admin_msg_id,
                                         allow_sending_without_reply=True),
    )
    if await _send_into_topic(bot, group_id, thread_id, coro):
        await msg.copy_to(group_id, message_thread_id=thread_id)


@log
@handle_error
async def admin_edited_message(msg: agtypes.Message, *args, **kwargs) -> None:
    """
    When an admin edits a relayed message, edit its copy on the user side.
    The copy is a bot message, so text and captions can be edited in place;
    media replacement is not mirrored.
    """
    bot, db = msg.bot, msg.bot.db

    mapping = await db.msgmap.get(msg.message_id)
    if not mapping:
        return
    tguser = await db.tguser.get(user_id=mapping.user_id)
    if tguser and tguser.banned:
        return

    try:
        if msg.text:
            await bot.edit_message_text(msg.html_text, chat_id=mapping.user_id,
                                        message_id=mapping.user_msg_id)
        elif msg.caption:
            await bot.edit_message_caption(chat_id=mapping.user_id,
                                           message_id=mapping.user_msg_id,
                                           caption=msg.html_text)
    except TelegramBadRequest as exc:
        if "can't be edited" in exc.message.lower():
            await msg.reply('⚠️ After 48 hours, edits cannot be delivered to the user')
        elif 'not modified' not in exc.message.lower():
            raise


def _mirror_reaction(update: agtypes.MessageReactionUpdated) -> list[ReactionTypeEmoji]:
    """
    The reaction to mirror to the other side: a single standard emoji, or an
    empty list to clear (when the reaction was removed or is a custom emoji,
    which bots can't set).
    """
    for reaction in update.new_reaction:
        if isinstance(reaction, ReactionTypeEmoji):
            return [ReactionTypeEmoji(emoji=reaction.emoji)]
    return []


@log
@handle_error
async def reaction_changed(update: agtypes.MessageReactionUpdated, *args, **kwargs) -> None:
    """
    Mirror a reaction between a user message and its counterpart in the admin
    topic, in either direction, using the message_map pairing.
    """
    bot, db = update.bot, update.bot.db
    if not bot.cfg.mirror_reactions:
        return

    reaction = _mirror_reaction(update)

    if update.chat.type == ChatType.PRIVATE:  # user -> admin
        mapping = await db.msgmap.get_by_user_msg(update.chat.id, update.message_id)
        target = (bot.cfg.admin_group_id, mapping.admin_msg_id) if mapping else None
    elif update.chat.id == bot.cfg.admin_group_id:  # admin -> user
        if not update.user:  # anonymous admin, nobody to attribute it to
            return
        mapping = await db.msgmap.get(update.message_id)
        target = (mapping.user_id, mapping.user_msg_id) if mapping else None
        if mapping:
            tguser = await db.tguser.get(user_id=mapping.user_id)
            if tguser and tguser.banned:
                return
    else:
        return

    if not target:
        return

    await bot.set_message_reaction(target[0], target[1], reaction=reaction)


@log
@handle_error
async def mention_in_admin_group(msg: agtypes.Message, *args, **kwargs) -> None:
    """
    Show the admin menu on the bot's mention
    """
    bot, group = msg.bot, msg.chat

    if not await may_use_admin_actions(bot, msg.from_user):
        await msg.reply('Only group admins can do this')
        return

    await send_new_msg_with_keyboard(bot, group.id, 'Choose:', bot.admin_menu)


def register_handlers(dp: Dispatcher) -> None:
    """
    Register all the handlers to the provided dispatcher
    """
    dp.message.register(user_message, PrivateChatFilter(), ~ACommandFilter())
    dp.message.register(admin_message, ~ACommandFilter(), AdminMessageForUser())
    dp.message.register(cmd_start, PrivateChatFilter(), Command('start'))

    dp.edited_message.register(user_edited_message, PrivateChatFilter(), ~ACommandFilter())
    dp.edited_message.register(admin_edited_message, ~ACommandFilter(), AdminMessageForUser())

    dp.message.register(added_to_group, NewChatMembersFilter())
    dp.message.register(group_chat_created, GroupChatCreatedFilter())
    dp.message.register(mention_in_admin_group, BotMention(), InAdminGroup())

    dp.message.register(admin_broadcast_ask_confirm, BroadcastForm.message)
    dp.callback_query.register(admin_broadcast_cancel, BroadcastForm.message, BtnInAdminGroup(),
                               CBD.filter(F.code == 'cancel'))
    dp.callback_query.register(admin_broadcast_finish, BroadcastForm.confirm, BtnInAdminGroup())

    dp.callback_query.register(user_btn_handler, BtnInPrivateChat())
    dp.callback_query.register(admin_btn_handler, BtnInAdminGroup())

    dp.message_reaction.register(reaction_changed)
