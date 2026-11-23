// WP-31 disaster recovery drill. Source: wp31-e2e stack. Target: a separate wp31-dr
// stack with its own mongod, network and volumes. Same physical host, so this is NOT
// host-loss evidence. Prints no secrets.
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { PROJECT, REPO, check, client, docker, enroll, fact, fixturePass, isolatedMongo, login, present, results, sleep, stepUp, walletOf } from "./wp31_lib.mjs";

const SUFFIX = Date.now().toString(36);
const SOURCE = "http://localhost:29300";
const DR = "http://localhost:29400";
const DR_PROJECT = "audit-20261121-dr5";
const DIR = new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const SCRATCH = process.env.WP31_SCRATCH;
const users = JSON.parse(readFileSync(`${SCRATCH}/wp31_users.json`, "utf8"));
const state = JSON.parse(readFileSync(`${SCRATCH}/wp31_state.json`, "utf8"));
const env = Object.fromEntries(readFileSync(`${SCRATCH}/wp31.env`, "utf8").trim().split("\n").map((l) => { const i = l.indexOf("="); return [l.slice(0, i), l.slice(i + 1)]; }));
const measured = {};

// fresh administrators: the E2E run keeps its TOTP secrets in memory only
const extra = { [`admin.c.${SUFFIX}@wp31.test`]: { name: "Admin C (synthetic)", role: "admin", password: `Wp29-${Date.now()}-c` }, [`admin.d.${SUFFIX}@wp31.test`]: { name: "Admin D (synthetic)", role: "admin", password: `Wp29-${Date.now()}-d` } };
execFileSync("docker", ["exec", "-i", "-w", "/app", `${PROJECT}-identity-service-1`, "python", "-"], {
  input: readFileSync(`${DIR}seed_users.py`, "utf8").replace("json.load(sys.stdin)", `json.loads(${JSON.stringify(JSON.stringify(extra))})`), encoding: "utf8",
});
const adminC = await login(SOURCE, `admin.c.${SUFFIX}@wp31.test`, extra[`admin.c.${SUFFIX}@wp31.test`].password);
const adminD = await login(SOURCE, `admin.d.${SUFFIX}@wp31.test`, extra[`admin.d.${SUFFIX}@wp31.test`].password);
await enroll(adminC);
await enroll(adminD);

const list = await adminC("GET", "/api/v1/identity/admin/platform-backups");
check("dr", "scope lists identity, ledger and recovery", list, (r) => ["identity", "ledger", "recovery"].every((c) => r.data.scope.includes(c)), JSON.stringify(list.data.scope));
fact("dr", "off-site, immutable and PITR are reported NOT_CONFIGURED", list.data.offsite === "NOT_CONFIGURED" && list.data.immutable === "NOT_CONFIGURED" && list.data.pointInTime === "NOT_CONFIGURED");
check("dr", "creating a backup without step-up is refused", await adminC("POST", "/api/v1/identity/admin/platform-backups"), (r) => r.status === 403);
const sourceAudit = await adminC("GET", "/api/v1/identity/audit/integrity");
const t0 = Date.now();
const created = check("dr", "coordinated backup succeeds", await adminC("POST", "/api/v1/identity/admin/platform-backups", undefined, await stepUp(adminC, "platform.backup.create", "platform")), (r) => r.status === 201 && r.data.status === "SUCCEEDED");
measured.backupWallClockMs = Date.now() - t0;
const backup = created.data;
measured.backupServerMs = backup.durationMs;
measured.backupBytes = backup.sizeBytes;
fact("dr", "backup is COMPLETE and carries a ledger watermark", backup.completeness === "COMPLETE" && /^\d+:[0-9a-f]{64}$/.test(backup.watermark ?? ""), `${backup.completeness} seq=${(backup.watermark ?? "").split(":")[0]}`);
const names = backup.collections.map((c) => c.name);
fact("dr", "archive contains recovery and ledger collections", names.includes("recovery/guardians") && names.includes("recovery/recovery_requests") && names.includes("ledger/revocation_ledger_events"), `collections=${names.length}`);
check("dr", "archive verifies", await adminC("POST", `/api/v1/identity/admin/platform-backups/${backup.backupId}/verify`), (r) => r.status === 200 && r.data.integrityVerified === true);

