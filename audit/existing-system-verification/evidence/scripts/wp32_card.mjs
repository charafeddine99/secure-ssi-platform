// WP-32: the green credential card, Present, scanner input and the verifier QR flow,
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
const PORT = 9427;
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
  await go("/wallet");
  await waitText("Stored credentials");
  await sleep(2500);
  let card = await cardText();
  report("the green card is still a wallet pass", Boolean(await ev(`Boolean(document.querySelector("article.ssi-pass"))`)));
  report("the card carries no QR code", !(await ev(`Boolean(document.querySelector("article.ssi-pass img, article.ssi-pass canvas, article.ssi-pass svg[aria-label*=QR]"))`)));
  report("credential status comes from the live check and says Active", /Credential status\s*Active/i.test(card), card.replace(/\n/g, " ").slice(0, 120));
  report("issuer trust is shown separately", /Trusted issuer|Issuer not in registry|Issuer trust unknown/.test(card));
  report("Active · stored is gone", !/Active · stored/.test(card));
  report("a valid card keeps its colour", !(await ev(`document.querySelector("article.ssi-pass").classList.contains("is-inactive")`)));
  report("the page says how to share", /scan the verifier/i.test(await text()));
  for (const [w, h] of [[1440, 900], [768, 1024], [390, 844], [320, 720]]) {
    await size(w, h); await go("/wallet"); await waitText("Stored credentials"); await sleep(2200);
    await ev(`document.querySelector("article.ssi-pass").scrollIntoView({block:"center"})`); await sleep(400);
    await shot(`wallet-card-${w}`);
    const overflow = await ev("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1");
    const clipped = await ev(`(()=>{const c=document.querySelector("article.ssi-pass .ssi-pass-front");return [...c.querySelectorAll("*")].some(e=>{const r=e.getBoundingClientRect(),p=c.getBoundingClientRect();return r.width>0&&(r.right>p.right+1||r.left<p.left-1)})})()`);
    const issues = await axe();
    report(`card at ${w}px fits and passes axe`, !overflow && !clipped && issues.length === 0, issues.join("; ").slice(0, 120));
  }
  await size(1440, 900); await go("/wallet"); await waitText("Stored credentials"); await sleep(2000);

  // Keyboard: the card's controls are reachable in order and show focus
  // Focus the element just before the card, then use real Tab presses, as a keyboard user would.
  await ev(`(()=>{const all=[...document.querySelectorAll("a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex='-1'])")];const first=document.querySelector("article.ssi-pass a, article.ssi-pass button");all[all.indexOf(first)-1].focus()})()`);
  for (const type of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type, key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 });
  await sleep(150);
  const order = [];
  for (let i = 0; i < 3; i += 1) {
    order.push(await ev(`(()=>{const e=document.activeElement;const c=getComputedStyle(e);return e.textContent.trim().split(/\\s+/)[0]+"|"+(c.outlineStyle!=="none"||c.boxShadow!=="none")})()`));
    for (const type of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type, key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 });
    await sleep(120);
  }
  report("keyboard reaches Present, Attributes, Details in order with visible focus", order.map((o) => o.split("|")[0]).join(",") === "Present,Attributes,Details" && order.every((o) => o.endsWith("true")), order.join(" "));

  // Light and dark theme
  for (const theme of ["light", "dark"]) {
    await ev(`document.documentElement.setAttribute("data-bs-theme", ${JSON.stringify(theme)})`); await sleep(400);
    const issues = await axe();
    await shot(`wallet-card-${theme}`);
    report(`card passes axe in the ${theme} theme`, issues.length === 0, issues.join("; ").slice(0, 120));
  }

  // Attributes: the back face, read only
  await click("Attributes", "article.ssi-pass button"); await sleep(900);
  const back = await ev(`(document.querySelector("article.ssi-pass .ssi-pass-back")||{}).innerText||""`);
  report("Attributes shows the signed claims on the back and shares nothing", /Signed attributes/i.test(back) && /affiliation/i.test(back) && (await ev("location.pathname")) === "/wallet");
  await shot("card-attributes");
  await click("Front", "article.ssi-pass button"); await sleep(700);

  // Details
  await click("Details", "article.ssi-pass a"); await sleep(2200);
  report("Details opens the stored credential", (await ev("location.pathname")).startsWith("/wallet/credentials/") && /Attributes/i.test(await text()));
  await shot("credential-detail");

  // Present
  await go("/wallet"); await waitText("Stored credentials"); await sleep(1500);
  await click("Present", "article.ssi-pass a"); await sleep(1800);
  report("Present opens the request page with guidance", (await ev("location.pathname")) === "/wallet/scan" && /Presenting starts with the verifier/i.test(await text()));
  await shot("present-guidance");

  // The old card QR value
  await setField("Offer or request link", cred.id);
  await click("Review link", "button"); await sleep(600);
  report("pasting the old card value explains itself", /credential identifier, not a request/i.test(await text()));
  await shot("scan-old-card-value");
  await setField("Offer or request link", `https://evil.example/wallet/present?request=session_${"a".repeat(24)}`);
  await click("Review link", "button"); await sleep(600);
  report("a handoff link from another site is refused", /belongs to another site/i.test(await text()));

  // Verifier QR → wallet → consent → result
  const request = (await verifier("POST", "/api/v1/oid4vp/requests", { purpose: "WP-32 desktop check", requestedCredentialTypes: ["UniversityAffiliationCredential"], requestedFields: ["affiliation"], ttlSeconds: 600 })).data;
  report("the verifier QR is a link with an opaque handle, not a credential id", /\/wallet\/present\?request=session_/.test(request.qrPayload ?? "") && !(request.qrPayload ?? "").includes("urn:uuid"), (request.qrPayload ?? "").replace(/session_[A-Za-z0-9_-]+/, "session_<handle>"));
  await setField("Offer or request link", `${BASE}/wallet/present?request=${request.sessionId}`);
  await click("Review link", "button"); await sleep(2500);
  report("the pasted verifier link opens consent", (await ev("location.pathname")) === "/wallet/consent");
  await waitText("WP-32 desktop check");
  await shot("consent");
  report("consent shows purpose and requested fields", /affiliation/i.test(await text()));
  await ev(`[...document.querySelectorAll("main input[type=radio]")].slice(0,1).forEach(r=>{if(!r.checked)r.click()})`); await sleep(300);
  await ev(`[...document.querySelectorAll("main input[type=checkbox]")].forEach(c=>{if(!c.checked)c.click()})`); await sleep(500);
  const approve = await ev(`(()=>{const b=[...document.querySelectorAll("button")].find(x=>x.textContent.trim()==="Share credential"&&!x.disabled);if(!b)return false;b.click();return true})()`);
  report("the holder can approve", approve);
  await sleep(4500);
  await shot("presentation-result");
  const result = (await verifier("GET", `/api/v1/oid4vp/requests/${request.sessionId}`)).data;
  report("the verifier records the presentation as accepted after its checks", /ACCEPT|VERIFIED|COMPLETED/i.test(JSON.stringify(result.status ?? "") + JSON.stringify(result.verificationResult ?? "")), String(result.status));

  // Revoked: the card follows the issuer, not the stored copy
  await issuer("POST", `/api/v1/identity/credentials/${encodeURIComponent(cred.id)}/revoke`, { reason: "WP-32 check" });
  await go("/wallet"); await waitText("Stored credentials"); await sleep(2500);
  card = await cardText();
  report("after revocation the card says Revoked", /Credential status\s*Revoked/i.test(card), card.replace(/\n/g, " ").slice(0, 120));
  report("a revoked card is dimmed", await ev(`document.querySelector("article.ssi-pass").classList.contains("is-inactive")`));
  report("Present is disabled for a revoked credential, with a reason", await ev(`(()=>{const b=[...document.querySelectorAll("article.ssi-pass button")].find(x=>x.textContent.trim().startsWith("Present"));return Boolean(b&&b.disabled)})()`) && /revoked this credential\. It cannot be presented/i.test(card));
  report("trust and status stay separate: trusted issuer, revoked credential", /Trusted issuer/.test(card) && /Credential status\s*Revoked/i.test(card));
  await shot("wallet-card-revoked");

  // Status service unreachable: Unknown, never Valid
  await send("Network.setBlockedURLs", { urls: ["*/status"] });
  await go("/wallet"); await waitText("Stored credentials"); await sleep(2500);
  card = await cardText();
  report("an unreachable status check shows Unknown, not Valid", /Credential status\s*Unknown/i.test(card));
  await send("Network.setBlockedURLs", { urls: [] });

  // Untrusted issuer: trust shows separately
  await enroll(admin);
  const issuers = (await anon("GET", "/api/v1/identity/trust-registry/issuers?limit=100")).data;
  const record = issuers.find((r) => r.issuerDid === cred.issuer);
  if (record) {
    await admin("POST", `/api/v1/identity/trust-registry/issuers/${encodeURIComponent(record.id)}/suspend`, { reason: "WP-32 check" }, await stepUp(admin, "trust.registry.write", record.id));
    await go("/wallet"); await waitText("Stored credentials"); await sleep(2500);
    report("a suspended issuer is shown as suspended", /Issuer suspended/.test(await cardText()));
    await shot("wallet-card-issuer-suspended");
  } else {
    report("the issuer is in the trust registry", false, "no record found");
  }
  report("no uncaught page errors", consoleErrors === 0, String(consoleErrors));
} catch (error) {
  await shot("failure").catch(() => {});
  report("run stopped", false, String(error).slice(0, 180));
}
const failed = results.filter((r) => !r.pass).length;
writeFileSync(`${DIR}card_results.json`, JSON.stringify(results, null, 1));
console.log(`\nTOTAL pass=${results.length - failed} fail=${failed}`);
edge.kill();
process.exit(failed ? 1 : 0);
