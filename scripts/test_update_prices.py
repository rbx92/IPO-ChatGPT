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
    def test_whole_rupee_gain(self):
        self.assertEqual(f"{((79 - 67) / 67 * 100):.1f}%", "17.9%")

if __name__ == "__main__":
    unittest.main()
