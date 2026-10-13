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

    # Parse the returned HTML tables and fail clearly if Groww changes its markup.
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

    required = {"Company Name": name_col, "Close Date": date_col, "QIB": qib_col, "NII": nii_col, "Retail": retail_col, "Total": total_col}
    missing = [label for label, col in required.items() if col is None]
    if missing:
        raise RuntimeError(f"Groww table headers changed; missing {missing}. Found headers: {list(table.columns)}")

    today = datetime.now().date()
    records = []
    seen = set()

    for _, row in table.iterrows():
        name = clean(row[name_col])
        if not name or name.lower() in {"company name", "nan"}:
            continue
        status_text = clean(row[status_col]).lower() if status_col else ""
        if "pre-apply" in status_text or "pre apply" in status_text or "preapply" in status_text:
            continue
        close_text = clean(row[date_col])
        try:
            close_date = datetime.strptime(close_text, "%d %b %Y").date()
            if close_date < today:
                continue
        except ValueError:
            # Preserve the row on unexpected date formats; the source date is retained verbatim.
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
            "stage": status_text or "Open / Upcoming",
        })

    if not records:
        raise RuntimeError(
            f"Groww HTML table was found ({len(table)} rows) but no open/upcoming IPOs remained after date filtering. "
            f"Headers: {list(table.columns)}. Existing feed left untouched."
        )

    OUT.write_text(json.dumps({
        "source": URL,
        "updatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "ipos": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Parsed {len(table)} table rows; wrote {len(records)} open/upcoming IPOs to {OUT}")


if __name__ == "__main__":
    main()
