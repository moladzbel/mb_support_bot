from pathlib import Path

import aiogram.types as agtypes
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine


Base = declarative_base()
BASE_DIR = Path(__file__).resolve().parent.parent


class Threads(Base):
    __tablename__ = "threads"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    user_id = sa.Column(sa.Integer, index=True)
    thread_id = sa.Column(sa.Integer, index=True)


class Bans(Base):
    __tablename__ = "bans"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    user_id = sa.Column(sa.Integer, index=True)
    is_shadow = sa.Column(sa.Boolean, default=False)


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
        self._threads = {}
        self._bans = {}

    async def get_thread_id(self, user: agtypes.User) -> int:
        return self._threads.get(user.id)

    async def get_user_id(self, thread_id: int) -> int:
        for k, v in self._threads.items():
            if v == thread_id:
                return k

    async def set_thread_id(self, user: agtypes.User, thread_id: int) -> None:
        self._threads[user.id] = thread_id


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
            query = sa.select(Threads).where(Threads.user_id==user.id)
            result = await conn.execute(query)
            if row := result.fetchone():
                return row.thread_id

    async def get_user_id(self, thread_id: int) -> int:
        async with create_async_engine(self.url).begin() as conn:
            query = sa.select(Threads).where(Threads.thread_id==thread_id)
            result = await conn.execute(query)
            if row := result.fetchone():
                return row.user_id

    async def set_thread_id(self, user: agtypes.User, thread_id: int) -> None:
        async with create_async_engine(self.url).begin() as conn:
            query = sa.insert(Threads).values(user_id=user.id, thread_id=thread_id)
            await conn.execute(query)
