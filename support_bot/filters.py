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
    Important. Checks all the signs that it is a reply to a user,
    and that it is a allowed reply (made in another group).
    """
    async def __call__(self, msg: agtypes.Message) -> bool:
        if to_msg := msg.reply_to_message:
            by_bot = to_msg.from_user.id == msg.bot.id
            forwarded = to_msg.forward_origin is not None

            group_id = int(msg.bot.cfg['admin_group_id'])
            is_admin_group_1 = msg.chat.id == group_id
            is_admin_group_2 = to_msg.chat.id == group_id

            return by_bot and forwarded and is_admin_group_1 and is_admin_group_2
