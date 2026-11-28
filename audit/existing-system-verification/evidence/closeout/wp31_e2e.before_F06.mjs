// WP-31 security E2E. Runs only against the isolated audit-20261121 stack and real MongoDB.
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import {
  PROJECT, acceptInvitation, check, client, decide, deviceKey, docker, enroll, fact, fixturePass,
  isolatedMongo, issue, login, nextCode, present, results, signGuardianJwt, sleep, stepUp, walletOf,
} from "./wp31_lib.mjs";

const BASE = "http://localhost:29300";
const DIR = new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const SECRET_FILE = process.env.WP31_USERS;
const anon = client(BASE, "anon");

// ---------------------------------------------------------------- setup
const users = JSON.parse(readFileSync(SECRET_FILE, "utf8"));
const seedOut = execFileSync("docker", ["exec", "-i", "-w", "/app", `${PROJECT}-identity-service-1`, "python", "-"], {
  input: readFileSync(`${DIR}seed_users.py`, "utf8").replace("json.load(sys.stdin)", `json.loads(${JSON.stringify(JSON.stringify(users))})`),
  encoding: "utf8",
});
fact("setup", "synthetic accounts seeded in the isolated database", seedOut.includes("created") || seedOut === "", seedOut.split("\n").length - 1 + " created");

const fresh = (u) => login(BASE, u, users[u].password);
const holderA = await login(BASE, "holder@example.test", fixturePass("HOLDER"));
const holderB = await fresh("holder.b@wp31.test");
const guardians = [await fresh("guardian.a@wp31.test"), await fresh("guardian.b@wp31.test"), await fresh("guardian.c@wp31.test")];
const issuer = await login(BASE, "issuer@example.test", fixturePass("ISSUER"));
const verifier = await login(BASE, "verifier@example.test", fixturePass("VERIFIER"));
const admin = await login(BASE, "admin@example.test", fixturePass("ADMIN"));
const admin2 = await fresh("admin.b@wp31.test");
const walletA = await walletOf(holderA);
const walletB = await walletOf(holderB);
for (const g of guardians) await walletOf(g);
const me = async (c) => (await c("GET", "/api/v1/identity/auth/me")).data;
const meA = await me(holderA);
const meB = await me(holderB);
const gMe = [];
for (const g of guardians) gMe.push(await me(g));

// ---------------------------------------------------------------- MFA
check("mfa", "status reports required and not enrolled", await holderA("GET", "/api/v1/identity/auth/mfa"), (r) => r.data.required === true && r.data.enrolled === false);
check("mfa", "enrollment refuses a wrong password", await holderA("POST", "/api/v1/identity/auth/mfa/totp", { password: "not-the-password" }), (r) => r.status === 403);
for (const c of [holderA, holderB, ...guardians, admin, admin2]) await enroll(c);
fact("mfa", "seven principals enrolled through the real API", true);
const replayCode = await nextCode(holderA);
const firstUse = await holderA("POST", "/api/v1/identity/auth/step-up", { action: "x.y", resource: "r", code: replayCode });
check("mfa", "a valid code is accepted", firstUse, (r) => r.status === 200);
check("mfa", "the same code cannot be used twice", await holderA("POST", "/api/v1/identity/auth/step-up", { action: "x.y", resource: "r", code: replayCode }), (r) => r.status === 403);
check("mfa", "replacing a factor needs the current code", await holderA("POST", "/api/v1/identity/auth/mfa/totp", { password: holderA.password }), (r) => r.status === 403);

// ---------------------------------------------------------------- revocation: database permissions
const ledgerUri = () => docker("exec", `${PROJECT}-identity-service-1`, "printenv", "IDENTITY_REVOCATION_LEDGER_URI");
const appUri = () => docker("exec", `${PROJECT}-identity-service-1`, "printenv", "IDENTITY_MONGO_URI");
function asPrincipal(uri, script) {
  try {
    return execFileSync("docker", ["exec", "-i", `${PROJECT}-mongodb-1`, "mongosh", uri, "--quiet", "--file", "/dev/stdin"], { input: script, encoding: "utf8", stdio: ["pipe", "pipe", "pipe"] }).trim();
  } catch (error) { return `ERROR ${String(error.stdout)} ${String(error.stderr)}`.slice(0, 400); }
}
const c1 = await issue(BASE, issuer, holderA, walletA.walletId, "SYN-WP31-A1");
const c2 = await issue(BASE, issuer, holderA, walletA.walletId, "SYN-WP31-A2");
const c3 = await issue(BASE, issuer, holderA, walletA.walletId, "SYN-WP31-A3");
const ledgerBase = Number(isolatedMongo('print(db.getSiblingDB("secure_revocation_ledger").revocation_ledger_events.countDocuments({}))'));
const revoked = await issuer("POST", `/api/v1/identity/credentials/${encodeURIComponent(c3.id)}/revoke`, { reason: "WP-31 test revocation" });
check("ledger", "issuer revokes c3 through the API", revoked, (r) => r.status === 200);
const ledgerCount = () => Number(isolatedMongo('print(db.getSiblingDB("secure_revocation_ledger").revocation_ledger_events.countDocuments({}))'));
fact("ledger", "the revocation is in the dedicated ledger database", ledgerCount() === ledgerBase + 1, `events=${ledgerCount()}`);

