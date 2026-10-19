import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"


class LifecycleImportAndSaveRegression(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copytree(SCRIPTS, self.root / "scripts")
        (self.root / "live-ipo-data.json").write_text(json.dumps({
            "ipos": [{
                "companyName": "Regression Test IPO",
                "applicationEnd": (date.today() - timedelta(days=1)).strftime("%d %b %Y"),
                "issuePrice": 100,
                "qib": "60x",
                "listingGain": "20%",
                "stage": "Waiting for Listing",
                "status": "Waiting for Listing"
            }]
        }), encoding="utf-8")
        (self.root / "ipos.json").write_text("[]\n", encoding="utf-8")
        (self.root / "eligibility-rules.json").write_text(json.dumps({
            "qib_min_multiple": 10,
            "listing_gain_min_percent": 15,
            "excluded_company_names_normalized": ["nacdac infrastructure"],
            "company_name_suffixes": ["limited", "ltd", "plc", "pvt", "private", "company", "co"]
        }), encoding="utf-8")
        (self.root / "mocknet").mkdir()
        (self.root / "mocknet" / "sitecustomize.py").write_text(MOCK_NETWORK, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, script, *args):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.root / "mocknet")
        return subprocess.run(
            [sys.executable, str(self.root / "scripts" / script), *args],
            cwd=self.root, env=env, text=True, capture_output=True, timeout=30
        )


    def test_live_cmp_writer_is_restricted_to_main(self):
        workflow = (REPO / ".github" / "workflows" / "daily-price-update.yml").read_text(encoding="utf-8")
        self.assertIn("branches:\n      - main", workflow)
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)

    def test_actual_lifecycle_command_saves_feed_and_history(self):
        # This executes the actual direct-script command against disposable data,
        # with only Screener HTTP responses replaced by deterministic fixtures.
        result = self.run_script("update_ipo_lifecycle.py")
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

        feed = json.loads((self.root / "live-ipo-data.json").read_text(encoding="utf-8"))
        history = json.loads((self.root / "ipos.json").read_text(encoding="utf-8"))
        data_js = (self.root / "data.js").read_text(encoding="utf-8")

        self.assertEqual(feed["ipos"][0]["stage"], "Listed")
        self.assertEqual(feed["ipos"][0]["status"], "Listed")
        self.assertEqual(feed["ipos"][0]["listingPrice"], 125)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["companyName"], "Regression Test IPO")
        self.assertEqual(history[0]["listingPrice"], 125)
        self.assertIn("Regression Test IPO", data_js)


    def test_shared_rules_normalize_nacdac_variants_without_prefix_false_positives(self):
        spec = importlib.util.spec_from_file_location(
            "isolated_shared_rules", self.root / "scripts" / "rules.py"
        )
        rules = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rules)

        def row(name, qib="10x", gain="15%"):
            return {"companyName": name, "qib": qib, "listingGain": gain}

        self.assertFalse(rules.qualifies(row("NACDAC Infrastructure Ltd.")))
        self.assertFalse(rules.qualifies(row("NACDAC Infrastructure Limited")))
        self.assertFalse(rules.qualifies(row("Nacdac Infrastructure")))
        self.assertTrue(rules.qualifies(row("NACDAC Infrastructure Services Ltd.")))
        self.assertFalse(rules.qualifies(row("Other Company Ltd.", qib="9.9x")))
        self.assertFalse(rules.qualifies(row("Other Company Ltd.", gain="14.9%")))

    def test_dashboard_uses_shared_eligibility_config(self):
        page = (REPO / "index.html").read_text(encoding="utf-8")
        self.assertIn("fetch('eligibility-rules.json?ts='+Date.now())", page)
        self.assertIn("eligibilityRules.qib_min_multiple", page)
        self.assertIn("eligibilityRules.listing_gain_min_percent", page)
        self.assertIn("eligibilityRules.excluded_company_names_normalized", page)
        self.assertNotIn("name==='nacdac infrastructure ltd.'", page)
        self.assertNotIn("name.startsWith('nacdac infrastructure ')", page)

    def test_price_updater_prioritizes_missing_and_oldest_timestamps(self):
        sys.path.insert(0, str(SCRIPTS))
        try:
            from update_prices import select_eligible_rows
        finally:
            sys.path.pop(0)
        rows = [
            {"companyName": "Recently Updated", "qib": "60x", "listingGain": "20%", "priceUpdatedAt": "2026-10-19T10:00:00+00:00"},
            {"companyName": "Oldest Updated", "qib": "60x", "listingGain": "20%", "priceUpdatedAt": "2026-10-01T10:00:00+00:00"},
            {"companyName": "Never Updated", "qib": "60x", "listingGain": "20%"},
            {"companyName": "Invalid Timestamp", "qib": "60x", "listingGain": "20%", "priceUpdatedAt": "bad timestamp"},
        ]
        ordered = [row["companyName"] for _, row in select_eligible_rows(rows)]
        self.assertEqual(ordered, ["Never Updated", "Invalid Timestamp", "Oldest Updated", "Recently Updated"])

    def test_price_updater_direct_invocation_and_dry_run(self):
        # Exercise the price updater as a directly launched script. Dry-run means
        # the disposable fixture files must remain unchanged.
        eligible_row = {
            "companyName": "Regression Test IPO",
            "qib": "60x",
            "listingGain": "20%",
            "issuePrice": 100,
            "listingPrice": 125
        }
        (self.root / "ipos.json").write_text(json.dumps([eligible_row]) + "\n", encoding="utf-8")
        before = (self.root / "ipos.json").read_text(encoding="utf-8")
        result = self.run_script("update_prices.py", "--dry-run", "--limit", "1", "--delay", "1")
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn("CMP ₹125", result.stdout)
        self.assertEqual((self.root / "ipos.json").read_text(encoding="utf-8"), before)



    def test_groww_zero_apply_rows_preserves_and_advances_feed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copy2(REPO / "scrape_groww_ipo.py", root / "scrape_groww_ipo.py")
            (root / "mocknet").mkdir()
            (root / "mocknet" / "sitecustomize.py").write_text(MOCK_GROWW_NETWORK, encoding="utf-8")
            yesterday = (date.today() - timedelta(days=1)).strftime("%d %b %Y")
            tomorrow = (date.today() + timedelta(days=1)).strftime("%d %b %Y")
            original = {"source": "test", "updatedAt": "old", "ipos": [
                {"companyName": "Closed Test IPO", "applicationEnd": yesterday, "listingDate": yesterday,
                 "issuePrice": 100, "qib": "60x", "hni": "1x", "retail": "1x", "total": "10x",
                 "stockType": "SME", "status": "Open", "stage": "Apply", "source": "Groww",
                 "currentPrice": None, "listingGain": None, "currentGain": None},
                {"companyName": "Future Test IPO", "applicationEnd": tomorrow, "listingDate": tomorrow,
                 "issuePrice": 100, "qib": "1x", "hni": "1x", "retail": "1x", "total": "1x",
                 "stockType": "Mainboard", "status": "Open", "stage": "Apply", "source": "Groww",
                 "currentPrice": None, "listingGain": None, "currentGain": None}
            ]}
            (root / "live-ipo-data.json").write_text(json.dumps(original), encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(root / "mocknet")
            result = subprocess.run([sys.executable, str(root / "scrape_groww_ipo.py")],
                                    cwd=root, env=env, text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)
            updated = json.loads((root / "live-ipo-data.json").read_text(encoding="utf-8"))
            by_name = {row["companyName"]: row for row in updated["ipos"]}
            self.assertEqual(set(by_name), {"Closed Test IPO", "Future Test IPO"})
            self.assertEqual(by_name["Closed Test IPO"]["stage"], "Waiting for Listing")
            self.assertEqual(by_name["Closed Test IPO"]["status"], "Waiting for Listing")
            self.assertEqual(by_name["Future Test IPO"]["stage"], "Apply")
            self.assertIn("No IPOs currently marked Apply", result.stdout)


MOCK_GROWW_NETWORK = r'''
import pandas as pd
import requests

class FakeResponse:
    def __init__(self, text):
        self.text = text
    def raise_for_status(self):
        return None

def fake_get(url, **kwargs):
    return FakeResponse("MAIN" if url.endswith("/ipo") else "SUBSCRIPTION")

requests.get = fake_get

def fake_read_html(source):
    html = source.getvalue()
    if html == "MAIN":
        return [pd.DataFrame({
            "Company Name": ["Upcoming Test IPO"],
            "Type": ["Mainboard"],
            "Close Date": ["30 Oct 2026"],
            "Issue Price": ["₹100"],
            "Unnamed: 4": ["Pre-Apply"]
        })]
    return [pd.DataFrame({
        "Company Name": ["Upcoming Test IPO"],
        "QIB": ["1x"], "NII": ["1x"], "Retail": ["1x"], "Total": ["1x"]
    })]

pd.read_html = fake_read_html
'''

MOCK_NETWORK = r'''
import json
import time
import urllib.request
from io import BytesIO
from datetime import date

time.sleep = lambda *_args, **_kwargs: None

class FakeResponse:
    def __init__(self, body):
        self._body = body.encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def read(self):
        return self._body

_original_urlopen = urllib.request.urlopen

def _mock_urlopen(req, timeout=0, *args, **kwargs):
    url = req.full_url if hasattr(req, "full_url") else str(req)
    if "/api/company/search/" in url:
        return FakeResponse(json.dumps([{
            "name": "Regression Test IPO",
            "url": "/company/regression-test-ipo/"
        }]))
    if "/api/company/12345/chart/" in url:
        return FakeResponse(json.dumps({
            "datasets": [{
                "metric": "Price",
                "values": [[date.today().strftime("%d %b %Y"), 125]]
            }]
        }))
    if "/company/regression-test-ipo/" in url:
        return FakeResponse(
            '<div data-company-id="12345"></div>'
            '<li><span class="name">Current Price</span>'
            '<span class="number">125</span></li>'
        )
    return _original_urlopen(req, timeout=timeout, *args, **kwargs)

urllib.request.urlopen = _mock_urlopen
'''
