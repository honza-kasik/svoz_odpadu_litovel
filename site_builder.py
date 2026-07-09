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

def build_index(streets, social_images):

    location_list_html = build_location_list(streets)

    context = {
        **meta_builder.index(),
        "SEO_FALLBACK": "",
        "LOCATION_LIST": location_list_html,
        "STREET_NAME": "null",
        "RELATED_STREETS_HTML": "",
        **build_social_context(social_images["index"]),
        "BREADCRUMBS_JSONLD": build_index_jsonld() + build_index_itemlist_jsonld(streets)
    }

    render_template("index.html", context)


# -------------------------------------------------
# STREET PAGES
# -------------------------------------------------

def build_street_pages(generator, streets, social_images):

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
            **build_social_context(social_images[slug]),
            "BREADCRUMBS_JSONLD": build_breadcrumbs_jsonld(street, slug)
        }

        render_template(
            f"ulice/{slug}/index.html",
            context
        )


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
      <li>17. 12. 2025 - svoz komunálního odpadu ve městě Litovel se přesouvá ze čtvrtku 1. 1. 2026 (svátek) na pátek 2. 1. 2026. <a href="https://www.facebook.com/litovel.eu/posts/pfbid02mx6FiHsbQETRC2V9vzuCBQMpQUDh84tfzyz7NspBdy3AL5pMdApFuzaqmGLwSfphl" target="_blank">Zdroj</a></li>
      <li>12. 2. 2026 - svoz komunálního odpadu ve městě Litovel (dle harmonogramu) se z provozních důvodů (školení řidičů) přesouvá z pondělí 16. února na úterý 17. února. <a href="https://www.litovel.eu/cs/urad/uredni-deska/aktualni-informace/zmena-svozu-odpadu.html" target="_blank">Zdroj</a></li>
      <li>30. 3. 2026 - Svoz plastů v místních částech Březové, Chořelice, Nasobůrky, Rozvadovice, Unčovice, Víska se přesouvá z pondělí 6. 4. 2026 na čtvrtek 9. 4. 2026. <a href="https://www.facebook.com/litovel.eu/posts/pfbid0325mgqJ9rzqXcXrhyQSLJ6vvTAkiG8gWd2rbrr7hbzQZ3RZgyGoc5cxFNDpQwrVjql" target="_blank">Zdroj</a></li>
      <li>19. 5. 2026 – aplikace Svoz odpadu Litovel pro Android je dostupná na <a href="https://play.google.com/store/apps/details?id=cz.litovle.svoz">Google Play</a>. Umí upozornění před svozem a zobrazuje i změny termínů.</li>
      <li>2. 7. 2026 - svoz papíru ve městě Litovel se přesouvá z pondělí 6. 7. na čtvrtek 9. 7. a svoz BIO odpadu v místních částech Chořelice, Myslechovice, Nasobůrky, Unčovice, Víska, Nová Ves, Savín a Chudobín se přesouvá z pondělí 6. 7. na úterý 7. 7. <a href="https://www.litovel.eu/cs/urad/uredni-deska/aktualni-informace/zmena-svozu-odpadu-v-pondeli-6-cervence.html" target="_blank">Zdroj</a></li>
      <li>9. 7. 2026 - svoz BIO odpadu ve městě Litovel se z provozních důvodů přesouvá ze čtvrtka 9. 7. na pátek 10. 7. 2026. <a href="https://www.litovel.eu/cs/urad/uredni-deska/aktualni-informace/svoz-bioodpadu-se-presouva-na-patek-10-7.html" target="_blank">Zdroj</a></li>
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