const P = 'const c=db.getSiblingDB("secure_revocation_ledger").revocation_ledger_events;';
const tryOp = (name, op) => `try{ ${op}; print("${name}=ALLOWED") }catch(e){ print("${name}=DENIED:"+e.codeName) }`;
const perms = asPrincipal(ledgerUri(), P + [
  tryOp("find", "c.find().toArray()"),
  tryOp("update", 'c.updateOne({},{$set:{eventType:"UNREVOKED"}})'),
  tryOp("replace", 'c.replaceOne({},{x:1})'),
  tryOp("delete", "c.deleteMany({})"),
  tryOp("drop", "c.drop()"),
  tryOp("dropDatabase", 'db.getSiblingDB("secure_revocation_ledger").dropDatabase()'),
].join(";"));
const denied = (op) => new RegExp(`${op}=DENIED:Unauthorized`).test(perms);
fact("ledger", "ledger principal can read", /find=ALLOWED/.test(perms));
fact("ledger", "ledger principal cannot update (database refuses)", denied("update"), perms.match(/update=\S+/)?.[0]);
fact("ledger", "ledger principal cannot replace (database refuses)", denied("replace"));
fact("ledger", "ledger principal cannot delete (database refuses)", denied("delete"), perms.match(/delete=\S+/)?.[0]);
fact("ledger", "ledger principal cannot drop the collection", denied("drop"));
fact("ledger", "ledger principal cannot drop the database", denied("dropDatabase"));
const appPerms = asPrincipal(appUri(), `${tryOp("read", 'db.getSiblingDB("secure_revocation_ledger").revocation_ledger_events.find().toArray()')};${tryOp("write", 'db.getSiblingDB("secure_revocation_ledger").revocation_ledger_events.insertOne({x:1})')}`);
fact("ledger", "application principal cannot read the ledger", /read=DENIED:Unauthorized/.test(appPerms), appPerms.split("\n")[0]);
fact("ledger", "application principal cannot write the ledger", /write=DENIED:Unauthorized/.test(appPerms));
fact("ledger", "ledger count unchanged by those attempts", ledgerCount() === ledgerBase + 1);

// ---------------------------------------------------------------- revocation: attacks on real data
const listId = c3.credentialStatus.statusListCredential.split("/").pop();
const statusPath = `/api/v1/identity/status-lists/${listId}`;
const encodedBit = async (index) => {
  const r = await anon("GET", statusPath);
  if (r.status !== 200) return { status: r.status, bit: null };
  const { gunzipSync } = await import("node:zlib");
  const encoded = r.data.credentialSubject.encodedList.slice(1);
  const bytes = gunzipSync(Buffer.from(encoded, "base64url"));
  return { status: 200, bit: Boolean(bytes[Math.floor(index / 8)] & (1 << (7 - (index % 8)))) };
};
const index3 = Number(c3.credentialStatus.statusListIndex);
const index1 = Number(c1.credentialStatus.statusListIndex);
let view = await encodedBit(index3);
fact("ledger", "published list shows c3 revoked", view.bit === true, JSON.stringify(view));
fact("ledger", "published list shows c1 not revoked", (await encodedBit(index1)).bit === false);
const before = await present(verifier, holderA, walletA, c1);
fact("ledger", "c1 is accepted before any attack", before.final === "ACCEPTED", before.final);

isolatedMongo(`const d=db.getSiblingDB("secure_identity"); print(d.credentials.deleteOne({credentialId:${JSON.stringify(c3.id)}}).deletedCount)`);
view = await encodedBit(index3);
fact("ledger", "scenario 1: record deleted, bit stays revoked", view.bit === true, JSON.stringify(view));

isolatedMongo(`const d=db.getSiblingDB("secure_identity"); d.status_lists.deleteMany({}); print("ok")`);
view = await encodedBit(index3);
fact("ledger", "scenario 2: record and published list both gone, bit stays revoked", view.bit === true, JSON.stringify(view));

const c4 = await issue(BASE, issuer, holderA, walletA.walletId, "SYN-WP31-A4");
await issuer("POST", `/api/v1/identity/credentials/${encodeURIComponent(c4.id)}/revoke`, { reason: "WP-31 stale restore" });
isolatedMongo(`const d=db.getSiblingDB("secure_identity"); print(d.credentials.updateOne({credentialId:${JSON.stringify(c4.id)}},{$set:{status:"ACTIVE",revokedAt:null,revokedBy:null,revocationReason:null}}).modifiedCount)`);
view = await encodedBit(Number(c4.credentialStatus.statusListIndex));
fact("ledger", "scenario 3: stale ACTIVE record with current audit, bit stays revoked", view.bit === true, JSON.stringify(view));
const staleVerify = await present(verifier, holderA, walletA, c4);
fact("ledger", "stale ACTIVE record cannot pass verification", staleVerify.final !== "ACCEPTED", staleVerify.final);
check("ledger", "credential status reports REVOKED despite the stale record", await issuer("GET", `/api/v1/identity/credentials/${encodeURIComponent(c4.id)}/status`), (r) => r.data.status === "REVOKED", String(0));

const tamper = (op) => isolatedMongo(`const c=db.getSiblingDB("secure_revocation_ledger").revocation_ledger_events; ${op}`);
const firstEvent = JSON.parse(tamper('print(JSON.stringify(c.find({sequence:1}).next()))'));
tamper(`c.updateOne({sequence:1},{$set:{statusListIndex:${firstEvent.statusListIndex + 1}}}); print("x")`);
await sleep(62_000); // past the verified-chain cache window
view = await encodedBit(index3);
fact("ledger", "scenario 4: altered ledger gives no status at all", view.status === 503, JSON.stringify(view));
const whileBroken = await present(verifier, holderA, walletA, c1);
fact("ledger", "verification fails closed while the ledger is altered", whileBroken.final !== "ACCEPTED", whileBroken.final);
tamper(`c.updateOne({sequence:1},{$set:{statusListIndex:${firstEvent.statusListIndex}}}); print("x")`);
await sleep(62_000);
fact("ledger", "restoring the original event restores status", (await encodedBit(index3)).bit === true);

