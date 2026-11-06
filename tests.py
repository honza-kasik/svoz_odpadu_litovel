from contextlib import contextmanager
import hashlib
from dataclasses import replace
from datetime import date, datetime
from itertools import product
import json
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

import calendar_generator
from collection_changes import change_record, content_hash, load_collection_changes, write_collection_changes
from icalendar import Calendar, Event
from bio_containers import (
    BioCoordinates,
    BioPlacement,
    BioSchedule,
    BioSite,
    BioSource,
    load_bio_schedule,
)
from bio_disposal import load_bio_disposal_source
from PIL import Image
from generator_svozu_odpadu import date_end, date_start, generate_release_data
from lokace_svozu import (
    CollectionEvent,
    LokaceSvozu,
    WasteType,
    lokace_svozu_bio,
    lokace_svozu_papir,
    lokace_svozu_plast,
    lokace_svozu_smes,
    validate_regular_schedule_years,
)
from streets import all_streets, litovel_lokace_bio_0, mistni_casti
from schedule_exceptions import apply_schedule_exceptions
from svoz_exceptions import SvozException, SvozExceptionSource, load_svoz_exceptions
from utils import slugify
from scripts.watch_litovel_eu import (
    DEFAULT_URLS,
    extract_articles,
    find_candidate_articles,
    find_matched_articles,
    load_known_urls,
    run as run_litovel_watcher,
    write_json_report,
)
from social_preview import _save_card
from social_post import (
    POST_SIZE,
    SAFE_BOTTOM,
    affected_location_names,
    find_exception,
    format_czech_day,
    location_heading,
    render_post,
    save_post,
    waste_name_genitive,
)
from site_builder import (
    build_bio_placement_rows,
    build_collection_yard_html,
    build_garden_waste_guide_html,
    build_bio_overview,
    build_bio_collection_jsonld,
    build_bio_search_items,
    build_bio_site_detail,
    build_bio_year_notice,
    build_fallback_table,
    build_nearby_bio_html,
    generate_robots_txt,
    generate_sitemap,
    validate_bio_routes,
)
from meta_builder import MetaBuilder, config as meta_config
from site_builder import (
    build_breadcrumbs_jsonld, build_bio_detail_breadcrumbs_jsonld,
    build_index_itemlist_jsonld, build_social_context, render_template,
)
from seo import script_json
from scripts.validate_site_artifact import SeoParser, validate_seo_metadata
from proximity import (
    ProximityConfig,
    find_nearby_bio_placements,
    haversine_distance_km,
    load_proximity_config,
    resolve_site_coordinates,
    resolve_street_coordinates,
)
from project_config import project_config, validate_rollover
from release_data import (
    load_bio_disposal_release,
    load_bio_release,
    load_waste_schedule,
)


BIO_2026_PATH = Path("data/bio_containers/2026.json")
BIO_RELEASE_PATH = Path("bio_schedule.json")
BIO_DISPOSAL_RELEASE_PATH = Path("bio_disposal.json")


