#!/usr/bin/env python3
"""Current price and daily closes from the exchanges' official closing-price files.

NSE and BSE publish a "bhavcopy" every trading evening: the official close of
every listed stock, SME included. This is the primary price source; Yahoo and
Screener only fill gaps afterwards.

- Each stock is identified by ISIN, saved in isin_map.json (edit it to fix a
  match by hand). New stocks are matched by symbol first, then by exact
  company name, then by a unique name prefix, with a price sanity check.
- Closes for qualifying stocks are kept in official_closes.json for the last
  ~100 days, so the pullback signal has history from day one. Only days not
  yet in that file are downloaded (two files per trading day, 1 s apart).
"""
import csv
import io
import json
import sys
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rules import ELIGIBILITY_CONFIG, normalized_name, qualifies  # noqa: E402
from update_ipo_lifecycle import parse_date  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "ipos.json"
ISIN_MAP = ROOT / "isin_map.json"
CLOSES = ROOT / "official_closes.json"
IST = ZoneInfo("Asia/Kolkata")
KEEP_DAYS = ELIGIBILITY_CONFIG["pullback_signal"]["max_days_since_listing"] + 40
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124 Safari/537.36", "Accept": "*/*"}


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def fetch_day(day):
    """Rows (symbol, isin, name, close, exchange) for one trading day, or None if not published."""
    rows = []
    nse = requests.get(f"https://nsearchives.nseindia.com/content/cm/"
                       f"BhavCopy_NSE_CM_0_0_0_{day:%Y%m%d}_F_0000.csv.zip",
                       headers={**H, "Referer": "https://www.nseindia.com/"}, timeout=60)
    if nse.status_code == 200 and nse.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(nse.content)) as z:
            text = z.read(z.namelist()[0]).decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(text)):
            if r.get("ClsPric") and r.get("ISIN"):
                rows.append((r["TckrSymb"], r["ISIN"], r.get("FinInstrmNm", ""), float(r["ClsPric"]), "NSE"))
    time.sleep(1)
    bse = requests.get(f"https://www.bseindia.com/download/BhavCopy/Equity/"
                       f"BhavCopy_BSE_CM_0_0_0_{day:%Y%m%d}_F_0000.CSV",
                       headers={**H, "Referer": "https://www.bseindia.com/"}, timeout=60)
    if bse.status_code == 200 and b"TckrSymb" in bse.content[:600]:
        for r in csv.DictReader(io.StringIO(bse.content.decode("utf-8", "replace"))):
            if r.get("ClsPric") and r.get("ISIN"):
                rows.append((r["TckrSymb"], r["ISIN"], r.get("FinInstrmNm", ""), float(r["ClsPric"]), "BSE"))
    time.sleep(1)
    return rows or None


def by_isin(day_rows, keep=None):
    """{isin: close}, preferring the NSE close when a stock trades on both exchanges."""
    out = {}
    for _, isin, _, close, ex in sorted(day_rows, key=lambda r: r[4] != "NSE"):
        if (keep is None or isin in keep) and isin not in out:
            out[isin] = close
    return out


def plausible(close, row):
    issue = float(row.get("issuePrice") or 0)
    return not issue or 0.1 <= close / issue <= 25


FILLER = {"and", "l", "lt", "ltd", "limit", "limite", "limited", "the", "co", "india", "ind"}


def words(name):
    return [w for w in normalized_name(name).split() if w not in FILLER]


def abbrev_match(ours, theirs):
    """True if exchange name is our name with words shortened, e.g.
    'TECHERA ENGINEER (IND) L' ~ 'Techera Engineering India'."""
    a, b = words(ours), words(theirs)
    if len(a) < 2 or len(b) < 2 or a[0] != b[0]:
        return False
    n = min(len(a), len(b))
    return all(x.startswith(y) or y.startswith(x) for x, y in zip(a[:n], b[:n])) and min(len(w) for w in b[:n]) >= 2


def match_isin(row, latest, yahoo):
    """Find a stock's ISIN in the latest bhavcopy. Returns (isin, how) or (None, reason)."""
    by_sym, by_name = latest["by_sym"], latest["by_name"]
    symbols = [row.get("symbol"), (yahoo.get(row["companyName"]) or "").replace(".NS", "").replace(".BO", "")]
    for sym in filter(None, symbols):
        hit = by_sym.get(sym.upper())
        if hit and plausible(hit[3], row):
            return hit[1], f"symbol {sym}"
    want = normalized_name(row["companyName"])
    exact = {r[1] for n, r in by_name if n == want and plausible(r[3], row)}
    if len(exact) == 1:
        return exact.pop(), "exact name"
    prefix = {r[1] for n, r in by_name if n and len(want) >= 6 and (n.startswith(want) or want.startswith(n))
              and plausible(r[3], row)}
    if len(prefix) == 1:
        return prefix.pop(), "name prefix"
    short = {r[1] for _, r in by_name if abbrev_match(row["companyName"], r[2]) and plausible(r[3], row)}
    if len(short) == 1:
        return short.pop(), "abbreviated name"
    return None, f"{len(exact) or len(prefix) or len(short)} name candidates"


def main():
    now = datetime.now(IST)
    rows = load(DATA, [])
    isin_map = load(ISIN_MAP, {})
    closes = load(CLOSES, {})          # {"YYYY-MM-DD": {isin: close}}
    yahoo = load(ROOT / "yahoo_symbols.json", {})
    targets = [r for r in rows if qualifies(r)]

    # Trading days to have: weekdays in the window, up to today (today only after 18:30 IST).
    last = now.date() if now.hour * 60 + now.minute >= 18 * 60 + 30 else now.date() - timedelta(days=1)
    window = [last - timedelta(days=i) for i in range(KEEP_DAYS)]
    wanted_days = [d for d in window if d.weekday() < 5]
    latest_rows, latest_day = None, None

    # Always fetch the newest day (needed for matching); then any missing older days.
    for d in wanted_days:
        if d.isoformat() in closes and latest_rows is not None:
            continue
        if latest_rows is not None and d.isoformat() in closes.get("_holidays", []):
            continue
        day_rows = fetch_day(d)
        if not day_rows:
            if latest_rows is not None:  # an older weekday with no file: market holiday
                closes.setdefault("_holidays", []).append(d.isoformat())
            continue
        if latest_rows is None:
            latest_rows, latest_day = day_rows, d
        mapped = set(isin_map.values())
        closes[d.isoformat()] = by_isin(day_rows, mapped or None)
        print(f"Downloaded official closes for {d}: {len(day_rows)} rows")

    if latest_rows is None:
        raise SystemExit("No official bhavcopy available in the window; nothing updated.")

    latest = {"by_sym": {}, "by_name": []}
    for r in latest_rows:
        latest["by_sym"].setdefault(r[0].upper(), r)
        latest["by_name"].append((normalized_name(r[2]), r))

    unmatched, new_since = [], {}
    for row in targets:
        name = row["companyName"]
        if name in isin_map:
            continue
        isin, how = match_isin(row, latest, yahoo)
        if isin:
            isin_map[name] = isin
            listed = parse_date(str(row.get("listingDate") or "").strip())
            new_since[isin] = listed.isoformat() if listed else "0000"
            print(f"Mapped {name} -> {isin} ({how})")
        else:
            unmatched.append(f"{name} ({how})")

    # Re-filter stored days to the ISINs we track, and backfill days fetched before mapping.
    tracked = set(isin_map.values())
    day_key = latest_day.isoformat()
    closes[day_key] = by_isin(latest_rows, tracked)
    for d in [k for k in closes if not k.startswith("_")]:
        closes[d] = {i: c for i, c in closes[d].items() if i in tracked}
        if date.fromisoformat(d) < last - timedelta(days=KEEP_DAYS):
            del closes[d]
    # Stocks matched for the first time need their closes since listing from days
    # cached before they were tracked: refetch only those days, once.
    seen_any = {i for k, v in closes.items() if not k.startswith("_") for i in v}
    for isin in tracked - seen_any:  # e.g. added to isin_map.json by hand
        new_since.setdefault(isin, "0000")
    missing_back = [k for k in closes if not k.startswith("_") and k != day_key
                    and any(k >= since and i not in closes[k] for i, since in new_since.items())]
    print(f"Backfilling {len(missing_back)} earlier days for {len(new_since)} newly matched stocks.")
    for d in missing_back:
        fresh = fetch_day(date.fromisoformat(d))
        if fresh:
            closes[d] = by_isin(fresh, tracked)

    stamp = now.isoformat(timespec="minutes")
    days = sorted(k for k in closes if not k.startswith("_"))
    updated = 0
    from update_pullbacks import is_candidate  # noqa: E402
    for row in targets:
        isin = isin_map.get(row["companyName"])
        if not isin:
            continue
        # Thinly traded stocks are missing from days they did not trade: use the
        # last day they did trade (within the cached window).
        traded = next((d for d in reversed(days) if isin in closes[d]), None)
        if not traded:
            continue
        close = closes[traded][isin]
        issue = float(row.get("issuePrice") or 0)
        row["isin"] = isin
        row["currentPrice"] = round(close, 2)
        row["currentGain"] = f"{(close - issue) / issue * 100:.1f}%" if issue > 0 else "-"
        row["priceUpdatedAt"] = stamp
        row["priceDate"] = traded
        row["priceSource"] = "NSE/BSE official close"
        if is_candidate(row, now.date()):
            listed = parse_date(str(row.get("listingDate") or "").strip())
            row["priceHistory"] = [{"date": d, "close": closes[d][isin]} for d in days
                                   if isin in closes[d] and (not listed or d >= listed.isoformat())]
            row["priceHistoryUpdatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            row["priceHistorySource"] = "NSE/BSE official close"
        updated += 1

    closes["_holidays"] = sorted(set(closes.get("_holidays", [])))[-30:]
    DATA.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "data.js").write_text(
        "window.IPO_DATA = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    ISIN_MAP.write_text(json.dumps(isin_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    CLOSES.write_text(json.dumps(closes, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    print(f"Official close date {day_key}: priced {updated} of {len(targets)} qualifying stocks. "
          f"Unmatched {len(unmatched)} (Yahoo/Screener will try): {unmatched}")


if __name__ == "__main__":
    main()
