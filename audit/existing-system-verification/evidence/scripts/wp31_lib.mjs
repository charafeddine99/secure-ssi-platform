// Shared helpers for WP-31 tests. ISOLATED wp31-* projects only.
// Never prints tokens, passwords, TOTP secrets or payloads.
import { createHmac, generateKeyPairSync, sign as edSign } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { didKeyFromPublicKey, signGuardianJwt } from "file:///C:/Users/besna/OneDrive/Bureau/secure-ssi-platform/apps/web/src/lib/guardianDeviceKey.ts";

export const PROJECT = "audit-20261121";
export const REPO = "C:/Users/besna/OneDrive/Bureau/secure-ssi-platform";
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fixtures = readFileSync(`${REPO}/apps/web/src/api/session.ts`, "utf8");
export const fixturePass = (role) => new RegExp(`${role}: \\{ username: "[^"]+", pass: "([^"]+)"`).exec(fixtures)[1];

export const results = [];
export function check(area, name, response, ok, note = "") {
  let pass = false;
  try { pass = Boolean(ok(response)); } catch { pass = false; }
  results.push({ area, name, status: response?.status ?? null, pass, note });
  console.log(`${pass ? "PASS" : "FAIL"} [${area}] ${name} -> ${response?.status ?? "-"}${note ? " | " + note : ""}`);
  return response;
}
export const fact = (area, name, pass, note = "") => check(area, name, { status: null }, () => pass, note);

export function client(base, label) {
  let cookie = "";
  const call = async (method, path, json, extra = {}) => {
    const headers = { ...extra, origin: base, "x-ssi-client": "web", "sec-fetch-site": "same-origin", accept: "application/json" };
    if (cookie) headers.cookie = cookie;
    let body;
    if (json instanceof URLSearchParams) { headers["content-type"] = "application/x-www-form-urlencoded"; body = json.toString(); }
    else if (typeof json === "string") { headers["content-type"] = "application/json"; body = json; }
    else if (json !== undefined) { headers["content-type"] = "application/json"; body = JSON.stringify(json); }
    let res = await fetch(base + path, { method, headers, body });
    for (let attempt = 0; res.status === 429 && attempt < 8; attempt += 1) {
      const reset = Number(res.headers.get("x-ratelimit-reset")) * 1000;
      await sleep(Math.min(Math.max(reset - Date.now(), 1000) + 250, 61_000));
      res = await fetch(base + path, { method, headers, body });
    }
    const set = res.headers.get("set-cookie");
    if (set) cookie = set.split(";")[0].endsWith("=") ? "" : set.split(";")[0];
    const text = await res.text();
    let data; try { data = JSON.parse(text); } catch { data = text; }
    return { status: res.status, data, text, headers: res.headers };
  };
  call.label = label;
  call.cookie = () => cookie;
  call.setCookie = (value) => { cookie = value; };
  return call;
}

export async function login(base, username, password) {
  const c = client(base, username);
  const r = await c("POST", "/api/v1/identity/auth/token", { username, password });
  if (r.status !== 200) throw new Error(`login failed for ${username}: ${r.status}`);
  c.username = username;
  c.password = password;
  return c;
}

export async function walletOf(c) {
  const listed = await c("GET", "/api/v1/identity/wallets");
  if (listed.status === 200 && listed.data.items?.length) return listed.data.items[0];
  const created = await c("POST", "/api/v1/identity/wallets", {});
  if (created.status !== 201) throw new Error(`wallet create failed ${created.status}`);
  return created.data;
}

export function isolatedMongo(script, container = `${PROJECT}-mongodb-1`) {
  if (!container.startsWith("audit-20261121-")) throw new Error("refusing non-isolated container");
  return execFileSync("docker", ["exec", "-i", container, "sh", "-c",
    'mongosh --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --file /dev/stdin'],
  { input: script, encoding: "utf8" }).trim();
}

export function docker(...args) {
  const joined = args.join(" ");
  if (!joined.includes("audit-20261121-")) throw new Error("refusing a docker command without a wp31 target");
  return execFileSync("docker", args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
}

// ---- TOTP: an independent RFC 6238 implementation, so the test does not trust pyotp.
function base32(value) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of value.replace(/=+$/, "")) bits += alphabet.indexOf(ch).toString(2).padStart(5, "0");
  const out = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) out.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(out);
}
export function totpAt(secret, counter) {
  const message = Buffer.alloc(8);
  message.writeBigUInt64BE(BigInt(counter));
  const digest = createHmac("sha1", base32(secret)).update(message).digest();
  const offset = digest[digest.length - 1] & 15;
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}
/** Each code is single use, so walk the +-1 window, then wait for the next step. */
export async function nextCode(c) {
  for (;;) {
    const now = Math.floor(Date.now() / 30_000);
    // Near the end of a window, a code from the previous one would expire in flight.
    const oldest = Date.now() % 30_000 < 20_000 ? now - 1 : now;
    const counter = Math.max((c.lastCounter ?? 0) + 1, oldest);
    if (counter <= now + 1) { c.lastCounter = counter; return totpAt(c.totpSecret, counter); }
    await sleep(2_000);
  }
}
export async function enroll(c) {
  const begin = await c("POST", "/api/v1/identity/auth/mfa/totp", { password: c.password });
  if (begin.status !== 200) throw new Error(`enroll ${begin.status}`);
  c.totpSecret = begin.data.secret;
  const code = await nextCode(c);
  const confirm = await c("POST", "/api/v1/identity/auth/mfa/totp/confirm", { code });
  if (confirm.status !== 200) throw new Error(`confirm ${confirm.status} ${confirm.text.slice(0, 120)}`);
}
export async function stepUp(c, action, resource) {
  for (let attempt = 0; ; attempt += 1) {
    const r = await c("POST", "/api/v1/identity/auth/step-up", { action, resource, code: await nextCode(c) });
    if (r.status === 200) return { "x-step-up-token": r.data.stepUpToken };
    if (attempt === 1) throw new Error(`step-up ${r.status} ${r.text.slice(0, 160)}`);
    c.lastCounter = Math.max(c.lastCounter ?? 0, Math.floor(Date.now() / 30_000) - 1);
  }
}

