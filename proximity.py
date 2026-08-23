from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

from bio_containers import BioCoordinates, BioPlacement, BioSchedule, BioSite


DEFAULT_DATA_PATH = Path("data/proximity_coordinates.json")
ROOT_FIELDS = {
    "version",
    "source",
    "street_coordinates",
    "site_coordinates",
}
SOURCE_FIELDS = {"name", "url", "license", "imported"}
POINT_FIELDS = {"latitude", "longitude", "accuracy"}


@dataclass(frozen=True)
class ProximityConfig:
    street_coordinates: dict[str, BioCoordinates]
    site_coordinates: dict[str, BioCoordinates]


@dataclass(frozen=True)
class NearbyBioPlacement:
    placement: BioPlacement
    site_coordinates: BioCoordinates
    distance_km: float
    status: str
    approximate: bool


def load_proximity_config(
    streets: list[str],
    sites: tuple[BioSite, ...],
    path: str | Path = DEFAULT_DATA_PATH,
) -> ProximityConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("proximity root must be an object")
    unknown = set(data) - ROOT_FIELDS
    if unknown:
        raise ValueError(f"proximity root contains unknown fields: {', '.join(sorted(unknown))}")
    if data.get("version") != 1:
        raise ValueError("proximity version must be 1")

    source = data.get("source")
    if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
        raise ValueError("proximity source metadata is incomplete")
    if any(not isinstance(value, str) or not value.strip() for value in source.values()):
        raise ValueError("proximity source metadata must contain non-empty strings")

    street_coordinates = _load_overrides(
        data.get("street_coordinates"), "street_coordinates"
    )
    site_coordinates = _load_overrides(
        data.get("site_coordinates"), "site_coordinates"
    )
    unknown_streets = set(street_coordinates) - set(streets)
    unknown_sites = set(site_coordinates) - {site.id for site in sites}
    if unknown_streets:
        raise ValueError(f"unknown street coordinate overrides: {', '.join(sorted(unknown_streets))}")
    if unknown_sites:
        raise ValueError(f"unknown site coordinate overrides: {', '.join(sorted(unknown_sites))}")

    return ProximityConfig(street_coordinates, site_coordinates)


def resolve_street_coordinates(
    street: str, config: ProximityConfig
) -> BioCoordinates | None:
    return config.street_coordinates.get(street)


def resolve_site_coordinates(
    site: BioSite, config: ProximityConfig
) -> BioCoordinates | None:
    return site.coordinates or config.site_coordinates.get(site.id)


def find_nearby_bio_placements(
    street: str,
    schedule: BioSchedule,
    config: ProximityConfig,
    reference_date: date,
    limit: int = 3,
) -> list[NearbyBioPlacement]:
    if limit <= 0:
        return []
    street_point = resolve_street_coordinates(street, config)
    if street_point is None:
        return []
    active = [
        placement
        for placement in schedule.placements
        if placement.date_from <= reference_date <= placement.date_through
    ]
    chosen = _nearest_distinct(active, street_point, config, "current", limit)
    chosen_site_ids = {item.placement.site.id for item in chosen}

    if len(chosen) < limit:
        future = [
            placement
            for placement in schedule.placements
            if placement.date_from > reference_date
            and placement.site.id not in chosen_site_ids
        ]
        while future and len(chosen) < limit:
            next_date = min(item.date_from for item in future)
            next_window = [item for item in future if item.date_from == next_date]
            additions = _nearest_distinct(
                next_window,
                street_point,
                config,
                "upcoming",
                limit - len(chosen),
            )
            chosen.extend(additions)
            chosen_site_ids.update(item.placement.site.id for item in additions)
            future = [
                item
                for item in future
                if item.date_from > next_date and item.site.id not in chosen_site_ids
            ]
    if not chosen:
        latest_by_site = {}
        for placement in schedule.placements:
            previous = latest_by_site.get(placement.site.id)
            if previous is None or placement.date_through > previous.date_through:
                latest_by_site[placement.site.id] = placement
        chosen = _nearest_distinct(
            latest_by_site.values(),
            street_point,
            config,
            "schedule-unavailable",
            limit,
        )
    return chosen


def haversine_distance_km(first: BioCoordinates, second: BioCoordinates) -> float:
    earth_radius_km = 6371.0088
    lat1, lon1, lat2, lon2 = map(
        radians,
        (first.latitude, first.longitude, second.latitude, second.longitude),
    )
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )
    return earth_radius_km * 2 * asin(sqrt(value))


def _nearest_distinct(placements, street_point, config, status, limit):
    candidates = []
    seen_sites = set()
    for placement in placements:
        if placement.site.id in seen_sites:
            continue
        seen_sites.add(placement.site.id)
        site_point = resolve_site_coordinates(placement.site, config)
        if site_point is None:
            continue
        candidates.append(
            NearbyBioPlacement(
                placement,
                site_point,
                haversine_distance_km(street_point, site_point),
                status,
                street_point.accuracy != "precise" or site_point.accuracy != "precise",
            )
        )
    return sorted(candidates, key=lambda item: item.distance_km)[:limit]


def _load_overrides(raw, label: str) -> dict[str, BioCoordinates]:
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be an object")
    return {key: _load_point(value, f"{label}.{key}") for key, value in raw.items()}


def _load_point(raw, label: str, default_accuracy: str | None = None) -> BioCoordinates:
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be an object")
    allowed = {"latitude", "longitude"} if default_accuracy else POINT_FIELDS
    unknown = set(raw) - allowed
    if unknown or set(raw) != allowed:
        raise ValueError(f"{label} must contain exactly {', '.join(sorted(allowed))}")
    latitude = raw["latitude"]
    longitude = raw["longitude"]
    if not isinstance(latitude, (int, float)) or isinstance(latitude, bool):
        raise ValueError(f"{label}.latitude must be a number")
    if not isinstance(longitude, (int, float)) or isinstance(longitude, bool):
        raise ValueError(f"{label}.longitude must be a number")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError(f"{label} is outside valid coordinate ranges")
    accuracy = default_accuracy or raw["accuracy"]
    if accuracy not in {"provisional", "precise"}:
        raise ValueError(f"{label}.accuracy must be provisional or precise")
    return BioCoordinates(float(latitude), float(longitude), accuracy)
