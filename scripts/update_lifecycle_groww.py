#!/usr/bin/env python3
"""Move IPOs through Apply -> Waiting for Listing -> Listed using Groww's own data.

Groww's IPO page embeds a list of recently closed IPOs with the stock symbol,
whether it has listed, the official listing price and the listing date. That
replaces the old Screener name search, which missed companies whose Screener
name differs (e.g. "Zetwerk" vs its full legal name).

One request to groww.in per run. Also records each IPO's stock symbol, which
the Yahoo price updater uses for mainboard stocks.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rules import normalized_name, qualifies  # noqa: E402
from update_ipo_lifecycle import (  # noqa: E402
    CMP_KEYS, is_listed_record, lifecycle_stage, number, parse_date,
)

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "live-ipo-data.json"
DATA = ROOT / "ipos.json"
IST = ZoneInfo("Asia/Kolkata")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124 Safari/537.36"}


def groww_closed_ipos():
    html = requests.get("https://groww.in/ipo", headers=HEADERS, timeout=40)
    html.raise_for_status()
    found = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html.text, re.S)
    if not found:
        raise RuntimeError("Groww IPO page has no embedded data; layout changed.")
    props = json.loads(found.group(1))["props"]["pageProps"]
    closed = props.get("closedDataList")
    if not isinstance(closed, list):
        raise RuntimeError("Groww IPO page data has no closedDataList; layout changed.")
    items = {}
    for item in closed + (props.get("openDataList") or []):
        if item.get("companyName"):
            items[normalized_name(item["companyName"])] = item
    return items


def listed_on(item):
    ts = item.get("listingTimestamp")
    if not ts:
        return None
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).astimezone(IST).date()


def save(feed, rows):
    feed["updatedAt"] = datetime.now().astimezone().isoformat(timespec="seconds")
    FEED.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DATA.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "data.js").write_text(
        "window.IPO_DATA = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8")


def main():
    groww = groww_closed_ipos()
    print(f"Groww lists {len(groww)} recent IPOs with symbols.")
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    history = json.loads(DATA.read_text(encoding="utf-8"))
    by_name = {normalized_name(r.get("companyName", "")): r for r in history}
    today = datetime.now(IST).date()
    moved = added = symbols = 0

    for row in feed.get("ipos", []):
        key = normalized_name(row.get("companyName", ""))
        item = groww.get(key, {})
        if item.get("symbol") and row.get("symbol") != item["symbol"]:
            row["symbol"] = item["symbol"]
        was_listed = is_listed_record(row)
        close_date = parse_date(row.get("applicationEnd") or row.get("closeDate"))
        stage = lifecycle_stage(close_date, today, was_listed)
        if stage == "Apply":
            row["stage"], row["status"] = "Apply", "Open"
            continue
        if stage == "Listed":
            continue
        row["stage"], row["status"] = "Waiting for Listing", "Waiting for Listing"
        price, day = number(item.get("listingPrice")), listed_on(item)
        if not (item.get("isListed") and price and day and day <= today):
            continue
        issue = number(item.get("issuePrice")) or number(row.get("issuePrice"))
        if not issue:
            print(f"Listed but no issue price, skipped: {row['companyName']}")
            continue
        row.update({
            "stage": "Listed", "status": "Listed",
            "listingDate": day.strftime("%d %b %Y"),
            "listingPrice": round(price, 2),
            "listingPriceBasis": "Groww official listing price",
            "listingGain": f"{(price - issue) / issue * 100:.1f}%",
            "issuePrice": issue,
            "currentPrice": None, "currentGain": None,
        })
        moved += 1
        print(f"Listed: {row['companyName']} on {day} at {price} (issue {issue})")
        if qualifies(row):
            prior = by_name.get(key, {})
            listed = {k: v for k, v in row.items() if k not in CMP_KEYS}
            by_name[key] = {**prior, **listed, "companyName": row["companyName"]}
            added += 1

    for key, rec in by_name.items():  # backfill symbols on stored history
        sym = groww.get(key, {}).get("symbol")
        if sym and rec.get("symbol") != sym:
            rec["symbol"] = sym
            symbols += 1

    save(feed, list(by_name.values()))
    print(f"Moved to Listed: {moved}; added to history (passed rules): {added}; symbols backfilled: {symbols}.")


if __name__ == "__main__":
    main()
