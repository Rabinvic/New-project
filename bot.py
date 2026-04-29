import os
from datetime import date, datetime
from typing import Any

import discord
import httpx
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"


load_dotenv()


def parse_date(value: str | None) -> date:
    if not value:
        return date.today()

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise app_commands.AppCommandError(
            "Please use a date in YYYY-MM-DD format, like 2026-04-29."
        ) from exc


async def fetch_mlb_games(game_date: date, team_id: int | None = None) -> list[dict[str, Any]]:
    params: dict[str, str | int] = {
        "sportId": 1,
        "date": game_date.isoformat(),
        "hydrate": "linescore,team",
    }

    if team_id is not None:
        params["teamId"] = team_id

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(MLB_SCHEDULE_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    games: list[dict[str, Any]] = []
    for day in payload.get("dates", []):
        games.extend(day.get("games", []))
    return games


def format_game(game: dict[str, Any]) -> str:
    teams = game["teams"]
    away = teams["away"]
    home = teams["home"]
    away_name = away["team"]["name"]
    home_name = home["team"]["name"]
    status = game["status"]["detailedState"]

    away_score = away.get("score")
    home_score = home.get("score")

    if away_score is None or home_score is None:
        game_time = datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00"))
        timestamp = int(game_time.timestamp())
        return f"**{away_name} at {home_name}** - {status}, <t:{timestamp}:t>"

    line = f"**{away_name} {away_score}, {home_name} {home_score}** - {status}"

    if status not in {"Final", "Game Over"}:
        inning_state = game.get("linescore", {}).get("inningState")
        current_inning = game.get("linescore", {}).get("currentInningOrdinal")
        if inning_state and current_inning:
            line += f" ({inning_state} {current_inning})"

    return line


def build_results_message(games: list[dict[str, Any]], game_date: date, team_filter: str | None = None) -> str:
    readable_date = f"{game_date:%B} {game_date.day}, {game_date.year}"

    header = "MLB games"
    if team_filter:
        header += f" for {team_filter}"
    header += f" for {readable_date}:"

    if not games:
        suffix = f" for {team_filter}" if team_filter else ""
        return f"No MLB games found for {readable_date}{suffix}."

    formatted_games = "\n".join(format_game(game) for game in games)
    return f"{header}\n{formatted_games}"


class MlbBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await self.tree.sync()


bot = MlbBot()


@bot.tree.command(name="mlb", description="Show MLB game results for a date.")
@app_commands.describe(day="Optional date in YYYY-MM-DD format. Defaults to today.")
@app_commands.describe(team="Optional team name (e.g., Yankees, Mets, Dodgers)")
async def mlb(interaction: discord.Interaction, day: str | None = None, team: str | None = None) -> None:
    await interaction.response.defer(thinking=True)

    game_date = parse_date(day)

    # Resolve team name to team ID if provided
    team_id: int | None = None
    team_filter: str | None = None
    if team:
        team_lower = team.lower().strip()
        if team_lower in TEAMS:
            team_id = TEAMS[team_lower]
            team_filter = team
        else:
            await interaction.followup.send(
                f"Team '{team}' not found. Please use a valid team name like 'Yankees', 'Mets', 'Dodgers', etc."
            )
            return

    try:
        games = await fetch_mlb_games(game_date, team_id)
    except httpx.HTTPError:
        await interaction.followup.send(
            "I couldn't reach the MLB results service right now. Please try again in a minute."
        )
        return

    await interaction.followup.send(build_results_message(games, game_date, team_filter))


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user}")


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("Set DISCORD_TOKEN in your environment or .env file.")
    bot.run(token)


if __name__ == "__main__":
    main()
