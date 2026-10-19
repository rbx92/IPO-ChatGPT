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

The authoritative rules are in `IPO_FILTER_RULES.md`.

## Data sources and automated jobs

- **Historical IPO data:** `ipos.json`, mirrored into `data.js` for the static browser dashboard.
- **Live IPO feed:** Groww subscription data is saved in `live-ipo-data.json`.
- **Current market price (CMP):** Screener.in is used for both SME and Mainboard IPOs, with exact company-name matching and saved paths in `screener_map.json`. Requests run in batches of 9 with a 60-second delay; completed batches are saved.
- `.github/workflows/refresh-groww-ipo.yml` refreshes the live feed hourly.
- `.github/workflows/ipo-lifecycle.yml` advances live records through Apply, Waiting for Listing, and Listed on weekdays or when manually dispatched. Code pushes do not trigger live Screener requests.
- `.github/workflows/daily-price-update.yml` updates eligible IPO CMP from Screener.in in batches of 9 with a 60-second delay and preserves all historical records.

The Screener CMP updater uses exact company-name matching and saved Screener paths, writes current-price fields only, preserves the full historical dataset, and stops on throttling or parse errors while retaining completed batches. The lifecycle updater may use Screener's first available daily close as a clearly labelled listing-price proxy. It also stops further network lookups on throttling and does not demote records already marked Listed when a lookup fails.

## Local preview

Open `index.html` in a browser. No build step is required.
