// Offline self-test of the two F-06 checks' logic (same expressions as in wp31_e2e.mjs). No network, no stack.
import { createPublicKey, generateKeyPairSync, sign, verify as verifySignature } from "node:crypto";
const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
const clientIdFor = (jwk) => `decentralized_identifier:did:jwk:${b64(jwk)}`;
const clientIdCheck = (clientId) => {
  const m = /^decentralized_identifier:(did:jwk:([A-Za-z0-9_-]+))$/.exec(String(clientId)); let jwk = {};
  try { jwk = m ? JSON.parse(Buffer.from(m[2], "base64url").toString("utf8")) : {}; } catch { jwk = {}; }
  return { ok: Boolean(m) && jwk.kty === "OKP" && jwk.crv === "Ed25519" && typeof jwk.x === "string" && !("d" in jwk) && !/identity-service|api-gateway|localhost|mongodb|:8000/.test(String(clientId)), jwk, m };
};
const sigCheck = (jwt, jwk) => { const [h, p, s] = jwt.split("."); try { return verifySignature(null, Buffer.from(`${h}.${p}`), createPublicKey({ key: jwk, format: "jwk" }), Buffer.from(s, "base64url")); } catch { return false; } };
const jws = (privateKey, claims) => { const h = b64({ typ: "oauth-authz-req+jwt", alg: "EdDSA" }), p = b64(claims); return `${h}.${p}.${sign(null, Buffer.from(`${h}.${p}`), privateKey).toString("base64url")}`; };
const a = generateKeyPairSync("ed25519"), b = generateKeyPairSync("ed25519");
const pubA = a.publicKey.export({ format: "jwk" }), privA = a.privateKey.export({ format: "jwk" });
let pass = 0, fail = 0; const t = (name, ok) => { ok ? pass++ : fail++; console.log(`${ok ? "PASS" : "FAIL"} [f06-selftest] ${name}`); };
t("a real did:jwk public key is accepted", clientIdCheck(clientIdFor(pubA)).ok === true);
t("a client_id that carries the private part (d) is refused", clientIdCheck(clientIdFor(privA)).ok === false);
t("the old URL client_id is refused", clientIdCheck("http://wallet.wp31.test/verifier").ok === false);
t("an internal host is refused", clientIdCheck("http://identity-service:8000/verifier").ok === false);
t("a request object signed by the client_id key verifies", sigCheck(jws(a.privateKey, { client_id: "x" }), pubA) === true);
t("a request object signed by another key is refused", sigCheck(jws(b.privateKey, { client_id: "x" }), pubA) === false);
t("a tampered payload is refused", (() => { const [h, , s] = jws(a.privateKey, { nonce: "n1" }).split("."); return sigCheck(`${h}.${b64({ nonce: "n2" })}.${s}`, pubA) === false; })());
console.log(`TOTAL pass=${pass} fail=${fail}`); process.exit(fail ? 1 : 0);
