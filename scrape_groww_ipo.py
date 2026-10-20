"""Refresh the live Apply/Waiting IPO feed from Groww subscription tables.

This script updates subscription and lifecycle feed data only. CMP updates are
handled separately by scripts/update_prices.py using Screener.in.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

IPO_URL = "https://groww.in/ipo"
SUBSCRIPTION_URL = "https://groww.in/ipo/subscription"
OUT = Path("live-ipo-data.json")
HEADERS = {"User-Agent": "Mozilla/5.0"}


def clean(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalized_name(value):
    return re.sub(r"[^a-z0-9]", "", clean(value).lower())


def number(value):
    found = re.findall(r"\d[\d,]*(?:\.\d+)?", clean(value).replace(",", ""))
    return float(found[-1]) if found else None


def fetch_tables(url):
    response = requests.get(url, headers=HEADERS, timeout=40)
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
    if not tables:
        raise RuntimeError(f"No HTML tables found at {url}")
    return tables


def find_column(frame, *names):
    wanted = set(names)
    for heading in frame.columns:
        key = re.sub(r"[^a-z]", "", clean(heading).lower())
        if key in wanted:
            return heading
    return None


def find_stage_column(frame):
    # Groww currently exposes the stage as an unnamed column.
    # Detect it by its actual values instead of relying on the header.
    for heading in frame.columns:
        values = frame[heading].map(lambda value: clean(value).lower())
        if values.isin({"apply", "pre-apply", "pre apply"}).any():
            return heading
    return None


def parse_close_date(value):
    value = clean(value)
    for fmt in (
        "%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d-%m-%Y",
        "%d/%m/%Y", "%d-%b-%Y", "%d %b, %Y", "%b %d, %Y",
    ):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def main():
    print("Fetching Groww main IPO page...")
    ipo_tables = fetch_tables(IPO_URL)
    ipo_table = ipo_tables[0].copy()
    ipo_table.columns = [clean(column) for column in ipo_table.columns]

    name_col = find_column(ipo_table, "companyname", "name")
    type_col = find_column(ipo_table, "type", "ipotype")
    close_col = find_column(ipo_table, "closedate", "closingdate")
    price_col = find_column(ipo_table, "issueprice", "priceband")
    stage_col = find_stage_column(ipo_table)

    if not all([name_col, type_col, close_col, stage_col]):
        raise RuntimeError(
            "Groww main IPO table headings changed: "
            f"{list(ipo_table.columns)}; detected stage column={stage_col!r}"
        )

    apply_ipos = []
    for _, row in ipo_table.iterrows():
        name = clean(row[name_col])
        stage = clean(row[stage_col]).lower()
        if not name or stage != "apply":
            continue

        kind = clean(row[type_col]).lower()
        apply_ipos.append({
            "name": name,
            "key": normalized_name(name),
            "close_date": clean(row[close_col]),
            "issue_price": number(row[price_col]) if price_col else None,
            "stock_type": "SME" if "sme" in kind else "Mainboard",
        })

    if not apply_ipos:
        # A valid page can contain only Pre-Apply/closed IPOs after the last
        # application window ends. Preserve existing records and advance
        # expired applications below instead of treating this as a parser failure.
        print("No IPOs currently marked Apply; preserving existing feed records.")

    keys = [ipo["key"] for ipo in apply_ipos]
    if len(keys) != len(set(keys)):
        raise RuntimeError("Duplicate company names among Apply rows; refusing to write.")

    print(f"Found {len(apply_ipos)} IPOs marked Apply.")

    # The standard schedule runs hourly at minute 17. Additional scheduled
    # runs are added on IPO closing days: every 15 minutes, then every 5
    # minutes during the final hour. On non-closing days, skip those extra
    # scheduled runs so the normal hourly refresh remains unchanged.
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    is_scheduled_run = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    closes_today = any(
        parse_close_date(ipo["close_date"]) == now_ist.date()
        for ipo in apply_ipos
    )
    if is_scheduled_run and now_ist.minute != 17 and not closes_today:
        print("No IPO closes today; skipping this extra high-frequency run.")
        return
    if closes_today and is_scheduled_run:
        print("IPO closing day detected; refreshing subscription figures on the enhanced schedule.")

    print("Fetching Groww subscription page...")
    subscription_tables = fetch_tables(SUBSCRIPTION_URL)
    subscription_table = max(subscription_tables, key=len).copy()
    subscription_table.columns = [clean(column) for column in subscription_table.columns]

    sub_name_col = find_column(subscription_table, "companyname", "name")
    sub_price_col = find_column(subscription_table, "issueprice", "priceband")
    qib_col = find_column(subscription_table, "qib")
    nii_col = find_column(subscription_table, "nii", "hni")
    retail_col = find_column(subscription_table, "retail", "rii")
    total_col = find_column(subscription_table, "total", "totalsubscription")

    required = [sub_name_col, qib_col, nii_col, retail_col, total_col]
    if any(column is None for column in required):
        raise RuntimeError(
            f"Groww subscription table headings changed: {list(subscription_table.columns)}"
        )

    subscriptions = {}
    for _, row in subscription_table.iterrows():
        name = clean(row[sub_name_col])
        key = normalized_name(name)
        if not name or not key:
            continue
        if key in subscriptions:
            raise RuntimeError(f"Duplicate subscription rows for {name!r}; refusing to write.")
        subscriptions[key] = row

    records = []
    unmatched = []
    for ipo in apply_ipos:
        matched = subscriptions.get(ipo["key"])
        if matched is None:
            unmatched.append(ipo["name"])
            qib = hni = retail = total = "—"
            issue_price = ipo["issue_price"]
        else:
            qib = clean(matched[qib_col]) or "—"
            hni = clean(matched[nii_col]) or "—"
            retail = clean(matched[retail_col]) or "—"
            total = clean(matched[total_col]) or "—"
            issue_price = (
                number(matched[sub_price_col])
                if sub_price_col and clean(matched[sub_price_col])
                else ipo["issue_price"]
            )

        # Preserve the current dashboard schema. Historically, listingDate in
        # this feed contains the IPO close date; do not silently rename it here.
        records.append({
            "companyName": ipo["name"],
            "currentPrice": None,
            "listingDate": ipo["close_date"],
            "applicationEnd": ipo["close_date"],
            "issuePrice": issue_price,
            "qib": qib,
            "hni": hni,
            "retail": retail,
            "total": total,
            "listingGain": None,
            "currentGain": None,
            "stockType": ipo["stock_type"],
            "source": "Groww",
            "status": "Open",
            "stage": "Apply",
        })

    if len(records) != len(apply_ipos):
        raise RuntimeError("Record count validation failed; refusing to write.")

    # Groww's Apply table omits IPOs after applications close. Preserve those
    # records locally so the lifecycle updater can keep checking for listing data.
    existing_records = []
    if OUT.exists():
        try:
            existing_records = json.loads(OUT.read_text(encoding="utf-8")).get("ipos", [])
        except (ValueError, AttributeError):
            raise RuntimeError("Existing live IPO feed is unreadable; refusing to overwrite it.")
    current_keys = {record["companyName"].casefold() for record in records}
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    for old in existing_records:
        key = clean(old.get("companyName")).casefold()
        if not key or key in current_keys:
            continue
        close_date = None
        for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                close_date = datetime.strptime(clean(old.get("applicationEnd") or old.get("closeDate") or old.get("listingDate")), fmt).date()
                break
            except ValueError:
                pass
        if close_date and close_date < today:
            old["applicationEnd"] = close_date.strftime("%d %b %Y")
            old["stage"] = old.get("stage") if old.get("stage") == "Listed" else "Waiting for Listing"
            old["status"] = old.get("status") if old.get("status") == "Listed" else "Waiting for Listing"

        # Keep closed-but-not-yet-listed IPO subscription figures fresh too.
        # Groww's subscription table can retain the final/current category totals
        # after an IPO disappears from the Apply table. Do not freeze the values
        # captured on the last application day.
        if str(old.get("stage") or old.get("status") or "").strip().lower() == "waiting for listing":
            matched = subscriptions.get(normalized_name(old.get("companyName", "")))
            if matched is not None:
                old["qib"] = clean(matched[qib_col]) or old.get("qib", "—")
                old["hni"] = clean(matched[nii_col]) or old.get("hni", "—")
                old["retail"] = clean(matched[retail_col]) or old.get("retail", "—")
                old["total"] = clean(matched[total_col]) or old.get("total", "—")
                if sub_price_col and clean(matched[sub_price_col]):
                    parsed_price = number(matched[sub_price_col])
                    if parsed_price is not None:
                        old["issuePrice"] = parsed_price
                old["subscriptionUpdatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        records.append(old)
        current_keys.add(key)

    required_fields = {
        "companyName", "currentPrice", "listingDate", "issuePrice", "qib",
        "hni", "retail", "total", "listingGain", "currentGain", "stockType",
        "source", "status", "stage",
    }
    for record in records:
        if required_fields - set(record):
            raise RuntimeError(f"Output schema validation failed for {record['companyName']}.")

    output = {
        "source": IPO_URL,
        "subscriptionSource": SUBSCRIPTION_URL,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ipos": records,
    }

    # Only replace production data after both pages and schema have validated.
    # A missing subscription match is retained with — figures as requested.
    temp_out = OUT.with_suffix(".json.tmp")
    temp_out.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp_out.replace(OUT)

    print(f"Apply IPOs: {len(apply_ipos)}")
    print(f"Matched subscription rows: {len(records) - len(unmatched)}")
    print(f"Unmatched (kept with — subscription figures): {unmatched or 'None'}")
    print(f"Wrote {len(records)} IPOs to {OUT}.")


if __name__ == "__main__":
    main()
