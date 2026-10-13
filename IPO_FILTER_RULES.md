# IPO Lens Dashboard Inclusion Rules

These are the standing, hard-coded inclusion and exclusion rules for IPO Lens. Apply them to the existing IPO dataset and every newly discovered/live IPO before displaying it on the dashboard.

## Inclusion criteria

An IPO is included only when all conditions pass:

1. **QIB subscription >= 50x**
   - Exclude values below 50x.
   - Exclude missing, blank, dash, or invalid QIB values.
   - This supersedes the earlier 30x threshold.

2. **Listing gain >= 15%**
   - Exclude listing gain below 15%.
   - Exclude missing or invalid listing-gain values.
   - This supersedes the earlier 10% threshold.

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
- Pharmaceutical/biotech company-name terms: pharma, pharmaceutical, pharmaceuticals, biopharma, biotechnology, and biotech.

Apply these sector exclusions in the dashboard's data-filtering path before calculating metrics or rendering IPO cards. Apply the same rules to all newly added/live IPOs so excluded sectors do not reappear.

## Other dashboard behavior

- Current gain is displayed as a percentage but is not an inclusion filter.
- Display Listing Gain and Current Gain as percentages.
- Keep an IPO only if it passes QIB >= 50x, listing gain >= 15%, and none of the excluded-sector rules.

## Logic

```text
include_ipo = valid_qib AND (qib >= 50) AND valid_listing_gain AND (listing_gain >= 0.15) AND NOT excluded_financial_sector AND NOT excluded_pharma_or_biotech_sector
```
