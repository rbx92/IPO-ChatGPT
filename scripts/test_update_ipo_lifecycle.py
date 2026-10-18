import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("update_ipo_lifecycle", Path(__file__).with_name("update_ipo_lifecycle.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class LifecycleTests(unittest.TestCase):
    def test_parse_close_date(self):
        self.assertEqual(str(module.parse_date("15 Oct 2026")), "2026-10-15")
    def test_normalized_legal_suffix(self):
        self.assertEqual(module.normalized("Example Industries Ltd."), module.normalized("Example Industries Limited"))
    def test_missing_date_is_not_guessed(self):
        self.assertIsNone(module.parse_date("unknown"))

    def test_listed_state_is_preserved_when_price_is_missing(self):
        self.assertTrue(module.is_listed_record({"stage": "Listed", "listingPrice": None}))
        self.assertTrue(module.is_listed_record({"status": "Listed", "listingPrice": None}))
        self.assertTrue(module.is_listed_record({"listingPrice": 123.45}))
        self.assertFalse(module.is_listed_record({"stage": "Waiting for Listing", "listingPrice": None}))

    def test_screener_rate_limit_stops_following_lookups(self):
        self.assertTrue(module.is_screener_rate_limit(RuntimeError("Screener denied/throttled request (HTTP 429); stopping safely")))
        self.assertTrue(module.is_screener_rate_limit(RuntimeError("Screener denied/throttled request (HTTP 403); stopping safely")))
        self.assertFalse(module.is_screener_rate_limit(RuntimeError("Could not identify Screener chart ID")))

if __name__ == "__main__":
    unittest.main()
