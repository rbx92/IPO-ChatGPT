# IPO Lens — Indian IPO Dashboard

Static dashboard for GitHub Pages. The browser loads historical records from `data.js` and merges in the latest live IPO feed from `live-ipo-data.json`.

## Dashboard behaviour

- Separate sections for Open IPOs, Waiting for Listing, and Listed IPOs.
- Listed IPOs are shown only when QIB subscription is at least 50x, listing gain is at least 15%, and the company does not match the financial-sector or pharma/biotech exclusions.
- Open and waiting IPOs require QIB subscription of at least 50x and must pass the same sector exclusions; they do not need a listing gain before listing. Pre-Apply records are hidden.
- Current gain is displayed and can be filtered/sorted, but it is not an eligibility rule.
- Eligibility filters affect display and price-update selection; they do not delete non-qualifying historical records from the source dataset.
- The dashboard includes the subscription breakdown, listing/current gain, shortlist, and slider-based filters.

The authoritative rules are in `IPO_FILTER_RULES.md`.

## Data sources and automated jobs

- **Historical IPO data:** `ipos.json`, mirrored into `data.js` for the static browser dashboard.
- **Live IPO feed:** Groww subscription data is saved in `live-ipo-data.json`.
- **Current market price (CMP):** Screener.in mappings are stored in `screener_map.json`.
- `.github/workflows/refresh-groww-ipo.yml` refreshes the live feed hourly.
- `.github/workflows/ipo-lifecycle.yml` advances live records through Apply, Waiting for Listing, and Listed.
- `.github/workflows/daily-price-update.yml` updates prices only for IPOs that pass the hard eligibility rules, while preserving all historical records.
- `.github/workflows/python-tests.yml` runs the Python test suite.

The price updater uses exact company-name matching and stops safely when Screener denies or throttles requests. It does not bypass access restrictions.

## Local preview

Open `index.html` in a browser. No build step is required.
