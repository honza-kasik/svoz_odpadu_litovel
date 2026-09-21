from datetime import datetime, timedelta, timezone
from pathlib import Path

from icalendar import Calendar, Event
from icalendar.prop import vDate, vUri

from lokace_svozu import LokaceSvozu, CollectionEvent
from utils import slugify


SITE_BASE_URL = "https://svoz.litovle.cz"


def _format_czech_date(value) -> str:
    return f"{value.day}. {value.month}. {value.year}"


def _description_for_event(
    street: str,
    event: CollectionEvent,
) -> str:
    parts = [f"Svoz odpadu ({event.waste_type.label}) – {street}, Litovel"]
    exception = event.exception

    if exception is not None:
        if (
            exception.action == "reschedule"
            and exception.original_date is not None
        ):
            parts.append(
                "Termín přesunut z "
                f"{_format_czech_date(exception.original_date)} na "
                f"{_format_czech_date(event.date.date())}."
            )
        elif event.is_override:
            parts.append("Termín upraven oproti pravidelnému harmonogramu.")

        parts.extend(
            value
            for value in (
                exception.source.evidence,
                exception.source.note,
                exception.note,
            )
            if value
        )
    elif event.is_override:
        parts.append("Termín upraven oproti pravidelnému harmonogramu.")

    return "\n".join(_unique_description_parts(parts))


def _unique_description_parts(parts: list[str]) -> list[str]:
    """Remove repeated human-readable description paragraphs."""

    result = []
    seen_text = set()

    for part in parts:
        text = part.strip()
        if not text or text in seen_text:
            continue
        seen_text.add(text)
        result.append(text)

    return result

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


    def generate_ical_file(
        self,
        street: str,
        directory: str | Path,
        date_start: datetime,
        date_end: datetime,
        *,
        include_legacy_alias: bool = True,
    ):
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

        slugified_street = slugify(street)

        STATIC_DTSTAMP = datetime(2025, 1, 1, tzinfo=timezone.utc)

        for event in self._event_cache[street]:

            e = Event()

            uid = f"{slugified_street}-{event.waste_type.key}-{event.date.date()}@svoz.litovle.cz"

            e.add("uid", uid)
            # no need to have change in all generated calendars with each change, let's use static stamp
            e.add("dtstamp", STATIC_DTSTAMP)

            # --- All-day event ---
            e.add("dtstart", event.date.date())
            e.add("dtend", event.date.date() + timedelta(days=1))

            summary = f"{event.waste_type.label} svoz – {street}"
            if event.is_override:
                summary = f"Změna: {summary}"

            e.add("summary", summary)

            e.add("description", _description_for_event(street, event))
            e.add("location", f"{street}, Litovel")
            e.add("transp", "TRANSPARENT")

            if event.exception is not None:
                exception = event.exception
                e.add("X-SVOZ-EXCEPTION-ID", exception.id)
                if (
                    exception.action == "reschedule"
                    and exception.original_date is not None
                ):
                    e.add(
                        "X-SVOZ-ORIGINAL-DATE",
                        vDate(exception.original_date),
                        parameters={"VALUE": "DATE"},
                    )
                e.add("url", f"{SITE_BASE_URL}/ulice/{slugified_street}/")
                if exception.source.url:
                    e.add("X-SVOZ-SOURCE-URL", vUri(exception.source.url))
                for archive_url in exception.source.archive_urls:
                    e.add("X-SVOZ-ARCHIVE-URL", vUri(archive_url))
                if exception.source.title:
                    e.add("X-SVOZ-SOURCE-TITLE", exception.source.title)
                if exception.source.evidence:
                    e.add("X-SVOZ-CHANGE-MESSAGE", exception.source.evidence)

            cal.add_component(e)

        output_dir = Path(directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        content = cal.to_ical()

        (output_dir / f"{slugified_street}.ics").write_bytes(content)
        if include_legacy_alias:
            (output_dir / f"{street}.ics").write_bytes(content)

    def generate_csv_file(self, streets: list, date_start: datetime, date_end: datetime, output_path: str | Path = "waste_schedule.csv"):
        """
        Vytvori .csv soubor se vsemi terminy svozu ve vsech lokacich, vsech typu odpadu

        Args:
            streets (list): Seznam lokaci, ktere se budou vyhledavat v dostupnych lokacich svozu po porovnani predikatu
            date_start (datetime): Datum od ktereho se zacnou porovnavat predikaty v lokacich svozu
            date_end (datetime): Nejzassi datum, ktere se pouzije pro predikat v lokaci svozu
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", encoding="utf-8") as f:
            for street in streets:
                for event in self._event_cache[street]:
                    date_string = event.date.strftime("%Y-%m-%d")
                    f.write(f'{date_string},{event.waste_type.key},{street},{int(event.is_override)}\n')
