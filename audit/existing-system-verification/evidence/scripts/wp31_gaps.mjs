// Acceptance checks for matrix rows the 2026-10-31 audit left as "not yet evidenced".
// Isolated wp31 stack only, synthetic accounts. Prints no secrets.
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { PROJECT, check, client, docker, fact, fixturePass, isolatedMongo, issue, login, present, results, sleep, walletOf } from "./wp31_lib.mjs";

const BASE = "http://localhost:29300";
const DIR = new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const password = `Wp30-${randomBytes(12).toString("hex")}`;
const name = `holder.gap.${randomBytes(3).toString("hex")}@wp31.test`;
const other = `holder.gap2.${randomBytes(3).toString("hex")}@wp31.test`;
const extra = { [name]: { name: "Gap Holder", role: "holder", password }, [other]: { name: "Gap Other", role: "holder", password } };
execFileSync("docker", ["exec", "-i", "-w", "/app", `${PROJECT}-identity-service-1`, "python", "-"], {
  input: readFileSync(`${DIR}seed_users.py`, "utf8").replace("json.load(sys.stdin)", `json.loads(${JSON.stringify(JSON.stringify(extra))})`), encoding: "utf8",
});
const holder = await login(BASE, name, password);
const stranger = await login(BASE, other, password);
const issuer = await login(BASE, "issuer@example.test", fixturePass("ISSUER"));
const verifier = await login(BASE, "verifier@example.test", fixturePass("VERIFIER"));
const admin = await login(BASE, "admin@example.test", fixturePass("ADMIN"));
const anon = client(BASE, "anon");
const wallet = await walletOf(holder);
const cred = await issue(BASE, issuer, holder, wallet.walletId, "SYN-GAP-1");
const items = (r) => r.data?.items ?? r.data?.credentials ?? r.data?.sessions ?? r.data?.events ?? r.data?.activities ?? (Array.isArray(r.data) ? r.data : []);

// ISS-07
const ISSUED = "/api/v1/identity/credentials/issued?limit=100";
check("ISS-07", "an issued credential appears in the issuer's list", await issuer("GET", ISSUED), (r) => r.status === 200 && JSON.stringify(r.data).includes(cred.id));
check("ISS-07", "the list carries no raw claims", await issuer("GET", ISSUED), (r) => !JSON.stringify(r.data).includes("SYN-GAP-1"));
check("ISS-07", "a holder cannot read the issuer list", await holder("GET", ISSUED), (r) => r.status === 403);
check("ISS-07", "an anonymous caller cannot read it", await anon("GET", ISSUED), (r) => r.status === 401);

// ISS-04
const badOffer = await issuer("POST", "/api/v1/oid4vci/offers", { credentialConfigurationIds: ["UniversityAffiliationCredential"], subjectData: { affiliation: "student", injectedClaim: "x" }, ttlSeconds: 300 });
check("ISS-04", "an offer with an undeclared claim is refused", badOffer, (r) => r.status >= 400 && r.status < 500);
check("ISS-04", "an unknown credential configuration is refused", await issuer("POST", "/api/v1/oid4vci/offers", { credentialConfigurationIds: ["NoSuchCredential"], subjectData: { affiliation: "student" }, ttlSeconds: 300 }), (r) => r.status >= 400 && r.status < 500);

