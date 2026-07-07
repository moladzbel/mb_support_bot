import datetime
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import aiogram.types as agtypes
import sqlalchemy as sa
from sqlalchemy.engine.row import Row as SaRow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import false

from .const import ActionName


Base = declarative_base()
BASE_DIR = Path(__file__).resolve().parent.parent


class TgUsers(Base):
    __tablename__ = 'tgusers'

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    user_id = sa.Column(sa.BigInteger, index=True, nullable=False)
    full_name = sa.Column(sa.String(129))
    username = sa.Column(sa.String(32))
    thread_id = sa.Column(sa.Integer, index=True)
    last_user_msg_at = sa.Column(sa.DateTime)
    subject = sa.Column(sa.String(32))
    banned = sa.Column(sa.Boolean, default=False, nullable=False)
    first_replied = sa.Column(sa.Boolean, server_default=false(), nullable=False)


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
    chat_id = sa.Column(sa.BigInteger, nullable=False)
    msg_id = sa.Column(sa.Integer, nullable=False)
    sent_at = sa.Column(sa.DateTime, nullable=False)
    by_bot = sa.Column(sa.Boolean, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint('chat_id', 'msg_id'),
    )


class MessageMap(Base):
    __tablename__ = 'message_map'

    id = sa.Column(sa.Integer, primary_key=True)
    admin_msg_id = sa.Column(sa.Integer, nullable=False)
    user_id = sa.Column(sa.BigInteger, nullable=False)
    user_msg_id = sa.Column(sa.Integer, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint('admin_msg_id'),
        sa.UniqueConstraint('user_id', 'user_msg_id'),
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
    subject: str | None = None
    banned: bool = False
    first_replied: bool = False  # whether first_reply has been sent or not


class SqlDb:
    """
    A database which uses SQL through SQLAlchemy.
    """
    def __init__(self, url: str):
        self.url = url
        self.engine = create_async_engine(url)
        self.tguser = SqlTgUser(self.engine)
        self.action = SqlAction(self.engine)
        self.msgtodel = SqlMessageToDelete(self.engine)
        self.msgmap = SqlMessageMap(self.engine)


class SqlRepo:
    """
    Repository for a table
    """
    def __init__(self, engine: AsyncEngine):
        self.engine = engine


class SqlTgUser(SqlRepo):
    """
    Repository for TgUsers table
    """
    async def add(self,
                  user: agtypes.User,
                  user_msg: agtypes.Message,
                  thread_id: int | None = None,
                  first_replied: bool = False) -> DbTgUser:
        tguser = DbTgUser(
            user_id=user.id, full_name=user.full_name, username=user.username, thread_id=thread_id,
            last_user_msg_at=user_msg.date.replace(tzinfo=None), first_replied=first_replied,
        )
        async with self.engine.begin() as conn:
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

        async with self.engine.begin() as conn:
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

        async with self.engine.begin() as conn:
            await conn.execute(sa.update(TgUsers).where(TgUsers.user_id==user_id).values(**kwargs))

    async def del_thread_id(self, user_id: int) -> None:
        async with self.engine.begin() as conn:
            query = sa.update(TgUsers).where(TgUsers.user_id==user_id).values(thread_id=None)
            await conn.execute(query)

    async def get_all(self) -> Sequence[SaRow]:
        async with self.engine.begin() as conn:
            result = await conn.execute(sa.select(TgUsers))
            return result.fetchall()

    async def get_olds(self) -> Sequence[SaRow]:
        async with self.engine.begin() as conn:
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
        async with self.engine.begin() as conn:
            vals = {'name': name, 'date': datetime.date.today(), 'count': 1}
            insert_q = sa.insert(ActionStats).values(vals)
            update_q = sa.update(ActionStats).values(count=ActionStats.count + 1).where(
                (ActionStats.name == vals['name']) & (ActionStats.date == vals['date'])
            )
            try:
                await conn.execute(insert_q)
            except IntegrityError:
                await conn.execute(update_q)

    async def get_grouped(self, from_date: datetime.date) -> Sequence[SaRow]:
        """
        Statistics over time starting from "from_date"
        """
        async with self.engine.begin() as conn:
            query = (
                sa.select(ActionStats.name, sa.func.sum(ActionStats.count))
                .where(ActionStats.date >= from_date)
                .group_by(ActionStats.name)
            )
            result = await conn.execute(query)
            return result.fetchall()

    async def get_total(self) -> Sequence[SaRow]:
        """
        Statistics over entire bot existence time
        """
        async with self.engine.begin() as conn:
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
    async def add(self, msg: agtypes.Message | agtypes.MessageId,
                  chat_id: int | None = None) -> None:
        """
        Remember new message
        """
        if chat_id:  # special case when the message was copied
            vals = {'chat_id': chat_id, 'sent_at': datetime.datetime.utcnow(), 'by_bot': True}
        else:  # the usual full message object
            vals = {'chat_id': msg.chat.id, 'sent_at': msg.date, 'by_bot': msg.from_user.is_bot}

        vals['msg_id'] = msg.message_id

        async with self.engine.begin() as conn:
            try:
                await conn.execute(sa.insert(MessagesToDelete).values(vals))
            except IntegrityError:
                pass  # such message already in the db

    async def get_many(self, before: datetime.datetime, by_bot: bool) -> Sequence[SaRow]:
        """
        Statistics over entire bot existence time
        """
        async with self.engine.begin() as conn:
            query = sa.select(MessagesToDelete).where(
                (MessagesToDelete.sent_at <= before) & (MessagesToDelete.by_bot == by_bot))
            result = await conn.execute(query)
            return result.fetchall()

    async def remove(self, msgs: Sequence[SaRow]) -> None:
        """
        Remove rows with these ids
        """
        if ids := [msg.id for msg in msgs]:
            async with self.engine.begin() as conn:
                query = sa.delete(MessagesToDelete).filter(MessagesToDelete.id.in_(ids))
                await conn.execute(query)


class SqlMessageMap(SqlRepo):
    """
    Repository for MessageMap table. A row pairs a message in the admin chat
    with the corresponding message in the user chat (in either direction).
    """
    async def add(self, admin_msg_id: int, user_id: int, user_msg_id: int) -> None:
        vals = {'admin_msg_id': admin_msg_id, 'user_id': user_id, 'user_msg_id': user_msg_id}
        async with self.engine.begin() as conn:
            await conn.execute(sa.insert(MessageMap).values(vals))

    async def get(self, admin_msg_id: int) -> SaRow | None:
        query = sa.select(MessageMap).where(MessageMap.admin_msg_id==admin_msg_id)
        async with self.engine.begin() as conn:
            result = await conn.execute(query)
            return result.fetchone()

    async def get_by_user_msg(self, user_id: int, user_msg_id: int) -> SaRow | None:
        query = sa.select(MessageMap).where(
            (MessageMap.user_id == user_id) & (MessageMap.user_msg_id == user_msg_id)
        )
        async with self.engine.begin() as conn:
            result = await conn.execute(query)
            return result.fetchone()
