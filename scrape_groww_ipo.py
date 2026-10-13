import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

URL = "https://groww.in/ipo/subscription"
OUT = Path("live-ipo-data.json")

def text(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()

def number(value):
    match = re.search(r"[\d,]+(?:\.\d+)?", text(value).replace(",", ""))
    return float(match.group(0)) if match else None

def subscription(value):
    value = text(value)
    return value if value and value not in {"--", "-", "nan"} else "—"

def main():
    response = requests.get(URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; IPODashboard/1.0)",
        "Accept-Language": "en-IN,en;q=0.9",
    }, timeout=30)
    response.raise_for_status()
    tables = pd.read_html(response.text)
    today = datetime.now().date()
    records = []
    seen = set()

    for table in tables:
        table.columns = [text(c).lower() for c in table.columns]
        if not any("company name" in c or c == "company" for c in table.columns):
            continue
        def col(*parts):
            return next((c for c in table.columns if any(p in c for p in parts)), None)
        name_col = col("company name", "company")
        type_col = col("type")
        close_col = col("close date")
        price_col = col("issue price")
        qib_col = col("qib")
        nii_col = col("nii", "hni")
        retail_col = col("retail")
        total_col = col("total")
        if not all([name_col, type_col, close_col, price_col, qib_col, nii_col, retail_col, total_col]):
            continue

        for _, row in table.iterrows():
            name = text(row.get(name_col, ""))
            if not name or name.lower() in seen:
                continue
            close_text = text(row.get(close_col, ""))
            try:
                close_date = pd.to_datetime(close_text, dayfirst=True, errors="raise").date()
            except Exception:
                close_date = None
            # The dashboard's live feed is for open and upcoming issues; exclude closed issues.
            if close_date and close_date < today:
                continue

            price_text = text(row.get(price_col, ""))
            price_numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", price_text.replace(",", ""))
            issue_price = float(price_numbers[-1]) if price_numbers else None
            kind = text(row.get(type_col, ""))
            records.append({
                "companyName": name,
                "currentPrice": None,
                "listingDate": close_text or "Date unavailable",
                "issuePrice": issue_price,
                "qib": subscription(row.get(qib_col)),
                "hni": subscription(row.get(nii_col)),
                "retail": subscription(row.get(retail_col)),
                "total": subscription(row.get(total_col)),
                "listingGain": None,
                "currentGain": None,
                "stockType": "SME" if "sme" in kind.lower() else "Mainboard",
                "source": "Groww",
                "status": "Open / Upcoming",
            })
            seen.add(name.lower())

    if not records:
        raise RuntimeError("No open/upcoming IPO rows parsed from Groww; refusing to replace the existing feed.")
    OUT.write_text(json.dumps({
        "source": URL,
        "updatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "ipos": records
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} open/upcoming IPOs to {OUT}")

if __name__ == "__main__":
    main()
