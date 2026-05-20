from collections.abc import Callable
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from svoz_exceptions import load_svoz_exceptions
from streets import *
from utils import date_range


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

class LokaceSvozu:
    """
    Reprezentuje konkrétní seznam lokaci a predikát, který udává, kdy v daném místě probíhá svoz

    Args:
        predicate (Callable[datetime, bool): Pokud je predikát vyhodnocen na true, svoz v dané oblasti pro dané datum probíhá
        locations (list[str]): Seznam lokací ve kterých svoz probíhá, pokud je predicate vyhodnocen na true
        excluded_dates (list[datetime]): Seznam datumů ve kterých svoz neprobíhá i když je pro ně vyhodnoce predicate na true
        included_dates (list[datetime]): Seznam datumů ve kterých svoz probíhá i když je pro ně vyhodnocen predicate na false
    """

    def __init__(self, predicate: Callable[[datetime], bool], locations: list[str], waste_type: WasteType, excluded_dates: list[datetime] | None = None, included_dates: list[datetime] | None = None):
        self.predicate = predicate
        self.locations = locations
        self.excluded_dates = set(excluded_dates or [])
        self.included_dates = set(included_dates or [])
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
                is_override = is_date_active != predicate
                events.setdefault(street, []).append(
                    CollectionEvent(date, self.waste_type, is_override)
                )

        self._events_cache[cache_key] = events
        return events


SVOZ_EXCEPTIONS = load_svoz_exceptions(allowed_waste_types={waste_type.name for waste_type in WasteType})


def exception_dates(
    waste_type: WasteType,
    locations: list[str],
    affected_location_group: str | None = None
) -> tuple[list[datetime], list[datetime]]:
    """Vrátí data výjimek pro konkrétní definici svozu.

    Překládá datové výjimky na původní dvojici ``excluded_dates`` a
    ``included_dates``, kterou používá ``LokaceSvozu``. ``affected_location_group``
    je interní spojovací klíč pro případy, kdy jedno oznámení města dopadá na
    více samostatných definic svozu v Pythonu.
    """

    excluded_dates = []
    included_dates = []
    location_set = set(locations)

    for exception in SVOZ_EXCEPTIONS:
        if exception.waste_type != waste_type.name:
            continue

        if affected_location_group is not None:
            if exception.affected_location_group != affected_location_group:
                continue
            if exception.affected_locations and not location_set.issubset(set(exception.affected_locations)):
                raise ValueError(
                    f"{exception.id}: affected_locations do not include schedule locations"
                )
        elif set(exception.affected_locations) != location_set:
            continue

        if exception.action == "reschedule":
            if exception.original_date is None or exception.new_date is None:
                raise ValueError(f"{exception.id}: reschedule exception requires dates")
            excluded_dates.append(datetime.combine(exception.original_date, datetime.min.time()))
            included_dates.append(datetime.combine(exception.new_date, datetime.min.time()))
        elif exception.action == "include":
            if exception.date is None:
                raise ValueError(f"{exception.id}: include exception requires date")
            included_dates.append(datetime.combine(exception.date, datetime.min.time()))
        elif exception.action == "cancel":
            if exception.date is None:
                raise ValueError(f"{exception.id}: cancel exception requires date")
            excluded_dates.append(datetime.combine(exception.date, datetime.min.time()))
        else:
            raise ValueError(f"{exception.id}: unsupported action {exception.action!r}")

    return excluded_dates, included_dates


lokace_svozu_plast = [
    #POZOR! kazdy prvni lichy a sudy tyden v mesici, ne kazdy sudy a lichy tyden jak rika letak s odpady! Barevna kolecka v letaku jsou OK.
    LokaceSvozu(lambda date: week(date) % 4 == 3 and date.weekday() == 0, [location for location in litovel_lokace_plast_0 if location != 'Pavlínka'], WasteType.PLAST),
    LokaceSvozu(lambda date: week(date) % 4 == 3 and date.weekday() == 0, ['Pavlínka'], WasteType.PLAST,
                                *exception_dates(WasteType.PLAST, ['Pavlínka'])),
    LokaceSvozu(lambda date: week(date) % 4 == 2 and date.weekday() == 0, litovel_lokace_plast_1, WasteType.PLAST,
                                *exception_dates(WasteType.PLAST, litovel_lokace_plast_1, "litovel_lokace_plast_1")),
    #zacatek treti tyden v roce v pondeli, kazdy ctvrty tyden
    LokaceSvozu(lambda date: week(date) % 4 == 3 and date.weekday() == 0, 
                                ['Březové', 'Chořelice', 'Nasobůrky', 'Víska', 'Rozvadovice', 'Unčovice'], WasteType.PLAST,
                                *exception_dates(WasteType.PLAST, ['Březové', 'Chořelice', 'Nasobůrky', 'Víska', 'Rozvadovice', 'Unčovice'], "plast_pondeli_mistni_casti")),
    #zacatek druhy tyden v roce v pondeli, kazdy ctvrty tyden
    LokaceSvozu(lambda date: week(date) % 4 == 2 and date.weekday() == 4,
                                ['Savín', 'Nová Ves', 'Chudobín', 'Tři Dvory', 'Myslechovice'], WasteType.PLAST,
                                *exception_dates(WasteType.PLAST, ['Savín', 'Nová Ves', 'Chudobín', 'Tři Dvory', 'Myslechovice'])),
]

