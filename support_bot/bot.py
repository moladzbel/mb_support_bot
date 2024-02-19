import logging
import os

from aiogram import Bot
from aiogram.enums import ParseMode


BOT_CFG_VARS = ('internal_group_id', )


class SupportBot(Bot):

    def __init__(self, token: str, cfg: dict, logger: logging.Logger):
        super().__init__(token, parse_mode=ParseMode.HTML)
        self.cfg = cfg
        self.name = cfg['name']
        self._logger = logger

    async def log(self, logmsg: str):
        self._logger.info(f'{self.name}: {logmsg}')


def read_bot_config(name: str) -> tuple[str, dict]:
    """
    Read a bot token and a config with other vars
    """
    cfg = {'name': name}
    for bot_var in BOT_CFG_VARS:
        cfg[bot_var] = os.getenv(f'{name}_{bot_var.upper()}')

    return os.getenv(f'{name}_TOKEN'), cfg
