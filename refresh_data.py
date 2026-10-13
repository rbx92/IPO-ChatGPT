"""Safe validation scaffold for IPO Lens.

Implement source-specific Groww/Screener adapters only after checking permitted access,
rate limits and stable response formats. Never fabricate prices or fuzzy-match company names.
"""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
rows = json.loads((ROOT / 'data' / 'ipos.json').read_text(encoding='utf-8'))
required = {'companyName','listingDate','issuePrice','qib','hni','retail','total','listingGain','currentGain','stockType'}
if not isinstance(rows, list):
    raise SystemExit('Expected IPO data to be a list')
for i, row in enumerate(rows):
    missing = required - row.keys()
    if missing:
        raise SystemExit(f'Row {i} missing required fields: {sorted(missing)}')
print(f'Validated {len(rows)} IPO rows. No live scrape performed by scaffold.')