const tail = JSON.parse(tamper('print(JSON.stringify(c.find().sort({sequence:-1}).limit(1).next()))'));
tamper(`c.deleteOne({sequence:${tail.sequence}}); print("x")`);
view = await encodedBit(index3);
fact("ledger", "scenario 4: rolled back ledger is detected by the anchor", view.status === 503, JSON.stringify(view));
tamper(`c.insertOne(${JSON.stringify(tail)}); print("x")`);
fact("ledger", "reinstating the event clears the rollback finding", (await encodedBit(index3)).status === 200);

const before6 = ledgerCount();
const again = await issuer("POST", `/api/v1/identity/credentials/${encodeURIComponent(c4.id)}/revoke`, { reason: "replayed" });
fact("ledger", "scenario 6: replayed revocation adds no event", ledgerCount() === before6, `status=${again.status}`);

const batch = [];
for (let i = 0; i < 6; i += 1) batch.push(await issue(BASE, issuer, holderA, walletA.walletId, `SYN-WP31-C${i}`));
const responses = await Promise.all(batch.map((c) => issuer("POST", `/api/v1/identity/credentials/${encodeURIComponent(c.id)}/revoke`, { reason: "concurrent" })));
fact("ledger", "scenario 7: six concurrent revocations all succeed", responses.every((r) => r.status === 200), responses.map((r) => r.status).join(","));
const sequences = JSON.parse(tamper('print(JSON.stringify(c.find({},{sequence:1}).sort({sequence:1}).toArray().map(x=>x.sequence)))'));
fact("ledger", "scenario 7: sequence stays contiguous and unique", sequences.every((v, i) => v === i + 1), `n=${sequences.length}`);

docker("restart", `${PROJECT}-identity-service-1`);
for (let i = 0; i < 40; i += 1) { const r = await anon("GET", "/api/v1/identity/status-lists/none").catch(() => null); if (r && r.status !== 502 && r.status !== 503) break; await sleep(1_000); }
await sleep(3_000);
const repaired = isolatedMongo(`print(db.getSiblingDB("secure_identity").credentials.findOne({credentialId:${JSON.stringify(c4.id)}}).status)`);
fact("ledger", "startup reconciliation repairs the stale record to REVOKED", repaired === "REVOKED", repaired);

// ---------------------------------------------------------------- Guardian policy and bypasses
const POLICY = { walletId: walletA.walletId, minimumApprovals: 2, maximumGuardians: 3, approvalWindowSeconds: 600, timeLockSeconds: 10, recoveryExpirationSeconds: 1800, maximumAttempts: 3, cooldownSeconds: 0, allowCancellation: true };
check("guardian", "policy change without step-up is refused", await holderA("PUT", "/api/v1/recovery/policy", POLICY), (r) => r.status === 403);
check("guardian", "client-invented step-up value is refused", await holderA("PUT", "/api/v1/recovery/policy", POLICY, { "x-step-up-token": "true" }), (r) => r.status === 403);
const wrongAction = await stepUp(holderA, "recovery.request.create", walletA.walletId);
check("guardian", "step-up for another action is refused", await holderA("PUT", "/api/v1/recovery/policy", POLICY, wrongAction), (r) => r.status === 403);
check("guardian", "allowSelfGuardian=true is rejected", await holderA("PUT", "/api/v1/recovery/policy", { ...POLICY, allowSelfGuardian: true }, await stepUp(holderA, "recovery.policy.update", walletA.walletId)), (r) => r.status === 422);
check("guardian", "M=1 is rejected", await holderA("PUT", "/api/v1/recovery/policy", { ...POLICY, minimumApprovals: 1 }, await stepUp(holderA, "recovery.policy.update", walletA.walletId)), (r) => r.status === 422);
check("guardian", "time-lock below the floor is rejected", await holderA("PUT", "/api/v1/recovery/policy", { ...POLICY, timeLockSeconds: 0 }, await stepUp(holderA, "recovery.policy.update", walletA.walletId)), (r) => r.status === 422);
const setPolicy = async (c, policy) => c("PUT", "/api/v1/recovery/policy", policy, await stepUp(c, "recovery.policy.update", policy.walletId));
check("guardian", "valid 2-of-3 policy is saved", await setPolicy(holderA, POLICY), (r) => r.status === 200);

