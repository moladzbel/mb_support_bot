import datetime
import html

import aiogram.types as agtypes

from .const import MsgType


async def make_user_info(user: agtypes.User, bot=None, tguser=None) -> str:
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


def make_short_user_info(user: agtypes.User | None=None, tguser=None) -> str:
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


def determine_msg_type(msg: agtypes.Message) -> str:
    """
    Determine a type of the message by inspecting its content
    """
    if msg.photo:
        return MsgType.photo
    elif msg.video:
        return MsgType.video
    elif msg.animation:
        return MsgType.animation
    elif msg.sticker:
        return MsgType.sticker
    elif msg.audio:
        return MsgType.audio
    elif msg.voice:
        return MsgType.voice
    elif msg.document:
        return MsgType.document
    elif msg.video_note:
        return MsgType.video_note
    elif msg.contact:
        return MsgType.contact
    elif msg.location:
        return MsgType.location
    elif msg.venue:
        return MsgType.venue
    elif msg.poll:
        return MsgType.poll
    elif msg.dice:
        return MsgType.dice
    else:
        return MsgType.regular_or_other


async def destruct_messages(bots: list) -> None:
    """
    Delete messages for users, if a bot is set up to do so
    """
    for bot in bots:
        destructed = 0

        for var in 'destruct_user_messages_for_user', 'destruct_bot_messages_for_user':
            if val := bot.cfg.get(var):
                error_reported = False
                by_bot = var == 'destruct_bot_messages_for_user'
                before = datetime.datetime.utcnow() - datetime.timedelta(hours=val)
                msgs = await bot.db.msgtodel.get_many(before, by_bot)

                for msg in msgs:
                    try:
                        await bot.delete_message(msg.chat_id, msg.msg_id)
                        destructed += 1
                    except Exception as exc:
                        if not error_reported:
                            await bot.log_error(exc)
                        error_reported = True

                await bot.db.msgtodel.remove(msgs)

        if destructed:
            await bot.log(f'Messages destructed: {destructed}')


async def save_for_destruction(msg, bot, chat_id=None):
    """
    Save msg id to destruct the msg later, if required
    """
    if not msg:
        return

    if chat_id:  # special case when there is no full msg object
        if bot.cfg.get('destruct_bot_messages_for_user'):
            await bot.db.msgtodel.add(msg, chat_id=chat_id)
        return

    var = 'destruct_user_messages_for_user'
    if msg.from_user.is_bot:
        var = 'destruct_bot_messages_for_user'

    if bot.cfg.get(var):
        await bot.db.msgtodel.add(msg)
