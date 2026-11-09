#!/usr/bin/env python3
"""Mainboard CMP and daily closes from Yahoo Finance (NSE, ".NS" tickers).

SME stocks stay on Screener (Yahoo coverage of SME is poor). For each
qualifying Mainboard IPO this reads Yahoo's public daily chart once, which
gives both the current price and the closes the pullback signal needs.

Ticker: the IPO's Groww symbol if known, else a Yahoo name search. Resolved
tickers are cached in yahoo_symbols.json. Two seconds between requests.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rules import normalized_name, qualifies  # noqa: E402
from update_pullbacks import is_candidate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "ipos.json"
CACHE = ROOT / "yahoo_symbols.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124 Safari/537.36"}
IST = ZoneInfo("Asia/Kolkata")
DELAY = 2


def get_json(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    if response.status_code in (401, 403, 429):
        raise PermissionError(f"Yahoo returned HTTP {response.status_code}")
    response.raise_for_status()
    return response.json()


def search_ticker(name):
    url = "https://query1.finance.yahoo.com/v1/finance/search"
    data = get_json(f"{url}?q={requests.utils.quote(name)}&quotesCount=8&newsCount=0")
    want = normalized_name(name)
    for quote in data.get("quotes", []):
        sym, long = quote.get("symbol", ""), normalized_name(quote.get("longname") or quote.get("shortname") or "")
        if sym.endswith(".NS") and long and (long.startswith(want) or want.startswith(long)):
            return sym
    return None


def chart(ticker):
    data = get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=6mo&interval=1d")
    result = (data.get("chart", {}).get("result") or [None])[0]
    if not result:
        return None, []
    price = result.get("meta", {}).get("regularMarketPrice")
    closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    days = [datetime.fromtimestamp(t, tz=timezone.utc).astimezone(IST).date().isoformat()
            for t in result.get("timestamp") or []]
    history = [{"date": d, "close": round(c, 2)} for d, c in zip(days, closes) if c]
    now = datetime.now(IST)
    if now.weekday() < 5 and now.hour * 60 + now.minute < 15 * 60 + 45:
        # Market still open (closes 15:30 IST): today's bar is not a close yet.
        history = [h for h in history if h["date"] != now.date().isoformat()]
    return price, history


def save(rows, cache):
    DATA.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "data.js").write_text(
        "window.IPO_DATA = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    today = datetime.now(IST).date()
    stamp = datetime.now().astimezone().isoformat(timespec="minutes")
    targets = [r for r in rows if r.get("stockType") == "Mainboard" and qualifies(r)]
    print(f"Mainboard IPOs to price from Yahoo: {len(targets)}")
    updated, unmatched = 0, []
    try:
        for row in targets:
            name = row["companyName"]
            ticker = cache.get(name) or (f"{row['symbol']}.NS" if row.get("symbol") else None)
            if not ticker:
                ticker = search_ticker(name)
                time.sleep(DELAY)
            if not ticker:
                unmatched.append(name)
                continue
            price, history = chart(ticker)
            time.sleep(DELAY)
            if not price:
                unmatched.append(f"{name} ({ticker})")
                continue
            cache[name] = ticker
            issue = float(row.get("issuePrice") or 0)
            row["currentPrice"] = round(price)
            row["currentGain"] = f"{(price - issue) / issue * 100:.1f}%" if issue > 0 else "-"
            row["priceUpdatedAt"] = stamp
            row["priceSource"] = "Yahoo Finance"
            if is_candidate(row, today):
                listed = str(row.get("listingDate") or "")
                row["priceHistory"] = [h for h in history if not listed or h["date"] >= _iso(listed)]
                row["priceHistoryUpdatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                row["priceHistorySource"] = "Yahoo Finance daily close"
            updated += 1
            print(f"OK   {name} ({ticker}): ₹{price}")
    except PermissionError as exc:
        print(f"STOPPED: {exc}. Keeping {updated} completed updates; no retries.")
        save(rows, cache)
        sys.exit(1)
    save(rows, cache)
    print(f"Done: {updated} updated from Yahoo; unmatched {len(unmatched)}: {unmatched}")


def _iso(value):
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value[:11].strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return ""


if __name__ == "__main__":
    main()