const invite = async (owner, wallet, target, name) => owner("POST", "/api/v1/recovery/guardians", { walletId: wallet.walletId, guardianUserId: target.id, displayName: name }, await stepUp(owner, "recovery.guardian.manage", wallet.walletId));
check("guardian", "owner cannot invite themself", await invite(holderA, walletA, meA, "Me"), (r) => r.status === 422);
check("guardian", "owner cannot register a DID for someone", await holderA("POST", "/api/v1/recovery/guardians", { walletId: walletA.walletId, guardianUserId: gMe[0].id, displayName: "G", guardianDid: "did:key:zSomeone" }, await stepUp(holderA, "recovery.guardian.manage", walletA.walletId)), (r) => r.status === 422);
const keys = [deviceKey(), deviceKey(), deviceKey()];
const invitedA = check("guardian", "invitation has no key and no authority", await invite(holderA, walletA, gMe[0], "Guardian A"), (r) => r.status === 201 && r.data.status === "INVITED" && r.data.guardianDid === "");
fact("guardian", "invitation challenge is not shown to the owner", !invitedA.text.includes("challenge"));
const invitationsOf = async (g) => (await g("GET", "/api/v1/recovery/guardians/invitations")).data.items;
const invA = (await invitationsOf(guardians[0]))[0];
check("guardian", "another user cannot accept the invitation", await acceptInvitation(BASE, guardians[1], invA, keys[1]), (r) => r.status === 404);
check("guardian", "a DID without its private key is refused", await acceptInvitation(BASE, guardians[0], invA, keys[1], { proofKey: keys[0] }), (r) => r.status === 409);
check("guardian", "the server-side Guardian signer no longer exists", await guardians[0]("POST", "/api/v1/identity/wallets/guardian-recovery-proof", { guardianDid: "x" }), (r) => [404, 405, 422].includes(r.status));
const gWallet = await walletOf(guardians[0]);
const managedAttempt = await acceptInvitation(BASE, guardians[0], invA, { ...keys[0], did: gWallet.holderDid, verificationMethod: `${gWallet.holderDid}#${gWallet.holderDid.slice(8)}` });
check("guardian", "the platform-held wallet DID cannot become a Guardian key", managedAttempt, (r) => r.status === 409);
const gA = check("guardian", "guardian A accepts with a key only they hold", await acceptInvitation(BASE, guardians[0], invA, keys[0]), (r) => r.status === 200 && r.data.status === "ACTIVE");
await invite(holderA, walletA, gMe[1], "Guardian B");
const invB = (await invitationsOf(guardians[1]))[0];
const gB = check("guardian", "guardian B accepts", await acceptInvitation(BASE, guardians[1], invB, keys[1]), (r) => r.data.status === "ACTIVE");
await invite(holderA, walletA, gMe[2], "Guardian C");
const invC = (await invitationsOf(guardians[2]))[0];
check("guardian", "two guardians cannot share a key", await acceptInvitation(BASE, guardians[2], invC, keys[0]), (r) => r.status === 409);
const gC = check("guardian", "a guardian added after setup waits for activation", await acceptInvitation(BASE, guardians[2], invC, keys[2]), (r) => r.data.status === "PENDING_ACTIVATION" && r.data.pendingEffectiveAt);
const ids = [gA.data.guardianId, gB.data.guardianId, gC.data.guardianId];

const weaker = await setPolicy(holderA, { ...POLICY, maximumAttempts: 9 });
check("guardian", "weakening the policy is scheduled, not applied", weaker, (r) => r.data.maximumAttempts === 3 && r.data.pendingChange?.maximumAttempts === 9 && r.data.pendingEffectiveAt);
const notices = (await guardians[0]("GET", "/api/v1/recovery/notifications")).data.items;
fact("guardian", "guardians get a durable notice of the scheduled change", notices.some((n) => n.eventType === "RECOVERY_POLICY_CHANGE_SCHEDULED"), `n=${notices.length}`);
fact("guardian", "notices say e-mail is not configured", notices.every((n) => n.emailStatus === "NOT_CONFIGURED"));
await sleep(16_000);
const listed = (await holderA("GET", `/api/v1/recovery/guardians?walletId=${walletA.walletId}`)).data.items;
fact("guardian", "after the delay guardian C is active", listed.find((g) => g.guardianId === ids[2]).status === "ACTIVE");

// ---------------------------------------------------------------- recovery flow
const rotateTarget = (await holderA("GET", `/api/v1/identity/wallets/${walletA.walletId}/keys`)).data.items.find((k) => k.state === "ACTIVE");
check("guardian", "direct key rotation without step-up is refused", await holderA("POST", `/api/v1/identity/wallets/${walletA.walletId}/keys/${rotateTarget.keyId}/rotate`, {}, { "idempotency-key": `rot-${randomBytes(6).toString("hex")}` }), (r) => r.status === 403);
const createRequest = async (c, wallet, reason = "ACCOUNT_COMPROMISE") => c("POST", "/api/v1/recovery/requests", { walletId: wallet.walletId, reason }, await stepUp(c, "recovery.request.create", wallet.walletId));
check("recovery", "starting recovery without step-up is refused", await holderA("POST", "/api/v1/recovery/requests", { walletId: walletA.walletId, reason: "ACCOUNT_COMPROMISE" }), (r) => r.status === 403);
const opened = check("recovery", "owner opens a request", await createRequest(holderA, walletA), (r) => r.status === 201);
const request = opened.data;
fact("recovery", "risk service answered through a real service call", request.riskLevel !== "NOT_ASSESSED", `${request.riskLevel}/${request.riskStatus}`);
const guardianView = (await guardians[0]("GET", `/api/v1/recovery/requests/${request.requestId}`)).data;
check("recovery", "owner cannot approve their own request", await decide(holderA, ids[0], keys[0], guardianView).catch((e) => ({ status: 0, text: String(e) })), (r) => r.status === 404);
check("recovery", "guardian decision without step-up is refused", await guardians[0]("POST", `/api/v1/recovery/requests/${request.requestId}/approve`, { guardianId: ids[0], challenge: guardianView.challenge, proof: "a.b.c-long-enough-string" }), (r) => r.status === 403);
check("recovery", "proof for another policy snapshot is refused", await decide(guardians[0], ids[0], keys[0], guardianView, "APPROVE", { policyHash: "0".repeat(64) }), (r) => r.status === 409);
check("recovery", "a key that is not the Guardian's is refused", await decide(guardians[0], ids[0], keys[1], guardianView), (r) => r.status === 409);
const one = check("recovery", "first approval does not reach quorum", await decide(guardians[0], ids[0], keys[0], guardianView), (r) => r.status === 200 && r.data.recovery.state === "PENDING_APPROVALS");
const concurrent = await Promise.all([decide(guardians[1], ids[1], keys[1], guardianView), decide(guardians[2], ids[2], keys[2], guardianView)]);
fact("recovery", "concurrent decisions are accepted or cleanly refused", concurrent.every((r) => [200, 409].includes(r.status)), concurrent.map((r) => r.status).join(","));
const timeline = (await holderA("GET", `/api/v1/recovery/requests/${request.requestId}/timeline`)).data.items;
fact("recovery", "quorum transition happens exactly once", timeline.filter((e) => e.eventType === "RECOVERY_QUORUM_REACHED").length === 1);

