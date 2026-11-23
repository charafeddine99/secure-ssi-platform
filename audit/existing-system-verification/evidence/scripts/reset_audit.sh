#!/usr/bin/env bash
# Empties application collections in the ISOLATED audit-20261121 MongoDB only. Never touches other projects or volumes.
set -euo pipefail
C=audit-20261121-mongodb-1
[[ "$C" == audit-20261121-* ]] || { echo "refusing"; exit 1; }
docker inspect "$C" --format '{{index .Config.Labels "com.docker.compose.project"}}' | grep -qx audit-20261121 || { echo "refusing: not audit project"; exit 1; }
U=$(docker exec "$C" printenv MONGO_INITDB_ROOT_USERNAME); P=$(docker exec "$C" printenv MONGO_INITDB_ROOT_PASSWORD)
docker exec "$C" mongosh --quiet -u "$U" -p "$P" --authenticationDatabase admin --eval '
for (const n of db.getMongo().getDBNames()) { if (["admin","local","config"].includes(n)) continue;
  const d=db.getSiblingDB(n); for (const c of d.getCollectionNames()) { if (!c.startsWith("system.")) d.getCollection(c).deleteMany({}); } }
print("isolated audit databases emptied")'
# The ledger anchor must be cleared together with the ledger, otherwise rollback protection (correctly) blocks status lists.
I=audit-20261121-identity-service-1
docker inspect "$I" --format '{{index .Config.Labels "com.docker.compose.project"}}' | grep -qx audit-20261121 || { echo "refusing"; exit 1; }
MSYS_NO_PATHCONV=1 docker exec "$I" sh -c 'rm -f "$IDENTITY_REVOCATION_ANCHOR_PATH"' && echo "ledger anchor cleared"
# Rate-limit counters live in the isolated Redis; carrying them between stages makes TOTP-based steps time out.
RD=audit-20261121-redis-1
docker inspect "$RD" --format '{{index .Config.Labels "com.docker.compose.project"}}' | grep -qx audit-20261121 || { echo "refusing"; exit 1; }
docker exec "$RD" redis-cli FLUSHALL >/dev/null && echo "isolated redis counters cleared"
