# IPO Lens Dashboard Inclusion Rules

These are the current standing filters for the IPO Lens dashboard. Apply them to the existing IPO dataset and every newly discovered/live IPO before showing it on the dashboard.

## Inclusion criteria

An IPO is included only when **both** conditions pass:

1. **QIB subscription >= 50x**
   - Exclude values below 50x.
   - Exclude missing, blank, dash, or otherwise invalid QIB values.
   - This supersedes the earlier 30x threshold.

2. **Listing gain >= 15%**
   - Exclude listing gain below 15%.
   - Exclude missing or invalid listing-gain values.
   - This supersedes the earlier 10% threshold.

## Dashboard behavior

- Apply these filters to the existing dataset and to newly added/live IPOs.
- Keep IPOs that pass both criteria.
- Drop IPOs that fail either criterion from the dashboard dataset.
- Current gain is displayed as a percentage but is **not** an inclusion filter.
- Display Listing Gain and Current Gain as percentages.

## Logic

```text
include_ipo = valid_qib AND (qib >= 50) AND valid_listing_gain AND (listing_gain >= 0.15)
```

This file documents the required behavior. The live-IPO ingestion/filtering code must read or implement these same rules for automatic enforcement.
