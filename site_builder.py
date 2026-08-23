from datetime import date, datetime
from html import escape
import hashlib
import json
from pathlib import Path
import random
from zoneinfo import ZoneInfo

from utils import slugify
from streets import mistni_casti
from meta_builder import MetaBuilder, config
from proximity import find_nearby_bio_options
from project_config import project_config

BASE_URL = "https://svoz.litovle.cz"
TEMPLATE_PATH = "templates/layout.html"
BIO_TEMPLATE_PATH = "templates/bio.html"
BIO_DETAIL_TEMPLATE_PATH = "templates/bio_detail.html"

meta_builder = MetaBuilder(config)

# -------------------------------------------------
# TEMPLATE RENDER
# -------------------------------------------------

def render_template(output_path: str | Path, context: dict):
    template_path = context.pop("_TEMPLATE_PATH", TEMPLATE_PATH)
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Keep generated markup and its stylesheet in sync across deployments.
    context.setdefault("CSS_VERSION", file_digest("styles.css"))

    for key, value in context.items():
        html = html.replace(f"{{{{{key}}}}}", value)

    html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        f.write(html)


def file_digest(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


# -------------------------------------------------
# INDEX
# -------------------------------------------------

def build_index(streets, social_images, output_dir: str | Path = "."):

    location_list_html = build_location_list(streets)

    context = {
        **meta_builder.index(),
        "SEO_FALLBACK": "",
        "LOCATION_LIST": location_list_html,
        "STREET_NAME": "null",
        "RELATED_STREETS_HTML": "",
        "NEARBY_BIO_HTML": "",
        **build_social_context(social_images["index"]),
        "BREADCRUMBS_JSONLD": build_index_jsonld() + build_index_itemlist_jsonld(streets)
    }

    render_template(Path(output_dir) / "index.html", context)


# -------------------------------------------------
# STREET PAGES
# -------------------------------------------------

def build_street_pages(
    generator,
    streets,
    social_images,
    bio_schedule,
    proximity_config,
    output_dir: str | Path = ".",
):

    reference_date = datetime.now(ZoneInfo("Europe/Prague")).date()

    for street in streets:

        slug = slugify(street)
        fallback = build_fallback_table(generator, street)
        related_html = build_related_streets_html(street, streets)

        context = {
            **meta_builder.street(street, slug, street in mistni_casti),
            "SEO_FALLBACK": fallback,
            "LOCATION_LIST": "",
            "STREET_NAME": f'"{street}"',
            "RELATED_STREETS_HTML": related_html,
            "NEARBY_BIO_HTML": build_nearby_bio_html(
                street,
                bio_schedule,
                proximity_config,
                reference_date,
            ),
            **build_social_context(social_images[slug]),
            "BREADCRUMBS_JSONLD": build_breadcrumbs_jsonld(street, slug)
        }

        render_template(
            Path(output_dir) / "ulice" / slug / "index.html",
            context
        )


def build_bio_pages(
    schedule,
    streets,
    proximity_config,
    social_image,
    output_dir: str | Path = ".",
):
    validate_bio_routes(schedule, streets)
    reference_date = datetime.now(ZoneInfo("Europe/Prague")).date()
    search_items = build_bio_search_items(schedule, streets, proximity_config)
    overview = build_bio_overview(schedule, reference_date)

    overview_context = {
        **meta_builder.bio(schedule.year),
        "_TEMPLATE_PATH": BIO_TEMPLATE_PATH,
        "SCHEDULE_YEAR": str(schedule.year),
        "BIO_YEAR_NOTICE": build_bio_year_notice(schedule.year),
        "CURRENT_PLACEMENTS": overview["current"],
        "NEXT_PLACEMENTS": overview["next"],
        "GROUPED_SCHEDULE": overview["schedule"],
        "SOURCE_LINKS": build_bio_source_links(schedule.sources),
        "SEARCH_ITEMS_JSON": json.dumps(search_items, ensure_ascii=False).replace("<", "\\u003c"),
        "BIO_JS_VERSION": file_digest("js/bio.js"),
        **build_social_context(social_image),
        "BREADCRUMBS_JSONLD": (
            build_bio_breadcrumbs_jsonld()
            + build_bio_collection_jsonld(schedule)
        ),
    }
    render_template(Path(output_dir) / "bio" / "index.html", overview_context)

    for site in schedule.sites:
        placements = [item for item in schedule.placements if item.site.id == site.id]
        context = {
            **meta_builder.bio_site(site.display_name, site.id, schedule.year),
            "_TEMPLATE_PATH": BIO_DETAIL_TEMPLATE_PATH,
            "CONTENT": (
                build_bio_year_notice(schedule.year)
                + build_bio_site_detail(
                    site,
                    placements,
                    schedule.sources,
                    reference_date,
                    schedule.year,
                )
            ),
            "BACK_LINK": "/bio/",
            "BACK_LABEL": "Všechna stanoviště",
            **build_social_context(social_image),
            "BREADCRUMBS_JSONLD": build_bio_detail_breadcrumbs_jsonld(
                "Stanoviště", site.display_name, f"stanoviste/{site.id}"
            ),
        }
        render_template(
            Path(output_dir) / "bio" / "stanoviste" / site.id / "index.html",
            context,
        )

    for street in streets:
        if street not in proximity_config.street_coordinates:
            continue
        slug = slugify(street)
        content = build_nearby_bio_html(
            street,
            schedule,
            proximity_config,
            reference_date,
            focused=True,
        )
        context = {
            **meta_builder.bio_nearby(street, slug, schedule.year),
            "_TEMPLATE_PATH": BIO_DETAIL_TEMPLATE_PATH,
            "CONTENT": build_bio_year_notice(schedule.year) + content,
            "BACK_LINK": "/bio/",
            "BACK_LABEL": "Bio kontejnery",
            **build_social_context(social_image),
            "BREADCRUMBS_JSONLD": build_bio_detail_breadcrumbs_jsonld(
                "Poblíž", street, f"pobliz/{slug}"
            ),
        }
        render_template(
            Path(output_dir) / "bio" / "pobliz" / slug / "index.html",
            context,
        )


def validate_bio_routes(schedule, streets) -> None:
    site_slugs = [site.id for site in schedule.sites]
    street_slugs = [slugify(street) for street in streets]
    if len(site_slugs) != len(set(site_slugs)):
        raise ValueError("duplicate bio site route")
    if len(street_slugs) != len(set(street_slugs)):
        raise ValueError("duplicate bio nearby route")
    invalid = [site_id for site_id in site_slugs if slugify(site_id) != site_id]
    if invalid:
        raise ValueError(f"bio site ids must be URL-safe slugs: {', '.join(invalid)}")


def build_bio_search_items(schedule, streets, proximity_config) -> list[dict]:
    items = [
        {
            "type": "site",
            "label": site.display_name,
            "url": f"/bio/stanoviste/{site.id}/",
        }
        for site in schedule.sites
    ]
    items.extend(
        {
            "type": "location",
            "label": street,
            "url": f"/bio/pobliz/{slugify(street)}/",
        }
        for street in streets
        if street in proximity_config.street_coordinates
    )
    return items


def build_bio_overview(schedule, reference_date: date) -> dict[str, str]:
    windows = group_bio_placements(schedule.placements)
    current_windows = [
        window
        for window in windows
        if window[0] <= reference_date <= window[1]
    ]
    future_windows = [window for window in windows if window[0] > reference_date]

    if current_windows:
        current_html = "".join(build_bio_window_html(window) for window in current_windows)
    else:
        current_html = '<p class="bio-window-empty">Právě nyní není přistaven žádný kontejner.</p>'

    if future_windows:
        next_date = min(window[0] for window in future_windows)
        next_html = "".join(
            build_bio_window_html(window)
            for window in future_windows
            if window[0] == next_date
        )
    else:
        next_html = '<p class="bio-window-empty">Další termín zatím není uveden.</p>'

    months = []
    for month in range(1, 13):
        month_windows = [window for window in windows if window[0].month == month]
        if not month_windows:
            continue
        month_content = "".join(build_bio_window_html(window) for window in month_windows)
        months.append(
            f'''<section class="bio-schedule-month">
                <h3>{czech_month_name(month)}</h3>
                <div class="bio-window-list ui-data-list">{month_content}</div>
            </section>'''
        )
    schedule_html = f'''<details class="bio-year-schedule ui-panel">
        <summary>Celý roční harmonogram</summary>
        <div class="bio-year-schedule-content">{''.join(months)}</div>
    </details>'''
    return {"current": current_html, "next": next_html, "schedule": schedule_html}


def group_bio_placements(placements):
    grouped = {}
    for placement in placements:
        key = (placement.date_from, placement.date_through)
        grouped.setdefault(key, []).append(placement.site)
    return [
        (date_from, date_through, tuple(sorted(sites, key=lambda site: site.display_name)))
        for (date_from, date_through), sites in sorted(grouped.items())
    ]


def build_bio_window_html(window) -> str:
    date_from, date_through, sites = window
    site_links = ", ".join(
        f'<a href="/bio/stanoviste/{escape(site.id)}/">{escape(site.display_name)}</a>'
        for site in sites
    )
    return f'''<article class="bio-window">
        <div class="bio-window-date"><strong>{format_bio_date_range(date_from, date_through)}</strong></div>
        <div class="bio-window-sites">{site_links}</div>
    </article>'''


def czech_month_name(month: int) -> str:
    return (
        "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
        "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec",
    )[month - 1]


def build_bio_site_detail(
    site,
    placements,
    sources,
    reference_date: date,
    schedule_year: int | None = None,
) -> str:
    schedule_year = schedule_year or placements[0].date_from.year
    current = next(
        (
            item
            for item in placements
            if item.date_from <= reference_date <= item.date_through
        ),
        None,
    )
    upcoming = next((item for item in placements if item.date_from > reference_date), None)
    if current:
        status_html = f'''<section class="bio-answer bio-answer-current ui-status">
            <span class="bio-answer-kicker">Kontejner je právě přistaven</span>
            <strong>K dispozici do {format_czech_short_date(current.date_through)}</strong>
        </section>'''
    elif upcoming:
        status_html = f'''<section class="bio-answer bio-answer-upcoming ui-status">
            <span class="bio-answer-kicker">Kontejner zde nyní není</span>
            <strong>Další přistavení {format_bio_date_range(upcoming.date_from, upcoming.date_through)}</strong>
        </section>'''
    else:
        status_html = '''<section class="bio-answer ui-status">
            <span class="bio-answer-kicker">Kontejner zde nyní není</span>
            <strong>Další termín zatím není uveden.</strong>
        </section>'''

    map_link = ""
    if site.coordinates and site.coordinates.accuracy == "precise":
        point = site.coordinates
        map_link = (
            '<p><a class="button bio-detail-map" target="_blank" rel="noopener" '
            f'href="https://www.openstreetmap.org/?mlat={point.latitude:.6f}&mlon={point.longitude:.6f}#map=18/{point.latitude:.6f}/{point.longitude:.6f}">'
            "Zobrazit na mapě</a></p>"
        )

    rows = "".join(build_bio_detail_date_row(item) for item in placements)
    relevant_source_ids = {item.source.id for item in placements}
    if site.locality == "Unčovice":
        relevant_source_ids.add("bio-uncovice")
    relevant_sources = [item for item in sources if item.id in relevant_source_ids]
    source_links = build_bio_source_links(relevant_sources)
    return f'''{status_html}{map_link}
        <section class="bio-detail-schedule ui-panel">
            <h2>Termíny v roce {schedule_year}</h2>
            <ol class="bio-detail-dates ui-data-list">{rows}</ol>
        </section>
        <section class="bio-sources"><h2>Zdroje</h2><p>{source_links}</p></section>'''


def build_bio_year_notice(schedule_year: int) -> str:
    if schedule_year >= project_config.target_year:
        return ""
    return (
        '<aside class="bio-notice bio-year-notice">'
        f'Harmonogram bio kontejnerů pro rok {project_config.target_year} '
        f'zatím nebyl zveřejněn. Zobrazen je poslední dostupný harmonogram pro rok {schedule_year}.'
        "</aside>"
    )


def build_bio_detail_date_row(placement) -> str:
    date_from = placement.date_from
    date_through = placement.date_through
    return f'''<li>
        <time datetime="{date_from.isoformat()}">{date_from.day}.&nbsp;{date_from.month}.</time>
        <span class="bio-date-separator" aria-hidden="true">–</span>
        <time datetime="{date_through.isoformat()}">{date_through.day}.&nbsp;{date_through.month}.&nbsp;{date_through.year}</time>
    </li>'''


def build_nearby_bio_html(
    street,
    schedule,
    proximity_config,
    reference_date: date,
    focused: bool = False,
) -> str:
    options = find_nearby_bio_options(
        street,
        schedule,
        proximity_config,
        reference_date,
    )
    if not (options.current or options.upcoming or options.unavailable):
        return ""

    current_limit = 3 if focused else 1
    upcoming_limit = 3 if focused else 2

    def render_cards(items):
        return "".join(render_nearby_bio_card(item) for item in items)

    groups = []
    if options.current:
        groups.append(
            '<section class="nearby-bio-group">'
            '<h3>Kam lze bioodpad odvézt nyní</h3>'
            f'<div class="nearby-bio-list ui-data-list">{render_cards(options.current[:current_limit])}</div>'
            '</section>'
        )
    if options.upcoming:
        groups.append(
            '<section class="nearby-bio-group">'
            '<h3>Další přistavení v okolí</h3>'
            f'<div class="nearby-bio-list ui-data-list">{render_cards(options.upcoming[:upcoming_limit])}</div>'
            '</section>'
        )
    if options.unavailable:
        groups.append(
            '<section class="nearby-bio-group">'
            '<h3>Nejbližší známá stanoviště</h3>'
            f'<div class="nearby-bio-list ui-data-list">{render_cards(options.unavailable)}</div>'
            '</section>'
        )

    heading = "" if focused else f'''<div class="nearby-bio-heading">
            <h2 id="nearbyBioHeading">Bio kontejnery poblíž</h2>
            <a href="/bio/pobliz/{slugify(street)}/">Podrobný přehled</a>
        </div>'''
    accessible_name = 'aria-label="Bio kontejnery poblíž"' if focused else 'aria-labelledby="nearbyBioHeading"'
    street_schedule_link = ""
    if focused:
        street_schedule_link = (
            '<p class="bio-related-link">'
            f'<a href="/ulice/{slugify(street)}/">Zobrazit pravidelný svoz odpadu pro ulici {escape(street)}</a>'
            "</p>"
        )
    return f'''<section id="nearbyBio" class="nearby-bio ui-panel" {accessible_name}>
        {heading}
        {''.join(groups)}
    </section>{street_schedule_link}'''


def render_nearby_bio_card(item) -> str:
    placement = item.placement
    if item.status == "current":
        date_html = f"<span>Odvoz: {format_czech_date_with_weekday(placement.date_through)}</span>"
    elif item.status == "upcoming":
        date_html = (
            f"<span>Přistavení: {format_czech_short_date(placement.date_from)}, "
            f"odvoz: {format_czech_short_date(placement.date_through)}</span>"
        )
    else:
        date_html = "<span>Nový termín zatím není zveřejněn</span>"
    map_link = ""
    if item.site_coordinates.accuracy == "precise":
        point = item.site_coordinates
        map_url = (
            "https://www.openstreetmap.org/"
            f"?mlat={point.latitude:.6f}&mlon={point.longitude:.6f}"
            f"#map=18/{point.latitude:.6f}/{point.longitude:.6f}"
        )
        map_link = (
            f'<a class="nearby-bio-map" href="{escape(map_url)}" '
            'target="_blank" rel="noopener">Mapa</a>'
        )
    return f'''<article class="nearby-bio-card">
                <div class="nearby-bio-marker nearby-bio-marker-{item.status}" aria-hidden="true">●</div>
                <div class="nearby-bio-site">
                    <strong><a href="/bio/stanoviste/{escape(placement.site.id)}/">{escape(placement.site.display_name)}</a></strong>
                    {date_html}
                </div>
                <div class="nearby-bio-distance">{format_distance(item.distance_km, item.approximate)}</div>{map_link}
            </article>'''


def format_distance(distance_km: float, approximate: bool) -> str:
    prefix = "cca " if approximate else ""
    if distance_km < 1:
        metres = round(distance_km * 1000 / 50) * 50
        return f"{prefix}{metres} m"
    return f"{prefix}{distance_km:.1f} km".replace(".", ",")


def build_bio_placement_rows(placements, today: date | None = None) -> str:
    reference_date = today or date.today()
    rows = []
    for placement in placements:
        if placement.date_from <= reference_date <= placement.date_through:
            status = "Právě přistaveno"
            status_key = "current"
        elif placement.date_from > reference_date:
            status = "Nadcházející"
            status_key = "upcoming"
        else:
            status = "Ukončeno"
            status_key = "past"

        map_link = ""
        if (
            placement.site.coordinates is not None
            and placement.site.coordinates.accuracy == "precise"
        ):
            coordinates = placement.site.coordinates
            map_url = (
                "https://www.openstreetmap.org/"
                f"?mlat={coordinates.latitude:.6f}&mlon={coordinates.longitude:.6f}"
                f"#map=18/{coordinates.latitude:.6f}/{coordinates.longitude:.6f}"
            )
            map_link = (
                f'<a class="bio-map-link" href="{escape(map_url)}" '
                'target="_blank" rel="noopener">Zobrazit na mapě</a>'
            )

        rows.append(
            f'''<article class="bio-placement" data-date-from="{placement.date_from.isoformat()}"
                     data-date-through="{placement.date_through.isoformat()}"
                     data-site-id="{escape(placement.site.id)}"
                     data-locality="{escape(placement.site.locality)}"
                     data-search="{escape((placement.site.locality + ' ' + placement.site.name).lower())}">
                <div class="bio-site-marker" aria-hidden="true">●</div>
                <div class="bio-site">
                    <strong><a href="/bio/stanoviste/{escape(placement.site.id)}/">{escape(placement.site.display_name)}</a></strong>
                    <span>{escape(placement.site.locality)}</span>
                </div>
                <div class="bio-dates">
                    <strong>{format_bio_date_range(placement.date_from, placement.date_through)}</strong>
                    <span class="bio-status bio-status-{status_key}">{status}</span>
                </div>
                <div class="bio-actions">{map_link}</div>
            </article>'''
        )
    return "\n".join(rows)


def format_bio_date_range(date_from: date, date_through: date) -> str:
    if date_from.year == date_through.year:
        return f"{date_from.day}. {date_from.month}.–{date_through.day}. {date_through.month}. {date_through.year}"
    return (
        f"{date_from.day}. {date_from.month}. {date_from.year}–"
        f"{date_through.day}. {date_through.month}. {date_through.year}"
    )


def format_czech_short_date(value: date) -> str:
    return f"{value.day}. {value.month}. {value.year}"


def format_czech_date_with_weekday(value: date) -> str:
    weekdays = (
        "pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"
    )
    return f"{weekdays[value.weekday()]} {format_czech_short_date(value)}"


def build_bio_source_links(sources) -> str:
    return " · ".join(
        f'<a href="{escape(source.file)}">{escape(source.title)}</a>'
        for source in sources
    )


def build_bio_breadcrumbs_jsonld() -> str:
    return f'''<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "Svoz odpadu Litovel", "item": "{BASE_URL}/"}},
    {{"@type": "ListItem", "position": 2, "name": "Bio kontejnery", "item": "{BASE_URL}/bio/"}}
  ]
}}
</script>'''


def build_bio_collection_jsonld(schedule) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": f"Svoz bioodpadu Litovel – bio kontejnery {schedule.year}",
        "url": f"{BASE_URL}/bio/",
        "description": (
            "Aktuální umístění a termíny přistavení kontejnerů "
            "na bioodpad v Litovli a místních částech."
        ),
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(schedule.sites),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": position,
                    "name": site.display_name,
                    "url": f"{BASE_URL}/bio/stanoviste/{site.id}/",
                }
                for position, site in enumerate(schedule.sites, start=1)
            ],
        },
    }
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(data, ensure_ascii=False, indent=2).replace("<", "\\u003c")
        + "\n</script>"
    )


