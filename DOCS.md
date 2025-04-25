## Available .env options

The following variables are available in `.env` file:
- `BOTS_ENABLED` - names of all the bots you want to run, separated by comma. Example: `YOUTH_BLOC,LEGALIZE`. A name from this list used in below vars in place of `{BOTNAME}`. Do not change the name after the first start of the bot.
- `{BOTNAME}_TOKEN` - Bot's secret token.
- `{BOTNAME}_ADMIN_GROUP_ID` - ID of a Telegram group, where the bot should forward messages from users. Example: `-1002014482535`. The group must have the "Topics" enabled, and the bot has to be an admin with 'Manage topics' permission.
- `{BOTNAME}_HELLO_MSG` - Optional. A welcome message to a new user. This and other messages (`{BOTNAME}_HELLO_PS`, `{BOTNAME}_FIRST_REPLY`) can use all the HTML tags supported by Telegram for styling: see *Styling messages* section below.
- `{BOTNAME}_HELLO_PS` - Optional. A P.S. in hello message. Default is "The bot is created by @moladzbel".
- `{BOTNAME}_FIRST_REPLY` - Optional. Text of an automatic reply to the first meaningful user mesasge (not the /start) sent to the bot.
- `{BOTNAME}_DB_URL` - Optional. Database URL if you want to use something other than SQLite in `shared/`.
- `{BOTNAME}_DB_ENGINE` - Optional. Database library to use. Only `aiosqlite` is currently supported.
- `{BOTNAME}_SAVE_MESSAGES_GSHEETS_CRED_FILE` - Optional. Google Service Account credentials file. If set, all the income and outcome bot messages are being saved to Google Sheets. See the setup steps in "How To" below.
- `{BOTNAME}_SAVE_MESSAGES_GSHEETS_FILENAME` - Optional. File name of a spreadsheet where to send all the messages.
- `{BOTNAME}_DESTRUCT_USER_MESSAGES_FOR_USER` - Optional. If the bot should delete user messages in the user chat after specified amount of hours. Accepted values are between 1 and 47.
- `{BOTNAME}_DESTRUCT_BOT_MESSAGES_FOR_USER` - Optional. If the bot should delete its own messages in the user chat after specified amount of hours. Accepted values are between 1 and 47.

## Styling messages

Messages set as .env variables can be formatted with Telegram HTML tags, such as `<b>`, `<i>`, `<s>` and so on, see the full list [here](https://publer.com/help/en/article/how-to-style-telegram-text-using-html-tags-xdepnw/). One can also use `\n` for a new line.

Example (a line in `.env` file):

`MYBOT_HELLO_MSG=Hi!\nThis is a support bot of <b>Title</b> channel.`

## Setting up bot menu

To setup a user menu for your bot, create a file `shared/{BOTNAME}/menu.toml`. See example of it's content in `menu.example.toml` file. There are 5 button modes currently supported:
- answer: just a text answer
- file: send a file to the user
- link: open an external link
- menu: open a submenu
- subject: allows users to choose subject they are willing to discuss. Useful for statistics.

## How To

### ... add a new bot to the already running instance

1. Create a bot in @BotFather, enable access to messages
1. Add some name unique for the bot to `BOTS_ENABLED` list in `.env`
1. Place bot token to `{BOTNAME}_TOKEN` var in `.env`
1. Create a new group, enable Topics in the group settings
1. Restart the container: `docker compose down; docker compose up -d`
1. Add your bot to the group, make it admin with "Manage topics" permission
1. Copy chat ID reported by the bot to `{BOTNAME}_ADMIN_GROUP_ID` var in `.env`
1. Restart the container again

### ... change the group for existing bot

1. add the bot to a new group
1. place the new `{BOTNAME}_ADMIN_GROUP_ID` to `.env`
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
1. Specify the name of the JSON file in `.env` file in `{BOTNAME}_SAVE_MESSAGES_GSHEETS_CRED_FILE` variable. Example: `MYBOT_SAVE_MESSAGES_GSHEETS_CRED_FILE=mybot-ga-api-ce213a7201e5.json`
1. Specify the name of your shared spreadsheet file in `.env` file in `{BOTNAME}_SAVE_MESSAGES_GSHEETS_FILENAME` variable. Example: `MYBOT_SAVE_MESSAGES_GSHEETS_FILENAME=Mybot archive`.
1. Restart the bot to re-read `.env`

## Hacking

- Statically check the code: `ruff check .` (`pip install ruff` first)
- Run without docker: create venv, install requirements.txt, and run the bot as `python code/run.py`
- Create migration scripts after changing DB schema: `cd code; python run.py makemigrations`
- Apply migration scripts to all the enabled bot databases: `cd code; python run.py migrate`
