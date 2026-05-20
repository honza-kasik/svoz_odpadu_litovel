"""Načítání jednorázových změn svozu z datového souboru.

Pravidelný harmonogram zůstává v ``lokace_svozu.py``. Tento modul řeší pouze
výjimky oznámené městem, aby budoucí změny mohly být malé datové diffy.
"""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from streets import (
    all_streets,
    litovel_lokace_plast_1,
    litovel_lokace_smes_1,
    litovel_lokace_smes_3,
    litovel_lokace_smes_4,
)


EXCEPTION_DATA_PATH = Path(__file__).resolve().parent / "data" / "svoz_exceptions.json"
ALLOWED_ACTIONS = {"reschedule", "include", "cancel"}
ALLOWED_WASTE_TYPES = {"SMES", "PLAST", "PAPIR", "BIO"}
ALLOWED_FIELDS = {
    "id",
    "action",
    "waste_type",
    "affected_location_group",
    "affected_locations",
    "affected_locations_snapshot",
    "original_date",
    "new_date",
    "date",
    "source",
    "note",
}
ALLOWED_SOURCE_FIELDS = {"url", "title", "evidence"}
ACTION_DATE_FIELDS = {
    "reschedule": {"required": {"original_date", "new_date"}, "forbidden": {"date"}},
    "include": {"required": {"date"}, "forbidden": {"original_date", "new_date"}},
    "cancel": {"required": {"date"}, "forbidden": {"original_date", "new_date"}},
}
LOCATION_GROUPS = {
    "all_streets_litovel": tuple(all_streets["Litovel"]),
    "litovel_lokace_plast_1": tuple(litovel_lokace_plast_1),
    "litovel_lokace_smes_1": tuple(litovel_lokace_smes_1),
    "litovel_lokace_smes_3": tuple(litovel_lokace_smes_3),
    "litovel_lokace_smes_4": tuple(litovel_lokace_smes_4),
    "smes_streda_mistni_casti": ("Savín", "Nová Ves", "Chudobín", "Tři Dvory"),
    "plast_pondeli_mistni_casti": (
        "Březové",
        "Chořelice",
        "Nasobůrky",
        "Víska",
        "Rozvadovice",
        "Unčovice",
    ),
    "papir_pondeli_mistni_casti": (
        "Březové",
        "Chořelice",
        "Nasobůrky",
        "Víska",
        "Rozvadovice",
        "Unčovice",
    ),
    "bio_pondeli_mistni_casti": (
        "Nasobůrky",
        "Víska",
        "Chořelice",
        "Myslechovice",
        "Savín",
        "Nová Ves",
        "Chudobín",
        "Unčovice",
    ),
}


@dataclass(frozen=True)
class SvozExceptionSource:
    """Zdroj oznámení změny svozu."""

    url: str | None
    title: str | None
    evidence: str | None


@dataclass(frozen=True)
class SvozException:
    """Validovaná jedna výjimka svozu.

    ``reschedule`` používá ``original_date`` a ``new_date``. ``include`` a
    ``cancel`` používají ``date``. Nepoužitá datumová pole zůstávají ``None``.
    """

    id: str
    action: str
    waste_type: str
    affected_locations: tuple[str, ...]
    affected_locations_snapshot: tuple[str, ...]
    affected_location_group: str | None
    original_date: date | None
    new_date: date | None
    date: date | None
    source: SvozExceptionSource
    note: str | None


def load_svoz_exceptions(
    path: Path = EXCEPTION_DATA_PATH,
    allowed_waste_types: set[str] = ALLOWED_WASTE_TYPES,
) -> tuple[SvozException, ...]:
    """Načte a zvaliduje výjimky svozu z JSON souboru.

    Funkce schválně selže výjimkou ``ValueError`` při neplatných datech, aby se
    chyba objevila při testech nebo generování webu.
    """

    with path.open(encoding="utf-8") as f:
        raw_data = json.load(f)

    if not isinstance(raw_data, list):
        raise ValueError(f"{path}: root must be a list")

    exceptions = tuple(
        _parse_exception(item, index, path, allowed_waste_types)
        for index, item in enumerate(raw_data)
    )
    _validate_unique_ids(exceptions, path)
    return exceptions


