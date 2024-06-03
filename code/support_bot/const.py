MSG_TEXT_LIMIT = 4096


class MsgType:
    photo = 'photo'
    video = 'video'
    animation = 'animation'
    sticker = 'sticker'
    audio = 'audio'
    voice = 'voice'
    document = 'document'
    video_note = 'video_note'
    contact = 'contact'
    location = 'location'
    venue = 'venue'
    poll = 'poll'
    dice = 'dice'
    regular_or_other = 'regular/other'


class AdminBtn:
    del_old_topics = 'del_old_topics'
    broadcast = 'broadcast'


class ButtonMode:
    link = 'link'  # open a link
    file = 'file'  # send a file
    menu = 'menu'  # open another menu
    answer = 'answer'  # send an answer message
    subject = 'subject'  # set a subject matter


class MenuMode:
    column = 'column'
    row = 'row'
