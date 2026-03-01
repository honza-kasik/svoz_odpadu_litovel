from datetime import datetime, timedelta

import calendar_generator
from lokace_svozu import *
from streets import *

from site_builder import (
    build_index,
    build_street_pages,
    generate_sitemap
)

date_start = datetime(2025, 1, 1)
date_end = datetime(2026, 12, 31)


def main():
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
        streets, date_start, date_end)        
    
    for street in streets:
        generator.generate_ical_file(street, "calendars", date_start, date_end)

    build_index(streets)
    build_street_pages(generator, streets)

    generate_sitemap(streets)

if __name__ == "__main__":
    main()
