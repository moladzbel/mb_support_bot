import aiogram.types as agtypes
from aiogram.enums.chat_type import ChatType
from aiogram.filters import Filter


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


class ReplyToBotInGroupForwardedFilter(Filter):
    """
    Checks that:
    - it is a reply to a user
    - made in the right group
    - reply to a bot message
    """
    async def __call__(self, msg: agtypes.Message) -> bool:
        if to_msg := msg.reply_to_message:
            by_bot = to_msg.from_user.id == msg.bot.id
            not_topic_reply = to_msg.message_id != msg.message_thread_id

            group_id = int(msg.bot.cfg['admin_group_id'])
            is_admin_group_1 = msg.chat.id == group_id
            is_admin_group_2 = to_msg.chat.id == group_id

            return by_bot and not_topic_reply and is_admin_group_1 and is_admin_group_2


class MessageInAdminTopic(Filter):
    """
    Matches any message posted by an admin in a user topic of the admin group,
    when forward_all_topic_messages is enabled. Excludes the bot's own messages
    (topic header, forwarded user messages) and replies to other admins.
    """
    async def __call__(self, msg: agtypes.Message) -> bool:
        if not msg.bot.cfg.get('forward_all_topic_messages'):
            return False
        if msg.chat.id != int(msg.bot.cfg['admin_group_id']):
            return False
        if not msg.message_thread_id:
            return False
        if msg.from_user and msg.from_user.id == msg.bot.id:
            return False
        if (to_msg := msg.reply_to_message) and to_msg.from_user.id != msg.bot.id:
            return False
        return True


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