def build_bio_detail_breadcrumbs_jsonld(section, name, relative_path) -> str:
    return f'''<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "Svoz odpadu Litovel", "item": "{BASE_URL}/"}},
    {{"@type": "ListItem", "position": 2, "name": "Bio kontejnery", "item": "{BASE_URL}/bio/"}},
    {{"@type": "ListItem", "position": 3, "name": "{escape(name)}", "item": "{BASE_URL}/bio/{relative_path}/"}}
  ]
}}
</script>'''


# -------------------------------------------------
# LOCATION LIST (homepage)
# -------------------------------------------------

def build_social_context(social_image):
    return {
        "SOCIAL_IMAGE": social_image.url,
        "SOCIAL_IMAGE_ALT": social_image.alt,
        "SOCIAL_IMAGE_WIDTH": "1200",
        "SOCIAL_IMAGE_HEIGHT": "630",
    }


def build_location_list(streets):

    items = ""

    for street in sorted(streets):
        slug = slugify(street)
        items += f'<li><a href="/ulice/{slug}/">{street}</a></li>\n'

    news_items = build_year_news(config.year)

    return f"""
<div id="introText">
    <div class="homepage-app-download">
      <span>Na Androidu můžete používat aplikaci s upozorněním před svozem.</span>
      <a class="google-play-badge"
         href="https://play.google.com/store/apps/details?id=cz.litovle.svoz"
         target="_blank"
         rel="noopener"
         aria-label="Stáhnout aplikaci Svoz odpadu Litovel na Google Play">
          <img src="https://play.google.com/intl/en_us/badges/static/images/badges/cs_badge_web_generic.png"
               width="134"
               height="52"
               alt="Rozjeďte to Google Play">
      </a>
    </div>
    <h2>Co nabízíme?</h2>
    <p>
    Jednoduchý přehled termínů odvozu popelnic v Litovli podle jednotlivých ulic.
    Data vycházejí z veřejných podkladů města a jsou přehledně uspořádána
    do kalendáře pro konkrétní ulici, nebo místní část. Kalendář vždy zobrazí 
    konkrétní měsíc se svozem směsného odpadu, plastů, papíru i bioodpadu.
    </p>

    <ul>
    <li>kalendář svozu odpadu pro konkrétní ulici</li>
    <li>PDF kalendář na měsíc nebo celý rok pro konkrétní ulici a místní část</li>
    <li>jedním tlačítkem přidání do Apple, Google nebo Outlook kalendáře</li>
    <li>přehledné zobrazení i na mobilu</li>
    <li>okamžitá aktualizace při změně termínu svozu</li>
    <li>označené změněné termíny svozu v kalendáři</li>
    </ul>
    <h2>Změny svozu a novinky v roce {config.year}</h2>
    <p>Seznam změn svozu odpadu v Litovli a místních částech v roce {config.year} seřazené dle data oznámení:</p>
    <ul>
      {news_items}
    </ul>
</div>
<div id="locationList">
    <h2>Lokace svozu odpadu v {config.city_v} v roce {config.year}</h2>
    <p>
        Vyberte konkrétní ulici nebo místní část pro zobrazení termínů svozu.
    </p>
    <ul>
        {items}
    </ul>
</div>
"""


