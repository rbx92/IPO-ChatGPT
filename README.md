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
- **Current market price (CMP):** Screener.in is used for both SME and Mainboard IPOs, with exact company-name matching and saved paths in `screener_map.json`. Requests run in batches of 9 with a 60-second delay; completed batches are saved.
- `.github/workflows/refresh-groww-ipo.yml` refreshes the live feed hourly.
- `.github/workflows/ipo-lifecycle.yml` advances live records through Apply, Waiting for Listing, and Listed on weekdays or when manually dispatched. Code pushes do not trigger live Screener requests.
- `.github/workflows/daily-price-update.yml` updates eligible IPO CMP from Screener.in in batches of 9 with a 60-second delay and preserves all historical records.
- Screener CMP updates are the active path for both Mainboard and SME; Groww mapping validation is diagnostic only and does not update CMP.
- `.github/workflows/groww-mapping-validation.yml` audits exact Groww instrument matches for all historical Mainboard and SME IPOs and uploads a CSV/JSON report without changing IPO prices.
- `.github/workflows/dashboard-browser-smoke.yml` checks the live GitHub Pages dashboard on desktop and mobile with a headless browser.
- `.github/workflows/python-tests.yml` runs the Python test suite.

The Screener CMP updater uses exact company-name matching and saved Screener paths, writes current-price fields only, preserves the full historical dataset, and stops on throttling or parse errors while retaining completed batches. The lifecycle updater may use Screener's first available daily close as a clearly labelled listing-price proxy. It also stops further network lookups on throttling and does not demote records already marked Listed when a lookup fails.

## Local preview

Open `index.html` in a browser. No build step is required.
