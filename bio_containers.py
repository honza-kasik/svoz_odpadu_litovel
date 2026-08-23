from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
from pathlib import Path

from project_config import project_config


DEFAULT_DATA_PATH = project_config.bio_schedule_path


@dataclass(frozen=True)
class BioSource:
    id: str
    title: str
    file: str


@dataclass(frozen=True)
class BioCoordinates:
    latitude: float
    longitude: float
    accuracy: str = "precise"


@dataclass(frozen=True)
class BioSite:
    id: str
    locality: str
    name: str
    coordinates: BioCoordinates | None

    @property
    def display_name(self) -> str:
        if self.locality == "Litovel" or self.name == self.locality:
            return self.name
        return f"{self.locality} – {self.name}"


@dataclass(frozen=True)
class BioPlacement:
    id: str
    site: BioSite
    date_from: date
    date_through: date
    source: BioSource

    def intersects_month(self, year: int, month: int) -> bool:
        month_from = date(year, month, 1)
        if month == 12:
            month_through = date(year, 12, 31)
        else:
            month_through = date(year, month + 1, 1) - timedelta(days=1)
        return self.date_from <= month_through and self.date_through >= month_from


@dataclass(frozen=True)
class BioSchedule:
    year: int
    sources: tuple[BioSource, ...]
    sites: tuple[BioSite, ...]
    placements: tuple[BioPlacement, ...]


ROOT_FIELDS = {"year", "sources", "sites", "placement_windows"}
SOURCE_FIELDS = {"id", "title", "file"}
SITE_FIELDS = {"id", "locality", "name", "coordinates"}
COORDINATE_FIELDS = {"latitude", "longitude", "accuracy"}
WINDOW_FIELDS = {"id", "date_from", "date_through", "source_id", "site_ids"}


def load_bio_schedule(path: str | Path = DEFAULT_DATA_PATH) -> BioSchedule:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    _require_object(data, "root")
    _reject_unknown_fields(data, ROOT_FIELDS, "root")

    year = data.get("year")
    if not isinstance(year, int):
        raise ValueError("root.year must be an integer")

    sources = _load_sources(data.get("sources"))
    _validate_source_files(sources, path)
    sites = _load_sites(data.get("sites"))
    source_by_id = {source.id: source for source in sources}
    site_by_id = {site.id: site for site in sites}
    placements = _load_placements(
        data.get("placement_windows"), year, source_by_id, site_by_id
    )
    _validate_no_site_overlaps(placements)

    return BioSchedule(year, tuple(sources), tuple(sites), tuple(placements))


def _load_sources(raw_sources) -> list[BioSource]:
    _require_list(raw_sources, "root.sources")
    sources = []
    seen = set()
    for index, raw in enumerate(raw_sources):
        label = f"root.sources[{index}]"
        _require_object(raw, label)
        _reject_unknown_fields(raw, SOURCE_FIELDS, label)
        source_id = _required_string(raw, "id", label)
        if source_id in seen:
            raise ValueError(f"duplicate source id: {source_id}")
        seen.add(source_id)
        sources.append(
            BioSource(
                source_id,
                _required_string(raw, "title", label),
                _required_string(raw, "file", label),
            )
        )
    return sources


def _validate_source_files(sources: list[BioSource], data_path: Path) -> None:
    for source in sources:
        relative_path = source.file.lstrip("/")
        local_path = next(
            (
                parent / relative_path
                for parent in data_path.resolve().parents
                if (parent / relative_path).is_file()
            ),
            None,
        )
        if local_path is None:
            raise ValueError(f"source file does not exist: {source.file}")


def _load_sites(raw_sites) -> list[BioSite]:
    _require_list(raw_sites, "root.sites")
    sites = []
    seen = set()
    for index, raw in enumerate(raw_sites):
        label = f"root.sites[{index}]"
        _require_object(raw, label)
        _reject_unknown_fields(raw, SITE_FIELDS, label)
        site_id = _required_string(raw, "id", label)
        if site_id in seen:
            raise ValueError(f"duplicate site id: {site_id}")
        seen.add(site_id)
        coordinates = _load_coordinates(raw.get("coordinates"), label)
        sites.append(
            BioSite(
                site_id,
                _required_string(raw, "locality", label),
                _required_string(raw, "name", label),
                coordinates,
            )
        )
    return sites


