from dataclasses import dataclass

@dataclass(frozen=True)
class MetaConfig:
    city: str
    city_v: str
    city_koho: str
    year: int
    base_url: str


config = MetaConfig(
    city = "Litovel",
    city_v = "Litovli",
    city_koho = "Litovle",
    year = 2026,
    base_url = "https://svoz.litovle.cz"
)


class MetaBuilder:

    def __init__(self, config: MetaConfig):
        self.config = config

    # -------------------------------------------------
    # INDEX
    # -------------------------------------------------

    def index(self):
        return {
            "TITLE": f"Svoz odpadu {self.config.city} – kalendář podle ulic",
            "DESCRIPTION": (
                f"Hledáte, kdy se v {self.config.city} vyváží popelnice? "
                "Zadejte svou ulici a získejte aktuální harmonogram "
                "svozu plastu, papíru i komunálního odpadu."
            ),
            "CANONICAL": f"{self.config.base_url}/",
            "H1": f"Kalendář svozu odpadu v {self.config.city_v}",
            "SUBTITLE": f"Aktuální přehled svozových dnů pro {config.city}. Harmonogram zahrnuje svoz komunálního odpadu, plastů, papíru a bioodpadu. Data jsou platná pro rok {config.year}."
        }

    # -------------------------------------------------
    # STREET
    # -------------------------------------------------

    def street(self, street_name: str, slug: str, is_mistni_cast: bool):

        city = self.config.city
        year = self.config.year

        if is_mistni_cast:
            description = (
                f"Termíny svozu odpadu pro místní část {street_name}, "
                f"{city} v roce {year}."
            )
            h1 = f"Svoz odpadu {city}, místní část {street_name}"
            subtitle =  f"Aktuální přehled svozových dnů pro obec {street_name} (místní část {config.city_koho}). Harmonogram zahrnuje svoz komunálního odpadu, plastů, papíru a bioodpadu. Data jsou platná pro rok {year}."
        else:
            description = (
                f"Termíny svozu odpadu pro ulici {street_name} "
                f"v {city} v roce {year}."
            )
            h1 = f"Svoz odpadu {city}, {street_name}"
            subtitle =  f"Aktuální přehled svozových dnů pro ulici {street_name} v {config.city_v}. Harmonogram zahrnuje svoz komunálního odpadu, plastů, papíru a bioodpadu. Data jsou platná pro rok {year}."

        return {
            "TITLE": (
                f"Svoz odpadu {street_name} ({city}) – "
                f"Kalendář a termíny {year}"
            ),
            "DESCRIPTION": description,
            "CANONICAL": f"{self.config.base_url}/ulice/{slug}/",
            "H1": h1,
            "SUBTITLE": subtitle
        }
