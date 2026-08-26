from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path

from bio_disposal import validate_bio_disposal_payload

# TODO: Move these shared value types into a source-neutral domain-model module.
# Release-data loading should not need to import modules that also load source
# rules, exceptions, or the active annual bio configuration.
from bio_containers import (
    BioCoordinates,
    BioPlacement,
    BioSchedule,
    BioSite,
    BioSource,
)
from lokace_svozu import CollectionEvent, WasteType
from proximity import BioCollectionYard, ProximityConfig, resolve_site_coordinates
from utils import slugify


BIO_SCHEMA_VERSION = 1


class ReleasedWasteSchedule:
    def __init__(self, event_cache: dict[str, list[CollectionEvent]]):
        self._event_cache = event_cache

    def get_events_for_street(self, street: str) -> list[CollectionEvent]:
        return self._event_cache[street]


@dataclass(frozen=True)
class ReleasedBioData:
    schedule: BioSchedule
    proximity: ProximityConfig


@dataclass(frozen=True)
class ReleasedBioDisposal:
    last_verified: date
    sources: tuple[dict, ...]
    channels: tuple[dict, ...]
    items: tuple[dict, ...]
    collection_yard: dict

    def channel(self, channel_id: str) -> dict:
        return next(channel for channel in self.channels if channel["id"] == channel_id)


def load_waste_schedule(path: str | Path, streets: list[str]) -> ReleasedWasteSchedule:
    event_cache = {street: [] for street in streets}
    street_order = {street: index for index, street in enumerate(streets)}
    waste_types = {waste_type.key: waste_type for waste_type in WasteType}
    previous_key = None
    seen = set()

    with Path(path).open(newline="", encoding="utf-8") as handle:
        for line_number, row in enumerate(csv.reader(handle), 1):
            if len(row) != 4:
                raise ValueError(f"{path}:{line_number}: expected four CSV columns")
            date_raw, waste_key, street, override_raw = row
            if street not in event_cache:
                raise ValueError(f"{path}:{line_number}: unknown location {street!r}")
            if waste_key not in waste_types:
                raise ValueError(f"{path}:{line_number}: unknown waste type {waste_key!r}")
            if override_raw not in {"0", "1"}:
                raise ValueError(f"{path}:{line_number}: override must be 0 or 1")
            try:
                event_date = datetime.fromisoformat(date_raw)
            except ValueError as error:
                raise ValueError(f"{path}:{line_number}: invalid date {date_raw!r}") from error
            if date_raw != event_date.date().isoformat():
                raise ValueError(f"{path}:{line_number}: date must use YYYY-MM-DD")
            event = CollectionEvent(event_date, waste_types[waste_key], override_raw == "1")
            identity = (street, event_date, waste_key)
            if identity in seen:
                raise ValueError(f"{path}:{line_number}: duplicate event {identity}")
            seen.add(identity)
            order_key = (street_order[street], event_date, event.waste_type.name)
            if previous_key is not None and order_key < previous_key:
                raise ValueError(f"{path}:{line_number}: events are not deterministically ordered")
            previous_key = order_key
            event_cache[street].append(event)

    return ReleasedWasteSchedule(event_cache)