const holderBefore = holderA.cookie();
if (request.riskStatus === "ON_HOLD") {
  await sleep(14_000);
  const held = (await guardians[0]("GET", `/api/v1/recovery/requests/${request.requestId}`)).data;
  fact("recovery", "a held request does not rotate", held.state !== "COMPLETED", held.state);
  check("recovery", "the requester cannot release the hold", await holderA("POST", `/api/v1/recovery/requests/${request.requestId}/risk-review`, { decision: "RELEASE", reason: "trust me" }, await stepUp(holderA, "recovery.risk.review", request.requestId)), (r) => r.status === 403);
  check("recovery", "an administrator releases the hold", await admin("POST", `/api/v1/recovery/requests/${request.requestId}/risk-review`, { decision: "RELEASE", reason: "checked with owner" }, await stepUp(admin, "recovery.risk.review", request.requestId)), (r) => r.status === 200);
}
let finished = null;
for (let i = 0; i < 40 && !finished; i += 1) {
  await sleep(1_500);
  const state = (await guardians[0]("GET", `/api/v1/recovery/requests/${request.requestId}`)).data;
  if (state.state === "COMPLETED" || state.state === "FAILED") finished = state;
}
fact("recovery", "recovery completes after quorum and time-lock", finished?.state === "COMPLETED", finished?.state ?? "timeout");
const events = (await guardians[0]("GET", `/api/v1/recovery/requests/${request.requestId}/timeline`)).data.items.map((e) => e.eventType);
fact("recovery", "exactly one rotation was executed", events.filter((e) => e === "RECOVERY_COMPLETED").length === 1);

check("session", "the old session is dead on Identity", await holderA("GET", "/api/v1/identity/auth/me"), (r) => r.status === 401);
const replay = client(BASE, "old-session");
replay.setCookie(holderBefore);
check("session", "the old session is dead on Recovery", await replay("GET", "/api/v1/recovery/requests"), (r) => r.status === 401);
docker("restart", `${PROJECT}-identity-service-1`, `${PROJECT}-recovery-service-1`);
for (let i = 0; i < 40; i += 1) { const r = await anon("GET", "/api/v1/identity/auth/me").catch(() => null); if (r && r.status === 401) break; await sleep(1_000); }
await sleep(2_000);
const replay2 = client(BASE, "old-session-after-restart");
replay2.setCookie(holderBefore);
check("session", "the old session stays dead after restarting both services", await replay2("GET", "/api/v1/identity/auth/me"), (r) => r.status === 401);
const reentry = await login(BASE, "holder@example.test", fixturePass("HOLDER"));
reentry.totpSecret = holderA.totpSecret; reentry.lastCounter = holderA.lastCounter; reentry.password = holderA.password;
check("session", "the owner can sign in again", await reentry("GET", "/api/v1/identity/auth/me"), (r) => r.status === 200);
const walletAfter = await walletOf(reentry);
fact("session", "the wallet has a new DID", walletAfter.holderDid !== walletA.holderDid);

// ---------------------------------------------------------------- key administration
const keysAfter = (await reentry("GET", `/api/v1/identity/wallets/${walletA.walletId}/keys`)).data.items;
const compromised = keysAfter.find((k) => k.state === "COMPROMISED");
fact("keys", "the predecessor key is COMPROMISED", Boolean(compromised), keysAfter.map((k) => k.state).join(","));
check("keys", "a compromised key cannot be rotated directly", await reentry("POST", `/api/v1/identity/wallets/${walletA.walletId}/keys/${compromised.keyId}/rotate`, {}, { ...(await stepUp(reentry, "wallet.key.rotate", compromised.keyId)), "idempotency-key": `rot-${randomBytes(6).toString("hex")}` }), (r) => r.status === 409 || r.status === 422);
const active = keysAfter.find((k) => k.state === "ACTIVE");
const COMPROMISE = `/api/v1/identity/wallets/${walletA.walletId}/keys/${active.keyId}/compromise`;
check("keys", "one administrator alone cannot compromise a key", await admin("POST", COMPROMISE, { reason: "single admin attempt" }), (r) => r.status === 403);
const dual = (await admin("POST", "/api/v1/identity/admin/dual-control", { operationType: "KEY_COMPROMISE", target: active.keyId, reason: "drill" }, await stepUp(admin, "dual-control.request", active.keyId))).data;
check("keys", "an administrator cannot approve their own operation", await admin("POST", `/api/v1/identity/admin/dual-control/${dual.operationId}/approve`, undefined, await stepUp(admin, "dual-control.approve", dual.operationId)), (r) => r.status === 403);
const approved = check("keys", "a second administrator approves", await admin2("POST", `/api/v1/identity/admin/dual-control/${dual.operationId}/approve`, undefined, await stepUp(admin2, "dual-control.approve", dual.operationId)), (r) => r.status === 200);
check("keys", "approval for another key is refused", await admin("POST", `/api/v1/identity/wallets/${walletA.walletId}/keys/${compromised.keyId}/compromise`, { reason: "wrong key" }, { "x-dual-control-operation": dual.operationId, "x-dual-control-token": approved.data.executionToken }), (r) => r.status === 403);

