import json
import re
from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

URL = "https://groww.in/ipo/subscription"
OUT = Path("live-ipo-data.json")


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


def is_pre_apply(value):
    normalized = re.sub(r"[^a-z]", "", clean(value).lower())
    return "preapply" in normalized


def main():
    response = requests.get(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36",
            "Accept-Language": "en-IN,en;q=0.9",
        },
        timeout=40,
    )
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
    if not tables:
        raise RuntimeError(f"No HTML tables found on Groww page ({len(response.text)} bytes)")

    table = max(tables, key=len).copy()
    table.columns = [clean(c).lower() for c in table.columns]

    def column(*candidates):
        for col in table.columns:
            normalized = re.sub(r"[^a-z]", "", col)
            if normalized in candidates:
                return col
        return None

    name_col = column("companyname", "name")
    type_col = column("type", "ipotype")
    date_col = column("closedate", "closingdate")
    price_col = column("issueprice", "priceband")
    qib_col = column("qib")
    nii_col = column("nii", "hni")
    retail_col = column("retail", "rii")
    total_col = column("total", "totalsubscription")
    status_col = column("status", "ipostatus", "stage", "ipostage")
    action_col = column("action", "apply", "button")

    required = {"Company Name": name_col, "Close Date": date_col, "QIB": qib_col, "NII": nii_col, "Retail": retail_col, "Total": total_col}
    missing = [label for label, col in required.items() if col is None]
    if missing:
        raise RuntimeError(f"Groww table headers changed; missing {missing}. Found headers: {list(table.columns)}")

    today = datetime.now().date()
    records = []
    seen = set()
    pre_apply_skipped = 0

    for _, row in table.iterrows():
        name = clean(row[name_col])
        if not name or name.lower() in {"company name", "nan"}:
            continue

        # Groww labels pre-application rows with a "Pre-apply" action.
        # Some page versions expose a status column; others expose it as the action column.
        status_text = clean(row[status_col]).lower() if status_col else ""
        action_text = clean(row[action_col]).lower() if action_col else ""
        stage_text = " ".join(part for part in (status_text, action_text) if part)
        if is_pre_apply(stage_text):
            pre_apply_skipped += 1
            continue

        # Do not classify rows as open if Groww's table no longer exposes an Apply action.
        if action_col and action_text and "apply" not in action_text:
            continue

        close_text = clean(row[date_col])
        try:
            close_date = datetime.strptime(close_text, "%d %b %Y").date()
            if close_date < today:
                continue
        except ValueError:
            pass

        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)

        kind = clean(row[type_col]).lower() if type_col else ""
        records.append({
            "companyName": name,
            "currentPrice": None,
            "listingDate": close_text or "Date unavailable",
            "issuePrice": issue_price(row[price_col]) if price_col else None,
            "qib": valid(row[qib_col]),
            "hni": valid(row[nii_col]),
            "retail": valid(row[retail_col]),
            "total": valid(row[total_col]),
            "listingGain": None,
            "currentGain": None,
            "stockType": "SME" if "sme" in kind else "Mainboard",
            "source": "Groww",
            "status": "Open / Upcoming",
            "stage": "Apply",
        })

    if not records:
        raise RuntimeError(
            f"Groww table had {len(table)} rows but no eligible IPOs remained after filtering. "
            f"Skipped {pre_apply_skipped} pre-apply rows. Headers: {list(table.columns)}. "
            "Existing feed left untouched."
        )

    OUT.write_text(json.dumps({
        "source": URL,
        "updatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "ipos": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Parsed {len(table)} table rows; skipped {pre_apply_skipped} pre-apply rows; "
        f"wrote {len(records)} eligible open IPOs to {OUT}"
    )


if __name__ == "__main__":
    main()
