# mb_support_bot

Support (feedback) bot for Telegram based on aiogram, SQLAlchemy, and Alembic.

Features:
- Ability to run any number of bots in one process, each with its own configuration and a database
- A separate topic in admin group for each user
- Easy bot menu builder using `toml` file
- Optional messages self-destruction on user side
- Broadcasting a message to all the users right from the admin group
- Optional archiving all the messages to your Google Sheet
- Reporting bot statistics once a week in your admin group

![Alt text](media/menu_screenshot.png?raw=true "Menu screenshot")

## Run in production

- Install latest Docker and Docker Compose
- `cd mb_support_bot`
- `cp .env.example .env`
- Fill the variables in the `.env` file (see available options [here](#available-env-options)).
- Run the bots: `docker compose up -d`

Databases and logs are in `shared/` dir.
If `.env` has been modified, restart the container: `docker compose down; docker compose up -d`

## Available .env options

The following variables are available in `.env` file:
- `BOTS_ENABLED` - names of all the bots you want to run, separated by comma. Example: `YOUTH_BLOC,LEGALIZE`. A name from this list used in below vars in place of `{BOT_NAME}`. Do not change the name after the first start of the bot.
- `{BOT_NAME}_TOKEN` - Bot's secret token.
- `{BOT_NAME}_ADMIN_GROUP_ID` - ID of a Telegram group, where the bot should forward messages from users. Example: `-1002014482535`. The group must have the "Topics" enabled, and the bot has to be an admin with 'Manage topics' permission.
- `{BOT_NAME}_HELLO_MSG` - Optional. Your welcome message to a new user.
- `{BOT_NAME}_HELLO_PS` - Optional. Your P.S. in hello message. Default is "The bot is created by @moladzbel".
- `{BOT_NAME}_DB_URL` - Optional. Database URL if you want to use something other than SQLite in `shared/`.
- `{BOT_NAME}_DB_ENGINE` - Optional. Database library to use. Only `aiosqlite` is currently supported.
- `{BOT_NAME}_SAVE_MESSAGES_GSHEETS_CRED_FILE` - Optional. Google Service Account credentials file. If set, all the income and outcome bot messages are being saved to Google Sheets. See the setup steps in "How To" below.
- `{BOT_NAME}_SAVE_MESSAGES_GSHEETS_FILENAME` - Optional. File name of a spreadsheet where to send all the messages.
- `{BOT_NAME}_DESTRUCT_USER_MESSAGES_FOR_USER` - Optional. If the bot should delete user messages in the user chat after specified amount of hours. Accepted values are between 1 and 47.
- `{BOT_NAME}_DESTRUCT_BOT_MESSAGES_FOR_USER` - Optional. If the bot should delete its own messages in the user chat after specified amount of hours. Accepted values are between 1 and 47.

## Setting up bot menu

To setup a user menu for your bot, create a file `shared/{BOT_NAME}/menu.toml`. See example of it's content in `menu.example.toml` file. There are 5 button modes currently supported:
- answer: just a text answer
- file: send a file to the user
- link: open an external link
- menu: open a submenu
- subject: allows users to choose subject they are willing to discuss. Useful for statistics.

## How To

### ... add a new bot to the already running instance

1. Create a bot in @BotFather, enable access to messages
1. Add some name unique for the bot to `BOTS_ENABLED` list in `.env`
1. Place bot token to `{BOT_NAME}_TOKEN` var in `.env`
1. Create a new group, enable Topics in the group settings
1. Restart the container: `docker compose down; docker compose up -d`
1. Add your bot to the group, make it admin with "Manage topics" permission
1. Copy chat ID reported by the bot to `{BOT_NAME}_ADMIN_GROUP_ID` var in `.env`
1. Restart the container again

### ... change the group for existing bot

1. add the bot to a new group
1. rename the bot in `.env`. Use a name not existing in `.env` before
1. place the new `{BOT_NAME}_ADMIN_GROUP_ID` to `.env`
1. Restart the container: `docker compose down; docker compose up -d`

### ... save all the income and outcome bot messages to Google Sheets

1. Head to [Google Developers Console](https://console.developers.google.com/) and create a new project (or select the one you already have).
1. Click "+ Enable APIs and services"
1. In the box labeled “Search for APIs and Services”, search for “Google Drive API” and enable it.
1. In the box labeled “Search for APIs and Services”, search for “Google Sheets API” and enable it.
1. Go to "APIs & Services > Credentials" and choose “Create credentials > Service account”. Make "Service account name" something similar to the bot name.
1. Click “Create” and “Done”.
1. Press “Manage service accounts” above Service Accounts.
1. Press on ⋮ near recently created service account and select “Manage keys” and then click on “ADD KEY > Create new key”.
1. Select JSON key type and press “Create”. You will automatically download a JSON file with credentials.
1. Important! In the JSON file there is an app email in "client_email" field (it's the same as in "APIs & Services > Credentials > Service Accounts"). Go to your spreadsheet and share it with this client_email, just like you do with any other Google account.
1. Place the JSON file on a server, to `mb_support_bot/shared/{bot_name}/{your_file.json}`.
1. Specify the name of the JSON file in `.env` file in `{BOT_NAME}_SAVE_MESSAGES_GSHEETS_CRED_FILE` variable. Example: `MYBOT_SAVE_MESSAGES_GSHEETS_CRED_FILE=mybot-ga-api-ce213a7201e5.json`
1. Specify the name of your shared spreadsheet file in `.env` file in `{BOT_NAME}_SAVE_MESSAGES_GSHEETS_FILENAME` variable. Example: `MYBOT_SAVE_MESSAGES_GSHEETS_FILENAME=Mybot archive`.
1. Restart the bot to re-read `.env`

## Development

- Statically check the code: `ruff check .` (`pip install ruff` first)
- Create migration scripts after changing DB schema: `python run.py makemigrations`
- Apply migration scripts to all the bot databases: `python run.py migrate`
