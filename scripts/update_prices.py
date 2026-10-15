#!/usr/bin/env python3
"""Conservative Screener.in CMP validation for IPO Lens.

Reads root ipos.json, processes rows in batches (default 9), rounds CMP to whole rupees,
and updates currentGain. Each completed batch is saved, so a later error does not discard
previous batches. Does not fuzzy-match names or bypass 403/429 restrictions.
"""
from __future__ import annotations
import argparse, json, re, sys, time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ipos.json"
DATA_JS_PATH = ROOT / "data.js"
MAP_PATH = ROOT / "screener_map.json"
BASE = "https://www.screener.in"
USER_AGENT = "IPO-Lens-price-refresh/1.0"
TIMEOUT = 20

# Current gain is deliberately not part of eligibility because it changes daily.
FINANCIAL_NAME = re.compile(
    r"\b(?:bank|banks|banking|nbfc|finance|financial|finserv|fintech|microfinance|"
    r"insurance|insurer|securities|stockbrok\w*|brokerage|broking|asset management|"
    r"mutual funds?|capital markets|wealth management|investment services|"
    r"housing finance|credit|lending)\b", re.I)
PHARMA_NAME = re.compile(
    r"\b(?:pharma|pharmaceuticals?|biotech|biotechnology|biopharma|drug|"
    r"lifesciences|life sciences)\b", re.I)

def multiple_value(value):
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*x?\s*", str(value or ""), re.I)
    return float(match.group(1)) if match else None

def percent_value(value):
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*%?\s*", str(value or ""))
    return float(match.group(1)) if match else None

def qualifies(row):
    qib = multiple_value(row.get("qib"))
    listing_gain = percent_value(row.get("listingGain"))
    name = str(row.get("companyName") or "")
    return (qib is not None and qib >= 50
            and listing_gain is not None and listing_gain >= 15
            and not FINANCIAL_NAME.search(name)
            and not PHARMA_NAME.search(name))

def normalized_name(value: str) -> str:
    value = value.casefold().replace("&", " and ")
    words = re.sub(r"[^a-z0-9]+", " ", value).split()
    suffixes = {"limited", "ltd", "plc", "pvt", "private", "company", "co"}
    while words and words[-1] in suffixes:
        words.pop()
    return " ".join(words)

class CurrentPriceParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.li_depth = 0
        self.span_depth = 0
        self.li_text = []
        self.span_text = []
        self.span_class = ""
        self.spans = []
        self.prices = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "li":
            self.li_depth += 1
            if self.li_depth == 1:
                self.li_text, self.spans = [], []
        if tag == "span":
            self.span_depth += 1
            self.span_class = attrs.get("class", "")
            self.span_text = []
    def handle_data(self, data):
        text = data.strip()
        if not text: return
        if self.li_depth: self.li_text.append(text)
        if self.span_depth: self.span_text.append(text)
    def handle_endtag(self, tag):
        if tag == "span" and self.span_depth:
            self.spans.append((self.span_class, " ".join(self.span_text).strip()))
            self.span_depth -= 1
            self.span_class, self.span_text = "", []
        if tag == "li" and self.li_depth:
            if self.li_depth == 1:
                all_text = " ".join(self.li_text).casefold()
                if "current price" in all_text:
                    values = [v for cls, v in self.spans if set(cls.split()) & {"number", "value"}]
                    for candidate in values or [" ".join(self.li_text)]:
                        m = re.search(r"(?:₹\s*)?([0-9][0-9,]*(?:\.[0-9]+)?)", candidate)
                        if m:
                            price = float(m.group(1).replace(",", ""))
                            if price > 0: self.prices.append(price)
                            break
            self.li_depth -= 1

