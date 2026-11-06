"""Apply source exceptions once to the shared schedule, scoped to exact streets."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, time

from lokace_svozu import CollectionEvent, WasteType
from svoz_exceptions import SvozException


Schedule = dict[str, list[CollectionEvent]]
EventKey = tuple[datetime, WasteType]
Operation = tuple[datetime, bool]
PlannedException = tuple[SvozException, tuple[str, ...], WasteType, tuple[Operation, ...]]


def apply_schedule_exceptions(
    regular: Schedule,
    exceptions: Iterable[SvozException],
    date_start: datetime,
    date_end: datetime,
) -> tuple[Schedule, tuple[SvozException, ...]]:
    """Return a new schedule and the exceptions relevant to its half-open range.

    Groups only select streets; they do not need to match a regular rule's group.
    Unknown streets, duplicate identities and overlapping operations fail before
    any changes are applied, including dates outside the export range. A move
    whose original date is outside the range can still add its new date inside
    it. Original input events remain unchanged.
    """
    planned = _plan_exceptions(exceptions, set(regular), date_start, date_end)
    indexed = _index_schedule(regular)
    for exception, streets, waste_type, operations in planned:
        for street in streets:
            for day, include in operations:
                key = (day, waste_type)
                if include:
                    indexed[street][key] = CollectionEvent(
                        day, waste_type, is_override=True, exception=exception
                    )
                else:
                    indexed[street].pop(key, None)
    schedule = {
        street: sorted(events.values(), key=lambda event: (event.date, event.waste_type.name))
        for street, events in indexed.items()
    }
    return schedule, tuple(exception for exception, *_ in planned)


def _plan_exceptions(
    exceptions: Iterable[SvozException],
    known_streets: set[str],
    date_start: datetime,
    date_end: datetime,
) -> list[PlannedException]:
    planned = []
    identities = set()
    claimed = {}
    for exception in sorted(exceptions, key=lambda item: item.id):
        if exception.id in identities:
            raise ValueError(f"Duplicate collection exception ID: {exception.id}")
        identities.add(exception.id)
        operations = _operations(exception)
        streets = tuple(sorted(set(exception.resolved_locations)))
        unknown = set(streets) - known_streets
        if not streets or unknown:
            raise ValueError(f"{exception.id}: unknown or empty exception locations: {sorted(unknown)}")
        waste_type = WasteType[exception.waste_type]
        for street in streets:
            for day, _ in operations:
                key = (street, waste_type, day)
                if key in claimed:
                    raise ValueError(
                        f"Conflicting collection exceptions {claimed[key]} and {exception.id}: "
                        f"{street}, {waste_type.name}, {day.date().isoformat()}"
                    )
                claimed[key] = exception.id
        in_range = tuple(
            (day, include) for day, include in operations if date_start <= day < date_end
        )
        if in_range:
            planned.append((exception, streets, waste_type, in_range))
    return planned


def _operations(exception: SvozException) -> tuple[Operation, ...]:
    if exception.action == "reschedule":
        dates = ((exception.original_date, False), (exception.new_date, True))
    elif exception.action in {"include", "cancel"}:
        dates = ((exception.date, exception.action == "include"),)
    else:
        raise ValueError(f"{exception.id}: unsupported action {exception.action}")
    if any(day is None for day, _ in dates):
        raise ValueError(f"{exception.id}: missing exception date")
    return tuple((datetime.combine(day, time.min), include) for day, include in dates)


def _index_schedule(regular: Schedule) -> dict[str, dict[EventKey, CollectionEvent]]:
    indexed = {}
    for street, events in regular.items():
        indexed[street] = {}
        for event in events:
            key = (event.date, event.waste_type)
            if key in indexed[street]:
                raise ValueError(f"Duplicate regular collection: {street}, {key}")
            indexed[street][key] = event
    return indexed
