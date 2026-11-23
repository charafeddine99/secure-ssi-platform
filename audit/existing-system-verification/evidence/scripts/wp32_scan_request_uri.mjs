// WP-32: an openid4vp:// link with request_uri pasted into Scan QR, through the real pages.
// through the real pages on the isolated stack. Desktop browser only: no phone.
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { client, enroll, fixturePass, issue, login, sleep, stepUp, walletOf } from "./wp31_lib.mjs";

const BASE = "http://localhost:29300";
const SHOTS = process.argv[2];
const SCRATCH = process.env.WP31_SCRATCH;
const DIR = new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const PORT = 9437;
mkdirSync(SHOTS, { recursive: true });
const AXE = readFileSync("C:/Users/besna/OneDrive/Bureau/secure-ssi-platform/apps/web/node_modules/axe-core/axe.min.js", "utf8");
const results = [];
const report = (name, pass, note = "") => { results.push({ name, pass, note }); console.log(`${pass ? "PASS" : "FAIL"} ${name}${note ? ` | ${note}` : ""}`); };

// Synthetic holder and credential through the real APIs.
const tag = randomBytes(3).toString("hex");
const pw = `correct horse ${randomBytes(6).toString("hex")} staple`;
const anon = client(BASE, "anon");
const email = `card.${tag}@wp32.test`;
await anon("POST", "/api/v1/identity/auth/register", { email, displayName: "Card Holder", password: pw, role: "holder" });
const holderApi = await login(BASE, email, pw);
const wallet = await walletOf(holderApi);
const issuer = await login(BASE, "issuer@example.test", fixturePass("ISSUER"));
const verifier = await login(BASE, "verifier@example.test", fixturePass("VERIFIER"));
const admin = await login(BASE, "admin@example.test", fixturePass("ADMIN"));
const cred = await issue(BASE, issuer, holderApi, wallet.walletId, "SYN-WP32-1");

