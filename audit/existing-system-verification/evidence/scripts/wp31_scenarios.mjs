// WP-31 SSI detection scenarios. Real API calls on the isolated stack; every event is
// stamped SYNTHETIC_TEST. These prove the plumbing, not real-world detection performance.
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { PROJECT, check, client, docker, enroll, fact, fixturePass, isolatedMongo, issue, login, nextCode, present, results, sleep, stepUp, walletOf } from "./wp31_lib.mjs";

const BASE = "http://localhost:29300";
const DIR = new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const I = "/api/v1/fraud/intel";
const tag = randomBytes(3).toString("hex");
const password = `Wp31-${randomBytes(12).toString("hex")}`;
const names = ["brute", "burst", "holder", "other"].map((n) => `${n}.${tag}@wp31.test`);
const extra = Object.fromEntries(names.map((n) => [n, { name: "Scenario account", role: "holder", password }]));
execFileSync("docker", ["exec", "-i", "-w", "/app", `${PROJECT}-identity-service-1`, "python", "-"], {
  input: readFileSync(`${DIR}seed_users.py`, "utf8").replace("json.load(sys.stdin)", `json.loads(${JSON.stringify(JSON.stringify(extra))})`), encoding: "utf8",
});
const [brute, burst, holderName, otherName] = names;
const anon = client(BASE, "anon");
const admin = await login(BASE, "admin@example.test", fixturePass("ADMIN"));
const issuer = await login(BASE, "issuer@example.test", fixturePass("ISSUER"));
const verifier = await login(BASE, "verifier@example.test", fixturePass("VERIFIER"));
const holder = await login(BASE, holderName, password);
const other = await login(BASE, otherName, password);
const wallet = await walletOf(holder);

const incidents = async () => (await admin("GET", `${I}/incidents?limit=200`)).data.items;
async function waitRule(ruleId, ms = 30_000) {
  const end = Date.now() + ms;
  for (;;) {
    const found = (await incidents()).find((i) => i.rule_id === ruleId);
    if (found || Date.now() > end) return found;
    await sleep(1_500);
  }
}
const counts = async () => Object.fromEntries((await admin("GET", `${I}/metrics?hours=1`)).data.event_counts.map((e) => [e.event_type, e.count]));
const rate = async (name) => (await admin("GET", `${I}/metrics?hours=1`)).data.rates.find((r) => r.name === name);
const badLogin = (u) => anon("POST", "/api/v1/identity/auth/token", { username: u, password: "wrong-password-value" });

// ---- empty-state truth, before scenario traffic builds up
const cold = await admin("GET", `${I}/anomalies`);
check("S14", "cold start reports insufficient baseline for every series", cold, (r) => r.data.series.every((s) => s.state === "INSUFFICIENT_BASELINE"));
const recoveryRate = await rate("Recovery signals");
fact("metrics", "no recovery requests gives N/A, not 0%", recoveryRate.denominator === 0 && recoveryRate.value === null, JSON.stringify(recoveryRate));

// ---- access control on the subsystem itself
check("access", "a holder cannot read metrics", await holder("GET", `${I}/metrics`), (r) => r.status === 403);
check("access", "a verifier cannot read incidents", await verifier("GET", `${I}/incidents`), (r) => r.status === 403);
check("access", "an anonymous caller cannot read health", await anon("GET", `${I}/health`), (r) => r.status === 401);
const forged = { source: "identity-service", environment: "test", events: [] };
check("access", "the gateway does not pass a forged ingest", await anon("POST", `${I}/ingest`, forged, { "x-internal-service-token": "forged-token-of-a-reasonable-length-00" }), (r) => r.status === 401 || r.status === 403);

// ---- S1 repeated failed sign-in
for (let i = 0; i < 6; i += 1) await badLogin(brute);
const s1 = await waitRule("AUTH-01");
fact("S1", "failed sign-ins open a suspicious activity case", s1?.detection_state === "SUSPICIOUS_ACTIVITY" && s1?.status === "NEW", s1?.title);
fact("S1", "the case is not a confirmed incident", s1?.status !== "CONFIRMED");
fact("S1", "several signals share one case", (await incidents()).filter((i) => i.rule_id === "AUTH-01").length === 1);