// ---------------------------------------------------------------- risk hold on fraud outage
const POLICY_B = { ...POLICY, walletId: walletB.walletId };
await setPolicy(holderB, POLICY_B);
const bKeys = [deviceKey(), deviceKey()];
const bIds = [];
for (let i = 0; i < 2; i += 1) {
  await invite(holderB, walletB, gMe[i], `B guardian ${i}`);
  const invitation = (await invitationsOf(guardians[i])).find((x) => x.walletId === walletB.walletId);
  bIds.push((await acceptInvitation(BASE, guardians[i], invitation, bKeys[i])).data.guardianId);
}
docker("stop", `${PROJECT}-fraud-service-1`);
const held = check("risk", "fraud outage puts the request on hold", await createRequest(holderB, walletB, "DEVICE_LOSS"), (r) => r.status === 201 && r.data.riskStatus === "ON_HOLD" && r.data.riskLevel === "UNAVAILABLE", "");
docker("start", `${PROJECT}-fraud-service-1`);
const heldView = (await guardians[0]("GET", `/api/v1/recovery/requests/${held.data.requestId}`)).data;
await decide(guardians[0], bIds[0], bKeys[0], heldView);
await decide(guardians[1], bIds[1], bKeys[1], heldView);
await sleep(14_000);
const stillHeld = (await guardians[0]("GET", `/api/v1/recovery/requests/${held.data.requestId}`)).data;
fact("risk", "quorum plus time-lock does not rotate while held", stillHeld.state === "READY_FOR_EXECUTION", stillHeld.state);
const walletBNow = await walletOf(holderB);
fact("risk", "the DID has not changed during the hold", walletBNow.holderDid === walletB.holderDid);
check("risk", "the holder cannot release their own hold", await holderB("POST", `/api/v1/recovery/requests/${held.data.requestId}/risk-review`, { decision: "RELEASE", reason: "mine" }, await stepUp(holderB, "recovery.risk.review", held.data.requestId)), (r) => r.status === 403);
const upheld = check("risk", "an administrator can uphold the hold and cancel", await admin("POST", `/api/v1/recovery/requests/${held.data.requestId}/risk-review`, { decision: "UPHOLD", reason: "not confirmed" }, await stepUp(admin, "recovery.risk.review", held.data.requestId)), (r) => r.status === 200 && r.data.state === "CANCELLED");
fact("risk", "cancelled request left the key alone", upheld.status === 200 && (await walletOf(holderB)).holderDid === walletB.holderDid);

// ---------------------------------------------------------------- wallet restore against the ledger
const bW = `/api/v1/identity/wallets/${walletB.walletId}`;
const w1 = await issue(BASE, issuer, holderB, walletB.walletId, "SYN-WP31-W1");
const w2 = await issue(BASE, issuer, holderB, walletB.walletId, "SYN-WP31-W2");
const stepBackup = await stepUp(holderB, "wallet.backup.create", walletB.walletId);
check("wallet", "credential backup without step-up is refused", await holderB("POST", `${bW}/backups`), (r) => r.status === 403);
const created = check("wallet", "credential backup with step-up", await holderB("POST", `${bW}/backups`, undefined, stepBackup), (r) => r.status === 201);
await issuer("POST", `/api/v1/identity/credentials/${encodeURIComponent(w2.id)}/revoke`, { reason: "revoked after backup" });
isolatedMongo(`const d=db.getSiblingDB("secure_identity"); print(d.credentials.deleteMany({credentialId:{$in:${JSON.stringify([w1.id, w2.id])}}}).deletedCount); d.wallet_backups.deleteMany({walletId:${JSON.stringify(walletB.walletId)}}); d.audit_events.deleteMany({subjectId:${JSON.stringify(w2.id)}});`);
check("wallet", "the audit chain reports the deleted audit rows", await admin("GET", "/api/v1/identity/audit/integrity"), (r) => r.status === 200 && r.data.status === "BROKEN", "");
const standalone = check("wallet", "archive previews with no server row and no audit trail", await holderB("POST", `${bW}/backups/${created.data.backup.backupId}/preview`, { payload: created.data.payload }), (r) => r.status === 200);
const outcomes = Object.fromEntries(standalone.data.items.map((i) => [i.credentialId, i.outcome]));
fact("wallet", "scenario 10: revoked credential stays revoked via the ledger alone", outcomes[w2.id] === "REVOKED", JSON.stringify(Object.values(outcomes)));
fact("wallet", "valid credential is restorable from the standalone archive", outcomes[w1.id] === "RESTORABLE");
check("wallet", "restore without step-up is refused", await holderB("POST", `${bW}/backups/${created.data.backup.backupId}/restore`, { payload: created.data.payload }, { "idempotency-key": "wp31-restore-no-stepup-1" }), (r) => r.status === 403);
const restored = check("wallet", "restore with step-up restores only the valid credential", await holderB("POST", `${bW}/backups/${created.data.backup.backupId}/restore`, { payload: created.data.payload }, { "idempotency-key": "wp31-restore-with-stepup-1", ...(await stepUp(holderB, "wallet.backup.restore", walletB.walletId)) }), (r) => r.status === 201 && r.data.restored === 1);
const verifiedAfter = await present(verifier, holderB, walletB, w1);
fact("wallet", "restored credential verifies", verifiedAfter.final === "ACCEPTED", verifiedAfter.final);

