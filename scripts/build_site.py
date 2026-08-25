#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generator_svozu_odpadu import generate_release_data
from release_data import load_bio_release, load_waste_schedule
from site_builder import build_bio_pages, build_index, build_street_pages, generate_sitemap
from social_preview import build_social_images
from streets import all_streets, mistni_casti
from utils import slugify


STATIC_ENTRIES = (
    "CNAME",
    "styles.css",
    "favicon.png",
    "js",
    "resources",
    "docs",
    "waste_schedule.csv",
    "bio_schedule.json",
    "calendars",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the deployable static site artifact.")
    parser.add_argument(
        "--output-dir",
        default="_site",
        help="Directory where the deployable site will be created.",
    )
    args = parser.parse_args()

    os.chdir(ROOT)

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    if output_dir.resolve() == ROOT:
        raise SystemExit("Refusing to use the repository root as the artifact output directory.")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for entry in STATIC_ENTRIES:
        copy_static_entry(ROOT / entry, output_dir / entry)

    validate_release_data()
    build_presentation(output_dir)
    create_legacy_calendar_aliases(output_dir)
    return 0


def validate_release_data() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        generated = Path(temp_dir)
        generate_release_data(generated)
        differences = compare_release_data(ROOT, generated)
    if differences:
        preview = "\n".join(f"- {item}" for item in differences[:20])
        raise SystemExit(
            "Tracked schedule exports are stale:\n"
            f"{preview}\n"
            "Run: python scripts/generate_schedule_exports.py"
        )


def compare_release_data(expected: Path, actual: Path) -> list[str]:
    expected_files = {
        Path("waste_schedule.csv"),
        Path("bio_schedule.json"),
        *(path.relative_to(expected) for path in (expected / "calendars").glob("*.ics")),
    }
    actual_files = {
        Path("waste_schedule.csv"),
        Path("bio_schedule.json"),
        *(path.relative_to(actual) for path in (actual / "calendars").glob("*.ics")),
    }
    differences = [
        f"obsolete tracked file: {path}"
        for path in sorted(expected_files - actual_files)
    ]
    differences.extend(
        f"missing tracked file: {path}"
        for path in sorted(actual_files - expected_files)
    )
    for relative_path in sorted(expected_files & actual_files):
        if (expected / relative_path).read_bytes() != (actual / relative_path).read_bytes():
            differences.append(f"content differs: {relative_path}")
    return differences


def build_presentation(output_dir: Path) -> None:
    streets = all_streets["Litovel"] + mistni_casti
    regular_schedule = load_waste_schedule(ROOT / "waste_schedule.csv", streets)
    bio_data = load_bio_release(ROOT / "bio_schedule.json")
    social_images = build_social_images(
        regular_schedule,
        streets,
        bio_schedule=bio_data.schedule,
        card_dir=output_dir / "resources/social",
    )
    build_index(streets, social_images, output_dir=output_dir)
    build_street_pages(
        regular_schedule,
        streets,
        social_images,
        bio_data.schedule,
        bio_data.proximity,
        output_dir=output_dir,
    )
    build_bio_pages(
        bio_data.schedule,
        streets,
        bio_data.proximity,
        social_images["bio"],
        output_dir=output_dir,
    )
    generate_sitemap(
        streets,
        output_dir / "sitemap.xml",
        bio_schedule=bio_data.schedule,
        proximity_config=bio_data.proximity,
    )


def create_legacy_calendar_aliases(output_dir: Path) -> None:
    streets = all_streets["Litovel"] + mistni_casti
    calendars_dir = output_dir / "calendars"
    for street in streets:
        canonical = calendars_dir / f"{slugify(street)}.ics"
        legacy = calendars_dir / f"{street}.ics"
        if legacy != canonical and not (
            legacy.exists() and legacy.samefile(canonical)
        ):
            shutil.copy2(canonical, legacy)


def copy_static_entry(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, ignore=ignore_generated_social)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def ignore_generated_social(directory: str, names: list[str]) -> set[str]:
    if Path(directory).resolve() == (ROOT / "resources").resolve():
        return {"social"} & set(names)
    return set()


if __name__ == "__main__":
    raise SystemExit(main())
