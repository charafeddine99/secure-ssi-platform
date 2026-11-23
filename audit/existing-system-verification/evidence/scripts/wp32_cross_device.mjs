// WP-32 final: cross-device flow with two separate browsers on one computer.
// Browser 1 is the verifier (desktop). Browser 2 is the holder at phone size.
// The QR is decoded from the real canvas with jsQR. This is NOT a physical phone test.
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { client, fixturePass, issue, login, sleep, walletOf } from "./wp31_lib.mjs";

const BASE = "http://localhost:29300";
const PUBLIC_ORIGIN = "http://wallet.wp31.test";
const SHOTS = process.argv[2];
const SCRATCH = process.env.WP31_SCRATCH;
const JSQR = readFileSync(join(SCRATCH, "qrdec/node_modules/jsqr/dist/jsQR.js"), "utf8");
const AXE = readFileSync("C:/Users/besna/OneDrive/Bureau/secure-ssi-platform/apps/web/node_modules/axe-core/axe.min.js", "utf8");
const DIR = new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
mkdirSync(SHOTS, { recursive: true });
const results = [];
const report = (name, pass, note = "") => { results.push({ name, pass, note }); console.log(`${pass ? "PASS" : "FAIL"} ${name}${note ? ` | ${note}` : ""}`); };

const tag = randomBytes(3).toString("hex");
const pw = `correct horse ${randomBytes(6).toString("hex")} staple`;
const anon = client(BASE, "anon");
const email = `phone.${tag}@wp32.test`;
await anon("POST", "/api/v1/identity/auth/register", { email, displayName: "Phone Holder", password: pw, role: "holder" });
const holderApi = await login(BASE, email, pw);
const wallet = await walletOf(holderApi);
const issuer = await login(BASE, "issuer@example.test", fixturePass("ISSUER"));
const cred = await issue(BASE, issuer, holderApi, wallet.walletId, "SYN-WP32-PHONE");

