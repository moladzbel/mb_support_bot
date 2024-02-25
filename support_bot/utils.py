import aiogram.types as agtypes


def make_user_info(user: agtypes.User) -> str:
    """
    Text representation of a user
    """
    username = f'@{user.username}' if user.username else 'No username'
    return f'<b>{user.full_name}</b>\n\n{username}\n\nID: <code>{user.id}</code>'


def make_short_user_info(user: agtypes.User) -> str:
    """
    Short text representation of a user
    """
    tech_part = f'@{user.username}, id {user.id}' if user.username else f'id {user.id}'
    return f'<b>{user.full_name}</b> ({tech_part})'