def build_year_news(year: int) -> str:
    path = Path("data") / "news" / f"{year}.html"
    if not path.is_file():
        raise ValueError(f"missing annual news file: {path}")
    return path.read_text(encoding="utf-8").strip()


# -------------------------------------------------
# SEO FALLBACK TABLE
# -------------------------------------------------

def build_fallback_table(generator, street):
    events = generator.get_events_for_street(street)

    rows = ""

    for event in events:
        date_str = event.date.strftime('%d.%m.%Y')
        waste_label = event.waste_type.label
        note = "Změna termínu" if event.is_override else ""

        rows += (
            f"<tr>"
            f"<td>{date_str}</td>"
            f"<td>{waste_label}</td>"
            f"<td>{note}</td>"
            f"</tr>\n"
        )

    return f"""
<h2>Termíny svozu odpadu – {street}</h2>
<table>
<tr>
    <th>Datum</th>
    <th>Typ odpadu</th>
    <th>Poznámka</th>
</tr>
{rows}
</table>
"""


# -------------------------------------------------
# SITEMAP
# -------------------------------------------------

def generate_sitemap(
    streets,
    output_path: str | Path = "sitemap.xml",
    bio_schedule=None,
    proximity_config=None,
):

    today = datetime.utcnow().strftime("%Y-%m-%d")

    urls = []

    urls.append(f"""
  <url>
    <loc>{BASE_URL}/</loc>
    <lastmod>{today}</lastmod>
  </url>""")

    urls.append(f"""
  <url>
    <loc>{BASE_URL}/bio/</loc>
    <lastmod>{today}</lastmod>
  </url>""")

    for street in streets:
        slug = slugify(street)
        urls.append(f"""
  <url>
    <loc>{BASE_URL}/ulice/{slug}/</loc>
    <lastmod>{today}</lastmod>
  </url>""")

    if bio_schedule is not None:
        for site in bio_schedule.sites:
            urls.append(f"""
  <url>
    <loc>{BASE_URL}/bio/stanoviste/{site.id}/</loc>
    <lastmod>{today}</lastmod>
  </url>""")

    if proximity_config is not None:
        for street in streets:
            if street not in proximity_config.street_coordinates:
                continue
            slug = slugify(street)
            urls.append(f"""
  <url>
    <loc>{BASE_URL}/bio/pobliz/{slug}/</loc>
    <lastmod>{today}</lastmod>
  </url>""")

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{''.join(urls)}
</urlset>
"""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(sitemap)


def pick_related_streets(current_street, all_streets, count=5):
    pool = [s for s in all_streets if s != current_street]

    seed = int(hashlib.md5(current_street.encode()).hexdigest(), 16)
    rng = random.Random(seed)

    if len(pool) <= count:
        return pool

    return rng.sample(pool, count)


def build_related_streets_html(current_street, all_streets):
    related = pick_related_streets(current_street, all_streets, 4)

    if not related:
        return ""

    links = []

    for street in related:
        slug = slugify(street)
        links.append(
            f'<a href="/ulice/{slug}/">{street}</a>'
        )

    return (
        '<p id="relatedStreets" class="related-streets">'
        'Další ulice: '
        + ' · '.join(links) +
        '</p>'
    )


def build_breadcrumbs_jsonld(street: str, slug: str) -> str:
    return f"""
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{
      "@type": "ListItem",
      "position": 1,
      "name": "Svoz odpadu Litovel",
      "item": "{BASE_URL}/"
    }},
    {{
      "@type": "ListItem",
      "position": 2,
      "name": "Ulice",
      "item": "{BASE_URL}/ulice/"
    }},
    {{
      "@type": "ListItem",
      "position": 3,
      "name": "{street}",
      "item": "{BASE_URL}/ulice/{slug}/"
    }}
  ]
}}
</script>
"""


def build_index_jsonld():
    return f"""
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Svoz odpadu Litovel",
  "url": "{BASE_URL}/"
}}
</script>
"""


def build_index_itemlist_jsonld(streets):
    items = []

    for i, street in enumerate(sorted(streets), start=1):
        slug = slugify(street)
        items.append(f"""
        {{
          "@type": "ListItem",
          "position": {i},
          "name": "{street}",
          "url": "{BASE_URL}/ulice/{slug}/"
        }}""")

    return f"""
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "Ulice svozu odpadu Litovel",
  "itemListElement": [{','.join(items)}]
}}
</script>
"""
