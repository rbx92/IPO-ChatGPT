# IPO Lens — Indian IPO Dashboard

Static dashboard for GitHub Pages. The browser loads historical records from `data.js` and merges in the latest live IPO feed from `live-ipo-data.json`.

## Dashboard behaviour

- Separate sections for Open IPOs, Waiting for Listing, and Listed IPOs.
- Open IPOs: show every IPO currently accepting applications, without a QIB or sector filter. Pre-Apply records are hidden.
- Waiting for Listing: require QIB subscription of at least 10x, regardless of sector.
- Listed IPOs: require QIB subscription of at least 10x and listing gain of at least 15%, regardless of sector. NACDAC Infrastructure Ltd. remains explicitly excluded.
- Current gain is displayed and can be filtered/sorted, but it is not an eligibility rule.
- Eligibility filters affect display and price-update selection; they do not delete non-qualifying historical records from the source dataset. Financial-sector, pharma and biotech companies are allowed; NACDAC Infrastructure Ltd. remains explicitly excluded.
- The dashboard includes the subscription breakdown, listing/current gain, shortlist, and slider-based filters.

The authoritative numeric thresholds and normalized company exclusions are in `eligibility-rules.json`; `scripts/rules.py` reads that configuration. `IPO_FILTER_RULES.md` documents the lifecycle behavior and intent.

## Data sources and automated jobs

- **Historical IPO data:** `ipos.json`, mirrored into `data.js` for the static browser dashboard.
- **Live IPO feed:** Groww subscription data is saved in `live-ipo-data.json`.
- **Current market price (CMP):** The existing updater uses Screener.in for both SME and Mainboard IPOs, with exact company-name matching and saved paths in `screener_map.json`. Automated CMP updates run daily in batches of 9 with a 60-second delay. Screener.in written permission was not obtained; the owner has chosen to scrape. The updater stops on any HTTP 401, 403 or 429 and does not retry or bypass it.
- `.github/workflows/refresh-groww-ipo.yml` refreshes the live feed hourly. Its expired-application checks use India Standard Time (IST). It also runs on pushes that change `scrape_groww_ipo.py` or that workflow file.
- `.github/workflows/ipo-lifecycle.yml` runs on weekdays. Its lifecycle updater, with a 60-second delay between Screener requests, can advance records through Apply, Waiting for Listing, and Listed; date-based decisions use India Standard Time (IST).
- `.github/workflows/daily-price-update.yml` runs on weekdays. It updates eligible IPO CMP in batches of 9 with a 60-second delay while preserving historical records.
- The Groww feed refresh runs hourly. The two Screener-dependent jobs above run on weekdays. Stop them if Screener returns HTTP 401, 403 or 429.

The Screener CMP updater uses exact company-name matching and saved Screener paths, writes current-price fields only, preserves the full historical dataset, and stops on throttling or parse errors while retaining completed batches. The lifecycle updater may use Screener's first available daily close as a clearly labelled listing-price proxy. It also stops further network lookups on throttling and does not demote records already marked Listed when a lookup fails.

## Local preview

Open `index.html` in a browser. No build step is required.
