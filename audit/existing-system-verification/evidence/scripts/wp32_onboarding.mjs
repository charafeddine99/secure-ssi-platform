// Account creation and role boundaries on the isolated stack. Real API calls.
import { randomBytes } from "node:crypto";
import { writeFileSync } from "node:fs";
import { check, client, enroll, fact, fixturePass, login, nextCode, results, sleep, stepUp, walletOf } from "./wp31_lib.mjs";

const BASE = "http://localhost:29300";
const DIR = new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const tag = randomBytes(3).toString("hex");
const pw = `correct horse ${randomBytes(6).toString("hex")} staple`;
const anon = client(BASE, "anon");
const R = "/api/v1/identity/auth/register";
const mail = (n) => `${n}.${tag}@wp32.test`;
const signIn = (u, p = pw) => anon("POST", "/api/v1/identity/auth/token", { username: u, password: p });

// ---- Holder
const holderBody = { email: mail("holder"), displayName: "New Holder", password: pw, role: "holder" };
check("holder", "a short password is refused", await anon("POST", R, { ...holderBody, password: "too-short" }), (r) => r.status === 422);
check("holder", "a common password is refused", await anon("POST", R, { ...holderBody, password: "my-password-is-very-long" }), (r) => r.status === 422);
const first = await anon("POST", R, holderBody);
check("holder", "a person can register", first, (r) => r.status === 202);
const second = await anon("POST", R, holderBody);
fact("holder", "a used address gets the same answer", second.status === first.status && second.text === first.text);
check("holder", "extra fields cannot add a role", await anon("POST", R, { ...holderBody, email: mail("sneaky"), roles: ["admin"] }), (r) => r.status === 422 || r.status === 202);
const holder = await login(BASE, mail("holder"), pw);
const me = (await holder("GET", "/api/v1/identity/auth/me")).data;
fact("holder", "the new account is only a holder", JSON.stringify(me.roles) === '["holder"]', JSON.stringify(me.roles));
const wallet = await walletOf(holder);
fact("holder", "the new holder gets a working wallet", Boolean(wallet?.walletId));
const sneaky = await login(BASE, mail("sneaky"), pw).catch(() => null);
if (sneaky) fact("holder", "a sent role field changes nothing", !JSON.stringify((await sneaky("GET", "/api/v1/identity/auth/me")).data.roles).includes("admin"));

// ---- Issuer application
const admin = await login(BASE, "admin@example.test", fixturePass("ADMIN"));
await enroll(admin);
const apply = (role, n) => anon("POST", R, { email: mail(n), displayName: "Applicant", password: pw, role, organization: "Synthetic University", purpose: "Issue synthetic test credentials" });
check("issuer", "an application without an organisation is refused", await anon("POST", R, { email: mail("x"), displayName: "No Org", password: pw, role: "issuer" }), (r) => r.status === 422);
check("issuer", "an issuer can apply", await apply("issuer", "issuer"), (r) => r.status === 202);
check("issuer", "an applicant cannot sign in yet", await signIn(mail("issuer")), (r) => r.status === 401);
const list = await admin("GET", "/api/v1/identity/admin/onboarding");
const application = list.data.find((i) => i.email === mail("issuer"));
fact("issuer", "the administrator sees the application", application?.status === "PENDING");
const O = "/api/v1/identity/admin/onboarding";
check("issuer", "a holder cannot read applications", await holder("GET", O), (r) => r.status === 403);
check("issuer", "a holder cannot approve", await holder("POST", `${O}/${application.requestId}/approve`, { note: "self approval" }), (r) => r.status === 403);
check("issuer", "approval needs step-up", await admin("POST", `${O}/${application.requestId}/approve`, { note: "checked" }), (r) => r.status === 403);
check("issuer", "the administrator approves with step-up", await admin("POST", `${O}/${application.requestId}/approve`, { note: "Checked by registry" }, await stepUp(admin, "onboarding.decide", application.requestId)), (r) => r.status === 200);
check("issuer", "a decided request cannot be decided again", await admin("POST", `${O}/${application.requestId}/reject`, { note: "changed my mind" }, await stepUp(admin, "onboarding.decide", application.requestId)), (r) => r.status === 409);
await sleep(1_200);
const issuer = await login(BASE, mail("issuer"), pw);
check("issuer", "an unbound issuer cannot create offers", await issuer("POST", "/api/v1/oid4vci/offers", { credentialConfigurationIds: ["UniversityAffiliationCredential"], subjectData: { affiliation: "student" }, ttlSeconds: 300 }), (r) => r.status === 403 || r.status === 409);

// ---- Verifier rejected
check("verifier", "a verifier can apply", await apply("verifier", "verifier"), (r) => r.status === 202);
const vApp = (await admin("GET", O)).data.find((i) => i.email === mail("verifier"));
check("verifier", "the administrator can reject", await admin("POST", `${O}/${vApp.requestId}/reject`, { note: "Could not check the organisation" }, await stepUp(admin, "onboarding.decide", vApp.requestId)), (r) => r.status === 200);
check("verifier", "a rejected applicant still cannot sign in", await signIn(mail("verifier")), (r) => r.status === 401);

