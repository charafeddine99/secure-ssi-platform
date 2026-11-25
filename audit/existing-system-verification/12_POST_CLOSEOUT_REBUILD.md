# 12 – Post-closeout: harness watchdog and owner-stack rebuild

**Date:** 2026-11-25
**Branch:** `besna-dev`
**Scope:** two items that report 11 left open: I-5 (the harness time limit) and I-1 (the owner stack runs pre-fix images).
**Approval:** on 2026-11-25 the owner answered "Yes, do both" to the question "Should I do the two remaining fixes now?". The question's message said that a yes also meant starting Docker Desktop, which was off. Reports 00–11 are not changed.

Evidence is in `evidence/post_closeout/`. Backups, build logs and container definitions stay in `C:\ssi-backups\2026-11-25`, outside OneDrive and outside the repository, because they hold real data and the development default settings.

---

## A. Summary

| Item | Result | Evidence |
|---|---|---|
| I-5: harness time limit | **Fixed.** `stage.sh` and `run_noreset.sh` run each stage through `run_limited` (`scripts/watchdog.sh`). On Windows, `run_limited` stops the whole process tree with taskkill once the limit has passed. One real stage passed through it: `wp32_oid4vp_security` 16/0, as on 23 November. The 23 November hang itself could not be reproduced (B.3). | `watchdog_test*.txt`, commit `d234bcf` |
| I-1: owner stack on pre-fix images | **Done.** The five app services run images built from `besna-dev`. MongoDB, Redis and the 5 volumes were kept. Each service was healthy within 7–10 s, with 0 restarts and 0 error lines. | `owner_rebuild_log.txt` |
| Backups before the rebuild | **Done and checked.** A `mongodump` (34 collections, 86,581 documents, equal to a live count), read-only tars of the 5 volumes, the 7 container definitions, and a rollback image of each app service. | C.2 |
| Data after the rebuild | **Preserved.** No collection shrank or disappeared. The audit chain is `INTACT` before and after. | C.6 |
| FIX-4 on the owner's real data | **Confirmed.** About 13 routine audit events per minute before the switch, 0 in the 7 minutes after it. | C.7 |
| New build problem found and fixed | The web image build read the host's `node_modules`, and 4,525 of those files are OneDrive cloud-only. Fixed with `apps/web/.dockerignore`. | commit `f724f7a`, C.4 |
| Still for the owner | Sign in once and verify one credential (D). Decide whether to keep the backups. OneDrive (I-6) is still open. | D, E |

---

## B. Harness watchdog (I-5)

### B.1 Change

- New `evidence/scripts/watchdog.sh` with one function, `run_limited <seconds> <command…>`:
  - on Windows (when `taskkill` exists), it starts the stage in the background and checks the elapsed wall-clock time every second;
  - once the limit has passed, it stops the stage's whole native process tree with `taskkill /T /F` and returns 124, the same code as `timeout`;
  - on other systems it calls `timeout --kill-after=10`.
- `stage.sh` and `run_noreset.sh` load it and call `run_limited 2400` where they called `timeout 2400`. Nothing else changed: the environment variables, redirection, log names and summary lines are the same.

### B.2 Tests (`post_closeout/watchdog_test.sh`)

The script ran twice: from a foreground shell (`watchdog_test.txt`) and as a background task (`watchdog_test_background.txt`), which is how the 23 November chain ran. Both runs gave the same results:

| Check | Result |
|---|---|
| Exit code passes through (`process.exit(3)`) | 3 |
| Variables set before the call reach the stage | yes |
| stdout and stderr follow the redirection | 2 of 2 lines |
| Hung node with a child process, limit 5 s, **new runner** | returned 124 after 5–6 s; 0 marked node processes left |
| Same, **old runner** (`timeout 5`) | also stopped it; 0 left |

**Real stage.** The changed `stage.sh` then ran one stage on the isolated audit stack, with a reset:
- `wp32_oid4vp_security.mjs`: 16 passed, 0 failed, exit 0, in 19 s (23 November: 16/0);
- log: `post_closeout/oid4vp_security_watchdog.log` (local only, because `*.log` is gitignored).

Afterwards the audit stack was stopped again, by a stop selected by its compose project label, with its 26 volumes kept.

### B.3 What this does and does not show

- The old `timeout` also stopped this simple hung process. So the cause of the 23 November hang was **not reproduced**.
- Two facts from that run stand:
  - the hung run's log ends with `exit=1 secs=3900`, not `exit=124` after about 2400 s, so `timeout` never ended it;
  - `taskkill` on the process tree did end it.
- The new runner relies on both of those: it measures the elapsed wall-clock time itself, and it stops the process tree with taskkill. That covers the likely causes: a timer that did not fire, or a stop signal that did not reach a native process. The fix is therefore a safer default, not a proven root-cause fix.

