# Changelog

Versions follow MAJOR.MINOR.PATCH. The current version is in `VERSION`.

## 2.0.0 (10 Nov 2026)

Rebuilt data pipeline and cleaned-up repository.

**Data**
- Prices: official NSE/BSE closing prices (bhavcopy) for every stock, matched by ISIN. Yahoo (mainboard) and Screener.in are backups only for stocks the official files miss that day. Thinly traded stocks use their last traded close.
- Listings: an IPO moves to Listed when Groww's IPO page marks it listed, with Groww's official listing price.
- Groww feed no longer stops when no IPO is open.
- One nightly job runs listings, official prices, then the backups, in order, at 19:40 IST on weekdays.
- Manual jobs: check saved prices against the official closes; backtest the pullback rule.

**Dashboard**
- Listing Price and CMP row restored on listed cards, aligned with the gain row.
- Rainbow glow only on open IPOs with QIB of at least 10x and listed stocks showing a pullback.
- Pullback signal: 15-30% fall from the latest high within 100 days of listing, at or above the first day's close, can repeat after each new high. Shows whether the fall came on heavy, mixed or light selling.
- Anchor lock-in expiry notes on recent listings.
- Refreshes itself every 15 minutes and shows when the data was last updated.

**Repository**
- Code moved into `pipeline/` (common, groww, prices, tools); lookup tables and caches into `data/`.
- Removed the old Screener-based lifecycle job, the CMP history job, the WhatsApp alert, the Groww API test and committed Python cache files.
- Workflows renamed by what they do and how often.

## 1.0.0 (to 23 Oct 2026)

Original dashboard: Groww subscription scraper, Screener.in for prices and listing detection, card layout with filters and shortlist.
