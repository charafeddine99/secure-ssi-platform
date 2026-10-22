# Secure SSI Platform — Performance and Reliability Report

**Review date:** 15 October 2026 · **Gate:** G15 · **Result:** `PARTIAL`.

## Current evidence

No project-wide API load test, concurrency test, database-pool saturation test, end-to-end OID4VP benchmark, or failure/recovery experiment was run. Component-level numbers from the 15 October checkpoint are reported below; they are not platform latency, throughput, reliability, or availability claims.

An earlier Recovery Service report records an in-memory 25-run workflow mean of 2.335 ms and p95 of 2.711 ms. This is a historical component microbenchmark; it does not include real MongoDB, browser/network latency, concurrent traffic, service restarts, or production infrastructure. It is not an SLA and cannot be extrapolated to the whole platform.

## Required measurement plan

After G6 and G11 prerequisites are accepted, run in an isolated authorized environment and record:

- plan target, service build/source checkpoint, host/container sizing, database version and dataset size;
- concurrency, request volume, warm-up, duration, repetitions, and exact tool version/command;
- P50/P95/P99 latency, throughput, error rate, CPU/memory, Mongo pool/wait behavior;
- credential proof creation/verification and status/trust lookup costs;
- OID4VCI issuance, wallet consent and OID4VP presentation latency;
- Recovery and audit delivery behavior;
- timeout, retry, idempotency, dependency outage, restart, and recovery outcomes.

Do not run against production or a public chain. Do not infer a performance PASS from a unit benchmark or frontend build.

## 15 October 2026 component benchmark checkpoint

The three existing performance test files were run on the repository virtual environment (Python 3.11.16) on Windows `10.0.26300.0`. Tests ran in-process on the host, sequentially; no Docker load, HTTP traffic, concurrency, real MongoDB pool measurement, or external load generator was used. CPU/RAM inventory was unavailable because Windows denied `Get-CimInstance`. `Get-Command locust,k6,wrk,vegeta,ab -ErrorAction SilentlyContinue` found none of those tools.

Identity measures local canonicalization and Ed25519 signing only. Fraud measures the deterministic `rule-heuristic-v1` evaluator; it is not trained-model inference. Recovery measures in-memory service processing with a fake managed-key gateway. Percentiles are selected by the tests from sorted samples using direct array indexes (not an interpolated estimator); small-sample tail percentiles therefore have limited statistical meaning.

| Component / workload | P50 ms | P95 ms | P99 ms | Throughput / scope |
|---|---:|---:|---:|---|
| Identity signing, 10 credentials | 0.185 | 0.291 | 0.291 | 4,884 credential-signing ops/s |
| Identity signing, 100 credentials | 0.183 | 0.501 | 0.761 | 4,159 credential-signing ops/s |
| Identity signing, 500 credentials | 0.185 | 0.496 | 0.786 | 4,007 credential-signing ops/s |
| Fraud heuristic, 1 evaluation | 0.026 | 0.026 | 0.026 | One sample; tail percentiles are not meaningful |
| Fraud heuristic, 10 evaluations | 0.025 | 0.043 | 0.043 | 30,303 evaluations/s |
| Fraud heuristic, 100 evaluations | 0.011 | 0.017 | 0.023 | 67,114 evaluations/s |
| Fraud heuristic, 500 evaluations | 0.011 | 0.016 | 0.109 | 60,145 evaluations/s |
| Recovery, 25 in-memory workflows | — | 4.151 | — | Mean 3.098 ms; maximum 6.473 ms; fake managed-key gateway |

The Identity status-list microbenchmark also passed its assertions for 131,072 entries, encoded size, encode time and 1,000 lookups; it does not print those timings. The exact targeted commands and pytest outcomes are in [test evidence](SECURE_SSI_PLATFORM_TEST_EVIDENCE.md). The tests passed their existing assertions, but that only establishes these narrow component checks. G15 stays **PARTIAL** until the planned API/reliability workload is executed after G11 reaches L3 and records concurrency, error rate, resource use, persistence, timeout/retry/idempotency, and recovery outcomes.
