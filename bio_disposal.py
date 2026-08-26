from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE_PATH = ROOT / "data" / "bio_disposal_rules.json"
SCHEMA_VERSION = 1

ROOT_FIELDS = {
    "schema_version",
    "last_verified",
    "sources",
    "channels",
    "items",
    "collection_yard",
}
SOURCE_FIELDS = {"id", "title", "published", "url", "file"}
CHANNEL_FIELDS = {
    "id",
    "name",
    "description",
    "accepted_item_ids",
    "rejected_labels",
    "source_ids",
}
ITEM_FIELDS = {"id", "name", "anchor", "summary", "source_ids"}
YARD_SOURCE_FIELDS = {
    "locality",
    "operator",
    "opening_hours",
    "opening_hours_note",
    "eligibility_note",
    "accepted_note",
    "source_ids",
}
YARD_RELEASE_FIELDS = YARD_SOURCE_FIELDS | {"name", "coordinates"}


def load_bio_disposal_source(path: str | Path = DEFAULT_SOURCE_PATH) -> dict:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    validate_bio_disposal_payload(
        raw,
        path,
        require_yard_coordinates=False,
        validate_local_files=True,
    )
    return raw


def validate_bio_disposal_payload(
    raw: dict,
    path: str | Path,
    *,
    require_yard_coordinates: bool,
    validate_local_files: bool,
) -> None:
    path = Path(path)
    _require_object(raw, path, ROOT_FIELDS)
    if raw["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"{path}: unsupported bio disposal schema version")
    try:
        verified = date.fromisoformat(raw["last_verified"])
    except (TypeError, ValueError) as error:
        raise ValueError(f"{path}: last_verified must be an ISO date") from error
    if verified > date.today():
        raise ValueError(f"{path}: last_verified cannot be in the future")

    sources = raw["sources"]
    channels = raw["channels"]
    items = raw["items"]
    if not all(isinstance(value, list) and value for value in (sources, channels, items)):
        raise ValueError(f"{path}: sources, channels and items must be non-empty lists")

    source_ids = _validate_sources(sources, path, validate_local_files)
    item_ids = _validate_items(items, source_ids, path)
    _validate_channels(channels, item_ids, source_ids, path)
    _validate_yard(
        raw["collection_yard"],
        source_ids,
        path,
        require_yard_coordinates,
    )

    channel_by_id = {channel["id"]: channel for channel in channels}
    required_channels = {"brown_bin", "large_container", "collection_yard"}
    if set(channel_by_id) != required_channels:
        raise ValueError(f"{path}: expected disposal channels {sorted(required_channels)}")
    if "branches" in channel_by_id["large_container"]["accepted_item_ids"]:
        raise ValueError(f"{path}: branches cannot be accepted by the large container")


def _validate_sources(sources: list, path: Path, validate_local_files: bool) -> set[str]:
    identifiers: set[str] = set()
    for index, source in enumerate(sources):
        label = f"{path}: source {index}"
        _require_object(source, label, SOURCE_FIELDS)
        _require_non_empty_strings(source, label, {"id", "title", "published", "url"})
        if source["id"] in identifiers:
            raise ValueError(f"{path}: duplicate source id {source['id']}")
        identifiers.add(source["id"])
        parsed = urlparse(source["url"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"{label}: source URL must use https")
        local_file = source["file"]
        if local_file is not None:
            if not isinstance(local_file, str) or not local_file.startswith("/resources/"):
                raise ValueError(f"{label}: local source must be under /resources/")
            if validate_local_files and not (ROOT / local_file.lstrip("/")).is_file():
                raise ValueError(f"{label}: missing local source file {local_file}")
    return identifiers


def _validate_items(items: list, source_ids: set[str], path: Path) -> set[str]:
    identifiers: set[str] = set()
    anchors: set[str] = set()
    for index, item in enumerate(items):
        label = f"{path}: item {index}"
        _require_object(item, label, ITEM_FIELDS)
        _require_non_empty_strings(item, label, {"id", "name", "anchor", "summary"})
        if item["id"] in identifiers or item["anchor"] in anchors:
            raise ValueError(f"{label}: duplicate item id or anchor")
        identifiers.add(item["id"])
        anchors.add(item["anchor"])
        _validate_references(item["source_ids"], source_ids, f"{label}.source_ids")
    return identifiers


def _validate_channels(
    channels: list,
    item_ids: set[str],
    source_ids: set[str],
    path: Path,
) -> None:
    identifiers: set[str] = set()
    for index, channel in enumerate(channels):
        label = f"{path}: channel {index}"
        _require_object(channel, label, CHANNEL_FIELDS)
        _require_non_empty_strings(channel, label, {"id", "name", "description"})
        if channel["id"] in identifiers:
            raise ValueError(f"{label}: duplicate channel id")
        identifiers.add(channel["id"])
        _validate_references(
            channel["accepted_item_ids"], item_ids, f"{label}.accepted_item_ids"
        )
        _validate_string_list(channel["rejected_labels"], f"{label}.rejected_labels")
        _validate_references(channel["source_ids"], source_ids, f"{label}.source_ids")


def _validate_yard(
    yard: dict,
    source_ids: set[str],
    path: Path,
    require_coordinates: bool,
) -> None:
    fields = YARD_RELEASE_FIELDS if require_coordinates else YARD_SOURCE_FIELDS
    _require_object(yard, f"{path}: collection_yard", fields)
    _require_non_empty_strings(
        yard,
        f"{path}: collection_yard",
        {
            "locality",
            "operator",
            "opening_hours_note",
            "eligibility_note",
            "accepted_note",
        },
    )
    if yard["opening_hours"] is not None:
        raise ValueError(f"{path}: opening hours require a current authoritative source")
    _validate_references(yard["source_ids"], source_ids, f"{path}: collection_yard.source_ids")
    if require_coordinates:
        if not isinstance(yard["name"], str) or not yard["name"].strip():
            raise ValueError(f"{path}: collection_yard.name must be a non-empty string")
        coordinates = yard["coordinates"]
        _require_object(
            coordinates,
            f"{path}: collection_yard.coordinates",
            {"latitude", "longitude", "accuracy"},
        )
        if coordinates["accuracy"] != "precise":
            raise ValueError(f"{path}: collection yard coordinates must be precise")
        if not isinstance(coordinates["latitude"], (int, float)) or not isinstance(
            coordinates["longitude"], (int, float)
        ):
            raise ValueError(f"{path}: invalid collection yard coordinates")


def _require_object(value, label, fields: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label}: expected exactly {sorted(fields)}")


def _require_non_empty_strings(value: dict, label, fields: set[str]) -> None:
    for field in fields:
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"{label}: {field} must be a non-empty string")


def _validate_references(values, allowed: set[str], label) -> None:
    _validate_string_list(values, label)
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"{label}: unknown references {sorted(unknown)}")


def _validate_string_list(values, label) -> None:
    if not isinstance(values, list) or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise ValueError(f"{label}: expected a list of non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"{label}: duplicate values")
