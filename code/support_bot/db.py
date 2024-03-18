from dataclasses import asdict, dataclass
from pathlib import Path

import aiogram.types as agtypes
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine


Base = declarative_base()
BASE_DIR = Path(__file__).resolve().parent.parent


class TgUsers(Base):
    __tablename__ = "tgusers"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    user_id = sa.Column(sa.Integer, index=True, nullable=False)
    full_name = sa.Column(sa.String(129))
    username = sa.Column(sa.String(32))
    thread_id = sa.Column(sa.Integer, index=True)
    banned = sa.Column(sa.Boolean, default=False, nullable=False)
    shadow_banned = sa.Column(sa.Boolean, default=False, nullable=False)


@dataclass
class DbTgUser:
    """
    Fake TgUser to return inserted TgUser row without another DB query
    """
    user_id: int
    full_name: str
    username: str
    thread_id: int
    banned: bool = False
    shadow_banned: bool = False


class Database:
    """
    Base class for any Database. It's a Repository pattern.
    """
    def __init__(self, name: str):
        self.name = name

    async def get_tguser(self, user: agtypes.User=None, thread_id: int=None) -> int:
        raise NotImplementedError

    async def set_tguser(self, user: agtypes.User, thread_id: int) -> DbTgUser:
        raise NotImplementedError


class MemoryDb(Database):
    """
    A dummy database keeping everything in memory.
    Suitable for development only - looses data on restart.
    """
    def __init__(self, name: str):
        super().__init__(name)
        self._tgusers = {}

    async def get_tguser(self, user: agtypes.User=None, thread_id: int=None) -> int:
        if user:
            return self._tgusers.get(user.id)

        for k, v in self._tgusers.items():
            if v['thread_id'] == thread_id:
                return k

    async def set_tguser(self, user: agtypes.User, thread_id: int) -> DbTgUser:
        tguser = DbTgUser(
            user_id=user.id, full_name=user.full_name, username=user.username, thread_id=thread_id,
        )
        self._tgusers[user.id] = tguser
        return tguser


class SqlDb(Database):
    """
    A database which uses SQL through SQLAlchemy.
    Default choice for production.
    """
    def __init__(self, name: str, url: str):
        super().__init__(name)
        self.url = url

    async def get_tguser(self, user: agtypes.User=None, thread_id: int=None) -> int:
        async with create_async_engine(self.url).begin() as conn:
            if user:
                query = sa.select(TgUsers).where(TgUsers.user_id==user.id)
            else:
                query = sa.select(TgUsers).where(TgUsers.thread_id==thread_id)

            result = await conn.execute(query)
            if row := result.fetchone():
                return row

    async def set_tguser(self, user: agtypes.User, thread_id: int) -> DbTgUser:
        tguser = DbTgUser(
            user_id=user.id, full_name=user.full_name, username=user.username, thread_id=thread_id,
        )
        async with create_async_engine(self.url).begin() as conn:
            await conn.execute(sa.delete(TgUsers).filter_by(user_id=user.id))
            await conn.execute(sa.insert(TgUsers).values(**asdict(tguser)))

        return tguser
