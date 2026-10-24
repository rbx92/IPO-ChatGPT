# IPO Lens Dashboard Inclusion Rules

This document explains the dashboard's lifecycle-stage behavior. The authoritative numeric thresholds, company-name exclusions, and suffix normalization list are maintained in `eligibility-rules.json` and loaded by `scripts/rules.py`; do not duplicate those values here or in application code. Apply the rules to existing and newly discovered IPOs at display/update time. `ipos.json` and `data.js` hold only IPOs that pass the Listed rules; non-qualifying records were deleted on 24 Oct 2026 (recoverable from Git history).

## Inclusion criteria

Eligibility depends on the IPO lifecycle stage:

1. **Open IPOs:** display all IPOs currently accepting applications, regardless of QIB subscription or sector. Pre-Apply records are hidden.
2. **Waiting for Listing:** require QIB subscription >= 10x. Listing gain is not required before listing.
3. **Listed IPOs:** require QIB subscription >= 10x and listing gain >= 15%. Exclude missing or invalid QIB/listing-gain values.
4. **No QIB category:** fixed-price SME IPOs with no QIB portion are not eligible at any stage after applications close.
5. **Highlight:** every displayed card that passes its stage's rule gets the rainbow glow (Open IPOs only when QIB >= 10x).
6. **Listing price:** Screener's first daily close is used as the listing price on purpose.

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

## Current archive count (2026-10-24)

- After deleting non-qualifying records: **219** IPO records (104 removed: 41 QIB below 10x, 35 listing gain below 15%, 27 with no QIB category, 1 excluded company).
- This is a dated snapshot, not a fixed threshold; never weaken the hard filters just to preserve a previous total.
