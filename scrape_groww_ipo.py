import json
import re
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

IPO_URL = "https://groww.in/ipo"
SUBSCRIPTION_URL = "https://groww.in/ipo/subscription"
OUT = Path("live-ipo-data.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}


def clean(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def valid(value):
    value = clean(value)
    return value if value and value.lower() not in {"--", "-", "nan", "none"} else "—"


def issue_price(value):
    numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", clean(value).replace(",", ""))
    return float(numbers[-1]) if numbers else None


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", clean(value).lower())


def get_tables(url):
    response = requests.get(url, headers=HEADERS, timeout=40)
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
    if not tables:
        raise RuntimeError(f"No HTML tables found at {url} ({len(response.text)} bytes)")
    return tables


def column_for(table, *candidates):
    for col in table.columns:
        if re.sub(r"[^a-z]", "", clean(col).lower()) in candidates:
            return col
    return None


def main():
    # The /ipo dashboard carries the authoritative Apply / Pre-apply action.
    # The subscription page carries QIB/NII/Retail/Total figures. Do not try to
    # infer application stage from subscription rows or dates.
    ipo_tables = get_tables(IPO_URL)
    ipo_table = None
    ipo_cols = None
    for candidate in ipo_tables:
        cols = {
            "name": column_for(candidate, "companyname", "name"),
            "type": column_for(candidate, "type", "ipotype"),
            "open": column_for(candidate, "opendate", "openingdate"),
            "close": column_for(candidate, "closedate", "closingdate"),
            "price": column_for(candidate, "issueprice", "priceband"),
        }
        if all(cols.values()) and len(candidate.columns) >= 6:
            # The Open IPOs table has an extra final action column.
            ipo_table, ipo_cols = candidate.copy(), cols
            break
    if ipo_table is None:
        raise RuntimeError(
            "Could not identify Groww's Open IPOs table with company, type, open date, "
            f"close date and issue price columns. Found table headers: "
            f"{[list(t.columns) for t in ipo_tables]}"
        )

    # The action is the table cell after issue price (usually the final column).
    action_col = ipo_table.columns[-1]
    subscription_tables = get_tables(SUBSCRIPTION_URL)
    sub_table = None
    sub_cols = None
    for candidate in subscription_tables:
        cols = {
            "name": column_for(candidate, "companyname", "name"),
            "type": column_for(candidate, "type", "ipotype"),
            "close": column_for(candidate, "closedate", "closingdate"),
            "price": column_for(candidate, "issueprice", "priceband"),
            "qib": column_for(candidate, "qib"),
            "nii": column_for(candidate, "nii", "hni"),
            "retail": column_for(candidate, "retail", "rii"),
            "total": column_for(candidate, "total", "totalsubscription"),
        }
        if all(cols[k] for k in ("name", "qib", "nii", "retail", "total")):
            sub_table, sub_cols = candidate.copy(), cols
            break
    if sub_table is None:
        raise RuntimeError(
            "Could not identify Groww's subscription table with QIB/NII/Retail/Total. "
            f"Found table headers: {[list(t.columns) for t in subscription_tables]}"
        )

    subscriptions = {}
    for _, row in sub_table.iterrows():
        name = clean(row[sub_cols["name"]])
        if name:
            subscriptions[normalize(name)] = row

    today = datetime.now().date()
    records = []
    seen = set()
    pre_apply_skipped = 0
    unknown_stage_skipped = 0
    expired_skipped = 0

    for _, row in ipo_table.iterrows():
        name = clean(row[ipo_cols["name"]])
        if not name or name.lower() in {"company name", "nan"}:
            continue

        action = clean(row[action_col]).lower()
        open_text = clean(row[ipo_cols["open"]])
        close_text = clean(row[ipo_cols["close"]])

        # The table is specifically Groww's "Open IPOs" section. Sometimes
        # pandas omits the action button column, so use the published open/close
        # dates as a fallback only within this section.
        try:
            open_date = datetime.strptime(open_text, "%d %b %Y").date()
            close_date = datetime.strptime(close_text, "%d %b %Y").date()
        except ValueError:
            unknown_stage_skipped += 1
            continue

        if close_date < today:
            expired_skipped += 1
            continue

        if re.search(r"\bpre[ -]?apply\b", action):
            pre_apply_skipped += 1
            continue
        if re.search(r"\bapply\b", action):
            stage = "Apply"
        elif open_date > today and close_date >= today:
            pre_apply_skipped += 1
            continue
        elif open_date <= today <= close_date:
            stage = "Apply"
        else:
            unknown_stage_skipped += 1
            continue

        key = normalize(name)
        if key in seen:
            continue
        seen.add(key)

        sub_row = subscriptions.get(key)
        kind = clean(row[ipo_cols["type"]]).lower()
        price = row[ipo_cols["price"]]
        records.append({
            "companyName": name,
            "currentPrice": None,
            "listingDate": close_text or "Date unavailable",
            "issuePrice": issue_price(price),
            "qib": valid(sub_row[sub_cols["qib"]]) if sub_row is not None else "—",
            "hni": valid(sub_row[sub_cols["nii"]]) if sub_row is not None else "—",
            "retail": valid(sub_row[sub_cols["retail"]]) if sub_row is not None else "—",
            "total": valid(sub_row[sub_cols["total"]]) if sub_row is not None else "—",
            "listingGain": None,
            "currentGain": None,
            "stockType": "SME" if "sme" in kind else "Mainboard",
            "source": "Groww",
            "status": "Open",
            "stage": stage,
        })

    if not records:
        raise RuntimeError(
            "No eligible IPOs with a verified Apply action found on Groww's IPO dashboard. "
            f"Open-table rows: {len(ipo_table)}; pre-apply skipped: {pre_apply_skipped}; "
            f"unknown stage skipped: {unknown_stage_skipped}; expired skipped: {expired_skipped}. "
            "Existing feed left untouched."
        )

    OUT.write_text(json.dumps({
        "source": IPO_URL,
        "subscriptionSource": SUBSCRIPTION_URL,
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ipos": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Groww IPO dashboard rows: {len(ipo_table)}; skipped {pre_apply_skipped} pre-apply, "
        f"{unknown_stage_skipped} unknown-stage and {expired_skipped} expired rows; "
        f"wrote {len(records)} verified Apply IPOs."
    )


if __name__ == "__main__":
    main()
