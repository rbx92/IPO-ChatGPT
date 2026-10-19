# IPO Lens Dashboard Inclusion Rules

This document explains the dashboard's lifecycle-stage behavior. The authoritative numeric thresholds, company-name exclusions, and suffix normalization list are maintained in `eligibility-rules.json` and loaded by `scripts/rules.py`; do not duplicate those values here or in application code. Apply the rules to existing and newly discovered IPOs at display/update time. Keep the full historical source records in `ipos.json` and `data.js`; filtering must not delete historical records.

## Inclusion criteria

Eligibility depends on the IPO lifecycle stage:

1. **Open IPOs:** display all IPOs currently accepting applications, regardless of QIB subscription or sector. Pre-Apply records are hidden.
2. **Waiting for Listing:** require QIB subscription >= 10x. Listing gain is not required before listing.
3. **Listed IPOs:** require QIB subscription >= 10x and listing gain >= 15%. Exclude missing or invalid QIB/listing-gain values.

## Explicit company exclusion

- **NACDAC Infrastructure Ltd.** remains explicitly excluded from the dashboard and price updates. Keep its historical record in the archive, but do not display it or update it.
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

## Current archive count reconciliation (2026-10-19)

- Historical archive: **323** unique IPO records.
- This snapshot predates the current Listed IPO QIB threshold of 10x; current displayed totals are calculated from the live data.

These are a dated validation snapshot, not fixed thresholds. Future records or corrected source data can change the counts; never weaken the hard filters just to preserve a previous total.
