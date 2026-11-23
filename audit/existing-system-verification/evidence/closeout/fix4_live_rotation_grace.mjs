// Closeout: a state change found by a ROUTINE reconciliation, live on the ISOLATED audit stack.
// Precondition: the audit identity service runs with IDENTITY_KMS_ROTATION_GRACE_SECONDS=30, so a rotation leaves
// the predecessor ROTATING and the background reconciliation (not the API) moves it to SUSPENDED after the grace.
// With grace 0 (the stack's normal setting) rotate() suspends the predecessor inside the API call instead.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { PROJECT, check, enroll, fact, isolatedMongo, login, results, sleep, stepUp, walletOf } from "../scripts/wp31_lib.mjs";

const BASE = "http://localhost:29300";
const SCRIPTS = new URL("../scripts/", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const SFX = Date.now().toString(36);
const users = { [`holder.grace.${SFX}@wp31.test`]: { name: "Holder grace (synthetic)", role: "holder", password: `Wp31-${Date.now()}-g` } };
execFileSync("docker", ["exec", "-i", "-w", "/app", `${PROJECT}-identity-service-1`, "python", "-"], {
  input: readFileSync(`${SCRIPTS}seed_users.py`, "utf8").replace("json.load(sys.stdin)", `json.loads(${JSON.stringify(JSON.stringify(users))})`), encoding: "utf8",
});
const grace = execFileSync("docker", ["exec", `${PROJECT}-identity-service-1`, "printenv", "IDENTITY_KMS_ROTATION_GRACE_SECONDS"], { encoding: "utf8" }).trim();
fact("setup", "the audit identity runs with a 30 s rotation grace", grace === "30", grace);
const [name] = Object.keys(users);
const holder = await login(BASE, name, users[name].password);
await enroll(holder);
const byKey = (keyId) => JSON.parse(isolatedMongo(`const d=db.getSiblingDB("secure_identity"); const o={};
for (const t of ["KEY_RECONCILIATION_CLAIMED","KEY_RECONCILIATION_COMPLETED","KEY_RECONCILIATION_FAILED"]) o[t]=d.audit_events.countDocuments({eventType:t, subjectId:${JSON.stringify(keyId)}});
print(JSON.stringify(o))`));

const wallet = await walletOf(holder);
const W = `/api/v1/identity/wallets/${wallet.walletId}/keys`;
let key = ((await holder("GET", W)).data.items ?? []).find((k) => k.state === "ACTIVE");
if (!key) key = check("live", "the holder provisions a managed key", await holder("POST", W, {}, { "idempotency-key": `closeout-gkey-${SFX}` }), (r) => r.status === 201).data;
check("rotation", "the holder rotates the key with step-up", await holder("POST", `${W}/${key.keyId}/rotate`, {}, { "idempotency-key": `closeout-grot-${SFX}`, ...(await stepUp(holder, "wallet.key.rotate", key.keyId)) }), (r) => r.status === 200);
const right = (await holder("GET", `${W}/${key.keyId}`)).data;
fact("rotation", "right after the call the predecessor is ROTATING (the API did not finish it)", right?.state === "ROTATING", right?.state);
const before = byKey(key.keyId);
let predecessor = right;
const started = Date.now();
for (let i = 0; i < 48 && predecessor?.state !== "SUSPENDED"; i += 1) { await sleep(5_000); predecessor = (await holder("GET", `${W}/${key.keyId}`)).data; }
const after = byKey(key.keyId);
fact("fix4-live", "the routine reconciliation moved the predecessor to SUSPENDED", predecessor?.state === "SUSPENDED", `${predecessor?.state} after ${Math.round((Date.now() - started) / 1000)} s`);
fact("fix4-live", "that state change is audited for this key (claim + completion)",
  after.KEY_RECONCILIATION_CLAIMED >= before.KEY_RECONCILIATION_CLAIMED + 1 && after.KEY_RECONCILIATION_COMPLETED >= before.KEY_RECONCILIATION_COMPLETED + 1, `${JSON.stringify(before)} -> ${JSON.stringify(after)}`);
const passed = results.filter((r) => r.pass).length;
console.log(`\nTOTAL pass=${passed} fail=${results.length - passed}`);
process.exit(results.length === passed ? 0 : 1);
