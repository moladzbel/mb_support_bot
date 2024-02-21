import logging
import os
from pathlib import Path

from aiogram import Bot
from aiogram.enums import ParseMode

from .db import MemoryDb, SqlDb


BASE_DIR = Path(__file__).resolve().parent.parent


class SupportBot(Bot):
    """
    Aiogram Bot Wrapper
    """
    config_vars = (
        'admin_group_id', 'hello_msg', 'db_url', 'db_engine',
    )

    def __init__(self, name: str, logger: logging.Logger):
        self.name = name
        self._logger = logger

        token, cfg = self._read_config()
        self._configure_db(cfg)

        super().__init__(token, parse_mode=ParseMode.HTML)

    def _read_config(self) -> tuple[str, dict]:
        """
        Read a bot token and a config with other vars
        """
        cfg = {
            'name': self.name,
            'hello_msg': 'Hello! Write your message',
            'db_url': f'sqlite+aiosqlite:///{BASE_DIR / f"shared/{self.name}.sqlite"}',
            'db_engine': 'aiosqlite',
        }
        for bot_var in self.config_vars:
            if envvar := os.getenv(f'{self.name}_{bot_var.upper()}'):
                cfg[bot_var] = envvar

        return os.getenv(f'{self.name}_TOKEN'), cfg

    def _configure_db(self, cfg) -> None:
        if cfg['db_engine'] == 'memory':
            self.db = MemoryDb(self.name)
            cfg['db_url'] == ''
        elif cfg['db_engine'] == 'aiosqlite':
            self.db = SqlDb(self.name, cfg['db_url'])

        self.cfg = cfg

    async def log(self, message: str, level=logging.INFO) -> None:
        self._logger.log(level, f'{self.name}: {message}')

    async def log_error(self, exception: Exception) -> None:
        self._logger.exception(str(exception))
