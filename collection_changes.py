"""Deterministic public announcements generated from the maintained exceptions."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path

from icalendar import Calendar

from lokace_svozu import WasteType
from project_config import project_config
from svoz_exceptions import SvozException
from utils import slugify


FEED_NAME = "collection_changes.json"
SCHEMA_VERSION = 1
DATE_FIELDS = {"reschedule": ("original_date", "new_date"), "include": ("date",), "cancel": ("date",)}


def content_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def change_record(exception: SvozException) -> dict:
    # Street membership is compared separately by each subscriber. Expanding a
    # location group must not re-alert streets whose dates have not changed.
    semantic = {"action": exception.action, "waste_type": exception.waste_type}
    semantic.update({key: getattr(exception, key).isoformat() for key in DATE_FIELDS[exception.action]})
    source = exception.source
    return {
        "id": exception.id,
        "revision": content_hash(semantic),
        **semantic,
        "street_slugs": sorted({slugify(name) for name in exception.resolved_locations}),
        "message": source.evidence or exception.note,
        "source": {
            "title": source.title,
            "url": source.url,
            "archive_urls": list(source.archive_urls),
        },
    }


def write_collection_changes(
    output_dir: Path, streets: list[str], exceptions: tuple[SvozException, ...],
) -> None:
    """Export the exceptions applied to the same schedule as the canonical ICS."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "calendars": {
            slug: hashlib.sha256((output_dir / "calendars" / f"{slug}.ics").read_bytes()).hexdigest()
            for slug in sorted(slugify(name) for name in streets)
        },
        "changes": [change_record(item) for item in sorted(exceptions, key=lambda item: item.id)],
    }
    payload["revision"] = content_hash(payload)
    _validate_calendar_changes(payload, output_dir / "calendars")
    (output_dir / FEED_NAME).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_collection_changes(path: Path, calendars_dir: Path | None = None) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "revision", "calendars", "changes"}:
        raise ValueError("Invalid collection-change feed fields")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported collection-change feed schema")
    if payload["revision"] != content_hash({key: value for key, value in payload.items() if key != "revision"}):
        raise ValueError("Collection-change feed revision does not match its content")
    calendars = payload["calendars"]
    if not isinstance(calendars, dict) or not calendars:
        raise ValueError("Collection-change feed has no calendars")
    for slug, digest in calendars.items():
        if slugify(slug) != slug or not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid collection-change calendar fingerprint")
        if calendars_dir is not None and hashlib.sha256((calendars_dir / f"{slug}.ics").read_bytes()).hexdigest() != digest:
            raise ValueError(f"Collection-change calendar hash mismatch: {slug}")
    if not isinstance(payload["changes"], list):
        raise ValueError("Collection-change feed changes must be a list")
    ids = set()
    for record in payload["changes"]:
        action = record.get("action") if isinstance(record, dict) else None
        if action not in DATE_FIELDS:
            raise ValueError("Invalid collection-change action")
        required = {"id", "revision", "action", "waste_type", "street_slugs", "message", "source", *DATE_FIELDS[action]}
        if set(record) != required or not isinstance(record["id"], str) or not record["id"] or record["id"] in ids:
            raise ValueError("Invalid or duplicate collection-change record")
        ids.add(record["id"])
        if record["waste_type"] not in {"SMES", "PLAST", "PAPIR", "BIO"}:
            raise ValueError("Invalid collection-change waste type")
        for field in DATE_FIELDS[action]:
            if date.fromisoformat(record[field]).isoformat() != record[field]:
                raise ValueError("Invalid collection-change date")
        semantic = {key: record[key] for key in ("action", "waste_type", *DATE_FIELDS[action])}
        if record["revision"] != content_hash(semantic):
            raise ValueError("Invalid collection-change semantic revision")
        slugs = record["street_slugs"]
        if not isinstance(slugs, list) or not slugs or len(set(slugs)) != len(slugs) or not set(slugs) <= calendars.keys():
            raise ValueError("Collection change references an unknown street")
        source = record["source"]
        if not isinstance(source, dict) or set(source) != {"title", "url", "archive_urls"}:
            raise ValueError("Invalid public collection-change source")
    if calendars_dir is not None:
        _validate_calendar_changes(payload, calendars_dir)
    return payload


def _validate_calendar_changes(payload: dict, calendars_dir: Path) -> None:
    """Verify event meaning as well as byte hashes in the configured release range."""
    indexed = {}
    for record in payload["changes"]:
        checks = (
            ((date.fromisoformat(record["original_date"]), False),
             (date.fromisoformat(record["new_date"]), True))
            if record["action"] == "reschedule"
            else ((date.fromisoformat(record["date"]), record["action"] == "include"),)
        )
        for slug in record["street_slugs"]:
            if slug not in indexed:
                indexed[slug] = _calendar_events(calendars_dir / f"{slug}.ics")
            for day, included in checks:
                if not project_config.date_start.date() <= day < project_config.date_end.date():
                    continue
                matches = indexed[slug].get((day, record["waste_type"]), [])
                if included:
                    valid = len(matches) == 1 and str(
                        matches[0].get("X-SVOZ-EXCEPTION-ID", "")
                    ) == record["id"]
                else:
                    valid = not matches
                if not valid:
                    raise ValueError(
                        f"Collection change {record['id']} contradicts calendar {slug}: "
                        f"{record['waste_type']} {day.isoformat()} "
                        f"must be {'included with its metadata' if included else 'absent'}"
                    )


def _calendar_events(path: Path) -> dict:
    indexed = {}
    calendar = Calendar.from_ical(path.read_bytes())
    for event in calendar.walk("VEVENT"):
        summary = str(event.get("SUMMARY", "")).removeprefix("Změna: ")
        waste = next((item.name for item in WasteType if summary.startswith(f"{item.label} svoz")), None)
        if waste is not None:
            indexed.setdefault((event.decoded("DTSTART"), waste), []).append(event)
    return indexed
