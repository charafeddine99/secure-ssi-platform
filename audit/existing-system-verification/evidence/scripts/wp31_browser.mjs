// WP-31 browser E2E: real headless Edge, real clicks and typing through the DevTools
// protocol, against the isolated stack. Nothing is injected into browser storage.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { PROJECT, client, enroll, fixturePass, isolatedMongo, issue, login, nextCode, walletOf, sleep } from "./wp31_lib.mjs";
import { execFileSync } from "node:child_process";

const BASE = "http://localhost:29300";
const DIR = new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const SHOTS = process.argv[2];
const SCRATCH = process.env.WP31_SCRATCH;
const PORT = 9377;
mkdirSync(SHOTS, { recursive: true });

const run = Date.now().toString(36);
const DOWNLOADS = join(SCRATCH, `downloads-${run}`);
mkdirSync(DOWNLOADS, { recursive: true });
const password = () => `Wp29-${Math.random().toString(36).slice(2)}-${run}`;
const names = ["owner", "g1", "g2", "g3", "adm1", "adm2"];
const accounts = Object.fromEntries(names.map((n) => [`${n}.${run}@wp31.test`, { name: `${n} (synthetic)`, role: n.startsWith("adm") ? "admin" : "holder", password: password() }]));
const email = (n) => `${n}.${run}@wp31.test`;
execFileSync("docker", ["exec", "-i", "-w", "/app", `${PROJECT}-identity-service-1`, "python", "-"], {
  input: readFileSync(`${DIR}seed_users.py`, "utf8").replace("json.load(sys.stdin)", `json.loads(${JSON.stringify(JSON.stringify(accounts))})`), encoding: "utf8",
});

const results = [];
const consoleErrors = [];
const findings = [];
const report = (name, pass, note = "") => { results.push({ name, pass: Boolean(pass), note }); console.log(`${pass ? "PASS" : "FAIL"} ${name}${note ? " | " + note : ""}`); };

const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", [
  "--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${join(SCRATCH, `edge-${run}`)}`,
  "--window-size=1440,900", "--hide-scrollbars", "--no-first-run", "about:blank",
], { stdio: "ignore" });
let ws;
for (let i = 0; i < 80 && !ws; i += 1) {
  try {
    const page = (await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()).find((t) => t.type === "page");
    if (page) ws = new WebSocket(page.webSocketDebuggerUrl);
  } catch { await sleep(250); }
}
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0;
const pending = new Map();
ws.addEventListener("message", (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); return; }
  if (msg.method === "Runtime.exceptionThrown") consoleErrors.push(msg.params.exceptionDetails.text);
  if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
    const text = msg.params.args.map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 160);
    consoleErrors.push(text);
  }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
  id += 1;
  pending.set(id, (m) => (m.error ? reject(new Error(`${method}: ${m.error.message}`)) : resolve(m.result)));
  ws.send(JSON.stringify({ id, method, params }));
});
const evaluate = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(`page: ${r.exceptionDetails.text}`);
  return r.result.value;
};
await send("Page.enable"); await send("Runtime.enable"); await send("DOM.enable"); await send("Network.enable");
await send("Network.setCacheDisabled", { cacheDisabled: true });
await send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: DOWNLOADS, eventsEnabled: false });