// ---- Administrator by invitation only
const adminBody = { email: mail("admin"), displayName: "New Admin", password: pw, role: "admin" };
check("admin", "nobody registers as administrator alone", await anon("POST", R, adminBody), (r) => r.status === 403);
check("admin", "a made-up invitation is refused", await anon("POST", R, { ...adminBody, invitationCode: "x".repeat(40) }), (r) => r.status === 403);
const I = "/api/v1/identity/admin/invitations";
check("admin", "a holder cannot invite", await holder("POST", I, { email: mail("admin") }), (r) => r.status === 403);
check("admin", "inviting needs step-up", await admin("POST", I, { email: mail("admin") }), (r) => r.status === 403);
const invite = await admin("POST", I, { email: mail("admin") }, await stepUp(admin, "admin.invite", mail("admin")));
check("admin", "an administrator can invite", invite, (r) => r.status === 201);
const code = invite.data.invitationCode;
check("admin", "the invitation works only for its address", await anon("POST", R, { ...adminBody, email: mail("other"), invitationCode: code }), (r) => r.status === 403);
check("admin", "the invited person can join", await anon("POST", R, { ...adminBody, invitationCode: code }), (r) => r.status === 202);
check("admin", "the invitation works once", await anon("POST", R, { ...adminBody, email: mail("admin"), invitationCode: code }), (r) => r.status === 403);
const newAdmin = await login(BASE, mail("admin"), pw);
check("admin", "the new administrator has access", await newAdmin("GET", "/api/v1/identity/admin/users"), (r) => r.status === 200);

// ---- Role boundaries
const fixtureIssuer = await login(BASE, "issuer@example.test", fixturePass("ISSUER"));
const verifier = await login(BASE, "verifier@example.test", fixturePass("VERIFIER"));
const W = `/api/v1/identity/wallets/${wallet.walletId}`;
check("roles", "an administrator cannot read a holder wallet", await admin("GET", `${W}/credentials`), (r) => r.status === 403);
check("roles", "an administrator cannot create offers", await admin("POST", "/api/v1/oid4vci/offers", { credentialConfigurationIds: ["UniversityAffiliationCredential"], subjectData: {}, ttlSeconds: 300 }), (r) => r.status === 403);
check("roles", "an issuer cannot read a holder wallet", await fixtureIssuer("GET", `${W}/credentials`), (r) => r.status === 403);
check("roles", "an issuer cannot read users", await fixtureIssuer("GET", "/api/v1/identity/admin/users"), (r) => r.status === 403);
check("roles", "a verifier cannot create offers", await verifier("POST", "/api/v1/oid4vci/offers", { credentialConfigurationIds: ["UniversityAffiliationCredential"], subjectData: {}, ttlSeconds: 300 }), (r) => r.status === 403);
check("roles", "a holder cannot change the trust registry", await holder("POST", "/api/v1/identity/trust-registry/issuers", { issuerDid: "did:web:x.wp32.test", organizationName: "X", permittedCredentialTypes: ["A"], validDays: 1, roles: ["issuer"] }), (r) => r.status === 403);
check("roles", "every role can open its own MFA status", await verifier("GET", "/api/v1/identity/auth/mfa"), (r) => r.status === 200);

// ---- Incident review
const N = "/api/v1/fraud/intel/incidents";
await sleep(6_000);
for (let i = 0; i < 6; i += 1) await anon("POST", "/api/v1/identity/auth/token", { username: mail("target"), password: "wrong-password-value" });
let incident;
for (let i = 0; i < 20 && !incident; i += 1) { await sleep(1_500); incident = (await admin("GET", `${N}?limit=200`)).data.items.find((x) => x.rule_id === "AUTH-01" && x.status === "NEW"); }
fact("incident", "a case exists to review", Boolean(incident));
const T = `${N}/${incident.incident_id}/transition`;
check("incident", "triage needs no step-up", await admin("POST", T, { status: "TRIAGED", note: "Looking at it" }), (r) => r.status === 200);
check("incident", "dismissing a case needs step-up", await admin("POST", T, { status: "FALSE_POSITIVE", note: "Owner typo" }), (r) => r.status === 403);
check("incident", "dismissing works with step-up", await admin("POST", T, { status: "FALSE_POSITIVE", note: "Owner typo" }, await stepUp(admin, "incident.review", incident.incident_id)), (r) => r.status === 200);

const passed = results.filter((r) => r.pass).length;
writeFileSync(`${DIR}onboarding_results.json`, JSON.stringify({ passed, failed: results.length - passed, results }, null, 1));
console.log(`\nTOTAL pass=${passed} fail=${results.length - passed}`);
process.exit(results.length === passed ? 0 : 1);
