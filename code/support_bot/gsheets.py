"""
Work with Google Sheets
"""
import string
from datetime import datetime
from typing import Any

import aiogram.types as agtypes
import gspread_asyncio
from gspread_asyncio import AsyncioGspreadWorksheet
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from gspread.utils import ValueInputOption

from .const import MsgType
from .utils import determine_msg_type, make_short_user_info


CLIENT = None
CLIENT_MANAGER = None
COLUMN_NAMES = 'When, UTC', 'Type', 'Who', 'To whom', 'Text', 'Filename', 'Forward', 'Subject'
LAST_COLUMN_SHEET_LETTER = string.ascii_uppercase[len(COLUMN_NAMES) - 1]


async def _get_client(bot):
    """
    gspread_asyncio docs require to do it this way
    """
    global CLIENT, CLIENT_MANAGER

    if not CLIENT_MANAGER:
        await bot.log('Create Asyncio Gspread Client Manager')
        CLIENT_MANAGER = gspread_asyncio.AsyncioGspreadClientManager(bot.get_gsheets_creds)
    if not CLIENT:
        await bot.log('Create Asyncio Gspread Client')
        CLIENT = await CLIENT_MANAGER.authorize()
    return CLIENT


def _to_gsheet_text(obj: Any) -> str:
    """
    Prepare object to be posted to Google Sheets as text
    """
    text = str(obj or '')
    if text and not text[0].isalpha():
        text = "'" + text
    return text


def _msg_to_row_data(msg: agtypes.Message) -> dict:
    """
    Convert message to Google Sheets fields.
    Fields different for admin and user are ommited or empty
    (to_whom, subject).
    """
    when = msg.date.strftime('%Y-%m-%d %H:%M:%S')
    typ = determine_msg_type(msg)
    who = make_short_user_info(msg.from_user)
    forward = 'Yes' if msg.forward_origin else 'No'
    text = msg.text or msg.caption

    filename = ''
    if typ in (MsgType.document, MsgType.audio, MsgType.video):
        filename = getattr(msg, typ).file_name

    if typ == MsgType.poll:
        text = msg.poll.question

    return {'when': when,
            'type': typ,
            'who': _to_gsheet_text(who),
            'text': _to_gsheet_text(text),
            'filename': _to_gsheet_text(filename),
            'forward': forward,
            'subject': ''}


async def _ensure_worksheet(doc):
    """
    Get or reate a worksheet with correct columns
    """
    now = datetime.utcnow()
    name = f'{now.year}-{now.month}'
    try:
        sheet = await doc.worksheet(name)
    except WorksheetNotFound:
        sheet = await doc.add_worksheet(title=name, cols=len(COLUMN_NAMES), rows=5)
        L = LAST_COLUMN_SHEET_LETTER
        await format_cells(sheet, f"A1:{L}1", ('bold', 'underline'))
        await sheet.update(f"A1:{L}1", [COLUMN_NAMES])

    try:  # delete default worksheet
        default_sheet = await doc.worksheet('Sheet1')
        await doc.del_worksheet(worksheet=default_sheet)
    except WorksheetNotFound:
        pass

    return sheet


async def _gsheets_connect(msg: agtypes.Message) -> None:
    """
    Prepare everything to insert a row:
    autheticate, ensure spreadsheet, ensure worksheet,
    calculate a place to insert, construct row fields
    """
    bot = msg.bot
    client = await _get_client(bot)

    gsheets_filename = bot.cfg['save_messages_gsheets_filename']
    await bot.log(f'Saving message to Google Sheet "{gsheets_filename}"')

    try:  # open spreadsheet document
        doc = await client.open(gsheets_filename)
    except SpreadsheetNotFound as exc:
        await bot.log_error(exc)
        return

    sheet = await _ensure_worksheet(doc)
    row_data = _msg_to_row_data(msg)
    index = len(await sheet.col_values(1)) + 1
    return sheet, row_data, index


async def _insert_row(sheet: AsyncioGspreadWorksheet, rd: dict, index: int) -> None:
    """
    Insert row field in right order into provided worksheet
    """
    row = (rd['when'], rd['type'], rd['who'], rd['to_whom'], rd['text'], rd['filename'],
           rd['forward'], rd['subject'])
    await sheet.insert_row(row, index=index, value_input_option=ValueInputOption.user_entered)


async def gsheets_save_admin_message(msg: agtypes.Message, tguser) -> None:
    """
    Save a message written by Admin in Google Sheets
    """
    sheet, row_data, index = await _gsheets_connect(msg)
    row_data['to_whom'] = _to_gsheet_text(make_short_user_info(tguser=tguser))
    await _insert_row(sheet, row_data, index)


async def gsheets_save_user_message(msg: agtypes.Message, highlight: bool=False) -> None:
    """
    Save a message written by User in Google Sheets
    """
    sheet, row_data, index = await _gsheets_connect(msg)

    botname = msg.bot.name.lower()
    to_whom = botname if botname.endswith('bot') else f'{botname} bot'
    row_data['to_whom'] = _to_gsheet_text(to_whom)
    row_data['subject'] = (await msg.bot.db.tguser.get(user=msg.from_user)).subject
    await _insert_row(sheet, row_data, index)

    if highlight:
        await format_cells(sheet, f"A{index}:D{index}", ('bold',))


async def format_cells(sheet, ranje: str, modes: tuple[str], switch: bool=True):
    """
    Shortcut for basic cell format.
    Modes: bold, italic, underline etc.
    switch=False desables the chosen formatting mode.
    """
    modesdict = {m: switch for m in modes}
    await sheet.batch_format([{"range": ranje, "format": {"textFormat": modesdict}}])
