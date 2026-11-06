from collections.abc import Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from svoz_exceptions import SvozException
from streets import *
from utils import date_range


REGULAR_SCHEDULE_YEARS = {2025, 2026}
BIO_COLLECTION_WEEK_RULES = {
    2025: {"parity": "odd", "excluded_weeks": {1, 3, 7, 51, 53}},
    2026: {"parity": "even", "excluded_weeks": {1, 2, 6, 50, 52}},
}


class WasteType(Enum):
    SMES = ("Směsný odpad", "generic")
    PLAST = ("Plast", "plastics")
    PAPIR = ("Papír", "paper")
    BIO = ("Bioodpad", "bio")

    def __init__(self, label: str, key: str):
        self.label = label
        self.key = key

@dataclass(frozen=True)
class CollectionEvent:
    date: datetime
    waste_type: WasteType
    is_override: bool = False
    exception: SvozException | None = field(default=None, compare=False)

class LokaceSvozu:
    """
    Reprezentuje konkrétní seznam lokaci a predikát, který udává, kdy v daném místě probíhá svoz

    Args:
        predicate (Callable[datetime, bool): Pokud je predikát vyhodnocen na true, svoz v dané oblasti pro dané datum probíhá
        locations (list[str]): Seznam lokací ve kterých svoz probíhá, pokud je predicate vyhodnocen na true
        excluded_dates (list[datetime]): Seznam datumů ve kterých svoz neprobíhá i když je pro ně vyhodnoce predicate na true
        included_dates (list[datetime]): Seznam datumů ve kterých svoz probíhá i když je pro ně vyhodnocen predicate na false
        event_exceptions (dict[datetime, SvozException]): Metadata výjimky pro
            jednotlivá přidaná data svozu
    """

    def __init__(
        self,
        predicate: Callable[[datetime], bool],
        locations: list[str],
        waste_type: WasteType,
        excluded_dates: list[datetime] | None = None,
        included_dates: list[datetime] | None = None,
        event_exceptions: dict[datetime, SvozException] | None = None,
    ):
        self.predicate = predicate
        self.locations = locations
        self.excluded_dates = set(excluded_dates or [])
        self.included_dates = set(included_dates or [])
        self.event_exceptions = event_exceptions or {}
        self.waste_type = waste_type
        self._events_cache = {}

    def _is_date_active(self, date: datetime) -> bool:
        if date in self.included_dates:
            return True

        if date in self.excluded_dates:
            return False

        return self.predicate(date)

    def is_collection_happening(self, date: datetime, street: str) -> bool:
        """
        Probiha svoz na street v danem date?
        """
        return street in self.locations and self._is_date_active(date)


    def get_events(
        self,
        date_start: datetime,
        date_end: datetime
    ) -> dict[str, list[CollectionEvent]]:
        """
        Ziska vsechna data jako jednotlive udalosti pro dane datum
        """

        cache_key = (date_start, date_end)
        if cache_key in self._events_cache:
            return self._events_cache[cache_key]

        events: dict[str, list[CollectionEvent]] = {}

        for date in date_range(date_start, date_end):
            is_date_active = self._is_date_active(date)

            if not is_date_active:
                continue

            predicate = self.predicate(date)
            for street in self.locations:
                exception = self.event_exceptions.get(date)
                is_override = is_date_active != predicate or exception is not None
                events.setdefault(street, []).append(
                    CollectionEvent(
                        date,
                        self.waste_type,
                        is_override,
                        exception,
                    )
                )

        self._events_cache[cache_key] = events
        return events


lokace_svozu_plast = [
    #POZOR! kazdy prvni lichy a sudy tyden v mesici, ne kazdy sudy a lichy tyden jak rika letak s odpady! Barevna kolecka v letaku jsou OK.
    LokaceSvozu(lambda date: week(date) % 4 == 3 and date.weekday() == 0, [location for location in litovel_lokace_plast_0 if location != 'Pavlínka'], WasteType.PLAST),
    LokaceSvozu(lambda date: week(date) % 4 == 3 and date.weekday() == 0, ['Pavlínka'], WasteType.PLAST),
    LokaceSvozu(lambda date: week(date) % 4 == 2 and date.weekday() == 0, litovel_lokace_plast_1, WasteType.PLAST),
    #zacatek treti tyden v roce v pondeli, kazdy ctvrty tyden
    LokaceSvozu(lambda date: week(date) % 4 == 3 and date.weekday() == 0, 
                                ['Březové', 'Chořelice', 'Nasobůrky', 'Víska', 'Rozvadovice', 'Unčovice'], WasteType.PLAST),
    #zacatek druhy tyden v roce v pondeli, kazdy ctvrty tyden
    LokaceSvozu(lambda date: week(date) % 4 == 2 and date.weekday() == 4,
                                ['Savín', 'Nová Ves', 'Chudobín', 'Tři Dvory', 'Myslechovice'], WasteType.PLAST),
]