// ---- Guardian device key in Node, signing through the real web module.
export function deviceKey() {
  const { publicKey, privateKey } = generateKeyPairSync("ed25519");
  const raw = publicKey.export({ format: "der", type: "spki" }).subarray(-32);
  return { ...didKeyFromPublicKey(new Uint8Array(raw)), sign: async (data) => new Uint8Array(edSign(null, Buffer.from(data), privateKey)) };
}
export { signGuardianJwt };

export async function issue(base, issuer, holder, walletId, programCode) {
  const anon = client(base, "anon");
  const offer = (await issuer("POST", "/api/v1/oid4vci/offers", { credentialConfigurationIds: ["UniversityAffiliationCredential"], subjectData: { affiliation: "student", programCode, degree: "Master of Science", graduationYear: 2028 }, ttlSeconds: 600 })).data;
  const code = JSON.parse(decodeURIComponent((offer.deepLinkUri || offer.qrPayload).split("credential_offer=")[1])).grants["urn:ietf:params:oauth:grant-type:pre-authorized_code"]["pre-authorized_code"];
  const tok = (await anon("POST", "/api/v1/oid4vci/token", new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:pre-authorized_code", "pre-authorized_code": code }))).data;
  const meta = (await anon("GET", "/api/v1/oid4vci/.well-known/openid-credential-issuer")).data;
  const proof = (await holder("POST", "/api/v1/oid4vci/holder-proof", { walletId, audience: meta.credential_issuer, nonce: tok.c_nonce })).data;
  const cred = await holder("POST", "/api/v1/oid4vci/credential", { credentialConfigurationId: "UniversityAffiliationCredential", proof: { proofType: "jwt", jwt: proof.jwt }, walletId }, { authorization: `Bearer ${tok.access_token}` });
  if (cred.status !== 200) throw new Error(`issuance failed ${cred.status} ${cred.text.slice(0, 200)}`);
  return cred.data.credential;
}

export async function present(verifier, holder, wallet, credential) {
  const req = (await verifier("POST", "/api/v1/oid4vp/requests", { purpose: "WP-31 verification", requestedCredentialTypes: ["UniversityAffiliationCredential"], requestedFields: ["affiliation"], ttlSeconds: 600 })).data;
  const sid = req.sessionId;
  await holder("POST", `/api/v1/oid4vp/requests/${sid}/evaluate-dcql`, { candidateCredentials: [credential] });
  const claims = Object.fromEntries(Object.entries(credential.credentialSubject).filter(([k]) => k !== "id"));
  const consent = await holder("POST", `/api/v1/oid4vp/requests/${sid}/wallet-consent`, { walletId: wallet.walletId, holderDid: wallet.holderDid, action: "APPROVE", approvedCredentials: [credential.id], approvedClaims: claims, rejectedClaims: [] });
  const vp = await holder("POST", "/api/v1/oid4vp/wallet-presentation", { sessionId: sid, walletId: wallet.walletId, credentialIds: [credential.id], disclosedClaims: claims });
  if (vp.status !== 200) return { final: `NO_PRESENTATION(${consent.status}/${vp.status})`, detail: JSON.stringify(vp.data).slice(0, 160) };
  const resp = await holder("POST", "/api/v1/oid4vp/response", { sessionId: sid, vpToken: vp.data.vpToken, disclosedClaims: claims });
  return { final: resp.data?.result?.finalPolicyResult ?? `HTTP_${resp.status}`, detail: "" };
}

/** Binds a device key to an invitation and returns the accept response. */
export async function acceptInvitation(base, guardian, invitation, key, { proofKey, claims } = {}) {
  const signer = proofKey ?? key;
  const proof = await signGuardianJwt(signer, "guardian-binding+jwt", { sub: invitation.guardianId, walletId: invitation.walletId, challenge: invitation.challenge, ...claims });
  return guardian("POST", `/api/v1/recovery/guardians/${invitation.guardianId}/accept`,
    { guardianDid: key.did, verificationMethod: key.verificationMethod, proof },
    await stepUp(guardian, "recovery.guardian.accept", invitation.guardianId));
}

export async function decide(guardian, guardianId, key, request, decision = "APPROVE", override = {}) {
  const proof = await signGuardianJwt(key, "guardian-recovery+jwt", {
    sub: guardianId, requestId: request.requestId, sessionId: request.sessionId, walletId: request.walletId,
    decision, challenge: request.challenge, policyHash: request.policyHash, ...override,
  });
  return guardian("POST", `/api/v1/recovery/requests/${request.requestId}/${decision === "APPROVE" ? "approve" : "reject"}`,
    { guardianId, challenge: request.challenge, proof },
    await stepUp(guardian, "recovery.decide", request.requestId));
}
