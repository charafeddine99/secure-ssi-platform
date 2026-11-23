#!/usr/bin/env bash
# Runs one harness stage WITHOUT resetting (for stages that need the previous stage's data).
set -uo pipefail
E=/c/Users/besna/OneDrive/Bureau/secure-ssi-platform/audit/existing-system-verification/evidence; SP=/c/Users/besna/AppData/Local/Temp/claude/b0377565361f0138/d98effa4-4aa7-43c3-a72b-ba17436fece1/scratchpad/audit; cd $E; name=$1; shift; start=$(date +%s)
WP31_USERS=$(cygpath -w $SP/users.json) WP31_STATE=$(cygpath -w $SP/wp31_state.json) WP31_SCRATCH=$(cygpath -w $SP) timeout 2400 node --experimental-strip-types scripts/"$@" > $name.log 2>&1
echo "exit=$? secs=$(( $(date +%s)-start ))" >> $name.log
echo "$name: PASS $(grep -c '^PASS' $name.log) FAIL $(grep -c '^FAIL' $name.log) $(tail -1 $name.log)"
