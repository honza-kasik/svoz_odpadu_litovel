import os
from datetime import datetime

from utils import slugify

BASE_URL = "https://svoz.litovle.cz"
TEMPLATE_PATH = "templates/layout.html"


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
        "TITLE": "Svoz odpadu Litovel – kalendář podle ulic",
        "DESCRIPTION": "Termíny svozu odpadu v Litovli podle jednotlivých ulic.",
        "CANONICAL": f"{BASE_URL}/",
        "H1": "Kalendář svozu odpadu v Litovli",
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

        context = {
            "TITLE": f"Svoz odpadu Litovel – {street}",
            "DESCRIPTION": f"Termíny svozu odpadu pro ulici {street} v Litovli.",
            "CANONICAL": f"{BASE_URL}/ulice/{slug}/",
            "H1": f"Svoz odpadu Litovel – {street}",
            "SEO_FALLBACK": fallback,
            "LOCATION_LIST": "",
            "STREET_NAME": f'"{street}"'
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
    <h2>Lokace v Litovli</h2>
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
<h2>Termíny svozu</h2>
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