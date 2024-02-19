import os

import asyncio
from dotenv import load_dotenv
from aiogram import Dispatcher

from support_bot import SupportBot, read_bot_config, register_handlers


async def main():
    """
    Create bot instances and run them within a dispatcher
    """
    load_dotenv()
    bots = []
    dp = Dispatcher()
    register_handlers(dp)

    for bot_name in os.getenv('BOTS_ENABLED').split(','):
        if bot_name := bot_name.strip():
            token, cfg = read_bot_config(bot_name)
            bots.append(SupportBot(token, cfg))
    
    await dp.start_polling(*bots, polling_timeout=30)


if __name__ == '__main__':
    asyncio.run(main())
