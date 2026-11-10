# IPO Lens Dashboard Inclusion Rules

This document explains the dashboard's lifecycle-stage behavior. The authoritative numeric thresholds, company-name exclusions, and suffix normalization list are maintained in `eligibility-rules.json` and loaded by `scripts/rules.py`; do not duplicate those values here or in application code. Apply the rules to existing and newly discovered IPOs at display/update time. `ipos.json` and `data.js` hold only IPOs that pass the Listed rules; non-qualifying records were deleted on 24 Oct 2026 (recoverable from Git history).

## Inclusion criteria

Eligibility depends on the IPO lifecycle stage:

1. **Open IPOs:** display all IPOs currently accepting applications, regardless of QIB subscription or sector. Pre-Apply records are hidden.
2. **Waiting for Listing:** require QIB subscription >= 10x. Listing gain is not required before listing.
3. **Listed IPOs:** require QIB subscription >= 10x and listing gain >= 15%. Exclude missing or invalid QIB/listing-gain values.
4. **No QIB category:** fixed-price SME IPOs with no QIB portion are not eligible at any stage after applications close.
5. **Highlight:** the rainbow glow marks cards worth a look today: Open IPOs with QIB >= 10x, and Listed stocks showing the post-listing pullback message.
6. **Listing:** an IPO moves to Listed when Groww's IPO page marks it listed; listing price and listing gain are Groww's official figures (before 9 Nov 2026 Screener's first daily close was used).

## Explicit company exclusion

- **NACDAC Infrastructure Ltd.** remains explicitly excluded from the dashboard and price updates. Do not display it, store it or update it.
- No financial-sector, pharmaceutical, biopharmaceutical, or biotechnology sector exclusions apply. Companies in these sectors are eligible if they meet the relevant lifecycle-stage criteria.

## Lifecycle-stage handling

- **Open IPOs:** display every application-open record; no QIB or sector filter. Exclude Pre-Apply records.
- **Waiting for Listing:** require QIB >= 10x, regardless of sector.
- **Listed IPOs:** require QIB >= 10x and listing gain >= 15%, regardless of sector.
- Do not use current gain as an eligibility criterion.

## Other dashboard behavior

- Current gain is displayed as a percentage but is not an inclusion filter.
- Display Listing Gain and Current Gain as percentages.
- Keep a listed IPO only if it passes QIB >= 10x and listing gain >= 15%, and is not the explicitly excluded company. Apply the lifecycle-stage rules above to open and waiting IPOs.

## Logic

```text
open_ipo = application_open AND NOT pre_apply
waiting_ipo = valid_qib AND (qib >= 10) AND NOT explicitly_excluded_company
listed_ipo = valid_qib AND (qib >= 10) AND valid_listing_gain AND (listing_gain >= 0.15) AND NOT explicitly_excluded_company
```

## Post-listing pullback signal

A listed card shows "Stock fell more than X% in the last N trading days" when QIB >= 50x, listing gain >= 25%, it listed within the last 60 days, and the fall from its highest close since listing to the latest close is 15-30%. N is trading days since that peak. Thresholds live under `pullback_signal` in `eligibility-rules.json`. Daily closes come from Screener via `scripts/update_pullbacks.py` (weekdays 22:07 IST, 60s between requests) and are kept only while a stock can still show the signal.

## Pullback extras (since 10 Nov 2026)

- **Never below issue price:** no pullback signal if the latest close is under the IPO issue price (`require_above_issue_price`).
- **Volume:** the pullback message adds whether the fall came on heavy selling (median volume since the peak at least 1.5x the median before it, ignoring the first 3 listing days), light volume (0.7x or less), or normal volume.
- **Anchor lock-in:** listed cards show when the anchor lock-in ends (50% after 30 days, the rest after 90 days from allotment; allotment taken as 2 trading days before listing when not known), from 10 days before to 5 days after (`anchor_lock_in`).

## Price sources (since 9 Nov 2026)

- **Main source, all stocks:** the official NSE and BSE closing-price files (bhavcopy), via `scripts/update_prices_official.py`. Stocks are identified by ISIN (`isin_map.json`, editable by hand). Closes for the last ~100 days are cached in `official_closes.json` and feed the pullback signal.
- **Backups, only for stocks not priced from the official files that day:** Yahoo Finance for mainboard (`update_prices_yahoo.py`), then Screener.in for anything left (`update_prices.py --stock-type SME`, 60 s between requests) and for SME pullback history (`update_pullbacks.py --stock-type SME`).
- All run in order in one nightly workflow, `daily-data-update.yml`, at 20:00 IST on weekdays.
- `verify-prices.yml` (manual) compares saved prices with the official closes for any day.

## Current archive count (2026-10-24)

- After deleting non-qualifying records: **219** IPO records (104 removed: 41 QIB below 10x, 35 listing gain below 15%, 27 with no QIB category, 1 excluded company).
- This is a dated snapshot, not a fixed threshold; never weaken the hard filters just to preserve a previous total.
