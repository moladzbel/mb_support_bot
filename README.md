
# mb_support_bot

Open Source support bot for Telegram based on aiogram. Not ready for production yet.

## Quick start

- copy `shared/.env.example` file to `shared/.env`
- fill the variables in `.env` file
- create venv: `python3 -m venv .venv`
- activate it: `. .venv/bin/activate`
- install dependencies: `pip install -r requirements.txt`
- run migrations `python3 run.py migrate`
- run the bots with `python3 run.py`

## System commands

- statically check the code: `ruff check .` (`pip install ruff` for the first time)
- create migration scripts after changing DB schema: `python run.py makemigrations`
- apply migration scripts to all the bot databases: `python run.py migrate`
