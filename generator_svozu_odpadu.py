from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

import calendar_generator
from bio_containers import load_bio_schedule
from bio_disposal import load_bio_disposal_source
from lokace_svozu import (
    lokace_svozu_bio,
    lokace_svozu_papir,
    lokace_svozu_plast,
    lokace_svozu_smes,
    validate_regular_schedule_years,
)
from proximity import load_proximity_config
from project_config import project_config, validate_rollover
from release_data import write_bio_disposal_release, write_bio_release
from streets import all_streets, mistni_casti


date_start = project_config.date_start
date_end = project_config.date_end


def create_regular_schedule() -> tuple[calendar_generator.WasteCollectionCalendarGenerator, list[str]]:
    validate_rollover(project_config)
    validate_regular_schedule_years(project_config.calendar_years)
    streets = all_streets["Litovel"] + mistni_casti
    generator = calendar_generator.WasteCollectionCalendarGenerator(
        lokace_svozu_smes,
        lokace_svozu_plast,
        lokace_svozu_papir,
        lokace_svozu_bio,
        streets,
        date_start,
        date_end,
    )
    return generator, streets


def generate_release_data(output_dir: str | Path = ".") -> None:
    output_dir = Path(output_dir)
    generator, streets = create_regular_schedule()
    bio_schedule = load_bio_schedule()
    bio_disposal = load_bio_disposal_source()
    if bio_schedule.year != project_config.bio_active_year:
        raise ValueError(
            f"bio active year {project_config.bio_active_year} does not match "
            f"bio schedule year {bio_schedule.year}"
        )
    proximity_config = load_proximity_config(streets, bio_schedule.sites)

    generator.generate_csv_file(
        streets, date_start, date_end, output_dir / "waste_schedule.csv"
    )
    calendars_dir = output_dir / "calendars"
    if calendars_dir.exists():
        shutil.rmtree(calendars_dir)
    for street in streets:
        generator.generate_ical_file(
            street,
            calendars_dir,
            date_start,
            date_end,
            include_legacy_alias=False,
        )
    write_bio_release(
        bio_schedule,
        proximity_config,
        streets,
        output_dir / "bio_schedule.json",
    )
    if proximity_config.collection_yard is None:
        raise ValueError("bio disposal release requires a collection yard")
    write_bio_disposal_release(
        bio_disposal,
        proximity_config.collection_yard,
        output_dir / "bio_disposal.json",
    )


def refresh_release_data(output_dir: str | Path = ".") -> None:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        generated = Path(temp_dir)
        generate_release_data(generated)
        for filename in (
            "waste_schedule.csv",
            "bio_schedule.json",
            "bio_disposal.json",
        ):
            _replace_file(generated / filename, output_dir / filename)

        destination_calendars = output_dir / "calendars"
        destination_calendars.mkdir(parents=True, exist_ok=True)
        expected_names = {path.name for path in (generated / "calendars").glob("*.ics")}
        for obsolete in destination_calendars.glob("*.ics"):
            if obsolete.name not in expected_names:
                obsolete.unlink()
        for source in sorted((generated / "calendars").glob("*.ics")):
            _replace_file(source, destination_calendars / source.name)


def _replace_file(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.tmp")
    shutil.copy2(source, temporary)
    temporary.replace(destination)


def build(output_dir: str | Path = ".") -> None:
    """Compatibility entry point for regenerating tracked release data."""
    refresh_release_data(output_dir)


def main() -> None:
    refresh_release_data()


if __name__ == "__main__":
    main()
