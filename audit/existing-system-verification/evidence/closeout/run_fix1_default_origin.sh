#!/usr/bin/env bash
# Closeout: FIX-1 re-check in the DEFAULT setup (IDENTITY_PUBLIC_ORIGIN empty) on the ISOLATED audit-20261121 stack.
# The audit env normally sets a public origin, which hides F-01. This run recreates ONLY the audit identity service
# from a temporary copy of the audit env with that one key emptied, runs audit_fix1_origin.mjs, then recreates the
# service from the normal audit env and deletes the temporary copy. The owner stack is never addressed: every
# compose call names the audit project, and reset_audit.sh refuses containers without its project label.
set -uo pipefail
R=/c/Users/besna/OneDrive/Bureau/secure-ssi-platform; E=$R/audit/existing-system-verification/evidence
SP=/c/Users/besna/AppData/Local/Temp/claude/b0377565361f0138/d98effa4-4aa7-43c3-a72b-ba17436fece1/scratchpad/audit
TMP=$SP/fix1_default_origin.env
OUT=$E/closeout/fix1_default_origin.log
SVC=audit-20261121-identity-service-1
dc() { (cd "$R" && docker compose -p audit-20261121 --env-file "$1" -f "$R/docker-compose.yml" -f "$E/scripts/wp31.override.yml" "${@:2}"); }
wait_ready() {
  for i in $(seq 1 40); do [ "$(docker inspect -f '{{.State.Health.Status}}' $SVC 2>/dev/null)" = healthy ] && break; sleep 3; done
  for i in $(seq 1 40); do code=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "content-type: application/json" -H "origin: http://localhost:29300" -H "x-ssi-client: web" -d "{}" http://localhost:29300/api/v1/identity/auth/token); case "$code" in 400|401|422) echo "login-route=$code"; return 0;; esac; sleep 3; done
  echo "login route not ready"; return 1
}
: > "$OUT"
{
  echo "== $(date -Iseconds) temporary env: the audit env with only IDENTITY_PUBLIC_ORIGIN emptied"
  sed 's/^IDENTITY_PUBLIC_ORIGIN=.*/IDENTITY_PUBLIC_ORIGIN=/' "$SP/audit.env" > "$TMP"
  echo "keys changed vs audit env: $(diff <(cut -d= -f1,2 "$SP/audit.env") <(cut -d= -f1,2 "$TMP") | grep -c '^>')"
  echo "== reset the isolated data (as every stage does), then recreate only the audit identity service"
  bash "$E/scripts/reset_audit.sh"
  dc "$TMP" up -d --no-deps identity-service 2>&1 | grep -v "^ *$"
  (cd "$R" && docker restart audit-20261121-recovery-service-1 audit-20261121-fraud-service-1 >/dev/null)
  wait_ready
  echo "IDENTITY_PUBLIC_ORIGIN inside the audit identity: '$(docker exec $SVC printenv IDENTITY_PUBLIC_ORIGIN)'"
  echo "== $(date -Iseconds) run audit_fix1_origin.mjs"
  (cd "$E" && WP31_USERS=$(cygpath -w $SP/users.json) WP31_STATE=$(cygpath -w $SP/wp31_state.json) WP31_SCRATCH=$(cygpath -w $SP) timeout 600 node --experimental-strip-types scripts/audit_fix1_origin.mjs)
  echo "exit=$?"
  echo "== $(date -Iseconds) restore the audit identity from the normal audit env and delete the temporary env"
  dc "$SP/audit.env" up -d --no-deps identity-service 2>&1 | grep -v "^ *$"
  rm -f "$TMP"
  wait_ready
  echo "IDENTITY_PUBLIC_ORIGIN restored: $( [ -n "$(docker exec $SVC printenv IDENTITY_PUBLIC_ORIGIN)" ] && echo yes || echo NO )"
  echo "temporary env deleted: $( [ -e "$TMP" ] && echo NO || echo yes )"
} >> "$OUT" 2>&1
grep -a "^TOTAL\|^exit=\|restored\|deleted\|inside the audit" "$OUT"
