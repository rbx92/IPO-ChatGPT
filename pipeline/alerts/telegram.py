#!/usr/bin/env python3
"""Telegram alert when a stock enters the pullback buy zone.

Same rule as the dashboard's pullback message (eligibility-rules.json,
pullback_signal): QIB and listing-gain minimums, listed within the day limit,
15-30% below its highest close so far, and not below its first day's close.

One message per stock per high: once alerted, the stock alerts again only
after it makes a new high and falls back into the zone. Sent alerts are
remembered in data/alerts_sent.json.

Needs repository secrets TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID; without
them it prints what it would send and exits quietly.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # pipeline/
from common.helpers import load_json, parse_date  # noqa: E402
from common.paths import DATA, IPOS  # noqa: E402
from common.rules import ELIGIBILITY_CONFIG  # noqa: E402
from prices.screener_history import is_candidate  # noqa: E402

SENT = DATA / "alerts_sent.json"
RULE = ELIGIBILITY_CONFIG["pullback_signal"]
SITE = "https://rbx92.github.io/IPO-ChatGPT/"


def pullback(row):
    """(fall %, trading days since peak, peak date, volume note) or None."""
    h = sorted((e for e in row.get("priceHistory") or [] if e.get("close")), key=lambda e: e["date"])
    listed = parse_date(str(row.get("listingDate") or "").strip())
    if len(h) < 2 or not listed:
        return None
    if abs((datetime.fromisoformat(h[0]["date"]).date() - listed).days) > 2:
        return None  # history does not start at listing: first-day close unknown
    peak = max(range(len(h)), key=lambda i: h[i]["close"])
    days = len(h) - 1 - peak
    last = h[-1]["close"]
    fall = (h[peak]["close"] - last) / h[peak]["close"] * 100
    if days < 1 or not RULE["min_fall_percent"] <= fall <= RULE["max_fall_percent"]:
        return None
    if RULE.get("require_above_listing_day_close") and last < h[0]["close"]:
        return None
    down = total = 0
    for i in range(peak + 1, len(h)):
        v = h[i].get("volume") or 0
        total += v
        if h[i]["close"] < h[i - 1]["close"]:
            down += v
    note = ""
    if total:
        share = round(down / total * 100)
        kind = "heavy" if share >= 65 else "light" if share <= 45 else "mixed"
        note = f"{kind.capitalize()} selling: {share}% of volume since the peak on down days"
    return fall, days, h[peak]["date"], note


def send(token, chat, text):
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                      json={"chat_id": chat, "text": text, "disable_web_page_preview": True})
    if not r.ok:
        raise RuntimeError(f"Telegram refused the message: HTTP {r.status_code} {r.text[:200]}")


def main():
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    rows = json.loads(IPOS.read_text(encoding="utf-8"))
    sent = load_json(SENT, {})
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    new = []
    for row in rows:
        if not is_candidate(row, today):
            continue
        p = pullback(row)
        if not p:
            continue
        fall, days, peak_date, note = p
        if sent.get(row["companyName"]) == peak_date:
            continue  # already alerted for this high
        new.append((row, fall, days, peak_date, note))

    for row, fall, days, peak_date, note in new:
        cmp_ = row.get("currentPrice")
        text = (f"{row['companyName']} ({row.get('stockType', '')}) entered the buy zone\n"
                f"Down {fall:.0f}% from its high over {days} trading day{'s' if days != 1 else ''}"
                f"{f', CMP ₹{cmp_}' if cmp_ else ''}\n"
                f"QIB {row.get('qib')}, listing gain {row.get('listingGain')}\n"
                f"{note + chr(10) if note else ''}{SITE}")
        if token and chat:
            send(token, chat, text)
            print(f"Sent: {row['companyName']}")
        else:
            print(f"Would send (no Telegram secrets yet):\n{text}\n")
        sent[row["companyName"]] = peak_date

    if token and chat:
        SENT.write_text(json.dumps(sent, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Pullback alerts: {len(new)} new.")


if __name__ == "__main__":
    main()