const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${join(SCRATCH, `edge-card-${Date.now()}`)}`, "--window-size=1440,900", "--hide-scrollbars", "--no-first-run", "about:blank"], { stdio: "ignore" });
let ws;
for (let i = 0; i < 80 && !ws; i += 1) {
  try { const page = (await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()).find((t) => t.type === "page"); if (page) ws = new WebSocket(page.webSocketDebuggerUrl); } catch { await sleep(250); }
}
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0; const pending = new Map(); let consoleErrors = 0;
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === "Runtime.exceptionThrown") consoleErrors += 1;
});
const send = (method, params = {}) => new Promise((res, rej) => { id += 1; pending.set(id, (m) => (m.error ? rej(new Error(m.error.message)) : res(m.result))); ws.send(JSON.stringify({ id, method, params })); });
const ev = async (expression) => (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result.value;
await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable");
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 700 });
const text = () => ev("document.body.innerText");
const go = async (path) => { await send("Page.navigate", { url: BASE + path }); await sleep(2200); };
const waitText = async (pattern, ms = 15000) => { const end = Date.now() + ms; const re = new RegExp(pattern, "i"); for (;;) { if (re.test(await text())) return true; if (Date.now() > end) throw new Error(`timeout: ${pattern}`); await sleep(250); } };
const shot = async (name) => { const { data } = await send("Page.captureScreenshot", { format: "png" }); writeFileSync(join(SHOTS, `${name}.png`), Buffer.from(data, "base64")); };
const setField = (label, value) => ev(`(()=>{const lab=[...document.querySelectorAll("label")].find(x=>x.textContent.trim().startsWith(${JSON.stringify(label)}));const i=document.getElementById(lab.htmlFor);const p=i.tagName==="TEXTAREA"?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,"value").set.call(i,${JSON.stringify(value)});i.dispatchEvent(new Event("input",{bubbles:true}))})()`);
const click = (label, scope = "button,a") => ev(`(()=>{const b=[...document.querySelectorAll(${JSON.stringify(scope)})].find(x=>x.textContent.trim().startsWith(${JSON.stringify(label)})&&!x.disabled);b.click();return true})()`);
const cardText = () => ev(`(document.querySelector("article.ssi-pass")||{}).innerText||""`);
const axe = async () => { await ev(AXE + ";0"); return JSON.parse(await ev(`axe.run(document.querySelector("main")||document,{runOnly:["wcag2a","wcag2aa","wcag21a","wcag21aa","wcag22aa"]}).then(r=>JSON.stringify(r.violations.map(v=>v.id+" "+v.nodes[0].target.join(" "))))`)); };

try {
  await size(1440, 900);
  await go("/login");
  await setField("Username", email); await setField("Password", pw);
  await ev(`document.querySelector("form button[type=submit]").click()`);
  await sleep(2500);

  const request = (await verifier("POST", "/api/v1/oid4vp/requests", { purpose: "WP-32 request_uri check", requestedCredentialTypes: ["UniversityAffiliationCredential"], requestedFields: ["affiliation"], ttlSeconds: 600 })).data;
  const link = request.deepLinkUri ?? "";
  const params = new URLSearchParams(link.split("?")[1] ?? "");
  report("the same-device link carries request_uri and client_id only", link.startsWith("openid4vp://") && params.has("request_uri") && params.has("client_id") && !params.has("dcql_query") && !params.has("nonce"), [...params.keys()].join(","));
  const objectUrl = new URL(params.get("request_uri") ?? "http://invalid/");
  const object = await fetch(`${BASE}${objectUrl.pathname}`);
  const jwt = await object.text();
  const header = JSON.parse(Buffer.from((jwt.split(".")[0] ?? "").replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8") || "{}");
  report("request_uri serves a signed request object", object.status === 200 && jwt.split(".").length === 3 && header.typ === "oauth-authz-req+jwt" && header.alg === "EdDSA", `${object.status} ${object.headers.get("content-type")} ${header.typ} ${header.alg}`);

  await go("/wallet/scan");
  const tampered = link.replace(encodeURIComponent(objectUrl.origin), encodeURIComponent("https://evil.example")).replace(objectUrl.origin, "https://evil.example");
  await setField("Offer or request link", tampered);
  await click("Review link", "button"); await sleep(2500);
  report("a request_uri on an unknown host does not open consent", (await ev("location.pathname")) === "/wallet/scan", (await text()).match(/(refused|not|cannot|could)[^\n]{0,90}/i)?.[0] ?? "no message");
  await shot("scan-request-uri-foreign-host");

  const unknown = link.replace(request.sessionId, `session_${"b".repeat(32)}`);
  await setField("Offer or request link", unknown);
  await click("Review link", "button"); await sleep(2500);
  report("a request_uri for an unknown request does not open consent", (await ev("location.pathname")) === "/wallet/scan");

  await setField("Offer or request link", link);
  const violations = await axe();
  report("the scan page has no axe issue", violations.length === 0, violations.join("; ").slice(0, 120));
  await click("Review link", "button"); await sleep(3000);
  report("the pasted request_uri link opens consent", (await ev("location.pathname")) === "/wallet/consent", await ev("location.pathname"));
  await waitText("WP-32 request_uri check");
  report("consent shows the verifier purpose and requested field", /affiliation/i.test(await text()));
  await shot("consent-from-request-uri");
  await ev(`[...document.querySelectorAll("main input[type=radio]")].slice(0,1).forEach(r=>{if(!r.checked)r.click()})`); await sleep(300);
  await ev(`[...document.querySelectorAll("main input[type=checkbox]")].forEach(c=>{if(!c.checked)c.click()})`); await sleep(500);
  const approve = await ev(`(()=>{const b=[...document.querySelectorAll("button")].find(x=>x.textContent.trim()==="Share credential"&&!x.disabled);if(!b)return false;b.click();return true})()`);
  report("the holder can approve", approve);
  await sleep(4500);
  await shot("presentation-result-request-uri");
  const result = (await verifier("GET", `/api/v1/oid4vp/requests/${request.sessionId}`)).data;
  report("the verifier accepts the presentation after its checks", /ACCEPT|VERIFIED|COMPLETED/i.test(JSON.stringify(result.status ?? "") + JSON.stringify(result.verificationResult ?? "")), String(result.status));

  await setField("Offer or request link", link).catch(() => {});
  await go("/wallet/scan");
  await setField("Offer or request link", link);
  await click("Review link", "button"); await sleep(2500);
  report("the used request cannot be opened again", (await ev("location.pathname")) !== "/wallet/consent" || /no longer|expired|completed|already/i.test(await text()));
  report("no console exception", consoleErrors === 0, String(consoleErrors));
} catch (error) {
  await shot("failure").catch(() => {});
  report("run stopped", false, String(error).slice(0, 180));
}
const failed = results.filter((r) => !r.pass).length;
writeFileSync(`${DIR}scan_request_uri_results.json`, JSON.stringify(results, null, 1));
console.log(`\nTOTAL pass=${results.length - failed} fail=${failed}`);
edge.kill();
process.exit(failed ? 1 : 0);
