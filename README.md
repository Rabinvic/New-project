This is an attempt at learning how to use AI models to create programming projects.
This is my first time using a model, in this case GPT 5.5 through Codex to "vibe" code

# MLB Discord Bot

A Python Discord bot that returns MLB game results using Discord slash commands.

## Setup

1. Create a Discord application and bot at <https://discord.com/developers/applications>.
2. Copy `.env.example` to `.env` and set `DISCORD_TOKEN`.
3. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

4. Run the bot:

```powershell
python bot.py
```

## Commands

`/mlb`

Shows today's MLB games and results.

`/mlb day:2026-04-29`

Shows MLB games and results for a specific date.

`/mlb box_score:True`

Shows detailed inning-by-inning box scores for completed games.

`/mlb team:Yankees box_score:True`

Shows detailed box scores for completed Yankees games.

`/schedule add team:Yankees time:09:00 box_score:True`

Creates a daily Yankees notification with detailed box scores for completed games.

## Discord Invite Permissions

When inviting the bot, include these scopes:

- `bot`
- `applications.commands`

The bot only needs permission to send messages in channels where you use it.
