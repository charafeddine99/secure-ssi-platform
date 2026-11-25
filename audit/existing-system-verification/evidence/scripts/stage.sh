#!/usr/bin/env bash
# Usage: stage.sh <name> <script.mjs> [args]  - resets the ISOLATED audit stack, then runs one harness stage under run_limited (scripts/watchdog.sh; report 11, I-5).
set -uo pipefail
cd "C:/Users/besna/OneDrive/Bureau/secure-ssi-platform"
R=/c/Users/besna/OneDrive/Bureau/secure-ssi-platform; E=$R/audit/existing-system-verification/evidence; SP=/c/Users/besna/AppData/Local/Temp/claude/b0377565361f0138/d98effa4-4aa7-43c3-a72b-ba17436fece1/scratchpad/audit
DC="docker compose -p audit-20261121 --env-file $SP/audit.env -f $R/docker-compose.yml -f $E/scripts/wp31.override.yml"
(cd $R && $DC up -d >/dev/null 2>&1)
bash $E/scripts/reset_audit.sh
(cd $R && $DC restart identity-service recovery-service fraud-service >/dev/null 2>&1)
for i in $(seq 1 30); do n=$(docker ps --filter label=com.docker.compose.project=audit-20261121 --filter health=healthy -q | wc -l); [ "$n" -ge 7 ] && break; sleep 3; done
# Wait until sign-in answers (400/401/422 = ready; 502/503 = not yet), as the earlier reset did.
for i in $(seq 1 40); do code=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "content-type: application/json" -H "origin: http://localhost:29300" -H "x-ssi-client: web" -d "{}" http://localhost:29300/api/v1/identity/auth/token); case "$code" in 400|401|422) echo "login-route=$code"; break;; esac; sleep 3; done
cd $E; . $E/scripts/watchdog.sh; name=$1; shift; start=$(date +%s)
WP31_USERS=$(cygpath -w $SP/users.json) WP31_STATE=$(cygpath -w $SP/wp31_state.json) WP31_SCRATCH=$(cygpath -w $SP) run_limited 2400 node --experimental-strip-types scripts/"$@" > $name.log 2>&1
echo "exit=$? secs=$(( $(date +%s)-start ))" >> $name.log
echo "$name: PASS $(grep -c '^PASS' $name.log) FAIL $(grep -c '^FAIL' $name.log) $(tail -1 $name.log)"
