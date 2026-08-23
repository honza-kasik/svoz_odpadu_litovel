from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = ROOT / "data" / "site_config.json"
CONFIG_FIELDS = {
    "target_year",
    "waste_active_year",
    "bio_active_year",
    "calendar_years",
    "bio_schedule_file",
}


@dataclass(frozen=True)
class ProjectConfig:
    target_year: int
    waste_active_year: int
    bio_active_year: int
    calendar_years: tuple[int, ...]
    bio_schedule_path: Path

    @property
    def date_start(self) -> datetime:
        return datetime(min(self.calendar_years), 1, 1)

    @property
    def date_end(self) -> datetime:
        return datetime(max(self.calendar_years), 12, 31)


def load_project_config(path: str | Path = DEFAULT_CONFIG_PATH) -> ProjectConfig:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != CONFIG_FIELDS:
        raise ValueError(f"{path}: expected exactly {sorted(CONFIG_FIELDS)}")
    target_year = raw["target_year"]
    waste_active_year = raw["waste_active_year"]
    bio_active_year = raw["bio_active_year"]
    calendar_years = raw["calendar_years"]
    bio_schedule_file = raw["bio_schedule_file"]
    if any(not isinstance(year, int) for year in (target_year, waste_active_year, bio_active_year)):
        raise ValueError(f"{path}: active years must be integers")
    if waste_active_year > target_year or bio_active_year > target_year:
        raise ValueError(f"{path}: active data years cannot be newer than target_year")
    if (
        not isinstance(calendar_years, list)
        or not calendar_years
        or any(not isinstance(year, int) for year in calendar_years)
        or calendar_years != sorted(set(calendar_years))
        or calendar_years != list(range(min(calendar_years), max(calendar_years) + 1))
    ):
        raise ValueError(f"{path}: calendar_years must be contiguous, sorted and unique")
    if waste_active_year != max(calendar_years):
        raise ValueError(f"{path}: waste_active_year must be the latest calendar year")
    if not isinstance(bio_schedule_file, str) or not bio_schedule_file.strip():
        raise ValueError(f"{path}: bio_schedule_file must be a non-empty path")
    bio_schedule_path = ROOT / bio_schedule_file
    if not bio_schedule_path.is_file():
        raise ValueError(f"{path}: bio schedule does not exist: {bio_schedule_file}")
    if bio_schedule_path.stem != str(bio_active_year):
        raise ValueError(
            f"{path}: bio schedule filename must match bio_active_year ({bio_active_year})"
        )
    return ProjectConfig(
        target_year,
        waste_active_year,
        bio_active_year,
        tuple(calendar_years),
        bio_schedule_path,
    )


def validate_rollover(config: ProjectConfig, today: date | None = None) -> None:
    today = today or date.today()
    if config.waste_active_year < today.year:
        raise ValueError(
            f"waste active year {config.waste_active_year} is stale for {today.year}; "
            "publish and audit the new regular schedule before deploying"
        )
    if config.target_year < today.year:
        raise ValueError(
            f"target year {config.target_year} is stale for {today.year}; "
            "advance the public site year before deploying"
        )


project_config = load_project_config()
