#!/usr/bin/env bash
# Tests run_limited (scripts/watchdog.sh) against the old coreutils `timeout`, with a hung node process that has a child
# (the shape of the 2026-11-23 hang: node plus its headless Edge). No Docker needed. Output: watchdog_test.txt
set -uo pipefail
. /c/Users/besna/OneDrive/Bureau/secure-ssi-platform/audit/existing-system-verification/evidence/scripts/watchdog.sh
export MSYS2_ARG_CONV_EXCL='*'
TMPF=$(mktemp)
alive() { # number of node.exe processes whose command line contains $1
  powershell.exe -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Where-Object { \$_.CommandLine -match '$1' }).Count" | tr -d '\r'
}
stop_marked() { # stops every node.exe whose command line contains $1, with its child processes
  powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Where-Object { \$_.CommandLine -match '$1' } | ForEach-Object { taskkill /PID \$_.ProcessId /T /F | Out-Null }"
}
hang() { # node code that never ends and starts a child that never ends; both command lines carry the marker $1
  echo "const {spawn}=require('child_process'); spawn(process.execPath,['-e','setInterval(()=>{},1000) /*$1-child*/'],{stdio:'ignore'}); setInterval(()=>{},1000) /*$1-parent*/"
}

echo "# run_limited test, $(date -Iseconds)"
echo "1. The exit code passes through"
run_limited 30 node -e "process.exit(3)"; echo "   exit=$? (expected 3)"

echo "2. Environment variables set before the call reach the stage"
out=$(WD_PROBE=reached run_limited 30 node -e "console.log(process.env.WD_PROBE)"); echo "   printed=$out (expected reached)"

echo "3. stdout and stderr follow the redirection"
run_limited 30 node -e "console.log('out line'); console.error('err line')" > "$TMPF" 2>&1
echo "   log lines=$(wc -l < "$TMPF") (expected 2)"

echo "4. Old runner: coreutils timeout 5 s on a hung node with a child"
start=$SECONDS
timeout 5 node -e "$(hang wdold)" & tp=$!
sleep 15
echo "   after $((SECONDS-start)) s: timeout still waiting=$(kill -0 $tp 2>/dev/null && echo yes || echo no), marked node processes alive=$(alive wdold)"
stop_marked wdold; wait $tp 2>/dev/null
echo "   after the manual cleanup: marked node processes alive=$(alive wdold)"

echo "5. New runner: run_limited 5 s on the same hung node with a child"
start=$SECONDS
run_limited 5 node -e "$(hang wdnew)" 2>"$TMPF"; rc=$?
echo "   exit=$rc (expected 124) after $((SECONDS-start)) s; marked node processes alive=$(alive wdnew) (expected 0)"
echo "   watchdog message: $(cat "$TMPF")"
stop_marked wdnew
rm -f "$TMPF"
