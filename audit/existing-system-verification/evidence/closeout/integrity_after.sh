#!/usr/bin/env bash
# Closeout data-integrity re-check. Read-only: docker inspect/ls, git, file scans. Writes closeout/integrity_after.txt.
# Prints no secret: env files are checked by key name only, and scan hits are reported as counts and file names.
set -uo pipefail
R=/c/Users/besna/OneDrive/Bureau/secure-ssi-platform; C=$R/audit/existing-system-verification/evidence/closeout
SP=/c/Users/besna/AppData/Local/Temp/claude/b0377565361f0138/d98effa4-4aa7-43c3-a72b-ba17436fece1/scratchpad
OUT=$C/integrity_after.txt
cd "$R"
{
echo "# Data-integrity re-check after the closeout ($(date -Iseconds))"
echo
echo "## 1. Owner containers: image, creation, start time and restarts, compared with docker_before.txt"
for n in secure-ssi-platform-api-gateway-1 secure-ssi-platform-fraud-service-1 secure-ssi-platform-identity-service-1 secure-ssi-platform-mongodb-1 secure-ssi-platform-recovery-service-1 secure-ssi-platform-redis-1 secure-ssi-platform-web-1; do
  now=$(docker inspect -f '{{.Name}}|{{.Image}}|{{.State.Status}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.Created}}' "$n" 2>&1 | sed 's#^/##')
  before=$(grep "^$n|" "$C/docker_before.txt" | head -n 1)
  img_now=$(echo "$now" | cut -d'|' -f2); img_before=$(echo "$before" | cut -d'|' -f3)
  started_now=$(echo "$now" | cut -d'|' -f4); started_before=$(echo "$before" | cut -d'|' -f5)
  echo "$n status=$(echo "$now" | cut -d'|' -f3) restarts=$(echo "$now" | cut -d'|' -f5) image_same=$([ "$img_now" = "$img_before" ] && echo yes || echo NO) started_same=$([ "$started_now" = "$started_before" ] && echo yes || echo "NO ($started_before -> $started_now)") created=$(echo "$now" | cut -d'|' -f6 | cut -c1-19)"
done
echo
echo "## 2. Owner images (tags) compared with docker_before.txt"
docker images --format '{{.Repository}}:{{.Tag}}|{{.ID}}' | grep '^secure-ssi-platform-' | sort | while IFS='|' read -r tag id; do
  b=$(grep "^$tag|" "$C/docker_before.txt" | cut -d'|' -f2); echo "$tag $id $([ "$id" = "$b" ] && echo unchanged || echo "CHANGED (before: ${b:-absent})")"; done
echo
echo "## 3. Owner volumes (names, creation time)"
for v in $(docker volume ls -q | grep '^secure-ssi-platform_'); do echo "$v created=$(docker volume inspect -f '{{.CreatedAt}}' "$v") in_before=$(grep -qx "$v" "$C/docker_before.txt" && echo yes || echo NO)"; done
echo "owner volumes before: $(sed -n '/^## owner volumes/,/^##/p' "$C/docker_before.txt" | grep -c '^secure-ssi-platform_') now: $(docker volume ls -q | grep -c '^secure-ssi-platform_')"
echo
echo "## 4. Separation of the owner and audit stacks (networks per container)"
for n in $(docker ps -a --format '{{.Names}}' | grep -E '^(secure-ssi-platform-|audit-20261121)' | sort); do
  echo "$n project=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$n") networks=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$n")state=$(docker inspect -f '{{.State.Status}}' "$n")"
done
echo "audit containers on the owner network: $(docker network inspect -f '{{range .Containers}}{{.Name}} {{end}}' secure-ssi-platform_default | tr ' ' '\n' | grep -c '^audit-')"
echo "owner containers on audit networks: $(for net in $(docker network ls --format '{{.Name}}' | grep '^audit-20261121'); do docker network inspect -f '{{range .Containers}}{{.Name}} {{end}}' "$net"; done | tr ' ' '\n' | grep -c '^secure-ssi-platform-')"
echo "audit volumes: $(docker volume ls -q | grep -c '^audit-20261121')"
echo
echo "## 5. Git"
echo "branch: $(git branch --show-current)"
echo "HEAD: $(git rev-parse HEAD)"
echo "origin/besna-dev: $(git ls-remote origin refs/heads/besna-dev | cut -f1)"
echo "commits since the closeout start (9fa97d7): $(git rev-list --count 9fa97d7..HEAD)"
echo "other branches touched: $(git for-each-ref --format='%(refname:short) %(objectname:short)' refs/heads | grep -v '^besna-dev ' | tr '\n' ';')"
echo "uncommitted entries now (excluded on purpose):"; git status --porcelain | sed 's/^/  /'
echo
echo "## 6. Environment files"
echo "repo .env files: $(ls -a "$R" | grep -E '^\.env' | tr '\n' ' ')"
echo ".env.example keys changed by the closeout: $(git diff 9fa97d7 HEAD -- .env.example | grep -c '^[+-][A-Z_]*=' ) lines (all from the committed WP and FIX-2/3 work; the closeout itself did not edit it)"
echo "temporary env files left in the scratchpad: $(ls "$SP/audit/" | grep -E 'fix1|grace|tmp' | grep -c '\.env$')"
echo
echo "## 7. Secret and personal-data scan of the closeout files (committed and local-only)"
cd "$C"
files=$(find . -type f \( -name '*.log' -o -name '*.txt' -o -name '*.json' -o -name '*.mjs' -o -name '*.py' -o -name '*.sh' \) ! -name 'integrity_after.txt')
echo "files scanned: $(echo "$files" | wc -l)"
echo "three-part JWTs (header.payload.signature): $(echo "$files" | xargs grep -aoE 'eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}' 2>/dev/null | wc -l)"
echo "MongoDB URIs with credentials: $(echo "$files" | xargs grep -aoE 'mongodb(\+srv)?://[^:/@ \"]+:[^@ \"]+@' 2>/dev/null | wc -l)"
echo "password/secret assignments with a value: $(echo "$files" | xargs grep -aoiE '(password|secret|api_key|private_key)[a-z_]*[\"]?[:=][\" ]*[A-Za-z0-9+/_-]{12,}' 2>/dev/null | grep -viE 'synthetic|example|placeholder|fixturePass|PASSWORD\$' | wc -l)"
echo "e-mail addresses outside the synthetic test domains: $(echo "$files" | xargs grep -aohE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}' 2>/dev/null | grep -vE '@(wp31\.test|example\.test|example\.com|anthropic\.com)$' | sort -u | wc -l)"
echo "11-digit numbers (national ID shape): $(echo "$files" | xargs grep -aoE '\b[1-9][0-9]{10}\b' 2>/dev/null | wc -l)"
} > "$OUT" 2>&1
cat "$OUT"
