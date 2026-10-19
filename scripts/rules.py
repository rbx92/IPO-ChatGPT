"""Shared IPO eligibility rules used by lifecycle and price update scripts."""

import re

# Preserve the existing exclusion list and qualification thresholds.
EXCLUDED_COMPANIES = {"nacdac infrastructure"}


def multiple_value(value):
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*x?\s*", str(value or ""), re.I)
    return float(match.group(1)) if match else None


def percent_value(value):
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*%?\s*", str(value or ""))
    return float(match.group(1)) if match else None


def normalized_name(value: str) -> str:
    value = value.casefold().replace("&", " and ")
    words = re.sub(r"[^a-z0-9]+", " ", value).split()
    suffixes = {"limited", "ltd", "plc", "pvt", "private", "company", "co"}
    while words and words[-1] in suffixes:
        words.pop()
    return " ".join(words)


def qualifies(row):
    qib = multiple_value(row.get("qib"))
    listing_gain = percent_value(row.get("listingGain"))
    name = str(row.get("companyName") or "")
    return (
        qib is not None
        and qib >= 10
        and listing_gain is not None
        and listing_gain >= 15
        and normalized_name(name) not in EXCLUDED_COMPANIES
    )
