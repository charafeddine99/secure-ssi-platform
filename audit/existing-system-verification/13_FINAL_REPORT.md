# 13 – Final report

**Date:** 2026-11-25
**Branch:** `besna-dev`, at the commit that adds this report.
**Covers:** reports 00–12: the audit of 2026-11-21, the closeout of 2026-11-23 and the rebuild of 2026-11-25.

---

## 1. Verdict

The existing system is verified, fixed and deployed.

- **Code:** six defects were fixed, and the full test regression passes with no new failure.
- **Running stack:** the owner's stack now runs the fixed code. It is healthy and its data is intact, and the owner confirmed that sign-in works.
- **Git:** all work is committed and pushed to `besna-dev`.

The platform is ready to **start** the next phase (D1–D5). It is still an academic prototype, not a production system (section 6).

---

## 2. Timeline

| Date | Work | Report |
|---|---|---|
| 2026-11-21 | **Audit** of the existing system: feature inventory, tests before and after, findings, fixes FIX-1 to FIX-6, security review, external dependencies. | 00–10 |
| 2026-11-23 | **Technical closeout:** FIX-4, FIX-5 and FIX-6 checked live; the two outdated QR checks rewritten; real-MongoDB tests; full regression; Git and Docker state. All the work was committed and pushed (54 commits). | 11 |
| 2026-11-25 | **Rebuild:**<br>• a test-harness watchdog (I-5);<br>• the owner stack rebuilt from `besna-dev`, with backups and checks (I-1);<br>• a web build fix;<br>• the owner confirmed sign-in.<br>6 commits. | 12 |

---

## 3. Fixes

| Fix | Problem | In the code | In the owner's running stack |
|---|---|---|---|
| FIX-1 (F-01) | The gateway dropped the `Host` header, so QR links (`request_uri`) used the internal address. | yes | yes |
| FIX-2 (F-02) | One step-up secret was wired as two variables, so recovery step-up could fail (403). | yes | yes |
| FIX-3 (F-03) | The default Mongo URIs held literal passwords, so a custom DB password did not reach them. | yes | yes (the same values as before) |
| FIX-4 (F-14) | Every routine key sync was written to the audit log, about 2 events per key per minute. | yes | yes. On the owner's data: about 13 events per minute before, **0 in 7 minutes after** |
| FIX-5 (F-12) | The DR drill raised a false "source changed" alarm because the audit log keeps growing. | yes | yes (DR drill 32/0) |
| FIX-6 (F-15) | The retry counter was never reset, so one passing error could fail a healthy key. | yes | yes |
| F-06 (test only) | Two E2E checks still expected the old QR design. | rewritten, and stricter | – |
| Web build | The host's `node_modules`, partly OneDrive cloud-only, broke the image build. | `apps/web/.dockerignore` | yes |
| Test harness | `timeout` did not stop a hung stage on this machine. | `run_limited` watchdog | – |

---

## 4. Test results

Latest run of each suite. Everything ran on the isolated audit stack with synthetic users, on 2026-11-23 unless a date is given.

| Area | Result |
|---|---|
| Unit tests | identity 1,095 passed (12 skipped); recovery 131 (1 skipped); gateway 50; fraud 90; shared 5; root 3; web 42 |
| Web lint and build | pass; the image build also passes on 2026-11-25 |
| End-to-end (E2E) | **132 / 0** (130 / 2 before the F-06 rewrite) |
| Disaster-recovery drill | **32 / 0**, exit 0 |
| Real-MongoDB integration | 7 / 0 |
| FIX-4 / FIX-6 scenario | 33 / 0; live key rotation 5 / 0 |
| Browser and pages | browser 40 / 0; 62 pages with 0 accessibility issues and 0 console errors; UI 41 / 0; scenarios 41 / 0 |
| Security and protocol stages | OID4VP security 16 / 0 (16 / 0 again on 2026-11-25, through the new watchdog); `request_uri` scan 11 / 0; wallet card 31 / 0; cross-device 13 / 0; wp32 UI 12 / 0 |
| Other stages | onboarding 40 / 0; gaps 38 / 0; post 15 / 0; FIX-1 default origin 7 / 0 |
| Owner stack after the rebuild (2026-11-25, read-only) | 7 of 7 containers healthy with 0 restarts; all endpoints answer; `/ready` reports `READY`; the home and sign-in pages render with 0 console errors |

One check in `fix4_live_api.log` (8 / 1) failed because of how that test was designed. It was repeated correctly and passed 5 / 0 (report 11, B.6).

---

## 5. Data and safety

- **No test touched the owner's data.** The tests used an isolated stack, its own databases and synthetic users.
- **Before the rebuild, a checked backup was made** in `C:\ssi-backups\2026-11-25`, outside OneDrive:
  - a database dump that equals a live count (34 collections, 86,581 documents);
  - copies of the volumes and the container settings;
  - a rollback image for each service.
- **After the rebuild:**
  - no collection shrank or disappeared;
  - the audit chain is **INTACT**: 30,811 chained events, plus 12,411 older events written before the chain existed.
- **Secrets and personal data:** none in the reports or in the committed evidence. The files were scanned before every push.
- **Git:**
  - only `besna-dev` moved, with nothing force-pushed, reset or rewritten;
  - before this report, 60 commits were pushed (`9fa97d7..828bda9`);
  - `research/` (the TÜBİTAK drafts) stays local, by the owner's decision.

---

## 6. Still open

**For the owner**
1. Verify one credential in the app. Sign-in is already confirmed.
2. Delete the backups in `C:\ssi-backups\2026-11-25` once the new version has run for a while, because they hold a full copy of the data.
3. OneDrive (I-6): 4,631 repository files are cloud-only while the client is off. Start OneDrive and keep the folder on this device, or move the repository out of OneDrive.
4. Review the WP-28..WP-32 commits (I-11) before `besna-dev` is merged into `main`.

**Known limits.** These are not bugs, and none of them blocks D1–D5 (report 11, I-10):
- no independent penetration test;
- a development key provider, with no KMS or HSM;
- no test on a physical phone or over public HTTPS;
- backups are not kept off-site, and there is no point-in-time recovery;
- the audit log is tamper-evident, not write-once (WORM);
- the fraud/risk module is **rule-based** (`rule-heuristic-v1`, `NOT_TRAINED`), not a trained model;
- blockchain anchoring needs a local Hardhat node (5 skipped tests).

**Optional:**
- I-2: a metrics endpoint;
- I-3 and I-4: extra failure tests;
- I-7: the raw logs are local only;
- I-9: the old audit DR projects can be removed with approval.

---

## 7. Where the details are

| Report | Content |
|---|---|
| `00`–`09` | Audit: baseline, inventory, tests before, findings, fixes, tests after, module matrix, security, external dependencies, status |
| `10_FINAL_EXECUTION_REPORT.md` | Consolidated audit report: each fix's cause, change and verification |
| `11_FINAL_TECHNICAL_CLOSEOUT.md` | Closeout: live fix checks, F-06, MongoDB tests, full regression, Git and Docker state, rebuild plan, open issues I-1 to I-11 |
| `12_POST_CLOSEOUT_REBUILD.md` | Watchdog, owner-stack rebuild (backups, configuration, rollout, checks), rollback commands |
| `evidence/` | Logs and results; `closeout/` (2026-11-23) and `post_closeout/` (2026-11-25) |
