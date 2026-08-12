import json
from statistics import fmean
from time import perf_counter

from app.domain.recovery import RecoveryReason, RecoveryState
from tests.support import WALLET_ID, build_runtime, configure_guardians


def test_in_memory_three_of_five_recovery_processing_budget() -> None:
    """Measure service processing only; excludes humans, network, MongoDB, and KMS."""
    durations: list[float] = []
    components: dict[str, list[float]] = {
        "request_creation_ms": [],
        "approval_processing_per_decision_ms": [],
        "quorum_calculation_per_decision_ms": [],
        "timelock_transition_ms": [],
        "key_rotation_ms": [],
        "execution_ms": [],
    }
    iterations = 25

    for _ in range(iterations):
        runtime = build_runtime()
        guardian_ids = configure_guardians(
            runtime,
            count=5,
            threshold=3,
            time_lock_seconds=1,
        )
        started = perf_counter()
        request = runtime.service.create_request(
            runtime.owner,
            wallet_id=WALLET_ID,
            reason=RecoveryReason.KEY_LOSS,
        )
        for index in range(3):
            runtime.service.approve(
                runtime.guardians[index],
                request.request_id,
                guardian_id=guardian_ids[index],
                challenge=request.challenge.value,
            )
        runtime.clock.advance(seconds=1)
        succeeded, failed = runtime.service.reconcile_due()
        durations.append(perf_counter() - started)

        completed = runtime.repository.get_request(request.request_id)
        metrics = runtime.metrics.snapshot()
        assert (succeeded, failed) == (1, 0)
        assert completed is not None
        assert completed.session.state is RecoveryState.COMPLETED
        components["request_creation_ms"].append(
            metrics.request_creation_seconds * 1000
        )
        components["approval_processing_per_decision_ms"].append(
            metrics.approval_processing_seconds * 1000 / 3
        )
        components["quorum_calculation_per_decision_ms"].append(
            metrics.quorum_calculation_seconds * 1000 / 3
        )
        components["timelock_transition_ms"].append(
            metrics.timelock_processing_seconds * 1000
        )
        components["key_rotation_ms"].append(
            metrics.key_rotation_seconds * 1000
        )
        components["execution_ms"].append(metrics.execution_seconds * 1000)

    ordered = sorted(durations)
    p95_index = max(0, int(iterations * 0.95) - 1)
    result = {
        "iterations": iterations,
        "workflow_mean_ms": round(fmean(durations) * 1000, 3),
        "workflow_p95_ms": round(ordered[p95_index] * 1000, 3),
        "workflow_max_ms": round(max(durations) * 1000, 3),
        "component_mean_ms": {
            name: round(fmean(values), 3)
            for name, values in components.items()
        },
        "scope": "in-memory service processing with fake managed-key gateway",
    }
    print("RECOVERY_BENCHMARK=" + json.dumps(result, sort_keys=True))

    assert fmean(durations) < 2.7
