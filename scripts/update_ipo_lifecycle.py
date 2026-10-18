#!/usr/bin/env python3
"""Advance Groww IPO records through Apply -> Waiting for Listing -> Listed.

Screener's daily chart is used as the source for the first available trading-day
close on/after the application close date. This is explicitly a closing-price
proxy, not an exchange's official opening/listing price.
"""
import json, re, sys, time
from datetime import datetime, date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "live-ipo-data.json"
DATA = ROOT / "ipos.json"
BASE = "https://www.screener.in"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; IPO-Lens/1.0)", "X-Requested-With": "XMLHttpRequest", "Referer": BASE + "/"}

def parse_date(value):
    if not value: return None
    for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d-%m-%Y"):
        try: return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError: pass
    return None

def number(value):
    m = re.search(r"-?\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    return float(m.group()) if m else None

def get(url):
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=25) as response:
            return response.read().decode("utf-8", "replace")
    except HTTPError as exc:
        if exc.code in (401, 403, 429):
            raise RuntimeError(f"Screener denied/throttled request (HTTP {exc.code}); stopping safely") from exc
        raise

def normalized(value):
    words = re.sub(r"[^a-z0-9]+", " ", str(value).casefold().replace("&", " and ")).split()
    while words and words[-1] in {"limited", "ltd", "plc", "pvt", "private", "company", "co"}: words.pop()
    return " ".join(words)

def is_listed_record(row):
    """A known listed state is monotonic: missing data must never demote it."""
    return (str(row.get("stage", "")).casefold() == "listed"
            or str(row.get("status", "")).casefold() == "listed"
            or row.get("listingPrice") not in (None, "", "-"))

def is_screener_rate_limit(exc):
    """Recognize access denial/throttling so the run stops instead of retrying more names."""
    return bool(re.search(r"HTTP (?:401|403|429)\b", str(exc)))

def resolve(name):
    found = json.loads(get(f"{BASE}/api/company/search/?q={quote_plus(name)}"))
    target = normalized(name)
    matches = {x.get("url", "").split("?", 1)[0] for x in found
               if isinstance(x, dict) and normalized(x.get("name", "")) == target
               and isinstance(x.get("url"), str) and x["url"].startswith("/company/")}
    return next(iter(matches)) if len(matches) == 1 else None

def chart_identity(path):
    html = get(BASE + path)
    patterns = [r'data-company-id=["\'](\d+)["\']', r'data-company-id=["\'](\d+)']
    for pattern in patterns:
        m = re.search(pattern, html)
        if m: return m.group(1)
    raise RuntimeError(f"Could not identify Screener chart ID for {path}")

def first_close_on_or_after(path, start_date):
    company_id = chart_identity(path)
    chart = json.loads(get(f"{BASE}/api/company/{company_id}/chart/?q=Price&days=10000"))
    values = []
    for dataset in chart.get("datasets", []):
        if dataset.get("metric", "").casefold() == "price":
            values = dataset.get("values", [])
            break
    candidates = []
    for item in values:
        if not isinstance(item, list) or len(item) < 2: continue
        day, price = parse_date(item[0]), number(item[1])
        if day and price and price > 0 and day >= start_date: candidates.append((day, price))
    return min(candidates, key=lambda x: x[0]) if candidates else None

def main():
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    records = feed.get("ipos", [])
    today = datetime.now().date()
    history = json.loads(DATA.read_text(encoding="utf-8"))
    by_name = {normalized(x.get("companyName")): x for x in history}
    changed = 0
    for row in records:
        was_listed = is_listed_record(row)
        close_date = parse_date(row.get("applicationEnd") or row.get("closeDate") or row.get("listingDate"))
        if not close_date:
            if not was_listed:
                row["stage"] = "Apply"
                row["status"] = "Open"
            continue
        row["applicationEnd"] = close_date.strftime("%d %b %Y")
        if today <= close_date:
            if not was_listed:
                row["stage"], row["status"] = "Apply", "Open"
                row["listingDate"] = None
            continue
        # Preserve already-listed records; this transition job only discovers first listing.
        if was_listed:
            row["stage"], row["status"] = "Listed", "Listed"
            continue
        row["stage"], row["status"] = "Waiting for Listing", "Waiting for Listing"
        row["listingPrice"] = None
        row["listingGain"] = None
        row["currentPrice"] = None
        row["currentGain"] = None
        name = normalized(row.get("companyName"))
        try:
            path = resolve(row.get("companyName", ""))
            if path:
                result = first_close_on_or_after(path, close_date)
                if result:
                    listed_on, listing_price = result
                    issue = number(row.get("issuePrice"))
                    if issue:
                        row["stage"], row["status"] = "Listed", "Listed"
                        row["listingDate"] = listed_on.strftime("%d %b %Y")
                        row["listingPrice"] = round(listing_price, 2)
                        row["listingPriceBasis"] = "Screener first available daily close on/after application close; not official listing/opening price"
                        row["listingGain"] = f"{(listing_price - issue) / issue * 100:.1f}%"
                        row["currentPrice"] = round(listing_price, 2)
                        row["currentGain"] = row["listingGain"]
                        row["priceSource"] = "Screener.in"
                        row["priceUpdatedAt"] = datetime.now().astimezone().isoformat(timespec="minutes")
                        # Only listed records with complete eligibility data enter the persistent dataset.
                        from scripts.update_prices import qualifies
                        if qualifies({**row, "companyName": row.get("companyName")}):
                            prior = by_name.get(name, {})
                            by_name[name] = {**prior, **row, "companyName": row["companyName"]}
                        changed += 1
        except (RuntimeError, URLError, ValueError, KeyError) as exc:
            print(f"Deferred {row.get('companyName')}: {exc}", file=sys.stderr)
            if is_screener_rate_limit(exc):
                print("Stopping lifecycle network lookups after Screener denial/throttling; no retries or bypasses.", file=sys.stderr)
                break
        time.sleep(5)
    feed["updatedAt"] = datetime.now().astimezone().isoformat(timespec="seconds")
    FEED.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = list(by_name.values())
    DATA.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "data.js").write_text("window.IPO_DATA = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Lifecycle checked {len(records)} Groww records; listed/eligible transitions processed: {changed}; saved tracked dataset: {len(rows)}.")

if __name__ == "__main__":
    main()
