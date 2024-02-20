import aiogram.types as agtypes
from aiogram.enums.chat_type import ChatType
from aiogram.filters import Filter


class PrivateChatFilter(Filter):

    async def __call__(self, msg: agtypes.Message) -> bool:
        return msg.chat.type == ChatType.PRIVATE


class NewChatMembersFilter(Filter):

    async def __call__(self, msg: agtypes.Message) -> bool:
        return bool(getattr(msg, 'new_chat_members', None))


class ACommandFilter(Filter):

    async def __call__(self, msg: agtypes.Message) -> bool:
        return str(getattr(msg, 'text', '')).startswith('/')