// Expired and reused offers
const offerBody = { credentialConfigurationIds: ["UniversityAffiliationCredential"], subjectData: { affiliation: "student", programCode: "SYN-GAP-2", degree: "Master of Science", graduationYear: 2028 }, ttlSeconds: 600 };
const codeOf = (o) => JSON.parse(decodeURIComponent((o.deepLinkUri || o.qrPayload).split("credential_offer=")[1])).grants["urn:ietf:params:oauth:grant-type:pre-authorized_code"]["pre-authorized_code"];
const tokenFor = (code) => anon("POST", "/api/v1/oid4vci/token", new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:pre-authorized_code", "pre-authorized_code": code }));
const expiring = (await issuer("POST", "/api/v1/oid4vci/offers", offerBody)).data;
isolatedMongo(`const c=db.getSiblingDB("secure_identity").credential_offers; const o=c.find().sort({_id:-1}).limit(1).next(); const past=new Date(Date.now()-60000); const made=new Date(Date.now()-120000); const v=(d)=>typeof o.expiresAt==="string"?d.toISOString():d; c.updateOne({_id:o._id},{$set:{expiresAt:v(past),createdAt:v(made)}});`);
check("OFFER", "an expired offer gives no token", await tokenFor(codeOf(expiring)), (r) => r.status >= 400 && r.status < 500);
const usedCode = codeOf((await issuer("POST", "/api/v1/oid4vci/offers", offerBody)).data);
check("OFFER", "a fresh offer gives a token", await tokenFor(usedCode), (r) => r.status === 200);
check("OFFER", "the same code cannot be used twice", await tokenFor(usedCode), (r) => r.status >= 400 && r.status < 500);

// VER-03
const request = (await verifier("POST", "/api/v1/oid4vp/requests", { purpose: "Gap preview", requestedCredentialTypes: ["UniversityAffiliationCredential"], requestedFields: ["affiliation"], ttlSeconds: 600 })).data;
const seen = await holder("GET", `/api/v1/oid4vp/requests/${request.sessionId}/holder-request`);
check("VER-03", "the wallet reads the same request the verifier made", seen, (r) => r.status === 200 && r.data.nonce === request.nonce);
fact("VER-03", "the DCQL query is identical on both sides", JSON.stringify(seen.data.dcqlQuery ?? seen.data.dcql_query) === JSON.stringify(request.dcqlQuery ?? request.dcql_query) && Boolean(seen.data.dcqlQuery ?? seen.data.dcql_query));
fact("VER-03", "the purpose is identical on both sides", seen.data.purpose === undefined || seen.data.purpose === request.purpose, String(seen.data.purpose));

// VER-05
await holder("POST", `/api/v1/oid4vp/requests/${request.sessionId}/evaluate-dcql`, { candidateCredentials: [cred] });
const denied = await holder("POST", `/api/v1/oid4vp/requests/${request.sessionId}/wallet-consent`, { walletId: wallet.walletId, holderDid: wallet.holderDid, action: "REJECT", approvedCredentials: [], approvedClaims: {}, rejectedClaims: [] });
check("VER-05", "the holder's refusal is recorded", denied, (r) => r.status < 300);
const afterDeny = await verifier("GET", `/api/v1/oid4vp/requests/${request.sessionId}`);
check("VER-05", "the verifier sees an explicit final state, not success", afterDeny, (r) => r.status === 200 && r.data.status !== "PENDING" && !/ACCEPT|VERIFIED|SUCCESS/i.test(String(r.data.status)), String(afterDeny.data?.status));

// VER-07, HOL-12
const accepted = await present(verifier, holder, wallet, cred);
fact("VER-07", "a real presentation is accepted first", accepted.final === "ACCEPTED", accepted.final);
const history = await verifier("GET", "/api/v1/oid4vp/requests?limit=100");
check("VER-07", "the refused request is in the verifier history", history, (r) => r.status === 200 && JSON.stringify(r.data).includes(request.sessionId));
fact("VER-07", "history reports the refusal truthfully", JSON.stringify(items(history).find((i) => (i.sessionId ?? i.session_id) === request.sessionId)?.status ?? "") === JSON.stringify(afterDeny.data.status), String(afterDeny.data.status));
check("VER-07", "a holder cannot read verifier history", await holder("GET", "/api/v1/oid4vp/requests?limit=100"), (r) => r.status === 403 || (r.status === 200 && !JSON.stringify(r.data).includes(request.sessionId)));
const ACT = `/api/v1/identity/wallets/${wallet.walletId}/activity`;
const activity = await holder("GET", ACT);
check("HOL-12", "the wallet activity lists what happened", activity, (r) => r.status === 200 && items(r).length > 0, `${items(activity).length} entries`);
check("HOL-12", "another holder cannot read it", await stranger("GET", ACT), (r) => [403, 404].includes(r.status));
fact("HOL-12", "activity carries no raw credential or proof", !/"proofValue"|vpToken|credentialSubject/.test(JSON.stringify(activity.data)));

// ADM-03
const spoof = { "x-user-id": "admin", "x-user-role": "admin", "x-user-roles": "admin", "x-roles": "admin", "x-authenticated-user": "admin", "x-forwarded-user": "admin" };
check("ADM-03", "spoofed role headers do not reach admin data", await holder("GET", "/api/v1/identity/admin/users", undefined, spoof), (r) => r.status === 403);
check("ADM-03", "the admin list works for an administrator", await admin("GET", "/api/v1/identity/admin/users"), (r) => r.status === 200);
const meSpoofed = await holder("GET", "/api/v1/identity/auth/me", undefined, spoof);
fact("ADM-03", "the session identity ignores those headers", !JSON.stringify(meSpoofed.data.roles ?? "").toLowerCase().includes("admin"), JSON.stringify(meSpoofed.data.roles));

// ADM-06, HOL-05
const REV = `/api/v1/identity/credentials/${encodeURIComponent(cred.id)}`;
check("ADM-06", "an administrator cannot revoke an issuer's credential", await admin("POST", `${REV}/revoke`, { reason: "gap test" }), (r) => r.status === 403);
const tampered = structuredClone(cred);
tampered.credentialSubject.affiliation = "faculty";
const verdict = await verifier("POST", "/api/v1/identity/credentials/verify", { credential: tampered });
check("HOL-05", "a tampered copy does not verify", verdict, (r) => r.status >= 400 || r.data.valid === false || r.data.verified === false, `HTTP ${verdict.status}`);
check("ADM-06", "the issuer can revoke it", await issuer("POST", `${REV}/revoke`, { reason: "gap test" }), (r) => r.status === 200);
const lifecycle = await issuer("GET", `${REV}/history`);
check("ADM-06", "the revocation is in the persisted history", lifecycle, (r) => r.status === 200 && /REVOK/i.test(JSON.stringify(r.data)));
const afterRevoke = await present(verifier, holder, wallet, cred);
fact("ADM-06", "a verifier then refuses the credential", afterRevoke.final !== "ACCEPTED", afterRevoke.final);

// Audit chain
const INTEGRITY = "/api/v1/identity/audit/integrity";
const clean = await admin("GET", INTEGRITY);
check("AUDIT-CHAIN", "the chain of real events is intact", clean, (r) => r.status === 200 && r.data.status === "INTACT" && r.data.checked > 0, `${clean.data?.checked} checked`);
check("AUDIT-CHAIN", "a holder cannot read integrity", await holder("GET", INTEGRITY), (r) => r.status === 403);
isolatedMongo(`const d=db.getSiblingDB("secure_identity").audit_events; const e=d.find({chainSeq:{$exists:true}}).sort({chainSeq:1}).limit(1).next(); d.updateOne({_id:e._id},{$set:{"wp31Original":e.eventType,eventType:"WP31_TAMPERED"}});`);
check("AUDIT-CHAIN", "an edited event breaks the chain", await admin("GET", INTEGRITY), (r) => r.data.status === "BROKEN");
isolatedMongo(`const d=db.getSiblingDB("secure_identity").audit_events; const e=d.findOne({eventType:"WP31_TAMPERED"}); d.updateOne({_id:e._id},{$set:{eventType:e.wp31Original},$unset:{wp31Original:""}});`);
check("AUDIT-CHAIN", "undoing the edit restores the chain", await admin("GET", INTEGRITY), (r) => r.data.status === "INTACT");

// AI-09: quarantine survives a real restart of the fraud container
const qDid = `did:example:wp31-${randomBytes(4).toString("hex")}`;
const Q = "/api/v1/fraud/quarantine";
const restartFraud = async () => {
  docker("restart", `${PROJECT}-fraud-service-1`);
  for (let i = 0; i < 60; i += 1) { const r = await fetch("http://localhost:29382/health").catch(() => null); if (r?.ok) return; await sleep(500); }
  throw new Error("fraud service did not come back");
};
check("AI-09", "an administrator quarantines a DID", await admin("POST", Q, { did: qDid, reason: "synthetic drill" }), (r) => r.status === 200 && r.data.is_quarantined === true);
await restartFraud();
const afterRestart = await admin("GET", `${Q}/${encodeURIComponent(qDid)}`);
check("AI-09", "the quarantine survives a container restart", afterRestart, (r) => r.status === 200 && r.data.is_quarantined === true && r.data.reason === "synthetic drill");
const onDisk = docker("exec", `${PROJECT}-fraud-service-1`, "cat", "/var/lib/secure-ssi/fraud/quarantine.json");
fact("AI-13", "the quarantine store holds no raw DID", !onDisk.includes(qDid) && onDisk.includes("subject:"));
check("AI-09", "release works", await admin("DELETE", `${Q}/${encodeURIComponent(qDid)}`), (r) => r.status === 200);
await restartFraud();
check("AI-09", "the release survives a restart", await admin("GET", `${Q}/${encodeURIComponent(qDid)}`), (r) => r.status === 200 && r.data.is_quarantined === false);

const passed = results.filter((r) => r.pass).length;
writeFileSync(`${DIR}gaps_results.json`, JSON.stringify({ passed, failed: results.length - passed, results }, null, 1));
console.log(`\nTOTAL pass=${passed} fail=${results.length - passed}`);
process.exit(results.length === passed ? 0 : 1);
