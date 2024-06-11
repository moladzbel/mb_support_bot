import datetime
from dataclasses import asdict, dataclass
from pathlib import Path

import aiogram.types as agtypes
import sqlalchemy as sa
from sqlalchemy.engine.row import Row as SaRow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base

from .enums import ActionName


Base = declarative_base()
BASE_DIR = Path(__file__).resolve().parent.parent


class TgUsers(Base):
    __tablename__ = 'tgusers'

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    user_id = sa.Column(sa.Integer, index=True, nullable=False)
    full_name = sa.Column(sa.String(129))
    username = sa.Column(sa.String(32))
    thread_id = sa.Column(sa.Integer, index=True)
    last_user_msg_at = sa.Column(sa.DateTime)
    subject = sa.Column(sa.String(32))

    banned = sa.Column(sa.Boolean, default=False, nullable=False)
    shadow_banned = sa.Column(sa.Boolean, default=False, nullable=False)


class ActionStats(Base):
    __tablename__ = 'actionstats'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.Enum(ActionName), nullable=False)
    date = sa.Column(sa.Date)
    count = sa.Column(sa.Integer, default=0)

    __table_args__ = (
        sa.UniqueConstraint('name', 'date'),
    )


class MessagesToDelete(Base):
    __tablename__ = 'messages_to_delete'

    id = sa.Column(sa.Integer, primary_key=True)
    chat_id = sa.Column(sa.Integer, nullable=False)
    msg_id = sa.Column(sa.Integer, nullable=False)
    sent_at = sa.Column(sa.DateTime, nullable=False)
    by_bot = sa.Column(sa.Boolean, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint('chat_id', 'msg_id'),
    )


@dataclass
class DbTgUser:
    """
    Fake TgUser to return inserted TgUser row without another DB query
    """
    user_id: int
    full_name: str
    username: str
    thread_id: int
    last_user_msg_at: datetime.datetime
    subject: str

    banned: bool = False
    shadow_banned: bool = False


class SqlDb:
    """
    A database which uses SQL through SQLAlchemy.
    """
    def __init__(self, url: str):
        self.url = url
        self.tguser = SqlTgUser(url)
        self.action = SqlAction(url)
        self.msgtodel = SqlMessageToDelete(url)


class SqlRepo:
    """
    Repository for a table
    """
    def __init__(self, url: str):
        self.url = url


class SqlTgUser(SqlRepo):
    """
    Repository for TgUsers table
    """
    async def add(self,
                  user: agtypes.User,
                  user_msg: agtypes.Message,
                  thread_id: int | None = None) -> DbTgUser:
        tguser = DbTgUser(
            user_id=user.id, full_name=user.full_name, username=user.username, thread_id=thread_id,
            last_user_msg_at=user_msg.date.replace(tzinfo=None),
        )
        async with create_async_engine(self.url).begin() as conn:
            await conn.execute(sa.delete(TgUsers).filter_by(user_id=user.id))
            await conn.execute(sa.insert(TgUsers).values(**asdict(tguser)))

        return tguser

    async def get(self,
                  user: agtypes.User | None = None,
                  thread_id: int | None = None) -> SaRow | None:
        if user:
            query = sa.select(TgUsers).where(TgUsers.user_id==user.id)
        else:
            query = sa.select(TgUsers).where(TgUsers.thread_id==thread_id)

        async with create_async_engine(self.url).begin() as conn:
            result = await conn.execute(query)
            if row := result.fetchone():
                return row

    async def update(self,
                     user_id: int,
                     user_msg: agtypes.Message | None = None,
                     **kwargs) -> None:
        """
        Update TgUser fields (thread_id, subject, etc) provided as kwargs.
        if user_msg provided, set it's date to last_user_msg_at field.
        """
        if user_msg:
            kwargs['last_user_msg_at'] = user_msg.date.replace(tzinfo=None)

        async with create_async_engine(self.url).begin() as conn:
            await conn.execute(sa.update(TgUsers).where(TgUsers.user_id==user_id).values(**kwargs))

    async def del_thread_id(self, user_id: int) -> None:
        async with create_async_engine(self.url).begin() as conn:
            query = sa.update(TgUsers).where(TgUsers.user_id==user_id).values(thread_id=None)
            await conn.execute(query)

    async def get_all(self) -> list[SaRow]:
        async with create_async_engine(self.url).begin() as conn:
            result = await conn.execute(sa.select(TgUsers))
            return result.fetchall()

    async def get_olds(self) -> list[SaRow]:
        async with create_async_engine(self.url).begin() as conn:
            ago = datetime.datetime.utcnow() - datetime.timedelta(weeks=2)
            query = sa.select(TgUsers).where(TgUsers.last_user_msg_at <= ago)

            result = await conn.execute(query)
            return result.fetchall()


class SqlAction(SqlRepo):
    """
    Repository for ActionStats table
    """
    async def add(self, name: str) -> None:
        """
        Sum it with the existing action count for today
        """
        async with create_async_engine(self.url).begin() as conn:
            vals = {'name': name, 'date': datetime.date.today(), 'count': 1}
            insert_q = sa.insert(ActionStats).values(vals)
            update_q = sa.update(ActionStats).values(count=ActionStats.count + 1).where(
                (ActionStats.name == vals['name']) & (ActionStats.date == vals['date'])
            )
            try:
                await conn.execute(insert_q)
            except IntegrityError:
                await conn.execute(update_q)

    async def get_grouped(self, from_date: datetime.date) -> list:
        """
        Statistics over time starting from "from_date"
        """
        async with create_async_engine(self.url).begin() as conn:
            query = (
                sa.select(ActionStats.name, sa.func.sum(ActionStats.count))
                .where(ActionStats.date >= from_date)
                .group_by(ActionStats.name)
            )
            result = await conn.execute(query)
            return result.fetchall()

    async def get_total(self) -> list:
        """
        Statistics over entire bot existence time
        """
        async with create_async_engine(self.url).begin() as conn:
            query = (
                sa.select(ActionStats.name, sa.func.sum(ActionStats.count))
                .group_by(ActionStats.name)
            )
            result = await conn.execute(query)
            return result.fetchall()


class SqlMessageToDelete(SqlRepo):
    """
    Repository for MessagesToDelete table
    """
    async def add(self, msg: agtypes.Message, chat_id: int | None = None) -> None:
        """
        Remember new message
        """
        if chat_id:  # special case when the message was copied
            vals = {'chat_id': chat_id, 'sent_at': datetime.datetime.utcnow(), 'by_bot': True}
        else:  # the usual full message object
            vals = {'chat_id': msg.chat.id, 'sent_at': msg.date, 'by_bot': msg.from_user.is_bot}

        vals['msg_id'] = msg.message_id

        async with create_async_engine(self.url).begin() as conn:
            try:
                await conn.execute(sa.insert(MessagesToDelete).values(vals))
            except IntegrityError:
                pass  # such message already in the db

    async def get_many(self, before: datetime.datetime, by_bot: bool) -> list[SaRow]:
        """
        Statistics over entire bot existence time
        """
        async with create_async_engine(self.url).begin() as conn:
            query = sa.select(MessagesToDelete).where(
                (MessagesToDelete.sent_at <= before) & (MessagesToDelete.by_bot == by_bot))
            result = await conn.execute(query)
            return result.fetchall()

    async def remove(self, msgs: list[SaRow]) -> None:
        """
        Remove rows with these ids
        """
        if ids := [msg.id for msg in msgs]:
            async with create_async_engine(self.url).begin() as conn:
                query = sa.delete(MessagesToDelete).filter(MessagesToDelete.id.in_(ids))
                await conn.execute(query)
