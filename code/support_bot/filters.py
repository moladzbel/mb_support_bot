import aiogram.types as agtypes
from aiogram.enums.chat_type import ChatType
from aiogram.filters import Filter

from .const import SendMode


class PrivateChatFilter(Filter):

    async def __call__(self, msg: agtypes.Message) -> bool:
        return msg.chat.type == ChatType.PRIVATE


class NewChatMembersFilter(Filter):

    async def __call__(self, msg: agtypes.Message) -> bool:
        return bool(getattr(msg, 'new_chat_members', None))


class GroupChatCreatedFilter(Filter):

    async def __call__(self, msg: agtypes.Message) -> bool:
        return bool(getattr(msg, 'group_chat_created', None))


class ACommandFilter(Filter):

    async def __call__(self, msg: agtypes.Message) -> bool:
        return str(getattr(msg, 'text', '')).startswith('/')


class AdminMessageForUser(Filter):
    """
    Matches an admin's message in a user topic of the admin group that should
    be relayed to the user, according to the bot's send_mode:
    - REPLY: only replies to a bot message (excluding the topic header).
    - ALL: any admin message in the topic.
    - ALL_EXCEPT_ADMINS: any admin message except replies to another admin.
    The bot's own messages (topic header, forwarded user messages) are always excluded.
    """
    async def __call__(self, msg: agtypes.Message) -> bool:
        if msg.chat.id != int(msg.bot.cfg['admin_group_id']):
            return False
        if not msg.message_thread_id:
            return False
        if msg.from_user and msg.from_user.id == msg.bot.id:
            return False

        to_msg = msg.reply_to_message
        is_reply_to_bot = bool(
            to_msg
            and to_msg.from_user.id == msg.bot.id
            and to_msg.message_id != msg.message_thread_id
        )
        is_reply_to_admin = bool(to_msg and to_msg.from_user.id != msg.bot.id)

        mode = msg.bot.cfg['send_mode']
        if mode == SendMode.reply:
            return is_reply_to_bot
        if mode == SendMode.all:
            return True
        if mode == SendMode.all_except_admins:
            return not is_reply_to_admin
        return False


class InAdminGroup(Filter):
    """
    Checks that a message posted in the admin group,
    in General topic (message_thread_id is None)
    """
    async def __call__(self, msg: agtypes.Message) -> bool:
        is_admin_group = msg.chat.id == int(msg.bot.cfg['admin_group_id'])
        return is_admin_group and not msg.message_thread_id


class BotMention(Filter):
    """
    Checks it is a bot's mention, only
    """
    async def __call__(self, msg: agtypes.Message) -> bool:
        me = await msg.bot.me()
        return msg.text == f'@{me.username}'


class BtnInAdminGroup(Filter):
    """
    Checks that a message posted in the admin group
    """
    async def __call__(self, call: agtypes.CallbackQuery) -> bool:
        msg = call.message
        return msg.chat.id == int(msg.bot.cfg['admin_group_id'])


class BtnInPrivateChat(Filter):

    async def __call__(self, call: agtypes.CallbackQuery) -> bool:
        msg = call.message
        return msg.chat.type == ChatType.PRIVATE
