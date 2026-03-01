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
                 lokace_svozu_bio: list[LokaceSvozu],
                 streets,
                 date_start,
                 date_end):
        self.lokace_svozu_smes = lokace_svozu_smes
        self.lokace_svozu_plast = lokace_svozu_plast
        self.lokace_svozu_papir = lokace_svozu_papir
        self.lokace_svozu_bio = lokace_svozu_bio
        self._event_cache = {}
        self._event_cache = self._build_event_cache(streets, date_start, date_end)

    def _build_event_cache(
        self,
        streets: list[str],
        date_start: datetime,
        date_end: datetime
    ) -> dict[str, list[dict]]:

        event_cache = {}

        waste_types = [
            ("Směsný odpad", "generic", self.lokace_svozu_smes),
            ("Plast", "plastics", self.lokace_svozu_plast),
            ("Papír", "paper", self.lokace_svozu_papir),
            ("Bioodpad", "bio", self.lokace_svozu_bio),
        ]

        for street in streets:
            event_cache[street] = []

            for date in date_range(date_start, date_end):
                for waste_name, waste_key, locations in waste_types:
                    for lokace in locations:
                        if lokace.is_collection_happening(date, street):
                            event_cache[street].append({
                                "date": date,
                                "type_name": waste_name,
                                "type_key": waste_key
                            })

        return event_cache

    def get_events_for_street(self, street):
        return self._event_cache[street]


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

        for event in self._event_cache[street]:
            e = Event()
            e.add("summary", f"{event['type_name']} svoz - {street}")
            e.add("dtstart", event["date"].date())
            e.add("dtend", event["date"].date() + timedelta(days=1))
            cal.add_component(e)

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
                for event in self._event_cache[street]:
                    date_string = event["date"].strftime("%Y-%m-%d")
                    f.write(f'{date_string},{event["type_key"]},{street}\n')
