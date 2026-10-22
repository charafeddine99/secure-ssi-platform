# Fraud Service

FastAPI service for deterministic, advisory risk heuristics over synthetic
Secure SSI prototype signals. It does not load or train an ML model. The
current rule engine identifies as `rule-heuristic-v1`; stats disclose
`NOT_TRAINED`, `NO_INDEPENDENT_LABELLED_EVALUATION`, the synthetic dataset
label, and configured signal names.

## Behavior and authority

- `/api/v1/fraud/evaluate` returns a risk score, reason signals, version, and
  advisory recommendation. Repeated evaluation of identical inputs returns
  the same score and does not change quarantine state.
- `/api/v1/fraud/events` and `/api/v1/fraud/events/batch` update the
  process-local feature store only. Event ingestion does not quarantine a DID.
- `/api/v1/fraud/dataset/metrics` reports one seeded, generated synthetic
  replay for diagnostics. These metrics are not evidence of production
  accuracy or generalization.
- The explicit `/api/v1/fraud/quarantine` routes operate on local demo state;
  that state is not credential status, Trust Registry state, durable evidence,
  or a blockchain receipt.
- Identity's verification policy consumes risk only after all credential,
  issuer trust, signature, holder, expiry, status, nonce, DCQL, and consent
  checks pass. Risk cannot make a failed check accepted or create issuer trust
  or an active credential status. A configured high-risk policy may reject an
  otherwise valid presentation or request an optional quarantine action.

The IP, device, velocity, and travel values are prototype heuristics. They are
not validated threat-intelligence sources, device identity proofs, or a
trained risk model. Synthetic metrics remain clearly labeled in API and UI.

## Run locally

From this directory, use the existing repository Python environment:

```powershell
python -m uvicorn app.main:app --reload --port 8002
```

## Focused tests

```powershell
python -m pytest -q tests/test_fraud_service.py tests/test_event_pipeline_and_dataset.py tests/test_layer2_fraud_detection.py
python -m pytest -q tests/test_health.py
python -m ruff check app tests
```

No model-quality claim is made without an identified model artifact and
independent, representative labeled evaluation. For evaluation governance,
see [NIST AI RMF 1.0](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf)
and the [validity and reliability characteristics](https://airc.nist.gov/airmf-resources/airmf/3-sec-characteristics/).
