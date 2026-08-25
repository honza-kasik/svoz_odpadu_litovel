from dataclasses import dataclass
from urllib.parse import quote

from project_config import project_config

@dataclass(frozen=True)
class MetaConfig:
    city: str
    city_v: str
    city_koho: str
    year: int
    base_url: str
    base_domain: str


config = MetaConfig(
    city = "Litovel",
    city_v = "Litovli",
    city_koho = "Litovle",
    year = project_config.waste_active_year,
    base_url = "https://svoz.litovle.cz",
    base_domain = "svoz.litovle.cz"
)


class MetaBuilder:

    def __init__(self, config: MetaConfig):
        self.config = config

    # -------------------------------------------------
    # INDEX
    # -------------------------------------------------

    def index(self):
        return {
            "TITLE": f"Svoz odpadu {self.config.city} {self.config.year} – kalendář podle ulic",
            "DESCRIPTION": (
                f"Kdy je v {self.config.city_v} svoz bioodpadu, plastu, papíru nebo "
                f"směsného odpadu? Vyberte ulici a zobrazte aktuální termíny pro rok {self.config.year}."
            ),
            "CANONICAL": f"{self.config.base_url}/",
            "H1": f"Kalendář svozu odpadu v {self.config.city_v}",
            "SUBTITLE": f"Aktuální přehled svozových dnů pro {config.city}. Harmonogram zahrnuje svoz komunálního odpadu, plastů, papíru a bioodpadu. Data jsou platná pro rok {config.year}.",
            "ICS_DOWNLOAD": "",
            "ICS_SUBSCRIPTION_WEBCAL": "",
            "ICS_SUBSCRIPTION_GOOGLE": ""

        }

    def bio(self, year: int):
        return {
            "TITLE": f"Svoz bioodpadu Litovel {year} – velkoobjemové kontejnery",
            "DESCRIPTION": (
                f"Svoz bioodpadu v Litovli {year}: zjistěte, kde jsou právě přistavené "
                "velkoobjemové kontejnery, kdy budou odvezeny a kam přijedou příště."
            ),
            "CANONICAL": f"{self.config.base_url}/bio/",
            "H1": f"Velkoobjemové kontejnery na bioodpad v Litovli {year}",
            "SUBTITLE": "Aktuální stanoviště a termíny přistavení.",
        }

    def bio_site(self, site_name: str, slug: str, year: int):
        return {
            "TITLE": f"Bio kontejner {site_name} – termíny přistavení {year} | Litovel",
            "DESCRIPTION": (
                f"Bio kontejner {site_name}: zjistěte, zda je právě přistavený, "
                f"a prohlédněte si všechny termíny přistavení a odvozu pro rok {year}."
            ),
            "CANONICAL": f"{self.config.base_url}/bio/stanoviste/{slug}/",
            "H1": f"Bio kontejner {site_name}",
        }

    def bio_nearby(self, street_name: str, slug: str, year: int):
        return {
            "TITLE": f"Bio kontejnery pro lokalitu {street_name} – aktuální stanoviště {year} | Litovel",
            "DESCRIPTION": (
                f"Najděte nejbližší bio kontejnery pro lokalitu {street_name} v Litovli, "
                f"jejich vzdálenost a termíny přistavení v roce {year}."
            ),
            "CANONICAL": f"{self.config.base_url}/bio/pobliz/{slug}/",
            "H1": f"Bio kontejnery pro lokalitu {street_name}",
        }

    # -------------------------------------------------
    # STREET
    # -------------------------------------------------

    def street(self, street_name: str, slug: str, is_mistni_cast: bool):

        city = self.config.city
        year = self.config.year

        if is_mistni_cast:
            description = (
                f"Kdy se v místní části {street_name} v {self.config.city_v} vyváží plast, papír nebo bioodpad? Podívejte se na aktuální harmonogram svozu pro rok {self.config.year} a stáhněte si kalendář do mobilu."
            )
            h1 = f"Svoz odpadu {city}, místní část {street_name}"
            subtitle =  f"Aktuální přehled svozových dnů pro obec {street_name} (místní část {config.city_koho}). Harmonogram zahrnuje svoz komunálního odpadu, plastů, papíru a bioodpadu. Data jsou platná pro rok {year}."
        else:
            description = (
                f"Kdy se v ulici {street_name} v {self.config.city_v} vyváží plast, papír nebo bioodpad? Podívejte se na aktuální harmonogram svozu pro rok {self.config.year} a stáhněte si kalendář do mobilu."

            )
            h1 = f"Svoz odpadu {city}, {street_name}"
            subtitle =  f"Aktuální přehled svozových dnů pro ulici {street_name} v {config.city_v}. Harmonogram zahrnuje svoz komunálního odpadu, plastů, papíru a bioodpadu. Data jsou platná pro rok {year}."


        ics_path = f"{self.config.base_domain}/calendars/{slug}.ics"

        # 1. Pro Apple, Outlook a mobilní Android (systémový kalendář)
        ics_download_https = f"https://{ics_path}"
        ics_subsciption_webcal = f"webcal://{ics_path}"

        # 2. Specificky pro Google Kalendář (webové rozhraní / odběr)
        encoded_webcal = quote(ics_subsciption_webcal, safe='')
        ics_subsciption_google = f"https://www.google.com/calendar/render?cid={encoded_webcal}"

        return {
            "TITLE": (
                f"Svoz odpadu {street_name} ({city}) – "
                f"Kalendář a termíny {year}"
            ),
            "DESCRIPTION": description,
            "CANONICAL": f"{self.config.base_url}/ulice/{slug}/",
            "H1": h1,
            "SUBTITLE": subtitle,
            "ICS_DOWNLOAD": ics_download_https,
            "ICS_SUBSCRIPTION_WEBCAL": ics_subsciption_webcal,
            "ICS_SUBSCRIPTION_GOOGLE": ics_subsciption_google
        }
