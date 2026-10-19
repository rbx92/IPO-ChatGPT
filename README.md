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
- **Current market price (CMP):** Groww Trading API is the sole source for future CMP updates. Exact instrument overrides are stored in `groww_map.json`; the read-only validation workflow audits Mainboard and SME mappings against Groww's instrument master.
- `.github/workflows/refresh-groww-ipo.yml` refreshes the live feed hourly.
- `.github/workflows/ipo-lifecycle.yml` advances live records through Apply, Waiting for Listing, and Listed on weekdays or when manually dispatched. Code pushes do not trigger live Screener requests.
- `.github/workflows/daily-price-update.yml` updates prices only for IPOs that pass the hard eligibility rules, using Groww Trading API only and preserving all historical records. It requires the repository Actions secrets `GROWW_TOTP_TOKEN` and `GROWW_TOTP_SECRET` from an active Groww Trading API TOTP setup.
- Legacy Screener CMP validation workflow has been removed; future CMP updates use Groww only.
- Legacy Screener mapping files are retained only as historical reference; their old CMP validation workflows have been removed.
- `.github/workflows/groww-mapping-validation.yml` audits exact Groww instrument matches for all historical Mainboard and SME IPOs and uploads a CSV/JSON report without changing IPO prices.
- `.github/workflows/dashboard-browser-smoke.yml` checks the live GitHub Pages dashboard on desktop and mobile with a headless browser.
- `.github/workflows/python-tests.yml` runs the Python test suite.

The Groww CMP updater uses exact instrument-name matching plus explicitly reviewed Groww symbol overrides, saves completed batches, and preserves the full historical dataset. It does not use Screener as a CMP fallback. Unmatched or ambiguous instruments retain their existing price and appear in the mapping report. The lifecycle updater may use Screener's first available daily close as a clearly labelled listing-price proxy, but it never writes that value into CMP fields; CMP remains Groww-owned. It also stops further network lookups on throttling and does not demote records already marked Listed when a lookup fails.

## Local preview

Open `index.html` in a browser. No build step is required.
