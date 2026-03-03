from icalendar import Calendar, Event
from datetime import datetime, timedelta, timezone

from lokace_svozu import LokaceSvozu, CollectionEvent
from utils import slugify

class WasteCollectionCalendarGenerator:
    """
    Generator jednotlivych datovych podkladu (.ics a .csv)

    Args:
        lokace_svozu_smes: list[LokaceSvozu]: Vsechny lokace svozu smesneho odpadu, ktere se maji pouzit v generatoru
        lokace_svozu_plast: list[LokaceSvozu]: Vsechny lokace svozu plastoveho odpadu, ktere se maji pouzit v generatoru
        lokace_svozu_papir: list[LokaceSvozu]: Vsechny lokace svozu papiroveho odpadu, ktere se maji pouzit v generatoru
        lokace_svozu_bio: list[LokaceSvozu]: Vsechny lokace svozu bioodpadu, ktere se maji pouzit v generatoru
    """

    def __init__(
        self,
        lokace_svozu_smes: list[LokaceSvozu],
        lokace_svozu_plast: list[LokaceSvozu],
        lokace_svozu_papir: list[LokaceSvozu],
        lokace_svozu_bio: list[LokaceSvozu],
        streets: list[str],
        date_start: datetime,
        date_end: datetime
    ):
        self._event_cache = self._build_event_cache(
            lokace_svozu_smes
            + lokace_svozu_plast
            + lokace_svozu_papir
            + lokace_svozu_bio,
            streets,
            date_start,
            date_end
        )

    def _build_event_cache(
        self,
        all_lokace: list[LokaceSvozu],
        streets: list[str],
        date_start: datetime,
        date_end: datetime
    ) -> dict[str, list[CollectionEvent]]:

        event_cache: dict[str, list[CollectionEvent]] = {
            street: [] for street in streets
        }

        for lokace in all_lokace:
            lokace_events = lokace.get_events(date_start, date_end)
            for street, events in lokace_events.items():
                if street not in event_cache:
                    continue  # safety
                event_cache[street].extend(events)

        # deterministic ordering (important for static output)
        for street in event_cache:
            event_cache[street].sort(key=lambda e: (e.date, e.waste_type.name))

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
        cal.add("prodid", "-//svoz.litovle.cz//Kalendář svozu odpadu//CS")
        cal.add("version", "2.0")
        cal.add("calscale", "GREGORIAN")
        cal.add("method", "PUBLISH")
        cal.add("X-WR-CALNAME", f"Svoz odpadu – {street} (Litovel)")
        cal.add("X-WR-TIMEZONE", "Europe/Prague")
        cal.add("X-WR-CALDESC", "Aktuální harmonogram svozu odpadu. Aktualizováno dle oficiálních podkladů města.")

        now_utc = datetime.now(timezone.utc)

        for event in self._event_cache[street]:

            e = Event()

            uid = f"{slugify(street)}-{event.waste_type.key}-{event.date.date()}@svoz.litovle.cz"

            e.add("uid", uid)
            e.add("dtstamp", now_utc)

            # --- All-day event ---
            e.add("dtstart", event.date.date())
            e.add("dtend", event.date.date() + timedelta(days=1))

            e.add("summary", f"{event.waste_type.label} svoz – {street}")

            # volitelné, ale dobré:
            e.add("description", f"Svoz odpadu ({event.waste_type.label}) – {street}, Litovel")
            e.add("location", f"{street}, Litovel")
            e.add("transp", "TRANSPARENT")

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
                    date_string = event.date.strftime("%Y-%m-%d")
                    f.write(f'{date_string},{event.waste_type.key},{street}\n')
