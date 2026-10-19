# IPO Lens Dashboard Inclusion Rules

These are the standing, hard-coded inclusion and exclusion rules for IPO Lens. Apply them to the existing IPO dataset and every newly discovered/live IPO before displaying it on the dashboard. Keep the full historical source records in `ipos.json` and `data.js`; filter at display/update time rather than deleting historical records.

## Inclusion criteria

Eligibility depends on the IPO lifecycle stage:

1. **Open IPOs:** display all IPOs currently accepting applications, regardless of QIB subscription or sector. Pre-Apply records are hidden.
2. **Waiting for Listing:** require QIB subscription >= 50x and no excluded-sector match. Listing gain is not required before listing.
3. **Listed IPOs:** require QIB subscription >= 10x, listing gain >= 15%, and no excluded-sector match. Exclude missing or invalid QIB/listing-gain values.

## Sector exclusions — hard-coded

Exclude bank-related businesses, NBFCs, brokers/broking businesses, asset managers, and pharmaceutical/biopharmaceutical/biotechnology businesses, even if they pass the QIB and listing-gain thresholds.

- Financial-sector company-name terms: bank, banking, finance, financial, NBFC, broker, broking, securities, asset, capital, trusteeship, insurance, wealth, lending, credit, microfinance, investment/investments, and fund.
- Also exclude these explicit financial-sector businesses:
  - ICICI Prudential Asset
  - Moneyview
  - Rikhav Securities Ltd.
  - Beacon Trusteeship
  - Pune E-Stock Broking
  - Dam Capital Advisors Ltd.
  - Manba Finance Ltd.
  - Northern Arc Capital
  - Bajaj Housing Finance Ltd.
  - RNFI Services
  - One MobiKwik Systems Ltd.
- Explicit user-requested removal from the dashboard: **NACDAC Infrastructure Ltd.** (keep its historical record in the archive, but do not display or update it).
- Pharmaceutical/biotech company-name terms: pharma, pharmaceutical, pharmaceuticals, biopharma, biotechnology, and biotech.

Apply these sector exclusions in the dashboard's data-filtering path before calculating metrics or rendering IPO cards. Apply the same rules to all newly added/live IPOs so excluded sectors do not reappear.

## Lifecycle-stage handling

- **Open IPOs:** display every application-open record; no QIB or sector filter. Exclude Pre-Apply records.
- **Waiting for Listing:** require QIB >= 50x and no excluded-sector match.
- **Listed IPOs:** require QIB >= 10x, listing gain >= 15%, and no excluded-sector match.
- Do not use current gain as an eligibility criterion.

## Other dashboard behavior

- Current gain is displayed as a percentage but is not an inclusion filter.
- Display Listing Gain and Current Gain as percentages.
- Keep a listed IPO only if it passes QIB >= 10x, listing gain >= 15%, and none of the excluded-sector rules. Apply the lifecycle-stage rules above to open and waiting IPOs.

## Logic

```text
open_ipo = application_open AND NOT pre_apply
waiting_ipo = valid_qib AND (qib >= 50) AND NOT excluded_financial_sector AND NOT excluded_pharma_or_biotech_sector
listed_ipo = valid_qib AND (qib >= 10) AND valid_listing_gain AND (listing_gain >= 0.15) AND NOT excluded_financial_sector AND NOT excluded_pharma_or_biotech_sector
```

## Current archive count reconciliation (2026-10-19)

- Historical archive: **323** unique IPO records.
- This snapshot predates the current Listed IPO QIB threshold of 10x; current displayed totals are calculated from the live data.

These are a dated validation snapshot, not fixed thresholds. Future records or corrected source data can change the counts; never weaken the hard filters just to preserve a previous total.
