import aiogram.types as agtypes
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base


Base = declarative_base()


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
    pass


class MemoryDb(Database):
    """
    A dummy database keeping everything in memory.
    Suitable for development only - looses data on restart.
    """
    def __init__(self, name: str):
        self.name = name
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
    def __init__(self, name: str):
        ...

    async def get_thread_id(self, user: agtypes.User) -> int:
        ...

    async def get_user_id(self, thread_id: int) -> int:
        ...

    async def set_thread_id(self, user: agtypes.User, thread_id: int) -> None:
        ...
