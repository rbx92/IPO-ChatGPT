#!/usr/bin/env python3
"""Read-only validation of the 40 Screener mappings added in commit 97d6dfd.

Fetches one mapped company page at a time, verifies the page heading and labelled CMP,
and writes JSON/CSV reports. Stops immediately on 401/403/429; no bypasses or data writes.
"""
import argparse
import csv
import importlib.util
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "screener_map.json"
REPORT_JSON = ROOT / "screener-mapping-validation.json"
REPORT_CSV = ROOT / "screener-mapping-validation.csv"
BASE = "https://www.screener.in"
ALIASES = {
    "Anawil Wire Engineering": ["Anawil Wire and Engineering Ltd"],
    "Horizon Reclaim": ["Horizon Reclaim (India) Ltd"],
    "Susan Electricals": ["Susan Electricals India Ltd"],
    "E to E Transportation": ["E to E Transportation Infrastructure Ltd"],
    "Jindal Supreme": ["Jindal Supreme (India) Ltd"],
    "IndoMIM": ["Indo-MIM Ltd"],
    "Adcounty Media": ["Adcounty Media India Ltd"],
    "Sat Kartar Shopping": ["Sat Kartar Life Ltd"],
    "Fabtech Technologies Cleanrooms Ltd.": ["Fabtech Cleanrooms Ltd"],
    "Anya Polytech Fertilizers": ["Anya Polytech & Fertilizers Ltd"],
    "ICICI Prudential Asset": ["ICICI Prudential Asset Management Co Ltd"],
    "LG Electronics": ["LG Electronics India Ltd"],
    "Sri Lotus Developers": ["Sri Lotus Developers & Realty Ltd"],
    "Sunlite Recycling": ["Sunlite Recycling Industries Ltd"],
    "Bulkcorp Intl": ["Bulkcorp International Ltd"],
    "Sathlokhar Synergys": ["Sathlokhar Synergys E&C Global Ltd"],
    "S A Tech Software": ["S A Tech Software India Ltd"],
    "Manglam Infra": ["Manglam Infra & Engineering Ltd"],
    "Nephro Care": ["Nephro Care India Ltd"],
}

NEW_NAMES = [
    "Anawil Wire Engineering", "Shree Balaji Mala Textiles", "Horizon Reclaim",
    "Susan Electricals", "E to E Transportation", "Jindal Supreme", "IndoMIM",
    "Laser Power and Infra", "Adcounty Media", "Sat Kartar Shopping",
    "Fabtech Technologies Cleanrooms Ltd.", "Anya Polytech Fertilizers",
    "ICICI Prudential Asset", "LG Electronics", "Sri Lotus Developers",
    "Stallion India Fluorochemicals Ltd.", "Identical Brains Studios Ltd.",
    "Rajputana Biodiesel Ltd.", "Danish Power Ltd.", "Freshara Agro Exports Ltd.",
    "Lakshya Powertech Ltd.", "Sahasra Electronic Solutions Ltd.",
    "Thinking Hats Entertainment Solutions Ltd.", "WOL 3D India Ltd.",
    "Namo eWaste Management Ltd.", "Indian Phosphate Ltd.", "Sunlite Recycling",
    "Bulkcorp Intl", "Sathlokhar Synergys", "S A Tech Software", "Manglam Infra",
    "Nephro Care", "Parmeshwar Metal Ltd.", "Apex Ecotech Ltd.",
    "Dhanlaxmi Crop Science Ltd.", "Ganesh Infraworld Ltd.", "Yash Highvoltage Ltd.",
    "Jungle Camps India Ltd.", "Toss The Coin Ltd.", "Emerald Tyre Manufacturers Ltd."
]

spec = importlib.util.spec_from_file_location("update_prices", ROOT / "scripts" / "update_prices.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)

def normalized(value):
    value = str(value or "").casefold().replace("&", " and ")
    words = re.sub(r"[^a-z0-9]+", " ", value).split()
    while words and words[-1] in {"limited", "ltd", "plc", "pvt", "private", "company", "co"}:
        words.pop()
    return " ".join(words)

class HeadingParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current = None
        self.headings = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "h1" and self.current is None:
            self.current = []
    def handle_endtag(self, tag):
        if tag.lower() == "h1" and self.current is not None:
            heading = " ".join(self.current).strip()
            if heading and heading not in self.headings:
                self.headings.append(heading)
            self.current = None
    def handle_data(self, data):
        if self.current is not None and data.strip():
            self.current.append(data.strip())

def identity_status(company, heading):
    if not heading:
        return "UNKNOWN"
    target = normalized(company)
    candidates = [normalized(heading)] + [normalized(alias) for alias in ALIASES.get(company, [])]
    # Some Screener h1 blocks repeat the company name; the parser deduplicates headings.
    if target in candidates or normalized(heading) in [normalized(alias) for alias in ALIASES.get(company, [])]:
        return "PASS"
    # Handle known IPO display-name vs registered-name differences without fuzzy matching.
    if normalized(heading) in [normalized(alias) for alias in ALIASES.get(company, [])]:
        return "PASS"
    return "REVIEW"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=60, help="delay between page requests (minimum 10 seconds)")
    args = ap.parse_args()
    if args.delay < 10:
        ap.error("delay must be at least 10 seconds")
    mapping = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    rows = []
    for i, name in enumerate(NEW_NAMES, start=1):
        path = mapping.get(name)
        if not path:
            rows.append({"company": name, "path": "", "page_heading": "", "cmp": "", "identity": "FAIL", "price": "FAIL", "http": "NO_MAPPING"})
            continue
        try:
            html = updater.get_text(BASE + path)
        except Exception as exc:
            message = str(exc)
            rows.append({"company": name, "path": path, "page_heading": "", "cmp": "", "identity": "NOT_CHECKED", "price": "NOT_CHECKED", "http": message})
            break
        heading = HeadingParser()
        heading.feed(html)
        page_heading = heading.headings[0] if heading.headings else ""
        parser = updater.CurrentPriceParser()
        parser.feed(html)
        identity = identity_status(name, page_heading)
        # Screener may use a registered legal name or a brand heading; report rather than auto-correct.
        rows.append({
            "company": name, "path": path, "page_heading": page_heading,
            "cmp": parser.prices[0] if parser.prices else "",
            "identity": identity,
            "price": "PASS" if parser.prices and parser.prices[0] > 0 else "FAIL",
            "http": "200/OK"
        })
        print(f"[{i}/{len(NEW_NAMES)}] {name}: heading={page_heading}; identity={rows[-1]['identity']}; price={rows[-1]['price']}; CMP={rows[-1]['cmp']}", flush=True)
        if i < len(NEW_NAMES):
            time.sleep(args.delay)
    REPORT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with REPORT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["company", "path", "page_heading", "cmp", "identity", "price", "http"])
        writer.writeheader()
        writer.writerows(rows)
    passed_identity = sum(r["identity"] == "PASS" for r in rows)
    passed_price = sum(r["price"] == "PASS" for r in rows)
    review = sum(r["identity"] in ("REVIEW", "UNKNOWN", "NOT_CHECKED") for r in rows)
    print(f"REPORT: checked {len(rows)}/{len(NEW_NAMES)}; exact identity {passed_identity}; usable CMP {passed_price}; needs review {review}.")
    print(f"Reports: {REPORT_JSON.name}, {REPORT_CSV.name}")
    if len(rows) < len(NEW_NAMES) or any(str(r["http"]).find("HTTP 403") >= 0 or str(r["http"]).find("HTTP 429") >= 0 for r in rows):
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
