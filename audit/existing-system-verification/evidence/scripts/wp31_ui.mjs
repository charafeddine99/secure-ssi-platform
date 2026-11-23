// Every Security intelligence view at desktop and 390 px: real sign-in, real API data,
// axe, console, overflow, and on-screen numbers compared with the API.
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fixturePass, sleep } from "./wp31_lib.mjs";

const BASE = "http://localhost:29300";
const DIR = new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const SHOTS = process.argv[2];
const SCRATCH = process.env.WP31_SCRATCH;
const PORT = 9397;
mkdirSync(SHOTS, { recursive: true });
const AXE = readFileSync("C:/Users/besna/OneDrive/Bureau/secure-ssi-platform/apps/web/node_modules/axe-core/axe.min.js", "utf8");
const TABS = ["Overview", "Risk analysis", "Attack analytics", "Control coverage", "Anomalies", "Incidents", "Model and data", "Rules"];
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${join(SCRATCH, `edge-ui-${Date.now()}`)}`, "--window-size=1440,900", "--hide-scrollbars", "--no-first-run", "about:blank"], { stdio: "ignore" });
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

const results = [];
const report = (name, pass, note = "") => { results.push({ name, pass, note }); console.log(`${pass ? "PASS" : "FAIL"} ${name}${note ? ` | ${note}` : ""}`); };
const clickTab = (label) => ev(`(()=>{const b=[...document.querySelectorAll('[role=tab]')].find(x=>x.textContent.trim()===${JSON.stringify(label)});b.click();return Boolean(b)})()`);
const text = () => ev("document.body.innerText");
const api = (path) => ev(`fetch(${JSON.stringify(`/api/v1/fraud/intel/${path}`)},{headers:{"X-SSI-Client":"web",Accept:"application/json"}}).then(r=>r.json())`);

await send("Page.navigate", { url: `${BASE}/login` }); await sleep(1500);
await ev(`(()=>{const set=(l,v)=>{const lab=[...document.querySelectorAll("label")].find(x=>x.textContent.trim().startsWith(l));const i=document.getElementById(lab.htmlFor);Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(i,v);i.dispatchEvent(new Event("input",{bubbles:true}))};set("Username","admin@example.test");set("Password",${JSON.stringify(fixturePass("ADMIN"))});document.querySelector("form button[type=submit]").click()})()`);
for (let i = 0; i < 40; i += 1) { await sleep(250); if ((await ev("location.pathname")) !== "/login") break; }

let n = 0;
const axeRows = [];
for (const [width, height] of [[1440, 900], [390, 844]]) {
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 700 });
  await send("Page.navigate", { url: `${BASE}/admin/intelligence` });
  await sleep(2500);
  for (const tab of TABS) {
    errors = [];
    await clickTab(tab);
    await sleep(2200);
    const body = await text();
    const overflow = await ev("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1");
    await ev(AXE + ";0");
    const axe = JSON.parse(await ev(`axe.run(document,{runOnly:["wcag2a","wcag2aa","wcag21a","wcag21aa","wcag22aa"]}).then(r=>JSON.stringify(r.violations.map(v=>({id:v.id,n:v.nodes.length,sample:v.nodes[0].target.join(" ")}))))`));
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    n += 1;
    const file = `${String(n).padStart(2, "0")}-${tab.toLowerCase().replace(/\W+/g, "-")}-${width}.png`;
    writeFileSync(join(SHOTS, file), Buffer.from(data, "base64"));
    const count = axe.reduce((s, v) => s + v.n, 0);
    axeRows.push({ tab, width, axe: count, sample: axe[0] ? `${axe[0].id} ${axe[0].sample}` : "", overflow, console: errors.length, file });
    report(`${tab} at ${width}: no axe issue, overflow or console error`, count === 0 && !overflow && errors.length === 0, count ? axe[0].sample.slice(0, 90) : errors[0] ?? "");
    report(`${tab} at ${width}: labelled as synthetic`, body.includes("Synthetic test data"));
    if (width === 1440) {
      if (tab === "Attack analytics") {
        const m = await api("metrics?hours=24");
        const rate = m.rates.find((r) => r.name === "Sign-in failure rate");
        report("Attack analytics shows the API numerator and denominator", body.includes(String(rate.numerator)) && body.includes(String(rate.denominator)) && rate.denominator > 0, `${rate.numerator}/${rate.denominator}`);
        report("Attack analytics separates signals from confirmed incidents", /raw signals/i.test(body) && /confirmed incidents/i.test(body));
      }
      if (tab === "Control coverage") {
        const p = await api("posture");
        report("Coverage shows the API percentage", body.includes(`${p.verified_control_coverage.percent}%`), `${p.verified_control_coverage.numerator}/${p.verified_control_coverage.denominator}`);
        report("Coverage says it is not a security score", body.includes("This is not a security score"));
        report("Coverage keeps open high findings visible", body.includes("Open critical and high findings") && p.open_findings.critical_and_high.every((f) => body.includes(f.id)));
      }
      if (tab === "Model and data") report("Model view says no trained model and gives no metrics", /Not Trained/i.test(body) && body.includes("no figure is shown"));
      if (tab === "Anomalies") report("Anomaly view shows the method and baseline state", body.includes("median-mad-hourly-1.0") && /Insufficient Baseline|Normal|Anomaly/i.test(body));
      if (tab === "Incidents") report("Incidents show status history", body.includes("threshold reached"));
    }
  }
}
// A real transition through the UI
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: `${BASE}/admin/intelligence` }); await sleep(2500);
await clickTab("Incidents"); await sleep(2200);
const before = (await api("incidents?limit=200")).items.filter((i) => i.status === "TRIAGED").length;
await ev(`(()=>{const card=[...document.querySelectorAll("article")].find(a=>a.querySelector("select")&&[...a.querySelector("select").options].some(o=>o.value==="TRIAGED"));const sel=card.querySelector("select");Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,"value").set.call(sel,"TRIAGED");sel.dispatchEvent(new Event("change",{bubbles:true}));const i=card.querySelector("input");Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(i,"Reviewed in the browser test");i.dispatchEvent(new Event("input",{bubbles:true}))})()`);
await sleep(300);
await ev(`[...document.querySelectorAll("article button")].find(b=>b.textContent.trim()==="Save"&&!b.disabled).click()`);
await sleep(2000);
const after = (await api("incidents?limit=200")).items.filter((i) => i.status === "TRIAGED").length;
report("An incident is triaged through the page", after === before + 1, `${before} to ${after}`);

writeFileSync(`${DIR}ui_results.json`, JSON.stringify(axeRows, null, 1));
const failed = results.filter((r) => !r.pass).length;
console.log(`\nTOTAL pass=${results.length - failed} fail=${failed}`);
edge.kill();
process.exit(failed ? 1 : 0);
