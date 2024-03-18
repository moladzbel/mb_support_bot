"""
A package for system messages:
technical informing in chats, writing logs
"""
import aiogram.types as agtypes
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from .gsheets import gsheets_save_admin_message, gsheets_save_user_message
from .utils import make_short_user_info


def log(func):
    """
    Decorator. Logs action name
    """
    async def wrapper(msg: agtypes.Message, *args):
        await msg.bot.log(func.__name__)
        return await func(msg, *args)

    wrapper.__name__ = func.__name__
    return wrapper


def handle_error(func):
    """
    Decorator. Processes any exception in a handler
    """
    async def wrapper(msg: agtypes.Message, *args):
        try:
            return await func(msg, *args)
        except TelegramForbiddenError:
            await report_user_ban(msg, func)
        except TelegramBadRequest as exc:
            if 'not enough rights to create a topic' in exc.message:
                await report_cant_create_topic(msg)
        except Exception as exc:
            await msg.bot.log_error(exc)

    wrapper.__name__ = func.__name__
    return wrapper


@log
async def report_user_ban(msg: agtypes.Message, func) -> None:
    """
    Report when the user banned the bot
    """
    bot = msg.bot
    thread_id = msg.message_thread_id

    if func.__name__ == 'admin_message' and await bot.db.get_tguser(thread_id=thread_id):
        group_id = bot.cfg['admin_group_id']
        await bot.send_message(
            group_id, 'The user banned the bot', message_thread_id=thread_id,
        )


@log
async def report_cant_create_topic(msg: agtypes.Message) -> None:
    """
    Report when the bot can't create a topic
    """
    user = msg.chat

    await msg.bot.send_message(
        msg.bot.cfg['admin_group_id'],
        (f'New user <b>{make_short_user_info(user=user)}</b> writes to the bot, '
         'but the bot has not enough rights to create a topic.\n\n️️️❗ '
         'Make the bot admin, and give it a "Manage topics" permission.'),
    )


async def save_admin_message(msg: agtypes.Message, tguser) -> None:
    """
    Entrypoint for all the mechanisms of saving messages sent by admin.
    There is only one currently: Google Sheets.
    """
    gsheets_cred_file = msg.bot.cfg.get('save_messages_gsheets_cred_file', None)
    gsheets_filename = msg.bot.cfg.get('save_messages_gsheets_filename', None)
    if gsheets_cred_file and gsheets_filename:
        await gsheets_save_admin_message(msg, tguser)


async def save_user_message(msg: agtypes.Message) -> None:
    """
    Entrypoint for all the mechanisms of saving messages sent by user.
    There is only one currently: Google Sheets.
    """
    gsheets_cred_file = msg.bot.cfg.get('save_messages_gsheets_cred_file', None)
    gsheets_filename = msg.bot.cfg.get('save_messages_gsheets_filename', None)
    if gsheets_cred_file and gsheets_filename:
        await gsheets_save_user_message(msg)
