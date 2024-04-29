from datetime import datetime, timedelta
from dataclasses import asdict, dataclass
from pathlib import Path

import aiogram.types as agtypes
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base


Base = declarative_base()
BASE_DIR = Path(__file__).resolve().parent.parent


class TgUsers(Base):
    __tablename__ = "tgusers"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    user_id = sa.Column(sa.Integer, index=True, nullable=False)
    full_name = sa.Column(sa.String(129))
    username = sa.Column(sa.String(32))
    thread_id = sa.Column(sa.Integer, index=True)
    last_user_msg_at = sa.Column(sa.DateTime)

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
    last_user_msg_at: datetime

    banned: bool = False
    shadow_banned: bool = False


class Database:
    """
    Base class for any Database. It's a Repository pattern.
    """
    def __init__(self, name: str):
        self.name = name

    async def get_tguser(self, user: agtypes.User=None, thread_id: int=None):
        raise NotImplementedError

    async def set_tguser(self, user: agtypes.User, user_msg: agtypes.Message, thread_id: int,
            ) -> DbTgUser:
        raise NotImplementedError

    async def update_tguser(self, user: agtypes.User, user_msg: agtypes.Message=None,
                            thread_id: int=None):
        raise NotImplementedError

    async def get_old_tgusers(self):
        raise NotImplementedError


class MemoryDb(Database):
    """
    A dummy database keeping everything in memory.
    Suitable for development only - looses data on restart.
    """
    def __init__(self, name: str):
        super().__init__(name)
        self._tgusers = {}

    async def get_tguser(self, user: agtypes.User=None, thread_id: int=None):
        if user:
            return self._tgusers.get(user.id)

        for k, v in self._tgusers.items():
            if v['thread_id'] == thread_id:
                return k

    async def set_tguser(self, user: agtypes.User, user_msg: agtypes.Message, thread_id: int,
            ) -> DbTgUser:
        tguser = DbTgUser(
            user_id=user.id, full_name=user.full_name, username=user.username, thread_id=thread_id,
            last_user_msg_at=user_msg.date.replace(tzinfo=None),
        )
        self._tgusers[user.id] = tguser
        return tguser

    async def update_tguser(self, user: agtypes.User, user_msg: agtypes.Message=None,
                            thread_id: int=None):
        if user_msg:
            self._tgusers[user.id]['last_user_msg_at'] = user_msg.date.replace(tzinfo=None)
        if thread_id:
            self._tgusers[user.id]['thread_id'] = thread_id


class SqlDb(Database):
    """
    A database which uses SQL through SQLAlchemy.
    Default choice for production.
    """
    def __init__(self, name: str, url: str):
        super().__init__(name)
        self.url = url

    async def get_tguser(self, user: agtypes.User=None, thread_id: int=None):
        if user:
            query = sa.select(TgUsers).where(TgUsers.user_id==user.id)
        else:
            query = sa.select(TgUsers).where(TgUsers.thread_id==thread_id)

        async with create_async_engine(self.url).begin() as conn:
            result = await conn.execute(query)
            if row := result.fetchone():
                return row

    async def set_tguser(self, user: agtypes.User, user_msg: agtypes.Message, thread_id: int,
            ) -> DbTgUser:
        tguser = DbTgUser(
            user_id=user.id, full_name=user.full_name, username=user.username, thread_id=thread_id,
            last_user_msg_at=user_msg.date.replace(tzinfo=None),
        )
        async with create_async_engine(self.url).begin() as conn:
            await conn.execute(sa.delete(TgUsers).filter_by(user_id=user.id))
            await conn.execute(sa.insert(TgUsers).values(**asdict(tguser)))

        return tguser

    async def update_tguser(self, user: agtypes.User, user_msg: agtypes.Message=None,
                            thread_id: int=None):
        vals = {}
        if user_msg:
            vals['last_user_msg_at'] = user_msg.date.replace(tzinfo=None)
        if thread_id:
            vals['thread_id'] = thread_id

        async with create_async_engine(self.url).begin() as conn:
            await conn.execute(sa.update(TgUsers).where(TgUsers.user_id==user.id).values(**vals))

    async def tguser_del_thread_id(self, user_id: int):
        async with create_async_engine(self.url).begin() as conn:
            query = sa.update(TgUsers).where(TgUsers.user_id==user_id).values(thread_id=None)
            await conn.execute(query)

    async def get_old_tgusers(self):
        async with create_async_engine(self.url).begin() as conn:
            ago = datetime.utcnow() - timedelta(weeks=2)
            query = sa.select(TgUsers).where(TgUsers.last_user_msg_at <= ago)

            result = await conn.execute(query)
            return result.fetchall()
