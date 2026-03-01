import os
import unicodedata
import re

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
        self._event_cache = {}

    def _slugify(self, text):
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")
        text = re.sub(r"[^\w\s-]", "", text).strip().lower()
        text = re.sub(r"[-\s]+", "-", text)
        return text

    def build_event_cache(self, streets: list, date_start: datetime, date_end: datetime):
        if self._event_cache:
            return

        waste_types = [
            ("Směsný odpad", "generic", self.lokace_svozu_smes),
            ("Plast", "plastics", self.lokace_svozu_plast),
            ("Papír", "paper", self.lokace_svozu_papir),
            ("Bioodpad", "bio", self.lokace_svozu_bio),
        ]

        for street in streets:
            self._event_cache[street] = []

            for date in date_range(date_start, date_end):
                for waste_name, waste_key, locations in waste_types:
                    for lokace in locations:
                        if lokace.is_collection_happening(date, street):
                            self._event_cache[street].append({
                                "date": date,
                                "type_name": waste_name,
                                "type_key": waste_key
                            })


    def generate_ical_file(self, street: str, directory: str, date_start: datetime, date_end: datetime):
        """
        Vytvori .ics soubor pro zadanou ulici. 

        Args:
            street (str): Ulice/lokace pro kterou bude vytvoren .ics soubor
            directory (str): Adresar, kde bude .ics soubor vytvoren
            date_start (datetime): Datum od ktereho se zacnou porovnavat predikaty v lokacich svozu
            date_end (datetime): Nejzassi datum, ktere se pouzije pro predikat v lokaci svozu
        """
        self.build_event_cache([street], date_start, date_end)

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
        self.build_event_cache(streets, date_start, date_end)

        with open("waste_schedule.csv", "w") as f:
            for street in streets:
                for event in self._event_cache[street]:
                    date_string = event["date"].strftime("%Y-%m-%d")
                    f.write(f'{date_string},{event["type_key"]},{street}\n')


    def generate_location_list_html(self, streets: list, output_file: str):

        items = ""

        for street in sorted(streets):
            slug = self._slugify(street)
            items += (
                f'<li>'
                f'<a href="/ulice/{slug}/">{street}</a>'
                f'</li>\n'
            )

        html = f"""
<h2>Lokace v Litovli</h2>
<ul>
{items}
</ul>
"""

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)


    def generate_sitemap(self, streets: list, output_file: str):

        base_url = "https://svoz.litovle.cz"
        today = datetime.utcnow().strftime("%Y-%m-%d")

        urls = []

        # Homepage
        urls.append(f"""
    <url>
        <loc>{base_url}/</loc>
        <lastmod>{today}</lastmod>
    </url>""")

        # Lokace
        for street in streets:
            slug = self._slugify(street)
            urls.append(f"""
    <url>
        <loc>{base_url}/ulice/{slug}/</loc>
        <lastmod>{today}</lastmod>
    </url>""")

        sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    {''.join(urls)}
    </urlset>
    """

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(sitemap)

    def generate_html_file(self, street: str, directory: str,
                       date_start: datetime, date_end: datetime):

        start_year = date_start.year
        end_year = date_end.year

        if start_year == end_year:
            year_label = f"{start_year}"
        else:
            year_label = f"{start_year}–{end_year}"

        slug = self._slugify(street)
        folder_path = os.path.join(directory, slug)
        os.makedirs(folder_path, exist_ok=True)

        events = self._event_cache[street]

        rows = ""
        for event in events:
            rows += f"<tr><td>{event['date']}</td><td>{event['type_name']}</td></tr>\n"

        html = f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Svoz odpadu Litovel – {street}</title>
<meta name="description" id="metaDescription" content="Termíny svozu odpadu pro ulici {street} v Litovli.">

<link rel="canonical" id="canonicalLink" href="https://svoz.litovle.cz/ulice/{slug}/">

<link rel="stylesheet" href="/styles.css">
<link rel="icon" type="image/png" href="/favicon.png">

<meta property="og:title" content="Svoz odpadu Litovel – {street}">
<meta property="og:description" content="Termíny svozu odpadu pro ulici {street} v Litovli.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://svoz.litovle.cz/ulice/{slug}/">
<script>
document.documentElement.classList.add("js");
</script>
</head>

<body>

<h1 id="mainHeader">Svoz odpadu Litovel – {street}</h1>

<div id="controls">
    <div id="date-picker">
        <button type="button" id="prevMonth" aria-label="Předchozí měsíc">◀</button>
        <select id="monthSelect" aria-label="Měsíc"></select>
        <select id="yearSelect" aria-label="Rok"></select>
        <button type="button" id="nextMonth" aria-label="Další měsíc">▶</button>
    </div>
    <div id="location-picker">
        <div id="locationDropdown" class="dropdown">
            <input type="text" id="locationSearch" placeholder="Vyhledat lokaci..." autocomplete="off">
            <div id="locationOptions" class="dropdown-options"></div>
        </div>
        <div id="resetFilter" class="button">Všechny lokace</div>
    </div>
</div>
<div id="calendarContainer"></div>
<div id="info"></div>
<div id="footerControls">
    <div id="pdfYear" class="button">PDF rok</div>
    <div id="pdfMonth" class="button">PDF měsíc</div>
    <div id="copyLink" class="button">Zkopírovat URL ICS souboru do schránky</div>
</div>

<!-- SEO fallback (pro roboty bez JS) -->
<div id="seoFallback">
    <h2>Termíny svozu pro ulici {street} v roce {year_label}</h2>
    <table>
        <tr>
            <th>Datum</th>
            <th>Typ odpadu</th>
        </tr>
        {rows}
    </table>
</div>

<p class="disclaimer">
    Kalendář je
    <a href="https://github.com/honza-kasik/svoz_odpadu_litovel"
       target="_blank" rel="noopener">
       nezávislý projekt
    </a>,
    který vytvořil a spravuje
    <a href="https://honzakasik.cz"
       target="_blank" rel="noopener">
       Honza Kašík
    </a>.
    Zdrojová data poskytuje Město Litovel.
</p>

<script>
    window.STREET_NAME = "{street}";
</script>

<script src="/js/app.js"></script>
<script async src="/js/pdf_generator.js"></script>
<script async src="https://scripts.simpleanalyticscdn.com/latest.js"></script>

</body>
</html>
"""

        with open(os.path.join(folder_path, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
                    