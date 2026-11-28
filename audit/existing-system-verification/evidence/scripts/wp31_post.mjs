// After the security E2E: checks that real recovery, key and backup activity reached
// intelligence, then stops a source to prove a silent producer lowers coverage.
import { writeFileSync } from "node:fs";
import { PROJECT, docker, fact, fixturePass, login, results, sleep } from "./wp31_lib.mjs";

const BASE = "http://localhost:29300";
const DIR = new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const I = "/api/v1/fraud/intel";
const admin = await login(BASE, "admin@example.test", fixturePass("ADMIN"));
await sleep(12_000);
const counts = Object.fromEntries((await admin("GET", `${I}/metrics?hours=2`)).data.event_counts.map((e) => [e.event_type, e.count]));
const items = (await admin("GET", `${I}/incidents?limit=200`)).data.items;
const has = (rule) => items.some((i) => i.rule_id === rule);
console.log(JSON.stringify(counts));
console.log(items.map((i) => `${i.rule_id}:${i.status}`).join(" "));

fact("S7", "real recovery requests arrived", (counts["recovery.requested"] ?? 0) > 0, String(counts["recovery.requested"]));
fact("S7", "rejected Guardian proofs arrived", (counts["recovery.proof_rejected"] ?? 0) > 0, String(counts["recovery.proof_rejected"]));
fact("S7", "unauthorized recovery attempts arrived and opened a case", (counts["recovery.unauthorized"] ?? 0) > 0 && has("REC-02"), String(counts["recovery.unauthorized"]));
fact("S7", "risk holds arrived", (counts["recovery.risk_hold"] ?? 0) > 0, String(counts["recovery.risk_hold"]));
fact("S8", "a compromised key arrived and opened a case", (counts["key.compromised"] ?? 0) > 0 && has("KEY-01"), String(counts["key.compromised"]));
fact("S8", "key rotations arrived", (counts["key.rotation.completed"] ?? 0) > 0, String(counts["key.rotation.completed"]));
fact("S12", "wallet backup and restore arrived", (counts["wallet.backup.created"] ?? 0) > 0 && (counts["wallet.restore.completed"] ?? 0) > 0);
fact("S7", "recovery risk used platform history", (await admin("GET", `${I}/risk?hours=2`)).data.types.recovery_request > 0);

const health = (await admin("GET", `${I}/health`)).data;
console.log(JSON.stringify(health.monitoring.domains.map((d) => [d.domain, d.state])));
fact("coverage", "all three sources are healthy before the stop", health.sources.every((s) => s.state === "HEALTHY"), JSON.stringify(health.sources.map((s) => [s.source, s.state])));
const before = health.monitoring.numerator;
fact("coverage", "monitoring coverage is computed from real events", before > 0, `${before}/${health.monitoring.denominator}`);

docker("stop", `${PROJECT}-recovery-service-1`);
await sleep(195_000);
const stale = (await admin("GET", `${I}/health`)).data;
docker("start", `${PROJECT}-recovery-service-1`);
fact("S13", "a silent source becomes STALE", stale.sources.find((s) => s.source === "recovery-service").state === "STALE");
fact("S13", "overall telemetry shows DEGRADED", stale.state === "DEGRADED");
fact("S13", "monitoring coverage falls", stale.monitoring.numerator < before, `${before} to ${stale.monitoring.numerator}`);
fact("S13", "the domain is marked by its source state, not as quiet", stale.monitoring.domains.find((d) => d.domain === "Guardian recovery").state === "SOURCE_STALE");
for (let i = 0; i < 40; i += 1) { const r = await fetch("http://localhost:29383/health").catch(() => null); if (r?.ok) break; await sleep(500); }
await sleep(9_000);
fact("S13", "the source recovers", (await admin("GET", `${I}/health`)).data.sources.find((s) => s.source === "recovery-service").state === "HEALTHY");

const passed = results.filter((r) => r.pass).length;
writeFileSync(`${DIR}post_results.json`, JSON.stringify({ passed, failed: results.length - passed, results, counts }, null, 1));
console.log(`\nTOTAL pass=${passed} fail=${results.length - passed}`);
process.exit(results.length === passed ? 0 : 1);
