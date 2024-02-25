import aiogram.types as agtypes


def make_user_info(user: agtypes.User) -> str:
    """
    Text representation of a user
    """
    name = user.full_name.replace('<', '').replace('>', '')
    username = f'@{user.username}' if user.username else 'No username'
    return f'<b>{name}</b>\n\n{username}\n\nID: <code>{user.id}</code>'


def make_short_user_info(user: agtypes.User) -> str:
    """
    Short text representation of a user
    """
    name = user.full_name.replace('<', '').replace('>', '')
    tech_part = f'@{user.username}, id {user.id}' if user.username else f'id {user.id}'
    return f'<b>{name}</b> ({tech_part})'
