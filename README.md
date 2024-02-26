
# mb_support_bot

Support bot for Telegram based on aiogram, SQLAlchemy, and Alembic. Allows to run any number of support bots in one process, each with its own configuration and a database.

## Run in production with Docker

- `cd mb_support_bot`
- `cp .env.example .env`, fill the variables in the `.env` file (see available options [here](#available-.env-options)
- Build the container: `docker build -t mb_support_bot .`
- Migrate databases: `docker run -v $(pwd)/shared:/bot/shared --env-file .env mb_support_bot python run.py --no-dotenv migrate`
- Run the bots: `docker run -d -v $(pwd)/shared:/bot/shared --env-file .env mb_support_bot`

SQLite databases and logs are in `shared/` dir.

## Run natively in local environment

- `cd mb_support_bot`
- `cp .env.example .env`, fill the variables in the `.env` file
- Create venv: `python3 -m venv .venv`
- Activate the venv: `. .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Migrate databases `python3 run.py migrate`
- Run the bots with `python3 run.py`

## System commands

- Statically check the code: `ruff check .` (`pip install ruff` for the first time)
- Create migration scripts after changing DB schema: `python run.py makemigrations`
- Apply migration scripts to all the bot databases: `python run.py migrate`

## Available .env options

The following variables are available in `.env` file:
- `BOTS_ENABLED` - names of all the bots you want to run, separated by comma. Example: `YOUTH_BLOC,LEGALIZE`. A name from this list used in below vars in place of `{BOT_NAME}`.
- `{BOT_NAME}_ADMIN_GROUP_ID` - ID of a Telegram group, where the bot should forward messages from users. The group must has Topic enabled, and the bot has to be admin with 'Manage topics' permission.
- `{BOT_NAME}_HELLO_MSG` - Optional. Your first message to a new user.
- `{BOT_NAME}_DB_URL` - Optional. Database URL if you want to use something other than SQLite.
- `{BOT_NAME}_DB_ENGINE` - Optional. Database library to use. Currently supported values are `memory` and `aiosqlite`.
