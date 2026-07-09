from datetime import datetime
from pathlib import Path

import calendar_generator
from lokace_svozu import *
from streets import *

from site_builder import (
    build_index,
    build_street_pages,
    generate_sitemap
)
from social_preview import build_social_images

date_start = datetime(2025, 1, 1)
date_end = datetime(2026, 12, 31)


def build(output_dir: str | Path = "."):
    output_dir = Path(output_dir)
    streets = all_streets['Litovel'] + mistni_casti

    generator = calendar_generator.WasteCollectionCalendarGenerator(lokace_svozu_smes,
                                                                    lokace_svozu_plast,
                                                                    lokace_svozu_papir,
                                                                    lokace_svozu_bio,
                                                                    streets,
                                                                    date_start,
                                                                    date_end)
    # csv soubor
    generator.generate_csv_file(
        streets, date_start, date_end, output_dir / "waste_schedule.csv")
    
    for street in streets:
        generator.generate_ical_file(street, output_dir / "calendars", date_start, date_end)

    social_images = build_social_images(generator, streets, card_dir=output_dir / "resources/social")

    build_index(streets, social_images, output_dir=output_dir)
    build_street_pages(generator, streets, social_images, output_dir=output_dir)

    generate_sitemap(streets, output_dir / "sitemap.xml")


def main():
    build()

if __name__ == "__main__":
    main()
