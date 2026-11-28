#!/usr/bin/env bash
# Closeout full regression on the ISOLATED audit-20261121 stack, in the 21 November order.
# Each stage.sh run resets the isolated stack first; ui needs the scenarios data, so it runs without a reset.
set -uo pipefail
E=/c/Users/besna/OneDrive/Bureau/secure-ssi-platform/audit/existing-system-verification/evidence
cd "$E"
OUT=closeout/chain_regression.txt
: > "$OUT"
run() { bash scripts/stage.sh "closeout/$1" "$2" >> "$OUT" 2>&1; }
noreset() { bash scripts/run_noreset.sh "closeout/$1" "$2" >> "$OUT" 2>&1; }
run e2e wp31_e2e.mjs
run browser wp31_browser.mjs
run pages wp31_pages.mjs
run gaps wp31_gaps.mjs
run onboarding wp32_onboarding.mjs
run oid4vp_security wp32_oid4vp_security.mjs
run wp32_scan wp32_scan_request_uri.mjs
run wp32_card wp32_card.mjs
run wp32_cross wp32_cross_device.mjs
run wp32_ui wp32_ui.mjs
run scenarios wp31_scenarios.mjs
noreset ui wp31_ui.mjs
echo "chain done $(date -Iseconds)" >> "$OUT"