def _load_coordinates(raw, label: str) -> BioCoordinates | None:
    if raw is None:
        return None
    _require_object(raw, f"{label}.coordinates")
    _reject_unknown_fields(raw, COORDINATE_FIELDS, f"{label}.coordinates")
    if set(raw) != COORDINATE_FIELDS:
        raise ValueError(
            f"{label}.coordinates requires latitude, longitude and accuracy"
        )
    latitude = raw["latitude"]
    longitude = raw["longitude"]
    if not isinstance(latitude, (int, float)) or isinstance(latitude, bool):
        raise ValueError(f"{label}.coordinates.latitude must be a number")
    if not isinstance(longitude, (int, float)) or isinstance(longitude, bool):
        raise ValueError(f"{label}.coordinates.longitude must be a number")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError(f"{label}.coordinates are outside valid ranges")
    accuracy = raw["accuracy"]
    if accuracy not in {"provisional", "precise"}:
        raise ValueError(f"{label}.coordinates.accuracy must be provisional or precise")
    return BioCoordinates(float(latitude), float(longitude), accuracy)


def _load_placements(raw_windows, year, source_by_id, site_by_id):
    _require_list(raw_windows, "root.placement_windows")
    placements = []
    seen_windows = set()
    seen_placements = set()
    for index, raw in enumerate(raw_windows):
        label = f"root.placement_windows[{index}]"
        _require_object(raw, label)
        _reject_unknown_fields(raw, WINDOW_FIELDS, label)
        window_id = _required_string(raw, "id", label)
        if window_id in seen_windows:
            raise ValueError(f"duplicate placement window id: {window_id}")
        seen_windows.add(window_id)
        date_from = _parse_date(raw.get("date_from"), f"{label}.date_from")
        date_through = _parse_date(raw.get("date_through"), f"{label}.date_through")
        if date_through < date_from:
            raise ValueError(f"{label}.date_through must not precede date_from")
        if date_from.year != year or date_through.year != year:
            raise ValueError(f"{label} must stay inside schedule year {year}")
        source_id = _required_string(raw, "source_id", label)
        if source_id not in source_by_id:
            raise ValueError(f"{label} references unknown source {source_id}")
        site_ids = raw.get("site_ids")
        _require_list(site_ids, f"{label}.site_ids")
        if not site_ids:
            raise ValueError(f"{label}.site_ids must not be empty")
        if len(site_ids) != len(set(site_ids)):
            raise ValueError(f"{label}.site_ids contains duplicates")
        for site_id in site_ids:
            if not isinstance(site_id, str) or not site_id.strip():
                raise ValueError(f"{label}.site_ids must contain non-empty strings")
            if site_id not in site_by_id:
                raise ValueError(f"{label} references unknown site {site_id}")
            placement_id = f"{window_id}--{site_id}"
            if placement_id in seen_placements:
                raise ValueError(f"duplicate placement id: {placement_id}")
            seen_placements.add(placement_id)
            placements.append(
                BioPlacement(
                    placement_id,
                    site_by_id[site_id],
                    date_from,
                    date_through,
                    source_by_id[source_id],
                )
            )
    return sorted(placements, key=lambda item: (item.date_from, item.site.display_name))


def _validate_no_site_overlaps(placements: list[BioPlacement]) -> None:
    by_site: dict[str, list[BioPlacement]] = {}
    for placement in placements:
        by_site.setdefault(placement.site.id, []).append(placement)
    for site_id, site_placements in by_site.items():
        ordered = sorted(site_placements, key=lambda item: item.date_from)
        for previous, current in zip(ordered, ordered[1:]):
            if current.date_from <= previous.date_through:
                raise ValueError(
                    f"overlapping placements for site {site_id}: "
                    f"{previous.id} and {current.id}"
                )


def _parse_date(raw, label: str) -> date:
    if not isinstance(raw, str):
        raise ValueError(f"{label} must be a valid ISO date")
    try:
        return date.fromisoformat(raw)
    except ValueError as error:
        raise ValueError(f"{label} must be a valid ISO date") from error


def _required_string(raw: dict, field: str, label: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{field} must be a non-empty string")
    return value.strip()


def _require_object(value, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")


def _require_list(value, label: str) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")


def _reject_unknown_fields(raw: dict, allowed: set[str], label: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"{label} contains unknown fields: {', '.join(sorted(unknown))}")
