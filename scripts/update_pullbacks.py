#!/usr/bin/env python3
"""Collect daily closes for the post-listing pullback signal.

Only listed IPOs that could show the signal are fetched: QIB, listing gain and
days-since-listing limits come from "pullback_signal" in eligibility-rules.json.
For each candidate the Screener daily price chart is read and the closes since
listing are stored as priceHistory. The dashboard turns that history into
"Stock fell more than X% in the last N trading days".

Same Screener etiquette as the CMP updater: 60 seconds between requests, and
the run stops immediately (keeping finished work) on HTTP 401, 403 or 429.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rules import ELIGIBILITY_CONFIG, multiple_value, percent_value  # noqa: E402
from update_ipo_lifecycle import (  # noqa: E402
    BASE, chart_identity, get, is_screener_rate_limit, number, parse_date, resolve,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "ipos.json"
MAP = ROOT / "screener_map.json"
IDS = ROOT / "screener_chart_ids.json"
RULE = ELIGIBILITY_CONFIG["pullback_signal"]
HISTORY_KEYS = ("priceHistory", "priceHistoryUpdatedAt", "priceHistorySource")


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def is_candidate(row, today):
    qib = multiple_value(row.get("qib"))
    gain = percent_value(row.get("listingGain"))
    listed = parse_date(str(row.get("listingDate") or "")[:10])
    if qib is None or gain is None or listed is None:
        return False
    age = (today - listed).days
    return (qib >= RULE["qib_min_multiple"]
            and gain >= RULE["listing_gain_min_percent"]
            and 0 <= age <= RULE["max_days_since_listing"])


def closes_since(company_id, listed):
    days = RULE["max_days_since_listing"] + 30
    chart = json.loads(get(f"{BASE}/api/company/{company_id}/chart/?q=Price&days={days}"))
    values = next((d.get("values", []) for d in chart.get("datasets", [])
                   if str(d.get("metric", "")).casefold() == "price"), [])
    closes = {}
    for item in values:
        if not isinstance(item, list) or len(item) < 2:
            continue
        day, price = parse_date(item[0]), number(item[1])
        if day and price and price > 0 and day >= listed:
            closes[day] = price
    return [{"date": d.isoformat(), "close": round(closes[d], 2)} for d in sorted(closes)]


def save(rows, paths, ids):
    DATA.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "data.js").write_text(
        "window.IPO_DATA = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8")
    MAP.write_text(json.dumps(paths, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    IDS.write_text(json.dumps(ids, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=60, help="seconds between Screener requests")
    args = ap.parse_args()

    rows = load(DATA, [])
    paths = load(MAP, {})
    ids = load(IDS, {})
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()

    candidates = [r for r in rows if is_candidate(r, today)]
    names = {r["companyName"] for r in candidates}
    cleared = 0
    for row in rows:  # history is only kept while a stock can still show the signal
        if row["companyName"] not in names and any(k in row for k in HISTORY_KEYS):
            for key in HISTORY_KEYS:
                row.pop(key, None)
            cleared += 1
    print(f"Pullback candidates: {len(candidates)}; cleared old history from {cleared} records.")

    def wait():
        time.sleep(args.delay)

    updated = skipped = 0
    try:
        for row in candidates:
            name = row["companyName"]
            try:
                path = paths.get(name)
                if not path:
                    path = resolve(name)
                    wait()
                    if not path:
                        print(f"SKIP {name}: no exact Screener match")
                        skipped += 1
                        continue
                    paths[name] = path
                company_id = ids.get(path)
                if not company_id:
                    company_id = chart_identity(path)
                    wait()
                    ids[path] = company_id
                history = closes_since(company_id, parse_date(row["listingDate"][:10]))
                wait()
            except (RuntimeError, ValueError, KeyError, OSError) as exc:
                if is_screener_rate_limit(exc):
                    raise
                print(f"SKIP {name}: {exc}")
                skipped += 1
                continue
            row["priceHistory"] = history
            row["priceHistoryUpdatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            row["priceHistorySource"] = "Screener.in daily close"
            updated += 1
            print(f"OK   {name}: {len(history)} closes")
    except RuntimeError as exc:
        print(f"STOPPED: {exc}. Keeping {updated} completed updates; no retries.")
        save(rows, paths, ids)
        sys.exit(1)

    save(rows, paths, ids)
    print(f"Done: {updated} updated, {skipped} skipped.")


if __name__ == "__main__":
    main()
