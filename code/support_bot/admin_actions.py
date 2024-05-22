import aiogram.types as agtypes

from .const import AdminBtn


async def del_old_topics(call: agtypes.CallbackQuery):
    """
    Admin action - delete topics older than 2 weeks,
    and delete their thread ids from DB
    """
    msg = call.message
    bot, db = msg.bot, msg.bot.db
    await msg.answer(bot.admin_menu[AdminBtn.del_old_topics]['answer'])

    i = 0
    for tguser in await db.get_old_tgusers():
        if tguser.thread_id:
            await bot.delete_forum_topic(bot.cfg['admin_group_id'], tguser.thread_id)
            await db.tguser_del_thread_id(tguser.user_id)
            i += 1

    emo = '😐' if i == 0 else '🫡'
    end = '' if i == 1 else 's'
    await msg.answer(f'Deleted {i} topic{end} {emo}')