def write_bio_release(
    schedule: BioSchedule,
    proximity: ProximityConfig,
    streets: list[str],
    output_path: str | Path,
) -> None:
    if proximity.collection_yard is None:
        raise ValueError("bio release requires a collection yard")

    payload = {
        "schema_version": BIO_SCHEMA_VERSION,
        "year": schedule.year,
        "sources": [
            {"id": item.id, "title": item.title, "file": item.file}
            for item in schedule.sources
        ],
        "sites": [
            _serialize_site(site, proximity)
            for site in schedule.sites
        ],
        "placements": [
            {
                "id": item.id,
                "site_id": item.site.id,
                "date_from": item.date_from.isoformat(),
                "date_through": item.date_through.isoformat(),
                "source_id": item.source.id,
            }
            for item in schedule.placements
        ],
        "reference_locations": [
            {
                "name": street,
                "slug": slugify(street),
                "coordinates": _serialize_coordinates(proximity.street_coordinates[street]),
            }
            for street in streets
            if street in proximity.street_coordinates
        ],
        "collection_yard": {
            "name": proximity.collection_yard.name,
            "coordinates": _serialize_coordinates(proximity.collection_yard.coordinates),
        },
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_bio_disposal_release(
    source: dict,
    collection_yard: BioCollectionYard,
    output_path: str | Path,
) -> None:
    yard = {
        **source["collection_yard"],
        "name": collection_yard.name,
        "coordinates": _serialize_coordinates(collection_yard.coordinates),
    }
    payload = {
        "schema_version": source["schema_version"],
        "last_verified": source["last_verified"],
        "sources": source["sources"],
        "channels": source["channels"],
        "items": source["items"],
        "collection_yard": yard,
    }
    validate_bio_disposal_payload(
        payload,
        output_path,
        require_yard_coordinates=True,
        validate_local_files=False,
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_bio_release(path: str | Path) -> ReleasedBioData:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version", "year", "sources", "sites", "placements",
        "reference_locations", "collection_yard",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError(f"{path}: invalid bio release root fields")
    if raw["schema_version"] != BIO_SCHEMA_VERSION:
        raise ValueError(f"{path}: unsupported bio schema version")

    sources = tuple(
        BioSource(item["id"], item["title"], item["file"])
        for item in raw["sources"]
    )
    source_by_id = {item.id: item for item in sources}
    sites = tuple(_load_release_site(item) for item in raw["sites"])
    site_by_id = {item.id: item for item in sites}
    placements = tuple(
        BioPlacement(
            item["id"],
            site_by_id[item["site_id"]],
            date.fromisoformat(item["date_from"]),
            date.fromisoformat(item["date_through"]),
            source_by_id[item["source_id"]],
        )
        for item in raw["placements"]
    )
    reference_locations = {
        item["name"]: _load_coordinates(item["coordinates"])
        for item in raw["reference_locations"]
    }
    yard_raw = raw["collection_yard"]
    yard = BioCollectionYard(
        yard_raw["name"], _load_coordinates(yard_raw["coordinates"])
    )
    schedule = BioSchedule(raw["year"], sources, sites, placements)
    return ReleasedBioData(schedule, ProximityConfig(reference_locations, {}, yard))


def load_bio_disposal_release(path: str | Path) -> ReleasedBioDisposal:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    validate_bio_disposal_payload(
        raw,
        path,
        require_yard_coordinates=True,
        validate_local_files=False,
    )
    return ReleasedBioDisposal(
        date.fromisoformat(raw["last_verified"]),
        tuple(raw["sources"]),
        tuple(raw["channels"]),
        tuple(raw["items"]),
        raw["collection_yard"],
    )


def _serialize_site(site: BioSite, proximity: ProximityConfig) -> dict:
    coordinates = resolve_site_coordinates(site, proximity)
    return {
        "id": site.id,
        "locality": site.locality,
        "name": site.name,
        "coordinates": _serialize_coordinates(coordinates) if coordinates else None,
        "coordinate_origin": "direct" if site.coordinates else "fallback",
    }


def _serialize_coordinates(coordinates: BioCoordinates) -> dict:
    return {
        "latitude": coordinates.latitude,
        "longitude": coordinates.longitude,
        "accuracy": coordinates.accuracy,
    }


def _load_release_site(raw: dict) -> BioSite:
    coordinates = raw["coordinates"]
    return BioSite(
        raw["id"],
        raw["locality"],
        raw["name"],
        _load_coordinates(coordinates) if coordinates is not None else None,
    )


def _load_coordinates(raw: dict) -> BioCoordinates:
    return BioCoordinates(raw["latitude"], raw["longitude"], raw["accuracy"])
