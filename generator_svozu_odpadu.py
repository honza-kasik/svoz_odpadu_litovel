from datetime import datetime, timedelta

from rules import *
from streets import *
import calendar_generator
from lokace_svozu import *

date_start =  datetime(2025, 1, 1)
date_end =  datetime(2025, 12, 31)

generator = calendar_generator.WasteCollectionCalendarGenerator(lokace_svozu_smes, lokace_svozu_plast, lokace_svozu_papir, lokace_svozu_bio)
generator.generate_csv_file(all_streets['Litovel'] + mistni_casti, date_start, date_end)
for location in all_streets['Litovel'] + mistni_casti:
    generator.generate_ical_files(location, "calendars", date_start, date_end)