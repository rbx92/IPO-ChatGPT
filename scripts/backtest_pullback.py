#!/usr/bin/env python3
"""Backtest the post-listing pullback rule on past IPOs using official closes.

1. Builds daily official closes (NSE/BSE bhavcopy) for every IPO in
   isin_map.json since 8 Jul 2024 (the exchanges' current file format),
   cached in reports/backtest/history.json so reruns only fetch new days.
2. Replays the rule: buy at the close of the first day a stock has fallen
   X% from its highest close since listing, within W trading days of
   listing, optionally only if still at or above the issue price.
3. Measures returns 20/60/120/250 trading days later and the worst further
   fall in the next 60 days, against simply buying at the listing-day close.

Writes reports/backtest/summary.md and reports/backtest/trades.csv.
"""
import csv
import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rules import multiple_value, percent_value, qualifies  # noqa: E402
from update_ipo_lifecycle import parse_date  # noqa: E402
from update_prices_official import by_isin, fetch_day  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "backtest"
HIST = OUT / "history.json"
START = date(2024, 7, 8)
HORIZONS = (20, 60, 120, 250)


def build_history(isins):
    OUT.mkdir(parents=True, exist_ok=True)
    hist = json.loads(HIST.read_text()) if HIST.exists() else {"days": {}, "holidays": []}
    end = date.today() - timedelta(days=1)
    d, fetched = START, 0
    while d <= end:
        key = d.isoformat()
        if d.weekday() < 5 and key not in hist["days"] and key not in hist["holidays"]:
            rows = fetch_day(d)
            if rows:
                hist["days"][key] = by_isin(rows, isins)
                fetched += 1
                if fetched % 25 == 0:
                    print(f"  fetched {fetched} days, at {key}", flush=True)
                    HIST.write_text(json.dumps(hist, separators=(",", ":")))
            elif d < end - timedelta(days=3):
                hist["holidays"].append(key)
        d += timedelta(days=1)
    # backfill ISINs added later for days cached earlier: refetch only if missing entirely
    OUT.mkdir(parents=True, exist_ok=True)
    HIST.write_text(json.dumps(hist, separators=(",", ":")))
    print(f"History: {len(hist['days'])} trading days ({fetched} new).")
    return hist


def series_for(isin, listed, hist):
    days = sorted(k for k in hist["days"] if k >= listed)
    return [(k, hist["days"][k][isin][0]) for k in days if isin in hist["days"][k]]


def ret(a, b):
    return (b - a) / a * 100


def simulate(s, issue, trigger, window, above_floor):
    """above_floor: only enter if the close is at or above the listing-day close."""
    peak = s[0][1]
    for t in range(1, len(s)):
        if window and t > window:
            return None
        close = s[t][1]
        peak = max(peak, close)
        fall = (peak - close) / peak * 100
        if fall >= trigger and (not above_floor or close >= s[0][1]):
            return t, fall
    return None


def outcomes(s, t):
    entry = s[t][1]
    out = {}
    for h in HORIZONS:
        out[h] = ret(entry, s[t + h][1]) if t + h < len(s) else None
    nxt = [c for _, c in s[t + 1:t + 61]]
    out["worst60"] = ret(entry, min(nxt)) if nxt else None
    out["latest"] = ret(entry, s[-1][1])
    return out


def stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "n/a", "n/a", 0
    return f"{statistics.median(vals):+.1f}%", f"{sum(v > 0 for v in vals) / len(vals) * 100:.0f}%", len(vals)


