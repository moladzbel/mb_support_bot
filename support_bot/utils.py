import aiogram.types as agtypes


async def make_user_info(user: agtypes.User, bot=None) -> str:
    """
    Text representation of a user
    """
    name = clean_html(user.full_name)
    username = f'@{user.username}' if user.username else 'No username'

    bio = 'No bio'
    if bot:
        user_info = await bot.get_chat(user.id)
        bio = f'Bio: {user_info.bio}' if user_info.bio else bio
    bio = clean_html(bio)

    return f'<b>{name}</b>\n\n{username}\n\nID: <code>{user.id}</code>\n\n{bio}'


def make_short_user_info(user: agtypes.User) -> str:
    """
    Short text representation of a user
    """
    name = user.full_name.replace('<', '').replace('>', '')
    tech_part = f'@{user.username}, id {user.id}' if user.username else f'id {user.id}'
    return f'<b>{name}</b> ({tech_part})'


def clean_html(string):
    for char in '<>/\\':
        string = string.replace(char, '')
    return string
