RAILWAY DEPLOYMENT — DISCORD SERVER STRUCTURE CLONER
====================================================

IMPORTANT ABOUT FREE HOSTING
----------------------------
Railway's free/trial allowance and always-on availability can change.
A free account may have limited credits or trial restrictions; do not assume
a free deployment will stay online forever. Check Railway's current pricing
and usage page before deploying. This project has no paid database or add-ons.

1) CREATE YOUR DISCORD APPLICATION
----------------------------------
- Visit https://discord.com/developers/applications
- Create an application and add a Bot.
- Copy/reset the bot token. Keep it secret.
- OAuth2 > URL Generator:
  Scopes: bot, applications.commands
  Bot permissions:
    View Channels
    Manage Channels
    Manage Roles
    Manage Emojis and Stickers
- Invite the bot to BOTH the source and destination servers.
- Source server: grant View Channels.
- Destination server: grant all four permissions above.
- Move the bot's role high enough in the destination role list to create
  the roles it needs. Administrator is not required.

2) UPLOAD THE PROJECT TO GITHUB
-------------------------------
- Create a new PRIVATE GitHub repository.
- Upload bot.py, requirements.txt, Procfile, railway.toml, and .gitignore.
- Do NOT upload your real token or a .env file.

3) DEPLOY ON RAILWAY
--------------------
- Visit https://railway.com/ and sign in.
- Create a project > Deploy from GitHub Repo.
- Select your private repository.
- In the Railway service, open Variables and add:
    DISCORD_TOKEN = your actual Discord bot token
- Deploy / redeploy the service.
- Open Deployments or Logs and confirm the bot logs in and syncs slash commands.

4) USE THE BOT
--------------
In the destination Discord server:
    /clone source_server_id: 123456789012345678

The bot must be in the source server too. A server ID alone does not provide
access. The bot does not bypass Discord permissions.

5) IF IT DOES NOT WORK
----------------------
- "I can't access that server": invite bot to source server.
- Missing permission: verify the individual server permissions.
- Role errors: move bot role above roles it must create; managed roles cannot
  be copied.
- Slash command missing: check Railway logs and ensure applications.commands
  was selected when inviting.
- Emoji copy failures: destination emoji limit, source access, or Discord API
  restrictions may prevent some emojis.
- If interrupted midway, some objects may already exist. This bot does not
  automatically roll back or deduplicate partially copied objects.

WHAT IT COPIES / DOES NOT COPY
------------------------------
Copies roles (excluding managed/integration roles), categories, text,
announcement, voice and stage channels, channel topics, text slowmode,
NSFW flag, role-based overwrites, and accessible custom emojis.

Does not copy messages, attachments, members, bots, integrations, webhooks,
server icon/banner, boosts, onboarding, or every server setting.
Member-specific overwrites are copied only for members present in both servers.

SECURITY
--------
Never commit your token to GitHub. Store it only in Railway Variables.
If it leaks, reset it immediately in the Discord Developer Portal.
Only back up servers you own or have permission to copy.