async function browser(port, label) {
  const proc = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${join(SCRATCH, `edge-${label}-${Date.now()}`)}`, "--window-size=1440,900", "--no-first-run", "about:blank"], { stdio: "ignore" });
  let ws;
  for (let i = 0; i < 80 && !ws; i += 1) {
    try { const page = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page"); if (page) ws = new WebSocket(page.webSocketDebuggerUrl); } catch { await sleep(250); }
  }
  await new Promise((r) => ws.addEventListener("open", r, { once: true }));
  let id = 0; const pending = new Map(); const b = { proc, errors: 0, failed: [] };
  ws.addEventListener("message", (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === "Runtime.exceptionThrown") b.errors += 1;
    if (m.method === "Network.responseReceived" && m.params.response.url.includes("/api/") && m.params.response.status >= 500) b.failed.push(m.params.response.status);
  });
  b.send = (method, params = {}) => new Promise((res, rej) => { id += 1; pending.set(id, (m) => (m.error ? rej(new Error(m.error.message)) : res(m.result))); ws.send(JSON.stringify({ id, method, params })); });
  b.ev = async (expression) => (await b.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result.value;
  b.go = async (url) => { await b.send("Page.navigate", { url }); await sleep(2300); };
  b.text = () => b.ev("document.body.innerText");
  b.shot = async (name) => { const { data } = await b.send("Page.captureScreenshot", { format: "png" }); writeFileSync(join(SHOTS, `${name}.png`), Buffer.from(data, "base64")); };
  b.set = (labelText, value) => b.ev(`(()=>{const lab=[...document.querySelectorAll("label")].find(x=>x.textContent.trim().startsWith(${JSON.stringify(labelText)}));const i=document.getElementById(lab.htmlFor);const p=i.tagName==="TEXTAREA"?HTMLTextAreaElement.prototype:i.tagName==="SELECT"?HTMLSelectElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,"value").set.call(i,${JSON.stringify(value)});i.dispatchEvent(new Event(i.tagName==="SELECT"?"change":"input",{bubbles:true}));return true})()`);
  b.click = (text, scope = "button,a") => b.ev(`(()=>{const x=[...document.querySelectorAll(${JSON.stringify(scope)})].find(e=>e.textContent.trim().startsWith(${JSON.stringify(text)})&&!e.disabled);if(!x)return false;x.click();return true})()`);
  b.wait = async (re, ms = 15000) => { const end = Date.now() + ms; for (;;) { if (new RegExp(re, "i").test(await b.text())) return true; if (Date.now() > end) return false; await sleep(300); } };
  // All test accounts share one IP, so a sign-in refused by the rate limit is waited out, never raised.
  b.signIn = async (user, password) => {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      await b.go(`${BASE}/login`); await b.set("Username", user); await b.set("Password", password);
      await b.ev(`document.querySelector("form button[type=submit]").click()`); await sleep(2800);
      if ((await b.ev("location.pathname")) !== "/login") return;
      await sleep(62_000);
    }
    throw new Error(`sign-in failed for ${label}`);
  };
  await b.send("Page.enable"); await b.send("Runtime.enable"); await b.send("Network.enable");
  return b;
}

const desk = await browser(9447, "verifier");
const phone = await browser(9457, "holder");
await desk.send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await phone.send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });

async function createRequest(purpose) {
  await desk.go(`${BASE}/verifier/request`);
  await desk.set("Credential type", "UniversityAffiliationCredential"); await sleep(500);
  await desk.ev(`[...document.querySelectorAll("form input[type=checkbox]")].forEach(c=>{if(!c.checked)c.click()})`);
  await desk.set("Purpose shown to the holder", purpose);
  await desk.click("Create request", "button"); await sleep(3000);
  await desk.ev(JSQR + ";0");
  return desk.ev(`(()=>{const c=document.querySelector("canvas[role=img]");if(!c)return null;const d=c.getContext("2d").getImageData(0,0,c.width,c.height);const r=jsQR(d.data,c.width,c.height);return r?r.data:null})()`);
}
const forPhone = (payload) => payload.replace(PUBLIC_ORIGIN, BASE);

try {
  await desk.signIn("verifier@example.test", fixturePass("VERIFIER"));
  await phone.signIn(email, pw);

  // 1-4: request, QR on screen, decoded from pixels
  const payload = await createRequest("WP-32 cross-device check");
  await desk.shot("verifier-qr-request");
  report("the verifier page renders a QR that decodes from its pixels", Boolean(payload));
  report("the QR is an HTTPS-style handoff link with an opaque handle, no credential id", /^https?:\/\/[^/]+\/wallet\/present\?request=session_[A-Za-z0-9_-]{24,}$/.test(payload ?? "") && !/urn:uuid|did:|nonce/.test(payload ?? ""), (payload ?? "").replace(/session_[A-Za-z0-9_-]+/, "session_<redacted>"));
  report("the QR carries the configured public origin, not localhost", (payload ?? "").startsWith(PUBLIC_ORIGIN));
  const deskAxe = JSON.parse(await (async () => { await desk.ev(AXE + ";0"); return desk.ev(`axe.run(document.querySelector("main")||document).then(r=>JSON.stringify(r.violations.map(v=>v.id)))`); })());
  report("the verifier QR page passes axe", deskAxe.length === 0, deskAxe.join(","));

  // 5-8: the "phone" opens the link, sees verifier, purpose and claims, approves
  await phone.go(forPhone(payload));
  report("the holder lands on consent", await phone.wait("WP-32 cross-device check") && (await phone.ev("location.pathname")) === "/wallet/consent");
  const consentText = await phone.text();
  report("consent names the verifier and the requested claim", /verifier/i.test(consentText) && /affiliation/i.test(consentText));
  await phone.shot("holder-consent-390");
  await phone.ev(`[...document.querySelectorAll("main input[type=radio]")].slice(0,1).forEach(r=>{if(!r.checked)r.click()})`); await sleep(300);
  await phone.ev(`[...document.querySelectorAll("main input[type=checkbox]")].forEach(c=>{if(!c.checked)c.click()})`); await sleep(400);
  report("the holder approves", await phone.click("Share credential", "button"));
  await sleep(5000);
  await phone.shot("holder-after-share-390");

  // 9-10: verifier sees the same transaction ACCEPTED with a check matrix
  await desk.click("Refresh", "button"); await sleep(2500);
  report("the verifier sees the result with its check matrix", await desk.wait("Verification checks") && /VERIFIED|ACCEPTED/i.test(await desk.text()));
  await desk.shot("verifier-accepted");

  // 11: the same QR again is refused
  await phone.go(forPhone(payload)); await sleep(1500);
  const replay = await phone.text();
  report("scanning the same QR again does not open a new consent", !/Share credential/.test(replay) || (await phone.ev(`!![...document.querySelectorAll("button")].find(b=>b.textContent.trim()==="Share credential"&&!b.disabled)`)) === false, replay.match(/(no longer|expired|completed|already|not found|could not)[^\n]{0,60}/i)?.[0] ?? "");
  await phone.shot("holder-replay-390");

  // 13: consent refused is not shown as success
  const declinePayload = await createRequest("WP-32 decline check");
  await phone.go(forPhone(declinePayload)); await phone.wait("WP-32 decline check");
  const declined = await phone.click("Decline", "button") || await phone.click("Reject", "button") || await phone.click("Do not share", "button");
  await sleep(2500);
  report("the holder can decline", declined);
  await desk.click("Refresh", "button"); await sleep(2500);
  const deskDecline = await desk.text();
  report("a declined request is not shown as verified", !/VERIFIED|ACCEPTED/.test(deskDecline));
  await desk.shot("verifier-declined");

  // 12: revoked credential is REJECTED
  await issuer("POST", `/api/v1/identity/credentials/${encodeURIComponent(cred.id)}/revoke`, { reason: "WP-32 cross-device" });
  const revokedPayload = await createRequest("WP-32 revoked check");
  await phone.go(forPhone(revokedPayload)); await phone.wait("WP-32 revoked check");
  await phone.ev(`[...document.querySelectorAll("main input[type=radio]")].slice(0,1).forEach(r=>{if(!r.checked)r.click()})`); await sleep(300);
  await phone.ev(`[...document.querySelectorAll("main input[type=checkbox]")].forEach(c=>{if(!c.checked)c.click()})`); await sleep(400);
  const shared = await phone.click("Share credential", "button"); await sleep(5000);
  await phone.shot("holder-revoked-390");
  await desk.click("Refresh", "button"); await sleep(2500);
  const deskRevoked = await desk.text();
  report("a revoked credential is not accepted", !/\bVERIFIED\b|\bACCEPTED\b/.test(deskRevoked) || /REJECTED|revoked/i.test(deskRevoked), shared ? "presented" : "wallet refused before sharing");
  await desk.shot("verifier-revoked");
  report("no browser exception and no 5xx", desk.errors + phone.errors === 0 && desk.failed.length + phone.failed.length === 0, `${desk.errors + phone.errors} exceptions, ${desk.failed.join(",")}${phone.failed.join(",")}`);
} catch (error) {
  await desk.shot("failure-desk").catch(() => {});
  await phone.shot("failure-phone").catch(() => {});
  report("run stopped", false, String(error).slice(0, 180));
}
const failed = results.filter((r) => !r.pass).length;
writeFileSync(`${DIR}cross_device_results.json`, JSON.stringify(results, null, 1));
console.log(`\nTOTAL pass=${results.length - failed} fail=${failed}`);
desk.proc.kill(); phone.proc.kill();
process.exit(failed ? 1 : 0);
