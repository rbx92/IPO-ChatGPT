#!/usr/bin/env python3
"""Cross-check stored prices against the exchanges' official closing prices.

Downloads the NSE and BSE daily "bhavcopy" (official close for every stock)
for one trading day and compares, for every qualifying IPO:
  - SME: the Screener price saved for that day
  - Mainboard: Yahoo's daily close for that day (fetched fresh)
Writes reports/price-check.json and reports/price-check.csv. Read-only on data.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # pipeline/
from common.paths import IPOS, ISIN_MAP, REPORTS as OUT, YAHOO_SYMBOLS  # noqa: E402
from common.rules import normalized_name, qualifies  # noqa: E402
IST = ZoneInfo("Asia/Kolkata")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124 Safari/537.36", "Accept": "*/*", "Referer": "https://www.nseindia.com/"}


def nse(day):
    url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{day:%Y%m%d}_F_0000.csv.zip"
    r = requests.get(url, headers=H, timeout=60)
    if r.status_code != 200:
        return None, f"NSE {r.status_code}"
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        text = z.read(z.namelist()[0]).decode("utf-8", "replace")
    return list(csv.DictReader(io.StringIO(text))), "ok"


def bse(day):
    url = f"https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{day:%Y%m%d}_F_0000.CSV"
    r = requests.get(url, headers={**H, "Referer": "https://www.bseindia.com/"}, timeout=60)
    if r.status_code != 200 or b"TckrSymb" not in r.content[:500]:
        return None, f"BSE {r.status_code}"
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8", "replace")))), "ok"


def yahoo_close(ticker, day):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1mo&interval=1d"
    res = (requests.get(url, headers=H, timeout=30).json().get("chart", {}).get("result") or [None])[0]
    if not res:
        return None
    closes = (res.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    for t, c in zip(res.get("timestamp") or [], closes):
        if datetime.fromtimestamp(t, tz=timezone.utc).astimezone(IST).date() == day and c:
            return round(c, 2)
    return None


def main():
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None
    tries = [day] if day else [datetime.now(IST).date() - timedelta(days=i) for i in range(1, 8)]
    nse_rows = bse_rows = None
    for d in tries:
        if d.weekday() >= 5:
            continue
        nse_rows, ns = nse(d)
        bse_rows, bs = bse(d)
        if nse_rows or bse_rows:
            day = d
            break
        print(f"{d}: {ns}, {bs}")
    if not (nse_rows or bse_rows):
        raise SystemExit("Could not download any official bhavcopy.")
    print(f"Official closes for {day}: NSE rows {len(nse_rows or [])}, BSE rows {len(bse_rows or [])}")

    def index(rows, ex):
        by_sym, by_name = {}, []
        for r in rows or []:
            if r.get("FinInstrmTp", "STK") not in ("STK", "") and ex == "NSE":
                continue
            close = float(r.get("ClsPric") or 0)
            if not close:
                continue
            item = (ex, r.get("TckrSymb"), r.get("FinInstrmNm") or "", close, r.get("SctySrs"))
            by_sym[r.get("TckrSymb", "").upper()] = item
            by_name.append((normalized_name(item[2]), item))
        return by_sym, by_name

    n_sym, n_name = index(nse_rows, "NSE")
    b_sym, b_name = index(bse_rows, "BSE")
    yahoo = json.loads(YAHOO_SYMBOLS.read_text()) if YAHOO_SYMBOLS.exists() else {}

    isin_close = {}
    for rows_, ex in ((nse_rows, "NSE"), (bse_rows, "BSE")):
        for r in rows_ or []:
            if r.get("ISIN") and r.get("ClsPric") and r["ISIN"] not in isin_close:
                isin_close[r["ISIN"]] = (ex, r.get("TckrSymb"), r.get("FinInstrmNm", ""), float(r["ClsPric"]), r.get("SctySrs"))
    isin_map = json.loads(ISIN_MAP.read_text()) if ISIN_MAP.exists() else {}

    def official(row):
        isin = row.get("isin") or isin_map.get(row["companyName"])
        if isin and isin in isin_close:
            return isin_close[isin]
        sym = (row.get("symbol") or yahoo.get(row["companyName"], "").replace(".NS", "")).upper()
        if sym and sym in n_sym:
            return n_sym[sym]
        if sym and sym in b_sym:
            return b_sym[sym]
        want = normalized_name(row["companyName"])
        for table in (n_name, b_name):
            for name, item in table:
                if name and (name.startswith(want) or want.startswith(name)):
                    return item
        return None

    rows = [r for r in json.loads(IPOS.read_text()) if qualifies(r)]
    results = []
    for r in rows:
        off = official(r)
        rec = {"company": r["companyName"], "type": r.get("stockType"), "date": day.isoformat()}
        if not off and (r.get("isin") or isin_map.get(r["companyName"])):
            rec["status"] = "did not trade that day"
            rec["ours"], rec["source"] = r.get("currentPrice"), r.get("priceSource")
            rec["lastTraded"] = r.get("priceDate")
            results.append(rec)
            continue
        if not off:
            rec["status"] = "not found in NSE/BSE bhavcopy"
            results.append(rec)
            continue
        ex, sym, oname, close, series = off
        rec.update({"exchange": ex, "symbol": sym, "series": series, "officialClose": close})
        if r.get("stockType") == "Mainboard" and r.get("priceSource") != "NSE/BSE official close":
            ticker = yahoo.get(r["companyName"]) or (f"{r['symbol']}.NS" if r.get("symbol") else None)
            ours = yahoo_close(ticker, day) if ticker else None
            time.sleep(1)
            rec.update({"source": "Yahoo close", "ticker": ticker, "ours": ours})
        else:
            stamp = str(r.get("priceDate") or r.get("priceUpdatedAt") or "")[:10]
            hist = {h["date"]: h["close"] for h in r.get("priceHistory") or []}
            rec.update({"source": r.get("priceSource") or "saved", "ours": hist.get(day.isoformat()) or
                        (r.get("currentPrice") if stamp == day.isoformat() else None),
                        "savedOn": stamp})
        if rec.get("ours"):
            diff = (float(rec["ours"]) - close) / close * 100
            rec["diffPercent"] = round(diff, 2)
            # Screener CMP is stored rounded to whole rupees, so allow rounding.
            tol = max(1.0, 0.6 / close * 100) if str(rec["source"]).startswith("Screener") else 0.5
            rec["status"] = "match" if abs(diff) <= tol else "MISMATCH"
        else:
            rec["status"] = "no stored/fetched price for that day"
        results.append(rec)

    summary = {}
    for rec in results:
        summary.setdefault(rec.get("type"), {}).setdefault(rec["status"], 0)
        summary[rec.get("type")][rec["status"]] += 1
    OUT.mkdir(exist_ok=True)
    (OUT / "price-check.json").write_text(json.dumps({"date": day.isoformat(), "summary": summary,
                                                     "results": results}, indent=2, ensure_ascii=False) + "\n")
    keys = ["company", "type", "exchange", "symbol", "officialClose", "ours", "diffPercent", "status", "source", "date"]
    with open(OUT / "price-check.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
