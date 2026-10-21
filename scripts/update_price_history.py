#!/usr/bin/env python3
"""Backfill and maintain daily closing-price history for recent IPO glow candidates.

Uses Yahoo Finance's publicly accessible chart/search endpoints. This is an
unofficial data interface; failures and ambiguous symbol matches are skipped.
Existing IPO records and unrelated fields are preserved.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ipos.json"
DATA_JS_PATH = ROOT / "data.js"
BASE = "https://query1.finance.yahoo.com"
USER_AGENT = "Mozilla/5.0 (compatible; IPO-Lens-history/1.0)"
TIMEOUT = 25
MAX_AGE_DAYS = 60
QIB_MIN = 50.0
LISTING_GAIN_MIN = 25.0


def get_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"request failed ({type(exc).__name__}): {exc}") from exc


def number(value) -> float | None:
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else None


def normalized(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"\b(limited|ltd|india|industries|industry|company|co)\b", " ", value)
    return re.sub(r"[^a-z0-9]", "", value)


def candidate(row: dict, today: date) -> bool:
    try:
        listed = date.fromisoformat(str(row.get("listingDate", ""))[:10])
    except ValueError:
        return False
    age = (today - listed).days
    qib = number(row.get("qib"))
    gain = number(row.get("listingGain"))
    return 0 <= age <= MAX_AGE_DAYS and qib is not None and qib >= QIB_MIN and gain is not None and gain >= LISTING_GAIN_MIN


def resolve_symbol(name: str) -> str | None:
    payload = get_json(f"{BASE}/v1/finance/search?q={quote(name)}&quotesCount=10&newsCount=0")
    target = normalized(name)
    candidates = []
    for item in payload.get("quotes", []):
        symbol = item.get("symbol", "")
        if not symbol.endswith((".NS", ".BO")):
            continue
        if item.get("quoteType") != "EQUITY":
            continue
        names = [item.get("longname", ""), item.get("shortname", "")]
        scores = []
        for candidate_name in names:
            cleaned = normalized(candidate_name)
            if not cleaned:
                continue
            if cleaned == target:
                scores.append(1.0)
            else:
                target_tokens = set(re.findall(r"[a-z0-9]+", name.casefold()))
                cand_tokens = set(re.findall(r"[a-z0-9]+", candidate_name.casefold()))
                ignored = {"limited", "ltd", "india", "the", "and"}
                target_tokens -= ignored
                cand_tokens -= ignored
                scores.append(len(target_tokens & cand_tokens) / max(1, len(target_tokens | cand_tokens)))
        score = max(scores or [0])
        if score >= 0.72:
            candidates.append((score, symbol))
    if not candidates:
        return None
    best_score = max(score for score, _ in candidates)
    best_symbols = sorted({symbol for score, symbol in candidates if score == best_score})
    # Multiple distinct symbols at the same match score are ambiguous: do not guess.
    return best_symbols[0] if len(best_symbols) == 1 else None


def fetch_history(symbol: str, start_date: date, today: date) -> list[dict]:
    period1 = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    period2 = int(datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    url = f"{BASE}/v8/finance/chart/{quote(symbol, safe='')}?period1={period1}&period2={period2}&interval=1d&events=history"
    payload = get_json(url)
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        error = payload.get("chart", {}).get("error")
        raise RuntimeError(f"no chart result: {error}")
    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quotes.get("close") or []
    history = []
    for stamp, close in zip(timestamps, closes):
        if close is None:
            continue
        trading_day = datetime.fromtimestamp(stamp, timezone.utc).date().isoformat()
        history.append({"date": trading_day, "close": round(float(close), 4)})
    return history


def main() -> int:
    today = datetime.now(timezone.utc).date()
    rows = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("ipos.json must contain a JSON list")
    targets = [(row, date.fromisoformat(str(row["listingDate"])[:10])) for row in rows if candidate(row, today)]
    print(f"Recent glow-candidate pool: {len(targets)} IPOs (QIB >= {QIB_MIN:g}x, listing gain >= {LISTING_GAIN_MIN:g}%, age <= {MAX_AGE_DAYS} days).", flush=True)
    changed = 0
    unresolved = 0
    for index, (row, listed) in enumerate(targets, 1):
        name = str(row.get("companyName", "")).strip()
        try:
            symbol = row.get("yahooSymbol")
            if not symbol:
                symbol = resolve_symbol(name)
                if not symbol:
                    unresolved += 1
                    print(f"[{index}/{len(targets)}] UNRESOLVED — {name}; no confident Yahoo symbol match", flush=True)
                    continue
                row["yahooSymbol"] = symbol
            history = fetch_history(symbol, listed, today)
            if not history:
                print(f"[{index}/{len(targets)}] NO DATA — {name} ({symbol})", flush=True)
                continue
            old_history = row.get("priceHistory")
            if old_history != history or row.get("priceHistorySource") != "Yahoo Finance":
                row["priceHistory"] = history
                row["priceHistorySource"] = "Yahoo Finance"
                row["priceHistoryUpdatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                changed += 1
            peak = max(item["close"] for item in history)
            latest = history[-1]["close"]
            pullback = (peak - latest) / peak * 100 if peak else 0
            print(f"[{index}/{len(targets)}] OK — {name}: {len(history)} closes; peak {peak:.2f}; latest {latest:.2f}; pullback {pullback:.1f}%", flush=True)
        except Exception as exc:
            print(f"[{index}/{len(targets)}] ERROR — {name}: {exc}", flush=True)
        # Keep the public endpoint load low and avoid burst requests.
        time.sleep(1.0)

    if changed:
        DATA_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        DATA_JS_PATH.write_text("window.IPO_DATA = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Updated historical series for {changed} IPOs; unresolved symbols: {unresolved}; dataset records preserved: {len(rows)}.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
