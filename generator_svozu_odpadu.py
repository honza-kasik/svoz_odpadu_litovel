from datetime import datetime
from pathlib import Path

import calendar_generator
from bio_containers import load_bio_schedule
from proximity import load_proximity_config
from lokace_svozu import *
from streets import *

from site_builder import (
    build_index,
    build_bio_pages,
    build_street_pages,
    generate_sitemap
)
from social_preview import build_social_images
from project_config import project_config, validate_rollover

date_start = project_config.date_start
date_end = project_config.date_end


def build(output_dir: str | Path = "."):
    validate_rollover(project_config)
    validate_regular_schedule_years(project_config.calendar_years)
    output_dir = Path(output_dir)
    streets = all_streets['Litovel'] + mistni_casti

    generator = calendar_generator.WasteCollectionCalendarGenerator(lokace_svozu_smes,
                                                                    lokace_svozu_plast,
                                                                    lokace_svozu_papir,
                                                                    lokace_svozu_bio,
                                                                    streets,
                                                                    date_start,
                                                                    date_end)
    bio_schedule = load_bio_schedule()
    if bio_schedule.year != project_config.bio_active_year:
        raise ValueError(
            f"bio active year {project_config.bio_active_year} does not match "
            f"bio schedule year {bio_schedule.year}"
        )
    proximity_config = load_proximity_config(streets, bio_schedule.sites)
    # csv soubor
    generator.generate_csv_file(
        streets, date_start, date_end, output_dir / "waste_schedule.csv")
    
    for street in streets:
        generator.generate_ical_file(street, output_dir / "calendars", date_start, date_end)

    social_images = build_social_images(
        generator,
        streets,
        bio_schedule=bio_schedule,
        card_dir=output_dir / "resources/social",
    )

    build_index(streets, social_images, output_dir=output_dir)
    build_street_pages(
        generator,
        streets,
        social_images,
        bio_schedule,
        proximity_config,
        output_dir=output_dir,
    )
    build_bio_pages(
        bio_schedule,
        streets,
        proximity_config,
        social_images["bio"],
        output_dir=output_dir,
    )

    generate_sitemap(
        streets,
        output_dir / "sitemap.xml",
        bio_schedule=bio_schedule,
        proximity_config=proximity_config,
    )


def main():
    build()

if __name__ == "__main__":
    main()
