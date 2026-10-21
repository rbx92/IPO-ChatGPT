#!/usr/bin/env python3
"""Record one daily Screener.in closing-price snapshot for every listed IPO.

Only listed IPOs are tracked. This does not bypass HTTP denial or rate limits.
The historical price log is retained in ipos.json as priceHistory entries and
is mirrored to data.js for the dashboard. Run after market close.
"""
from __future__ import annotations
import json, re, sys, time
from datetime import datetime, date
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"ipos.json"
DATA_JS=ROOT/"data.js"
MAP=ROOT/"screener_map.json"
BASE="https://www.screener.in"
UA="IPO-Lens-price-history/1.0"
TIMEOUT=20

def get_text(url):
    req=Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/json;q=0.9,*/*;q=0.8","Accept-Language":"en-IN,en;q=0.9","Referer":BASE+"/"})
    try:
        with urlopen(req,timeout=TIMEOUT) as resp: return resp.read().decode("utf-8",errors="replace")
    except HTTPError as exc:
        if exc.code in (401,403,429):
            raise RuntimeError(f"Screener denied/throttled request (HTTP {exc.code}); stopping without bypassing restriction") from exc
        raise RuntimeError(f"Screener HTTP {exc.code}") from exc
    except URLError as exc: raise RuntimeError(f"Network error: {exc.reason}") from exc

def norm(s):
    return re.sub(r"[^a-z0-9]","",re.sub(r"\b(limited|ltd|india|industries|industry|company|co)\b"," ",str(s).casefold()))

class PriceParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.li=0; self.span=0; self.cls=""; self.txt=[]; self.litxt=[]; self.spans=[]; self.prices=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="li":
            self.li+=1
            if self.li==1: self.litxt=[]; self.spans=[]
        if tag=="span": self.span+=1; self.cls=a.get("class",""); self.txt=[]
    def handle_data(self,data):
        t=data.strip()
        if t:
            if self.li: self.litxt.append(t)
            if self.span: self.txt.append(t)
    def handle_endtag(self,tag):
        if tag=="span" and self.span:
            self.spans.append((self.cls," ".join(self.txt))); self.span-=1; self.cls=""; self.txt=[]
        if tag=="li" and self.li:
            if self.li==1 and "current price" in " ".join(self.litxt).casefold():
                vals=[v for c,v in self.spans if set(c.split()) & {"number","value"}]
                for v in vals or [" ".join(self.litxt)]:
                    m=re.search(r"(?:₹\s*)?([0-9][0-9,]*(?:\.[0-9]+)?)",v)
                    if m:
                        n=float(m.group(1).replace(",",""))
                        if n>0:self.prices.append(n)
                        break
            self.li-=1

def resolve(name):
    data=json.loads(get_text(BASE+"/api/company/search/?q="+quote_plus(name)))
    target=norm(name)
    found={x["url"].split("?",1)[0] for x in data if isinstance(x,dict) and isinstance(x.get("name"),str) and norm(x["name"])==target and isinstance(x.get("url"),str) and x["url"].startswith("/company/")}
    return next(iter(found)) if len(found)==1 else None

def current_price(path):
    p=PriceParser(); p.feed(get_text(BASE+path))
    if not p.prices: raise RuntimeError("No labelled current price parsed for "+path)
    return round(p.prices[0],2)

def main():
    today=date.today().isoformat()
    rows=json.loads(DATA.read_text(encoding="utf-8"))
    paths=json.loads(MAP.read_text(encoding="utf-8")) if MAP.exists() else {}
    listed=[]
    for i,r in enumerate(rows):
        try: d=date.fromisoformat(str(r.get("listingDate",""))[:10])
        except ValueError: continue
        if d<=date.today() and not r.get("isOpen") and str(r.get("stage","")).casefold() not in {"open","waiting","waiting for listing"}:
            listed.append((i,r))
    updated=0; failed=[]
    for n,(i,r) in enumerate(listed):
        name=str(r.get("companyName","")).strip()
        try:
            path=paths.get(name)
            if not path:
                path=resolve(name)
                if path: paths[name]=path
                time.sleep(2)
            if not path: raise RuntimeError("No exact Screener company match")
            price=current_price(path)
            # Avoid repeated intraday snapshots for the same calendar date.
            history=r.setdefault("priceHistory",[])
            if not isinstance(history,list): history=[]; r["priceHistory"]=history
            previous=next((p for p in history if isinstance(p,dict) and p.get("date")==today),None)
            entry={"date":today,"close":price}
            if previous is None: history.append(entry)
            else: previous.update(entry)
            history.sort(key=lambda p:str(p.get("date","")))
            r["currentPrice"]=price
            issue=float(r.get("issuePrice") or 0)
            if issue>0:r["currentGain"]=f"{((price-issue)/issue*100):.1f}%"
            r["priceUpdatedAt"]=datetime.now().astimezone().isoformat(timespec="minutes")
            r["priceSource"]="Screener.in"
            r["priceHistorySource"]="Screener.in"
            updated+=1
            print(f"OK {name}: ₹{price} ({today})",flush=True)
            time.sleep(3)
        except Exception as exc:
            failed.append(f"{name}: {exc}")
            print(f"SKIP {name}: {exc}",file=sys.stderr,flush=True)
            if "denied/throttled" in str(exc): break
    DATA.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    DATA_JS.write_text("window.IPO_DATA = "+json.dumps(rows,ensure_ascii=False,separators=(",",":"))+";\n",encoding="utf-8")
    MAP.write_text(json.dumps(paths,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Finished: {updated}/{len(listed)} listed IPO prices saved; {len(failed)} skipped.")
    return 0 if not failed else 1
if __name__=="__main__": raise SystemExit(main())