def get_text(url):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8", "Accept-Language": "en-IN,en;q=0.9", "Referer": BASE + "/"})
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        if exc.code in (401, 403, 429):
            raise RuntimeError(f"Screener denied/throttled request (HTTP {exc.code}); stopped without bypassing restriction") from exc
        raise RuntimeError(f"Screener HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc

def resolve(name):
    results = json.loads(get_text(f"{BASE}/api/company/search/?q={quote_plus(name)}"))
    target = normalized_name(name)
    paths = {item["url"].split("?", 1)[0] for item in results
             if isinstance(item, dict) and isinstance(item.get("name"), str)
             and normalized_name(item["name"]) == target
             and isinstance(item.get("url"), str) and item["url"].startswith("/company/")}
    return next(iter(paths)) if len(paths) == 1 else None

def price_at(path):
    parser = CurrentPriceParser()
    parser.feed(get_text(BASE + path))
    if not parser.prices: raise RuntimeError(f"Could not parse labelled Current Price for {path}")
    return int(parser.prices[0] + 0.5)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0, help="zero-based row offset")
    ap.add_argument("--limit", type=int, default=0, help="rows to check (0 means all remaining)")
    ap.add_argument("--batch-size", type=int, default=9, help="rows per save batch (default 9)")
    ap.add_argument("--delay", type=float, default=60, help="seconds between requests, minimum 1 (default 60)")
    ap.add_argument("--dry-run", action="store_true", help="do not write files")
    args = ap.parse_args()
    if args.start < 0 or args.limit < 0 or args.delay < 1 or args.batch_size < 1: ap.error("start/limit must be >=0, batch-size >=1 and delay >=1 second")
    rows = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(rows, list): raise SystemExit("ipos.json must contain a JSON list")
    raw_count = len(rows)
    eligible_rows = [row for row in rows if qualifies(row)]
    rows = eligible_rows
    eligible = list(enumerate(rows))
    if eligible and args.start >= len(eligible): ap.error(f"start must be less than {len(eligible)} qualifying IPOs")
    if not eligible and args.start: ap.error("start must be 0 when there are no qualifying IPOs")
    selected = eligible[args.start:args.start + args.limit] if args.limit else eligible[args.start:]
    print("Hard filters: QIB >= 50x; listing gain >= 15%; valid values; excludes financial-sector and pharma names.", flush=True)
    print(f"Eligible IPOs retained: {len(eligible)} of {raw_count} raw records. Non-qualifying records will be removed. Current gain is not used as a filter.", flush=True)
    paths = json.loads(MAP_PATH.read_text(encoding="utf-8")) if MAP_PATH.exists() else {}
    unmatched = 0
    updated = 0
    stamp = datetime.now().astimezone().isoformat(timespec="minutes")

    def save_batch():
        DATA_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        DATA_JS_PATH.write_text("window.IPO_DATA = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
        MAP_PATH.write_text(json.dumps(paths, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Persist the filtered universe before network work, so rejected IPOs are dropped
    # even if a later request fails. Dry runs never modify files.
    if not args.dry_run:
        save_batch()

    for offset in range(0, len(selected), args.batch_size):
        batch = selected[offset:offset + args.batch_size]
        print(f"\nBatch {offset // args.batch_size + 1}: eligible IPOs {args.start + offset + 1}-{args.start + offset + len(batch)} of {len(selected)} selected ({len(eligible)} eligible total)", flush=True)
        try:
            for original_index, row in batch:
                row_index = original_index + 1
                name = str(row.get("companyName", "")).strip()
                path = paths.get(name)
                if not path:
                    path = resolve(name)
                    time.sleep(args.delay)
                    if path:
                        paths[name] = path
                if not path:
                    unmatched += 1
                    print(f"[{row_index}/{len(rows)}] UNMATCHED — {name}; preserving existing price", flush=True)
                    continue
                cmp = price_at(path)
                time.sleep(args.delay)
                issue = float(row.get("issuePrice") or 0)
                gain = f"{((cmp - issue) / issue * 100):.1f}%" if issue > 0 else "-"
                if not args.dry_run:
                    row["currentPrice"] = cmp
                    row["currentGain"] = gain
                    row["priceUpdatedAt"] = stamp
                    row["priceSource"] = "Screener.in"
                updated += 1
                print(f"[{row_index}/{len(rows)}] {name}: CMP ₹{cmp} | current gain {gain}", flush=True)
        except Exception as exc:
            if not args.dry_run:
                save_batch()
            print(f"UPDATE STOPPED: {exc}", file=sys.stderr, flush=True)
            print(f"Saved completed work so far: {updated} prices updated; {unmatched} unmatched.", file=sys.stderr, flush=True)
            return 2
        if not args.dry_run:
            save_batch()
            print(f"Saved batch. Cumulative prices updated: {updated}; unmatched: {unmatched}.", flush=True)

    if args.dry_run:
        print(f"DRY RUN: {len(selected)} qualifying IPOs checked; {updated} prices parsed; {unmatched} unmatched. No files written.")
    else:
        print(f"UPDATE COMPLETE: {updated} qualifying IPO prices updated; {unmatched} unmatched. Non-qualifying records were preserved. CMP rounded to whole rupees.")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
