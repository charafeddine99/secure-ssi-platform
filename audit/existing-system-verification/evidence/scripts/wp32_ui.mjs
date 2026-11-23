// Registration and account security through the real pages, by clicking.
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fixturePass, nextCode, sleep } from "./wp31_lib.mjs";

const BASE = "http://localhost:29300";
const SHOTS = process.argv[2];
const SCRATCH = process.env.WP31_SCRATCH;
const PORT = 9417;
mkdirSync(SHOTS, { recursive: true });
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${join(SCRATCH, `edge-reg-${Date.now()}`)}`, "--window-size=1440,900", "--hide-scrollbars", "--no-first-run", "about:blank"], { stdio: "ignore" });
let ws;
for (let i = 0; i < 80 && !ws; i += 1) {
  try { const page = (await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()).find((t) => t.type === "page"); if (page) ws = new WebSocket(page.webSocketDebuggerUrl); } catch { await sleep(250); }
}
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0; const pending = new Map();
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise((res, rej) => { id += 1; pending.set(id, (m) => (m.error ? rej(new Error(m.error.message)) : res(m.result))); ws.send(JSON.stringify({ id, method, params })); });
const ev = async (expression) => (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result.value;
await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
const results = [];
const report = (name, pass, note = "") => { results.push({ name, pass }); console.log(`${pass ? "PASS" : "FAIL"} ${name}${note ? ` | ${note}` : ""}`); };
const text = () => ev("document.body.innerText");
const go = async (path) => { await send("Page.navigate", { url: BASE + path }); await sleep(1800); };
const waitText = async (pattern, ms = 15000) => { const end = Date.now() + ms; const re = new RegExp(pattern, "i"); for (;;) { if (re.test(await text())) return true; if (Date.now() > end) throw new Error(`timeout: ${pattern}`); await sleep(250); } };
const setField = (label, value) => ev(`(()=>{const lab=[...document.querySelectorAll("label")].find(x=>x.textContent.trim().startsWith(${JSON.stringify(label)}));const i=document.getElementById(lab.htmlFor);const p=i.tagName==="TEXTAREA"?HTMLTextAreaElement.prototype:i.tagName==="SELECT"?HTMLSelectElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,"value").set.call(i,${JSON.stringify(value)});i.dispatchEvent(new Event(i.tagName==="SELECT"?"change":"input",{bubbles:true}))})()`);
const click = (label) => ev(`(()=>{const b=[...document.querySelectorAll("button,a")].find(x=>x.textContent.trim()===${JSON.stringify(label)}&&!x.disabled);b.click()})()`);
const shot = async (name) => { const { data } = await send("Page.captureScreenshot", { format: "png" }); writeFileSync(join(SHOTS, `${name}.png`), Buffer.from(data, "base64")); };
const signIn = async (user, password) => {
  await send("Network.clearBrowserCookies");
  await go("/login");
  await setField("Username", user); await setField("Password", password);
  await ev(`document.querySelector("form button[type=submit]").click()`);
  for (let i = 0; i < 40; i += 1) { await sleep(250); if ((await ev("location.pathname")) !== "/login") return; }
  throw new Error(`sign-in failed for ${user}`);
};

try {
  const tag = randomBytes(3).toString("hex");
  const pw = `correct horse ${randomBytes(6).toString("hex")} staple`;
  await go("/login");
  report("sign-in page offers account creation", /create an account/i.test(await text()));
  await click("Create an account"); await sleep(1500);
  report("the link opens the registration page", (await ev("location.pathname")) === "/register");
  await shot("register-holder");
  const email = `ui.holder.${tag}@wp32.test`;
  await setField("Full name", "Browser Holder"); await setField("E-mail address", email); await setField("Password", pw);
  await sleep(200); await click("Create account");
  await waitText("Request received");
  await shot("register-done");
  await signIn(email, pw);
  report("the new holder lands in the wallet", (await ev("location.pathname")).startsWith("/wallet"));
  await sleep(1500);
  await shot("new-holder-wallet");
  await go("/account/security");
  report("a holder has Account security", /Authenticator/.test(await text()) && /Password/.test(await text()));

  await send("Network.clearBrowserCookies");
  await go("/register");
  await setField("Account type", "issuer"); await sleep(300);
  await setField("Full name", "Browser Issuer"); await setField("E-mail address", `ui.issuer.${tag}@wp32.test`); await setField("Password", pw);
  await setField("Organisation", "Synthetic College"); await setField("Why you need this role", "Issue synthetic diplomas");
  await sleep(200); await shot("register-issuer"); await click("Send application");
  await waitText("waiting for an administrator");
  report("an issuer application is received", true);

  // The gap the earlier tests hid: an administrator setting up MFA through the page.
  await signIn("admin@example.test", fixturePass("ADMIN"));
  const nav = await text();
  report("the admin menu shows Account security", /Account security/.test(nav));
  await go("/account/security");
  await setField("Your account password", fixturePass("ADMIN"));
  await sleep(200); await click("Set up authenticator");
  for (let i = 0; i < 40 && !(await ev(`Boolean(document.querySelector('[data-testid="totp-secret"]'))`)); i += 1) await sleep(250);
  const secret = await ev(`document.querySelector('[data-testid="totp-secret"]').textContent`);
  const totp = { totpSecret: secret, lastCounter: Math.floor(Date.now() / 30_000) - 1 };
  await setField("Authenticator code", await nextCode(totp));
  await sleep(200); await click("Confirm authenticator");
  await waitText("Your authenticator app is active");
  report("an administrator sets up an authenticator in the page", true);
  await shot("admin-account-security");
  await go("/admin/users");
  await waitText("Synthetic College");
  await shot("admin-applications");
  report("the application appears for the administrator", true);
  await setField("Decision note", "Checked against the registry"); await sleep(200);
  await click("Approve");
  await waitText("Confirm with your authenticator");
  await setField("Authenticator code", await nextCode(totp)); await sleep(200);
  await ev(`[...document.querySelectorAll("button[type=submit]")].find(b=>b.textContent.trim()==="Confirm").click()`);
  await waitText("No applications waiting");
  report("the administrator approves through the page with step-up", true);
  await signIn(`ui.issuer.${tag}@wp32.test`, pw);
  report("the approved issuer signs in to its workspace", (await ev("location.pathname")).startsWith("/issuer"));
  await sleep(1200);
  report("the issuer has Account security", /Account security/.test(await text()));
  await signIn("verifier@example.test", fixturePass("VERIFIER"));
  report("the verifier has Account security", /Account security/.test(await text()));
} catch (error) {
  await shot("failure").catch(() => {});
  report("run stopped", false, String(error).slice(0, 160));
}
const failed = results.filter((r) => !r.pass).length;
console.log(`\nTOTAL pass=${results.length - failed} fail=${failed}`);
edge.kill();
process.exit(failed ? 1 : 0);
