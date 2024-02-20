import logging
import os

from aiogram import Bot
from aiogram.enums import ParseMode

from .db import MemoryDB


BOT_CFG_VARS = (
    'admin_group_id', 'hello_msg',
)


class SupportBot(Bot):

    def __init__(self, token: str, cfg: dict, logger: logging.Logger):
        super().__init__(token, parse_mode=ParseMode.HTML)
        self.cfg = cfg
        self.name = cfg['name']
        self.db = MemoryDB(self.name)
        self._logger = logger

    async def log(self, logmsg: str):
        self._logger.info(f'{self.name}: {logmsg}')


def read_bot_config(name: str) -> tuple[str, dict]:
    """
    Read a bot token and a config with other vars
    """
    cfg = {  # default config
        'name': name,
        'hello_msg': 'Hello! Write your message',
    }
    for bot_var in BOT_CFG_VARS:
        if envvar := os.getenv(f'{name}_{bot_var.upper()}'):
            cfg[bot_var] = envvar

    return os.getenv(f'{name}_TOKEN'), cfg