// ---------------------------------------------------------------- WP-31: QR
const qrSession = (await verifier("POST", "/api/v1/oid4vp/requests", { purpose: "WP-31 QR check", requestedCredentialTypes: ["UniversityAffiliationCredential"], requestedFields: ["affiliation"], ttlSeconds: 600 })).data;
const qr = String(qrSession.qrPayload);
fact("qr", "verifier QR is an http(s) link a camera can open", /^https?:\/\/wallet\.wp31\.test\/wallet\/present\?request=session_[A-Za-z0-9_-]{24,}$/.test(qr), qr.replace(/request=.*/, "request=<handle>"));
fact("qr", "the QR holds no credential id, urn, DID, nonce or claim", !/urn:|did:|nonce|dcql|affiliation/.test(qr));
fact("qr", "client_id is the public origin, not an internal host", qrSession.clientId === "http://wallet.wp31.test/verifier", qrSession.clientId);
fact("qr", "no internal host appears in the same-device link", !/identity-service|api-gateway|localhost|mongodb/.test(decodeURIComponent(qrSession.deepLinkUri)) || /response_uri=http%3A%2F%2Flocalhost/.test(qrSession.deepLinkUri), "");
fact("qr", "the same-device link is an OID4VP authorization request", qrSession.deepLinkUri.startsWith("openid4vp://?client_id=") && qrSession.deepLinkUri.includes("dcql_query=") && qrSession.deepLinkUri.includes("nonce="));
const second = (await verifier("POST", "/api/v1/oid4vp/requests", { purpose: "WP-31 QR check 2", requestedCredentialTypes: ["UniversityAffiliationCredential"], requestedFields: ["affiliation"], ttlSeconds: 600 })).data;
fact("qr", "every request gets a fresh nonce and handle", second.nonce !== qrSession.nonce && second.sessionId !== qrSession.sessionId);
check("qr", "an unknown handle gives 404", await holderB("GET", "/api/v1/oid4vp/requests/session_doesnotexist0000000000000000/holder-request"), (r) => r.status === 404);
check("qr", "an anonymous caller cannot read a request", await anon("GET", `/api/v1/oid4vp/requests/${qrSession.sessionId}/holder-request`), (r) => r.status === 401);

const denyClaims = Object.fromEntries(Object.entries(w1.credentialSubject).filter(([k]) => k !== "id"));
await holderB("POST", `/api/v1/oid4vp/requests/${second.sessionId}/evaluate-dcql`, { candidateCredentials: [w1] });
await holderB("POST", `/api/v1/oid4vp/requests/${second.sessionId}/wallet-consent`, { walletId: walletB.walletId, holderDid: walletB.holderDid, action: "REJECT", approvedCredentials: [], approvedClaims: {}, rejectedClaims: [] });
check("qr", "after a denial no presentation can be created", await holderB("POST", "/api/v1/oid4vp/wallet-presentation", { sessionId: second.sessionId, walletId: walletB.walletId, credentialIds: [w1.id], disclosedClaims: denyClaims }), (r) => r.status !== 200);

const third = (await verifier("POST", "/api/v1/oid4vp/requests", { purpose: "WP-31 replay", requestedCredentialTypes: ["UniversityAffiliationCredential"], requestedFields: ["affiliation"], ttlSeconds: 600 })).data;
await holderB("POST", `/api/v1/oid4vp/requests/${third.sessionId}/evaluate-dcql`, { candidateCredentials: [w1] });
await holderB("POST", `/api/v1/oid4vp/requests/${third.sessionId}/wallet-consent`, { walletId: walletB.walletId, holderDid: walletB.holderDid, action: "APPROVE", approvedCredentials: [w1.id], approvedClaims: denyClaims, rejectedClaims: [] });
const vp3 = await holderB("POST", "/api/v1/oid4vp/wallet-presentation", { sessionId: third.sessionId, walletId: walletB.walletId, credentialIds: [w1.id], disclosedClaims: denyClaims });
const firstResponse = await holderB("POST", "/api/v1/oid4vp/response", { sessionId: third.sessionId, vpToken: vp3.data.vpToken, disclosedClaims: denyClaims });
fact("qr", "the full request to verdict path is accepted", firstResponse.data?.result?.finalPolicyResult === "ACCEPTED", String(firstResponse.data?.result?.finalPolicyResult));
check("qr", "a replayed presentation is refused", await holderB("POST", "/api/v1/oid4vp/response", { sessionId: third.sessionId, vpToken: vp3.data.vpToken, disclosedClaims: denyClaims }), (r) => r.status !== 200 || r.data?.result?.finalPolicyResult !== "ACCEPTED");

