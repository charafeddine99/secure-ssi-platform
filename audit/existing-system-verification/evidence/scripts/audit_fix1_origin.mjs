// Audit FIX-1 live check: with IDENTITY_PUBLIC_ORIGIN empty (the default), the QR /
// same-device link must point at the address the browser used, never the internal
// Docker hostname, and the whole request_uri path must work through the web origin.
// ISOLATED audit-20261121 stack only. Never prints tokens or passwords.
import { check, fact, fixturePass, login, results } from "./wp31_lib.mjs";

const BASE = "http://localhost:29300";
const verifier = await login(BASE, "verifier@example.test", fixturePass("VERIFIER"));
const holder = await login(BASE, "holder@example.test", fixturePass("HOLDER"));
const body = { purpose: "Audit FIX-1 origin check", requestedCredentialTypes: ["UniversityAffiliationCredential"], requestedFields: ["affiliation"], ttlSeconds: 600 };

const created = check("fix1", "verifier creates a request through the web origin", await verifier("POST", "/api/v1/oid4vp/requests", body), (r) => r.status === 200 || r.status === 201);
const link = String(created.data?.deepLinkUri ?? "");
const qr = String(created.data?.qrPayload ?? "");
const requestUri = new URL(link.replace(/^openid4vp:\/\//, "https://x/")).searchParams.get("request_uri") ?? "";
fact("fix1", "request_uri uses the browser's origin", requestUri.startsWith(`${BASE}/api/v1/oid4vp/request-objects/session_`), requestUri.replace(/session_.*/, "session_<handle>"));
fact("fix1", "no internal hostname in the link or the QR", !/identity-service|api-gateway|mongodb|:8000/.test(decodeURIComponent(link) + decodeURIComponent(qr)));

const fetched = await fetch(requestUri, { headers: { accept: "application/oauth-authz-req+jwt" } });
const jwt = await fetched.text();
fact("fix1", "request_uri is reachable from outside the stack", fetched.status === 200 && jwt.split(".").length === 3, `status=${fetched.status} type=${fetched.headers.get("content-type")}`);

check("fix1", "the holder's wallet resolves the scanned link (own origin)", await holder("POST", "/api/v1/oid4vp/wallet/resolve-request", { link }), (r) => r.status === 200);

// A client cannot steer the link to another host through forwarded headers.
const spoofed = check("fix1", "request with a forged X-Forwarded-Host is still created", await verifier("POST", "/api/v1/oid4vp/requests", body, { "x-forwarded-host": "attacker.example", "x-forwarded-proto": "https" }), (r) => r.status === 200 || r.status === 201);
fact("fix1", "forged X-Forwarded-Host does not reach the link", !String(spoofed.data?.deepLinkUri ?? "").includes("attacker.example"));

const failed = results.filter((r) => !r.pass).length;
console.log(`\nTOTAL pass=${results.length - failed} fail=${failed}`);
process.exit(failed ? 1 : 0);
