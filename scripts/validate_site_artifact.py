#!/usr/bin/env python3
from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils import slugify

BASE_DOMAINS = {"svoz.litovle.cz", "www.svoz.litovle.cz"}
SIMPLE_ANALYTICS_SRC = "https://scripts.simpleanalyticscdn.com/sri/v11.js"
SIMPLE_ANALYTICS_INTEGRITY = (
    "sha384-rfv15RJy1bBYZ1Mf4xizO26jorXb2myipCvHXy4rkG0SuEET96S+m0sTzu5vfbSI"
)
REQUIRED_FILES = (
    "index.html",
    "bio/index.html",
    "styles.css",
    "waste_schedule.csv",
    "bio_schedule.json",
    "sitemap.xml",
    "CNAME",
    "docs/synchronizace-notifikace.html",
)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []
        self.scripts: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.scripts.append(dict(attrs))
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.references.append(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the deployable static site artifact.")
    parser.add_argument("site_dir", nargs="?", default="_site")
    args = parser.parse_args()

    site_dir = Path(args.site_dir)
    validate_required_files(site_dir)
    validate_release_data_files(site_dir)
    validate_calendar_urls(site_dir)
    validate_social_images(site_dir)
    validate_no_source_files(site_dir)
    validate_local_links(site_dir)
    validate_browser_scripts(site_dir)
    validate_bio_proximity_sections(site_dir)
    validate_bio_detail_pages(site_dir)
    return 0


def validate_required_files(site_dir: Path) -> None:
    from release_data import load_bio_release

    source_files = tuple(
        source.file.lstrip("/")
        for source in load_bio_release(site_dir / "bio_schedule.json").schedule.sources
    )
    missing = [
        path for path in REQUIRED_FILES + source_files
        if not (site_dir / path).is_file()
    ]
    if missing:
        raise SystemExit(f"Missing required artifact files: {', '.join(missing)}")


def validate_release_data_files(site_dir: Path) -> None:
    for relative_path in ("waste_schedule.csv", "bio_schedule.json"):
        if (ROOT / relative_path).read_bytes() != (site_dir / relative_path).read_bytes():
            raise SystemExit(f"Artifact release data differs from tracked {relative_path}")


def validate_calendar_urls(site_dir: Path) -> None:
    from streets import all_streets, mistni_casti

    calendars_dir = site_dir / "calendars"
    for street in all_streets["Litovel"] + mistni_casti:
        canonical = calendars_dir / f"{slugify(street)}.ics"
        legacy = calendars_dir / f"{street}.ics"
        if not canonical.is_file() or not legacy.is_file():
            raise SystemExit(f"Missing calendar URL pair for {street}")
        if canonical.read_bytes() != legacy.read_bytes():
            raise SystemExit(f"Legacy calendar differs from canonical calendar for {street}")
        tracked = ROOT / "calendars" / canonical.name
        if tracked.read_bytes() != canonical.read_bytes():
            raise SystemExit(f"Artifact calendar differs from tracked {canonical.name}")


def validate_social_images(site_dir: Path) -> None:
    from PIL import Image

    images = sorted((site_dir / "resources/social").glob("*.png"))
    expected = len(list(site_dir.glob("ulice/*/index.html"))) + 2
    if len(images) != expected:
        raise SystemExit(f"Expected {expected} shared/page social images, found {len(images)}")

    for path in images:
        with Image.open(path) as image:
            if image.size != (1200, 630):
                raise SystemExit(f"{path} has invalid size {image.size}, expected 1200x630")


def validate_no_source_files(site_dir: Path) -> None:
    forbidden = [
        path
        for pattern in ("*.py", "*.yml", "*.yaml")
        for path in site_dir.rglob(pattern)
    ]
    if forbidden:
        formatted = ", ".join(str(path) for path in forbidden[:10])
        raise SystemExit(f"Artifact contains source/config files: {formatted}")


def validate_local_links(site_dir: Path) -> None:
    missing: list[str] = []
    for html_file in site_dir.rglob("*.html"):
        parser = LinkParser()
        parser.feed(html_file.read_text(encoding="utf-8"))
        for reference in parser.references:
            target = resolve_local_reference(site_dir, reference)
            if target is not None and not target.exists():
                missing.append(f"{html_file.relative_to(site_dir)} -> {reference}")

    if missing:
        formatted = "\n".join(missing[:20])
        raise SystemExit(f"Missing local links:\n{formatted}")


def validate_browser_scripts(site_dir: Path) -> None:
    violations: list[str] = []
    pages = [
        site_dir / "index.html",
        site_dir / "bio/index.html",
        *sorted(site_dir.glob("bio/stanoviste/*/index.html")),
        *sorted(site_dir.glob("bio/pobliz/*/index.html")),
        *sorted(site_dir.glob("ulice/*/index.html")),
    ]

    for html_file in pages:
        parser = LinkParser()
        parser.feed(html_file.read_text(encoding="utf-8"))
        analytics_scripts = []

        for script in parser.scripts:
            src = script.get("src")
            if not src:
                continue
            if src == SIMPLE_ANALYTICS_SRC:
                analytics_scripts.append(script)
                continue
            if urlparse(src).scheme or src.startswith("//"):
                violations.append(
                    f"{html_file.relative_to(site_dir)} uses unapproved remote script {src}"
                )

        if len(analytics_scripts) != 1:
            violations.append(
                f"{html_file.relative_to(site_dir)} must contain exactly one approved analytics script"
            )
            continue

        analytics = analytics_scripts[0]
        if analytics.get("integrity") != SIMPLE_ANALYTICS_INTEGRITY:
            violations.append(
                f"{html_file.relative_to(site_dir)} has an invalid analytics integrity hash"
            )
        if analytics.get("crossorigin") != "anonymous":
            violations.append(
                f"{html_file.relative_to(site_dir)} must use crossorigin=anonymous for analytics"
            )

    if violations:
        raise SystemExit("Browser script policy violations:\n" + "\n".join(violations[:20]))


def validate_bio_proximity_sections(site_dir: Path) -> None:
    violations = []
    for html_file in sorted(site_dir.glob("ulice/*/index.html")):
        html = html_file.read_text(encoding="utf-8")
        section_count = html.count('id="nearbyBio"')
        card_count = html.count('class="nearby-bio-card"')
        if section_count not in {0, 1}:
            violations.append(f"{html_file.relative_to(site_dir)} has duplicate nearby bio sections")
        if (section_count == 0 and card_count != 0) or (
            section_count == 1 and not 1 <= card_count <= 3
        ):
            violations.append(f"{html_file.relative_to(site_dir)} has inconsistent nearby bio cards")
    if violations:
        raise SystemExit("Bio proximity violations:\n" + "\n".join(violations[:20]))


def validate_bio_detail_pages(site_dir: Path) -> None:
    from release_data import load_bio_release
    from streets import all_streets, mistni_casti

    bio_data = load_bio_release(site_dir / "bio_schedule.json")
    schedule = bio_data.schedule
    streets = all_streets["Litovel"] + mistni_casti
    proximity = bio_data.proximity
    expected_site_routes = {site.id for site in schedule.sites}
    expected_nearby_routes = {
        slugify(street) for street in streets
        if street in proximity.street_coordinates
    }
    site_pages = sorted(site_dir.glob("bio/stanoviste/*/index.html"))
    nearby_pages = sorted(site_dir.glob("bio/pobliz/*/index.html"))
    actual_site_routes = {path.parent.name for path in site_pages}
    actual_nearby_routes = {path.parent.name for path in nearby_pages}
    if actual_site_routes != expected_site_routes:
        raise SystemExit("Generated bio site routes do not match the active schedule")
    if actual_nearby_routes != expected_nearby_routes:
        raise SystemExit("Generated nearby routes do not match grounded street coordinates")
    for path in [*site_pages, *nearby_pages]:
        html = path.read_text(encoding="utf-8")
        if "<link rel=\"canonical\"" not in html or "BreadcrumbList" not in html:
            raise SystemExit(f"Missing SEO metadata in {path.relative_to(site_dir)}")


def resolve_local_reference(site_dir: Path, reference: str) -> Path | None:
    parsed = urlparse(reference)
    if parsed.scheme in {"http", "https"} and parsed.netloc not in BASE_DOMAINS:
        return None
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.path or parsed.path.startswith("#"):
        return None

    path = unquote(parsed.path)
    if not path.startswith("/"):
        return None
    target = site_dir / path.lstrip("/")
    if path.endswith("/"):
        return target / "index.html"
    return target


if __name__ == "__main__":
    raise SystemExit(main())
