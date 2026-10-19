"""Canonical IPO eligibility rules loaded from the shared JSON configuration."""

import json
import re
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1] / "eligibility-rules.json"
with CONFIG_PATH.open(encoding="utf-8") as config_file:
    ELIGIBILITY_CONFIG = json.load(config_file)

QIB_MIN_MULTIPLE = float(ELIGIBILITY_CONFIG["qib_min_multiple"])
LISTING_GAIN_MIN_PERCENT = float(ELIGIBILITY_CONFIG["listing_gain_min_percent"])
EXCLUDED_COMPANIES = set(ELIGIBILITY_CONFIG["excluded_company_names_normalized"])
COMPANY_NAME_SUFFIXES = set(ELIGIBILITY_CONFIG["company_name_suffixes"])


def multiple_value(value):
    match = re.fullmatch(r"\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*x?\s*", str(value or ""), re.I)
    return float(match.group(1).replace(",", "")) if match else None


def percent_value(value):
    match = re.fullmatch(r"\s*(-?\d+(?:,\d{3})*(?:\.\d+)?)\s*%?\s*", str(value or ""))
    return float(match.group(1).replace(",", "")) if match else None


def normalized_name(value: str) -> str:
    value = str(value or "").lower().replace("&", " and ")
    words = re.sub(r"[^a-z0-9]+", " ", value).split()
    while words and words[-1] in COMPANY_NAME_SUFFIXES:
        words.pop()
    return " ".join(words)


def qualifies(row):
    qib = multiple_value(row.get("qib"))
    listing_gain = percent_value(row.get("listingGain"))
    name = normalized_name(row.get("companyName"))
    return (
        qib is not None
        and qib >= QIB_MIN_MULTIPLE
        and listing_gain is not None
        and listing_gain >= LISTING_GAIN_MIN_PERCENT
        and name not in EXCLUDED_COMPANIES
    )