// ---- S2 burst then success
for (let i = 0; i < 5; i += 1) await badLogin(burst);
await sleep(7_000);
await login(BASE, burst, password);
const s2 = await waitRule("AUTH-03");
fact("S2", "success after a burst is a suspected attack", s2?.detection_state === "SUSPECTED_ATTACK", s2?.rule_id);

// ---- S1b step-up failures
await enroll(holder);
for (let i = 0; i < 3; i += 1) await holder("POST", "/api/v1/identity/auth/step-up", { action: "x.y", resource: "r", code: "000000" });
const mfa = await waitRule("MFA-01");
fact("S1b", "failed step-ups open a case", Boolean(mfa), mfa?.rule_id);

await sleep(62_000); // clears the sign-in rate window for what follows

// ---- S3 revoked session reuse
const victim = await login(BASE, otherName, password);
const stale = victim.cookie();
await victim("POST", "/api/v1/identity/auth/revoke", {});
const replay = client(BASE, "replay");
replay.setCookie(stale);
const before3 = (await counts())["auth.session.rejected"] ?? 0;
check("S3", "a revoked session is refused", await replay("GET", "/api/v1/identity/auth/me"), (r) => r.status === 401);
await sleep(7_000);
fact("S3", "the rejection is recorded as a raw signal", ((await counts())["auth.session.rejected"] ?? 0) > before3);
fact("S3", "one rejection opens no case", !(await incidents()).some((i) => i.rule_id === "SES-01"));