---

## C. Owner-stack rebuild (I-1), following report 11 H.4

### C.1 State before

- Docker Desktop was off. It was started at about 15:55 with the owner's approval, and the 7 owner containers came back by their restart policy (`unless-stopped`).
- All 7 were running and healthy, on the same image IDs as `docker_before.txt` of 23 November. No audit container was running.
- Endpoints (old images): identity `/health` 200 and `/ready` 200 `READY`; recovery, fraud and gateway `/health` 200; web `/` 200; the sign-in route answered an empty body with 422.
- The old identity code was adding routine audit events (F-14): 43,162 at 13:04:13Z, then 43,222 at 13:08:53Z, about 12.9 per minute with 6 managed keys.

### C.2 Backups (H.4 steps 1 and 2)

| Backup | Result |
|---|---|
| `mongodump --archive --gzip` (root user, credentials expanded inside the container) | exit 0, 36 collections, 4.2 MB |
| Check against a live `countDocuments` of every collection | 34 of 34 collections and 86,581 of 86,581 documents in the dump (plus 6 documents of `admin.system.*`); none missing, none lower |
| Read-only tars of `mongodb_data`, `redis_data`, `identity_backups`, `identity_ledger_anchor`, `fraud_state` | 4 clean. `mongodb_data` ended with "file changed as we read it" in `diagnostic.data`, because MongoDB was running. That tar is a secondary copy; the dump is the primary one. |
| `docker inspect` of the 7 containers | saved in the backup folder only |
| Rollback images (`docker commit`, H.4 step 2) | `secure-ssi-platform-<service>:rollback-20261125` for identity, recovery, fraud, gateway and web |
| Application platform backup (admin, step-up, dual control) | **Not done.** It needs the owner's administrator sign-in, which this work does not use. |

SHA-256 values of the dump and the tars are in `owner_rebuild_log.txt`.

### C.3 Configuration check (H.4 step 3)

- There is no `.env` file. The owner stack runs on the compose defaults, and the rebuild uses the same defaults.
- `owner_cfg_compare.py` compared each running container with what the current `docker-compose.yml` would create, by key and value. It printed only key names and set/empty flags.
  - identity: 110 values the same, 0 changed, 0 new;
  - recovery: 36 the same;
  - fraud: 7 the same;
  - gateway: 9 the same;
  - web: none set.
  - The only keys found only in the old containers come from the base images (Python and nginx variables).
  - Mounts, ports and read-only root file systems: the same for all five.
- This means FIX-2 and FIX-3, which changed how the step-up secret and the Mongo URIs are written in the compose file, resolve to exactly the values the owner stack already used. The step-up secret, the Mongo passwords and `IDENTITY_PUBLIC_ORIGIN` are still the development defaults (empty or published placeholders). That is acceptable for the local prototype, and it is still a production blocker (report 11, I-10).

### C.4 Build (H.4 step 4)

1. `docker compose -p secure-ssi-platform build` of the five services from `besna-dev` at `d234bcf`, with 0 tracked changes, **failed for web**. Docker could not read `apps/web/node_modules/…`: "The cloud file provider is not running".
   - A scan found 4,631 OneDrive cloud-only files in the repository: 4,525 in `apps/web/node_modules` and 106 in `.git/objects`.
   - The web failure also cancelled the identity and fraud builds; recovery and gateway were built.
2. Cause: `apps/web` had no `.dockerignore`. The whole folder, including the host's `node_modules` (about 199 MB), went into the build context, and `COPY . .` copied it over the container's own `npm ci` install.
3. Fix: `apps/web/.dockerignore` with `node_modules` and `dist` (commit `f724f7a`). The context is now 992 kB, and `npm ci`, `npm run lint` and `npm run build` pass in the image. The only gitignored local file left in the context, `.env.local`, sets the dev-server proxy target (`vite.config.ts`), which the bundle does not use.
4. Identity and fraud were then built on their own (exit 0), and web too (exit 0). All five images therefore match commit `f724f7a`, which is `d234bcf` plus the `.dockerignore`.
5. Content check:
   - the fix files in the new images (`managed_key_service.py`, `platform_restore_drill.py`, both `oid4vp.py`, gateway `proxy.py`) are byte-identical to the working tree;
   - they are equal to `HEAD` when CR characters are ignored. The Windows checkout uses CRLF (`core.autocrlf=true`), as the earlier images did.

### C.5 Rollout (H.4 step 5)

`docker compose -p secure-ssi-platform up -d --no-deps --no-build <service>`, one service at a time, waiting for `healthy` each time:

