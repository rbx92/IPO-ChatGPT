#!/usr/bin/env python3
"""Read-only Groww instrument mapping validation for every historical IPO."""
import csv
import json
import sys
from pathlib import Path
from update_groww_prices import DATA_PATH, MAP_PATH, ROOT, fetch_instruments, resolve_instrument, qualifies

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "groww-mapping-validation.json"
REPORT_CSV = ROOT / "groww-mapping-validation.csv"


def main():
    rows = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    mapping = json.loads(MAP_PATH.read_text(encoding="utf-8")) if MAP_PATH.exists() else {}
    legacy_path = ROOT / "screener_map.json"
    legacy = json.loads(legacy_path.read_text(encoding="utf-8")) if legacy_path.exists() else {}
    by_name, by_symbol = fetch_instruments()
    report = []
    for row in rows:
        name = str(row.get("companyName") or "").strip()
        stock_type = str(row.get("stockType") or "MISSING").strip()
        instrument, status = resolve_instrument(name, stock_type, by_name, by_symbol, mapping)
        candidate = None
        legacy_path_value = str(legacy.get(name, ""))
        match = __import__("re").search(r"/company/([A-Za-z][A-Za-z0-9_-]*)/", legacy_path_value)
        if not instrument and match:
            ticker = match.group(1).upper()
            candidates = [item for item in by_symbol.values()
                          if item["trading_symbol"].upper() == ticker and item["exchange"] in {"NSE", "BSE"}]
            if len(candidates) == 1:
                candidate = candidates[0]
            elif len(candidates) > 1:
                nse = [item for item in candidates if item["exchange"] == "NSE"]
                if len(nse) == 1:
                    candidate = nse[0]
        report.append({
            "company": name,
            "ipo_type": stock_type,
            "eligible_for_cmp": qualifies(row),
            "matched_exchange": instrument["exchange"] if instrument else "",
            "trading_symbol": instrument["trading_symbol"] if instrument else "",
            "groww_symbol": instrument["exchange_trading_symbol"] if instrument else "",
            "status": status,
            "legacy_ticker_candidate": candidate["trading_symbol"] if candidate else "",
            "candidate_exchange": candidate["exchange"] if candidate else "",
            "candidate_groww_name": candidate["name"] if candidate else "",
        })
    with REPORT_JSON.open("w", encoding="utf-8") as f:
        json.dump({
            "provider": "Groww Trading API instrument master",
            "historical_records": len(rows),
            "unique_company_names": len({r.get("companyName") for r in rows}),
            "mainboard_records": sum(1 for r in report if r["ipo_type"].casefold() == "mainboard"),
            "sme_records": sum(1 for r in report if r["ipo_type"].casefold() == "sme"),
            "eligible_for_cmp": sum(1 for r in report if r["eligible_for_cmp"]),
            "eligible_matched": sum(1 for r in report if r["eligible_for_cmp"] and r["status"] in {"EXACT_NAME_MATCH", "OVERRIDE"}),
            "eligible_unmatched": sum(1 for r in report if r["eligible_for_cmp"] and r["status"] not in {"EXACT_NAME_MATCH", "OVERRIDE"}),
            "matched": sum(1 for r in report if r["status"] in {"EXACT_NAME_MATCH", "OVERRIDE"}),
            "unmatched": sum(1 for r in report if r["status"] not in {"EXACT_NAME_MATCH", "OVERRIDE"}),
            "results": report,
        }, f, ensure_ascii=False, indent=2)
    with REPORT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["company", "ipo_type", "eligible_for_cmp", "matched_exchange", "trading_symbol", "groww_symbol", "status", "legacy_ticker_candidate", "candidate_exchange", "candidate_groww_name"])
        writer.writeheader()
        writer.writerows(report)
    matched = sum(1 for r in report if r["status"] in {"EXACT_NAME_MATCH", "OVERRIDE"})
    unmatched = len(report) - matched
    eligible = [r for r in report if r["eligible_for_cmp"]]
    eligible_matched = sum(1 for r in eligible if r["status"] in {"EXACT_NAME_MATCH", "OVERRIDE"})
    invalid_overrides = sum(1 for r in report if r["status"].startswith("INVALID_OVERRIDE"))
    print(f"Groww mapping validation: {len(rows)} historical records; {matched} matched; {unmatched} unresolved.")
    print(f"CMP-eligible: {len(eligible)}; mapped: {eligible_matched}; unresolved: {len(eligible) - eligible_matched}.")
    print(f"Mainboard: {sum(1 for r in report if r['ipo_type'].casefold() == 'mainboard')}; SME: {sum(1 for r in report if r['ipo_type'].casefold() == 'sme')}.")
    print(f"Invalid explicit Groww overrides: {invalid_overrides}.")
    print("Read-only validation: no IPO prices, source records, or mappings were changed.")
    if len(eligible) != eligible_matched or invalid_overrides:
        print("VALIDATION FAILED: every CMP-eligible IPO must resolve to a valid Groww instrument.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
