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
