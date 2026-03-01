from datetime import datetime, timedelta

import calendar_generator
from lokace_svozu import *
from streets import *

date_start = datetime(2025, 1, 1)
date_end = datetime(2026, 12, 31)


def main():
    generator = calendar_generator.WasteCollectionCalendarGenerator(lokace_svozu_smes,
                                                                    lokace_svozu_plast,
                                                                    lokace_svozu_papir,
                                                                    lokace_svozu_bio)
    # csv soubor
    generator.generate_csv_file(
        all_streets['Litovel'] + mistni_casti, date_start, date_end)        
    
    for street in all_streets['Litovel'] + mistni_casti:
        generator.generate_ical_file(street, "calendars", date_start, date_end)
        generator.generate_html_file(street, "ulice", date_start, date_end)


    generator.generate_location_list_html(
        all_streets['Litovel'] + mistni_casti,
        "location_list.html"
    )

    generator.generate_sitemap(all_streets['Litovel'] + mistni_casti, "sitemap.xml")

if __name__ == "__main__":
    main()
