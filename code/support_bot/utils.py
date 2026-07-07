import datetime
import html
from typing import TYPE_CHECKING

import aiogram.types as agtypes
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.engine.row import Row as SaRow

from .const import MsgType

if TYPE_CHECKING:
    from .bot import SupportBot


async def make_user_info(user: agtypes.User, bot: 'SupportBot | None' = None,
                         tguser: SaRow | None = None) -> str:
    """
    Text representation of a user
    """
    name = f'<b>{html.escape(user.full_name)}</b>'
    username = f'@{user.username}' if user.username else 'No username'
    userid = f'<b>ID</b>: <code>{user.id}</code>'
    fields = [name, username, userid]

    if lang := getattr(user, 'language_code', None):
        fields.append(f'Language code: {lang}')
    if premium := getattr(user, 'is_premium', None):
        fields.append(f'Premium: {premium}')

    if bot:
        uinfo = await bot.get_chat(user.id)
        fields.append(f'<b>Bio</b>: {html.escape(uinfo.bio)}' if uinfo.bio else 'No bio')

        if uinfo.active_usernames and len(uinfo.active_usernames) > 1:
            fields.append(f'Active usernames: @{", @".join(uinfo.active_usernames)}')

    if tguser and tguser.subject:
        fields.append(f'<b>Subject</b>: {tguser.subject}')

    return '\n\n'.join(fields)


def make_short_user_info(user: agtypes.User | None = None, tguser: SaRow | None = None) -> str:
    """
    Short text representation of a user
    """
    if user:
        user_id = user.id
    elif tguser:
        user_id = tguser.user_id
        user = tguser

    fullname = html.escape(user.full_name or '')
    tech_part = f'@{user.username}, id {user_id}' if user.username else f'id {user_id}'
    return f'{fullname} ({tech_part})'


def determine_msg_type(msg: agtypes.Message) -> MsgType:
    """
    Determine a type of the message by inspecting its content
    """
    if msg.photo:
        return MsgType.PHOTO
    elif msg.video:
        return MsgType.VIDEO
    elif msg.animation:
        return MsgType.ANIMATION
    elif msg.sticker:
        return MsgType.STICKER
    elif msg.audio:
        return MsgType.AUDIO
    elif msg.voice:
        return MsgType.VOICE
    elif msg.document:
        return MsgType.DOCUMENT
    elif msg.video_note:
        return MsgType.VIDEO_NOTE
    elif msg.contact:
        return MsgType.CONTACT
    elif msg.location:
        return MsgType.LOCATION
    elif msg.venue:
        return MsgType.VENUE
    elif msg.poll:
        return MsgType.POLL
    elif msg.dice:
        return MsgType.DICE
    else:
        return MsgType.REGULAR_OR_OTHER


async def destruct_messages(bots: list['SupportBot']) -> None:
    """
    Delete messages for users, if a bot is set up to do so.
    A message leaves the queue when it's deleted, when Telegram rejects
    the deletion as impossible (too old, already deleted), or when it's
    past Telegram's 48-hour deletion window anyway. A message which failed
    for any other reason stays queued and is retried on the next run.
    """
    for bot in bots:
        destructed = 0
        undeletable = 0

        for var in 'destruct_user_messages_for_user', 'destruct_bot_messages_for_user':
            if val := getattr(bot.cfg, var):
                error_reported = False
                by_bot = var == 'destruct_bot_messages_for_user'
                now = datetime.datetime.utcnow()
                before = now - datetime.timedelta(hours=val)
                deadline = now - datetime.timedelta(hours=48)
                msgs = await bot.db.msgtodel.get_many(before, by_bot)

                to_remove = []
                for msg in msgs:
                    try:
                        await bot.delete_message(msg.chat_id, msg.msg_id)
                        destructed += 1
                        to_remove.append(msg)
                    except TelegramBadRequest:
                        undeletable += 1
                        to_remove.append(msg)
                    except Exception as exc:
                        if msg.sent_at <= deadline:
                            undeletable += 1
                            to_remove.append(msg)
                        if not error_reported:
                            await bot.log_error(exc)
                        error_reported = True

                await bot.db.msgtodel.remove(to_remove)

        if destructed:
            await bot.log(f'Messages destructed: {destructed}')
        if undeletable:
            await bot.log(f'Messages impossible to delete, dropped from the queue: {undeletable}')


async def sweep_user_locks(bots: list['SupportBot']) -> None:
    """
    Drop unheld per-user locks of every bot.
    Async so the scheduler runs it on the event loop rather than in a thread.
    """
    for bot in bots:
        bot.sweep_user_locks()


async def save_for_destruction(msg: agtypes.Message | agtypes.MessageId | None, bot: 'SupportBot',
                               chat_id: int | None = None) -> None:
    """
    Save msg id to destruct the msg later, if required
    """
    if not msg:
        return

    if chat_id:  # special case when there is no full msg object
        if bot.cfg.destruct_bot_messages_for_user:
            await bot.db.msgtodel.add(msg, chat_id=chat_id)
        return

    var = 'destruct_user_messages_for_user'
    if msg.from_user.is_bot:
        var = 'destruct_bot_messages_for_user'

    if getattr(bot.cfg, var):
        await bot.db.msgtodel.add(msg)
