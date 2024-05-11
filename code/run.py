#!/usr/bin/env python
import logging
import os
import sys
from pathlib import Path

import asyncio
from dotenv import load_dotenv
from aiogram import Dispatcher

from support_bot import SupportBot, register_handlers, start_jobs


BASE_DIR = Path(__file__).resolve().parent
BOTS = ()


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


def init_bots():
    """
    Create Bot instances. Any command works with them,
    so it's shorter to have them as a global
    """
    global BOTS
    if BOTS:
        return BOTS

    BOTS = []
    for name in os.getenv('BOTS_ENABLED').split(','):
        if name := name.strip():
            BOTS.append(SupportBot(name, logger))


async def start() -> None:
    """
    Create bot instances and run them within a dispatcher
    """
    await start_jobs(BOTS)

    dp = Dispatcher()
    register_handlers(dp)

    logger.info('Started bots: %s', ', '.join([b.name for b in BOTS]))
    await dp.start_polling(*BOTS, polling_timeout=30)


def cmd_makemigrations() -> None:
    """
    Generate migration scripts if there are changes in schema
    """
    logger.info('Generating migration scripts')

    message = 'migration'
    if '-m' in sys.argv:
        message = sys.argv[sys.argv.index('-m') + 1]

    db_url = 'sqlite:///:memory:'
    for bot in BOTS:
        if 'sql' in bot.cfg['db_engine'].lower():
            db_url = bot.cfg['db_url']

    envvar = f'MBSB_SQLALCHEMY_URL="{db_url}"'
    stream = os.popen(f'{envvar} alembic revision --autogenerate -m "{message}"')
    stream.read()


def cmd_migrate() -> None:
    """
    Migrate each bot DB
    """
    for bot in BOTS:
        if 'sql' in bot.cfg['db_engine'].lower():
            logger.info('Migrating DB for %s', bot.name)
            envvar = 'MBSB_SQLALCHEMY_URL=' + bot.cfg['db_url']
            stream = os.popen(f'{envvar} alembic upgrade head')
            stream.read()

    logger.info('Migrating done')


def main() -> None:
    setup_logger(log_path=BASE_DIR / '..' / 'shared' / 'support_bot.log')

    if not os.environ.get('IS_DOCKER', False):
        load_dotenv(BASE_DIR / '../.env')

    init_bots()

    if 'makemigrations' in sys.argv:
        cmd_makemigrations()
    elif 'migrate' in sys.argv:
        cmd_migrate()
    else:
        asyncio.run(start())


if __name__ == '__main__':
    main()
