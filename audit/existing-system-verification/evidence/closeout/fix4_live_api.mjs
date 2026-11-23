// Closeout: FIX-4 / FIX-6 live checks through the real API of the running ISOLATED audit-20261121 stack.
// Fresh synthetic users only. Reads audit counts from the isolated MongoDB. Prints no secrets.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { PROJECT, check, enroll, fact, isolatedMongo, login, results, sleep, stepUp, walletOf } from "../scripts/wp31_lib.mjs";

const BASE = "http://localhost:29300";
const SCRIPTS = new URL("../scripts/", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const SFX = Date.now().toString(36);
const users = {
  [`holder.live.${SFX}@wp31.test`]: { name: "Holder live (synthetic)", role: "holder", password: `Wp31-${Date.now()}-h` },
  [`admin.live.${SFX}@wp31.test`]: { name: "Admin live (synthetic)", role: "admin", password: `Wp31-${Date.now()}-a` },
};
execFileSync("docker", ["exec", "-i", "-w", "/app", `${PROJECT}-identity-service-1`, "python", "-"], {
  input: readFileSync(`${SCRIPTS}seed_users.py`, "utf8").replace("json.load(sys.stdin)", `json.loads(${JSON.stringify(JSON.stringify(users))})`), encoding: "utf8",
});
const [holderName, adminName] = Object.keys(users);
const holder = await login(BASE, holderName, users[holderName].password);
const admin = await login(BASE, adminName, users[adminName].password);
await enroll(holder);

const counts = () => JSON.parse(isolatedMongo(`const d=db.getSiblingDB("secure_identity"); const o={};
for (const t of ["KEY_RECONCILIATION_CLAIMED","KEY_RECONCILIATION_COMPLETED","KEY_RECONCILIATION_FAILED"]) o[t]=d.audit_events.countDocuments({eventType:t});
o.total=d.audit_events.countDocuments({}); print(JSON.stringify(o))`));
const keyDoc = (keyId) => JSON.parse(isolatedMongo(`print(JSON.stringify(db.getSiblingDB("secure_identity").managed_keys.findOne({keyId:${JSON.stringify(keyId)}},{_id:0,state:1,reconciliationAttempts:1,lastProviderSyncAt:1,version:1})))`));

const wallet = await walletOf(holder);
const W = `/api/v1/identity/wallets/${wallet.walletId}/keys`;
let key = ((await holder("GET", W)).data.items ?? []).find((k) => k.state === "ACTIVE");
if (!key) key = check("live", "the holder provisions a managed key", await holder("POST", W, {}, { "idempotency-key": `closeout-key-${SFX}` }), (r) => r.status === 201).data;
fact("live", "the key is ACTIVE", key?.state === "ACTIVE", key?.state);

// 1) routine syncs of a fresh key: they run, but write no reconciliation audit event
const c0 = counts();
const k0 = keyDoc(key.keyId);
await sleep(130_000);
const c1 = counts();
const k1 = keyDoc(key.keyId);
fact("fix4-live", "routine syncs of the new key ran", new Date(k1.lastProviderSyncAt) > new Date(k0.lastProviderSyncAt) && k1.version > k0.version, `version ${k0.version}->${k1.version}`);
fact("fix4-live", "routine syncs wrote no reconciliation audit event",
  c1.KEY_RECONCILIATION_CLAIMED === c0.KEY_RECONCILIATION_CLAIMED && c1.KEY_RECONCILIATION_COMPLETED === c0.KEY_RECONCILIATION_COMPLETED && c1.KEY_RECONCILIATION_FAILED === c0.KEY_RECONCILIATION_FAILED, JSON.stringify(c1));
fact("fix6-live", "the retry counter stays 0 across routine syncs", k1.reconciliationAttempts === 0, String(k1.reconciliationAttempts));

// 2) a real state change: voluntary rotation (grace 0 s on the audit stack) is finished by the next routine sync
check("fix4-live", "the holder rotates the key with step-up", await holder("POST", `${W}/${key.keyId}/rotate`, {}, { "idempotency-key": `closeout-rot-${SFX}`, ...(await stepUp(holder, "wallet.key.rotate", key.keyId)) }), (r) => r.status === 200);
let predecessor = null;
for (let i = 0; i < 40; i += 1) { await sleep(5_000); predecessor = (await holder("GET", `${W}/${key.keyId}`)).data; if (predecessor?.state === "SUSPENDED") break; }
const c2 = counts();
fact("fix4-live", "the routine sync finished the rotation (ROTATING -> SUSPENDED)", predecessor?.state === "SUSPENDED", predecessor?.state);
fact("fix4-live", "that state change is audited (claim + completion)",
  c2.KEY_RECONCILIATION_CLAIMED >= c1.KEY_RECONCILIATION_CLAIMED + 1 && c2.KEY_RECONCILIATION_COMPLETED >= c1.KEY_RECONCILIATION_COMPLETED + 1, JSON.stringify(c2));

// 3) administrative reconciliation is always audited, even when nothing changes
const successor = ((await holder("GET", W)).data.items ?? []).find((k) => k.state === "ACTIVE");
check("fix4-live", "an administrator reconciles the successor key", await admin("POST", `${W}/${successor.keyId}/reconcile`, { reason: "closeout live check" }), (r) => r.status === 200);
const c3 = counts();
fact("fix4-live", "the administrative reconciliation is audited (claim + completion)",
  c3.KEY_RECONCILIATION_CLAIMED === c2.KEY_RECONCILIATION_CLAIMED + 1 && c3.KEY_RECONCILIATION_COMPLETED === c2.KEY_RECONCILIATION_COMPLETED + 1, JSON.stringify(c3));

console.log(`counts c0=${JSON.stringify(c0)} c1=${JSON.stringify(c1)} c2=${JSON.stringify(c2)} c3=${JSON.stringify(c3)}`);
const passed = results.filter((r) => r.pass).length;
console.log(`\nTOTAL pass=${passed} fail=${results.length - passed}`);
process.exit(results.length === passed ? 0 : 1);
