import logging
import os

import asyncio
from dotenv import load_dotenv
from aiogram import Dispatcher

from support_bot import SupportBot, read_bot_config, register_handlers


def setup_logger(level=logging.INFO, log_path=None) -> logging.Logger:
    logger = logging.getLogger('support_bot')
    logger.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    frmtr = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    stream_handler.setFormatter(frmtr)
    logger.addHandler(stream_handler)

    if log_path:
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(frmtr)
        logger.addHandler(file_handler)

    return logger


async def main() -> None:
    """
    Create bot instances and run them within a dispatcher
    """
    logger = setup_logger()
    load_dotenv()
    bots = []
    dp = Dispatcher()
    register_handlers(dp)

    for bot_name in os.getenv('BOTS_ENABLED').split(','):
        if bot_name := bot_name.strip():
            token, cfg = read_bot_config(bot_name)
            bots.append(SupportBot(token, cfg, logger))
    
    logger.info('Started bots: %s', ', '.join([b.name for b in bots]))
    await dp.start_polling(*bots, polling_timeout=30)


if __name__ == '__main__':
    asyncio.run(main())
