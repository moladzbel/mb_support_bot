import logging
import os
from pathlib import Path

from aiogram import Bot
from aiogram.enums import ParseMode
from google.oauth2.service_account import Credentials

from .buttons import load_toml
from .db import MemoryDb, SqlDb


BASE_DIR = Path(__file__).resolve().parent.parent


class SupportBot(Bot):
    """
    Aiogram Bot Wrapper
    """
    cfg_vars = (
        'admin_group_id', 'hello_msg', 'db_url', 'db_engine', 'save_messages_gsheets_cred_file',
        'save_messages_gsheets_filename',
    )
    botdir_file_cfg_vars = ('save_messages_gsheets_cred_file',)

    def __init__(self, name: str, logger: logging.Logger):
        self.name = name
        self._logger = logger

        token, self.cfg = self._read_config()
        self._configure_db(self.cfg)

        self.menu = load_toml(self._get_botdir() / 'menu.toml')
        if self.menu:
            self.menu['answer_text'] = self.cfg['hello_msg']

        super().__init__(token, parse_mode=ParseMode.HTML)

    def _get_botdir(self) -> Path:
        botdir = BASE_DIR / '..' / 'shared' / self.name
        botdir.mkdir(parents=True, exist_ok=True)
        return botdir

    def _read_config(self) -> tuple[str, dict]:
        """
        Read a bot token and a config with other vars
        """
        botdir = self._get_botdir()
        cfg = {
            'name': self.name,
            'hello_msg': 'Hello! Write your message',
            'db_url': f'sqlite+aiosqlite:///{botdir}/db.sqlite',
            'db_engine': 'aiosqlite',
        }
        for var in self.cfg_vars:
            if envvar := os.getenv(f'{self.name}_{var.upper()}'):
                cfg[var] = envvar

        # convert vars with filenames to actual pathes
        for var in self.botdir_file_cfg_vars:
            if var in cfg:
                cfg[var] = botdir / cfg[var]

        cfg['hello_msg'] += '\n\n<i>The bot created by @moladzbel</i>'
        return os.getenv(f'{self.name}_TOKEN'), cfg

    def _configure_db(self, cfg) -> None:
        if cfg['db_engine'] == 'memory':
            self.db = MemoryDb(self.name)
            cfg['db_url'] == ''
        elif cfg['db_engine'] == 'aiosqlite':
            self.db = SqlDb(self.name, cfg['db_url'])

    async def log(self, message: str, level=logging.INFO) -> None:
        self._logger.log(level, f'{self.name}: {message}')

    async def log_error(self, exception: Exception) -> None:
        self._logger.exception(str(exception))

    def get_gsheets_creds(self):
        """
        A callback to work with Google Sheets through gspread_asyncio
        """
        cred_file = self.cfg.get('save_messages_gsheets_cred_file', None)
        creds = Credentials.from_service_account_file(cred_file)
        scoped = creds.with_scopes([
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ])
        return scoped