// ---- S4 OID4VCI abuse
for (let i = 0; i < 6; i += 1) await anon("POST", "/api/v1/oid4vci/token", new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:pre-authorized_code", "pre-authorized_code": `invalid-${i}` }));
fact("S4", "bad token calls open a case", Boolean(await waitRule("VCI-01")));

// ---- S5 and S6 OID4VP failures, revoked credential shown again
const cred = await issue(BASE, issuer, holder, wallet.walletId, "SYN-WP31-1");
fact("S6", "a valid presentation is accepted first", (await present(verifier, holder, wallet, cred)).final === "ACCEPTED");
await issuer("POST", `/api/v1/identity/credentials/${encodeURIComponent(cred.id)}/revoke`, { reason: "scenario" });
for (let i = 0; i < 6; i += 1) await present(verifier, holder, wallet, cred);
fact("S5", "repeated refused presentation calls open a case", Boolean(await waitRule("VP-02")));
const presented = await counts();
fact("S6", "the revocation and refusals are visible as events", (presented["credential.revoked"] ?? 0) >= 1 && (presented["oid4vp.request.failure"] ?? 0) >= 5);

// ---- S9 function-level authorization probing
for (let i = 0; i < 11; i += 1) await other("GET", "/api/v1/identity/admin/users");
fact("S9", "repeated refused admin calls open a case", Boolean(await waitRule("API-01")));

await sleep(62_000);

// ---- S10 rate limiting
// Raw requests: the shared test client waits out a 429, which would hide this.
for (let i = 0; i < 55; i += 1) await fetch(`${BASE}/api/v1/oid4vci/token`, { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body: "grant_type=x&pre-authorized_code=x" });
fact("S10", "sustained rate limiting opens a case", Boolean(await waitRule("API-02")));
const limited = await rate("Rate-limited calls");
fact("S10", "the rate has a real denominator", limited.denominator > 0 && limited.numerator >= 20, JSON.stringify({ n: limited.numerator, d: limited.denominator }));

await sleep(62_000);

// ---- S11 privileged activity
await enroll(admin);
for (let i = 0; i < 5; i += 1) {
  const did = `did:web:scenario-${tag}-${i}.wp31.test`;
  await admin("POST", "/api/v1/identity/trust-registry/issuers", { issuerDid: did, organizationName: "Scenario Issuer", permittedCredentialTypes: ["UniversityAffiliationCredential"], validDays: 30, roles: ["issuer"] }, await stepUp(admin, "trust.registry.write", did));
}
fact("S11", "a burst of trust changes opens a case", Boolean(await waitRule("TRU-01", 40_000)));

// ---- incident lifecycle
const T = (id) => `${I}/incidents/${id}/transition`;
check("incident", "skipping triage straight to closed is refused", await admin("POST", T(s1.incident_id), { status: "CLOSED", note: "skip" }), (r) => r.status === 409);
check("incident", "a holder cannot change an incident", await holder("POST", T(s1.incident_id), { status: "TRIAGED", note: "nope" }), (r) => r.status === 403);
check("incident", "an administrator triages", await admin("POST", T(s1.incident_id), { status: "TRIAGED", note: "Checking with the account owner" }), (r) => r.status === 200);
const fp = await admin("POST", T(s1.incident_id), { status: "FALSE_POSITIVE", note: "Owner forgot the password" }, await stepUp(admin, "incident.review", s1.incident_id));
check("incident", "a false positive keeps its reason and history", fp, (r) => r.data.status === "FALSE_POSITIVE" && r.data.history.length === 3);
check("incident", "a human confirms a suspected attack", await admin("POST", T(s2.incident_id), { status: "CONFIRMED", note: "Scenario confirmed by reviewer" }, await stepUp(admin, "incident.review", s2.incident_id)), (r) => r.status === 200);
const labels = (await admin("GET", `${I}/model`)).data;
fact("incident", "reviewed labels are counted, the model stays untrained", labels.reviewed_labels.CONFIRMED === 1 && labels.reviewed_labels.FALSE_POSITIVE === 1 && labels.model_status === "NOT_TRAINED" && labels.metrics === null);

// ---- S13 source outage: delayed, not lost, not doubled
const beforeOutage = (await counts())["auth.login.failure"] ?? 0;
docker("stop", `${PROJECT}-fraud-service-1`);
const outageName = `outage.${tag}@wp31.test`;
for (let i = 0; i < 3; i += 1) await badLogin(outageName);
await sleep(8_000);
docker("start", `${PROJECT}-fraud-service-1`);
for (let i = 0; i < 40; i += 1) { const r = await fetch("http://localhost:29382/health").catch(() => null); if (r?.ok) break; await sleep(500); }
await sleep(12_000);
fact("S13", "events raised during the outage arrive exactly once", ((await counts())["auth.login.failure"] ?? 0) === beforeOutage + 3);
const sources = (await admin("GET", `${I}/health`)).data.sources;
fact("S13", "the delivery failures are visible", sources.find((s) => s.source === "identity-service").delivery_failures > 0, JSON.stringify(sources.map((s) => [s.source, s.state, s.delivery_failures])));

// ---- privacy: read what was really stored
const stored = isolatedMongo('const d=db.getSiblingDB("secure_security_intel"); print(JSON.stringify([d.security_events.find().limit(5000).toArray(), d.incidents.find().toArray(), d.risk_assessments.find().limit(1000).toArray()]))');
for (const [label, needle] of [["usernames", tag], ["e-mail domain", "@wp31.test"], ["example accounts", "example.test"], ["DIDs", "did:key"], ["DID web", "did:web"], ["JWTs", "eyJ"], ["wallet ids", "wallet_"], ["passwords", password], ["IP addresses", "172."]]) {
  fact("privacy", `stored intelligence holds no ${label}`, !stored.includes(needle));
}
fact("privacy", "stored data is real, so that check meant something", stored.length > 5_000, `${stored.length} characters`);

// ---- result
const assessed = (await admin("GET", `${I}/risk?hours=1`)).data;
fact("risk", "real presentations were assessed with mode and reason fields", assessed.assessments > 0 && assessed.recent.every((a) => a.assessment_mode === "RULE_BASED" && a.rule_version && Array.isArray(a.reason_codes)), `${assessed.assessments} assessed`);

const passed = results.filter((r) => r.pass).length;
writeFileSync(`${DIR}scenario_results.json`, JSON.stringify({ passed, failed: results.length - passed, results }, null, 1));
console.log(`\nTOTAL pass=${passed} fail=${results.length - passed}`);
process.exit(results.length === passed ? 0 : 1);
