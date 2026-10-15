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

if __name__ == "__main__":
    unittest.main()
