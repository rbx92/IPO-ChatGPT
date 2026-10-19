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
