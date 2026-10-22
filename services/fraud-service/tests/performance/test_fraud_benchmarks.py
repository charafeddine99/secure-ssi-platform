"""Sprint 20: Performance Benchmarks for Hybrid AI Fraud Threat Engine.

Measures:
1. Feature extraction latency.
2. Single-inference latency (Autoencoder + XGBoost ensemble).
3. Batch inference latency across workloads (1, 10, 100, 500).
4. End-to-end evaluation throughput.
"""

import json
import time
import pytest

from app.application.hybrid_detector import HybridFraudDetector
from app.schemas.fraud import FraudEvaluationRequest


@pytest.fixture(scope="module")
def fraud_detector():
    return HybridFraudDetector()


def test_ai_single_and_batch_inference_benchmarks(fraud_detector):
    """Measures single and batch inference latency across multiple workloads."""
    base_request = FraudEvaluationRequest(
        did="did:key:z6MkuBenchmarkUser2026",
        action="presentation_verification",
        client_ip="185.220.101.5",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        failed_attempts=0,
        geo_distance_km=25.0,
        time_since_last_action_sec=300.0,
        presentation_frequency_10m=1,
        device_fingerprint="bench-fp-001",
        device_fingerprint_match=True,
        is_tor_or_proxy=False,
    )

    # Warmup
    for _ in range(5):
        fraud_detector.evaluate(base_request)

    batch_sizes = [1, 10, 100, 500]
    results = {}

    for size in batch_sizes:
        latencies_ms = []
        t_start = time.perf_counter()
        for i in range(size):
            req = base_request.model_copy()
            req.failed_attempts = i % 5
            req.geo_distance_km = float((i * 17) % 1200)

            t0 = time.perf_counter()
            res = fraud_detector.evaluate(req)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000)
            assert res.risk_score >= 0
        total_time_s = time.perf_counter() - t_start
        latencies_ms.sort()

        results[size] = {
            "total_time_s": total_time_s,
            "throughput_eps": size / total_time_s,
            "avg_ms": sum(latencies_ms) / size,
            "p50_ms": latencies_ms[int(size * 0.50)],
            "p95_ms": latencies_ms[int(size * 0.95)],
            "p99_ms": latencies_ms[int(size * 0.99)],
        }

    print("FRAUD_BENCHMARK=" + json.dumps(results, sort_keys=True))

    # Verify that single/batch latency meets academic targets (< 10 ms per evaluation)
    assert results[100]["avg_ms"] < 10.0, f"Average batch evaluation too high: {results[100]['avg_ms']:.2f} ms"
    assert results[100]["throughput_eps"] >= 100.0, f"Throughput too low: {results[100]['throughput_eps']:.1f} evals/s"
