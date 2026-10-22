# Risk Heuristic Architecture

## Current implementation

The Fraud Service runs deterministic, rule-based scoring over synthetic prototype inputs. It does not load a trained model, contain a versioned model artifact, or have an independently labelled evaluation. The engine identifies itself as `rule-heuristic-v1`; its API reports `model_status=NOT_TRAINED`, `evaluation_status=NO_INDEPENDENT_LABELLED_EVALUATION`, `[DEMO LAB / SYNTHETIC]`, the configured risk-signal names, and `advisory_only=true`.

The primary `/api/v1/fraud/evaluate` route scores explicit thresholds for impossible-travel input, failed-attempt velocity, presentation frequency, device-fingerprint mismatch, and a supplied Tor/proxy indicator. The legacy `/api/fraud_detection` route normalizes failed attempts, hour, an IP-pattern heuristic, a deterministic DID/device hash, and burst rate before applying fixed weights. The IP and device values are demo heuristics; they are not threat-intelligence lookups, device identity proofs, or learned features.

`/api/v1/fraud/dataset/metrics` creates a seeded synthetic dataset and reports metrics for that one deterministic replay. Its response labels the dataset, run scope, seed, and `trained_model=false`. Those values do not estimate real-world performance or generalization and must not be displayed as production model accuracy.

## Security and authority boundary

Risk output is advisory. It cannot establish issuer trust, validate a credential proof, change credential status, or turn a failed protocol/security check into acceptance. Verification policy records protocol/security checks separately and evaluates risk only after those checks. A rejected credential remains rejected at low heuristic risk. High risk does not make an untrusted issuer trusted or set a credential to `ACTIVE`.

Fraud scoring is now side-effect-free: repeated high-risk evaluations return the same score without changing quarantine state, and event ingestion only updates the process-local feature store. The explicit Fraud `/quarantine` routes remain local demo state; they are not durable quarantine evidence, a credential-status authority, or a blockchain receipt. Identity's separate verification policy may reject an otherwise valid presentation or request optional quarantine only after every protocol/security gate passes. Any persistent or anchored quarantine claim must be established by the owning service and a verified receipt.

## Future model work

Trained-model claims require, at minimum, an identified and versioned artifact, documented training/evaluation data provenance, a reproducible split and metrics, leakage checks, calibrated threshold rationale, negative/security tests, and runtime evidence. Until those exist, UI and reports must retain the heuristic, synthetic, untrained, and advisory labels above.

NIST's AI RMF identifies validity and reliability as trustworthiness characteristics and frames evaluation against intended use. The current synthetic replay does not provide evidence about production use, so this project reports no model-performance or generalization claim. See [NIST AI RMF 1.0](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf) and [NIST's validity/reliability guidance](https://airc.nist.gov/airmf-resources/airmf/3-sec-characteristics/).
