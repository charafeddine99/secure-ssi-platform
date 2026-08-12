from dataclasses import asdict, dataclass
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class RecoveryMetricsSnapshot:
    active_guardians: int
    requests: int
    approvals: int
    rejections: int
    quorum_reached: int
    cancellations: int
    expirations: int
    successes: int
    failures: int
    reconciliation_attempts: int
    reconciliation_successes: int
    reconciliation_failures: int
    share_validation_failures: int
    request_creation_seconds: float
    approval_processing_seconds: float
    quorum_calculation_seconds: float
    timelock_processing_seconds: float
    key_rotation_seconds: float
    execution_seconds: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class RecoveryMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._values: dict[str, int | float] = {
            field: 0 for field in RecoveryMetricsSnapshot.__dataclass_fields__
        }

    def set_active_guardians(self, value: int) -> None:
        with self._lock:
            self._values["active_guardians"] = max(0, value)

    def increment(self, name: str, value: int = 1) -> None:
        if name not in self._values or name.endswith("_seconds"):
            raise ValueError("Unknown recovery counter metric.")
        with self._lock:
            self._values[name] = int(self._values[name]) + value

    def observe(self, name: str, seconds: float) -> None:
        if name not in self._values or not name.endswith("_seconds"):
            raise ValueError("Unknown recovery duration metric.")
        with self._lock:
            self._values[name] = float(self._values[name]) + max(0.0, seconds)

    def snapshot(self) -> RecoveryMetricsSnapshot:
        with self._lock:
            return RecoveryMetricsSnapshot(**self._values)
