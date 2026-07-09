#!/usr/bin/env python3
from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image


BASE_DOMAINS = {"svoz.litovle.cz", "www.svoz.litovle.cz"}
REQUIRED_FILES = (
    "index.html",
    "styles.css",
    "waste_schedule.csv",
    "sitemap.xml",
    "CNAME",
    "docs/synchronizace-notifikace.html",
)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.references.append(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the deployable static site artifact.")
    parser.add_argument("site_dir", nargs="?", default="_site")
    args = parser.parse_args()

    site_dir = Path(args.site_dir)
    validate_required_files(site_dir)
    validate_social_images(site_dir)
    validate_no_source_files(site_dir)
    validate_local_links(site_dir)
    return 0


def validate_required_files(site_dir: Path) -> None:
    missing = [path for path in REQUIRED_FILES if not (site_dir / path).is_file()]
    if missing:
        raise SystemExit(f"Missing required artifact files: {', '.join(missing)}")


def validate_social_images(site_dir: Path) -> None:
    pages = [site_dir / "index.html", *sorted(site_dir.glob("ulice/*/index.html"))]
    images = sorted((site_dir / "resources/social").glob("*.png"))
    if len(images) != len(pages):
        raise SystemExit(f"Expected {len(pages)} social images, found {len(images)}")

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
