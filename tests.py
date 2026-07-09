from contextlib import contextmanager
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import calendar_generator
from PIL import Image
from generator_svozu_odpadu import date_end, date_start
from lokace_svozu import (
    WasteType,
    lokace_svozu_bio,
    lokace_svozu_papir,
    lokace_svozu_plast,
    lokace_svozu_smes,
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
