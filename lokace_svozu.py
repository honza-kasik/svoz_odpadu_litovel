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
        self.locations = locations

lokace_svozu_plast = [
    #POZOR! kazdy prvni lichy a sudy tyden v mesici, ne kazdy sudy a lichy tyden jak rika letak s odpady! Barevna kolecka v letaku jsou OK.
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 3 and date.weekday() == 0, litovel_lokace_plast_0),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 2 and date.weekday() == 0 and 
                            date != datetime(2025,5,26) or date == datetime(2025,5,27), litovel_lokace_plast_1),
    #zacatek treti tyden v roce v pondeli, kazdy ctvrty tyden
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 3 and date.weekday() == 0, 'Březové'),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 3 and date.weekday() == 0, 'Chořelice'),
    #zacatek druhy tyden v roce v pondeli, kazdy ctvrty tyden
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 2 and date.weekday() == 4, 'Myslechovice'),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 3 and date.weekday() == 0, ['Nasobůrky', 'Víska']),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 3 and date.weekday() == 0, 'Rozvadovice'),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 2 and date.weekday() == 4, ['Savín', 'Nová Ves', 'Chudobín']),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 2 and date.weekday() == 4, 'Tři Dvory'),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 3 and date.weekday() == 0, 'Unčovice')
]

lokace_svozu_papir = [
    #kazdy ctvrty tyden v cele Litovli
    LokaceSvozu(lambda date: (date.isocalendar().week % 4 == 0 and date.weekday() == 0 and date != datetime(2025,5,12)) or date == datetime(2025,5,13), all_streets['Litovel']),
    #zacatek paty tyden v roce v pondeli, kazdy paty tyden
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 1 and date.weekday() == 0 and 
                            date != datetime(2025,4,21) or date == datetime(2025,4,24), 'Březové'),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 1 and date.weekday() == 0 and 
                            date != datetime(2025,4,21) or date == datetime(2025,4,24), 'Chořelice'),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 0 and date.weekday() == 4, 'Myslechovice'),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 1 and date.weekday() == 0 and 
                            date != datetime(2025,4,21) or date == datetime(2025,4,24), ['Nasobůrky', 'Víska']),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 1 and date.weekday() == 0 and 
                            date != datetime(2025,4,21) or date == datetime(2025,4,24), 'Rozvadovice'),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 0 and date.weekday() == 4, ['Savín', 'Nová Ves', 'Chudobín']),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 0 and date.weekday() == 4, 'Tři Dvory'),
    LokaceSvozu(lambda date: date.isocalendar().week % 4 == 1 and date.weekday() == 0 and 
                            date != datetime(2025,4,21) or date == datetime(2025,4,24), 'Unčovice')
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
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.weekday() == 1, 'Unčovice')
]

lokace_svozu_bio = [
    #nektera data v lednu, unoru a prosinci svoz neprobiha
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.isocalendar().week not in [1,3,7,51,53] and date.weekday() == 3, litovel_lokace_bio_0),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.isocalendar().week not in [1,3,7,51,53] and date.weekday() == 2, litovel_lokace_bio_1),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.isocalendar().week not in [1,3,7,51,53] and date.weekday() == 3, 'Březové'),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.isocalendar().week not in [1,3,7,51,53] and date.weekday() == 3, 'Rozvadovice'),
    LokaceSvozu(lambda date: date.isocalendar().week % 2 != 0 and date.isocalendar().week not in [1,3,7,51,53] and date.weekday() == 3, 'Tři Dvory'),
    LokaceSvozu(lambda date: (date.isocalendar().week % 2 != 0 and date.isocalendar().week not in [1,3,7,51,53] and date.weekday() == 0)  and 
                            date != datetime(2025,4,21) or date == datetime(2025,1,2) or date == datetime(2025,4,25), ['Nasobůrky', 'Víska']),
    LokaceSvozu(lambda date: (date.isocalendar().week % 2 != 0 and date.isocalendar().week not in [1,3,7,51,53] and date.weekday() == 0) and 
                            date != datetime(2025,4,21) or date == datetime(2025,1,2) or date == datetime(2025,4,25), 'Chořelice'),
    LokaceSvozu(lambda date: (date.isocalendar().week % 2 != 0 and date.isocalendar().week not in [1,3,7,51,53] and date.weekday() == 0) and 
                            date != datetime(2025,4,21) or date == datetime(2025,1,2) or date == datetime(2025,4,25), 'Myslechovice'),
    LokaceSvozu(lambda date: (date.isocalendar().week % 2 != 0 and date.isocalendar().week not in [1,3,7,51,53] and date.weekday() == 0) and 
                            date != datetime(2025,4,21) or date == datetime(2025,1,2) or date == datetime(2025,4,25), ['Savín', 'Nová Ves', 'Chudobín']),
    LokaceSvozu(lambda date: (date.isocalendar().week % 2 != 0 and date.isocalendar().week not in [1,3,7,51,53] and date.weekday() == 0) and 
                            date != datetime(2025,4,21) or date == datetime(2025,1,2) or date == datetime(2025,4,25), 'Unčovice')
]
