"""One-off lookup for stocks missing from the official close files."""
import json, sys, pathlib, time, requests, pandas as pd
sys.path.insert(0, "scripts")
from update_prices_official import fetch_day, words
from datetime import date, timedelta
names = ["Goldline Pharmaceutical","Defrail Technologies","E to E Transportation","HyTech Engineers","IndoMIM",
         "HRS Aluglaze","Sheel Biotech","Sat Kartar Shopping","Standard Glass Lining","Dhanlaxmi Crop Science",
         "Shiv Texchem","Mach Conferences and Events","Aesthetik Engineers","Manglam Infra","Chetana Education","Ambey Laboratories"]
inst = pd.read_csv("https://growwapi-assets.groww.in/instruments/instrument.csv", dtype=str, low_memory=False)
inst = inst[inst.segment == "CASH"]
days, d = {}, date(2026, 11, 6)
while len(days) < 15:
    if d.weekday() < 5:
        rows = fetch_day(d)
        if rows: days[d.isoformat()] = rows
    d -= timedelta(days=1)
H = {"User-Agent": "Mozilla/5.0"}
out = {}
for n in names:
    first = words(n)[0]
    g = inst[inst.name.fillna("").str.lower().str.contains(first, regex=False)][["exchange","trading_symbol","name","series","isin"]]
    isins = set(g["isin"].dropna())
    seen = {}
    for day, rows in days.items():
        for sym, isin, nm, close, ex in rows:
            if isin in isins or first in nm.lower():
                seen.setdefault(isin, {"symbol": sym, "name": nm, "ex": ex, "days": []})["days"].append((day, close))
    ys = requests.get(f"https://query1.finance.yahoo.com/v1/finance/search?q={requests.utils.quote(n)}&quotesCount=5", headers=H, timeout=30)
    out[n] = {"groww": g.head(6).to_dict("records"),
              "bhavcopy15d": {k: {**v, "days": v["days"][:3], "count": len(v["days"])} for k, v in list(seen.items())[:6]},
              "yahoo": [(q.get("symbol"), q.get("longname")) for q in ys.json().get("quotes", [])] if ys.ok else ys.status_code}
    time.sleep(1)
pathlib.Path("reports").mkdir(exist_ok=True)
pathlib.Path("reports/probe.json").write_text(json.dumps(out, indent=1, default=str))
