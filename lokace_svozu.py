from collections.abc import Callable
from datetime import datetime

from icalendar import Calendar, Event

from streets import *


class LokaceSvozu:
    """
    Reprezentuje konkrétní seznam lokaci a predikát, který udává, kdy v daném místě probíhá svoz

    Args:
        predicate (Callable[datetime, bool): Pokud je predikát vyhodnocen na true, svoz v dané oblasti pro dané datum probíhá
        locations (list[str]): Seznam lokací ve kterých svoz probíhá, pokud je predicate vyhodnocen na true
    """

    def __init__(self, predicate: Callable[[datetime], bool], locations: list[str]):
        self.predicate = predicate
        self.locations = locationsdate.isocalendar().week

class LokaceSvozu:
    """
    Reprezentuje konkrétní seznam lokaci a predikát, který udává, kdy v daném místě probíhá svoz

    Args:
        predicate (Callable[datetime, bool): Pokud je predikát vyhodnocen na true, svoz v dané oblasti pro dané datum probíhá
        locations (list[str]): Seznam lokací ve kterých svoz probíhá, pokud je predicate vyhodnocen na true
        excluded_dates (list[datetime]): Seznam datumů ve kterých svoz neprobíhá i když je pro ně vyhodnoce predicate na true
        included_dates (list[datetime]): Seznam datumů ve kterých svoz probíhá i když je pro ně vyhodnocen predicate na false
    """

    def __init__(self, predicate: Callable[[datetime], bool], locations: list[str], exluded_dates: list[datetime] = [], included_dates: list[datetime] = []):
        self.predicate = predicate
        self.locations = locations
        self.exluded_dates = exluded_dates
        self.included_dates = included_dates

    def is_collection_happening(self, date: datetime, street: str) -> bool:
        """
        Probiha svoz na street v danem date?
        """
        return street in self.locations and ((self.predicate(date) and date not in self.exluded_dates) or date in self.included_dates)


lokace_svozu_plast = [
    #POZOR! kazdy prvni lichy a sudy tyden v mesici, ne kazdy sudy a lichy tyden jak rika letak s odpady! Barevna kolecka v letaku jsou OK.
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 3 and date.weekday() == 0, [location for location in litovel_lokace_plast_0 if location != 'Pavlínka']),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 3 and date.weekday() == 0, 'Pavlínka', 
                                [datetime(2025,11,17)], 
                                [datetime(2025,11,18)]),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 2 and date.weekday() == 0, litovel_lokace_plast_1, 
                                [datetime(2025,5,26)], 
                                [datetime(2025,5,27)]),
    #zacatek treti tyden v roce v pondeli, kazdy ctvrty tyden
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 3 and date.weekday() == 0, 
                                ['Březové', 'Chořelice', 'Nasobůrky', 'Víska', 'Rozvadovice', 'Unčovice'], 
                                [datetime(2025,11,17)],
                                [datetime(2025,11,20)]),
    #zacatek druhy tyden v roce v pondeli, kazdy ctvrty tyden
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 2 and date.weekday() == 4,
                                ['Savín', 'Nová Ves', 'Chudobín', 'Tři Dvory', 'Myslechovice'],
                                [datetime(2025,7,25), datetime(2025,8,22), datetime(2025,9,19)],
                                [datetime(2025,7,23), datetime(2025,8,20), datetime(2025,9,17)]),
]

