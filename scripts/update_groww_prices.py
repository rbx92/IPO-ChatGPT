#!/usr/bin/env python3
"""Groww-only CMP updater for IPO Lens.

Uses Groww's authenticated market-data API for CMP. It never calls Screener for CMP,
never fuzzy-matches company names, and only changes current-price-related fields.
The complete historical dataset is always retained in ipos.json and data.js.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ipos.json"
DATA_JS_PATH = ROOT / "data.js"
MAP_PATH = ROOT / "groww_map.json"
INSTRUMENTS_URL = "https://growwapi-assets.groww.in/instruments/instrument.csv"
TIMEOUT = 30
FINANCIAL_NAME = re.compile(
    r"\b(?:bank|banking|finance|financial|nbfc|broker|broking|securities|asset|capital|"
    r"trusteeship|insurance|wealth|lending|credit|microfinance|investments?|fund)\b", re.I)
PHARMA_NAME = re.compile(r"\b(?:pharma|pharmaceuticals?|biopharma|biotechnology|biotech)\b", re.I)
EXPLICIT_FINANCIAL_COMPANIES = {
    "icici prudential asset", "moneyview", "rikhav securities",
    "beacon trusteeship", "pune e stock broking", "dam capital advisors",
    "manba finance", "northern arc capital", "bajaj housing finance",
    "rnfi services", "one mobikwik systems",
}
EXCLUDED_COMPANIES = {"nacdac infrastructure"}
LEGAL_SUFFIXES = {"limited", "ltd", "plc", "pvt", "private", "company", "co"}


def normalize_name(value: str) -> str:
    value = str(value or "").casefold().replace("&", " and ")
    words = re.sub(r"[^a-z0-9]+", " ", value).split()
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def number_value(value):
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*%?\s*", str(value or ""))
    return float(match.group(1)) if match else None


def multiple_value(value):
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*x?\s*", str(value or ""), re.I)
    return float(match.group(1)) if match else None


def qualifies(row):
    qib = multiple_value(row.get("qib"))
    listing_gain = number_value(row.get("listingGain"))
    name = str(row.get("companyName") or "")
    normalized = normalize_name(name)
    return (
        qib is not None and qib >= 50
        and listing_gain is not None and listing_gain >= 15
        and not FINANCIAL_NAME.search(name)
        and not PHARMA_NAME.search(name)
        and not any(normalized == excluded or normalized.startswith(excluded + " ")
                    for excluded in EXPLICIT_FINANCIAL_COMPANIES)
        and normalized not in EXCLUDED_COMPANIES
    )


def parse_instruments_csv(text: str):
    """Return exact normalized company-name matches and a symbol lookup."""
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise RuntimeError("Groww instruments CSV has no header row")
    headers = {str(header).strip().casefold(): header for header in reader.fieldnames}
    required = {"exchange", "trading_symbol", "name", "segment"}
    if not required.issubset(headers):
        raise RuntimeError("Groww instruments CSV schema changed; required columns missing")
    by_name = {}
    by_symbol = {}
    for raw in reader:
        row = {str(k).strip().casefold(): str(v or "").strip() for k, v in raw.items() if k is not None}
        exchange = row.get("exchange", "").upper()
        segment = row.get("segment", "").upper()
        symbol = row.get("trading_symbol", "").strip()
        company = row.get("name", "").strip()
        if segment != "CASH" or exchange not in {"NSE", "BSE"} or not symbol:
            continue
        item = {
            "exchange": exchange,
            "trading_symbol": symbol,
            "exchange_trading_symbol": f"{exchange}_{symbol}",
            "name": company,
            "series": row.get("series", ""),
            "isin": row.get("isin", ""),
        }
        by_symbol[item["exchange_trading_symbol"]] = item
        normalized = normalize_name(company)
        if normalized and normalized not in {"nan", "none"}:
            by_name.setdefault(normalized, []).append(item)
    return by_name, by_symbol


def resolve_instrument(company_name, stock_type, by_name, by_symbol, overrides):
    """Resolve an exact Groww instrument; ambiguous or absent matches are never guessed."""
    override = overrides.get(company_name)
    if override:
        if not isinstance(override, dict):
            return None, "INVALID_OVERRIDE"
        exchange = str(override.get("exchange", "")).upper()
        symbol = str(override.get("trading_symbol", "")).strip()
        key = f"{exchange}_{symbol}"
        item = by_symbol.get(key)
        return (item, "OVERRIDE") if item else (None, "INVALID_OVERRIDE_SYMBOL")

    candidates = by_name.get(normalize_name(company_name), [])
    # The same company may be listed on both exchanges. Prefer NSE when both rows
    # use the same trading symbol; otherwise require an explicit reviewed override.
    unique_symbols = {item["trading_symbol"] for item in candidates}
    if not candidates:
        return None, "NO_EXACT_NAME_MATCH"
    if len(unique_symbols) > 1:
        return None, "AMBIGUOUS_EXCHANGE_SYMBOL"
    preferred_exchange = "NSE" if any(x["exchange"] == "NSE" for x in candidates) else "BSE"
    selected = next((x for x in candidates if x["exchange"] == preferred_exchange), candidates[0])
    return selected, "EXACT_NAME_MATCH"


def fetch_instruments():
    request = Request(INSTRUMENTS_URL, headers={"User-Agent": "IPO-Lens-Groww-CMP/1.0"})
    with urlopen(request, timeout=TIMEOUT) as response:
        text = response.read().decode("utf-8-sig", errors="replace")
    return parse_instruments_csv(text)


def create_groww_client():
    api_key = os.environ.get("GROWW_TOTP_TOKEN", "").strip()
    totp_secret = os.environ.get("GROWW_TOTP_SECRET", "").strip()
    if not api_key or not totp_secret:
        raise RuntimeError(
            "Groww CMP is not configured. Add repository Actions secrets "
            "GROWW_TOTP_TOKEN and GROWW_TOTP_SECRET (active Groww Trading API subscription required)."
        )
    try:
        import pyotp
        from growwapi import GrowwAPI
    except ImportError as exc:
        raise RuntimeError("Groww API dependencies missing; install growwapi and pyotp") from exc
    totp = pyotp.TOTP(totp_secret).now()
    access_token = GrowwAPI.get_access_token(api_key=api_key, totp=totp)
    if not access_token:
        raise RuntimeError("Groww authentication returned an empty access token")
    return GrowwAPI(access_token)


def extract_ltp_response(response):
    if not isinstance(response, dict):
        raise RuntimeError("Groww LTP response was not a JSON object")
    prices = {}
    for symbol, value in response.items():
        if isinstance(value, dict):
            value = value.get("ltp", value.get("last_price", value.get("price")))
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            prices[str(symbol)] = price
    return prices


def save_dataset(rows, mapping):
    DATA_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DATA_JS_PATH.write_text(
        "window.IPO_DATA = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    MAP_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0, help="zero-based offset among eligible IPOs")
    parser.add_argument("--limit", type=int, default=0, help="eligible IPOs to process; 0 means all remaining")
    parser.add_argument("--batch-size", type=int, default=50, help="maximum instruments per Groww LTP request")
    parser.add_argument("--delay", type=float, default=1, help="seconds between LTP batches")
    parser.add_argument("--dry-run", action="store_true", help="fetch prices but do not write files")
    args = parser.parse_args()
    if args.start < 0 or args.limit < 0 or args.batch_size < 1 or args.batch_size > 50 or args.delay < 0:
        parser.error("start/limit must be >= 0, batch-size must be 1-50, and delay must be >= 0")

    rows = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("ipos.json must contain a JSON list")
    original_count = len(rows)
    eligible = [(index, row) for index, row in enumerate(rows) if qualifies(row)]
    if eligible and args.start >= len(eligible):
        parser.error(f"start must be less than {len(eligible)} eligible IPOs")
    if not eligible and args.start:
        parser.error("start must be 0 when there are no eligible IPOs")
    selected = eligible[args.start:args.start + args.limit] if args.limit else eligible[args.start:]

    by_name, by_symbol = fetch_instruments()
    mapping = json.loads(MAP_PATH.read_text(encoding="utf-8")) if MAP_PATH.exists() else {}
    resolved = []
    unmatched = 0
    for index, row in selected:
        name = str(row.get("companyName") or "").strip()
        instrument, status = resolve_instrument(name, row.get("stockType", ""), by_name, by_symbol, mapping)
        if not instrument:
            unmatched += 1
            print(f"UNMATCHED — {name}: {status}; existing price preserved", flush=True)
            continue
        resolved.append((index, row, instrument))
        mapping[name] = {"exchange": instrument["exchange"], "trading_symbol": instrument["trading_symbol"]}

    print(
        f"Groww-only CMP. Historical rows: {original_count}; eligible: {len(eligible)}; "
        f"selected: {len(selected)}; exact/overridden symbol matches: {len(resolved)}; "
        f"unmatched: {unmatched}. Mainboard and SME both use Groww market data.",
        flush=True,
    )
    if not resolved:
        print("No mapped instruments to update; no dataset writes performed.", flush=True)
        return 0

    client = create_groww_client()
    updated = 0
    stamp = datetime.now().astimezone().isoformat(timespec="minutes")
    for offset in range(0, len(resolved), args.batch_size):
        batch = resolved[offset:offset + args.batch_size]
        symbols = tuple(item[2]["exchange_trading_symbol"] for item in batch)
        try:
            prices = extract_ltp_response(
                client.get_ltp(segment=client.SEGMENT_CASH, exchange_trading_symbols=symbols)
            )
        except Exception as exc:
            if not args.dry_run and updated:
                save_dataset(rows, mapping)
            print(f"GROWW UPDATE STOPPED: {exc}", file=sys.stderr, flush=True)
            print(f"Completed prices before failure: {updated}; historical rows retained: {len(rows)}", file=sys.stderr, flush=True)
            return 2

        for index, row, instrument in batch:
            key = instrument["exchange_trading_symbol"]
            price = prices.get(key)
            name = row.get("companyName", "")
            if price is None:
                unmatched += 1
                print(f"NO_LTP — {name} ({key}); existing price preserved", flush=True)
                continue
            issue = number_value(row.get("issuePrice"))
            gain = f"{((price - issue) / issue * 100):.1f}%" if issue and issue > 0 else "-"
            print(f"{name}: Groww CMP ₹{price:g} | current gain {gain}", flush=True)
            if not args.dry_run:
                row["currentPrice"] = round(price, 2)
                row["currentGain"] = gain
                row["priceUpdatedAt"] = stamp
                row["priceSource"] = "Groww"
                row["growwExchange"] = instrument["exchange"]
                row["growwTradingSymbol"] = instrument["trading_symbol"]
            updated += 1

        if not args.dry_run:
            save_dataset(rows, mapping)
        print(f"Saved batch. Updated: {updated}; unmatched/preserved: {unmatched}.", flush=True)
        if offset + args.batch_size < len(resolved) and args.delay:
            time.sleep(args.delay)

    if len(rows) != original_count:
        raise RuntimeError("Historical dataset row count changed unexpectedly")
    action = "DRY RUN COMPLETE" if args.dry_run else "UPDATE COMPLETE"
    print(f"{action}: {updated} Groww CMP prices updated; {unmatched} unmatched; all {original_count} historical IPO records retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
