// Read-only probe of a headless Edge page through DevTools: reports the page state, changes nothing.
const port = process.argv[2];
const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener("open", resolve, { once: true }); ws.addEventListener("error", reject, { once: true }); });
let id = 0;
const pending = new Map();
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise((resolve) => { id += 1; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const evaluate = async (expression) => {
  const timer = new Promise((resolve) => setTimeout(() => resolve({ timeout: true }), 5000));
  const m = await Promise.race([send("Runtime.evaluate", { expression, returnByValue: true }), timer]);
  return m.timeout ? "<no answer in 5 s>" : (m.result?.result?.value ?? m.result?.exceptionDetails?.text ?? m.error?.message);
};
console.log("url:", page.url);
console.log("readyState:", await evaluate("document.readyState"));
console.log("tabs:", await evaluate("JSON.stringify([...document.querySelectorAll('[role=tab]')].map(t => t.textContent.trim() + (t.getAttribute('aria-selected') === 'true' ? '*' : '')))"));
console.log("axe injected:", await evaluate("typeof window.axe"));
console.log("visibility:", await evaluate("document.visibilityState"));
console.log("body length:", await evaluate("document.body.innerText.length"));
console.log("first text:", await evaluate("document.body.innerText.slice(0, 160).replace(/\\s+/g, ' ')"));
const timer = new Promise((resolve) => setTimeout(() => resolve({ timeout: true }), 8000));
const shot = await Promise.race([send("Page.captureScreenshot", { format: "png" }), timer]);
console.log("screenshot from a second client:", shot.timeout ? "NO ANSWER in 8 s" : (shot.result?.data ? `ok (${shot.result.data.length} b64 chars)` : JSON.stringify(shot.error)));
ws.close();
process.exit(0);
