import os
from datetime import date, datetime, timedelta
from typing import Any

import discord
import httpx
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

import schedules


MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"

# Team name/abbreviation to MLB team ID mapping
TEAMS: dict[str, int] = {
    # American League - East
    "yankees": 147, "nyy": 147, "new york yankees": 147,
    "red sox": 111, "bos": 111, "boston red sox": 111,
    "orioles": 110, "bal": 110, "baltimore orioles": 110,
    "rays": 139, "tb": 139, "tampa bay": 139, "tampa bay rays": 139,
    "blue jays": 141, "tor": 141, "toronto": 141, "toronto blue jays": 141,
    # American League - Central
    "guardians": 114, "cle": 114, "cleveland": 114, "cleveland guardians": 114,
    "white sox": 145, "cws": 145, "chw": 145, "chicago white sox": 145,
    "tigers": 116, "det": 116, "detroit": 116, "detroit tigers": 116,
    "royals": 118, "kc": 118, "kansas city": 118, "kansas city royals": 118,
    "twins": 142, "min": 142, "minnesota": 142, "minnesota twins": 142,
    # American League - West
    "astros": 117, "hou": 117, "houston": 117, "houston astros": 117,
    "angels": 108, "laa": 108, "ana": 108, "los angeles angels": 108, "anaheim": 108,
    "athletics": 133, "oak": 133, "oakland": 133, "oakland athletics": 133,
    "rangers": 140, "tex": 140, "texas": 140, "texas rangers": 140,
    "mariners": 136, "sea": 136, "seattle": 136, "seattle mariners": 136,
    # National League - East
    "mets": 121, "nym": 121, "new york mets": 121,
    "braves": 144, "atl": 144, "atlanta": 144, "atlanta braves": 144,
    "phillies": 143, "phi": 143, "philadelphia": 143, "philadelphia phillies": 143,
    "marlins": 146, "mia": 146, "miami": 146, "miami marlins": 146,
    "nationals": 120, "wsh": 120, "was": 120, "washington": 120, "washington nationals": 120,
    # National League - Central
    "cubs": 112, "chc": 112, "chicago cubs": 112,
    "cardinals": 138, "stl": 138, "st. louis": 138, "st louis cardinals": 138,
    "brewers": 158, "mil": 158, "milwaukee": 158, "milwaukee brewers": 158,
    "reds": 113, "cin": 113, "cincinnati": 113, "cincinnati reds": 113,
    "pirates": 134, "pit": 134, "pittsburgh": 134, "pittsburgh pirates": 134,
    # National League - West
    "dodgers": 119, "lad": 119, "la": 119, "los angeles dodgers": 119,
    "padres": 135, "sd": 135, "san diego": 135, "san diego padres": 135,
    "giants": 137, "sf": 137, "san francisco": 137, "san francisco giants": 137,
    "diamondbacks": 109, "ari": 109, "az": 109, "arizona": 109, "arizona diamondbacks": 109, "snakes": 109,
    "rockies": 115, "col": 115, "colorado": 115, "colorado rockies": 115,
}

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


def build_notification_message(yesterday_games: list[dict], today_games: list[dict], team_name: str | None) -> str:
    """Build a notification message with yesterday's results and today's games."""
    lines = []
    
    # Header
    header = "⚾ MLB Game Update"
    if team_name:
        header += f" - {team_name}"
    lines.append(header)
    lines.append("")
    
    # Yesterday's results (completed games)
    yesterday_results = [g for g in yesterday_games if g.get("status", {}).get("detailedState") == "Final"]
    if yesterday_results:
        lines.append("📅 **Yesterday's Results:**")
        for game in yesterday_results:
            lines.append(format_game_boxscore(game))
        lines.append("")
    
    # Today's games
    if today_games:
        lines.append("📅 **Today's Games:**")
        for game in today_games:
            lines.append(format_game(game))
    else:
        lines.append("📅 **Today's Games:**")
        lines.append("No games scheduled.")
    
    return "\n".join(lines)


def format_game_boxscore(game: dict[str, Any]) -> str:
    """Format a completed game as a box score."""
    teams = game["teams"]
    away = teams["away"]
    home = teams["home"]
    away_name = away["team"]["name"]
    home_name = home["team"]["name"]
    away_score = away.get("score", 0)
    home_score = home.get("score", 0)
    return f"  {away_name} {away_score}, {home_name} {home_score} - Final"


class MlbBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await self.tree.sync()
        self.check_schedules.start()

    @tasks.loop(minutes=1)
    async def check_schedules(self) -> None:
        """Check for scheduled notifications and send them."""
        now = datetime.now()
        current_time = f"{now.hour:02d}:{now.minute:02d}"
        
        matching = schedules.get_active_schedules_for_time(now.hour, now.minute)
        
        for schedule in matching:
            try:
                # Get yesterday and today games
                yesterday = date.today() - timedelta(days=1)
                today = date.today()
                
                yesterday_games = await fetch_mlb_games(yesterday, schedule.team_id)
                today_games = await fetch_mlb_games(today, schedule.team_id)
                
                # Build and send notification
                message = build_notification_message(
                    yesterday_games, 
                    today_games, 
                    schedule.team_name
                )
                
                channel = self.get_channel(schedule.channel_id)
                if channel:
                    await channel.send(message)
            except Exception as e:
                print(f"Error sending notification for schedule {schedule.id}: {e}")


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


@bot.tree.command(name="schedule", description="Manage MLB game notifications.")
async def schedule(interaction: discord.Interaction) -> None:
    """Show help for schedule commands."""
    await interaction.response.send_message(
        "Use `/schedule add` to create a notification, `/schedule list` to view your schedules, or `/schedule remove` to delete one.",
        ephemeral=True
    )


@schedule.command(name="add", description="Add a daily MLB game notification.")
@app_commands.describe(team="Team name (e.g., Yankees, Mets, Dodgers) or leave empty for all")
@app_commands.describe(time="Time to receive notification (e.g., 14:00 for 2 PM)")
async def schedule_add(interaction: discord.Interaction, team: str | None, time: str) -> None:
    """Add a new schedule for daily notifications."""
    await interaction.response.defer(ephemeral=True)
    
    # Validate time format
    try:
        hour, minute = map(int, time.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError()
    except ValueError:
        await interaction.followup.send("Invalid time format. Use HH:MM (e.g., 14:00 for 2 PM).", ephemeral=True)
        return
    
    # Resolve team if provided
    team_id: int | None = None
    team_name = "All Teams"
    if team:
        team_lower = team.lower().strip()
        if team_lower in TEAMS:
            team_id = TEAMS[team_lower]
            team_name = team
        else:
            await interaction.followup.send(
                f"Team '{team}' not found. Please use a valid team name like 'Yankees', 'Mets', 'Dodgers', etc.",
                ephemeral=True
            )
            return
    
    # Create schedule
    schedule = schedules.add_schedule(
        channel_id=interaction.channel_id,
        team_id=team_id,
        team_name=team_name,
        time=time
    )
    
    await interaction.followup.send(
        f"✅ Schedule created! ID: `{schedule.id}`\n"
        f"You'll receive MLB game updates for **{team_name}** at **{time}** daily in this channel.",
        ephemeral=True
    )


@schedule.command(name="list", description="List all notification schedules for this channel.")
async def schedule_list(interaction: discord.Interaction) -> None:
    """List all schedules for the current channel."""
    channel_schedules = schedules.get_channel_schedules(interaction.channel_id)
    
    if not channel_schedules:
        await interaction.response.send_message(
            "No schedules set up for this channel. Use `/schedule add` to create one.",
            ephemeral=True
        )
        return
    
    lines = ["**Your schedules:**"]
    for s in channel_schedules:
        status = "✅" if s.enabled else "❌"
        lines.append(f"`{s.id}` - {s.team_name} at **{s.time}** {status}")
    
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@schedule.command(name="remove", description="Remove a notification schedule.")
@app_commands.describe(schedule_id="The ID of the schedule to remove")
async def schedule_remove(interaction: discord.Interaction, schedule_id: str) -> None:
    """Remove a schedule by ID."""
    if schedules.remove_schedule(schedule_id):
        await interaction.response.send_message(
            f"✅ Schedule `{schedule_id}` removed.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"Schedule `{schedule_id}` not found. Use `/schedule list` to see available IDs.",
            ephemeral=True
        )


@schedule.command(name="toggle", description="Enable or disable a notification schedule.")
@app_commands.describe(schedule_id="The ID of the schedule to toggle")
async def schedule_toggle(interaction: discord.Interaction, schedule_id: str) -> None:
    """Toggle a schedule on or off."""
    new_state = schedules.toggle_schedule(schedule_id)
    if new_state is None:
        await interaction.response.send_message(
            f"Schedule `{schedule_id}` not found. Use `/schedule list` to see available IDs.",
            ephemeral=True
        )
        return
    
    status = "enabled" if new_state else "disabled"
    await interaction.response.send_message(
        f"✅ Schedule `{schedule_id}` {status}.",
        ephemeral=True
    )


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
