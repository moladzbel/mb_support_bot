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


class Database:
    """
    Base class for any Database. It's a Repository pattern.
    """
    def __init__(self, name: str):
        self.name = name

    async def get_thread_id(self, user: agtypes.User) -> int:
        raise NotImplementedError

    async def get_user_id(self, thread_id: int) -> int:
        raise NotImplementedError

    async def set_thread_id(self, user: agtypes.User, thread_id: int) -> None:
        raise NotImplementedError


class MemoryDb(Database):
    """
    A dummy database keeping everything in memory.
    Suitable for development only - looses data on restart.
    """
    def __init__(self, name: str):
        super().__init__(name)
        self._tgusers = {}

    async def get_thread_id(self, user: agtypes.User) -> int:
        return self._tgusers.get(user.id)['thread_id']

    async def get_user_id(self, thread_id: int) -> int:
        for k, v in self._tgusers.items():
            if v['thread_id'] == thread_id:
                return k['user_id']

    async def set_thread_id(self, user: agtypes.User, thread_id: int) -> None:
        self._tgusers[user.id] = {'thread_id': thread_id}


class SqlDb(Database):
    """
    A database which uses SQL through SQLAlchemy.
    Default choice for production.
    """
    def __init__(self, name: str, url: str):
        super().__init__(name)
        self.url = url

    async def get_thread_id(self, user: agtypes.User) -> int:
        async with create_async_engine(self.url).begin() as conn:
            query = sa.select(TgUsers).where(TgUsers.user_id==user.id)
            result = await conn.execute(query)
            if row := result.fetchone():
                return row.thread_id

    async def get_user_id(self, thread_id: int) -> int:
        async with create_async_engine(self.url).begin() as conn:
            query = sa.select(TgUsers).where(TgUsers.thread_id==thread_id)
            result = await conn.execute(query)
            if row := result.fetchone():
                return row.user_id

    async def set_thread_id(self, user: agtypes.User, thread_id: int) -> None:
        async with create_async_engine(self.url).begin() as conn:
            await conn.execute(sa.delete(TgUsers).filter_by(user_id=user.id))
            await conn.execute(sa.insert(TgUsers).values(user_id=user.id, thread_id=thread_id))
