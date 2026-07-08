#!/usr/bin/env python
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from aiogram import Dispatcher

from support_bot import (
    SupportBot, destruct_messages, register_handlers, stats_to_admin_chat, sweep_user_locks,
)


BASE_DIR = Path(__file__).resolve().parent
BOTS = ()
logger = logging.getLogger('support_bot')


def setup_logger(level: int = logging.INFO, log_path: Path | None = None) -> None:
    logger.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


def init_bots() -> None:
    """
    Create Bot instances. Any command works with them,
    so it's shorter to have them as a global
    """
    global BOTS
    if BOTS:
        return

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
        if 'sql' in bot.cfg.db_engine.lower():
            db_url = bot.cfg.db_url

    subprocess.run([sys.executable, '-m', 'alembic', 'revision', '--autogenerate', '-m', message],
                   env={**os.environ, 'MBSB_SQLALCHEMY_URL': db_url}, cwd=BASE_DIR)


def cmd_migrate() -> None:
    """
    Migrate each bot DB
    """
    for bot in BOTS:
        if 'sql' in bot.cfg.db_engine.lower():
            logger.info('Migrating DB for %s', bot.name)
            subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'],
                           env={**os.environ, 'MBSB_SQLALCHEMY_URL': bot.cfg.db_url}, cwd=BASE_DIR)

    logger.info('Migrating done')


async def start_jobs(bots: list[SupportBot]) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(stats_to_admin_chat, 'cron', day_of_week=0, args=(bots,))  # weekly
    scheduler.add_job(destruct_messages, 'interval', minutes=10, args=(bots,),
                      next_run_time=datetime.now())  # on startup, then every 10 minutes
    scheduler.add_job(sweep_user_locks, 'interval', hours=1, args=(bots,))
    scheduler.start()


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