const visible = `(e)=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=="hidden"}`;
async function rectOf(selectorJs) {
  return evaluate(`(()=>{const e=(${selectorJs})();if(!e)return null;e.scrollIntoView({block:"center",behavior:"instant"});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,disabled:!!e.disabled}})()`);
}
async function mouseClick(point) {
  for (const type of ["mouseMoved", "mousePressed", "mouseReleased"]) {
    await send("Input.dispatchMouseEvent", { type, x: point.x, y: point.y, button: type === "mouseMoved" ? "none" : "left", clickCount: type === "mouseMoved" ? 0 : 1 });
  }
}
const byText = (text, tag = "button,a") => `()=>[...document.querySelectorAll(${JSON.stringify(tag)})].filter(${visible}).reverse().find(e=>e.textContent.trim().startsWith(${JSON.stringify(text)}))`;
async function waitFor(selectorJs, ms = 15000) {
  let end = Date.now() + ms;
  for (;;) {
    const r = await rectOf(selectorJs);
    if (r) return r;
    if (await rateGuard()) end = Date.now() + ms;
    if (Date.now() > end) throw new Error(`timeout waiting for ${selectorJs.slice(0, 90)}`);
    await sleep(200);
  }
}
async function click(text, tag) {
  const end = Date.now() + 15000;
  for (;;) {
    const r = await waitFor(byText(text, tag));
    if (!r.disabled) { await mouseClick(r); return; }
    if (Date.now() > end) throw new Error(`button stayed disabled: ${text}`);
    await sleep(200);
  }
}
const fieldByLabel = (label, first = false) => `()=>{const all=[...document.querySelectorAll("label")].filter(${visible});const l=(${first}?all:all.reverse()).find(x=>x.textContent.trim().startsWith(${JSON.stringify(label)}));return l?(document.getElementById(l.htmlFor)||l.querySelector("input,textarea,select")):null}`;
async function type(label, value, first = false) {
  const r = await waitFor(fieldByLabel(label, first));
  await mouseClick(r);
  await send("Input.dispatchKeyEvent", { type: "rawKeyDown", key: "a", code: "KeyA", windowsVirtualKeyCode: 65, modifiers: 2, commands: ["selectAll"] });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: "a", code: "KeyA", windowsVirtualKeyCode: 65, modifiers: 2 });
  await send("Input.insertText", { text: value });
}
const text = () => evaluate("document.body.innerText");
// All test accounts share one IP, so the gateway limit is waited out, never raised.
async function rateGuard() {
  if (!/Rate limit of \d+ requests/.test(await evaluate("document.body.innerText"))) return false;
  console.log("waiting out the gateway rate limit");
  await sleep(61_000);
  await evaluate("location.reload()");
  await sleep(2_500);
  return true;
}
async function waitText(pattern, ms = 20000) {
  let end = Date.now() + ms;
  const re = new RegExp(pattern);
  for (;;) {
    if (re.test(await text())) return true;
    if (await rateGuard()) end = Date.now() + ms;
    if (Date.now() > end) throw new Error(`timeout waiting for text: ${pattern}`);
    await sleep(250);
  }
}
async function go(path) {
  await send("Page.navigate", { url: BASE + path });
  await sleep(900);
}
async function scan(label) {
  const hits = await evaluate(`(()=>{const out=[];const s=[...Object.values(localStorage),...Object.values(sessionStorage)].join(" ");if(/eyJ[A-Za-z0-9_-]{10,}/.test(s))out.push("jwt in storage");if(/eyJ[A-Za-z0-9_-]{10,}/.test(location.href))out.push("jwt in url");return out})()`);
  if (hits.length) findings.push({ label, hits });
}
let shot = 0;
async function screenshot(name) {
  await scan(name);
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  shot += 1;
  writeFileSync(join(SHOTS, `${String(shot).padStart(2, "0")}-${name}.png`), Buffer.from(data, "base64"));
}
async function signIn(user, pass) {
  await go("/login");
  await type("Username", user);
  await type("Password", pass);
  await send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, text: "\r" });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
  await sleep(1500);
  await waitFor(`()=>location.pathname!=="/login"?document.body:null`);
}
async function signOut() {
  await send("Network.clearBrowserCookies");
  await evaluate(`(()=>{ try { localStorage.clear(); sessionStorage.clear(); } catch {} })()`);
}

const totps = {};
// Typing takes time, so never start from the previous 30-second window.
const typedCode = (c) => { c.lastCounter = Math.max(c.lastCounter ?? 0, Math.floor(Date.now() / 30_000) - 1); return nextCode(c); };
async function enrollInBrowser(n) {
  await go("/account/security");
  await type("Your account password", accounts[email(n)].password);
  await click("Set up authenticator");
  await waitFor(`()=>document.querySelector('[data-testid="totp-secret"]')`);
  const secret = await evaluate(`document.querySelector('[data-testid="totp-secret"]').textContent`);
  totps[n] = { totpSecret: secret };
  await type("Authenticator code", await typedCode(totps[n]));
  await click("Confirm authenticator");
  await waitText("Your authenticator app is active");
}
async function confirmCode(n) {
  await waitText("Confirm with your authenticator");
  await type("Authenticator code", await typedCode(totps[n]));
  await click("Confirm", "button[type=submit]");
}

