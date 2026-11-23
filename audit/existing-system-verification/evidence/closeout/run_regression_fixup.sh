#!/usr/bin/env bash
# Closeout regression, fix-up run. run_regression_chain.sh called the seven screenshot stages without the
# screenshot-folder argument (argv[2]), so each crashed at mkdirSync(undefined) before any request: a harness
# invocation error, not a product result. Those first logs are kept in closeout/run1_missing_shots_arg/.
# This run waits for the first chain to finish, runs ui first (it needs the scenarios data the first chain just
# created, so no reset), then each other screenshot stage with its own reset, as on 21 November.
set -uo pipefail
E=/c/Users/besna/OneDrive/Bureau/secure-ssi-platform/audit/existing-system-verification/evidence
SHOTS=/c/Users/besna/AppData/Local/Temp/claude/b0377565361f0138/d98effa4-4aa7-43c3-a72b-ba17436fece1/scratchpad/audit/shots
cd "$E"
until grep -q "^chain done" closeout/chain_regression.txt 2>/dev/null; do sleep 10; done
mkdir -p closeout/run1_missing_shots_arg
for s in browser pages wp32_scan wp32_card wp32_cross wp32_ui ui; do
  [ -f "closeout/$s.log" ] && mv "closeout/$s.log" "closeout/run1_missing_shots_arg/$s.log"
done
OUT=closeout/chain_regression_fixup.txt
: > "$OUT"
run() { bash scripts/stage.sh "closeout/$1" "$2" "$(cygpath -w "$SHOTS/$3")" >> "$OUT" 2>&1; }
noreset() { bash scripts/run_noreset.sh "closeout/$1" "$2" "$(cygpath -w "$SHOTS/$3")" >> "$OUT" 2>&1; }
noreset ui wp31_ui.mjs c_ui
run browser wp31_browser.mjs c_browser
run pages wp31_pages.mjs c_pages
run wp32_scan wp32_scan_request_uri.mjs c_scan
run wp32_card wp32_card.mjs c_card
run wp32_cross wp32_cross_device.mjs c_cross
run wp32_ui wp32_ui.mjs c_wp32ui
echo "fixup done $(date -Iseconds)" >> "$OUT"
