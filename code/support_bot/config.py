from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from .const import SendMode


BASE_DIR = Path(__file__).resolve().parent.parent

Hours = Annotated[int, Field(ge=1, le=47)]


class BotConfig(BaseModel):
    """
    Per-bot configuration: one field per `{BOTNAME}_*` env var. Raw env strings
    are read in `SupportBot._read_config` and coerced/validated here, so bad
    values fail fast at startup. Add a new env var by adding a field below
    (and documenting it in DOCS.md).
    """
    name: str
    admin_group_id: int | None = None
    hello_msg: str = 'Hello! Write your message'
    hello_ps: str = '\n\n<i>The bot is created by @moladzbel</i>'
    first_reply: str = (
        "We have received your message. We'll get back to you as soon as we can. "
        "Please don't delete the chat so we can send you a reply."
    )
    db_url: str | None = None  # defaults to a per-bot sqlite file under botdir
    db_engine: str = 'aiosqlite'
    save_messages_gsheets_cred_file: Path | None = None  # resolved against botdir
    save_messages_gsheets_filename: str | None = None
    destruct_user_messages_for_user: Hours | None = None
    destruct_bot_messages_for_user: Hours | None = None
    send_mode: SendMode = SendMode.REPLY
    mirror_replies: bool = False
    mirror_reactions: bool = False
    admin_only_actions: bool = True

    @field_validator('send_mode', mode='before')
    @classmethod
    def _lower_send_mode(cls, value):
        return value.lower() if isinstance(value, str) else value

    @model_validator(mode='after')
    def _derive(self):
        botdir = BASE_DIR / '..' / 'shared' / self.name

        if self.db_url is None:
            self.db_url = f'sqlite+aiosqlite:///{botdir}/db.sqlite'

        if self.save_messages_gsheets_cred_file is not None:
            self.save_messages_gsheets_cred_file = botdir / self.save_messages_gsheets_cred_file

        self.hello_msg += self.hello_ps
        return self
