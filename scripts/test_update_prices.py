import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("update_prices", Path(__file__).with_name("update_prices.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PriceUpdaterTests(unittest.TestCase):
    def test_normalized_legal_suffix(self):
        self.assertEqual(module.normalized_name("Reliance Industries Ltd."), module.normalized_name("Reliance Industries Limited"))
    def test_not_fuzzy_match(self):
        self.assertNotEqual(module.normalized_name("Reliance Industries"), module.normalized_name("Reliance Power"))
    def test_current_price_parser(self):
        html = '<ul><li><span class="name">Current Price</span><span class="number">₹ 1,167.00</span></li></ul>'
        parser = module.CurrentPriceParser()
        parser.feed(html)
        self.assertEqual(parser.prices, [1167.0])
    def test_qualifying_filters(self):
        self.assertTrue(module.qualifies({"companyName": "Example Manufacturing", "qib": "50.0x", "listingGain": "15.0%", "currentGain": "-20%"}))
        self.assertFalse(module.qualifies({"companyName": "Example Manufacturing", "qib": "-", "listingGain": "90%"}))
        self.assertFalse(module.qualifies({"companyName": "Example Manufacturing", "qib": "49.9x", "listingGain": "90%"}))
        self.assertFalse(module.qualifies({"companyName": "Example Manufacturing", "qib": "80x", "listingGain": "14.9%"}))
        self.assertFalse(module.qualifies({"companyName": "Example Bank", "qib": "80x", "listingGain": "90%"}))
        self.assertFalse(module.qualifies({"companyName": "Example Biotech", "qib": "80x", "listingGain": "90%"}))
        self.assertFalse(module.qualifies({"companyName": "NACDAC Infrastructure Ltd.", "qib": "118.2x", "listingGain": "90.0%"}))

    def test_whole_rupee_gain(self):
        self.assertEqual(f"{((79 - 67) / 67 * 100):.1f}%", "17.9%")

    def test_eligible_selection_preserves_all_rows_and_original_indexes(self):
        rows = [
            {"companyName": "Eligible Manufacturing A", "qib": "50x", "listingGain": "15%"},
            {"companyName": "Not Eligible Manufacturing", "qib": "49x", "listingGain": "15%"},
            {"companyName": "Eligible Manufacturing B", "qib": "60x", "listingGain": "20%"},
        ]
        selected = module.select_eligible_rows(rows)
        self.assertEqual(len(rows), 3)
        self.assertEqual([index for index, _ in selected], [0, 2])
        self.assertIs(selected[0][1], rows[0])
        self.assertIs(selected[1][1], rows[2])

if __name__ == "__main__":
    unittest.main()
