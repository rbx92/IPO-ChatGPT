#!/usr/bin/env python3
"""Follow-up tests on the pullback rule: selling volume, anchor lock-in dates, later entry.
Run from the repository root after backtest_pullback.py has built reports/backtest/history.json."""
import json, sys, statistics as st
from datetime import date, timedelta
sys.path.insert(0, 'pipeline')
from common.helpers import parse_date
from common.rules import multiple_value, percent_value, qualifies
hist = json.load(open('reports/backtest/history.json'))['days']
days = sorted(hist)
isin_map = json.load(open('data/isin_map.json'))
H = (20, 60, 120, 250)

def series(isin, listed):
    return [(d, hist[d][isin][0], hist[d][isin][1]) for d in days if d >= listed and isin in hist[d]]

def signals(s, trig=15, maxdays=100, mindays=0, floor=True, cap=30):
    listed = date.fromisoformat(s[0][0]); peak, pi, armed, out = s[0][1], 0, True, []
    for t in range(1, len(s)):
        age = (date.fromisoformat(s[t][0]) - listed).days
        if age > maxdays: break
        c = s[t][1]
        if c > peak: peak, pi, armed = c, t, True; continue
        fall = (peak - c) / peak * 100
        if armed and age >= mindays and fall >= trig and fall <= cap and (not floor or c >= s[0][1]):
            out.append((t, pi)); armed = False
    return out

def outcome(s, t):
    e = s[t][1]
    return {h: ((s[t+h][1] - e) / e * 100 if t + h < len(s) else None) for h in H}

def downshare(s, t, pi):
    down = tot = 0
    for i in range(pi + 1, t + 1):
        tot += s[i][2]
        if s[i][1] < s[i-1][1]: down += s[i][2]
    return down / tot * 100 if tot else None

def weekdays_back(d, n):
    k = 0
    while k < n:
        d -= timedelta(days=1)
        if d.weekday() < 5: k += 1
    return d

def near_lockin(s, t, listed):
    allot = weekdays_back(listed, 2); sig = date.fromisoformat(s[t][0])
    return any(abs((sig - (allot + timedelta(days=n))).days) <= 7 for n in (30, 90))

def show(label, outs):
    cells = []
    for h in H:
        v = [o[h] for o in outs if o[h] is not None]
        cells.append(f"{st.median(v):+6.1f}% / {sum(x>0 for x in v)/len(v)*100:3.0f}% (n={len(v)})" if v else "   n/a")
    print(f"  {label:42} {len(outs):3}  " + " | ".join(cells))

stocks = []
for r in json.load(open('ipos.json')):
    if not qualifies(r): continue
    isin = isin_map.get(r['companyName']); listed = parse_date(str(r.get('listingDate') or '').strip())
    if not isin or not listed or listed < date(2024, 7, 8): continue
    s = series(isin, listed.isoformat())
    if len(s) < 10: continue
    stocks.append(dict(name=r['companyName'], s=s, listed=listed, strong=(multiple_value(r.get('qib')) or 0) >= 50 and (percent_value(r.get('listingGain')) or 0) >= 25))

for gname, flt in (("Stocks your rule watches (QIB>=50x, listing gain>=25%)", lambda x: x['strong']), ("All dashboard IPOs", lambda x: True)):
    U = [x for x in stocks if flt(x)]
    print(f"\n{gname}: {len(U)} IPOs")
    print(f"  {'':42} sig   " + " | ".join(f"after {h}d: median / % higher" for h in H))
    base = []; vol = {'heavy': [], 'mixed': [], 'light': []}; lock = {'near': [], 'other': []}
    for x in U:
        for t, pi in signals(x['s']):
            o = outcome(x['s'], t); base.append(o)
            sh = downshare(x['s'], t, pi)
            if sh is not None: vol['heavy' if sh >= 65 else 'light' if sh <= 45 else 'mixed'].append(o)
            lock['near' if near_lockin(x['s'], t, x['listed']) else 'other'].append(o)
    show("Your rule (all signals)", base)
    print("  1. Volume at the signal")
    for k in ('heavy', 'mixed', 'light'): show(f"   {k} selling", vol[k])
    print("  2. Anchor lock-in (signal within 7 days of 30/90-day date)")
    show("   near a lock-in date", lock['near']); show("   other days", lock['other'])
    print("  3. Later entry (same rule, by days since listing)")
    for lo, hi in ((0, 100), (100, 250), (250, 500)):
        show(f"   day {lo}-{hi}", [outcome(x['s'], t) for x in U for t, _ in signals(x['s'], maxdays=hi, mindays=lo)])
