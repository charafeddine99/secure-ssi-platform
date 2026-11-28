// WP-32 final: OpenID4VP positive and negative cases on the isolated stack, through
// the real gateway. Synthetic accounts only. A case passes only on the safe outcome.
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { writeFileSync } from "node:fs";
import { PROJECT, check, client, docker, fact, fixturePass, isolatedMongo, issue, login, results, sleep, walletOf } from "./wp31_lib.mjs";

const BASE = "http://localhost:29300";
const DIR = new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const tag = randomBytes(3).toString("hex");
const pw = `correct horse ${randomBytes(6).toString("hex")} staple`;
const anon = client(BASE, "anon");
async function holderAccount(name) {
  const email = `${name}.${tag}@wp32.test`;
  await anon("POST", "/api/v1/identity/auth/register", { email, displayName: "Synthetic Holder", password: pw, role: "holder" });
  const c = await login(BASE, email, pw);
  return { c, wallet: await walletOf(c) };
}
const A = await holderAccount("alpha");
const B = await holderAccount("bravo");
const issuer = await login(BASE, "issuer@example.test", fixturePass("ISSUER"));
const verifier = await login(BASE, "verifier@example.test", fixturePass("VERIFIER"));
const credA = await issue(BASE, issuer, A.c, A.wallet.walletId, "SYN-WP32-A");

const newRequest = async (types = ["UniversityAffiliationCredential"]) =>
  (await verifier("POST", "/api/v1/oid4vp/requests", { purpose: "WP-32 security check", requestedCredentialTypes: types, requestedFields: ["affiliation"], ttlSeconds: 600 })).data;
const claimsOf = (cred) => Object.fromEntries(Object.entries(cred.credentialSubject).filter(([k]) => k !== "id"));
async function consentAndVp(h, request, cred) {
  const claims = claimsOf(cred);
  await h.c("POST", `/api/v1/oid4vp/requests/${request.sessionId}/evaluate-dcql`, { candidateCredentials: [cred] });
  await h.c("POST", `/api/v1/oid4vp/requests/${request.sessionId}/wallet-consent`, { walletId: h.wallet.walletId, holderDid: h.wallet.holderDid, action: "APPROVE", approvedCredentials: [cred.id], approvedClaims: claims, rejectedClaims: [] });
  return h.c("POST", "/api/v1/oid4vp/wallet-presentation", { sessionId: request.sessionId, walletId: h.wallet.walletId, credentialIds: [cred.id], disclosedClaims: claims });
}
const respond = (h, sessionId, vpToken, cred) => h.c("POST", "/api/v1/oid4vp/response", { sessionId, vpToken, disclosedClaims: claimsOf(cred) });
const verdict = (r) => r.data?.result?.finalPolicyResult ?? `HTTP_${r.status}`;
const accepted = (r) => r.status === 200 && verdict(r) === "ACCEPTED";
const clone = (value) => JSON.parse(JSON.stringify(value));
const proofOf = (vp) => (Array.isArray(vp.proof) ? vp.proof[0] : vp.proof);

// Positive
const r1 = await newRequest();
const vp1 = await consentAndVp(A, r1, credA);
const ok = await respond(A, r1.sessionId, vp1.data.vpToken, credA);
fact("positive", "a valid presentation is ACCEPTED", accepted(ok), verdict(ok));
const seen = await verifier("GET", `/api/v1/oid4vp/requests/${r1.sessionId}`);
fact("positive", "the verifier shows a check matrix for the result", Boolean(seen.data.verificationResult) && JSON.stringify(seen.data.verificationResult).length > 50, String(seen.data.status));
check("replay", "the same presentation sent again is refused", await respond(A, r1.sessionId, vp1.data.vpToken, credA), (r) => !accepted(r), "");

// Nonce and state binding
const r2 = await newRequest();
await consentAndVp(A, r2, credA);
check("nonce", "a VP made for another request (other nonce) is refused", await respond(A, r2.sessionId, vp1.data.vpToken, credA), (r) => !accepted(r));
const r3 = await newRequest();
const vp3 = await consentAndVp(A, r3, credA);
const changedNonce = clone(vp3.data.vpToken);
const proof3 = proofOf(changedNonce);
if (proof3?.challenge) proof3.challenge = `${proof3.challenge}x`; else if (proof3?.nonce) proof3.nonce = `${proof3.nonce}x`;
check("nonce", "a VP whose nonce was edited is refused", await respond(A, r3.sessionId, changedNonce, credA), (r) => !accepted(r));
const changedDomain = clone(vp3.data.vpToken);
const proofD = proofOf(changedDomain);
if (proofD) proofD.domain = "decentralized_identifier:did:jwk:attacker";
check("client_id", "a VP bound to another client_id is refused", await respond(A, r3.sessionId, changedDomain, credA), (r) => !accepted(r));
const r4 = await newRequest();
await consentAndVp(A, r4, credA);
check("state", "a VP posted under another session (state mismatch) is refused", await respond(A, r4.sessionId, vp3.data.vpToken, credA), (r) => !accepted(r));