class SocialPostTest(unittest.TestCase):
    EVENT_ID = "2026-10-26-papir-litovel-posun-2026-10-28"

    def test_czech_day_uses_genitive_month_names_without_locale(self):
        expected = (
            "ledna", "února", "března", "dubna", "května", "června",
            "července", "srpna", "září", "října", "listopadu", "prosince",
        )
        for month, name in enumerate(expected, 1):
            with self.subTest(month=month):
                self.assertEqual(f"26. {name}", format_czech_day(date(2026, month, 26)))

    def test_waste_names_are_genitive(self):
        self.assertEqual(
            {key: waste_name_genitive(key) for key in ("PAPIR", "PLAST", "SMES", "BIO")},
            {"PAPIR": "papíru", "PLAST": "plastu", "SMES": "směsného odpadu", "BIO": "bioodpadu"},
        )

    def test_exception_lookup_by_id(self):
        exception = find_exception(self.EVENT_ID)
        self.assertEqual(date(2026, 10, 26), exception.original_date)
        self.assertEqual(date(2026, 10, 28), exception.new_date)
        with self.assertRaisesRegex(ValueError, "not found"):
            find_exception("missing-event")

    def test_header_locations_come_from_exception_group(self):
        self.assertEqual((), affected_location_names(find_exception(self.EVENT_ID)))
        self.assertEqual("LITOVEL", location_heading(find_exception(self.EVENT_ID)))
        selected = find_exception("2026-07-09-bio-litovel-ctvrtek-posun-2026-07-10")
        self.assertEqual("LITOVEL", location_heading(selected))
        self.assertEqual("Kosmonautů", affected_location_names(selected)[0])
        self.assertEqual("Loštická", affected_location_names(selected)[-1])
        local_parts = find_exception("2026-07-06-bio-mistni-casti-posun-2026-07-07")
        self.assertIsNone(location_heading(local_parts))

    def test_all_reschedule_posts_fit_safe_bounds(self):
        for exception in load_svoz_exceptions():
            if exception.action != "reschedule":
                continue
            with self.subTest(event=exception.id):
                result = render_post(exception)
                self.assertEqual(POST_SIZE, result.image.size)
                for element in result.elements:
                    left, top, right, bottom = element.bounds
                    self.assertGreaterEqual(left, 70)
                    self.assertLessEqual(right, 1010)
                    self.assertGreaterEqual(top, 55)
                    self.assertLessEqual(bottom, SAFE_BOTTOM)

    def test_logo_has_clear_space_below_footer_text(self):
        result = render_post(find_exception(self.EVENT_ID))
        logo_top = next(element.bounds[1] for element in result.elements if element.kind == "logo")
        footer_bottom = max(
            element.bounds[3]
            for element in result.elements
            if element.kind == "text" and element.bounds[1] >= 800
        )
        self.assertGreaterEqual(logo_top - footer_bottom, 30)

    def test_main_lines_use_one_font_size(self):
        for exception in load_svoz_exceptions():
            if exception.action != "reschedule":
                continue
            with self.subTest(event=exception.id):
                result = render_post(exception)
                sizes = [element.font_size for element in result.elements if element.kind == "main_text"]
                self.assertIn(len(sizes), (4, 5))
                self.assertEqual(1, len(set(sizes)))

    def test_missing_logo_and_fonts_fail_clearly(self):
        exception = find_exception(self.EVENT_ID)
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.png"
            with self.assertRaisesRegex(FileNotFoundError, "Litovle.cz logo PNG"):
                render_post(exception, logo_path=missing)
            with self.assertRaisesRegex(FileNotFoundError, "Inter regular font"):
                render_post(exception, font_dir=Path(temp_dir))

    def test_png_bytes_are_repeatable(self):
        exception = find_exception(self.EVENT_ID)
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.png"
            second = Path(temp_dir) / "second.png"
            save_post(render_post(exception), first)
            save_post(render_post(exception), second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_unsupported_action_fails_clearly(self):
        exception = replace(find_exception(self.EVENT_ID), action="include")
        with self.assertRaisesRegex(ValueError, "supports action 'reschedule'"):
            render_post(exception)


class BioContainersTest(unittest.TestCase):
    def test_released_bio_data_contains_resolved_presentation_inputs(self):
        released = load_bio_release(BIO_RELEASE_PATH)

        self.assertEqual(2026, released.schedule.year)
        self.assertEqual(22, len(released.schedule.sites))
        self.assertEqual(210, len(released.schedule.placements))
        self.assertTrue(all(site.coordinates for site in released.schedule.sites))
        self.assertEqual(94, len(released.proximity.street_coordinates))
        self.assertEqual("Sběrný dvůr Litovel", released.proximity.collection_yard.name)
        self.assertAlmostEqual(
            49.6861253,
            released.proximity.collection_yard.coordinates.latitude,
        )

    def test_released_bio_disposal_keeps_channels_separate(self):
        disposal = load_bio_disposal_release(BIO_DISPOSAL_RELEASE_PATH)

        self.assertEqual(date(2026, 8, 26), disposal.last_verified)
        self.assertIn("branches", disposal.channel("brown_bin")["accepted_item_ids"])
        self.assertNotIn(
            "branches", disposal.channel("large_container")["accepted_item_ids"]
        )
        self.assertIn(
            "Větve a dřevní odpad",
            disposal.channel("large_container")["rejected_labels"],
        )
        self.assertIsNone(disposal.collection_yard["opening_hours"])
        self.assertEqual(
            49.6861253,
            disposal.collection_yard["coordinates"]["latitude"],
        )

    def test_bio_disposal_source_archives_official_documents(self):
        source = load_bio_disposal_source()

        archived = [item["file"] for item in source["sources"] if item["file"]]
        self.assertEqual(4, len(archived))
        self.assertTrue(all((Path(path.lstrip("/"))).is_file() for path in archived))

    def test_active_bio_schedule_matches_project_config(self):
        schedule = load_bio_schedule()

        self.assertEqual(project_config.bio_active_year, schedule.year)

    def test_rollover_guard_rejects_stale_active_year(self):
        with self.assertRaisesRegex(ValueError, "waste active year 2026 is stale"):
            validate_rollover(project_config, date(2027, 1, 1))

    def test_bio_year_notice_is_hidden_when_years_match(self):
        self.assertEqual("", build_bio_year_notice(project_config.bio_active_year))

    def test_bio_year_notice_explains_unpublished_next_year(self):
        with patch(
            "site_builder.project_config",
            SimpleNamespace(target_year=2027),
        ):
            notice = build_bio_year_notice(2026)

        self.assertIn("pro rok 2027 zatím nebyl zveřejněn", notice)
        self.assertIn("pro rok 2026", notice)

    def test_rollover_allows_bio_schedule_to_lag_waste_schedule(self):
        decoupled = replace(
            project_config,
            target_year=2027,
            waste_active_year=2027,
            bio_active_year=2026,
            calendar_years=(2026, 2027),
        )

        validate_rollover(decoupled, date(2027, 1, 1))

    def test_unsupported_regular_schedule_year_fails_closed(self):
        with self.assertRaisesRegex(ValueError, r"not audited for \[2027\]"):
            validate_regular_schedule_years([2026, 2027])

    def test_real_schedule_loads_and_expands_windows(self):
        schedule = load_bio_schedule(BIO_2026_PATH)

        self.assertEqual(2026, schedule.year)
        self.assertEqual(22, len(schedule.sites))
        self.assertEqual(210, len(schedule.placements))
        self.assertTrue(all(item.date_from <= item.date_through for item in schedule.placements))

    def test_real_schedule_matches_audited_pdf_windows(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        groups = {
            "red": {
                "litovel-pavlinka", "litovel-dukelska", "rozvadovice", "tri-dvory"
            },
            "cyan": {
                "litovel-u-laguny", "litovel-javoricska", "litovel-cervenska",
                "brezove", "chorelice", "savin",
            },
            "yellow": {
                "litovel-komarov", "litovel-palackeho", "chudobin",
                "myslechovice", "nova-ves",
            },
            "green": {
                "litovel-sargounska", "litovel-sochova", "litovel-zerotinova",
                "nasoburky", "viska",
            },
        }
        audited = []
        red_windows = [
            ("2026-03-13", "2026-03-16", "uncovice-u-hasicarny"),
            ("2026-04-10", "2026-04-13", "uncovice-pred-selikem"),
            ("2026-05-08", "2026-05-11", "uncovice-u-hasicarny"),
            ("2026-06-05", "2026-06-08", "uncovice-pred-selikem"),
            ("2026-07-03", "2026-07-06", "uncovice-u-hasicarny"),
            ("2026-07-31", "2026-08-03", "uncovice-pred-selikem"),
            ("2026-08-28", "2026-08-31", "uncovice-u-hasicarny"),
            ("2026-09-25", "2026-09-28", "uncovice-pred-selikem"),
            ("2026-10-23", "2026-10-26", "uncovice-u-hasicarny"),
            ("2026-11-20", "2026-11-23", "uncovice-pred-selikem"),
        ]
        for date_from, date_through, uncovice_site in red_windows:
            audited.append((date_from, date_through, groups["red"] | {uncovice_site}))
        for group, windows in {
            "cyan": [
                ("2026-03-20", "2026-03-23"), ("2026-04-17", "2026-04-20"),
                ("2026-05-15", "2026-05-18"), ("2026-06-12", "2026-06-15"),
                ("2026-07-10", "2026-07-13"), ("2026-08-07", "2026-08-10"),
                ("2026-09-04", "2026-09-07"), ("2026-10-02", "2026-10-05"),
                ("2026-10-30", "2026-11-02"), ("2026-11-27", "2026-11-30"),
            ],
            "yellow": [
                ("2026-03-27", "2026-03-30"), ("2026-04-24", "2026-04-27"),
                ("2026-05-22", "2026-05-25"), ("2026-06-19", "2026-06-22"),
                ("2026-07-17", "2026-07-20"), ("2026-08-14", "2026-08-17"),
                ("2026-09-11", "2026-09-14"), ("2026-10-09", "2026-10-12"),
                ("2026-11-06", "2026-11-09"), ("2026-12-04", "2026-12-07"),
            ],
            "green": [
                ("2026-04-03", "2026-04-06"), ("2026-05-01", "2026-05-04"),
                ("2026-05-29", "2026-06-01"), ("2026-06-26", "2026-06-29"),
                ("2026-07-24", "2026-07-27"), ("2026-08-21", "2026-08-24"),
                ("2026-09-18", "2026-09-21"), ("2026-10-16", "2026-10-19"),
                ("2026-11-13", "2026-11-16"), ("2026-12-11", "2026-12-14"),
            ],
        }.items():
            audited.extend((start, end, groups[group]) for start, end in windows)

        actual = {}
        for placement in schedule.placements:
            key = (placement.date_from.isoformat(), placement.date_through.isoformat())
            actual.setdefault(key, set()).add(placement.site.id)
        expected = {(start, end): sites for start, end, sites in audited}

        self.assertEqual(expected, actual)

    def test_uncovice_uses_two_distinct_sites_from_supplement(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        placements = [
            item for item in schedule.placements if item.site.locality == "Unčovice"
        ]

        self.assertEqual(10, len(placements))
        self.assertEqual(
            {"uncovice-u-hasicarny", "uncovice-pred-selikem"},
            {item.site.id for item in placements},
        )

        fire_station = next(
            item.site for item in placements
            if item.site.id == "uncovice-u-hasicarny"
        )
        self.assertEqual("precise", fire_station.coordinates.accuracy)
        self.assertAlmostEqual(49.6678381, fire_station.coordinates.latitude)
        self.assertAlmostEqual(17.1074964, fire_station.coordinates.longitude)

        seliko = next(
            item.site for item in placements
            if item.site.id == "uncovice-pred-selikem"
        )
        self.assertEqual("precise", seliko.coordinates.accuracy)
        self.assertAlmostEqual(49.6651794, seliko.coordinates.latitude)
        self.assertAlmostEqual(17.1052936, seliko.coordinates.longitude)
        self.assertEqual("uncovice-u-hasicarny", placements[0].site.id)
        self.assertEqual("uncovice-pred-selikem", placements[1].site.id)

    def test_u_laguny_has_precise_coordinates(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        site = next(item for item in schedule.sites if item.id == "litovel-u-laguny")

        self.assertEqual("precise", site.coordinates.accuracy)
        self.assertAlmostEqual(49.70641145181769, site.coordinates.latitude)
        self.assertAlmostEqual(17.066887512989975, site.coordinates.longitude)

    def test_rozvadovice_has_precise_coordinates(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        site = next(item for item in schedule.sites if item.id == "rozvadovice")

        self.assertEqual("precise", site.coordinates.accuracy)
        self.assertAlmostEqual(49.6797269, site.coordinates.latitude)
        self.assertAlmostEqual(17.0944744, site.coordinates.longitude)

    def test_tri_dvory_has_precise_coordinates(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        site = next(item for item in schedule.sites if item.id == "tri-dvory")

        self.assertEqual("precise", site.coordinates.accuracy)
        self.assertAlmostEqual(49.7134986, site.coordinates.latitude)
        self.assertAlmostEqual(17.1080169, site.coordinates.longitude)

    def test_brezove_has_precise_coordinates(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        site = next(item for item in schedule.sites if item.id == "brezove")

        self.assertEqual("precise", site.coordinates.accuracy)
        self.assertAlmostEqual(49.67941821890901, site.coordinates.latitude)
        self.assertAlmostEqual(17.115419785060006, site.coordinates.longitude)

    def test_chorelice_has_precise_coordinates(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        site = next(item for item in schedule.sites if item.id == "chorelice")

        self.assertEqual("precise", site.coordinates.accuracy)
        self.assertAlmostEqual(49.6910900, site.coordinates.latitude)
        self.assertAlmostEqual(17.0788697, site.coordinates.longitude)

    def test_savin_has_precise_coordinates(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        site = next(item for item in schedule.sites if item.id == "savin")

        self.assertEqual("precise", site.coordinates.accuracy)
        self.assertAlmostEqual(49.6731936, site.coordinates.latitude)
        self.assertAlmostEqual(16.9842797, site.coordinates.longitude)

    def test_cross_month_placement_intersects_both_months(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        placement = next(
            item
            for item in schedule.placements
            if item.id == "bio-2026-05-29--litovel-sargounska"
        )

        self.assertTrue(placement.intersects_month(2026, 5))
        self.assertTrue(placement.intersects_month(2026, 6))
        self.assertFalse(placement.intersects_month(2026, 7))

    def test_generated_status_is_inclusive_on_both_boundaries(self):
        source = BioSource("source", "Source", "/source.pdf")
        site = BioSite("site", "Litovel", "Test", None)
        placement = BioPlacement(
            "placement", site, date(2026, 5, 10), date(2026, 5, 13), source
        )

        first_day = build_bio_placement_rows([placement], today=date(2026, 5, 10))
        last_day = build_bio_placement_rows([placement], today=date(2026, 5, 13))

        self.assertIn("Právě přistaveno", first_day)
        self.assertIn("Právě přistaveno", last_day)

    def test_map_link_requires_precise_coordinates(self):
        source = BioSource("source", "Source", "/source.pdf")
        placement_without_map = BioPlacement(
            "without-map",
            BioSite("without", "Litovel", "Bez mapy", None),
            date(2026, 5, 10),
            date(2026, 5, 13),
            source,
        )
        placement_with_map = BioPlacement(
            "with-map",
            BioSite(
                "with",
                "Litovel",
                "S mapou",
                BioCoordinates(49.701, 17.076),
            ),
            date(2026, 5, 10),
            date(2026, 5, 13),
            source,
        )

        self.assertNotIn("Zobrazit na mapě", build_bio_placement_rows([placement_without_map]))
        self.assertIn("Zobrazit na mapě", build_bio_placement_rows([placement_with_map]))

    def test_invalid_site_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "data").mkdir()
            (root / "resources").mkdir()
            (root / "resources" / "source.pdf").write_bytes(b"%PDF-test")
            path = root / "data" / "bio_containers.json"
            path.write_text(
                json.dumps(
                    {
                        "year": 2026,
                        "sources": [
                            {"id": "source", "title": "Source", "file": "/resources/source.pdf"}
                        ],
                        "sites": [],
                        "placement_windows": [
                            {
                                "id": "window",
                                "date_from": "2026-05-10",
                                "date_through": "2026-05-13",
                                "source_id": "source",
                                "site_ids": ["missing"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown site missing"):
                load_bio_schedule(path)


class BioProximityTest(unittest.TestCase):
    def _schedule(self):
        source = BioSource("source", "Source", "/source.pdf")
        sites = tuple(
            BioSite(site_id, "Litovel", site_id.upper(), None)
            for site_id in ("a", "b", "c", "d")
        )
        placements = (
            BioPlacement("a-current", sites[0], date(2026, 8, 19), date(2026, 8, 21), source),
            BioPlacement("b-current", sites[1], date(2026, 8, 20), date(2026, 8, 21), source),
            BioPlacement("c-next", sites[2], date(2026, 8, 23), date(2026, 8, 26), source),
            BioPlacement("d-next", sites[3], date(2026, 8, 23), date(2026, 8, 26), source),
            BioPlacement("a-later", sites[0], date(2026, 9, 1), date(2026, 9, 4), source),
        )
        return BioSchedule(2026, (source,), sites, placements)

    def _config(self, schedule, *, provisional=False):
        accuracy = "provisional" if provisional else "precise"
        return ProximityConfig(
            {"Testovací": BioCoordinates(49.7, 17.07, accuracy)},
            {
                "a": BioCoordinates(49.700, 17.071, accuracy),
                "b": BioCoordinates(49.700, 17.072, accuracy),
                "c": BioCoordinates(49.700, 17.073, accuracy),
                "d": BioCoordinates(49.700, 17.074, accuracy),
            },
        )

    def test_haversine_distance_is_reasonable(self):
        first = BioCoordinates(49.7, 17.07)
        second = BioCoordinates(49.7, 17.084)

        self.assertAlmostEqual(1.01, haversine_distance_km(first, second), delta=0.03)

    def test_nearby_sites_are_distance_first_with_status_as_context(self):
        schedule = self._schedule()
        nearby = find_nearby_bio_placements(
            "Testovací",
            schedule,
            self._config(schedule),
            date(2026, 8, 20),
        )

        self.assertEqual(["a", "b", "c"], [item.placement.site.id for item in nearby])
        self.assertEqual(["current", "current", "upcoming"], [item.status for item in nearby])

    def test_upcoming_sites_are_ranked_by_distance_not_window_date(self):
        schedule = self._schedule()
        nearby = find_nearby_bio_placements(
            "Testovací",
            schedule,
            self._config(schedule),
            date(2026, 8, 22),
            limit=2,
        )

        self.assertEqual(["a", "c"], [item.placement.site.id for item in nearby])
        self.assertTrue(all(item.status == "upcoming" for item in nearby))

    def test_expired_schedule_falls_back_to_nearest_physical_sites(self):
        schedule = self._schedule()
        nearby = find_nearby_bio_placements(
            "Testovací",
            schedule,
            self._config(schedule),
            date(2027, 1, 1),
            limit=3,
        )

        self.assertEqual(["a", "b", "c"], [item.placement.site.id for item in nearby])
        self.assertTrue(all(item.status == "schedule-unavailable" for item in nearby))

    def test_coordinate_replacement_reorders_without_changing_placements(self):
        schedule = self._schedule()
        original = self._config(schedule)
        moved = ProximityConfig(
            original.street_coordinates,
            {
                **original.site_coordinates,
                "a": BioCoordinates(49.700, 17.090),
                "b": BioCoordinates(49.700, 17.0705),
            },
        )

        original_nearest = find_nearby_bio_placements(
            "Testovací", schedule, original, date(2026, 8, 20), limit=1
        )
        moved_nearest = find_nearby_bio_placements(
            "Testovací", schedule, moved, date(2026, 8, 20), limit=1
        )

        self.assertEqual("a", original_nearest[0].placement.site.id)
        self.assertEqual("b", moved_nearest[0].placement.site.id)

    def test_provisional_coordinates_render_approximation_without_map(self):
        schedule = self._schedule()
        html = build_nearby_bio_html(
            "Testovací",
            schedule,
            self._config(schedule, provisional=True),
            date(2026, 8, 20),
        )

        self.assertEqual(3, html.count('class="nearby-bio-card"'))
        self.assertIn("cca ", html)
        self.assertNotIn("OpenStreetMap", html)
        self.assertNotIn("nearby-bio-map", html)

    def test_real_config_only_returns_results_for_grounded_streets(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        streets = all_streets["Litovel"] + mistni_casti
        config = load_proximity_config(streets, schedule.sites)

        self.assertEqual(94, len(config.street_coordinates))
        self.assertEqual(19, len(config.site_coordinates))
        self.assertEqual(
            3,
            len(find_nearby_bio_placements("B. Němcové", schedule, config, date(2026, 8, 20))),
        )
        self.assertEqual(
            [],
            find_nearby_bio_placements("Sovova", schedule, config, date(2026, 8, 20)),
        )

    def test_b_nemcove_to_sochova_provisional_distance_is_under_one_km(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        streets = all_streets["Litovel"] + mistni_casti
        config = load_proximity_config(streets, schedule.sites)
        street_point = resolve_street_coordinates("B. Němcové", config)
        sochova = next(
            site for site in schedule.sites if site.id == "litovel-sochova"
        )
        site_point = resolve_site_coordinates(sochova, config)

        self.assertLess(haversine_distance_km(street_point, site_point), 1)

    def test_uncovice_page_keeps_local_upcoming_site_ahead_of_distant_current_sites(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        streets = all_streets["Litovel"] + mistni_casti
        config = load_proximity_config(streets, schedule.sites)

        nearby = find_nearby_bio_placements(
            "Unčovice", schedule, config, date(2026, 8, 23)
        )

        self.assertEqual("uncovice-u-hasicarny", nearby[0].placement.site.id)
        self.assertEqual("upcoming", nearby[0].status)
        self.assertLess(nearby[0].distance_km, 1)


class SeoMetadataTest(unittest.TestCase):
    def render(self, root, name='Svoz odpadu "A & B" <test> {{TITLE}}'):
        image = SimpleNamespace(url=meta_config.base_url + '/resources/social/test.png', alt=name)
        context = {
            **MetaBuilder(meta_config).index(), 'TITLE': name, 'H1': name,
            'DESCRIPTION': 'Termíny pro "A & B" <lokalitu> v Litovli.',
            'SEO_FALLBACK': '<p>Static schedule.</p>', 'LOCATION_LIST': '',
            'STREET_NAME': script_json(name), 'RELATED_STREETS_HTML': '',
            'NEARBY_BIO_HTML': '', 'BREADCRUMBS_JSONLD': '',
            **build_social_context(image),
        }
        original = dict(context)
        path = root / 'index.html'
        render_template(path, context)
        self.assertEqual(context, original, 'Rendering must not alter caller metadata')
        (root / 'CNAME').write_text('svoz.litovle.cz\n')
        return path

    def test_metadata_round_trips_quotes_ampersands_and_placeholder_like_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.render(root)
            parser = SeoParser()
            parser.feed(path.read_text().split('</head>', 1)[0])
            self.assertEqual(parser.titles, ['Svoz odpadu "A & B" <test> {{TITLE}}'])
            self.assertEqual(parser.meta['description'], ['Termíny pro "A & B" <lokalitu> v Litovli.'])
            full = SeoParser()
            full.feed(path.read_text())
            self.assertEqual(full.headings, parser.titles)
            self.assertIn('<p>Static schedule.</p>', path.read_text())
            self.assertEqual(parser.structured[0]['@graph'][-1]['name'], parser.titles[0])
            validate_seo_metadata(root)

    def test_script_like_text_cannot_close_jsonld_or_street_name_script(self):
        name = 'Ulice </script><script>alert("x")</script> & "název"'
        with tempfile.TemporaryDirectory() as directory:
            path = self.render(Path(directory), name)
            text = path.read_text()
            self.assertNotIn('</script><script>alert', text)
            self.assertNotIn(name, text)
            self.assertIn(script_json(name), text)
            parser = SeoParser()
            parser.feed(text.split('</head>', 1)[0])
            self.assertEqual(parser.structured[0]['@graph'][-1]['name'], name)

    def test_breadcrumb_names_are_json_text_and_street_hierarchy_has_no_missing_index(self):
        name = 'Ulice "A & B" </script>'
        for markup in [build_breadcrumbs_jsonld(name, 'a-b'),
                       build_bio_detail_breadcrumbs_jsonld('Stanoviště', name, 'stanoviste/a-b')]:
            parser = SeoParser()
            parser.feed(markup)
            items = parser.structured[0]['itemListElement']
            self.assertEqual(items[-1]['name'], name)
            self.assertNotIn(meta_config.base_url + '/ulice/', [item['item'] for item in items])
            self.assertNotIn('</script><script>', markup)
        parser = SeoParser()
        parser.feed(build_index_itemlist_jsonld([name]))
        self.assertEqual(parser.structured[0]['itemListElement'][0]['name'], name)

    def test_metadata_uses_the_builders_year_and_city_consistently(self):
        builder = MetaBuilder(replace(meta_config, year=2030, city='Testov', city_v='Testově', city_koho='Testova'))
        for data in [builder.index(), builder.street('Ulice', 'ulice', False), builder.street('Část', 'cast', True)]:
            self.assertIn('2030', data['TITLE'])
            self.assertIn('2030', data['DESCRIPTION'])
            self.assertIn('2030', data['SUBTITLE'])
            self.assertNotIn('Litovel', data['SUBTITLE'])

    def test_street_description_does_not_promise_missing_mixed_waste_dates(self):
        streets = all_streets['Litovel'] + mistni_casti
        schedule = load_waste_schedule(Path('waste_schedule.csv'), streets)
        builder = MetaBuilder(replace(meta_config, year=2026))
        for street in ['Karlov', 'Koupaliště', 'Lesní zátiší', 'Sovova', 'Tichá', 'Třídvorská', 'Šerhovní']:
            with self.subTest(street=street):
                self.assertFalse(any(
                    event.date.year == 2026 and event.waste_type == WasteType.SMES
                    for event in schedule.get_events_for_street(street)
                ))
                description = builder.street(street, 'street', False)['DESCRIPTION']
                self.assertIn(street, description)
                self.assertIn('2026', description)
                self.assertNotIn('směsného odpadu', description)

    def test_artifact_validation_rejects_localhost_broken_json_and_missing_breadcrumb_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.render(root)
            good = path.read_text()
            path.write_text(good.replace('<h1 id="mainHeader">', '<h2 id="mainHeader">').replace('</h1>', '</h2>'))
            with self.assertRaisesRegex(SystemExit, 'main heading must match'):
                validate_seo_metadata(root)
            path.write_text(good.replace('rel="canonical" id="canonicalLink" href="https://svoz.litovle.cz/"',
                                         'rel="canonical" id="canonicalLink" href="http://localhost:8000/"'))
            with self.assertRaisesRegex(SystemExit, 'expected one canonical URL'):
                validate_seo_metadata(root)
            path.write_text(good.replace('"@context": "https://schema.org"', '"@context": broken'))
            with self.assertRaisesRegex(SystemExit, 'invalid JSON-LD'):
                validate_seo_metadata(root)
            path.write_text(good.replace('</head>', build_breadcrumbs_jsonld('Missing', 'missing') + '</head>'))
            with self.assertRaisesRegex(SystemExit, 'structured data links to missing page'):
                validate_seo_metadata(root)


class BioSeoPagesTest(unittest.TestCase):
    def test_bio_metadata_keeps_overview_and_detail_pages_container_specific(self):
        builder = MetaBuilder(meta_config)

        index = builder.index()
        overview = builder.bio(2026)
        site = builder.bio_site("Unčovice – u hasičárny", "uncovice-u-hasicarny", 2026)
        nearby = builder.bio_nearby("Unčovice", "uncovice", 2026)

        self.assertIn("Kdy je v Litovli svoz bioodpadu", index["DESCRIPTION"])
        self.assertIn("směsného odpadu", index["DESCRIPTION"])
        self.assertIn("Svoz bioodpadu Litovel 2026", overview["TITLE"])
        self.assertIn("velkoobjemové kontejnery", overview["TITLE"])
        self.assertIn("velkoobjemové kontejnery", overview["DESCRIPTION"])
        self.assertEqual("Aktuální stanoviště a termíny přistavení.", overview["SUBTITLE"])
        self.assertTrue(site["TITLE"].startswith("Bio kontejner"))
        self.assertTrue(nearby["TITLE"].startswith("Bio kontejnery pro lokalitu"))
        self.assertEqual(
            "Bio kontejnery pro lokalitu Unčovice",
            nearby["H1"],
        )
        self.assertNotIn("Svoz bioodpadu", site["TITLE"])
        self.assertNotIn("Svoz bioodpadu", nearby["TITLE"])

    def test_supporting_page_metadata_targets_distinct_search_intents(self):
        builder = MetaBuilder(meta_config)
        guide = builder.garden_waste_guide()
        yard = builder.collection_yard()

        self.assertIn("Kam s trávou, větvemi a ovocem", guide["TITLE"])
        self.assertIn("spadaným ovocem", guide["H1"])
        self.assertEqual(
            "https://svoz.litovle.cz/kam-se-zahradnim-odpadem-litovel/",
            guide["CANONICAL"],
        )
        self.assertIn("Sběrný dvůr Litovel", yard["TITLE"])
        self.assertEqual(
            "https://svoz.litovle.cz/sberny-dvur-litovel/",
            yard["CANONICAL"],
        )

    def test_garden_guide_is_action_oriented_and_keeps_branches_out_of_container(self):
        disposal = load_bio_disposal_release(BIO_DISPOSAL_RELEASE_PATH)
        html = build_garden_waste_guide_html(disposal)

        self.assertNotIn("Rychlé odpovědi", html)
        self.assertIn('id="trava"', html)
        self.assertIn('id="spadane-ovoce"', html)
        self.assertIn('id="vetve"', html)
        self.assertIn('id="co-nepatri"', html)
        self.assertIn("Větve a dřevní odpad", html)
        self.assertIn('href="/"', html)
        self.assertIn('href="/bio/"', html)
        self.assertIn('href="/sberny-dvur-litovel/"', html)

    def test_collection_yard_page_uses_precise_location_without_hours(self):
        disposal = load_bio_disposal_release(BIO_DISPOSAL_RELEASE_PATH)
        html = build_collection_yard_html(disposal)

        yard_sources = [
            source for source in disposal.sources
            if source["id"] in disposal.collection_yard["source_ids"]
        ]
        self.assertTrue(yard_sources)
        self.assertTrue(all("litovel.eu" in source["url"] for source in yard_sources))
        self.assertNotIn("hanovice.cz", html)
        self.assertIn("openstreetmap.org/export/embed.html", html)
        self.assertIn("marker=49.6861253%2C17.0508742", html)
        self.assertNotIn("49.6861253 N, 17.0508742 E", html)
        self.assertIn("Na výjezdu z Nasobůrek směrem na Haňovice", html)
        self.assertIn("Otevřít v mapě", html)
        self.assertIn("Provozní doba se může o svátcích", html)
        self.assertNotIn("Pondělí", html)

    def test_bio_collection_structured_data_lists_all_sites(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        markup = build_bio_collection_jsonld(schedule)
        payload = markup.split("\n", 1)[1].rsplit("\n", 1)[0]
        data = json.loads(payload)

        self.assertEqual("CollectionPage", data["@type"])
        self.assertEqual(22, data["mainEntity"]["numberOfItems"])
        self.assertEqual(22, len(data["mainEntity"]["itemListElement"]))
        self.assertIn("Svoz bioodpadu Litovel", data["name"])

    def test_routes_are_unique_and_search_items_use_permanent_paths(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        streets = all_streets["Litovel"] + mistni_casti
        config = load_proximity_config(streets, schedule.sites)

        validate_bio_routes(schedule, streets)
        items = build_bio_search_items(schedule, streets, config)

        self.assertEqual(116, len(items))
        self.assertEqual(len(items), len({item["url"] for item in items}))
        self.assertTrue(all("?" not in item["url"] for item in items))
        self.assertIn(
            "/bio/stanoviste/litovel-sochova/",
            {item["url"] for item in items},
        )
        self.assertIn(
            "/bio/pobliz/b-nemcove/",
            {item["url"] for item in items},
        )

    def test_site_detail_answers_current_and_next_placement(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        site = next(item for item in schedule.sites if item.id == "litovel-sochova")
        placements = [item for item in schedule.placements if item.site == site]

        current = build_bio_site_detail(
            site, placements, schedule.sources, date(2026, 8, 22)
        )
        upcoming = build_bio_site_detail(
            site, placements, schedule.sources, date(2026, 8, 25)
        )

        self.assertIn("Kontejner je právě přistaven", current)
        self.assertIn("K dispozici do 24. 8. 2026", current)
        self.assertIn("Kontejner zde nyní není", upcoming)
        self.assertIn("18. 9.–21. 9. 2026", upcoming)
        self.assertIn("Kalendář svozů bio odpadů 2026", current)

    def test_site_detail_formats_schedule_as_aligned_date_ranges(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        site = next(
            item for item in schedule.sites
            if item.id == "uncovice-u-hasicarny"
        )
        placements = [item for item in schedule.placements if item.site == site]

        html = build_bio_site_detail(
            site, placements, schedule.sources, date(2026, 8, 22)
        )

        self.assertIn('<ol class="bio-detail-dates ui-data-list">', html)
        self.assertIn('datetime="2026-03-13">13.&nbsp;3.</time>', html)
        self.assertIn('class="bio-date-separator" aria-hidden="true">–</span>', html)
        self.assertIn('datetime="2026-03-16">16.&nbsp;3.&nbsp;2026</time>', html)

    def test_nearby_cards_link_to_permanent_site_pages(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        streets = all_streets["Litovel"] + mistni_casti
        config = load_proximity_config(streets, schedule.sites)

        html = build_nearby_bio_html(
            "B. Němcové", schedule, config, date(2026, 8, 22), focused=True
        )

        self.assertIn('/bio/stanoviste/litovel-javoricska/', html)
        self.assertIn('aria-label="Bio kontejnery poblíž"', html)
        self.assertIn(
            '>Zobrazit termíny pravidelného svozu bioodpadu pro B. Němcové</a>',
            html,
        )
        self.assertIn('href="/ulice/b-nemcove/"', html)
        self.assertNotIn("?site=", html)

    def test_expired_nearby_page_shows_sites_without_reusing_old_dates(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        streets = all_streets["Litovel"] + mistni_casti
        config = load_proximity_config(streets, schedule.sites)

        html = build_nearby_bio_html(
            "B. Němcové", schedule, config, date(2027, 1, 1), focused=True
        )

        self.assertEqual(3, html.count('class="nearby-bio-card"'))
        self.assertIn("Nejbližší známá stanoviště", html)
        self.assertIn("Nový termín zatím není zveřejněn", html)
        self.assertNotIn("Nadcházející", html)
        self.assertNotIn("2026</span>", html)
        self.assertIn('href="/">v kalendáři podle ulice</a>', html)
        self.assertIn("Zobrazit termíny pravidelného svozu bioodpadu", html)

    def test_uncovice_page_separates_available_now_from_local_upcoming_sites(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        streets = all_streets["Litovel"] + mistni_casti
        config = load_proximity_config(streets, schedule.sites)

        html = build_nearby_bio_html(
            "Unčovice", schedule, config, date(2026, 8, 23), focused=True
        )

        current_group, upcoming_group = html.split(
            "<h3>Další přistavení v okolí</h3>", 1
        )
        self.assertIn("<h3>Kam lze bioodpad odvézt nyní</h3>", current_group)
        self.assertIn("ul. Šargounská", current_group)
        self.assertIn("Unčovice – u hasičárny", upcoming_group)
        self.assertIn("Unčovice – před Selikem", upcoming_group)
        self.assertIn(
            "Přistavení: 28. 8. 2026, odvoz: 31. 8. 2026",
            upcoming_group,
        )
        self.assertIn("Odvoz: pondělí 24. 8. 2026", current_group)
        self.assertIn("nearby-bio-marker-upcoming", upcoming_group)
        self.assertIn("nearby-bio-marker-current", current_group)
        self.assertNotIn("Právě přistaveno", html)
        self.assertNotIn("Nadcházející", html)

    def test_compact_nearby_section_fills_three_slots_when_nothing_is_current(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        streets = all_streets["Litovel"] + mistni_casti
        config = load_proximity_config(streets, schedule.sites)

        html = build_nearby_bio_html(
            "Čs. armády", schedule, config, date(2026, 8, 25)
        )

        self.assertEqual(3, html.count('class="nearby-bio-card"'))
        self.assertNotIn("Kam lze bioodpad odvézt nyní", html)
        self.assertIn("Další přistavení v okolí", html)
        self.assertIn("Žádný velkoobjemový kontejner právě není přistaven", html)
        self.assertIn("hnědé popelnice", html)
        self.assertIn("Termíny jejího svozu vidíte v kalendáři výše.", html)
        self.assertNotIn('href="/">v kalendáři podle ulice</a>', html)
        self.assertIn("Větší množství bioodpadu můžete odevzdat", html)
        self.assertIn("ve sběrném dvoře", html)
        self.assertIn('href="/sberny-dvur-litovel/"', html)

    def test_collection_yard_note_is_hidden_when_a_container_is_available(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        streets = all_streets["Litovel"] + mistni_casti
        config = load_proximity_config(streets, schedule.sites)

        html = build_nearby_bio_html(
            "Čs. armády", schedule, config, date(2026, 8, 23)
        )

        self.assertNotIn("sběrném dvoře", html)

    def test_overview_groups_sites_by_current_and_next_window(self):
        schedule = load_bio_schedule(BIO_2026_PATH)
        overview = build_bio_overview(schedule, date(2026, 8, 22))

        self.assertIn("ul. Sochova", overview["current"])
        self.assertIn("21. 8.–24. 8. 2026", overview["current"])
        self.assertIn("Unčovice – u hasičárny", overview["next"])
        self.assertIn("28. 8.–31. 8. 2026", overview["next"])
        self.assertNotIn("bio-window-status", overview["current"])
        self.assertNotIn("bio-window-status", overview["next"])
        self.assertIn("<details", overview["schedule"])
        self.assertIn(
            "Roční harmonogram 2026",
            overview["schedule"],
        )
        self.assertEqual(1, overview["schedule"].count("21. 8.–24. 8. 2026"))
        self.assertNotIn('class="bio-placement"', overview["schedule"])

    def test_empty_overview_links_to_collection_yard(self):
        schedule = load_bio_schedule(BIO_2026_PATH)

        overview = build_bio_overview(schedule, date(2026, 8, 25))

        self.assertIn(
            "Žádný velkoobjemový kontejner právě není přistaven",
            overview["current"],
        )
        self.assertIn("hnědé popelnice", overview["current"])
        self.assertIn('href="/">v kalendáři podle ulice</a>', overview["current"])
        self.assertIn("Větší množství bioodpadu můžete odevzdat", overview["current"])
        self.assertIn("ve sběrném dvoře", overview["current"])
        self.assertIn('href="/sberny-dvur-litovel/"', overview["current"])

    def test_street_fallback_only_lists_active_year(self):
        events = [
            CollectionEvent(datetime(2025, 9, 3), WasteType.BIO, False),
            CollectionEvent(datetime(2026, 9, 2), WasteType.BIO, False),
        ]
        generator = SimpleNamespace(get_events_for_street=lambda street: events)

        html = build_fallback_table(generator, "Palackého", 2026)

        self.assertIn("Termíny svozu odpadu – Palackého, 2026", html)
        self.assertIn("02.09.2026", html)
        self.assertNotIn("03.09.2025", html)

    def test_search_discovery_files_are_stable_and_do_not_fake_lastmod(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sitemap_path = Path(tmpdir) / "sitemap.xml"
            robots_path = Path(tmpdir) / "robots.txt"
            generate_sitemap(["Palackého"], sitemap_path)
            generate_robots_txt(robots_path)

            sitemap = sitemap_path.read_text(encoding="utf-8")
            robots = robots_path.read_text(encoding="utf-8")

        self.assertIn("https://svoz.litovle.cz/bio/", sitemap)
        self.assertIn(
            "https://svoz.litovle.cz/kam-se-zahradnim-odpadem-litovel/",
            sitemap,
        )
        self.assertIn("https://svoz.litovle.cz/sberny-dvur-litovel/", sitemap)
        self.assertIn("https://svoz.litovle.cz/ulice/palackeho/", sitemap)
        self.assertNotIn("<lastmod>", sitemap)
        self.assertEqual(
            "User-agent: *\nAllow: /\n\n"
            "Sitemap: https://svoz.litovle.cz/sitemap.xml\n",
            robots,
        )


class SocialPreviewTest(unittest.TestCase):
    def test_card_path_stays_stable_and_version_tracks_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            card_dir = Path(tmpdir)
            with patch("social_preview.CARD_DIR", card_dir):
                first = _save_card(Image.new("RGB", (10, 10), "white"), "home", "Preview")
                unchanged = _save_card(Image.new("RGB", (10, 10), "white"), "home", "Preview")
                changed = _save_card(Image.new("RGB", (10, 10), "black"), "home", "Preview")

            self.assertEqual(first.url, unchanged.url)
            self.assertNotEqual(first.url, changed.url)
            self.assertIn("/home.png?v=", first.url)
            self.assertEqual(first.url.split("?")[0], changed.url.split("?")[0])
            self.assertEqual([card_dir / "home.png"], list(card_dir.iterdir()))


class CollectionChangesFeedTest(unittest.TestCase):
    def test_public_records_have_explicit_actions_and_no_internal_notes(self):
        original = load_svoz_exceptions()[0]
        for action in ("reschedule", "include", "cancel"):
            item = replace(original, action=action, date=date(2026, 12, 24))
            record = change_record(item)
            self.assertEqual(action, record["action"])
            self.assertTrue(record["street_slugs"])
            self.assertNotIn("internal_note", record)
            self.assertNotIn("note", record["source"])
            self.assertEqual(action == "reschedule", "original_date" in record)
            self.assertEqual(action != "reschedule", "date" in record)

    def test_semantic_revision_ignores_sources_and_membership_but_tracks_dates(self):
        original = load_svoz_exceptions()[0]
        changed_source = replace(original, source=SvozExceptionSource(title="New title", evidence="New text"))
        changed_membership = replace(original, affected_location_group=None, affected_locations=("Sochova",))
        changed_date = replace(original, new_date=date(2026, 12, 25))
        self.assertEqual(change_record(original)["revision"], change_record(changed_source)["revision"])
        self.assertEqual(change_record(original)["revision"], change_record(changed_membership)["revision"])
        self.assertNotEqual(change_record(original)["revision"], change_record(changed_date)["revision"])

    def test_feed_matches_canonical_calendars_and_public_exception_data(self):
        payload = load_collection_changes(Path("collection_changes.json"), Path("calendars"))
        self.assertEqual(len(all_streets["Litovel"] + mistni_casti), len(payload["calendars"]))
        self.assertEqual(len(load_svoz_exceptions()), len(payload["changes"]))
        self.assertEqual(payload["changes"], [change_record(item) for item in sorted(load_svoz_exceptions(), key=lambda item: item.id)])

    def test_feed_is_deterministic_and_calendar_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "calendars").mkdir()
            calendar = root / "calendars/sochova.ics"
            original = replace(load_svoz_exceptions()[0], affected_location_group=None, affected_locations=("Sochova",))
            sample = Calendar()
            sample.add("version", "2.0")
            event = Event()
            event.add("dtstart", original.new_date or original.date)
            event.add("summary", f"Změna: {WasteType[original.waste_type].label} svoz – Sochova")
            event.add("X-SVOZ-EXCEPTION-ID", original.id)
            sample.add_component(event)
            calendar.write_bytes(sample.to_ical())
            write_collection_changes(root, ["Sochova"], (original,))
            before = (root / "collection_changes.json").read_bytes()
            write_collection_changes(root, ["Sochova"], (original,))
            self.assertEqual(before, (root / "collection_changes.json").read_bytes())
            payload = load_collection_changes(root / "collection_changes.json", root / "calendars")
            self.assertEqual(hashlib.sha256(calendar.read_bytes()).hexdigest(), payload["calendars"]["sochova"])
            calendar.write_bytes(b"different calendar")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                load_collection_changes(root / "collection_changes.json", root / "calendars")

    def test_invalid_schema_unknown_streets_and_internal_fields_are_rejected(self):
        payload = json.loads(Path("collection_changes.json").read_text())
        for mutation in ("schema", "street", "internal"):
            candidate = json.loads(json.dumps(payload))
            if mutation == "schema": candidate["schema_version"] = 2
            elif mutation == "street": candidate["changes"][0]["street_slugs"] = ["unknown-street"]
            else: candidate["changes"][0]["internal_note"] = "private"
            candidate["revision"] = content_hash({k: v for k, v in candidate.items() if k != "revision"})
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "feed.json"
                path.write_text(json.dumps(candidate))
                with self.assertRaises(ValueError): load_collection_changes(path)

    def test_matching_hashes_do_not_hide_a_calendar_that_contradicts_a_change(self):
        original_day = date(2026, 12, 14)
        moved_day = date(2026, 12, 15)
        cases = (
            ("include", ()),
            ("include", ((moved_day, None),)),
            ("cancel", ((moved_day, None),)),
            ("reschedule", ((original_day, None), (moved_day, "test-change"))),
            ("reschedule", ()),
        )
        for action, events in cases:
            with self.subTest(action=action, events=events), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / "calendars").mkdir()
                change = replace(
                    load_svoz_exceptions()[0], id="test-change", action=action,
                    waste_type="SMES", affected_location_group=None, affected_locations=("Sochova",),
                    original_date=original_day if action == "reschedule" else None,
                    new_date=moved_day if action == "reschedule" else None,
                    date=moved_day if action != "reschedule" else None,
                )
                calendar = Calendar()
                calendar.add("version", "2.0")
                for day, exception_id in events:
                    event = Event()
                    event.add("dtstart", day)
                    event.add("summary", "Směsný odpad svoz – Sochova")
                    if exception_id:
                        event.add("X-SVOZ-EXCEPTION-ID", exception_id)
                    calendar.add_component(event)
                encoded = calendar.to_ical()
                (root / "calendars/sochova.ics").write_bytes(encoded)
                payload = {
                    "schema_version": 1,
                    "calendars": {"sochova": hashlib.sha256(encoded).hexdigest()},
                    "changes": [change_record(change)],
                }
                payload["revision"] = content_hash(payload)
                (root / "collection_changes.json").write_text(json.dumps(payload))
                with self.assertRaisesRegex(ValueError, "test-change contradicts calendar sochova"):
                    load_collection_changes(root / "collection_changes.json", root / "calendars")
                with self.assertRaisesRegex(ValueError, "test-change contradicts calendar sochova"):
                    write_collection_changes(root, ["Sochova"], (change,))


class ScheduleExceptionsTest(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 12, 1)
        self.end = datetime(2027, 1, 1)
        self.original = datetime(2026, 12, 14)
        self.moved = datetime(2026, 12, 15)
        self.regular = {
            street: [CollectionEvent(self.original, WasteType.SMES)]
            for street in ("A", "B", "C")
        }
        self.regular["A"].append(CollectionEvent(self.original, WasteType.PAPIR))

    def exception(self, action="reschedule", streets=("A",), **overrides):
        fields = dict(
            id="test-change", action=action, waste_type="SMES",
            affected_locations=streets, affected_locations_snapshot=(),
            affected_location_group=None,
            original_date=self.original.date() if action == "reschedule" else None,
            new_date=self.moved.date() if action == "reschedule" else None,
            date=self.original.date() if action == "cancel" else self.moved.date() if action == "include" else None,
            source=SvozExceptionSource(), note=None,
        )
        return SvozException(**(fields | overrides))

    def apply(self, *exceptions):
        return apply_schedule_exceptions(self.regular, exceptions, self.start, self.end)

    def test_include_only_adds_to_selected_street_and_preserves_input(self):
        change = self.exception("include")
        corrected, applied = self.apply(change)
        self.assertEqual((change,), applied)
        self.assertEqual(CollectionEvent(self.moved, WasteType.SMES, True), corrected["A"][-1])
        self.assertIs(change, corrected["A"][-1].exception)
        self.assertEqual(self.regular["B"], corrected["B"])
        self.assertEqual(self.regular["C"], corrected["C"])
        self.assertEqual(2, len(self.regular["A"]))
        self.assertTrue(all(not event.is_override for events in self.regular.values() for event in events))

    def test_cancel_subset_keeps_other_streets_and_waste_types(self):
        corrected, _ = self.apply(self.exception("cancel", ("A", "C")))
        self.assertEqual([CollectionEvent(self.original, WasteType.PAPIR)], corrected["A"])
        self.assertEqual(self.regular["B"], corrected["B"])
        self.assertEqual([], corrected["C"])

    def test_reschedule_subset_keeps_other_streets_and_waste_types(self):
        change = self.exception(streets=("A", "C"))
        corrected, _ = self.apply(change)
        self.assertEqual([self.original, self.moved], [item.date for item in corrected["A"]])
        self.assertEqual(WasteType.PAPIR, corrected["A"][0].waste_type)
        self.assertEqual([self.moved], [item.date for item in corrected["C"]])
        self.assertEqual(self.regular["B"], corrected["B"])

    def test_named_group_can_span_multiple_regular_rules(self):
        streets = ["Savín", "Nová Ves", "Chudobín", "Tři Dvory"]
        rules = [LokaceSvozu(lambda day: day == self.original, names, WasteType.SMES)
                 for names in (streets[:2], streets[2:])]
        change = self.exception(streets=(), affected_location_group="smes_streda_mistni_casti")
        generator = calendar_generator.WasteCollectionCalendarGenerator(
            rules, [], [], [], streets, self.start, self.end, exceptions=(change,),
        )
        for street in streets:
            with self.subTest(street=street):
                events = generator.get_events_for_street(street)
                self.assertEqual([self.moved], [item.date for item in events])
                self.assertIs(change, events[0].exception)

    def test_half_open_range_handles_moves_across_both_boundaries(self):
        entering = self.exception(original_date=date(2026, 11, 30), new_date=self.start.date())
        leaving = self.exception(id="leaving", streets=("C",), new_date=self.end.date())
        outside = self.exception("include", id="outside", date=self.end.date())
        corrected, applied = self.apply(outside, leaving, entering)
        self.assertEqual([self.start, self.original, self.original], [item.date for item in corrected["A"]])
        self.assertEqual([], corrected["C"])
        self.assertEqual({entering.id, leaving.id}, {item.id for item in applied})
        self.assertTrue(all(self.start <= item.date < self.end for events in corrected.values() for item in events))

    def test_independent_changes_are_order_independent(self):
        include = self.exception("include", id="added")
        cancel = self.exception("cancel", ("B",), id="removed")
        self.assertEqual(self.apply(include, cancel), self.apply(cancel, include))

    def test_overlapping_changes_fail_with_both_ids_before_mutating_input(self):
        first = self.exception("include", id="first")
        second = self.exception("cancel", id="second", date=self.moved.date())
        with self.assertRaisesRegex(ValueError, "first and second: A, SMES, 2026-12-15"):
            self.apply(second, first)
        self.assertEqual(2, len(self.regular["A"]))
        self.assertTrue(all(not event.is_override for events in self.regular.values() for event in events))

    def test_shared_original_date_is_checked_outside_the_export_range(self):
        cases = (
            (date(2026, 11, 30), self.moved.date(), date(2026, 12, 16)),
            (date(2027, 1, 2), self.moved.date(), date(2026, 12, 16)),
            (date(2026, 11, 28), date(2026, 11, 29), date(2026, 11, 30)),
        )
        for original, first_day, second_day in cases:
            with self.subTest(original=original, first=first_day, second=second_day):
                first = self.exception(id="first", original_date=original, new_date=first_day)
                second = replace(first, id="second", new_date=second_day)
                with self.assertRaisesRegex(ValueError, f"first and second: A, SMES, {original}"):
                    self.apply(first, second)

    def test_shared_destination_is_checked_outside_the_export_range(self):
        self.regular["A"].append(CollectionEvent(self.moved, WasteType.SMES))
        first = self.exception(id="first", new_date=self.end.date())
        second = replace(first, id="second", original_date=self.moved.date())
        with self.assertRaisesRegex(ValueError, "first and second: A, SMES, 2027-01-01"):
            self.apply(first, second)

    def test_unknown_street_is_rejected_even_when_the_change_is_outside_range(self):
        for day in (date(2026, 11, 30), self.end.date()):
            with self.subTest(day=day):
                with self.assertRaisesRegex(ValueError, "unknown.*Missing"):
                    self.apply(self.exception("include", streets=("Missing",), date=day))

    def test_disjoint_streets_can_split_a_collection_from_outside_the_range(self):
        first = self.exception(id="first", original_date=date(2026, 11, 30), new_date=self.start.date())
        second = replace(first, id="second", affected_locations=("B",), new_date=self.moved.date())
        corrected, applied = apply_schedule_exceptions(
            {"A": [], "B": []}, (first, second), self.start, self.end,
        )
        self.assertEqual([self.start], [item.date for item in corrected["A"]])
        self.assertEqual([self.moved], [item.date for item in corrected["B"]])
        self.assertEqual((first, second), applied)

    def test_release_rejects_conflicting_boundary_moves_before_writing_exports(self):
        exceptions = load_svoz_exceptions()
        original = next(item for item in exceptions
                        if item.id == "2024-12-30-bio-mistni-casti-posun-2025-01-02")
        conflict = replace(original, id="conflicting-boundary-move", new_date=date(2025, 1, 3))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(ValueError, "Conflicting collection exceptions.*2024-12-30"):
                generate_release_data(root, exceptions=exceptions + (conflict,))
            self.assertEqual([], list(root.iterdir()))

    def test_duplicate_identity_and_unknown_street_fail(self):
        change = self.exception("include")
        with self.assertRaisesRegex(ValueError, "Duplicate collection exception ID"):
            self.apply(change, replace(change, affected_locations=("B",)))
        with self.assertRaisesRegex(ValueError, "unknown.*Missing"):
            self.apply(self.exception(streets=("Missing",)))

    def test_group_and_explicit_street_overlap_is_rejected(self):
        streets = {name: [] for name in ("Savín", "Nová Ves", "Chudobín", "Tři Dvory")}
        group = self.exception("include", id="group", streets=(), affected_location_group="smes_streda_mistni_casti")
        local = self.exception("include", id="local", streets=("Savín",))
        with self.assertRaisesRegex(ValueError, "group and local: Savín"):
            apply_schedule_exceptions(streets, (group, local), self.start, self.end)

    def test_single_street_exception_reaches_csv_ics_and_feed(self):
        change = self.exception("include", streets=("Sochova",))
        streets = all_streets["Litovel"] + mistni_casti
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            generate_release_data(root, exceptions=())
            before = {path.name: path.read_bytes() for path in (root / "calendars").glob("*.ics")}
            baseline = load_waste_schedule(root / "waste_schedule.csv", streets)
            self.assertFalse(any(item.date == self.moved and item.waste_type == WasteType.SMES
                                 for item in baseline.get_events_for_street("Sochova")))
            generate_release_data(root, exceptions=(change,))
            updated = load_waste_schedule(root / "waste_schedule.csv", streets)
            matches = [item for item in updated.get_events_for_street("Sochova")
                       if item.date == self.moved and item.waste_type == WasteType.SMES]
            self.assertEqual(1, len(matches))
            self.assertTrue(matches[0].is_override)
            for path in (root / "calendars").glob("*.ics"):
                with self.subTest(calendar=path.name):
                    if path.name != "sochova.ics":
                        self.assertEqual(before[path.name], path.read_bytes())
            calendar = Calendar.from_ical((root / "calendars/sochova.ics").read_bytes())
            event = next(item for item in calendar.walk("VEVENT")
                         if str(item.get("X-SVOZ-EXCEPTION-ID", "")) == change.id)
            self.assertEqual(self.moved.date(), event.decoded("DTSTART"))
            feed = load_collection_changes(root / "collection_changes.json", root / "calendars")
            self.assertEqual([change_record(change)], feed["changes"])

    def test_all_actions_and_target_scopes_agree_across_exports(self):
        streets = ["Sochova", "Jiráskova", "Savín", "Nová Ves", "Chudobín", "Tři Dvory"]
        routes = [streets[:2], streets[2:4], streets[4:]]
        scopes = (
            ("single", {"affected_locations": streets[:1]}, streets[:1]),
            ("subset-across-routes", {"affected_locations": [streets[0], streets[2]]}, [streets[0], streets[2]]),
            ("whole-route", {"affected_locations": streets[:2]}, streets[:2]),
            ("explicit-group", {"affected_locations": streets[2:]}, streets[2:]),
            ("named-group", {
                "affected_location_group": "smes_streda_mistni_casti",
                "affected_locations_snapshot": ["Sochova"],
            }, streets[2:]),
        )
        for waste_type, action in product(WasteType, ("include", "cancel", "reschedule")):
            control = WasteType.PAPIR if waste_type != WasteType.PAPIR else WasteType.PLAST
            rules = {
                waste_type: [LokaceSvozu(lambda day: day == self.original, route, waste_type)
                             for route in routes],
                control: [LokaceSvozu(lambda day: day == self.original, streets, control)],
            }
            for label, target, selected in scopes:
                with self.subTest(waste=waste_type.name, action=action, scope=label), tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    dates = (
                        {"original_date": self.original.date().isoformat(), "new_date": self.moved.date().isoformat()}
                        if action == "reschedule" else
                        {"date": (self.moved if action == "include" else self.original).date().isoformat()}
                    )
                    record = {
                        "id": f"test-{action}-{label}", "action": action, "waste_type": waste_type.name,
                        **target, **dates, "source": {"title": "Zkušební změna"},
                    }
                    source = root / "exceptions.json"
                    source.write_text(json.dumps([record]), encoding="utf-8")
                    exceptions = load_svoz_exceptions(source)
                    self.assertEqual(set(selected), set(exceptions[0].resolved_locations))
                    self.assertEqual(set(selected), set(affected_location_names(exceptions[0])))
                    generator = calendar_generator.WasteCollectionCalendarGenerator(
                        rules.get(WasteType.SMES, []), rules.get(WasteType.PLAST, []),
                        rules.get(WasteType.PAPIR, []), rules.get(WasteType.BIO, []),
                        streets, self.start, self.end, exceptions=exceptions,
                    )
                    generator.generate_csv_file(streets, self.start, self.end, root / "waste_schedule.csv")
                    released = load_waste_schedule(root / "waste_schedule.csv", streets)
                    for street in streets:
                        expected = {(self.original, control)}
                        if street not in selected or action == "include":
                            expected.add((self.original, waste_type))
                        if street in selected and action != "cancel":
                            expected.add((self.moved, waste_type))
                        self.assertEqual(expected, {(item.date, item.waste_type)
                                                    for item in released.get_events_for_street(street)})
                        generator.generate_ical_file(
                            street, root / "calendars", self.start, self.end, include_legacy_alias=False,
                        )
                        calendar = Calendar.from_ical((root / "calendars" / f"{slugify(street)}.ics").read_bytes())
                        self.assertEqual(
                            {(day.date(), f"{waste.label} svoz – {street}") for day, waste in expected},
                            {(event.decoded("DTSTART"), str(event["SUMMARY"]).removeprefix("Změna: "))
                             for event in calendar.walk("VEVENT")},
                        )
                    write_collection_changes(root, streets, generator.applied_exceptions)
                    feed = load_collection_changes(root / "collection_changes.json", root / "calendars")
                    self.assertEqual(1, len(feed["changes"]))
                    self.assertEqual(record["id"], feed["changes"][0]["id"])
                    self.assertEqual({slugify(street) for street in selected}, set(feed["changes"][0]["street_slugs"]))


class SvozExceptionsTest(unittest.TestCase):
    @contextmanager
    def _write_exception_file(self, data):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "svoz_exceptions.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            yield path

    def test_exception_file_loads(self):
        exceptions = load_svoz_exceptions(
            allowed_waste_types={waste_type.name for waste_type in WasteType}
        )

        self.assertGreater(len(exceptions), 0)
        self.assertTrue(all(exception.id for exception in exceptions))

    def test_invalid_exception_date_fails_clearly(self):
        invalid_data = [
            {
                "id": "invalid-date",
                "action": "reschedule",
                "waste_type": "SMES",
                "affected_locations": ["Dukelská"],
                "original_date": "2026-02-31",
                "new_date": "2026-03-01",
                "source": {"url": None, "title": None},
            }
        ]

        with self._write_exception_file(invalid_data) as path:
            with self.assertRaisesRegex(ValueError, "valid ISO date"):
                load_svoz_exceptions(path)

    def test_invalid_exception_combinations_fail_clearly(self):
        valid_base = {
            "id": "test-exception",
            "action": "reschedule",
            "waste_type": "SMES",
            "affected_locations": ["Dukelská"],
            "original_date": "2026-02-16",
            "new_date": "2026-02-17",
            "source": {"url": None, "title": None},
        }
        invalid_cases = [
            (
                "missing reschedule new_date",
                {**valid_base, "new_date": None},
                "new_date is required",
            ),
            (
                "include with reschedule date",
                {
                    **valid_base,
                    "action": "include",
                    "date": "2026-02-17",
                },
                "forbidden fields for include",
            ),
            (
                "cancel with reschedule dates",
                {
                    "id": "cancel-action",
                    "action": "cancel",
                    "waste_type": "SMES",
                    "affected_locations": ["Dukelská"],
                    "date": "2026-02-17",
                    "original_date": "2026-02-16",
                    "source": {"url": None, "title": None},
                },
                "forbidden fields for cancel",
            ),
            (
                "missing target",
                {
                    "id": "missing-target",
                    "action": "include",
                    "waste_type": "SMES",
                    "date": "2026-02-17",
                    "source": {"url": None, "title": None},
                },
                "affected_locations or affected_location_group is required",
            ),
            (
                "affected locations with group",
                {
                    "id": "locations-with-group",
                    "action": "include",
                    "waste_type": "SMES",
                    "affected_location_group": "smes_streda_mistni_casti",
                    "affected_locations": ["Dukelská"],
                    "date": "2026-02-17",
                    "source": {"url": None, "title": None},
                },
                "affected_locations cannot be used with affected_location_group",
            ),
            (
                "snapshot without group",
                {
                    "id": "snapshot-without-group",
                    "action": "include",
                    "waste_type": "SMES",
                    "affected_locations": ["Dukelská"],
                    "affected_locations_snapshot": ["Dukelská"],
                    "date": "2026-02-17",
                    "source": {"url": None, "title": None},
                },
                "affected_locations_snapshot requires affected_location_group",
            ),
            (
                "unknown group",
                {
                    "id": "unknown-group",
                    "action": "include",
                    "waste_type": "SMES",
                    "affected_location_group": "does_not_exist",
                    "date": "2026-02-17",
                    "source": {"url": None, "title": None},
                },
                "unknown affected_location_group",
            ),
            (
                "missing source",
                {
                    "id": "missing-source",
                    "action": "include",
                    "waste_type": "SMES",
                    "affected_locations": ["Dukelská"],
                    "date": "2026-02-17",
                },
                "source is required",
            ),
            (
                "old flat source field",
                {
                    **valid_base,
                    "source_url": "https://www.litovel.eu/",
                },
                "unknown fields",
            ),
            (
                "URL embedded in prose note",
                {
                    **valid_base,
                    "note": "Archiv: https://archive.example/test",
                },
                "must not contain URLs",
            ),
            (
                "invalid archive URL",
                {
                    **valid_base,
                    "source": {
                        "archive_urls": ["archive.example/test"],
                    },
                },
                r"absolute HTTP\(S\) URLs",
            ),
            (
                "invalid source URL",
                {
                    **valid_base,
                    "source": {"url": "litovel.eu/oznameni"},
                },
                r"absolute HTTP\(S\) URLs",
            ),
            (
                "duplicate archive URL",
                {
                    **valid_base,
                    "source": {
                        "archive_urls": [
                            "https://archive.example/test",
                            "https://archive.example/test",
                        ],
                    },
                },
                "must not contain duplicate URLs",
            ),
        ]

        for label, data, message in invalid_cases:
            with self.subTest(label=label):
                with self._write_exception_file([data]) as path:
                    with self.assertRaisesRegex(ValueError, message):
                        load_svoz_exceptions(path)

    def test_group_snapshot_and_source_evidence_load(self):
        data = [
            {
                "id": "group-snapshot",
                "action": "include",
                "waste_type": "SMES",
                "affected_location_group": "smes_streda_mistni_casti",
                "affected_locations_snapshot": ["Dukelská"],
                "date": "2026-02-17",
                "source": {
                    "url": None,
                    "title": None,
                    "evidence": "Test evidence",
                },
            }
        ]

        with self._write_exception_file(data) as path:
            exceptions = load_svoz_exceptions(path)

        self.assertEqual("include", exceptions[0].action)
        self.assertEqual(("Dukelská",), exceptions[0].affected_locations_snapshot)
        self.assertEqual("Test evidence", exceptions[0].source.evidence)

    def test_source_metadata_fields_are_optional_and_archives_load(self):
        data = [
            {
                "id": "optional-source-fields",
                "action": "include",
                "waste_type": "SMES",
                "affected_locations": ["Dukelská"],
                "date": "2026-02-17",
                "internal_note": "Interní migrační poznámka",
                "source": {
                    "note": "Poznámka ke zdroji",
                    "archive_urls": [
                        "https://archive.example/one",
                        "https://archive.example/two",
                    ],
                },
            }
        ]

        with self._write_exception_file(data) as path:
            exception = load_svoz_exceptions(path)[0]

        self.assertIsNone(exception.source.url)
        self.assertIsNone(exception.source.title)
        self.assertIsNone(exception.source.evidence)
        self.assertEqual("Poznámka ke zdroji", exception.source.note)
        self.assertEqual("Interní migrační poznámka", exception.internal_note)
        self.assertEqual(
            (
                "https://archive.example/one",
                "https://archive.example/two",
            ),
            exception.source.archive_urls,
        )

    def test_cancel_exception_loads(self):
        data = [
            {
                "id": "cancel-date",
                "action": "cancel",
                "waste_type": "SMES",
                "affected_locations": ["Dukelská"],
                "date": "2026-02-17",
                "source": {"url": None, "title": None},
            }
        ]

        with self._write_exception_file(data) as path:
            exceptions = load_svoz_exceptions(path)

        self.assertEqual("cancel", exceptions[0].action)
        self.assertEqual("2026-02-17", exceptions[0].date.isoformat())

    def test_waste_type_validation_matches_enum(self):
        self.assertEqual(
            {waste_type.name for waste_type in WasteType},
            {"SMES", "PLAST", "PAPIR", "BIO"},
        )

    def test_july_bio_collection_moves_to_friday_for_thursday_group(self):
        streets = all_streets["Litovel"] + mistni_casti
        generator = calendar_generator.WasteCollectionCalendarGenerator(
            lokace_svozu_smes,
            lokace_svozu_plast,
            lokace_svozu_papir,
            lokace_svozu_bio,
            streets,
            date_start,
            date_end,
            exceptions=load_svoz_exceptions(),
        )

        for street in litovel_lokace_bio_0:
            bio_events = {
                event.date.strftime("%Y-%m-%d"): event
                for event in generator.get_events_for_street(street)
                if event.waste_type == WasteType.BIO
            }
            self.assertNotIn("2026-07-09", bio_events)
            self.assertTrue(bio_events["2026-07-10"].is_override)

        unaffected_bio_dates = {
            event.date.strftime("%Y-%m-%d")
            for event in generator.get_events_for_street("1. máje")
            if event.waste_type == WasteType.BIO
        }
        self.assertIn("2026-07-08", unaffected_bio_dates)
        self.assertNotIn("2026-07-10", unaffected_bio_dates)

    def test_generated_schedule_matches_checked_in_csv(self):
        streets = all_streets["Litovel"] + mistni_casti
        generator = calendar_generator.WasteCollectionCalendarGenerator(
            lokace_svozu_smes,
            lokace_svozu_plast,
            lokace_svozu_papir,
            lokace_svozu_bio,
            streets,
            date_start,
            date_end,
            exceptions=load_svoz_exceptions(),
        )

        actual_lines = []
        for street in streets:
            for event in generator.get_events_for_street(street):
                date_string = event.date.strftime("%Y-%m-%d")
                actual_lines.append(
                    f"{date_string},{event.waste_type.key},{street},{int(event.is_override)}"
                )

        expected_lines = Path("waste_schedule.csv").read_text(encoding="utf-8").splitlines()

        self.assertEqual(expected_lines, actual_lines)

    def test_checked_in_csv_round_trips_to_collection_events(self):
        streets = all_streets["Litovel"] + mistni_casti
        released = load_waste_schedule("waste_schedule.csv", streets)
        generated = calendar_generator.WasteCollectionCalendarGenerator(
            lokace_svozu_smes,
            lokace_svozu_plast,
            lokace_svozu_papir,
            lokace_svozu_bio,
            streets,
            date_start,
            date_end,
            exceptions=load_svoz_exceptions(),
        )

        for street in streets:
            self.assertEqual(
                generated.get_events_for_street(street),
                released.get_events_for_street(street),
            )


class IcsExceptionMetadataTest(unittest.TestCase):
    def _calendar_events(self, generator, street):
        with tempfile.TemporaryDirectory() as tmpdir:
            generator.generate_ical_file(
                street,
                tmpdir,
                datetime(2026, 1, 1),
                datetime(2027, 1, 1),
                include_legacy_alias=False,
            )
            raw = (Path(tmpdir) / f"{calendar_generator.slugify(street)}.ics").read_bytes()

        parsed = Calendar.from_ical(raw)
        return raw, parsed.walk("VEVENT")

    def _generator_with_exception(self, exception, street="Zkušební ulice"):
        resulting_date = exception.new_date or exception.date
        self.assertIsNotNone(resulting_date)
        schedule = LokaceSvozu(
            lambda value: False,
            [street],
            WasteType.SMES,
        )
        return calendar_generator.WasteCollectionCalendarGenerator(
            [schedule], [], [], [], [street], datetime(2026, 1, 1), datetime(2027, 1, 1),
            exceptions=(exception,),
        )

    def test_sochova_reschedules_include_complete_exception_metadata(self):
        streets = all_streets["Litovel"] + mistni_casti
        generator = calendar_generator.WasteCollectionCalendarGenerator(
            lokace_svozu_smes,
            lokace_svozu_plast,
            lokace_svozu_papir,
            lokace_svozu_bio,
            streets,
            date_start,
            date_end,
            exceptions=load_svoz_exceptions(),
        )
        _, events = self._calendar_events(generator, "Sochova")
        by_date = {event.decoded("dtstart"): event for event in events}

        expected = {
            date(2026, 9, 25): {
                "id": "2026-09-28-smes-litovel-pondeli-posun-2026-09-25",
                "evidence": "Svoz komunálního odpadu ve městě Litovel (dle harmonogramu) se přesouvá z pondělí 28. září na pátek 25. září.",
                "new_date_text": "25. 9. 2026",
            },
            date(2026, 10, 1): {
                "id": "2026-09-28-papir-litovel-posun-2026-10-01",
                "evidence": "Svoz papíru (240 l) ve městě Litovel se přesouvá z pondělí 28. září na čtvrtek 1. října.",
                "new_date_text": "1. 10. 2026",
            },
        }
        source_url = "https://www.litovel.eu/cs/urad/uredni-deska/aktualni-informace/zmena-svozu-odpadu-v-pondeli-28-zari.html"
        archive_urls = (
            "https://archive.is/DiJh3",
            "https://web.archive.org/web/20260921155639/https://www.litovel.eu/cs/urad/uredni-deska/aktualni-informace/zmena-svozu-odpadu-v-pondeli-28-zari.html",
        )

        for event_date, values in expected.items():
            with self.subTest(event_date=event_date):
                event = by_date[event_date]
                description = event.decoded("description")
                self.assertTrue(event.decoded("summary").startswith("Změna:"))
                self.assertEqual(values["id"], event.decoded("X-SVOZ-EXCEPTION-ID"))
                self.assertEqual("20260928", event.decoded("X-SVOZ-ORIGINAL-DATE"))
                self.assertEqual(
                    "DATE", event["X-SVOZ-ORIGINAL-DATE"].params["VALUE"]
                )
                self.assertEqual(
                    "https://svoz.litovle.cz/ulice/sochova/",
                    event.decoded("url"),
                )
                self.assertEqual(
                    source_url,
                    event.decoded("X-SVOZ-SOURCE-URL"),
                )
                self.assertEqual(
                    list(archive_urls),
                    event.decoded("X-SVOZ-ARCHIVE-URL"),
                )
                self.assertEqual(
                    "Změna svozu odpadů v pondělí 28. září",
                    event.decoded("X-SVOZ-SOURCE-TITLE"),
                )
                self.assertEqual(
                    values["evidence"],
                    event.decoded("X-SVOZ-CHANGE-MESSAGE"),
                )
                self.assertIn(
                    f"Termín přesunut z 28. 9. 2026 na {values['new_date_text']}.",
                    description,
                )
                self.assertIn(values["evidence"], description)
                self.assertNotIn(source_url, description)
                for archive_url in archive_urls:
                    self.assertNotIn(archive_url, description)
                self.assertNotIn("http://", description)
                self.assertNotIn("https://", description)

        self.assertNotIn(date(2026, 9, 28), by_date)

    def test_reschedule_without_source_metadata_omits_optional_properties(self):
        exception = SvozException(
            id="reschedule-without-source",
            action="reschedule",
            waste_type="SMES",
            affected_locations=("Zkušební ulice",),
            affected_locations_snapshot=(),
            affected_location_group=None,
            original_date=date(2026, 4, 6),
            new_date=date(2026, 4, 9),
            date=None,
            source=SvozExceptionSource(),
            note=None,
        )
        _, events = self._calendar_events(
            self._generator_with_exception(exception), "Zkušební ulice"
        )
        event = events[0]

        self.assertEqual("reschedule-without-source", event.decoded("X-SVOZ-EXCEPTION-ID"))
        self.assertEqual("20260406", event.decoded("X-SVOZ-ORIGINAL-DATE"))
        self.assertEqual(
            "https://svoz.litovle.cz/ulice/zkusebni-ulice/",
            event.decoded("url"),
        )
        self.assertNotIn("X-SVOZ-SOURCE-URL", event)
        self.assertNotIn("X-SVOZ-ARCHIVE-URL", event)
        self.assertNotIn("X-SVOZ-SOURCE-TITLE", event)
        self.assertNotIn("X-SVOZ-CHANGE-MESSAGE", event)
        self.assertIn(
            "Termín přesunut z 6. 4. 2026 na 9. 4. 2026.",
            event.decoded("description"),
        )

    def test_include_exception_has_metadata_without_original_date(self):
        streets = all_streets["Litovel"] + mistni_casti
        generator = calendar_generator.WasteCollectionCalendarGenerator(
            lokace_svozu_smes,
            lokace_svozu_plast,
            lokace_svozu_papir,
            lokace_svozu_bio,
            streets,
            date_start,
            date_end,
            exceptions=load_svoz_exceptions(),
        )
        _, events = self._calendar_events(generator, "Dukelská")
        event = next(
            item
            for item in events
            if item.decoded("dtstart") == date(2025, 9, 11)
            and "Směsný odpad" in item.decoded("summary")
        )

        self.assertEqual(
            "2025-09-11-smes-dukelska-mimoradny-svoz",
            event.decoded("X-SVOZ-EXCEPTION-ID"),
        )
        self.assertNotIn("X-SVOZ-ORIGINAL-DATE", event)
        self.assertEqual(
            "https://svoz.litovle.cz/ulice/dukelska/",
            event.decoded("url"),
        )
        self.assertEqual(
            "https://www.facebook.com/litovel.eu/posts/pfbid02af6wuEMQTm3G4xLmkpFG5b8YnTEH2Pk4wSw3oPgbBkovEmRqTb76cfzaDCDs15pFl",
            event.decoded("X-SVOZ-SOURCE-URL"),
        )
        self.assertNotIn("X-SVOZ-ARCHIVE-URL", event)
        self.assertNotIn("X-SVOZ-SOURCE-TITLE", event)
        self.assertNotIn("X-SVOZ-CHANGE-MESSAGE", event)
        self.assertIn(
            "Termín upraven oproti pravidelnému harmonogramu.",
            event.decoded("description"),
        )
        self.assertNotIn("Migrated from lokace_svozu.py", event.decoded("description"))
        self.assertNotIn(
            "https://www.facebook.com/litovel.eu/posts/pfbid02af6wuEMQTm3G4xLmkpFG5b8YnTEH2Pk4wSw3oPgbBkovEmRqTb76cfzaDCDs15pFl",
            event.decoded("description"),
        )

    def test_unaffected_event_has_no_change_metadata(self):
        street = "Zkušební ulice"
        collection_date = datetime(2026, 3, 2)
        schedule = LokaceSvozu(
            lambda value: value == collection_date,
            [street],
            WasteType.SMES,
        )
        generator = calendar_generator.WasteCollectionCalendarGenerator(
            [schedule], [], [], [], [street], datetime(2026, 1, 1), datetime(2027, 1, 1),
            exceptions=()
        )
        _, events = self._calendar_events(generator, street)
        event = events[0]

        self.assertFalse(event.decoded("summary").startswith("Změna:"))
        self.assertNotIn("X-SVOZ-EXCEPTION-ID", event)
        self.assertNotIn("X-SVOZ-ORIGINAL-DATE", event)
        self.assertNotIn("X-SVOZ-SOURCE-URL", event)
        self.assertNotIn("X-SVOZ-ARCHIVE-URL", event)
        self.assertNotIn("X-SVOZ-SOURCE-TITLE", event)
        self.assertNotIn("X-SVOZ-CHANGE-MESSAGE", event)
        self.assertNotIn("URL", event)
        self.assertEqual(
            "Svoz odpadu (Směsný odpad) – Zkušební ulice, Litovel",
            event.decoded("description"),
        )

    def test_new_text_fields_are_escaped_and_long_unicode_lines_are_folded(self):
        street = "Zkušební, ulice; se zpětným\\lomítkem"
        source_url = "https://example.test/source?a=1,b=2;c=3"
        source_title = (
            "Změna, svozu; se zpětným\\lomítkem a novým\nřádkem – "
            "velmi dlouhý český název oznámení pro ověření skládání řádků"
        )
        archive_one = "https://archive.test/prvni"
        archive_two = "https://archive.test/druhy"
        exception = SvozException(
            id="escaped-fields",
            action="reschedule",
            waste_type="SMES",
            affected_locations=(street,),
            affected_locations_snapshot=(),
            affected_location_group=None,
            original_date=date(2026, 9, 28),
            new_date=date(2026, 9, 25),
            date=None,
            source=SvozExceptionSource(
                url=source_url,
                title=source_title,
                evidence="Důkaz, se středníkem; a zpětným\\lomítkem.",
                note="Doplňující poznámka, se středníkem; a zpětným\\lomítkem.",
                archive_urls=(archive_one, archive_two),
            ),
            note="Doplňující poznámka, se středníkem; a zpětným\\lomítkem.",
        )
        raw, events = self._calendar_events(
            self._generator_with_exception(exception, street), street
        )
        event = events[0]
        description = event.decoded("description")

        self.assertEqual(source_title, event.decoded("X-SVOZ-SOURCE-TITLE"))
        self.assertEqual(
            "Důkaz, se středníkem; a zpětným\\lomítkem.",
            event.decoded("X-SVOZ-CHANGE-MESSAGE"),
        )
        self.assertEqual(
            "https://svoz.litovle.cz/ulice/zkusebni-ulice-se-zpetnymlomitkem/",
            event.decoded("url"),
        )
        self.assertEqual(source_url, event.decoded("X-SVOZ-SOURCE-URL"))
        self.assertEqual(
            [archive_one, archive_two],
            event.decoded("X-SVOZ-ARCHIVE-URL"),
        )
        self.assertIn("Důkaz, se středníkem; a zpětným\\lomítkem.", description)
        self.assertNotIn(source_url, description)
        self.assertNotIn(archive_one, description)
        self.assertNotIn(archive_two, description)
        self.assertEqual(1, description.count("Doplňující poznámka"))

        unfolded = raw.replace(b"\r\n ", b"").decode("utf-8")
        escaped_title = (
            source_title.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n")
        )
        self.assertIn(f"X-SVOZ-SOURCE-TITLE:{escaped_title}", unfolded)
        self.assertIn(
            "X-SVOZ-CHANGE-MESSAGE:Důkaz\\, se středníkem\\; a zpětným\\\\lomítkem.",
            unfolded,
        )
        self.assertIn("Zkušební\\, ulice\\; se zpětným\\\\lomítkem", unfolded)
        for line in raw.split(b"\r\n"):
            self.assertLessEqual(len(line), 75)


class LitovelWatcherTest(unittest.TestCase):
    def test_extracts_and_filters_candidate_articles(self):
        html = """
        <html>
          <body>
            <article>
              <span>12. 2.</span>
              <a href="/cs/urad/uredni-deska/aktualni-informace/zmena-svozu-odpadu.html">
                Změna svozu odpadu
              </a>
            </article>
            <article>
              <time datetime="2026-02-13">13. 2. 2026</time>
              <a href="/cs/kultura/koncert.html">Koncert v Litovli</a>
            </article>
          </body>
        </html>
        """

        articles = extract_articles(html, "https://www.litovel.eu/cs/")
        candidates = find_candidate_articles(articles)

        self.assertEqual(1, len(candidates))
        self.assertEqual("Změna svozu odpadu", candidates[0].title)
        self.assertEqual(
            "https://www.litovel.eu/cs/urad/uredni-deska/aktualni-informace/zmena-svozu-odpadu.html",
            candidates[0].url,
        )
        self.assertEqual("12. 2.", candidates[0].publication_date)
        self.assertEqual("candidate", candidates[0].decision)
        self.assertIn("topic:svoz", candidates[0].topic_reasons)
        self.assertIn("change:zmena", candidates[0].change_reasons)

    def test_uses_local_context_for_unstructured_article_text(self):
        html = """
        <html>
          <body>
            <div>
              <span>20. 5.</span>
              <p>Svoz odpadu v Litovli bude kvůli svátku přesunut.</p>
              <a href="/cs/urad/uredni-deska/aktualni-informace/detail.html">
                Změna termínu
              </a>
            </div>
          </body>
        </html>
        """

        articles = extract_articles(html, "https://www.litovel.eu/")
        candidates = find_candidate_articles(articles)

        self.assertEqual(1, len(candidates))
        self.assertEqual("20. 5.", candidates[0].publication_date)
        self.assertEqual("candidate", candidates[0].decision)
        self.assertIn("topic:svoz", candidates[0].topic_reasons)
        self.assertIn("change:termin", candidates[0].change_reasons)

    def test_reports_waste_article_without_change_as_ignored_topic_match(self):
        html = """
        <html>
          <body>
            <article>
              <a href="/cs/odpady.html">Sběrný dvůr a třídění odpadu</a>
            </article>
          </body>
        </html>
        """

        articles = extract_articles(html, "https://www.litovel.eu/")
        matches = find_matched_articles(articles)

        self.assertEqual(1, len(matches))
        self.assertEqual("ignored", matches[0].decision)
        self.assertEqual(
            "waste-related article but no change-related term",
            matches[0].ignored_reason,
        )
        self.assertIn("topic:odpad", matches[0].topic_reasons)
        self.assertEqual((), matches[0].change_reasons)

    def test_ignores_change_article_without_waste_signal(self):
        html = """
        <html>
          <body>
            <article>
              <a href="/cs/aktuality/svatky.html">Změna programu vánočních svátků</a>
            </article>
          </body>
        </html>
        """

        articles = extract_articles(html, "https://www.litovel.eu/")
        matches = find_matched_articles(articles)

        self.assertEqual([], matches)

    def test_duplicate_links_are_deduplicated(self):
        html = """
        <html>
          <body>
            <article>
              <a href="/cs/zmena-svozu-odpadu.html">Změna svozu odpadu</a>
              <a href="/cs/zmena-svozu-odpadu.html">Změna svozu odpadu</a>
            </article>
          </body>
        </html>
        """

        articles = extract_articles(html, "https://www.litovel.eu/")
        candidates = find_candidate_articles(articles)

        self.assertEqual(1, len(articles))
        self.assertEqual(1, len(candidates))

    def test_default_urls_scan_only_official_information_page(self):
        self.assertEqual(
            ("https://www.litovel.eu/cs/urad/uredni-deska/aktualni-informace/",),
            DEFAULT_URLS,
        )

    def test_json_report_marks_reviewed_candidates(self):
        html = """
        <article>
          <span>25. 8. 2026</span>
          <a href="/cs/urad/uredni-deska/aktualni-informace/zmena-svozu-test.html">
            Změna svozu odpadu
          </a>
        </article>
        """
        matches = find_matched_articles(extract_articles(html, "https://www.litovel.eu/"))
        with tempfile.TemporaryDirectory() as tmpdir:
            known_path = Path(tmpdir) / "known.json"
            report_path = Path(tmpdir) / "report.json"
            known_path.write_text(
                json.dumps({"version": 1, "urls": [matches[0].url]}),
                encoding="utf-8",
            )
            write_json_report(report_path, matches, load_known_urls(known_path), [])
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(1, report["schema_version"])
        self.assertEqual(1, len(report["candidates"]))
        self.assertTrue(report["candidates"][0]["known"])
        self.assertEqual([], report["source_errors"])

    def test_fetch_failure_is_reported_and_fails_watcher(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            known_path = Path(tmpdir) / "known.json"
            report_path = Path(tmpdir) / "report.json"
            known_path.write_text(
                json.dumps({"version": 1, "urls": []}),
                encoding="utf-8",
            )
            with patch(
                "scripts.watch_litovel_eu.fetch_url",
                side_effect=OSError("source unavailable"),
            ):
                status = run_litovel_watcher(
                    ["https://www.litovel.eu/test/"],
                    timeout=1,
                    dry_run=True,
                    json_output=report_path,
                    known_urls_path=known_path,
                )
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(1, status)
        self.assertEqual([], report["candidates"])
        self.assertEqual("https://www.litovel.eu/test/", report["source_errors"][0]["url"])

    def test_known_url_file_rejects_foreign_and_duplicate_urls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "known.json"
            path.write_text(
                json.dumps({"version": 1, "urls": ["https://example.com/change"]}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_known_urls(path)


if __name__ == "__main__":
    unittest.main()
