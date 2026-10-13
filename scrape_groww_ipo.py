import json
import re
from datetime import datetime
from html import unescape
from pathlib import Path

import requests

URL = "https://groww.in/ipo/subscription"
OUT = Path("live-ipo-data.json")


def clean(value):
    value = unescape(str(value or ""))
    return re.sub(r"\\s+", " ", value).strip()


def parse_number(value):
    match = re.search(r"[-+]?\\d[\\d,]*(?:\\.\\d+)?", clean(value).replace(",", ""))
    return float(match.group(0)) if match else None


def mult(value):
    value = clean(value)
    return value if value and value not in {"--", "-", "nan", "None"} else "—"


def first(obj, *keys):
    for key in keys:
        value = obj.get(key)
        if value is not None and value != "":
            return value
    return None


def flatten(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from flatten(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from flatten(value)


def main():
    response = requests.get(URL, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36",
        "Accept-Language": "en-IN,en;q=0.9",
    }, timeout=40)
    response.raise_for_status()
    page = response.text

    # Groww is a Next.js page; its server-rendered IPO objects are embedded in __NEXT_DATA__.
    match = re.search(
        r'<script[^>]+id=["\\']__NEXT_DATA__["\\'][^>]*>(.*?)</script>',
        page,
        flags=re.DOTALL | re.IGNORECASE,
    )
    candidates = []
    if match:
        try:
            candidates = list(flatten(json.loads(match.group(1))))
        except json.JSONDecodeError:
            candidates = []

    # Fallback: inspect JSON-like script blocks, but never treat the whole HTML document as a table.
    if not candidates:
        for block in re.findall(r'<script[^>]*type=["\\']application/json["\\'][^>]*>(.*?)</script>', page, flags=re.DOTALL | re.IGNORECASE):
            try:
                candidates.extend(flatten(json.loads(block)))
            except json.JSONDecodeError:
                continue

    today = datetime.now().date()
    records = []
    seen = set()

    for item in candidates:
        name = first(item, "companyName", "company_name", "company", "name", "issuerName", "issuer_name", "ipoName")
        # Keep only objects that look like IPO records, not arbitrary page metadata.
        if not isinstance(name, str) or not name.strip():
            continue
        qib = first(item, "qib", "qibSubscription", "qib_subscription", "qualifiedInstitutionalBuyers")
        nii = first(item, "nii", "hni", "niiSubscription", "hniSubscription", "nonInstitutional")
        retail = first(item, "retail", "retailSubscription", "retail_subscription", "retailInvestor")
        total = first(item, "total", "totalSubscription", "total_subscription", "subscription")
        if not any(k is not None for k in (qib, nii, retail, total)):
            continue

        lowered = json.dumps(item, ensure_ascii=False).lower()
        status = clean(first(item, "status", "ipoStatus", "issueStatus") or "")
        close_value = first(item, "closeDate", "close_date", "closingDate", "endDate", "end_date", "lastDate")
        close_text = clean(close_value) if close_value else ""
        if close_value:
            try:
                close_date = __import__("pandas").to_datetime(close_value, dayfirst=True, errors="raise").date()
                if close_date < today:
                    continue
            except Exception:
                # Do not discard a current IPO only because a date format is unfamiliar.
                pass
        if any(term in status.lower() for term in ("closed", "listed", "allotted")):
            continue
        key = name.strip().lower()
        if key in seen:
            continue

        kind = clean(first(item, "ipoType", "ipo_type", "type", "issueType", "issue_type") or "")
        issue_price = first(item, "issuePrice", "issue_price", "priceBand", "price_band", "price")
        price = parse_number(issue_price) if issue_price is not None else None
        # Use upper end of a price band where Groww provides a range.
        if issue_price is not None:
            price_numbers = re.findall(r"\\d[\\d,]*(?:\\.\\d+)?", clean(issue_price).replace(",", ""))
            if price_numbers:
                price = float(price_numbers[-1])

        def fmt(v):
            if isinstance(v, (int, float)):
                return f"{v:g}x"
            value = mult(v)
            if value != "—" and not re.search(r"x|%|allot|subscr", value, re.I):
                n = parse_number(value)
                if n is not None:
                    return f"{n:g}x"
            return value

        records.append({
            "companyName": clean(name),
            "currentPrice": None,
            "listingDate": close_text or clean(first(item, "openDate", "open_date", "date") or "Date unavailable"),
            "issuePrice": price,
            "qib": fmt(qib),
            "hni": fmt(nii),
            "retail": fmt(retail),
            "total": fmt(total),
            "listingGain": None,
            "currentGain": None,
            "stockType": "SME" if "sme" in kind.lower() or "sme" in lowered else "Mainboard",
            "source": "Groww",
            "status": "Open / Upcoming",
        })
        seen.add(key)

    if not records:
        # Preserve the deployed feed when Groww changes markup or returns no parsable open issues.
        raise RuntimeError(
            f"No open/upcoming IPO records were parsed from Groww page (HTTP {response.status_code}, {len(page)} bytes); existing feed left untouched."
        )

    OUT.write_text(json.dumps({
        "source": URL,
        "updatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "ipos": records
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} open/upcoming IPOs to {OUT}")


if __name__ == "__main__":
    main()