| Order | Service | Healthy after | Image (old → new) | Restarts | Error lines |
|---|---|---|---|---|---|
| 1 | identity-service | 7 s | `eb3065f9794d` → `6f6d51e50638` | 0 | 0 |
| 2 | recovery-service | 8 s | `c92c09c1b35b` → `9b0b41686f13` | 0 | 0 |
| 3 | fraud-service | 7 s | `cf2ca9d77815` → `6e2fe064ed89` | 0 | 0 |
| 4 | api-gateway | 7 s | `f19f42d26dd0` → `1398c5f8e113` | 0 | 0 |
| 5 | web | 10 s | `844710f7aeeb` → `09e3ec775b77` | 0 | 0 |

MongoDB and Redis were not recreated; they kept their images and their start time from the Docker start. No `down`, no `-v` and no prune were used.

### C.6 Checks after the rollout (H.4 step 6, read-only)

| Check | Result |
|---|---|
| Containers | 7 of 7 running and healthy, 0 restarts |
| Web app in a browser | `/` and `/login` render, all assets load (200), 0 console errors. No sign-in. |
| Endpoints | identity `/health` 200, `/ready` 200 `READY`; recovery, fraud and gateway `/health` 200; web `/` 200; the sign-in route answered an empty body with 422 through web → gateway → identity. No sign-in was attempted. |
| Audit chain (`AuditChain.verify`, one-off container, read-only) | Before, with the identity image then tagged `latest` (`ae8d41c39d65`, two weeks old): `INTACT`, 30,763 chained and 12,411 unchained events.<br>After, with the new image: `INTACT`, 30,811 chained (the 48 added by the old code before the switch) and 12,411 unchained. |
| Collection counts against the backup | 34 collections before and after, none shrank or disappeared. Growth only:<br>• `audit_events` +84 and `audit_outbox` +84, all written by the old code before the switch (C.1);<br>• `security_events` +2 and `event_buckets` +1 in the security-intelligence store. |

The 12,411 unchained events date from 2026-11-03 13:26Z to 2026-11-06 15:53Z. The first chained event is at 2026-11-06 15:54Z, so they predate the chain. The verifier counts them separately and does not treat them as breaks. The newest chained event is at 13:08:40Z, 14 s before the identity switch.

### C.7 FIX-4 on the owner's real data

| Window | `audit_events` | Rate |
|---|---|---|
| Old code, 13:04:13Z → 13:08:53Z | 43,162 → 43,222 | about 12.9 per minute (6 managed keys) |
| New code, 13:08:54Z → 13:15:54Z (7 min, idle) | 43,222 → 43,222 | 0 (the same 6 managed keys) |

This is the F-14 noise that FIX-4 removes, now measured on the owner's own data rather than only on the isolated audit stack.

### C.8 Not checked here

The following need the owner's own account, so they are left to the owner (D):
- owner sign-in;
- one credential verification;
- the application platform backup.

### C.9 Rollback, if it is ever needed

For each service, newest first (web, api-gateway, fraud-service, recovery-service, identity-service):

```
docker tag secure-ssi-platform-<service>:rollback-20261125 secure-ssi-platform-<service>:latest
docker compose -p secure-ssi-platform up -d --no-deps --no-build <service>
```

- Restore the dump (`mongorestore --archive --gzip`, into the owner MongoDB) only if data were damaged, and only with the owner's approval, because it writes to the owner database.
- The new images stay available by their IDs (C.5).

---

## D. For the owner

1. **Sign in once** at `http://localhost:3000` and **verify one credential**. Sessions from before the rebuild may be gone, because the services restarted.
2. **Backups.** `C:\ssi-backups\2026-11-25` holds a full copy of the database, including personal and credential data. Keep it outside OneDrive, and delete it once the rebuilt stack has been in use for a while. The rollback images hold the old container settings; keep them local and never push them.
3. **OneDrive (I-6).** 4,631 files of the repository are cloud-only while the OneDrive client is off, 106 of them under `.git/objects`. Start OneDrive and mark the repository "Always keep on this device", or move the repository out of OneDrive.

---

## E. Open issues after this report

| Report 11 item | Status now |
|---|---|
| I-1 owner stack on pre-fix images | **Closed.** Rebuilt from `besna-dev` (C). The owner sign-in check (D.1) is still to do. |
| I-5 harness time limit | **Closed** with `run_limited` (B). The 23 November cause is not reproduced (B.3). |
| I-6 OneDrive cloud-only Git pack | **Open, and wider:** 4,631 cloud-only files (C.4). The web build no longer depends on them. |
| I-11 no line-by-line review of WP-28..WP-32 | **Open.** That code now runs in the owner stack. It passed every test on 23 November; the owner was told before approving the rebuild. |
| I-2, I-3, I-4, I-7, I-8, I-9, I-10 | Unchanged (report 11, section I). |
