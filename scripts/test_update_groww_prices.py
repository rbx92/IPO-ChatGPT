import importlib.util
import io
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "update_groww_prices", Path(__file__).with_name("update_groww_prices.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GrowwPriceTests(unittest.TestCase):
    def test_name_normalization(self):
        self.assertEqual(
            module.normalize_name("Example Industries Ltd."),
            module.normalize_name("Example Industries Limited"),
        )

    def test_exact_instrument_resolution_for_mainboard_and_sme(self):
        csv_text = (
            "exchange,exchange_token,trading_symbol,groww_symbol,name,instrument_type,segment,series,isin\n"
            "NSE,1,EXAMPLE,NSE-EXAMPLE,Example Manufacturing,EQ,CASH,EQ,INE000A01000\n"
            "BSE,2,SMECO,BSE-SMECO,Small Example Technologies,EQ,CASH,SM,INE000B01000\n"
            "NSE,3,OTHER,NSE-OTHER,Unrelated Company,EQ,CASH,EQ,INE000C01000\n"
        )
        by_name, by_symbol = module.parse_instruments_csv(csv_text)
        item, status = module.resolve_instrument("Example Manufacturing", "Mainboard", by_name, by_symbol, {})
        self.assertEqual(status, "EXACT_NAME_MATCH")
        self.assertEqual(item["exchange_trading_symbol"], "NSE_EXAMPLE")
        item, status = module.resolve_instrument("Small Example Technologies", "SME", by_name, by_symbol, {})
        self.assertEqual(status, "EXACT_NAME_MATCH")
        self.assertEqual(item["exchange_trading_symbol"], "BSE_SMECO")

    def test_missing_or_ambiguous_instrument_is_not_guessed(self):
        rows = [
            {"exchange":"NSE","trading_symbol":"DUP","name":"Duplicate Co","segment":"CASH"},
            {"exchange":"BSE","trading_symbol":"DUPB","name":"Duplicate Co","segment":"CASH"},
        ]
        by_name = {module.normalize_name("Duplicate Co"): rows}
        by_symbol = {x["exchange_trading_symbol"]:x for x in [
            dict(x, exchange_trading_symbol=f"{x['exchange']}_{x['trading_symbol']}") for x in rows
        ]}
        item, status = module.resolve_instrument("Missing Company", "SME", by_name, by_symbol, {})
        self.assertIsNone(item)
        self.assertEqual(status, "NO_EXACT_NAME_MATCH")
        item, status = module.resolve_instrument("Duplicate Co", "SME", by_name, by_symbol, {})
        self.assertIsNone(item)
        self.assertEqual(status, "AMBIGUOUS_EXCHANGE_SYMBOL")

    def test_groww_ltp_response(self):
        self.assertEqual(
            module.extract_ltp_response({"NSE_EXAMPLE": 123.45, "BSE_TEST": {"ltp": 50}}),
            {"NSE_EXAMPLE": 123.45, "BSE_TEST": 50.0},
        )

    def test_eligibility_does_not_use_current_gain(self):
        self.assertTrue(module.qualifies({
            "companyName":"Example Manufacturing", "qib":"50x",
            "listingGain":"15%", "currentGain":"-80%"
        }))
        self.assertFalse(module.qualifies({
            "companyName":"Example Bank", "qib":"80x", "listingGain":"50%"
        }))

    def test_existing_row_selection_preserves_original_indexes(self):
        rows = [
            {"companyName":"First","qib":"50x","listingGain":"15%"},
            {"companyName":"Second","qib":"10x","listingGain":"20%"},
            {"companyName":"Third","qib":"60x","listingGain":"20%"},
        ]
        selected = [(i,r) for i,r in enumerate(rows) if module.qualifies(r)]
        self.assertEqual([i for i,_ in selected], [0,2])
        self.assertEqual(len(rows), 3)


if __name__ == "__main__":
    unittest.main()