// Expired request
const r5 = await newRequest();
isolatedMongo(`db.getSiblingDB("secure_identity").verification_sessions.updateOne({sessionId:${JSON.stringify(r5.sessionId)}},{$set:{createdAt:new Date(Date.now()-120000),expiresAt:new Date(Date.now()-60000)}})`);
const expiredRead = await A.c("GET", `/api/v1/oid4vp/requests/${r5.sessionId}/holder-request`);
check("expiry", "an expired request cannot be opened by the wallet", expiredRead, (r) => r.status === 410 || r.status === 404, String(expiredRead.status));
const expiredVp = await consentAndVp(A, r5, credA);
fact("expiry", "an expired request yields no presentation", expiredVp.status !== 200, String(expiredVp.status));

// Consent refused
const r6 = await newRequest();
await A.c("POST", `/api/v1/oid4vp/requests/${r6.sessionId}/evaluate-dcql`, { candidateCredentials: [credA] });
await A.c("POST", `/api/v1/oid4vp/requests/${r6.sessionId}/wallet-consent`, { walletId: A.wallet.walletId, holderDid: A.wallet.holderDid, action: "REJECT", approvedCredentials: [], approvedClaims: {}, rejectedClaims: [] });
check("consent", "after a refusal no VP can be created", await A.c("POST", "/api/v1/oid4vp/wallet-presentation", { sessionId: r6.sessionId, walletId: A.wallet.walletId, credentialIds: [credA.id], disclosedClaims: claimsOf(credA) }), (r) => r.status !== 200);
const refused = await verifier("GET", `/api/v1/oid4vp/requests/${r6.sessionId}`);
fact("consent", "the verifier does not record a refusal as success", !/ACCEPT|VERIFIED/i.test(String(refused.data.status)), String(refused.data.status));

// Wrong holder
const r7 = await newRequest();
const stolen = await consentAndVp(B, r7, credA);
fact("holder binding", "another holder cannot present A's credential", stolen.status !== 200 || !accepted(await respond(B, r7.sessionId, stolen.data.vpToken, credA)), String(stolen.status));

// DCQL mismatch
const r8 = await newRequest(["NoSuchCredentialType"]);
const dcql = await A.c("POST", `/api/v1/oid4vp/requests/${r8.sessionId}/evaluate-dcql`, { candidateCredentials: [credA] });
fact("dcql", "a credential that does not match the query is not offered", !JSON.stringify(dcql.data ?? {}).includes(credA.id) || /no match|not satisf|unsatisf|false/i.test(JSON.stringify(dcql.data ?? {})), JSON.stringify(dcql.data ?? {}).slice(0, 120));
const mismatchVp = await consentAndVp(A, r8, credA);
fact("dcql", "a non-matching credential is never ACCEPTED", mismatchVp.status !== 200 || !accepted(await respond(A, r8.sessionId, mismatchVp.data.vpToken, credA)));

// Fraud outage
docker("stop", `${PROJECT}-fraud-service-1`);
const r9 = await newRequest();
const vp9 = await consentAndVp(A, r9, credA);
const duringOutage = vp9.status === 200 ? await respond(A, r9.sessionId, vp9.data.vpToken, credA) : vp9;
docker("start", `${PROJECT}-fraud-service-1`);
fact("outage", "a fraud outage never turns into ACCEPTED", !accepted(duringOutage), verdict(duringOutage));
for (let i = 0; i < 40; i += 1) { const r = await fetch("http://localhost:29382/health").catch(() => null); if (r?.ok) break; await sleep(500); }

// Revoked, with a trusted issuer
await issuer("POST", `/api/v1/identity/credentials/${encodeURIComponent(credA.id)}/revoke`, { reason: "WP-32 security check" });
const r10 = await newRequest();
const vp10 = await consentAndVp(A, r10, credA);
const revoked = vp10.status === 200 ? await respond(A, r10.sessionId, vp10.data.vpToken, credA) : vp10;
fact("revocation", "a revoked credential from a trusted issuer is not ACCEPTED", !accepted(revoked), verdict(revoked));

const passed = results.filter((r) => r.pass).length;
writeFileSync(`${DIR}oid4vp_security_results.json`, JSON.stringify({ passed, failed: results.length - passed, results }, null, 1));
console.log(`\nTOTAL pass=${passed} fail=${results.length - passed}`);
process.exit(results.length === passed ? 0 : 1);
