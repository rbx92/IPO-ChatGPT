#!/usr/bin/env bash
# Commit and push changed data files with a retrying rebase. Usage: commit_data.sh "message"
set -e
git add -A ipos.json data.js live-ipo-data.json screener_map.json screener_chart_ids.json yahoo_symbols.json isin_map.json official_closes.json 2>/dev/null || true
if git diff --cached --quiet; then echo "Nothing to commit."; exit 0; fi
git commit -q -m "$1"
for i in 1 2 3; do
  if git pull -q --rebase origin main && git push -q; then exit 0; fi
  git rebase --abort 2>/dev/null || true
  sleep 5
done
exit 1
