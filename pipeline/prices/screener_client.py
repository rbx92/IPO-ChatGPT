"""Screener.in access shared by the backup price steps.

Stops on HTTP 401/403/429 (raises RuntimeError) instead of retrying.
"""
import json
import re
from urllib.error import HTTPError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

BASE = "https://www.screener.in"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; IPO-Lens/1.0)", "X-Requested-With": "XMLHttpRequest",
           "Referer": BASE + "/"}


def get(url):
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=25) as response:
            return response.read().decode("utf-8", "replace")
    except HTTPError as exc:
        if exc.code in (401, 403, 429):
            raise RuntimeError(f"Screener denied/throttled request (HTTP {exc.code}); stopping safely") from exc
        raise


def is_rate_limit(exc):
    return bool(re.search(r"HTTP (?:401|403|429)\b", str(exc)))


def _normalized(value):
    words = re.sub(r"[^a-z0-9]+", " ", str(value).casefold().replace("&", " and ")).split()
    while words and words[-1] in {"limited", "ltd", "plc", "pvt", "private", "company", "co"}:
        words.pop()
    return " ".join(words)


def resolve(name):
    """Screener page path for an exact company-name match, else None."""
    found = json.loads(get(f"{BASE}/api/company/search/?q={quote_plus(name)}"))
    target = _normalized(name)
    matches = {x.get("url", "").split("?", 1)[0] for x in found
               if isinstance(x, dict) and _normalized(x.get("name", "")) == target
               and isinstance(x.get("url"), str) and x["url"].startswith("/company/")}
    return next(iter(matches)) if len(matches) == 1 else None


def chart_identity(path):
    html = get(BASE + path)
    m = re.search(r'data-company-id=["\'](\d+)', html)
    if m:
        return m.group(1)
    raise RuntimeError(f"Could not identify Screener chart ID for {path}")
