"""Every file the pipeline reads or writes, in one place.

Website files stay at the repository root because GitHub Pages serves them;
lookup tables and caches live in data/.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Website (served by GitHub Pages)
IPOS = ROOT / "ipos.json"              # listed IPOs that pass the rules
DATA_JS = ROOT / "data.js"             # same list, loaded by index.html
FEED = ROOT / "live-ipo-data.json"     # open / waiting / recently listed IPOs
RULES = ROOT / "eligibility-rules.json"

# Lookups and caches
DATA = ROOT / "data"
ISIN_MAP = DATA / "isin_map.json"               # company -> ISIN
OFFICIAL_CLOSES = DATA / "official_closes.json"  # {date: {isin: [close, volume]}}
SCREENER_MAP = DATA / "screener_map.json"        # company -> Screener page
SCREENER_IDS = DATA / "screener_chart_ids.json"  # Screener page -> chart id
YAHOO_SYMBOLS = DATA / "yahoo_symbols.json"      # company -> Yahoo ticker

REPORTS = ROOT / "reports"