def main():
    rows = [r for r in json.loads((ROOT / "ipos.json").read_text()) if qualifies(r)]
    isin_map = json.loads((ROOT / "isin_map.json").read_text())
    isins = {isin_map[r["companyName"]] for r in rows if r["companyName"] in isin_map}
    hist = build_history(isins)

    stocks = []
    for r in rows:
        isin = isin_map.get(r["companyName"])
        listed = parse_date(str(r.get("listingDate") or "").strip())
        if not isin or not listed or listed < START:
            continue
        s = series_for(isin, listed.isoformat(), hist)
        if len(s) < 10:
            continue
        issue = float(r.get("issuePrice") or 0) or None
        stocks.append({"name": r["companyName"], "type": r.get("stockType"), "s": s, "issue": issue,
                       "qib": multiple_value(r.get("qib")), "lg": percent_value(r.get("listingGain"))})
    print(f"Stocks with usable history: {len(stocks)}")

    groups = {
        "Your current rule (QIB>=50x, listing gain>=25%)": lambda x: (x["qib"] or 0) >= 50 and (x["lg"] or 0) >= 25,
        "All dashboard IPOs (QIB>=10x, listing gain>=15%)": lambda x: True,
    }
    variants = []
    for trig in (15, 20, 25, 30):
        for window in (40, 120):
            for above in (True, False):
                variants.append((trig, window, above))

    trades_out, md = [], []
    md.append("# Pullback rule backtest\n")
    md.append(f"Official NSE/BSE daily closes, {START} to {max(hist['days'])}. "
              f"{len(stocks)} IPOs with usable history. Returns are close to close, before costs and taxes.\n")
    md.append("Entry: close on the first day the stock is down X% from its highest close since listing, "
              "within W trading days of listing (40 is about 60 calendar days). "
              "'Above listing close' means only if the close is at or above the first trading day's close.\n")
    md.append("Past results do not guarantee future returns.\n")

    for gname, gfilter in groups.items():
        universe = [x for x in stocks if gfilter(x)]
        md.append(f"\n## {gname}: {len(universe)} IPOs\n")
        # baseline: buy listing-day close
        base = [outcomes(x["s"], 0) for x in universe]
        md.append("| Strategy | Trades |" + "".join(f" After {h} days: median / % up |" for h in HORIZONS) + " Worst fall in next 60 days (median) |")
        md.append("|---|---|" + "---|" * len(HORIZONS) + "---|")

        def row(label, outs, n):
            cells = []
            for h in HORIZONS:
                med, up, k = stats([o[h] for o in outs])
                cells.append(f" {med} / {up} (n={k}) |")
            wmed, _, _ = stats([o["worst60"] for o in outs])
            md.append(f"| {label} | {n} |" + "".join(cells) + f" {wmed} |")

        row("Buy at listing-day close", base, len(base))
        for trig, window, above in variants:
            outs = []
            for x in universe:
                hit = simulate(x["s"], x["issue"], trig, window, above)
                if not hit:
                    continue
                t, fall = hit
                o = outcomes(x["s"], t)
                outs.append(o)
                if gname.startswith("All"):
                    trades_out.append({"company": x["name"], "type": x["type"], "trigger": trig, "window": window,
                                       "aboveIssue": above, "entryDate": x["s"][t][0], "entry": x["s"][t][1],
                                       "daysAfterListing": t, **{f"ret{h}": None if o[h] is None else round(o[h], 1) for h in HORIZONS},
                                       "worst60": None if o["worst60"] is None else round(o["worst60"], 1),
                                       "toLatest": round(o["latest"], 1)})
            row(f"Fall {trig}%, within {window}d{', above listing close' if above else ''}", outs, len(outs))

        for typ in ("SME", "Mainboard"):
            sub = [x for x in universe if x["type"] == typ]
            md.append(f"\n**{typ} only ({len(sub)} IPOs), within 40 days, above listing close**\n")
            md.append("| Strategy | Trades |" + "".join(f" After {h} days |" for h in HORIZONS) + " Worst next 60d |")
            md.append("|---|---|" + "---|" * len(HORIZONS) + "---|")
            row("Buy at listing-day close", [outcomes(x["s"], 0) for x in sub], len(sub))
            for trig in (15, 20, 25, 30):
                outs = [outcomes(x["s"], h[0]) for x in sub if (h := simulate(x["s"], x["issue"], trig, 40, True))]
                row(f"Fall {trig}%", outs, len(outs))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.md").write_text("\n".join(md) + "\n")
    if trades_out:
        with open(OUT / "trades.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(trades_out[0].keys()))
            w.writeheader()
            w.writerows(trades_out)
    print("\n".join(md))


if __name__ == "__main__":
    main()
