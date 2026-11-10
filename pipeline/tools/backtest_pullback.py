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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # pipeline/
from common.helpers import parse_date  # noqa: E402
from common.paths import IPOS, ISIN_MAP, REPORTS  # noqa: E402
from common.rules import multiple_value, percent_value, qualifies  # noqa: E402
from prices.official import by_isin, fetch_day  # noqa: E402

OUT = REPORTS / "backtest"
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


def signals(s, trigger, days, floor=True, cap=30):
    """Every buy signal within `days` calendar days of listing.

    The high is the highest close so far. A signal fires on the first close
    that is `trigger`% or more below that high (and no more than `cap`% below,
    and at or above the first day's close if `floor`). After a signal, the next
    one needs a new high first.
    """
    listed = date.fromisoformat(s[0][0])
    peak, armed, out = s[0][1], True, []
    for t in range(1, len(s)):
        if (date.fromisoformat(s[t][0]) - listed).days > days:
            break
        close = s[t][1]
        if close > peak:
            peak, armed = close, True
            continue
        fall = (peak - close) / peak * 100
        if armed and fall >= trigger and (cap is None or fall <= cap) and (not floor or close >= s[0][1]):
            out.append((t, fall))
            armed = False
    return out


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
    rows = [r for r in json.loads(IPOS.read_text()) if qualifies(r)]
    isin_map = json.loads(ISIN_MAP.read_text())
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
        "Stocks your rule watches (QIB>=50x, listing gain>=25%)": lambda x: (x["qib"] or 0) >= 50 and (x["lg"] or 0) >= 25,
        "All dashboard IPOs (QIB>=10x, listing gain>=15%)": lambda x: True,
    }
    variants = [  # (label, trigger, days, floor, cap)
        ("YOUR RULE: 15% fall, 100 days, above first-day close, cap 30%", 15, 100, True, 30),
        ("Same, 20% fall", 20, 100, True, 30),
        ("Same, 25% fall", 25, 100, True, 30),
        ("15% fall, no first-day-close floor", 15, 100, False, 30),
        ("15% fall, no 30% cap", 15, 100, True, None),
        ("15% fall, 60 days only", 15, 60, True, 30),
    ]

    trades_out, md = [], []
    md.append("# Pullback rule backtest\n")
    md.append(f"Official NSE/BSE daily closes, {START} to {max(hist['days'])}. "
              f"{len(stocks)} IPOs with usable history. Returns are close to close, before costs and taxes.\n")
    md.append("A signal fires on the first close at least X% below the highest close so far, within the day limit "
              "after listing. After a signal, the stock must make a new high before it can signal again. "
              "Returns are measured from the signal day's close. 250 trading days is about a year.\n")
    md.append("Past results do not guarantee future returns.\n")

    def row(label, outs, n):
        cells = []
        for h in HORIZONS:
            med, up, k = stats([o[h] for o in outs])
            cells.append(f" {med} / {up} (n={k}) |")
        wmed, _, _ = stats([o["worst60"] for o in outs])
        md.append(f"| {label} | {n} |" + "".join(cells) + f" {wmed} |")

    header = ("| Strategy | Signals |" + "".join(f" After {h} days: median / % higher |" for h in HORIZONS)
              + " Further fall in next 60 days (median) |")
    sep = "|---|---|" + "---|" * len(HORIZONS) + "---|"
    for gname, gfilter in groups.items():
        for typ in (None, "SME", "Mainboard"):
            universe = [x for x in stocks if gfilter(x) and (typ is None or x["type"] == typ)]
            md.append(f"\n## {gname}{' - ' + typ if typ else ''}: {len(universe)} IPOs\n")
            md.append(header)
            md.append(sep)
            row("Buy at first-day close (comparison)", [outcomes(x["s"], 0) for x in universe], len(universe))
            for label, trig, days, floor, cap in variants:
                outs = []
                for x in universe:
                    for t, fall in signals(x["s"], trig, days, floor, cap):
                        o = outcomes(x["s"], t)
                        outs.append(o)
                        if typ is None and gname.startswith("Stocks") and label.startswith("YOUR"):
                            trades_out.append({"company": x["name"], "type": x["type"], "signalDate": x["s"][t][0],
                                               "close": x["s"][t][1], "fallFromHigh": round(fall, 1),
                                               "daysAfterListing": t, "firstDayClose": x["s"][0][1],
                                               **{f"ret{h}d": None if o[h] is None else round(o[h], 1) for h in HORIZONS},
                                               "furtherFall60d": None if o["worst60"] is None else round(o["worst60"], 1),
                                               "toLatest": round(o["latest"], 1)})
                row(label, outs, len(outs))

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
