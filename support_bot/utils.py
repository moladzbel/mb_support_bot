import aiogram.types as agtypes


async def make_user_info(user: agtypes.User, bot=None) -> str:
    """
    Text representation of a user
    """
    name = f'<b>{clean_html(user.full_name)}</b>'
    username = f'@{user.username}' if user.username else 'No username'
    userid = f'<b>ID</b>: <code>{user.id}</code>'
    fields = [name, username, userid]

    if lang := getattr(user, 'language_code', None):
        fields.append(f'Language code: {lang}')
    if premium := getattr(user, 'is_premium', None):
        fields.append(f'Premium: {premium}')

    if bot:
        userinfo = await bot.get_chat(user.id)
        fields.append(f'<b>Bio</b>: {clean_html(userinfo.bio)}' if userinfo.bio else 'No bio')

        if userinfo.active_usernames and len(userinfo.active_usernames) > 1:
            fields.append(f'Active usernames: @{", @".join(userinfo.active_usernames)}')

    return '\n\n'.join(fields)


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
