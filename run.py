import logging
import os
import sys
from pathlib import Path

import asyncio
from dotenv import load_dotenv
from aiogram import Dispatcher

from support_bot import SupportBot, read_bot_config, register_handlers


BASE_DIR = Path(__file__).resolve().parent


def setup_logger(level=logging.INFO, log_path=None) -> logging.Logger:
    global logger
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


def get_bot_names():
    """
    Return names of enabled bots
    """
    return [n.strip() for n in os.getenv('BOTS_ENABLED').split(',') if n.strip()]


async def start_bots() -> None:
    """
    Create bot instances and run them within a dispatcher
    """
    bots = []
    dp = Dispatcher()
    register_handlers(dp)

    for bot_name in get_bot_names():
        token, cfg = read_bot_config(bot_name)
        bots.append(SupportBot(token, cfg, logger))
    
    logger.info('Started bots: %s', ', '.join([b.name for b in bots]))
    await dp.start_polling(*bots, polling_timeout=30)


def cmd_makemigrations() -> None:
    """
    Generate migration scripts if there are changes in schema
    """
    logger.info('Generating migration scripts')

    message = 'migration'
    if '-m' in sys.argv:
        idx = sys.argv.index('-m') + 1
        message = sys.argv[idx]

    db_path = BASE_DIR / 'shared' / f'{get_bot_names()[0]}.sqlite'
    envvar = f'MBSB_SQLALCHEMY_URL="sqlite+aiosqlite:///{db_path}"'
    stream = os.popen(f'{envvar} alembic revision --autogenerate -m "{message}"')
    stream.read()


def cmd_migrate() -> None:
    """
    Migrate each bot DB
    """
    for bot_name in get_bot_names():
        logger.info('Migrating DB for %s', bot_name)

        db_path = BASE_DIR / 'shared' / f'{bot_name}.sqlite'
        envvar = f'MBSB_SQLALCHEMY_URL="sqlite+aiosqlite:///{db_path}"'
        stream = os.popen(f'{envvar} alembic upgrade head')
        stream.read()


def main() -> None:
    setup_logger()
    load_dotenv(BASE_DIR / 'shared' / '.env')

    if 'makemigrations' in sys.argv:
        cmd_makemigrations()
    elif 'migrate' in sys.argv:
        cmd_migrate()
    else:
        asyncio.run(start_bots())


if __name__ == '__main__':
    main()
