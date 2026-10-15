import json
import re
from datetime import datetime, timezone
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


def number(value):
    found = re.findall(r"\d[\d,]*(?:\.\d+)?", clean(value).replace(",", ""))
    return float(found[-1]) if found else None


def main():
    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
    table = max(tables, key=len)
    table.columns = [clean(c).lower() for c in table.columns]

    # Find columns by their headings.
    def col(*names):
        for heading in table.columns:
            key = re.sub(r"[^a-z]", "", heading)
            if key in names:
                return heading
        return None

    name_col = col("companyname", "name")
    type_col = col("type", "ipotype")
    close_col = col("closedate", "closingdate")
    price_col = col("issueprice", "priceband")
    qib_col = col("qib")
    nii_col = col("nii", "hni")
    retail_col = col("retail", "rii")
    total_col = col("total", "totalsubscription")

    required = [name_col, close_col, qib_col, nii_col, retail_col, total_col]
    if any(x is None for x in required):
        raise RuntimeError(f"Groww table headings changed: {list(table.columns)}")

    # Use the table's Apply / Pre-apply text when available.
    # If Groww does not provide it in this table, do not guess.
    action_col = next(
        (h for h in table.columns if "action" in h or "stage" in h),
        None,
    )

    today = datetime.now().date()
    records = []
    for _, row in table.iterrows():
        name = clean(row[name_col])
        if not name:
            continue

        action = clean(row[action_col]).lower() if action_col else ""
        if "pre-apply" in action or "pre apply" in action:
            continue
        if not re.search(r"\bapply\b", action):
            continue

        close_text = clean(row[close_col])
        try:
            if datetime.strptime(close_text, "%d %b %Y").date() < today:
                continue
        except ValueError:
            continue

        kind = clean(row[type_col]).lower() if type_col else ""
        records.append({
            "companyName": name,
            "currentPrice": None,
            "listingDate": close_text,
            "issuePrice": number(row[price_col]) if price_col else None,
            "qib": clean(row[qib_col]) or "—",
            "hni": clean(row[nii_col]) or "—",
            "retail": clean(row[retail_col]) or "—",
            "total": clean(row[total_col]) or "—",
            "listingGain": None,
            "currentGain": None,
            "stockType": "SME" if "sme" in kind else "Mainboard",
            "source": "Groww",
            "status": "Open",
            "stage": "Apply",
        })

    if not records:
        raise RuntimeError(
            "Groww subscription page did not expose any verified Apply rows. "
            "Existing live-ipo-data.json was left unchanged."
        )

    OUT.write_text(json.dumps({
        "source": URL,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ipos": records,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(records)} verified open IPOs.")


if __name__ == "__main__":
    main()
