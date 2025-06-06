import logging
import os
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from google.oauth2.service_account import Credentials

from .buttons import load_toml
from .const import AdminBtn
from .db import SqlDb


BASE_DIR = Path(__file__).resolve().parent.parent


class SupportBot(Bot):
    """
    Aiogram Bot Wrapper
    """
    cfg_vars = (
        'admin_group_id', 'hello_msg', 'first_reply', 'db_url', 'db_engine',
        'save_messages_gsheets_cred_file', 'save_messages_gsheets_filename', 'hello_ps',
        'destruct_user_messages_for_user', 'destruct_bot_messages_for_user'
    )
    botdir_file_cfg_vars = ('save_messages_gsheets_cred_file',)

    def __init__(self, name: str, logger: logging.Logger):
        self.name = name
        self._logger = logger

        self.botdir.mkdir(parents=True, exist_ok=True)
        token, self.cfg = self._read_config()
        self._configure_db()
        self._load_menu()

        super().__init__(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    @property
    def botdir(self) -> Path:
        return BASE_DIR / '..' / 'shared' / self.name

    def _read_config(self) -> tuple[str, dict]:
        """
        Read a bot token and a config with other vars
        """
        cfg = {
            'name': self.name,
            'hello_msg': 'Hello! Write your message',
            'first_reply': (
                "We have received your message. We'll get back to you as soon as we can. "
                "Please don't delete the chat so we can send you a reply."
            ),
            'db_url': f'sqlite+aiosqlite:///{self.botdir}/db.sqlite',
            'db_engine': 'aiosqlite',
            'hello_ps': '\n\n<i>The bot is created by @moladzbel</i>',
        }
        for var in self.cfg_vars:
            envvar = os.getenv(f'{self.name}_{var.upper()}')
            if envvar is not None:
                cfg[var] = envvar

        # convert vars with filenames to actual pathes
        for var in self.botdir_file_cfg_vars:
            if var in cfg:
                cfg[var] = self.botdir / cfg[var]

        # validate and convert destruction vars
        for var in 'destruct_user_messages_for_user', 'destruct_bot_messages_for_user':
            if var in cfg:
                cfg[var] = int(cfg[var])
                if not 1 <= cfg[var] <= 47:
                    raise ValueError(f'{var} must be between 1 and 47 (hours)')

        cfg['hello_msg'] += cfg['hello_ps']
        return os.getenv(f'{self.name}_TOKEN'), cfg

    def _configure_db(self) -> None:
        if self.cfg['db_engine'] == 'aiosqlite':
            self.db = SqlDb(self.cfg['db_url'])

    async def log(self, message: str, level=logging.INFO) -> None:
        self._logger.log(level, f'{self.name}: {message}')

    async def log_error(self, exception: Exception, traceback: bool = True) -> None:
        self._logger.error(str(exception), exc_info=traceback)

    def get_gsheets_creds(self):
        """
        A callback to work with Google Sheets through gspread_asyncio.
        """
        cred_file = self.cfg.get('save_messages_gsheets_cred_file', None)
        creds = Credentials.from_service_account_file(cred_file)
        scoped = creds.with_scopes([
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ])
        return scoped

    def _load_menu(self) -> None:
        self.menu = load_toml(self.botdir / 'menu.toml')
        if self.menu:
            self.menu['answer'] = self.cfg['hello_msg']

        self.admin_menu = {
            AdminBtn.broadcast: {'label': '📢 Broadcast to all subscribers',
                                 'answer': ("Send here a message to broadcast, and then I'll ask "
                                            "for confirmation")},
            AdminBtn.del_old_topics: {'label': '🧹 Delete topics older than 2 weeks',
                                      'answer': ('Deleting topics older than 2 weeks...')},
        }
