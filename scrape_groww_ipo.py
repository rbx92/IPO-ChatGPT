import json
import re
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from lxml import html as lxml_html

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


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", clean(value).lower())


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

    # pandas extracts the subscription data; lxml preserves action labels that
    # pandas may drop from cells (for example, "Apply" and "Pre-apply").
    tables = pd.read_html(StringIO(response.text))
    if not tables:
        raise RuntimeError(f"No HTML tables found on Groww page ({len(response.text)} bytes)")

    table = max(tables, key=len).copy()
    table.columns = [clean(c).lower() for c in table.columns]

    def column(*candidates):
        for col in table.columns:
            if re.sub(r"[^a-z]", "", col) in candidates:
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

    required = {"Company Name": name_col, "Close Date": date_col, "QIB": qib_col, "NII": nii_col, "Retail": retail_col, "Total": total_col}
    missing = [label for label, col in required.items() if col is None]
    if missing:
        raise RuntimeError(f"Groww table headers changed; missing {missing}. Found headers: {list(table.columns)}")

    # Build a per-company action map from the original HTML table rows.
    # Never default an undetected stage to "Apply".
    root = lxml_html.fromstring(response.content)
    row_texts = []
    for tr in root.xpath("//tr"):
        row_text = clean(" ".join(tr.itertext()))
        if row_text:
            row_texts.append((normalize(row_text), row_text.lower()))

    today = datetime.now().date()
    records = []
    seen = set()
    pre_apply_skipped = 0
    unknown_stage_skipped = 0

    for _, row in table.iterrows():
        name = clean(row[name_col])
        if not name or name.lower() in {"company name", "nan"}:
            continue

        normalized_name = normalize(name)
        matched_text = next((text for row_norm, text in row_texts if normalized_name and normalized_name in row_norm), "")
        if not matched_text:
            unknown_stage_skipped += 1
            continue

        if "pre-apply" in matched_text or "pre apply" in matched_text or "preapply" in normalize(matched_text):
            pre_apply_skipped += 1
            continue

        # Include only rows with a real Apply action, not rows where stage cannot be verified.
        if not re.search(r"\bapply\b", matched_text):
            unknown_stage_skipped += 1
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
            f"No IPOs with a verified Apply action found in Groww HTML. Table rows: {len(table)}; "
            f"pre-apply skipped: {pre_apply_skipped}; unknown stage skipped: {unknown_stage_skipped}. "
            f"Headers: {list(table.columns)}. Existing feed left untouched."
        )

    OUT.write_text(json.dumps({
        "source": URL,
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ipos": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Parsed {len(table)} table rows; skipped {pre_apply_skipped} pre-apply and "
        f"{unknown_stage_skipped} unverified-stage rows; wrote {len(records)} verified Apply IPOs."
    )


if __name__ == "__main__":
    main()
