# IPO Lens — Indian IPO Dashboard

Static dashboard intended for GitHub Pages. It imports the supplied IPO dataset and preserves its company names and historical fields as provided.

## What's included
- Responsive card grid matching the supplied reference: stock-type pill, QIB headline, QIB/HNI/Retail breakdown, listing gain and current gain.
- Search, Mainboard/SME filters, gain filter, and sorting by listing date, gains, total subscription, or company name.
- 323 IPO rows imported from `Pasted markdown(2).md` into `data/ipos.json` and `data.js`.
- A clear source/data caveat: imported prices are not live until the updater is configured and succeeds.
- `scripts/refresh_data.py` and a daily GitHub Actions workflow as the integration scaffold.

## Publish on GitHub Pages
1. Create a new GitHub repository, e.g. `ipo-lens`.
2. Upload the contents of this folder (the files inside, not the parent folder).
3. Go to **Settings → Pages** and choose **Deploy from a branch**, branch `main`, folder `/ (root)`.
4. Save and wait for GitHub Pages to publish the site.

## Data and refresh architecture
- Historical/company identity fields: use the supplied Excel-derived dataset as the source of truth. Do not rename companies by fuzzy matching.
- New/live IPO subscription data: `https://groww.in/ipo/subscription`.
- Daily current price: `https://www.screener.in/`.
- `scripts/refresh_data.py` is intentionally a safe scaffold. Before turning on automated scraping, confirm each source's terms, rate limits, and permitted access, then implement stable source-specific parsers. Do not guess data or silently overwrite an existing row when company identity is uncertain.
- Scheduled workflow runs daily and currently validates the existing JSON. It does **not** claim to have fetched live data. Add verified scrapers and credentials only after confirming the allowed access method. GitHub Pages serves static files; the updater commits refreshed data back to the repository.

## Local preview
Open `index.html` in a browser. No build tools or API keys are required for the static view.
