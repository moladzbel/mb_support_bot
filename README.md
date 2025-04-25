# mb_support_bot

Support (feedback) bot for Telegram. Based on aiogram and SQLAlchemy.

Features:
- Run as many bots as you want in one process. Each bot has its own settings and database
- Separate topic in the admin group for each user who writes to the bot
- Simple bot menu builder using `toml` file
- Optional message self-destruction on the user's side, triggered by a timer
- Admins can broadcast a message to all the users directly from the admin group
- Optional archiving of all the messages to a Google Sheet
- Reporting of bot statistics once a week in the admin group

![Alt text](media/menu_screenshot.png?raw=true "Menu screenshot")

## Run for the first time

1. Create a bot in @BotFather, enable access to messages
1. Install latest Docker and Docker Compose
1. Clone the repo
1. `cd mb_support_bot`
1. `cp .env.example .env`
1. Add some name unique for your first bot to `BOTS_ENABLED` list in `.env`, for example `BOTS_ENABLED=MYBOT`
1. Place bot token to `{BOTNAME}_TOKEN` var in `.env`, e.g. `MYBOT_TOKEN=1312:qwerty`
1. Restart the container: `docker compose up -d`
1. Create a new group, enable Topics in the group settings
1. Add your bot to the group, make it admin with "Manage topics" permission
1. Copy group ID reported by the bot to `{BOTNAME}_ADMIN_GROUP_ID` var in `.env`. Ensure it starts with `-100`. If it's not, add -100 manually. Example: `MYBOT_ADMIN_GROUP_ID=-1001337`
1. Restart the container: `docker compose down; docker compose up -d`, wait 10 seconds until it fully started
1. Finally, write to the bot to ensure it works

Mention the bot with @ in General topic of the admin group to perform admin actions.

Databases and logs are stored in `shared/` dir.

If `.env` has been modified, restart the container: `docker compose down; docker compose up -d`

## Documentation

More info on how to set up custom reply text, bot menu, and other see in [docs](DOCS.md).
