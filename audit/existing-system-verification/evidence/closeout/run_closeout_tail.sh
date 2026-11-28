#!/usr/bin/env bash
# Closeout, last runs on the ISOLATED audit-20261121 stack, after run_regression_fixup.sh:
#  1. The fix-up's ui run hung for 65 minutes inside its own DevTools session, before its first check: the page was
#     loaded and answered a second DevTools client, and axe had not been injected yet. The run's `timeout 2400` did not
#     stop the native node process, so it was stopped by hand with taskkill. Its log is kept in run2_ui_hung/.
#  2. ui needs the scenarios data, which the fix-up's later stages reset, so scenarios runs again (with a reset) and
#     ui runs right after it without a reset, as on 21 November. Both stages run under a watchdog that really stops
#     the stage's node process tree (taskkill), with limits far above their 21 November run times (414 s and 72 s).
#  3. The FIX-1 default-origin re-check (run_fix1_default_origin.sh), under the same kind of watchdog.
set -uo pipefail
E=/c/Users/besna/OneDrive/Bureau/secure-ssi-platform/audit/existing-system-verification/evidence
SHOTS=/c/Users/besna/AppData/Local/Temp/claude/b0377565361f0138/d98effa4-4aa7-43c3-a72b-ba17436fece1/scratchpad/audit/shots
cd "$E"
OUT=closeout/chain_regression_tail.txt
kill_stage() { # stops every node.exe whose command line matches $1, with its child processes (headless Edge)
  local cmd="\$ProgressPreference='SilentlyContinue'; Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Where-Object { \$_.CommandLine -match '$1' } | ForEach-Object { taskkill /PID \$_.ProcessId /T /F }"
  powershell.exe -NoProfile -EncodedCommand "$(printf '%s' "$cmd" | iconv -f utf-8 -t utf-16le | base64 -w0)" >/dev/null 2>&1
}
guarded() { # $1 limit in seconds, $2 regex of the stage's node script, rest: the command
  local limit=$1 pattern=$2; shift 2
  "$@" >> "$OUT" 2>&1 &
  local bg=$! start; start=$(date +%s)
  while kill -0 "$bg" 2>/dev/null; do
    if [ $(( $(date +%s) - start )) -ge "$limit" ]; then
      echo "watchdog: '$pattern' still running after ${limit}s; stopping its process tree" >> "$OUT"
      kill_stage "$pattern"
      break
    fi
    sleep 5
  done
  wait "$bg"
}
until grep -q "^fixup done" closeout/chain_regression_fixup.txt 2>/dev/null; do sleep 10; done
: > "$OUT"
mkdir -p closeout/run2_ui_hung
[ -f closeout/ui.log ] && mv closeout/ui.log closeout/run2_ui_hung/ui.log
guarded 1500 'wp31_scenarios\.mjs' bash scripts/stage.sh closeout/scenarios_rerun wp31_scenarios.mjs
guarded 600 'wp31_ui\.mjs' bash scripts/run_noreset.sh closeout/ui_rerun wp31_ui.mjs "$(cygpath -w "$SHOTS/c_ui2")"
guarded 900 'audit_fix1_origin\.mjs' bash closeout/run_fix1_default_origin.sh
echo "fix1_default_origin: PASS $(grep -c '^PASS' closeout/fix1_default_origin.log) FAIL $(grep -c '^FAIL' closeout/fix1_default_origin.log) $(grep '^exit=' closeout/fix1_default_origin.log | tail -n 1)" >> "$OUT"
echo "tail done $(date -Iseconds)" >> "$OUT"
