#!/usr/bin/env python3
"""Read-only Groww instrument mapping validation for every historical IPO."""
import csv
import json
import sys
from pathlib import Path
from update_groww_prices import DATA_PATH, MAP_PATH, fetch_instruments, resolve_instrument

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "groww-mapping-validation.json"
REPORT_CSV = ROOT / "groww-mapping-validation.csv"


def main():
    rows = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    mapping = json.loads(MAP_PATH.read_text(encoding="utf-8")) if MAP_PATH.exists() else {}
    by_name, by_symbol = fetch_instruments()
    report = []
    for row in rows:
        name = str(row.get("companyName") or "").strip()
        stock_type = str(row.get("stockType") or "MISSING").strip()
        instrument, status = resolve_instrument(name, stock_type, by_name, by_symbol, mapping)
        report.append({
            "company": name,
            "ipo_type": stock_type,
            "matched_exchange": instrument["exchange"] if instrument else "",
            "trading_symbol": instrument["trading_symbol"] if instrument else "",
            "groww_symbol": instrument["exchange_trading_symbol"] if instrument else "",
            "status": status,
        })
    with REPORT_JSON.open("w", encoding="utf-8") as f:
        json.dump({
            "provider": "Groww Trading API instrument master",
            "historical_records": len(rows),
            "unique_company_names": len({r.get("companyName") for r in rows}),
            "mainboard_records": sum(1 for r in report if r["ipo_type"].casefold() == "mainboard"),
            "sme_records": sum(1 for r in report if r["ipo_type"].casefold() == "sme"),
            "matched": sum(1 for r in report if r["status"] in {"EXACT_NAME_MATCH", "OVERRIDE"}),
            "unmatched": sum(1 for r in report if r["status"] not in {"EXACT_NAME_MATCH", "OVERRIDE"}),
            "results": report,
        }, f, ensure_ascii=False, indent=2)
    with REPORT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["company", "ipo_type", "matched_exchange", "trading_symbol", "groww_symbol", "status"])
        writer.writeheader()
        writer.writerows(report)
    matched = sum(1 for r in report if r["status"] in {"EXACT_NAME_MATCH", "OVERRIDE"})
    unmatched = len(report) - matched
    print(f"Groww mapping validation: {len(rows)} historical records; {matched} matched; {unmatched} unresolved.")
    print(f"Mainboard: {sum(1 for r in report if r['ipo_type'].casefold() == 'mainboard')}; SME: {sum(1 for r in report if r['ipo_type'].casefold() == 'sme')}.")
    print("Read-only validation: no IPO prices, source records, or mappings were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
