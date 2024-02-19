import os

from aiogram import Bot
from aiogram.enums import ParseMode


BOT_CFG_VARS = ('internal_group_id', )


class SupportBot(Bot):

    def __init__(self, token, cfg):
        super().__init__(token, parse_mode=ParseMode.HTML)
        self.cfg = cfg


def read_bot_config(name):
    """
    Read a bot token and a config with other vars
    """
    cfg = {}
    for bot_var in BOT_CFG_VARS:
        cfg[bot_var] = os.getenv(f'{name}_{bot_var.upper()}')

    return os.getenv(f'{name}_TOKEN'), cfg
