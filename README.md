
# mb_support_bot

Support bot for Telegram based on aiogram, SQLAlchemy, and Alembic. Allows to run any number of support bots in one process, each with its own configuration and database.

## Run in production with Docker

- Install Docker: https://docs.docker.com/engine/install/
- `cd mb_support_bot`
- `cp .env.example .env`, fill the variables in the `.env` file (see available options [here](#available-env-options)
- Build the container: `docker build -t mb_support_bot .`
- Migrate databases: `docker run -v $(pwd)/shared:/bot/shared --env-file .env mb_support_bot python run.py --no-dotenv migrate`
- Run the bots: `docker run -d -v $(pwd)/shared:/bot/shared --env-file .env --restart always mb_support_bot`

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
- `BOTS_ENABLED` - names of all the bots you want to run, separated by comma. Example: `YOUTH_BLOC,LEGALIZE`. A name from this list used in below vars in place of `{BOT_NAME}`. Do not change the name after the first start of the bot.
- `{BOT_NAME}_ADMIN_GROUP_ID` - ID of a Telegram group, where the bot should forward messages from users. Example: `-1002014482535`. The group must have the "Topics" enabled, and the bot has to be admin with 'Manage topics' permission.
- `{BOT_NAME}_HELLO_MSG` - Optional. Your first message to a new user.
- `{BOT_NAME}_DB_URL` - Optional. Database URL if you want to use something other than SQLite in `shared/`.
- `{BOT_NAME}_DB_ENGINE` - Optional. Database library to use. Currently supported values are `memory` and `aiosqlite`.

## How to

### ... add a new bot to the already running instance

- Create a bot in @BotFather, enable access to messages
- Add some name unique for the bot to `BOTS_ENABLED` list in `.env`
- Place bot token to `{BOT_NAME}_TOKEN` var in `.env`
- Create a new group, enable Topics in the group settings
- Stop the container, migrate database, and run it again (see the commands in the [first section](#run-in-production-with-docker))
- Add your bot to the group, make it admin with "Manage topics" permission
- Copy chat ID reported by the bot to `{BOT_NAME}_ADMIN_GROUP_ID` var in `.env`
- Stop the container, and run it as usual

### ... change the group for existing bot

- add the bot to a new group
- rename the bot in `.env`. Use a name not existing in `.env` before
- place the new `{BOT_NAME}_ADMIN_GROUP_ID` to `.env`
- Stop the container, migrate database, and run it again (see the commands in the [first section](#run-in-production-with-docker))
