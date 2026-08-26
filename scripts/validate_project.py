#!/usr/bin/env python3
from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    os.chdir(ROOT)
    validate_generated_files_are_not_tracked()
    validate_active_year()
    validate_release_exports()
    run([sys.executable, "tests.py"])
    validate_browser_dependencies()
    validate_exception_json()
    validate_bio_container_json()
    validate_bio_disposal_json()
    compile_python_files()
    return 0


def validate_generated_files_are_not_tracked() -> None:
    result = subprocess.run(
        [
            "git", "ls-files", "-z", "--",
            "index.html", "sitemap.xml", "ulice", "bio",
            "kam-se-zahradnim-odpadem-litovel", "sberny-dvur-litovel",
        ],
        check=True,
        capture_output=True,
    )
    tracked = [path for path in result.stdout.decode().split("\0") if path]
    if tracked:
        preview = ", ".join(tracked[:10])
        raise SystemExit(f"Generated site pages must not be tracked: {preview}")


def validate_active_year() -> None:
    from bio_containers import load_bio_schedule
    from lokace_svozu import validate_regular_schedule_years
    from project_config import project_config, validate_rollover

    validate_rollover(project_config)
    validate_regular_schedule_years(project_config.calendar_years)
    schedule = load_bio_schedule()
    if schedule.year != project_config.bio_active_year:
        raise ValueError(
            f"bio active year {project_config.bio_active_year} does not match "
            f"bio schedule year {schedule.year}"
        )


def validate_release_exports() -> None:
    from scripts.build_site import validate_release_data

    validate_release_data()


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def validate_browser_dependencies() -> None:
    node = shutil.which("node")
    if node is None:
        raise SystemExit("Node.js is required to validate vendored browser dependencies")
    run([node, "scripts/validate_browser_dependencies.cjs"])
    run([node, "scripts/validate_frontend_logic.cjs"])


def validate_exception_json() -> None:
    from lokace_svozu import WasteType
    from svoz_exceptions import load_svoz_exceptions

    load_svoz_exceptions(
        allowed_waste_types={waste_type.name for waste_type in WasteType}
    )
    from scripts.watch_litovel_eu import load_known_urls
    load_known_urls()


def validate_bio_container_json() -> None:
    from bio_containers import load_bio_schedule
    from proximity import load_proximity_config
    from streets import all_streets, mistni_casti

    schedule = load_bio_schedule()
    streets = all_streets["Litovel"] + mistni_casti
    load_proximity_config(streets, schedule.sites)


def validate_bio_disposal_json() -> None:
    from bio_disposal import load_bio_disposal_source

    load_bio_disposal_source()


def compile_python_files() -> None:
    python_files = sorted(Path(".").glob("*.py")) + sorted(Path("scripts").glob("*.py"))
    for path in python_files:
        py_compile.compile(str(path), doraise=True)


if __name__ == "__main__":
    raise SystemExit(main())
