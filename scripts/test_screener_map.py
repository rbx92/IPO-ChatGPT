import json
import unittest
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("validate_screener_map", ROOT / "scripts" / "validate_screener_map.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

class ScreenerMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((ROOT / "ipos.json").read_text(encoding="utf-8"))
        cls.mapping = json.loads((ROOT / "screener_map.json").read_text(encoding="utf-8"))

    def test_legacy_screener_mappings_reference_known_historical_ipos(self):
        names = [row.get("companyName") for row in self.rows]
        self.assertTrue(all(names), "Historical IPO records must have company names")
        self.assertEqual(len(names), len(set(names)), "Historical IPO company names must be unique")
        self.assertTrue(set(self.mapping).issubset(set(names)),
                        "Legacy Screener mappings must not refer to unknown IPOs")
        # The historical archive intentionally contains rows without legacy Screener
        # mappings. Future CMP updates use the separate Groww-only instrument map.

    def test_mapping_paths_are_screener_company_paths(self):
        for name, path in self.mapping.items():
            with self.subTest(company=name):
                self.assertIsInstance(path, str)
                self.assertRegex(path, r"^/company/(?:id/)?[A-Za-z0-9_-]+/(?:consolidated/)?$")

    def test_mapping_paths_are_unique(self):
        paths = list(self.mapping.values())
        self.assertEqual(len(paths), len(set(paths)), "Two IPO names must not silently share one Screener path")

    def test_browser_data_mirror_matches_source_json(self):
        source = (ROOT / "data.js").read_text(encoding="utf-8").strip()
        prefix = "window.IPO_DATA = "
        self.assertTrue(source.startswith(prefix), "data.js must export window.IPO_DATA")
        self.assertTrue(source.endswith(";"), "data.js export must end with a semicolon")
        mirrored = json.loads(source[len(prefix):-1])
        self.assertEqual(mirrored, self.rows, "data.js and ipos.json must remain synchronized")

    def test_all_reviewed_screener_name_aliases_match(self):
        for company, aliases in validator.ALIASES.items():
            for alias in aliases:
                with self.subTest(company=company, alias=alias):
                    self.assertEqual(validator.identity_status(company, alias), "PASS")

    def test_exact_name_and_unreviewed_mismatch(self):
        self.assertEqual(validator.identity_status("Danish Power Ltd.", "Danish Power Ltd"), "PASS")
        self.assertEqual(validator.identity_status("IndoMIM", "Unrelated Company Ltd"), "REVIEW")
        self.assertEqual(validator.identity_status("IndoMIM", ""), "UNKNOWN")

    def test_heading_parser_uses_one_unique_h1(self):
        parser = validator.HeadingParser()
        parser.feed('<h1>Example Company Ltd</h1><h1>Example Company Ltd</h1>')
        self.assertEqual(parser.headings, ["Example Company Ltd"])

if __name__ == "__main__":
    unittest.main()
