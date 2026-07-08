import asyncio
from typing import Any

import aiogram.types as agtypes
from aiogram import Dispatcher
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey

from .const import AdminBtn, SendMode
from .informing import handle_error, log
from .utils import may_use_admin_actions


class BroadcastForm(StatesGroup):
    message = State()
    confirm = State()


# Human-friendly labels for the config fields shown by `bot_settings`, in
# display order. Secret/technical fields (token, db, gsheets creds) are omitted.
SETTINGS_LABELS = {
    'admin_group_id': 'Admin group ID',
    'hello_msg': 'Welcome message',
    'first_reply': 'First auto-reply',
    'destruct_user_messages_for_user': "Auto-delete user's messages after (hours)",
    'destruct_bot_messages_for_user': "Auto-delete bot's messages after (hours)",
    'send_mode': 'Reply mode',
    'mirror_replies': 'Mirror replies',
    'mirror_reactions': 'Mirror reactions',
    'admin_only_actions': 'Admin actions for group admins only',
}

# Brief explanation of how each reply mode routes admin messages to the user.
SEND_MODE_EXPLANATIONS = {
    SendMode.REPLY: 'only replies to a bot message in a topic are sent to the user',
    SendMode.ALL: 'any message in a topic is sent to the user',
    SendMode.ALL_EXCEPT_ADMINS: ('any message in a topic is sent to the user, '
                                 'except replies to another admin'),
}


def _format_setting_value(field: str, value: Any) -> str:
    if value is None:
        return '<i>not set</i>'
    if isinstance(value, bool):
        return 'on' if value else 'off'
    if field == 'send_mode':
        return SEND_MODE_EXPLANATIONS[value]
    # admin-configured strings may contain Telegram HTML - render it, don't escape
    return str(value)


@log
@handle_error
async def bot_settings(call: agtypes.CallbackQuery) -> None:
    """
    Admin action - show the bot's options from .env in a human-readable form,
    excluding the secret and purely technical ones.
    """
    cfg = call.message.bot.cfg

    lines = [f'• <b>{label}:</b> {_format_setting_value(field, getattr(cfg, field))}'
             for field, label in SETTINGS_LABELS.items()]

    gsheets_on = bool(cfg.save_messages_gsheets_cred_file and cfg.save_messages_gsheets_filename)
    lines.append(f'• <b>Save messages to Google Sheets:</b> {"on" if gsheets_on else "off"}')
    if gsheets_on:
        lines.append(f'• <b>Google Sheets file name:</b> {cfg.save_messages_gsheets_filename}')

    await call.message.answer('\n\n'.join(lines))


@log
@handle_error
async def del_old_topics(call: agtypes.CallbackQuery) -> None:
    """
    Admin action - delete topics older than 2 weeks,
    and delete their thread ids from DB
    """
    msg = call.message
    bot, db = msg.bot, msg.bot.db
    await msg.answer(bot.admin_menu[AdminBtn.DEL_OLD_TOPICS]['answer'])

    i = 0
    for tguser in await db.tguser.get_olds():
        if tguser.thread_id:
            try:
                await bot.delete_forum_topic(bot.cfg.admin_group_id, tguser.thread_id)
                i += 1
            except TelegramBadRequest as exc:
                await bot.log_error(exc)

            await db.tguser.del_thread_id(tguser.user_id)

    emo = '😐' if i == 0 else '🫡'
    end = '' if i == 1 else 's'
    await msg.answer(f'Deleted {i} topic{end} {emo}')


@log
@handle_error
async def admin_broadcast_start(call: agtypes.CallbackQuery, dispatcher: Dispatcher) -> None:
    """
    Start broadcasting flow - ask for a message to broadcast
    """
    msg = call.message
    bot = msg.bot

    key = StorageKey(bot_id=bot._me.id, chat_id=msg.chat.id, user_id=call.from_user.id)
    state = FSMContext(dispatcher.storage, key)

    await state.set_state(BroadcastForm.message)
    await msg.answer(bot.admin_menu[AdminBtn.BROADCAST]['answer'])


@log
@handle_error
async def admin_broadcast_ask_confirm(msg: agtypes.Message, state: FSMContext,
                                      *args, **kwargs) -> None:
    """
    Middle of the broadcasting flow - confirmation
    """
    from .buttons import build_confirm_menu, send_new_msg_with_keyboard
    bot = msg.bot

    try:
        await bot.copy_message(msg.chat.id, from_chat_id=msg.chat.id, message_id=msg.message_id)
    except TelegramBadRequest:
        return await msg.answer("This type of message can't be sent, sorry 🥺. Try again.")

    await state.update_data(message=msg.message_id)
    await state.set_state(BroadcastForm.confirm)
    await asyncio.sleep(0.1)

    text = 'Send this 👆 message to all the bot users?'
    await send_new_msg_with_keyboard(bot, bot.cfg.admin_group_id, text, build_confirm_menu())


@log
@handle_error
async def admin_broadcast_finish(call: agtypes.CallbackQuery, state: FSMContext,
                                 *args, **kwargs) -> None:
    """
    End of the broadcasting flow - send the message or forget it
    """
    from .buttons import CBD

    msg = call.message
    bot = msg.bot

    if not await may_use_admin_actions(bot, call.from_user):
        return await call.answer('Only group admins can do this', show_alert=True)
    cbd = CBD.unpack(call.data)
    state_data = await state.get_data()

    if cbd.code == 'yes':
        text = 'Broadcasting the message...'
        await bot.edit_message_text(chat_id=msg.chat.id, message_id=cbd.msgid, text=text)

        success_count = 0
        forbidden_count = 0
        users = await bot.db.tguser.get_all()
        for i, user in enumerate(users):
            while True:
                try:
                    await bot.copy_message(user.user_id, from_chat_id=msg.chat.id,
                                           message_id=state_data['message'])
                    success_count += 1
                    break
                except TelegramRetryAfter as exc:
                    await bot.log(f'Throttled by Telegram, sleeping {exc.retry_after}s')
                    await asyncio.sleep(exc.retry_after)
                except TelegramForbiddenError:
                    forbidden_count += 1
                    break
                except Exception as exc:
                    await bot.log_error(exc, traceback=False)
                    break

            await asyncio.sleep(0.05)  # ~20 msgs/sec, under Telegram's ~30/sec global cap

            if len(users) > 50 and i != 0 and i % (len(users) // 10) == 0:
                await bot.log(f'{i}/{len(users)} processed for broadcasting')

        res_str = f'{success_count}/{len(users)}'
        await bot.log(f'Broadcasting is done: {res_str}')

        report = f'Broadcasting is done 🫡. {res_str} users received the message.'
        if forbidden_count:
            postfix = 's' if forbidden_count > 1 else ''
            report += f' Messages to {forbidden_count} user{postfix} were forbidden by Telegram.'
        await msg.answer(report)

    elif cbd.code == 'no':
        text = 'Broadcasting canceled'
        await bot.edit_message_text(chat_id=msg.chat.id, message_id=cbd.msgid, text=text)

    await state.clear()
    return await call.answer()
