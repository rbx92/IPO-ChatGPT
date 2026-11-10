# IPO Lens: Indian IPO dashboard

Version 2.0.0 (see `CHANGELOG.md`). Live at https://rbx92.github.io/IPO-ChatGPT/

A static dashboard on GitHub Pages. GitHub Actions update the data; the page
refreshes itself every 15 minutes.

## What it shows

- **Open IPOs:** every IPO accepting applications.
- **Waiting for Listing:** closed IPOs with QIB subscription of at least 10x.
- **Listed IPOs:** QIB of at least 10x and listing gain of at least 15%, with
  listing price, current price (CMP) and gains.
- **Pullback signal** on recently listed strong IPOs, with selling-volume
  context, and **anchor lock-in** dates.
- **Rainbow glow** on open IPOs with QIB of at least 10x and on stocks showing a
  pullback.

All thresholds live in `eligibility-rules.json`. `IPO_FILTER_RULES.md`
explains each rule.

## Layout

```
index.html                 the dashboard
data.js, ipos.json         listed IPOs that pass the rules (data.js is loaded by the page)
live-ipo-data.json         open, waiting and recently listed IPOs from Groww
eligibility-rules.json     every threshold

pipeline/
  common/    paths.py (every file location), rules.py, helpers.py
  groww/     subscriptions.py  hourly: Groww subscription figures
             listings.py       nightly: Apply -> Waiting -> Listed from Groww
  prices/    official.py       nightly: official NSE/BSE closes (main source)
             yahoo.py          backup for mainboard
             screener.py       backup for anything still unpriced
             screener_history.py  backup daily closes for SME pullbacks
             screener_client.py   shared Screener access
  tools/     verify_prices.py  compare saved prices with official closes
             backtest_pullback.py  test the pullback rule on past IPOs
             commit_data.sh    save data changes from the jobs

data/        isin_map.json (edit to fix a match), official_closes.json (cache),
             screener_map.json, screener_chart_ids.json, yahoo_symbols.json
reports/     price checks and backtest results
```

## Automated jobs (`.github/workflows/`)

| Workflow | When | What |
|---|---|---|
| `groww-subscriptions-hourly.yml` | Hourly; every 15 then 5 minutes on IPO closing days | Groww subscription data |
| `nightly-data-update.yml` | Weekdays 19:40 IST | Listings, official prices, then Yahoo and Screener backups |
| `check-prices-manual.yml` | By hand | Saved prices vs official closes, into `reports/` |
| `backtest-pullback-manual.yml` | By hand | Pullback rule backtest, into `reports/backtest/` |

GitHub often starts scheduled jobs late. Screener.in is used without written
permission; its steps stop immediately on HTTP 401, 403 or 429.

## Run locally

Open `index.html` in a browser. Scripts run from the repository root, for
example `python pipeline/prices/official.py`.
