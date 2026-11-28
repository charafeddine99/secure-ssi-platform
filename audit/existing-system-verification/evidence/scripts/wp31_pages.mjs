// Every route, per role, at desktop and 390 px: real sign-in, screenshot, console and axe.
// Isolated wp31 stack only.
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fixturePass, sleep } from "./wp31_lib.mjs";

const BASE = "http://localhost:29300";
const DIR = new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const SHOTS = process.argv[2];
const SCRATCH = process.env.WP31_SCRATCH;
const PORT = 9387;
mkdirSync(SHOTS, { recursive: true });
const AXE = readFileSync("C:/Users/besna/OneDrive/Bureau/secure-ssi-platform/apps/web/node_modules/axe-core/axe.min.js", "utf8");
const ROLES = {
  PUBLIC: { pages: ["/", "/ecosystem", "/docs", "/login", "/register", "/does-not-exist"] },
  HOLDER: { user: "holder@example.test", pages: ["/wallet", "/wallet/scan", "/wallet/security", "/wallet/backup", "/wallet/activity", "/wallet/consent", "/guardian", "/guardian/requests"] },
  ISSUER: { user: "issuer@example.test", pages: ["/issuer", "/issuer/templates", "/issuer/issue", "/issuer/revocations"] },
  VERIFIER: { user: "verifier@example.test", pages: ["/verifier", "/verifier/request", "/verifier/verify", "/verifier/history"] },
  ADMIN: { user: "admin@example.test", pages: ["/admin", "/admin/users", "/admin/trust-registry", "/admin/contracts", "/admin/audit", "/admin/recovery", "/admin/backups", "/admin/intelligence", "/account/security"] },
};
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${join(SCRATCH, `edge-pages-${Date.now()}`)}`, "--window-size=1440,900", "--hide-scrollbars", "--no-first-run", "about:blank"], { stdio: "ignore" });
let ws;
for (let i = 0; i < 80 && !ws; i += 1) {
  try { const page = (await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()).find((t) => t.type === "page"); if (page) ws = new WebSocket(page.webSocketDebuggerUrl); } catch { await sleep(250); }
}
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0; const pending = new Map(); let errors = [];
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.text);
  if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") errors.push(m.params.args.map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 140));
});
const send = (method, params = {}) => new Promise((res, rej) => { id += 1; pending.set(id, (m) => (m.error ? rej(new Error(m.error.message)) : res(m.result))); ws.send(JSON.stringify({ id, method, params })); });
const ev = async (expression) => (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result.value;
await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable"); await send("Network.setCacheDisabled", { cacheDisabled: true });

async function signIn(user, password) {
  await send("Network.clearBrowserCookies");
  await send("Page.navigate", { url: `${BASE}/login` }); await sleep(1200);
  await ev(`(()=>{const set=(l,v)=>{const lab=[...document.querySelectorAll("label")].find(x=>x.textContent.trim().startsWith(l));const i=document.getElementById(lab.htmlFor);Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(i,v);i.dispatchEvent(new Event("input",{bubbles:true}))};set("Username",${JSON.stringify(user)});set("Password",${JSON.stringify(password)});document.querySelector("form button[type=submit]").click()})()`);
  for (let i = 0; i < 40; i += 1) { await sleep(250); if ((await ev("location.pathname")) !== "/login") return; }
  throw new Error(`sign-in failed for ${user}`);
}
// Keyboard: real key events on sign-in. Automated; a person with a screen reader was not involved.
const tab = async (shift = false) => { for (const type of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type, key: "Tab", code: "Tab", windowsVirtualKeyCode: 9, modifiers: shift ? 8 : 0 }); await sleep(60); };
const focused = `(()=>{const e=document.activeElement;const c=getComputedStyle(e);return JSON.stringify({tag:e.tagName,label:(e.getAttribute("aria-label")||e.textContent||e.name||e.id||"").trim().slice(0,40),visible:c.outlineStyle!=="none"&&c.outlineWidth!=="0px"||c.boxShadow!=="none"})})()`;
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Network.clearBrowserCookies");
await send("Page.navigate", { url: `${BASE}/login` }); await sleep(1500);
const keyboard = [];
for (let i = 0; i < 12; i += 1) { await tab(); keyboard.push(JSON.parse(await ev(focused))); }
writeFileSync(`${DIR}keyboard_results.json`, JSON.stringify(keyboard, null, 1));
const reached = keyboard.filter((k) => k.tag !== "BODY");
console.log(`KEYBOARD stops=${reached.length} withoutVisibleFocus=${reached.filter((k) => !k.visible).length} reachedSubmit=${keyboard.some((k) => k.tag === "BUTTON" && /sign in/i.test(k.label))}`);

const rows = [];
let n = 0;
for (const [width, height] of [[1440, 900], [390, 844]]) {
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 700 });
  for (const [role, spec] of Object.entries(ROLES)) {
    if (spec.user) await signIn(spec.user, fixturePass(role)); else { await send("Network.clearBrowserCookies"); await ev("try{localStorage.clear()}catch{}"); }
    for (const path of spec.pages) {
      errors = [];
      await send("Page.navigate", { url: BASE + path });
      await sleep(1700);
      if (/Rate limit of \d+ requests/.test(await ev("document.body.innerText"))) { console.log(`waiting out the rate limit on ${path}`); await sleep(61_000); errors = []; await send("Page.navigate", { url: BASE + path }); await sleep(2500); }
      const final = await ev("location.pathname");
      const body = await ev("document.body.innerText.length");
      const overflow = await ev("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1");
      await ev(AXE + ";0");
      const axe = JSON.parse(await ev(`axe.run(document,{runOnly:["wcag2a","wcag2aa","wcag21a","wcag21aa","wcag22aa"]}).then(r=>JSON.stringify(r.violations.map(v=>({id:v.id,n:v.nodes.length,sample:v.nodes[0].target.join(" ")}))))`));
      const { data } = await send("Page.captureScreenshot", { format: "png" });
      n += 1;
      const file = `${String(n).padStart(3, "0")}-${role.toLowerCase()}-${path.replace(/\W+/g, "_") || "root"}-${width}.png`;
      writeFileSync(join(SHOTS, file), Buffer.from(data, "base64"));
      rows.push({ role, path, finalPath: final, viewport: width, screenshot: file, textLength: body, horizontalOverflow: overflow, consoleErrors: errors.length, consoleSample: errors[0] ?? "", axeViolations: axe.reduce((s, v) => s + v.n, 0), axeSample: axe[0] ? `${axe[0].id} ${axe[0].sample}` : "" });
      console.log(`${role} ${path} ${width} -> ${final} axe=${rows.at(-1).axeViolations} console=${errors.length} overflow=${overflow}`);
    }
  }
}
writeFileSync(`${DIR}pages_results.json`, JSON.stringify(rows, null, 1));
console.log(`\nTOTAL pages=${rows.length} axe=${rows.reduce((s, r) => s + r.axeViolations, 0)} console=${rows.reduce((s, r) => s + r.consoleErrors, 0)} overflow=${rows.filter((r) => r.horizontalOverflow).length}`);
edge.kill();
process.exit(0);
