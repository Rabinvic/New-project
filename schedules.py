"""Schedule data model and storage for MLB game notifications."""
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEDULES_FILE = Path(__file__).parent / "schedules.json"


@dataclass
class Schedule:
    """Represents a scheduled notification for MLB games."""
    id: str
    channel_id: int
    team_id: int | None  # None = all teams
    team_name: str  # Human-readable team name for display
    time: str  # HH:MM format in 24-hour
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "time": self.time,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Schedule":
        return cls(
            id=data["id"],
            channel_id=data["channel_id"],
            team_id=data["team_id"],
            team_name=data["team_name"],
            time=data["time"],
            enabled=data.get("enabled", True),
        )


def load_schedules() -> list[Schedule]:
    """Load all schedules from the JSON file."""
    if not SCHEDULES_FILE.exists():
        return []
    try:
        with open(SCHEDULES_FILE, "r") as f:
            data = json.load(f)
            return [Schedule.from_dict(s) for s in data]
    except (json.JSONDecodeError, KeyError):
        return []


def save_schedules(schedules: list[Schedule]) -> None:
    """Save all schedules to the JSON file."""
    with open(SCHEDULES_FILE, "w") as f:
        json.dump([s.to_dict() for s in schedules], f, indent=2)


def add_schedule(channel_id: int, team_id: int | None, team_name: str, time: str) -> Schedule:
    """Add a new schedule and return it."""
    schedules = load_schedules()
    new_schedule = Schedule(
        id=str(uuid.uuid4())[:8],
        channel_id=channel_id,
        team_id=team_id,
        team_name=team_name,
        time=time,
        enabled=True,
    )
    schedules.append(new_schedule)
    save_schedules(schedules)
    return new_schedule


def remove_schedule(schedule_id: str) -> bool:
    """Remove a schedule by ID. Returns True if removed."""
    schedules = load_schedules()
    initial_len = len(schedules)
    schedules = [s for s in schedules if s.id != schedule_id]
    if len(schedules) < initial_len:
        save_schedules(schedules)
        return True
    return False


def get_channel_schedules(channel_id: int) -> list[Schedule]:
    """Get all schedules for a specific channel."""
    return [s for s in load_schedules() if s.channel_id == channel_id]


def toggle_schedule(schedule_id: str) -> bool | None:
    """Toggle a schedule's enabled state. Returns new state or None if not found."""
    schedules = load_schedules()
    for s in schedules:
        if s.id == schedule_id:
            s.enabled = not s.enabled
            save_schedules(schedules)
            return s.enabled
    return None


def get_active_schedules_for_time(hour: int, minute: int) -> list[Schedule]:
    """Get all enabled schedules that match the given time."""
    time_str = f"{hour:02d}:{minute:02d}"
    return [s for s in load_schedules() if s.enabled and s.time == time_str]