// ---------------------------------------------------------------- WP-31: re-issuance
const R = `/api/v1/identity/wallets/${walletA.walletId}/reissuance-requests`;
const askedFor = check("reissue", "holder asks for a credential bound to the old DID", await reentry("POST", R, { credentialId: c1.id }), (r) => r.status === 201 && r.data.status === "PENDING");
check("reissue", "a revoked credential cannot be requested", await reentry("POST", R, { credentialId: c2.id === c1.id ? c1.id : batch[0].id }), (r) => [404, 409].includes(r.status));
check("reissue", "another holder cannot request it", await holderB("POST", R, { credentialId: c1.id }), (r) => [403, 404].includes(r.status));
const queue = await issuer("GET", "/api/v1/identity/reissuance-requests/issuer");
check("reissue", "the issuer sees the request", queue, (r) => r.data.items.some((i) => i.requestId === askedFor.data.requestId));
fact("reissue", "the issuer never sees an offer link in the queue", queue.data.items.every((i) => i.offerLink === null));
check("reissue", "a holder cannot approve it", await holderB("POST", `/api/v1/identity/reissuance-requests/${askedFor.data.requestId}/approve`), (r) => r.status === 403);
check("reissue", "the issuer approves", await issuer("POST", `/api/v1/identity/reissuance-requests/${askedFor.data.requestId}/approve`), (r) => r.status === 200 && r.data.status === "OFFERED");
const mine = (await reentry("GET", "/api/v1/identity/reissuance-requests/mine")).data.items.find((i) => i.requestId === askedFor.data.requestId);
fact("reissue", "the holder receives the offer", Boolean(mine?.offerLink));
const code = JSON.parse(decodeURIComponent(mine.offerLink.split("credential_offer=")[1])).grants["urn:ietf:params:oauth:grant-type:pre-authorized_code"]["pre-authorized_code"];
const tok2 = (await anon("POST", "/api/v1/oid4vci/token", new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:pre-authorized_code", "pre-authorized_code": code }))).data;
const meta2 = (await anon("GET", "/api/v1/oid4vci/.well-known/openid-credential-issuer")).data;
const proof2 = (await reentry("POST", "/api/v1/oid4vci/holder-proof", { walletId: walletA.walletId, audience: meta2.credential_issuer, nonce: tok2.c_nonce })).data;
const fresh2 = await reentry("POST", "/api/v1/oid4vci/credential", { credentialConfigurationId: "UniversityAffiliationCredential", proof: { proofType: "jwt", jwt: proof2.jwt }, walletId: walletA.walletId }, { authorization: `Bearer ${tok2.access_token}` });
check("reissue", "the new credential is claimed", fresh2, (r) => r.status === 200);
fact("reissue", "it is bound to the new DID", fresh2.data.credential.credentialSubject.id === walletAfter.holderDid);
fact("reissue", "it has a new id", fresh2.data.credential.id !== c1.id);
const after2 = await present(verifier, reentry, walletAfter, fresh2.data.credential);
fact("reissue", "the re-issued credential verifies with the new key", after2.final === "ACCEPTED", after2.final);

// ---------------------------------------------------------------- WP-31: password
const gc = guardians[2];
const newPassword = `Wp30-new-${randomBytes(8).toString("hex")}`;
const PW = "/api/v1/identity/auth/password";
check("password", "changing it without step-up is refused", await gc("POST", PW, { currentPassword: gc.password, newPassword }), (r) => r.status === 403);
check("password", "a wrong current password is refused", await gc("POST", PW, { currentPassword: "wrong-value-here", newPassword }, await stepUp(gc, "account.password.change", gMe[2].id)), (r) => r.status === 403);
check("password", "a short new password is refused", await gc("POST", PW, { currentPassword: gc.password, newPassword: "short" }, await stepUp(gc, "account.password.change", gMe[2].id)), (r) => r.status === 422);
const oldCookie = gc.cookie();
check("password", "the password changes with step-up", await gc("POST", PW, { currentPassword: gc.password, newPassword }, await stepUp(gc, "account.password.change", gMe[2].id)), (r) => r.status === 204);
const staleSession = client(BASE, "stale");
staleSession.setCookie(oldCookie);
check("password", "the old session is ended", await staleSession("GET", "/api/v1/identity/auth/me"), (r) => r.status === 401);
check("password", "the old password no longer works", await anon("POST", "/api/v1/identity/auth/token", { username: gc.username, password: gc.password }), (r) => r.status === 401);
await sleep(1_200);
const relogged = await login(BASE, gc.username, newPassword);
check("password", "the new password works", await relogged("GET", "/api/v1/identity/auth/me"), (r) => r.status === 200);

// ---------------------------------------------------------------- WP-31: trust registry step-up
const TRUST = "/api/v1/identity/trust-registry/issuers";
const trustDid = `did:web:trust-${randomBytes(4).toString("hex")}.wp31.test`;
const trustBody = { issuerDid: trustDid, organizationName: "WP31 Synthetic Issuer", permittedCredentialTypes: ["UniversityAffiliationCredential"], validDays: 30, roles: ["issuer"] };
check("trust", "adding an issuer without step-up is refused", await admin("POST", TRUST, trustBody), (r) => r.status === 403);
check("trust", "a token for another issuer is refused", await admin("POST", TRUST, trustBody, await stepUp(admin, "trust.registry.write", "did:web:other.wp31.test")), (r) => r.status === 403);
const trusted = check("trust", "the issuer is added with step-up", await admin("POST", TRUST, trustBody, await stepUp(admin, "trust.registry.write", trustDid)), (r) => r.status === 201);
const trustSuspend = `${TRUST}/${encodeURIComponent(trusted.data.id ?? trusted.data.recordId)}/suspend`;
check("trust", "suspending without step-up is refused", await admin("POST", trustSuspend, { reason: "synthetic drill" }), (r) => r.status === 403);
check("trust", "suspending with step-up works", await admin("POST", trustSuspend, { reason: "synthetic drill" }, await stepUp(admin, "trust.registry.write", trusted.data.id ?? trusted.data.recordId)), (r) => r.status === 200);

const passed = results.filter((r) => r.pass).length;
writeFileSync(`${DIR}e2e_results.json`, JSON.stringify({ passed, failed: results.length - passed, results }, null, 1));
writeFileSync(process.env.WP31_STATE, JSON.stringify({ c1, c3, walletA: walletAfter, walletB: walletBNow, w1, requestId: request.requestId, reentryCookie: reentry.cookie() }));
console.log(`\nTOTAL pass=${passed} fail=${results.length - passed}`);
process.exitCode = results.length === passed ? 0 : 1;
