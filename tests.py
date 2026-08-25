from contextlib import contextmanager
from dataclasses import replace
from datetime import date
import json
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

import calendar_generator
from bio_containers import (
    BioCoordinates,
    BioPlacement,
    BioSchedule,
    BioSite,
    BioSource,
    load_bio_schedule,
)
from PIL import Image
from generator_svozu_odpadu import date_end, date_start
from lokace_svozu import (
    WasteType,
    lokace_svozu_bio,
    lokace_svozu_papir,
    lokace_svozu_plast,
    lokace_svozu_smes,
    validate_regular_schedule_years,
)
from streets import all_streets, litovel_lokace_bio_0, mistni_casti
from svoz_exceptions import load_svoz_exceptions
from scripts.watch_litovel_eu import (
    DEFAULT_URLS,
    extract_articles,
    find_candidate_articles,
    find_matched_articles,
)
from social_preview import _save_card
from site_builder import (
    build_bio_placement_rows,
    build_bio_overview,
    build_bio_collection_jsonld,
    build_bio_search_items,
    build_bio_site_detail,
    build_bio_year_notice,
    build_nearby_bio_html,
    validate_bio_routes,
)
from proximity import (
    ProximityConfig,
    find_nearby_bio_placements,
    haversine_distance_km,
    load_proximity_config,
    resolve_site_coordinates,
    resolve_street_coordinates,
)
from project_config import project_config, validate_rollover


BIO_2026_PATH = Path("data/bio_containers/2026.json")


class BioContainersTest(unittest.TestCase):
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


class BioSeoPagesTest(unittest.TestCase):
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
            '>Zobrazit pravidelný svoz odpadu pro ulici B. Němcové</a>',
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
        self.assertIn("Zobrazit pravidelný svoz odpadu", html)

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
        self.assertIn("Právě není přistaven žádný bio kontejner", html)
        self.assertIn("ve sběrném dvoře", html)
        self.assertIn("49.6861253", html)

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
        self.assertEqual(1, overview["schedule"].count("21. 8.–24. 8. 2026"))
        self.assertNotIn('class="bio-placement"', overview["schedule"])

    def test_empty_overview_links_to_collection_yard(self):
        schedule = load_bio_schedule(BIO_2026_PATH)

        overview = build_bio_overview(schedule, date(2026, 8, 25))

        self.assertIn("Právě nyní není přistaven žádný kontejner", overview["current"])
        self.assertIn("ve sběrném dvoře", overview["current"])
        self.assertIn("49.6861253", overview["current"])


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
                "missing source title",
                {
                    "id": "missing-source-title",
                    "action": "include",
                    "waste_type": "SMES",
                    "affected_locations": ["Dukelská"],
                    "date": "2026-02-17",
                    "source": {"url": None},
                },
                "source.title is required",
            ),
            (
                "old flat source field",
                {
                    **valid_base,
                    "source_url": "https://www.litovel.eu/",
                },
                "unknown fields",
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


if __name__ == "__main__":
    unittest.main()
