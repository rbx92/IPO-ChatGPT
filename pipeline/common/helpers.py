"""Small shared helpers: dates, numbers, IPO stage, saving the IPO list."""
import json
import re
from datetime import datetime

from common.paths import DATA_JS, IPOS

CMP_KEYS = ("currentPrice", "currentGain", "priceSource", "priceUpdatedAt")


def parse_date(value):
    """Read '23 Oct 2026', '23 October 2026', '2026-10-23' or '23-10-2026'."""
    if not value:
        return None
    for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    return None


def number(value):
    """First number in a value such as '₹660 - ₹693' or '1,234.5'."""
    m = re.search(r"-?\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    return float(m.group()) if m else None


def is_listed_record(row):
    """A known Listed state never goes back, even if later data is missing."""
    return (str(row.get("stage", "")).casefold() == "listed"
            or str(row.get("status", "")).casefold() == "listed"
            or row.get("listingPrice") not in (None, "", "-"))


def lifecycle_stage(close_date, today, was_listed):
    """Apply until the close date, then Waiting for Listing; Listed is final."""
    if was_listed:
        return "Listed"
    if close_date is None or today <= close_date:
        return "Apply"
    return "Waiting for Listing"


def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_ipos(rows):
    """Write ipos.json and the data.js copy the website loads."""
    IPOS.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DATA_JS.write_text("window.IPO_DATA = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n",
                       encoding="utf-8")