lokace_svozu_papir = [
    #kazdy ctvrty tyden v cele Litovli
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 0 and date.weekday() == 0, all_streets['Litovel'], 
                                [datetime(2025,5,12)], 
                                [datetime(2025,5,13)]),
    #zacatek paty tyden v roce v pondeli, kazdy paty tyden
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 1 and date.weekday() == 0, 'Březové', 
                                [datetime(2025,4,21)], 
                                [datetime(2025,4,24)]),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 1 and date.weekday() == 0, 'Chořelice', 
                                [datetime(2025,4,21)], 
                                [datetime(2025,4,24)]),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 1 and date.weekday() == 0, ['Nasobůrky', 'Víska'], 
                                [datetime(2025,4,21)], 
                                [datetime(2025,4,24)]),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 1 and date.weekday() == 0, 'Rozvadovice', 
                                [datetime(2025,4,21)], 
                                [datetime(2025,4,24)]),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 0 and date.weekday() == 4, ['Savín', 'Nová Ves', 'Chudobín', 'Tři Dvory', 'Myslechovice'],
                                [datetime(2025,7,11), datetime(2025,8,8), datetime(2025,9,5)],
                                [datetime(2025,7,9), datetime(2025,8,6),datetime(2025,9,3)]),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 1 and date.weekday() == 0, 'Unčovice', 
                                [datetime(2025,4,21)], 
                                [datetime(2025,4,24)])
]

lokace_svozu_smes = [
    LokaceSvozu(lambda date: date.isocalendar().week % 2 == 0 and date.weekday() == 0, litovel_lokace_smes_1),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 == 0 and date.weekday() == 3, litovel_lokace_smes_5),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.weekday() == 0, litovel_lokace_smes_0),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.weekday() == 1, litovel_lokace_smes_2),
    LokaceSvozu(lambda date: (date.isocalendar().week % 2 != 0 and date.weekday() == 2 and date != datetime(2025,1,1)) or date == datetime(2025,1,3), litovel_lokace_smes_3),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.weekday() == 3, litovel_lokace_smes_4),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.weekday() == 1, 'Březové'),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.weekday() == 0, 'Chořelice'),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.weekday() == 4, 'Myslechovice'),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.weekday() == 4, ['Nasobůrky', 'Víska']),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.weekday() == 0, 'Rozvadovice'),
    LokaceSvozu(lambda date: (date.isocalendar().week % 2 != 0 and date.weekday() == 2 and date != datetime(2025,1,1)) or date == datetime(2025,1,3), ['Savín', 'Nová Ves', 'Chudobín']),
    LokaceSvozu(lambda date: (date.isocalendar().week % 2 != 0 and date.weekday() == 2 and date != datetime(2025,1,1)) or date == datetime(2025,1,3), 'Tři Dvory'),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.weekday() == 1, 'Unčovice'),
    LokaceSvozu(lambda date: date == datetime(2025, 9, 11), 'Dukelská')
]

lokace_svozu_bio = [
    #nektera data v lednu, unoru a prosinci svoz neprobiha
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 3, litovel_lokace_bio_0),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 2, litovel_lokace_bio_1),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 3, 'Březové'),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 3, 'Rozvadovice'),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 3, 'Tři Dvory'),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, ['Nasobůrky', 'Víska'], 
                                [datetime(2025,4,21)],
                                [ datetime(2025,1,2), datetime(2025,4,25)]),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, 'Chořelice', 
                                [datetime(2025,4,21)],
                                [ datetime(2025,1,2), datetime(2025,4,25)]),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, 'Myslechovice', 
                                [datetime(2025,4,21)],
                                [ datetime(2025,1,2), datetime(2025,4,25)]),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, ['Savín', 'Nová Ves', 'Chudobín'], 
                                [datetime(2025,4,21)],
                                [ datetime(2025,1,2), datetime(2025,4,25)]),
    LokaceSvozu(lambda date: is_bio_collection_week(date) and date.weekday() == 0, 'Unčovice', 
                                [datetime(2025,4,21)],
                                [ datetime(2025,1,2), datetime(2025,4,25)])
]


def week(date: datetime) -> int:
    return date.isocalendar().week

def is_bio_collection_week(date: datetime) -> bool:
    #returns true if bio waste is not collected in given week, false otherwise
    #week 1 is the week with first Thursday
    if date.year == 2025:
        return week(date) % 2 != 0 and week(date) not in [1,3,7,51,53]
    if date.year == 2026:
        return week(date) % 2 == 0 and week(date) not in [1,2,6,50,52]
    return False