lokace_svozu_papir = [
    #kazdy ctvrty tyden v cele Litovli
    LokaceSvozu(lambda date: week(date) % 4 == 0 and date.weekday() == 0, all_streets['Litovel'], WasteType.PAPIR),
    #zacatek paty tyden v roce v pondeli, kazdy paty tyden
    LokaceSvozu(lambda date: week(date) % 4 == 1 and date.weekday() == 0, ['Březové'], WasteType.PAPIR),
    LokaceSvozu(lambda date: week(date) % 4 == 1 and date.weekday() == 0, ['Chořelice'], WasteType.PAPIR),
    LokaceSvozu(lambda date: week(date) % 4 == 1 and date.weekday() == 0, ['Nasobůrky', 'Víska'], WasteType.PAPIR),
    LokaceSvozu(lambda date: week(date) % 4 == 1 and date.weekday() == 0, ['Rozvadovice'], WasteType.PAPIR),
    LokaceSvozu(lambda date: week(date) % 4 == 0 and date.weekday() == 4, ['Savín', 'Nová Ves', 'Chudobín', 'Tři Dvory', 'Myslechovice'], WasteType.PAPIR),
    LokaceSvozu(lambda date: week(date) % 4 == 1 and date.weekday() == 0, ['Unčovice'], WasteType.PAPIR)
]

lokace_svozu_smes = [
    LokaceSvozu(lambda date: week(date) % 2 == 0 and date.weekday() == 0, litovel_lokace_smes_1, WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 == 0 and date.weekday() == 3, litovel_lokace_smes_5, WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 0, litovel_lokace_smes_0, WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 1, litovel_lokace_smes_2, WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 2, litovel_lokace_smes_3, WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 3, litovel_lokace_smes_4, WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 1, ['Březové'], WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 0, ['Chořelice'], WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 4, ['Myslechovice'], WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 4, ['Nasobůrky', 'Víska'], WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 0, ['Rozvadovice'], WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 2, ['Savín', 'Nová Ves', 'Chudobín'], WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 2, ['Tři Dvory'], WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 1, ['Unčovice'], WasteType.SMES),
    LokaceSvozu(lambda date: False, ['Dukelská'], WasteType.SMES)
]

lokace_svozu_bio = [
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 3, litovel_lokace_bio_0, WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 2, litovel_lokace_bio_1, WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 3, ['Březové'], WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 3, ['Rozvadovice'], WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 3, ['Tři Dvory'], WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, ['Nasobůrky', 'Víska'], WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, ['Chořelice'], WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, ['Myslechovice'], WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, ['Savín', 'Nová Ves', 'Chudobín'], WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, ['Unčovice'], WasteType.BIO)
]


def week(date: datetime) -> int:
    return date.isocalendar().week

def is_bio_collection_week(date: datetime) -> bool:
    #nektera data v lednu, unoru a prosinci svoz neprobiha
    #returns true if bio waste is not collected in given week, false otherwise
    #week 1 is the week with first Thursday
    rule = BIO_COLLECTION_WEEK_RULES.get(date.year)
    if rule is None:
        return False
    expected_parity = 0 if rule["parity"] == "even" else 1
    return week(date) % 2 == expected_parity and week(date) not in rule["excluded_weeks"]


def validate_regular_schedule_years(years) -> None:
    unsupported = set(years) - REGULAR_SCHEDULE_YEARS
    missing_bio_rules = set(years) - set(BIO_COLLECTION_WEEK_RULES)
    if unsupported or missing_bio_rules:
        problems = []
        if unsupported:
            problems.append(f"regular schedule not audited for {sorted(unsupported)}")
        if missing_bio_rules:
            problems.append(f"bio week rules missing for {sorted(missing_bio_rules)}")
        raise ValueError("; ".join(problems))
