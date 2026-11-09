#!/usr/bin/env python3
"""One-off coverage test for the official Groww Trade API.

Logs in with the TOTP flow (secrets GROWW_TOTP_TOKEN and GROWW_TOTP_SECRET),
matches every dashboard IPO to a Groww cash-market instrument by name, then
fetches live prices in batches of 50 and one daily-candle history as a sample.
Writes reports/groww-api-test.json. It never writes credentials anywhere.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pyotp
from growwapi import GrowwAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from rules import normalized_name  # noqa: E402

REPORT = ROOT / "reports" / "groww-api-test.json"


def clean_secret(raw):
    """Accept the secret with spaces, dashes, lowercase, or as a full otpauth:// QR link."""
    raw = (raw or "").strip()
    if raw.lower().startswith("otpauth://"):
        from urllib.parse import parse_qs, urlparse
        raw = parse_qs(urlparse(raw).query).get("secret", [""])[0]
    return "".join(ch for ch in raw if ch.isalnum()).upper()


def describe(value):
    """Shape of a secret without revealing it, for troubleshooting."""
    value = value or ""
    return {"length": len(value), "hasDot": "." in value, "hasSpace": " " in value,
            "hasLower": any(c.islower() for c in value), "startsOtpauth": value.lower().startswith("otpauth"),
            "nonBase32": sorted({c for c in value.upper() if c.isalnum() and c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"})[:3] and True}


def login(report):
    token = (os.environ.get("GROWW_TOTP_TOKEN") or "").strip()
    raw = os.environ.get("GROWW_TOTP_SECRET")
    report["secretShape"] = {"token": describe(token), "secret": describe(raw)}
    if not token or not raw:
        raise SystemExit("Missing GROWW_TOTP_TOKEN or GROWW_TOTP_SECRET repository secret.")
    import base64
    try:  # read only the token's "role" claim, nothing secret
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        report["tokenRole"] = json.loads(claims.get("sub", "{}")).get("role")
    except Exception:
        report["tokenRole"] = "unreadable"
    if report["tokenRole"] != "auth-totp":
        # API key + secret flow (needs daily approval on Groww's API Keys page).
        report["flow"] = "api key + secret"
        return GrowwAPI(GrowwAPI.get_access_token(api_key=token, secret=raw.strip()))
    report["flow"] = "totp"
    secret = clean_secret(raw)
    import binascii
    try:
        base64.b32decode(secret + "=" * (-len(secret) % 8))
        report["secretFormat"] = "base32"
    except binascii.Error:
        # Some sites show the TOTP key as hex; convert it to the base32 form.
        secret = base64.b32encode(bytes.fromhex(secret)).decode().rstrip("=")
        report["secretFormat"] = "hex converted to base32"
    access = GrowwAPI.get_access_token(api_key=token, totp=pyotp.TOTP(secret).now())
    return GrowwAPI(access)


def main():
    report = {"ranAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        groww = login(report)
        report["login"] = "ok"
    except Exception as exc:  # report the reason without leaking secrets
        report["login"] = f"failed: {type(exc).__name__}: {str(exc)[:300]}"
        REPORT.parent.mkdir(exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2) + "\n")
        raise SystemExit(1)

    inst = pd.read_csv(groww.INSTRUMENT_CSV_URL, dtype=str, low_memory=False)
    cash = inst[inst["segment"].str.upper() == "CASH"].copy()
    report["instruments"] = {
        "cashRows": int(len(cash)),
        "byExchange": cash["exchange"].value_counts().to_dict(),
        "series": cash["series"].value_counts().head(25).to_dict(),
    }
    cash["key"] = cash["name"].fillna("").map(normalized_name)
    # Prefer NSE, then BSE, for each company name.
    cash["rank"] = cash["exchange"].map({"NSE": 0, "BSE": 1}).fillna(2)
    best = cash.sort_values("rank").drop_duplicates("key").set_index("key")

    rows = json.loads((ROOT / "ipos.json").read_text())
    live = json.loads((ROOT / "live-ipo-data.json").read_text())["ipos"]
    waiting = [r for r in live if r.get("stage") == "Waiting for Listing"]

    def match(name):
        key = normalized_name(name)
        if key in best.index:
            hit = best.loc[key]
            return {"exchange": hit["exchange"], "symbol": hit["trading_symbol"],
                    "series": hit["series"], "isin": hit["isin"]}
        return None

    matched, missing = {}, []
    for r in rows:
        m = match(r["companyName"])
        if m:
            matched[r["companyName"]] = m
        else:
            missing.append({"name": r["companyName"], "type": r.get("stockType")})
    report["dashboardIpos"] = {"total": len(rows), "matched": len(matched), "missing": missing}
    report["waitingForListing"] = {r["companyName"]: match(r["companyName"]) for r in waiting}

    # Live prices, 50 per call, well inside 10 requests/second.
    symbols = [f"{m['exchange']}_{m['symbol']}" for m in matched.values()]
    prices, errors = {}, []
    for i in range(0, len(symbols), 50):
        try:
            prices.update(groww.get_ltp(segment=groww.SEGMENT_CASH,
                                        exchange_trading_symbols=tuple(symbols[i:i + 50])))
        except Exception as exc:
            errors.append(f"batch {i // 50}: {type(exc).__name__}: {str(exc)[:200]}")
        time.sleep(0.5)
    report["ltp"] = {"requested": len(symbols), "returned": len(prices), "errors": errors,
                     "sample": dict(list(prices.items())[:5])}

    # One daily-candle history as a sample for the pullback signal.
    sample = next((r for r in rows if r.get("priceHistory") and r["companyName"] in matched), None)
    if sample:
        m = matched[sample["companyName"]]
        end = datetime.now()
        data, candle_errors = None, []
        for label, call in (
            ("get_historical_candles", lambda: groww.get_historical_candles(
                exchange=m["exchange"], segment=groww.SEGMENT_CASH, groww_symbol=f"{m['exchange']}-{m['symbol']}",
                start_time=(end - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S"),
                end_time=end.strftime("%Y-%m-%d %H:%M:%S"), candle_interval=groww.CANDLE_INTERVAL_DAY)),
            ("get_historical_candle_data", lambda: groww.get_historical_candle_data(
                trading_symbol=m["symbol"], exchange=m["exchange"], segment=groww.SEGMENT_CASH,
                start_time=(end - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S"),
                end_time=end.strftime("%Y-%m-%d %H:%M:%S"), interval_in_minutes=1440)),
        ):
            try:
                data = call()
                break
            except Exception as exc:
                candle_errors.append(f"{label}: {exc}")
        candles = (data or {}).get("candles") or []
        report["dailyCandles"] = {"company": sample["companyName"], "count": len(candles),
                                  "errors": candle_errors,
                                  "last": candles[-3:],
                                  "screenerLast": sample["priceHistory"][-3:]}

    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "dashboardIpos"}, indent=2, default=str)[:3000])


if __name__ == "__main__":
    main()