lokace_svozu_papir = [
    #kazdy ctvrty tyden v cele Litovli
    LokaceSvozu(lambda date: week(date) % 4 == 0 and date.weekday() == 0, all_streets['Litovel'], WasteType.PAPIR,
                                *exception_dates(WasteType.PAPIR, all_streets['Litovel'], "all_streets_litovel")),
    #zacatek paty tyden v roce v pondeli, kazdy paty tyden
    LokaceSvozu(lambda date: week(date) % 4 == 1 and date.weekday() == 0, ['Březové'], WasteType.PAPIR,
                                *exception_dates(WasteType.PAPIR, ['Březové'], "papir_pondeli_mistni_casti")),
    LokaceSvozu(lambda date: week(date) % 4 == 1 and date.weekday() == 0, ['Chořelice'], WasteType.PAPIR,
                                *exception_dates(WasteType.PAPIR, ['Chořelice'], "papir_pondeli_mistni_casti")),
    LokaceSvozu(lambda date: week(date) % 4 == 1 and date.weekday() == 0, ['Nasobůrky', 'Víska'], WasteType.PAPIR,
                                *exception_dates(WasteType.PAPIR, ['Nasobůrky', 'Víska'], "papir_pondeli_mistni_casti")),
    LokaceSvozu(lambda date: week(date) % 4 == 1 and date.weekday() == 0, ['Rozvadovice'], WasteType.PAPIR,
                                *exception_dates(WasteType.PAPIR, ['Rozvadovice'], "papir_pondeli_mistni_casti")),
    LokaceSvozu(lambda date: week(date) % 4 == 0 and date.weekday() == 4, ['Savín', 'Nová Ves', 'Chudobín', 'Tři Dvory', 'Myslechovice'], WasteType.PAPIR,
                                *exception_dates(WasteType.PAPIR, ['Savín', 'Nová Ves', 'Chudobín', 'Tři Dvory', 'Myslechovice'])),
    LokaceSvozu(lambda date: week(date) % 4 == 1 and date.weekday() == 0, ['Unčovice'], WasteType.PAPIR,
                                *exception_dates(WasteType.PAPIR, ['Unčovice'], "papir_pondeli_mistni_casti"))
]

lokace_svozu_smes = [
    LokaceSvozu(lambda date: week(date) % 2 == 0 and date.weekday() == 0, litovel_lokace_smes_1, WasteType.SMES,
                                *exception_dates(WasteType.SMES, litovel_lokace_smes_1, "litovel_lokace_smes_1")),
    LokaceSvozu(lambda date: week(date) % 2 == 0 and date.weekday() == 3, litovel_lokace_smes_5, WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 0, litovel_lokace_smes_0, WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 1, litovel_lokace_smes_2, WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 2, litovel_lokace_smes_3, WasteType.SMES,
                                *exception_dates(WasteType.SMES, litovel_lokace_smes_3, "litovel_lokace_smes_3")),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 3, litovel_lokace_smes_4, WasteType.SMES,
                                *exception_dates(WasteType.SMES, litovel_lokace_smes_4, "litovel_lokace_smes_4")),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 1, ['Březové'], WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 0, ['Chořelice'], WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 4, ['Myslechovice'], WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 4, ['Nasobůrky', 'Víska'], WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 0, ['Rozvadovice'], WasteType.SMES),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 2, ['Savín', 'Nová Ves', 'Chudobín'], WasteType.SMES,
                                *exception_dates(WasteType.SMES, ['Savín', 'Nová Ves', 'Chudobín'], "smes_streda_mistni_casti")),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 2, ['Tři Dvory'], WasteType.SMES,
                                *exception_dates(WasteType.SMES, ['Tři Dvory'], "smes_streda_mistni_casti")),
    LokaceSvozu(lambda date: week(date) % 2 != 0 and date.weekday() == 1, ['Unčovice'], WasteType.SMES),
    LokaceSvozu(lambda date: False, ['Dukelská'], WasteType.SMES,
                                *exception_dates(WasteType.SMES, ['Dukelská']))
]

lokace_svozu_bio = [
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 3, litovel_lokace_bio_0, WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 2, litovel_lokace_bio_1, WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 3, ['Březové'], WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 3, ['Rozvadovice'], WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 3, ['Tři Dvory'], WasteType.BIO),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, ['Nasobůrky', 'Víska'], WasteType.BIO,
                                *exception_dates(WasteType.BIO, ['Nasobůrky', 'Víska'], "bio_pondeli_mistni_casti")),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, ['Chořelice'], WasteType.BIO,
                                *exception_dates(WasteType.BIO, ['Chořelice'], "bio_pondeli_mistni_casti")),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, ['Myslechovice'], WasteType.BIO,
                                *exception_dates(WasteType.BIO, ['Myslechovice'], "bio_pondeli_mistni_casti")),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, ['Savín', 'Nová Ves', 'Chudobín'], WasteType.BIO, 
                                *exception_dates(WasteType.BIO, ['Savín', 'Nová Ves', 'Chudobín'], "bio_pondeli_mistni_casti")),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, ['Unčovice'], WasteType.BIO,
                                *exception_dates(WasteType.BIO, ['Unčovice'], "bio_pondeli_mistni_casti"))
]


def week(date: datetime) -> int:
    return date.isocalendar().week

def is_bio_collection_week(date: datetime) -> bool:
    #nektera data v lednu, unoru a prosinci svoz neprobiha
    #returns true if bio waste is not collected in given week, false otherwise
    #week 1 is the week with first Thursday
    if date.year == 2025:
        return week(date) % 2 != 0 and week(date) not in [1,3,7,51,53]
    if date.year == 2026:
        return week(date) % 2 == 0 and week(date) not in [1,2,6,50,52]
    return False
