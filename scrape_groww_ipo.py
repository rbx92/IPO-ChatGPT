import json
import re
from datetime import datetime
from html import unescape
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://groww.in/ipo/subscription"
OUT = Path("live-ipo-data.json")


def clean(value):
    value = unescape(str(value or ""))
    return re.sub(r"\s+", " ", value).strip()


def parse_number(value):
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", clean(value).replace(",", ""))
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

    # Groww renders the subscription list as server-side HTML cards, not HTML tables.
    soup = BeautifulSoup(page, "html.parser")
    today = datetime.now().date()
    records = []
    seen = set()

    def labelled(card, label):
        node = card.find(attrs={"aria-label": re.compile(r"^" + re.escape(label) + r" value$", re.I)})
        return clean(node.get_text(" ", strip=True)) if node else ""

    for card in soup.find_all("article"):
        name = labelled(card, "company name")
        if not name:
            continue
        kind = labelled(card, "Type")
        close_text = labelled(card, "Close Date")
        try:
            close_date = datetime.strptime(close_text, "%d %b %Y").date()
            if close_date < today:
                continue
        except ValueError:
            pass
        qib, nii = labelled(card, "QIB"), labelled(card, "NII")
        retail, total = labelled(card, "Retail"), labelled(card, "Total")
        issue_text = labelled(card, "Issue Price")
        price_numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", issue_text.replace(",", ""))
        issue_price = float(price_numbers[-1]) if price_numbers else None
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        records.append({
            "companyName": name, "currentPrice": None,
            "listingDate": close_text or "Date unavailable", "issuePrice": issue_price,
            "qib": mult(qib), "hni": mult(nii), "retail": mult(retail), "total": mult(total),
            "listingGain": None, "currentGain": None,
            "stockType": "SME" if "sme" in kind.lower() else "Mainboard",
            "source": "Groww", "status": "Open / Upcoming",
        })

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
