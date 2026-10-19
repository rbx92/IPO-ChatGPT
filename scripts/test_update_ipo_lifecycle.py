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


    def test_lifecycle_stage_transitions(self):
        from datetime import date
        today = date(2026, 10, 19)
        self.assertEqual(module.lifecycle_stage(date(2026, 10, 20), today, False), "Apply")
        self.assertEqual(module.lifecycle_stage(date(2026, 10, 18), today, False), "Waiting for Listing")
        self.assertEqual(module.lifecycle_stage(None, today, False), "Apply")
        self.assertEqual(module.lifecycle_stage(date(2026, 10, 20), today, True), "Listed")

    def test_listing_transition_never_sets_screener_as_cmp_source(self):
        from datetime import date
        prior = {
            "companyName": "Example IPO",
            "currentPrice": 99.0,
            "currentGain": " -1.0%",
            "priceSource": "Groww",
            "priceUpdatedAt": "2026-10-18T16:00+05:30",
        }
        live = {"companyName": "Example IPO", "currentPrice": None, "currentGain": None}
        module.apply_listing_result(live, date(2026, 10, 1), 120.0, 100.0)
        merged = {**prior, **live}
        self.assertEqual(live["listingPrice"], 120.0)
        self.assertEqual(live["listingGain"], "20.0%")
        self.assertNotIn("currentPrice", live)
        self.assertNotIn("currentGain", live)
        self.assertNotIn("priceSource", live)
        self.assertEqual(merged["currentPrice"], 99.0)
        self.assertEqual(merged["priceSource"], "Groww")

    def test_screener_rate_limit_stops_following_lookups(self):
        self.assertTrue(module.is_screener_rate_limit(RuntimeError("Screener denied/throttled request (HTTP 429); stopping safely")))
        self.assertTrue(module.is_screener_rate_limit(RuntimeError("Screener denied/throttled request (HTTP 403); stopping safely")))
        self.assertFalse(module.is_screener_rate_limit(RuntimeError("Could not identify Screener chart ID")))

if __name__ == "__main__":
    unittest.main()
