from datetime import datetime, timedelta

from icalendar import Calendar, Event

from lokace_svozu import LokaceSvozu
from streets import all_streets


def date_range(start_date: datetime, end_date: datetime):
    days = int((end_date - start_date).days)
    for n in range(days):
        yield start_date + timedelta(n)


class WasteCollectionCalendarGenerator:
    """
    Generator jednotlivych datovych podkladu (.ics a .csv)

    Args:
        lokace_svozu_smes: list[LokaceSvozu]: Vsechny lokace svozu smesneho odpadu, ktere se maji pouzit v generatoru
        lokace_svozu_plast: list[LokaceSvozu]: Vsechny lokace svozu plastoveho odpadu, ktere se maji pouzit v generatoru
        lokace_svozu_papir: list[LokaceSvozu]: Vsechny lokace svozu papiroveho odpadu, ktere se maji pouzit v generatoru
        lokace_svozu_bio: list[LokaceSvozu]: Vsechny lokace svozu bioodpadu, ktere se maji pouzit v generatoru
    """

    def __init__(self,  lokace_svozu_smes: list[LokaceSvozu],
                 lokace_svozu_plast: list[LokaceSvozu],
                 lokace_svozu_papir: list[LokaceSvozu],
                 lokace_svozu_bio: list[LokaceSvozu]):
        self.lokace_svozu_smes = lokace_svozu_smes
        self.lokace_svozu_plast = lokace_svozu_plast
        self.lokace_svozu_papir = lokace_svozu_papir
        self.lokace_svozu_bio = lokace_svozu_bio

    def generate_ical_file(self, street: str, directory: str, date_start: datetime, date_end: datetime):
        """
        Vytvori .ics soubor pro zadanou ulici. 

        Args:
            street (str): Ulice/lokace pro kterou bude vytvoren .ics soubor
            directory (str): Adresar, kde bude .ics soubor vytvoren
            date_start (datetime): Datum od ktereho se zacnou porovnavat predikaty v lokacich svozu
            date_end (datetime): Nejzassi datum, ktere se pouzije pro predikat v lokaci svozu
        """
        cal = Calendar()
        for date in date_range(date_start, date_end):
            for lokace in self.lokace_svozu_smes:
                if lokace.predicate(date) and street in lokace.locations:
                    event = Event()
                    event.add('summary', f'Směsný odpad svoz - {street}')
                    event.add('dtstart', date.date())
                    event.add('dtend', (date.date() + timedelta(days=1)))
                    cal.add_component(event)
            for lokace in self.lokace_svozu_plast:
                if lokace.predicate(date) and street in lokace.locations:
                    event = Event()
                    event.add('summary', f'Plast svoz - {street}')
                    event.add('dtstart', date.date())
                    event.add('dtend', (date.date() + timedelta(days=1)))
                    cal.add_component(event)
            for lokace in self.lokace_svozu_papir:
                if lokace.predicate(date) and street in lokace.locations:
                    event = Event()
                    event.add('summary', f'Papír svoz - {street}')
                    event.add('dtstart', date.date())
                    event.add('dtend', (date.date() + timedelta(days=1)))
                    cal.add_component(event)
            for lokace in self.lokace_svozu_bio:
                if lokace.predicate(date) and street in lokace.locations:
                    event = Event()
                    event.add('summary', f'Bioodpad svoz - {street}')
                    event.add('dtstart', date.date())
                    event.add('dtend', (date.date() + timedelta(days=1)))
                    cal.add_component(event)

        with open(f"{directory}/{street}.ics", "wb") as f:
            f.write(cal.to_ical())

    def generate_csv_file(self, streets: list, date_start: datetime, date_end: datetime):
        """
        Vytvori .csv soubor se vsemi terminy svozu ve vsech lokacich, vsech typu odpadu

        Args:
            streets (list): Seznam lokaci, ktere se budou vyhledavat v dostupnych lokacich svozu po porovnani predikatu
            date_start (datetime): Datum od ktereho se zacnou porovnavat predikaty v lokacich svozu
            date_end (datetime): Nejzassi datum, ktere se pouzije pro predikat v lokaci svozu
        """
        with open("waste_schedule.csv", "w") as f:
            for street in streets:
                for date in date_range(date_start, date_end):
                    date_string = date.strftime("%Y-%m-%d")
                    for lokace in self.lokace_svozu_smes:
                        if lokace.predicate(date) and street in lokace.locations:
                            f.write(f'{date_string},generic,{street}\n')
                    for lokace in self.lokace_svozu_plast:
                        if lokace.predicate(date) and street in lokace.locations:
                            f.write(f'{date_string},plastics,{street}\n')
                    for lokace in self.lokace_svozu_papir:
                        if lokace.predicate(date) and street in lokace.locations:
                            f.write(f'{date_string},paper,{street}\n')
                    for lokace in self.lokace_svozu_bio:
                        if lokace.predicate(date) and street in lokace.locations:
                            f.write(f'{date_string},bio,{street}\n')
