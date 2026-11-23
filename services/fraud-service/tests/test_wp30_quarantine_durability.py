"""Quarantine survives a restart and is stored without raw DIDs."""

import json

import pytest

from app.application.hybrid_detector import HybridFraudDetector
from app.core.subject import subject_key
from app.ml.feature_store import SlidingWindowFeatureStore

DID = "did:example:wp30-quarantine"


def test_quarantine_survives_a_new_process(tmp_path) -> None:
    path = tmp_path / "quarantine.json"
    HybridFraudDetector(str(path)).quarantine(DID, "synthetic")
    restarted = HybridFraudDetector(str(path))
    assert restarted.is_quarantined(DID)
    assert restarted.get_quarantine_info(DID)["reason"] == "synthetic"


def test_release_survives_a_new_process(tmp_path) -> None:
    path = tmp_path / "quarantine.json"
    first = HybridFraudDetector(str(path))
    first.quarantine(DID, "synthetic")
    assert first.release_quarantine(DID)
    assert not HybridFraudDetector(str(path)).is_quarantined(DID)


def test_the_store_holds_no_raw_did(tmp_path) -> None:
    path = tmp_path / "quarantine.json"
    HybridFraudDetector(str(path)).quarantine(DID, "synthetic")
    assert DID not in path.read_text()
    assert list(json.loads(path.read_text())) == [subject_key(DID)]


def test_a_corrupt_store_stops_startup(tmp_path) -> None:
    path = tmp_path / "quarantine.json"
    path.write_text("{not json")
    with pytest.raises(ValueError):
        HybridFraudDetector(str(path))


def test_a_failed_write_leaves_no_quarantine_claimed(tmp_path) -> None:
    detector = HybridFraudDetector(str(tmp_path / "missing" / "quarantine.json"))
    with pytest.raises(OSError):
        detector.quarantine(DID, "synthetic")
    assert not detector.is_quarantined(DID)


def test_raw_did_and_its_pseudonym_are_the_same_subject(tmp_path) -> None:
    detector = HybridFraudDetector(str(tmp_path / "quarantine.json"))
    detector.quarantine(DID, "synthetic")
    assert detector.is_quarantined(subject_key(DID))


def test_feature_history_is_keyed_by_the_pseudonym() -> None:
    store = SlidingWindowFeatureStore()
    store.ingest_event(event_id="e1", event_type="LOGIN_FAILED", did=subject_key(DID))
    raw = store.get_features(DID)
    pseudonym = store.get_features(subject_key(DID))
    assert raw == pseudonym
    assert DID not in store._did_events