// ---- separate target stack
const DC = ["compose", "-p", DR_PROJECT, "--env-file", `${SCRATCH}/wp31_dr.env`, "-f", `${REPO}/docker-compose.yml`, "-f", `${DIR}wp31_dr.override.yml`];
const dcRun = (...args) => execFileSync("docker", [...DC, ...args], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], cwd: REPO });
dcRun("up", "-d", "--wait", "mongodb");
try { docker("network", "connect", `${PROJECT}_default`, `${DR_PROJECT}-mongodb-1`, "--alias", "dr-mongodb"); } catch (error) { if (!/already exists/.test(String(error.stderr))) throw error; }
const rootUri = `mongodb://wp31root:${env.MONGO_INITDB_ROOT_PASSWORD}@dr-mongodb:27017/?authSource=admin`;
isolatedMongo(`db.getSiblingDB("admin").createUser({user:"drill_partial",pwd:${JSON.stringify(env.MONGO_INITDB_ROOT_PASSWORD)},roles:[{role:"dbOwner",db:"restore_drill_fail"},{role:"dbOwner",db:"restore_drill_fail_ledger"},{role:"read",db:"restore_drill_fail_recovery"}]}); print("ok")`, `${DR_PROJECT}-mongodb-1`);
const partialUri = `mongodb://drill_partial:${env.MONGO_INITDB_ROOT_PASSWORD}@dr-mongodb:27017/?authSource=admin`;