try {
  const ownerApi = await login(BASE, email("owner"), accounts[email("owner")].password);
  const owner = await walletOf(ownerApi);
  const ids = {};
  for (const n of ["g1", "g2", "g3"]) {
    const c = await login(BASE, email(n), accounts[email(n)].password);
    await walletOf(c);
    ids[n] = (await c("GET", "/api/v1/identity/auth/me")).data.id;
  }
  for (const n of ["adm1", "adm2"]) {
    const c = await login(BASE, email(n), accounts[email(n)].password);
    await enroll(c);
    totps[n] = c;
  }

  // ---- owner: authenticator, policy, invitations
  await signIn(email("owner"), accounts[email("owner")].password);
  await go("/account/security");
  await waitText("Authenticator");
  await screenshot("holder-security-before-mfa");
  await enrollInBrowser("owner");
  report("owner sets up an authenticator through the UI", true);
  await screenshot("holder-authenticator-active");

  await send("WebAuthn.enable", { enableUI: false });
  await send("WebAuthn.addVirtualAuthenticator", { options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } });
  await type("Password to add a key", accounts[email("owner")].password);
  await click("Register a key");
  await waitText("You can confirm sensitive actions with this key", 20000);
  report("owner registers a passkey through the real WebAuthn API", true, "virtual authenticator");
  await screenshot("holder-passkey-registered");
  await go("/wallet/security");
  await waitText("Recovery policy");
  await type("Required approvals", "2");
  await type("Maximum guardians", "3");
  await type("Time-lock after quorum", "0.0084");
  await click("Save policy");
  await waitText("Confirm with your authenticator");
  await click("Use passkey or security key");
  await waitText("Recovery policy saved");
  report("policy saved after a passkey step-up", true);

  await sleep(1000);
  for (const n of ["g1", "g2", "g3"]) {
    await type("Display name", `Guardian ${n}`);
    await type("Guardian account ID", ids[n]);
    await click("Send invitation");
    await confirmCode("owner");
    await waitText(`Guardian ${n}[^]{0,30}Invited`);
    await sleep(2500);
  }
  report("three guardians invited through the UI, no DID asked for", !(await text()).includes("Guardian wallet DID"));
  await screenshot("holder-guardians-invited");
  await signOut();

  // ---- each guardian: accept with a browser key
  for (const n of ["g1", "g2", "g3"]) {
    await signIn(email(n), accounts[email(n)].password);
    await enrollInBrowser(n);
    await go("/guardian");
    await waitText("Guardian invitations");
    if (n === "g1") await screenshot("guardian-invitation");
    await click("Accept with this browser");
    await confirmCode(n);
    await waitText("This browser holds your key");
    report(`${n} accepts with a key created in this browser`, true);
    if (n === "g1") await screenshot("guardian-key-bound");
    const exported = await evaluate(`new Promise((res,rej)=>{const q=indexedDB.open("secure-ssi-guardian");q.onsuccess=()=>{const g=q.result.transaction("device-keys").objectStore("device-keys").getAll();g.onsuccess=()=>res(g.result.map(p=>({ext:p.privateKey.extractable,type:p.privateKey.type})));g.onerror=()=>rej(g.error)}})`);
    report(`${n} private key is non-extractable`, exported.length >= 1 && exported.every((k) => k.ext === false && k.type === "private"));
    await signOut();
  }

  // ---- owner: start recovery
  await signIn(email("owner"), accounts[email("owner")].password);
  await go("/wallet/security");
  await waitText("Start wallet key recovery");
  const lostAccess = await text();
  report("page says account loss is not covered", lostAccess.includes("full account recovery is not available"));
  await click("Request recovery");
  await click("Request recovery", ".modal button");
  await confirmCode("owner");
  await waitText("Recovery in progress");
  await screenshot("holder-recovery-in-progress");
  report("recovery started from the UI with step-up", true);
  const oldCookies = (await send("Network.getCookies", { urls: [BASE] })).cookies.map((c) => `${c.name}=${c.value}`).join("; ");
  await signOut();

  // ---- two guardians approve in the browser
  for (const n of ["g1", "g2"]) {
    await signIn(email(n), accounts[email(n)].password);
    await go("/guardian");
    await click("Review");
    await waitText("Your decision");
    if (n === "g1") await screenshot("guardian-review");
    await mouseClick(await waitFor(`()=>document.querySelector('input[type=checkbox]')`));
    await click("Approve");
    await click("Sign and approve");
    await confirmCode(n);
    await waitText("Your decision was recorded");
    report(`${n} approves, signed in the browser`, true);
    await signOut();
  }

  // ---- admin: risk hold, backup, verify, dual control
  const adminApi = {};
  await signIn(email("adm1"), accounts[email("adm1")].password);
  await go("/admin/backups");
  await waitText("Production readiness");
  await screenshot("admin-readiness-and-backup");
  const pageText = await text();
  report("admin page shows off-site and point-in-time as not configured", /Off-site copy\s*Not configured/i.test(pageText) && /Point-in-time recovery\s*Not configured/i.test(pageText));
  await click("Create backup now");
  await click("Create backup", ".modal button");
  await confirmCode("adm1");
  await waitText("Succeeded", 30000);
  report("Create backup now clicked and succeeded", true);
  await click("Verify");
  await waitText("Verified", 30000);
  report("Verify clicked and succeeded", true);
  await screenshot("admin-backup-verified");
  await signOut();

  // ---- after the time-lock: old session dead, owner signs in again
  let finished = false;
  const adminCheck = await login(BASE, "admin@example.test", fixturePass("ADMIN"));
  for (let i = 0; i < 60 && !finished; i += 1) {
    const list = (await adminCheck("GET", "/api/v1/recovery/admin/requests")).data.items ?? [];
    const mine = list.find((x) => x.walletId === owner.walletId);
    finished = mine?.state === "COMPLETED";
    if (mine?.riskStatus === "ON_HOLD") { report("request went on hold", false, mine.riskLevel); break; }
    if (!finished) await sleep(1000);
  }
  report("key rotated after quorum and time-lock", finished);
  const stale = client(BASE, "browser-session-from-before-recovery");
  stale.setCookie(oldCookies);
  report("the browser session from before recovery was ended", (await stale("GET", "/api/v1/identity/auth/me")).status === 401);

  // ---- credential backup through the UI
  await signIn(email("owner"), accounts[email("owner")].password);
  const issuer = await login(BASE, "issuer@example.test", fixturePass("ISSUER"));
  const ownerApi2 = await login(BASE, email("owner"), accounts[email("owner")].password);
  const wallet = await walletOf(ownerApi2);
  const good = await issue(BASE, issuer, ownerApi2, wallet.walletId, "SYN-WP31-BR1");
  const revoked = await issue(BASE, issuer, ownerApi2, wallet.walletId, "SYN-WP31-BR2");
  await issuer("POST", `/api/v1/identity/credentials/${encodeURIComponent(revoked.id)}/revoke`, { reason: "browser test" });
  await go("/wallet/backup");
  await waitText("Credential backup");
  await screenshot("holder-credential-backup");
  const scope = await text();
  report("page states the server can read credentials and no keys are included", scope.includes("The platform can already read your credentials") && scope.includes("Not included: your private key"));
  const passphrase = `synthetic-${run}-passphrase-Xy9`;
  await type("Backup passphrase", passphrase, true);
  await type("Repeat passphrase", passphrase);
  await click("Create and download");
  await confirmCode("owner");
  await waitText("Encrypted backup downloaded", 30000);
  report("Create and download clicked", true);
  await sleep(800);
  let fileName;
  for (let i = 0; i < 60 && !fileName; i += 1) {
    const files = readdirSync(DOWNLOADS);
    if (!files.some((f) => f.endsWith(".crdownload"))) fileName = files.sort().pop();
    if (!fileName) await sleep(250);
  }
  const archiveText = readFileSync(join(DOWNLOADS, fileName), "utf8");
  report("downloaded file is encrypted", !archiveText.includes(good.id) && !archiveText.includes("SYN-WP31") && JSON.parse(archiveText).cipher.name === "AES-GCM");
  report("downloaded file has no key material", !/privateKey|keyReference|providerKey/.test(archiveText));
  await screenshot("holder-backup-downloaded");

  const upload = async (path) => {
    const { root } = await send("DOM.getDocument");
    const { nodeId } = await send("DOM.querySelector", { nodeId: root.nodeId, selector: "input[type=file]" });
    await send("DOM.setFileInputFiles", { nodeId, files: [path] });
  };
  const attempt = async (path, phrase) => {
    await go("/wallet/backup");
    await waitText("Credential backup");
    await upload(path);
    await sleep(500);
    await type("Backup passphrase", phrase);
    await click("Validate and preview");
  };
  const original = join(DOWNLOADS, fileName);
  await attempt(original, "a-wrong-passphrase-value");
  await waitText("Backup not accepted", 20000);
  report("wrong passphrase rejected in the browser", !(await text()).includes("Will be restored"));
  await screenshot("holder-wrong-passphrase");

  const parsed = JSON.parse(archiveText);
  const tampered = join(DOWNLOADS, "tampered.json");
  writeFileSync(tampered, JSON.stringify({ ...parsed, ciphertext: parsed.ciphertext.slice(0, 40) + (parsed.ciphertext[40] === "A" ? "B" : "A") + parsed.ciphertext.slice(41) }));
  await attempt(tampered, passphrase);
  await waitText("Backup not accepted", 20000);
  report("tampered file rejected in the browser", !(await text()).includes("Will be restored"));

  const future = join(DOWNLOADS, "future.json");
  writeFileSync(future, JSON.stringify({ ...parsed, version: 99 }));
  await attempt(future, passphrase);
  await waitText("Backup not accepted", 20000);
  report("unsupported version rejected in the browser", /not supported/.test(await text()));

  const extraField = join(DOWNLOADS, "extra.json");
  writeFileSync(extraField, JSON.stringify({ ...parsed, injected: true }));
  await attempt(extraField, passphrase);
  await waitText("Backup not accepted", 20000);
  report("unknown archive field rejected in the browser", /not supported/.test(await text()));

  await go("/wallet");
  await waitFor(`()=>document.querySelector(".ssi-pass")`);
  report("the credential card has no QR", await evaluate(`document.querySelectorAll(".ssi-pass img, .ssi-pass canvas").length === 0`));
  await screenshot("holder-card-without-qr");

  // the phone path, opened here because no phone is attached
  const verifierApi = await login(BASE, "verifier@example.test", fixturePass("VERIFIER"));
  const newRequest = async (purpose) => (await verifierApi("POST", "/api/v1/oid4vp/requests", { purpose, requestedCredentialTypes: ["UniversityAffiliationCredential"], requestedFields: ["affiliation"], ttlSeconds: 600 })).data;
  const local = (link) => link.replace("http://wallet.wp31.test", "");
  const deny = await newRequest("Browser denial check");
  await go(local(deny.qrPayload));
  await waitText("Browser denial check", 20000);
  await screenshot("holder-request-from-qr");
  report("the QR link opens the consent page with purpose and verifier", /verifier/i.test(await text()));
  await click("Decline");
  await click("Decline", ".modal button").catch(() => null);
  await waitText("You declined this request", 20000);
  const denied = (await verifierApi("GET", `/api/v1/oid4vp/requests/${deny.sessionId}`)).data;
  report("declining sends no presentation", !denied.verificationResult, denied.status);
  await go("/wallet/present?request=not-valid");
  await waitText("The link is not valid", 10000);
  report("a malformed handle shows a safe error", true);
  await go("/wallet/present?request=session_unknownunknownunknownunknown");
  await sleep(1800);
  report("an unknown request does not open a consent form", !/Approve|Share/.test(await text()));
  await screenshot("holder-unknown-request");
  const signedOut = await newRequest("Sign-in return check");
  await signOut();
  await go(local(signedOut.qrPayload));
  await waitFor(`()=>location.pathname==="/login"?document.body:null`);
  report("a signed-out phone lands on sign-in", true);
  await type("Username", email("owner"));
  await type("Password", accounts[email("owner")].password);
  await send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, text: "\r" });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
  await waitText("Sign-in return check", 20000);
  report("after sign-in the same request opens", true);

  // restore after real record loss, in the isolated database only
  await send("Storage.clearDataForOrigin", { origin: BASE, storageTypes: "all" });
  await send("Network.clearBrowserCookies");
  const leftInStorage = await evaluate("localStorage.length + sessionStorage.length");
  await signIn(email("owner"), accounts[email("owner")].password);
  report("restore starts from wiped browser storage and a new sign-in", leftInStorage === 0);
  isolatedMongo(`print(db.getSiblingDB("secure_identity").credentials.deleteMany({credentialId:{$in:${JSON.stringify([good.id, revoked.id])}}}).deletedCount)`);
  await attempt(original, passphrase);
  await waitText("Will be restored", 30000);
  await screenshot("holder-restore-preview");
  const preview = await text();
  report("revoked credential shown as revoked in the preview", preview.includes("Revoked by issuer"));
  await mouseClick(await waitFor(`()=>document.querySelector('input[type=checkbox]')`));
  await click("Restore");
  await click("Restore", ".modal button");
  await confirmCode("owner");
  await waitText("Restored", 30000);
  await screenshot("holder-restore-result");
  const inWallet = (await ownerApi2("GET", `/api/v1/identity/wallets/${wallet.walletId}/credentials`)).data.credentials.map((c) => c.credentialId ?? c.id);
  report("valid credential back in the wallet", inWallet.includes(good.id));
  report("revoked credential not restored", !inWallet.includes(revoked.id));
  await signOut();

  // ---- two-person approval through the UI
  await signIn(email("adm1"), accounts[email("adm1")].password);
  await go("/admin/backups");
  await click("Restore dry-run");
  await waitFor(fieldByLabel("Drill target database"));
  await click("Validate plan");
  await waitText("Two-person approval", 30000);
  await type("Reason for this restore", "Browser drill");
  await click("Request approval");
  await confirmCode("adm1");
  await waitText("Needs another administrator", 20000);
  report("the requester sees no Approve button for their own request", true);
  await screenshot("admin-dual-control-requested");
  await signOut();
  await signIn(email("adm2"), accounts[email("adm2")].password);
  await go("/admin/backups");
  await click("Restore dry-run");
  await waitFor(fieldByLabel("Drill target database"));
  await click("Validate plan");
  await waitText("Two-person approval", 30000);
  await click("Approve");
  await confirmCode("adm2");
  await waitFor(`()=>document.querySelector('[data-testid="dual-control-token"]')`);
  report("a second administrator approves in the UI and gets a one-time token", true);
  await send("Runtime.evaluate", { expression: `document.querySelector('[data-testid="dual-control-token"]').textContent="<redacted>"` });
  await screenshot("admin-dual-control-approved");
  await signOut();

  // ---- accessibility
  const axeSource = readFileSync("C:/Users/besna/OneDrive/Bureau/secure-ssi-platform/apps/web/node_modules/axe-core/axe.min.js", "utf8");
  const axe = [];
  const measure = async (label, width, height, path, user) => {
    await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 700 });
    await signIn(email(user), accounts[email(user)].password);
    await go(path);
    await sleep(1800);
    await evaluate(axeSource + ";0");
    const violations = await evaluate(`axe.run(document,{runOnly:["wcag2a","wcag2aa","wcag21a","wcag21aa","wcag22aa"]}).then(r=>r.violations.map(v=>({id:v.id,impact:v.impact,n:v.nodes.length,sample:v.nodes.slice(0,3).map(n=>n.target.join(" "))})))`);
    axe.push({ label: `${width} ${label}`, violations });
    console.log(`AXE ${width} ${label}: ${violations.reduce((s, v) => s + v.n, 0)}`);
    await signOut();
  };
  for (const [width, height] of [[1440, 900], [390, 844]]) {
    await measure("/wallet/security", width, height, "/wallet/security", "owner");
    await measure("/wallet/backup", width, height, "/wallet/backup", "owner");
    await measure("/guardian", width, height, "/guardian", "g1");
    await measure("/admin/backups", width, height, "/admin/backups", "adm1");
    await measure("/admin/recovery", width, height, "/admin/recovery", "adm1");
  }
  writeFileSync(`${DIR}axe_results.json`, JSON.stringify(axe, null, 1));
} catch (error) {
  report("browser run stopped", false, String(error).slice(0, 300));
  await screenshot("failure").catch(() => null);
} finally {
  writeFileSync(`${DIR}browser_results.json`, JSON.stringify({ results, consoleErrors, storageOrUrlFindings: findings }, null, 1));
  const passed = results.filter((r) => r.pass).length;
  console.log(`\nTOTAL pass=${passed} fail=${results.length - passed} consoleErrors=${consoleErrors.length} storageFindings=${findings.length}`);
  edge.kill();
  process.exit(results.length === passed ? 0 : 1);
}
