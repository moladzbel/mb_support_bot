import enum


MSG_TEXT_LIMIT = 4096


class BaseEnum(str, enum.Enum):
    """
    Base class for string-valued enums. Members are usable as plain strings,
    and str(member) yields the underlying value.
    """
    def __str__(self) -> str:
        return self.value

    @classmethod
    def validate(cls, value, raise_exc: bool=False) -> bool:
        is_valid = any(value == member.value for member in cls)
        if not is_valid and raise_exc:
            raise ValueError(f'{value} is not one of {", ".join(cls)}')
        return is_valid


class MsgType(BaseEnum):
    PHOTO = 'photo'
    VIDEO = 'video'
    ANIMATION = 'animation'
    STICKER = 'sticker'
    AUDIO = 'audio'
    VOICE = 'voice'
    DOCUMENT = 'document'
    VIDEO_NOTE = 'video_note'
    CONTACT = 'contact'
    LOCATION = 'location'
    VENUE = 'venue'
    POLL = 'poll'
    DICE = 'dice'
    REGULAR_OR_OTHER = 'regular/other'


class AdminBtn(BaseEnum):
    DEL_OLD_TOPICS = 'del_old_topics'
    BROADCAST = 'broadcast'


class ButtonMode(BaseEnum):
    LINK = 'link'  # open a link
    FILE = 'file'  # send a file
    MENU = 'menu'  # open another menu
    ANSWER = 'answer'  # send an answer message
    SUBJECT = 'subject'  # set a subject matter


class MenuMode(BaseEnum):
    COLUMN = 'column'
    ROW = 'row'


class SendMode(BaseEnum):
    REPLY = 'reply'
    ALL = 'all'
    ALL_EXCEPT_ADMINS = 'all_except_admins'
