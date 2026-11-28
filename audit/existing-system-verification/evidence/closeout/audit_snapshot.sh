#!/usr/bin/env bash
# Read-only snapshot of the ISOLATED audit-20261121 identity database: audit volume and managed-key bookkeeping.
# Refuses to run against any container that is not labelled with the audit compose project. Prints no secrets.
set -euo pipefail
C=audit-20261121-mongodb-1
[[ "$C" == audit-20261121-* ]] || { echo "refusing"; exit 1; }
docker inspect "$C" --format '{{index .Config.Labels "com.docker.compose.project"}}' | grep -qx audit-20261121 || { echo "refusing: not audit project"; exit 1; }
docker exec "$C" sh -c 'mongosh --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --eval '"'"'
const d = db.getSiblingDB("secure_identity");
const types = ["KEY_RECONCILIATION_CLAIMED","KEY_RECONCILIATION_COMPLETED","KEY_RECONCILIATION_FAILED","KEY_PROVIDER_MISMATCH","MANAGED_KEY_DESTROYED"];
const byType = {}; for (const t of types) byType[t] = d.audit_events.countDocuments({eventType: t});
const keys = d.managed_keys.find({}, {_id:0, keyId:1, state:1, reconciliationAttempts:1, lastProviderSyncAt:1, failureCode:1, version:1}).sort({keyId:1}).toArray()
  .map(k => ({keyId: k.keyId, state: k.state, attempts: k.reconciliationAttempts, lastSync: k.lastProviderSyncAt, failure: k.failureCode ?? null, version: k.version}));
print(JSON.stringify({at: new Date(), auditEvents: d.audit_events.countDocuments({}), auditOutbox: d.audit_outbox.countDocuments({}), reconciliationEvents: byType, managedKeys: keys}));
'"'"''