function cli(backupId, target, { operationId = "", token = "", uri = rootUri } = {}) {
  const lines = [
    `PLATFORM_RESTORE_TARGET_URI=${uri}`, `PLATFORM_RESTORE_TARGET_DATABASE=${target}`,
    `PLATFORM_RESTORE_OPERATION_ID=${operationId}`, `PLATFORM_RESTORE_EXECUTION_TOKEN=${token}`,
  ];
  const file = `${SCRATCH}/drill.env`;
  writeFileSync(file, lines.join("\n") + "\n");
  try {
    const out = execFileSync("docker", ["exec", "--env-file", file, "-w", "/app", `${PROJECT}-identity-service-1`, "python", "-m", "app.tools.platform_restore_drill", backupId], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    return { code: 0, report: JSON.parse(out) };
  } catch (error) {
    let report = {}; try { report = JSON.parse(error.stdout); } catch { report = { raw: String(error.stderr).slice(-300) }; }
    return { code: error.status, report };
  } finally { writeFileSync(file, ""); }
}
async function approval(target) {
  const op = (await adminC("POST", "/api/v1/identity/admin/dual-control", { operationType: "PLATFORM_RESTORE", target, reason: "DR drill" }, await stepUp(adminC, "dual-control.request", target))).data;
  const ok = await adminD("POST", `/api/v1/identity/admin/dual-control/${op.operationId}/approve`, undefined, await stepUp(adminD, "dual-control.approve", op.operationId));
  return { operationId: op.operationId, token: ok.data.executionToken };
}

let outcome = cli(backup.backupId, "restore_drill_wp31");
fact("dr", "CLI restore with no approval is refused", outcome.report.status === "REJECTED" && outcome.report.failureCode === "DUAL_CONTROL_REQUIRED", outcome.report.failureCode);
const selfOp = (await adminC("POST", "/api/v1/identity/admin/dual-control", { operationType: "PLATFORM_RESTORE", target: `${backup.backupId}:restore_drill_wp31`, reason: "one person" }, await stepUp(adminC, "dual-control.request", `${backup.backupId}:restore_drill_wp31`))).data;
check("dr", "one administrator cannot approve their own restore", await adminC("POST", `/api/v1/identity/admin/dual-control/${selfOp.operationId}/approve`, undefined, await stepUp(adminC, "dual-control.approve", selfOp.operationId)), (r) => r.status === 403);
const otherTarget = await approval(`${backup.backupId}:restore_drill_other`);
outcome = cli(backup.backupId, "restore_drill_wp31", otherTarget);
fact("dr", "approval for another target is refused", outcome.report.failureCode === "DUAL_CONTROL_REQUIRED", outcome.report.failureCode);

const live = await approval(`${backup.backupId}:secure_identity`);
outcome = cli(backup.backupId, "secure_identity", live);
fact("dr", "the live database name is refused even with approval", outcome.report.status === "REJECTED", outcome.report.failureCode);

// corrupted artifact: refused before any write, then put back
const artifact = `/var/lib/secure-ssi/backups/${backup.backupId}.ssipbak`;
const idc = `${PROJECT}-identity-service-1`;
docker("exec", idc, "sh", "-c", `cp ${artifact} /tmp/wp31-original && printf 'x' | dd of=${artifact} bs=1 seek=200 conv=notrunc 2>/dev/null`);
const corrupt = await approval(`${backup.backupId}:restore_drill_corrupt`);
outcome = cli(backup.backupId, "restore_drill_corrupt", corrupt);
fact("dr", "corrupted artifact is refused", outcome.report.status === "REJECTED", outcome.report.failureCode);
docker("exec", idc, "sh", "-c", `cp /tmp/wp31-original ${artifact} && rm /tmp/wp31-original`);
const emptyAfterCorrupt = isolatedMongo(`print(db.getMongo().getDBNames().filter(n=>n.startsWith("restore_drill_corrupt")).length)`, `${DR_PROJECT}-mongodb-1`);
fact("dr", "nothing reached the target after the refusal", emptyAfterCorrupt === "0", emptyAfterCorrupt);

// write failure half way through: identity and ledger writable, recovery not
const failing = await approval(`${backup.backupId}:restore_drill_fail`);
outcome = cli(backup.backupId, "restore_drill_fail", { ...failing, uri: partialUri });
fact("dr", "a write failure rolls back every component", outcome.report.status === "FAILED_ROLLED_BACK", `${outcome.report.status}/${outcome.report.failureCode}`);
const leftovers = isolatedMongo(`print(db.getMongo().getDBNames().filter(n=>n.startsWith("restore_drill_fail")).length)`, `${DR_PROJECT}-mongodb-1`);
fact("dr", "no partial database survives the failure", leftovers === "0", leftovers);

const real = await approval(`${backup.backupId}:restore_drill_wp31`);
const restoreStarted = Date.now();
outcome = cli(backup.backupId, "restore_drill_wp31", real);
measured.restoreWallClockMs = Date.now() - restoreStarted;
measured.restoreServerMs = outcome.report.restoreDurationMs;
fact("dr", "two-person restore into the separate mongod succeeds", outcome.report.status === "RESTORED_AND_VERIFIED" && outcome.code === 0, outcome.report.status);
fact("dr", "index and collection options match for every collection", outcome.report.collections.every((c) => c.indexesMatch && c.optionsMatch), `n=${outcome.report.collections.length}`);
fact("dr", "source database was not changed by the restore", outcome.report.sourceFingerprintUnchanged === true);
outcome = cli(backup.backupId, "restore_drill_wp31", real);
fact("dr", "the execution token cannot be reused", outcome.report.failureCode === "DUAL_CONTROL_REQUIRED", outcome.report.failureCode);

// ---- real services on the restored data
const bootStart = Date.now();
dcRun("up", "-d", "--wait", "redis", "fraud-service", "identity-service", "recovery-service", "api-gateway", "web");
measured.applicationBootMs = Date.now() - bootStart;
const anon = client(DR, "anon");
fact("dr", "restored stack is on its own project", docker("inspect", "-f", "{{.Config.Image}}", `${DR_PROJECT}-identity-service-1`).startsWith(DR_PROJECT));
const envOf = docker("exec", `${DR_PROJECT}-identity-service-1`, "printenv", "IDENTITY_MONGO_DATABASE");
fact("dr", "the application points at the restored database", envOf === "restore_drill_wp31", envOf);
check("dr", "identity is healthy on restored data", await fetch("http://127.0.0.1:29381/health").then((r) => ({ status: r.status })), (r) => r.status === 200);
const ready = await fetch("http://127.0.0.1:29381/ready").then(async (r) => ({ status: r.status, data: await r.json() }));
fact("dr", "readiness answers on the restored stack", [200, 503].includes(ready.status), JSON.stringify(ready.data));

const stale = client(DR, "stale");
stale.setCookie(state.reentryCookie);
check("dr", "a session issued before the restore is rejected", await stale("GET", "/api/v1/identity/auth/me"), (r) => r.status === 401);
await sleep(1_500);
const holderB = await login(DR, "holder.b@wp31.test", users["holder.b@wp31.test"].password);
check("dr", "a fresh sign-in works", await holderB("GET", "/api/v1/identity/auth/me"), (r) => r.status === 200);
const verifier = await login(DR, "verifier@example.test", fixturePass("VERIFIER"));
const admin = await login(DR, "admin@example.test", fixturePass("ADMIN"));
check("dr", "the restored audit chain gives the same verdict as the source", await admin("GET", "/api/v1/identity/audit/integrity"), (r) => r.status === 200 && r.data.status === sourceAudit.data.status && r.data.checked === sourceAudit.data.checked, `${sourceAudit.data.status} at ${sourceAudit.data.checked}`);
check("dr", "trust registry is readable", await admin("GET", "/api/v1/identity/trust-registry/issuers"), (r) => r.status === 200, "");
const wallet = await walletOf(holderB);
const accepted = await present(verifier, holderB, wallet, state.w1);
fact("dr", "a valid credential verifies on the restored stack", accepted.final === "ACCEPTED", `${accepted.final} ${accepted.detail}`);
const { gunzipSync } = await import("node:zlib");
const listId = state.c3.credentialStatus.statusListCredential.split("/").pop();
const list3 = await anon("GET", `/api/v1/identity/status-lists/${listId}`);
const bytes = gunzipSync(Buffer.from(list3.data.credentialSubject.encodedList.slice(1), "base64url"));
const index3 = Number(state.c3.credentialStatus.statusListIndex);
fact("dr", "a revoked credential stays revoked on the restored stack", Boolean(bytes[Math.floor(index3 / 8)] & (1 << (7 - (index3 % 8)))));
const cases = await admin("GET", "/api/v1/recovery/admin/requests");
check("dr", "guardian recovery state survived", cases, (r) => r.status === 200 && r.data.items.some((i) => i.requestId === state.requestId && i.state === "COMPLETED"), `cases=${cases.data.items?.length}`);
const seq = Number(isolatedMongo('print(db.getSiblingDB("restore_drill_wp31_ledger").revocation_ledger_events.countDocuments({}))', `${DR_PROJECT}-mongodb-1`));
fact("dr", "the ledger chain arrived whole", seq === Number(backup.watermark.split(":")[0]), `events=${seq}`);
const detail = await admin("GET", "/api/v1/identity/admin/readiness");
check("dr", "the ledger verifies on the restored stack", detail, (r) => r.status === 200 && !r.data.blockers.concat(r.data.warnings).includes("REVOCATION_LEDGER_UNAVAILABLE"), `seq=${detail.data.details?.ledger?.sequence}`);

const passed = results.filter((r) => r.pass).length;
writeFileSync(`${DIR}dr_results.json`, JSON.stringify({ passed, failed: results.length - passed, measured, note: "Same physical host: not host-loss evidence. Synthetic data of a few hundred documents.", results }, null, 1));
console.log(`\nTOTAL pass=${passed} fail=${results.length - passed}`);
console.log(JSON.stringify(measured));
process.exitCode = results.length === passed ? 0 : 1;
