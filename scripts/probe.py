"""Temporary probe: Groww page layout, Yahoo chart API, Groww instrument list."""
import json, pathlib, requests, io
out = pathlib.Path("reports/probe"); out.mkdir(parents=True, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
res = {}
for name, url in [("ipo", "https://groww.in/ipo"), ("subscription", "https://groww.in/ipo/subscription")]:
    r = requests.get(url, headers=H, timeout=40); res[name] = r.status_code
    (out / f"{name}.html").write_text(r.text)
for sym in ["RELIANCE.NS", "JPL.NS", "TONBO.NS", "HDFIRE.NS"]:
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=3mo&interval=1d", headers=H, timeout=30)
        j = r.json(); m = (j.get("chart", {}).get("result") or [{}])[0].get("meta", {})
        res[sym] = {"status": r.status_code, "price": m.get("regularMarketPrice"), "name": m.get("longName"), "err": j.get("chart", {}).get("error")}
    except Exception as e:
        res[sym] = str(e)[:200]
r = requests.get("https://query1.finance.yahoo.com/v1/finance/search?q=Tonbo%20Imaging&quotesCount=5", headers=H, timeout=30)
res["yahooSearch"] = [(q.get("symbol"), q.get("longname")) for q in r.json().get("quotes", [])] if r.ok else r.status_code
import pandas as pd
inst = pd.read_csv("https://growwapi-assets.groww.in/instruments/instrument.csv", dtype=str, low_memory=False)
res["instCols"] = list(inst.columns)
cash = inst[inst.segment == "CASH"]
res["instSample"] = cash[cash.name.str.contains("TONBO|ZETWERK|SAHAJANAND|BONFIGLIOLI|JIO PLAT", case=False, na=False)][["exchange","trading_symbol","name","series","isin"]].to_dict("records")
(out / "result.json").write_text(json.dumps(res, indent=2, default=str))
print(json.dumps(res, indent=2, default=str)[:3000])
