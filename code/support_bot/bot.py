import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from google.oauth2.service_account import Credentials

from .buttons import load_toml
from .config import BotConfig
from .const import AdminBtn
from .db import SqlDb


BASE_DIR = Path(__file__).resolve().parent.parent


class SupportBot(Bot):
    """
    Aiogram Bot Wrapper
    """
    cfg: BotConfig
    db: SqlDb
    menu: dict | None
    admin_menu: dict

    def __init__(self, name: str, logger: logging.Logger):
        self.name = name
        self._logger = logger
        self._user_locks: dict[int, asyncio.Lock] = {}

        self.botdir.mkdir(parents=True, exist_ok=True)
        token, self.cfg = self._read_config()
        self._configure_db()
        self._load_menu()

        super().__init__(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    def user_lock(self, user_id: int) -> asyncio.Lock:
        """
        Per-user lock that serializes get-or-create of the user's tguser row
        and admin-group topic, preventing duplicate topics when concurrent
        messages arrive for a brand-new user.
        """
        lock = self._user_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self._user_locks[user_id] = lock
        return lock

    def sweep_user_locks(self) -> None:
        """
        Forget unheld per-user locks so the dict doesn't grow forever.
        Must be called from the event loop: an unheld lock can't be acquired
        mid-sweep, because handlers acquire it with no await between
        the dict lookup and the acquire.
        """
        self._user_locks = {uid: lock for uid, lock in self._user_locks.items() if lock.locked()}

    @property
    def botdir(self) -> Path:
        return BASE_DIR / '..' / 'shared' / self.name

    def _read_config(self) -> tuple[str, BotConfig]:
        """
        Read the bot token and build the validated per-bot config from the
        `{NAME}_*` env vars (one per BotConfig field).
        """
        data = {'name': self.name}
        for field in BotConfig.model_fields:
            if field == 'name':
                continue
            if (envvar := os.getenv(f'{self.name}_{field.upper()}')) is not None:
                data[field] = envvar

        return os.getenv(f'{self.name}_TOKEN'), BotConfig(**data)

    def _configure_db(self) -> None:
        if self.cfg.db_engine == 'aiosqlite':
            self.db = SqlDb(self.cfg.db_url)

    async def log(self, message: str, level: int = logging.INFO) -> None:
        self._logger.log(level, f'{self.name}: {message}')

    async def log_error(self, exception: Exception, traceback: bool = True) -> None:
        self._logger.error(f'{self.name}: {exception}', exc_info=traceback)

    def get_gsheets_creds(self) -> Credentials:
        """
        A callback to work with Google Sheets through gspread_asyncio.
        """
        cred_file = self.cfg.save_messages_gsheets_cred_file
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
            self.menu['answer'] = self.cfg.hello_msg

        self.admin_menu = {
            AdminBtn.BROADCAST: {
                'label': '📢 Broadcast to all subscribers',
                'answer': "Send here a message to broadcast, and then I'll ask for confirmation",
            },
            AdminBtn.DEL_OLD_TOPICS: {
                'label': '🧹 Delete topics older than 2 weeks',
                'answer': 'Deleting topics older than 2 weeks...',
            },
            AdminBtn.SETTINGS: {
                'label': '⚙️ Show settings',
            },
        }
