import os
from datetime import datetime
import hashlib
import random

from utils import slugify
from streets import mistni_casti
from meta_builder import MetaBuilder, config

BASE_URL = "https://svoz.litovle.cz"
TEMPLATE_PATH = "templates/layout.html"

meta_builder = MetaBuilder(config)

# -------------------------------------------------
# TEMPLATE RENDER
# -------------------------------------------------

def render_template(output_path: str, context: dict):
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    for key, value in context.items():
        html = html.replace(f"{{{{{key}}}}}", value)

    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# -------------------------------------------------
# INDEX
# -------------------------------------------------

def build_index(streets):

    location_list_html = build_location_list(streets)

    context = {
        **meta_builder.index(),
        "SEO_FALLBACK": "",
        "LOCATION_LIST": location_list_html,
        "STREET_NAME": "null"
    }

    render_template("index.html", context)


# -------------------------------------------------
# STREET PAGES
# -------------------------------------------------

def build_street_pages(generator, streets):

    for street in streets:

        slug = slugify(street)
        fallback = build_fallback_table(generator, street)
        related_html = build_related_streets_html(street, streets)

        context = {
            **meta_builder.street(street, slug, street in mistni_casti),
            "SEO_FALLBACK": fallback,
            "LOCATION_LIST": "",
            "STREET_NAME": f'"{street}"',
            "RELATED_STREETS_HTML": related_html
        }

        render_template(
            f"ulice/{slug}/index.html",
            context
        )


# -------------------------------------------------
# LOCATION LIST (homepage)
# -------------------------------------------------

def build_location_list(streets):

    items = ""

    for street in sorted(streets):
        slug = slugify(street)
        items += f'<li><a href="/ulice/{slug}/">{street}</a></li>\n'

    return f"""
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


# -------------------------------------------------
# SEO FALLBACK TABLE
# -------------------------------------------------

def build_fallback_table(generator, street):

    events = generator.get_events_for_street(street)

    rows = ""

    for event in events:
        rows += (
            f"<tr>"
            f"<td>{event.date.strftime('%d.%m.%Y')}</td>"
            f"<td>{event.waste_type.label}</td>"
            f"</tr>\n"
        )

    return f"""
<h2>Termíny svozu odpadu</h2>
<table>
<tr><th>Datum</th><th>Typ odpadu</th></tr>
{rows}
</table>
"""


# -------------------------------------------------
# SITEMAP
# -------------------------------------------------

def generate_sitemap(streets):

    today = datetime.utcnow().strftime("%Y-%m-%d")

    urls = []

    urls.append(f"""
  <url>
    <loc>{BASE_URL}/</loc>
    <lastmod>{today}</lastmod>
  </url>""")

    for street in streets:
        slug = slugify(street)
        urls.append(f"""
  <url>
    <loc>{BASE_URL}/ulice/{slug}/</loc>
    <lastmod>{today}</lastmod>
  </url>""")

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{''.join(urls)}
</urlset>
"""

    with open("sitemap.xml", "w", encoding="utf-8") as f:
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
        '<p class="related-streets">'
        'Další ulice: '
        + ' · '.join(links) +
        '</p>'
    )