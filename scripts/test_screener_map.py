import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ScreenerMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((ROOT / "ipos.json").read_text(encoding="utf-8"))
        cls.mapping = json.loads((ROOT / "screener_map.json").read_text(encoding="utf-8"))

    def test_every_historical_ipo_has_exactly_one_mapping(self):
        names = [row.get("companyName") for row in self.rows]
        self.assertTrue(all(names), "Historical IPO records must have company names")
        self.assertEqual(len(names), len(set(names)), "Historical IPO company names must be unique")
        self.assertEqual(set(names), set(self.mapping), "Screener mappings must exactly cover the historical dataset")

    def test_mapping_paths_are_screener_company_paths(self):
        for name, path in self.mapping.items():
            with self.subTest(company=name):
                self.assertIsInstance(path, str)
                self.assertRegex(path, r"^/company/[A-Za-z0-9_-]+/(?:consolidated/)?$")

    def test_mapping_paths_are_unique(self):
        paths = list(self.mapping.values())
        self.assertEqual(len(paths), len(set(paths)), "Two IPO names must not silently share one Screener path")

if __name__ == "__main__":
    unittest.main()