def _parse_exception(
    item: Any, index: int, path: Path, allowed_waste_types: set[str]
) -> SvozException:
    prefix = f"{path}: exception at index {index}"
    if not isinstance(item, dict):
        raise ValueError(f"{prefix} must be an object")

    _validate_allowed_fields(item, ALLOWED_FIELDS, prefix)

    exception_id = _required_string(item, "id", prefix)
    action = _required_string(item, "action", prefix)
    waste_type = _required_string(item, "waste_type", prefix)
    affected_locations = tuple(_optional_string_list(item, "affected_locations", prefix))
    affected_locations_snapshot = tuple(
        _optional_string_list(item, "affected_locations_snapshot", prefix)
    )
    affected_location_group = _optional_string(item, "affected_location_group", prefix)

    if action not in ALLOWED_ACTIONS:
        raise ValueError(
            f"{prefix} {exception_id}: action must be one of {sorted(ALLOWED_ACTIONS)}"
        )
    if waste_type not in allowed_waste_types:
        raise ValueError(
            f"{prefix} {exception_id}: waste_type must be one of {sorted(allowed_waste_types)}"
        )

    _validate_exception_target(
        affected_locations,
        affected_locations_snapshot,
        affected_location_group,
        prefix,
        exception_id,
    )
    _validate_action_dates(item, action, prefix, exception_id)

    original_date = _optional_date(item, "original_date", prefix, exception_id)
    new_date = _optional_date(item, "new_date", prefix, exception_id)
    single_date = _optional_date(item, "date", prefix, exception_id)

    return SvozException(
        id=exception_id,
        action=action,
        waste_type=waste_type,
        affected_locations=affected_locations,
        affected_locations_snapshot=affected_locations_snapshot,
        affected_location_group=affected_location_group,
        original_date=original_date,
        new_date=new_date,
        date=single_date,
        source=_required_source(item, prefix),
        note=_optional_string(item, "note", prefix),
    )


def _validate_unique_ids(exceptions: tuple[SvozException, ...], path: Path) -> None:
    seen = set()
    for exception in exceptions:
        if exception.id in seen:
            raise ValueError(f"{path}: duplicate exception id {exception.id!r}")
        seen.add(exception.id)


def _validate_allowed_fields(
    item: dict[str, Any], allowed_fields: set[str], prefix: str
) -> None:
    unknown_fields = set(item) - allowed_fields
    if unknown_fields:
        raise ValueError(f"{prefix}: unknown fields {sorted(unknown_fields)}")


def _validate_exception_target(
    affected_locations: tuple[str, ...],
    affected_locations_snapshot: tuple[str, ...],
    affected_location_group: str | None,
    prefix: str,
    exception_id: str,
) -> None:
    if not affected_locations and affected_location_group is None:
        raise ValueError(
            f"{prefix} {exception_id}: affected_locations or affected_location_group is required"
        )

    if affected_location_group is None:
        if affected_locations_snapshot:
            raise ValueError(
                f"{prefix} {exception_id}: affected_locations_snapshot requires affected_location_group"
            )
        return

    if affected_location_group not in LOCATION_GROUPS:
        raise ValueError(
            f"{prefix} {exception_id}: unknown affected_location_group {affected_location_group!r}"
        )

    if affected_locations:
        raise ValueError(
            f"{prefix} {exception_id}: affected_locations cannot be used with affected_location_group; use affected_locations_snapshot"
        )


def _validate_action_dates(
    item: dict[str, Any], action: str, prefix: str, exception_id: str
) -> None:
    config = ACTION_DATE_FIELDS[action]
    missing_fields = [field for field in config["required"] if field not in item]
    if missing_fields:
        raise ValueError(
            f"{prefix} {exception_id}: missing required fields {sorted(missing_fields)}"
        )

    present_forbidden_fields = [field for field in config["forbidden"] if field in item]
    if present_forbidden_fields:
        raise ValueError(
            f"{prefix} {exception_id}: forbidden fields for {action}: {sorted(present_forbidden_fields)}"
        )


def _required_string(item: dict[str, Any], key: str, prefix: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{prefix}: {key} is required and must be a non-empty string")
    return value


def _optional_string(item: dict[str, Any], key: str, prefix: str) -> str | None:
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{prefix}: {key} must be null or a non-empty string")
    return value


def _optional_string_list(item: dict[str, Any], key: str, prefix: str) -> list[str]:
    value = item.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not value:
        raise ValueError(f"{prefix}: {key} must be a non-empty list of strings")
    if not all(isinstance(location, str) and location for location in value):
        raise ValueError(f"{prefix}: {key} must contain only non-empty strings")
    return value


def _required_source(item: dict[str, Any], prefix: str) -> SvozExceptionSource:
    value = item.get("source")
    if value is None:
        raise ValueError(f"{prefix}: source is required")
    if not isinstance(value, dict):
        raise ValueError(f"{prefix}: source must be an object")

    _validate_allowed_fields(value, ALLOWED_SOURCE_FIELDS, f"{prefix}: source")
    for required_key in ("url", "title"):
        if required_key not in value:
            raise ValueError(f"{prefix}: source.{required_key} is required")

    return SvozExceptionSource(
        url=_optional_string(value, "url", f"{prefix}: source"),
        title=_optional_string(value, "title", f"{prefix}: source"),
        evidence=_optional_string(value, "evidence", f"{prefix}: source"),
    )


def _optional_date(
    item: dict[str, Any], key: str, prefix: str, exception_id: str
) -> date | None:
    if key not in item:
        return None

    value = _required_string(item, key, prefix)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{prefix} {exception_id}: {key} must be a valid ISO date"
        ) from exc
