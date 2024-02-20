import aiogram.types as agtypes


def make_user_info(user: agtypes.User) -> str:
    """
    Text representation of a user
    """
    username = f'@{user.username}' if user.username else 'No username'
    return f'<b>{user.full_name}</b>\n\n{username}\n\nID: <code>{user.id}</code>'
