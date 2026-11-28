"""Event pipeline, detection, metrics, anomalies and API rules."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.intelligence.analytics import ANOMALY_METHOD, anomalies, metrics, monitoring_coverage, posture
from app.intelligence.rules import RULES
from app.intelligence.schema import SecurityEvent
from app.intelligence.store import IncidentConflictError, IntelStore, IntelUnavailableError, runtime
from app.intelligence.taxonomy import EVENT_TYPES, REQUIRED_DOMAINS
from app.main import app
from tests.intel_fake import FakeDatabase

TOKEN = "test-internal-service-token-of-32-chars"
NOW = datetime.now(UTC)
ORIGIN = "SYNTHETIC_TEST"


def event(number, event_type="auth.login.failure", *, at=None, origin=ORIGIN, source="identity-service", **fields):
    return SecurityEvent.model_validate({
        "event_id": f"event:{number:08d}",
        "occurred_at": (at or NOW).isoformat(),
        "source_service": source,
        "source_component": "test",
        "event_type": event_type,
        "origin": origin,
        **fields,
    }).model_dump()


@pytest.fixture
def store():
    value = IntelStore(FakeDatabase())
    runtime.use(value)
    yield value
    runtime.use(None)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(security, "FRAUD_INTERNAL_SERVICE_TOKEN", TOKEN)
    return TestClient(app)


async def _admin():
    return security.FraudPrincipal("admin-1", frozenset({"admin"}), frozenset({"admin:operations:read"}))


@pytest.fixture
def admin():
    app.dependency_overrides[security.require_admin] = _admin
    app.dependency_overrides[security.require_incident_writer] = _admin
    yield
    app.dependency_overrides.pop(security.require_admin, None)
    app.dependency_overrides.pop(security.require_incident_writer, None)


def ingest(client, events, source="identity-service"):
    return client.post(
        "/api/v1/fraud/intel/ingest",
        headers={"X-Internal-Service-Token": TOKEN},
        json={"source": source, "environment": "test", "events": events},
    )


def wire(number, event_type="auth.login.failure", **fields):
    return {
        "event_id": f"wire:{number:08d}", "occurred_at": NOW.isoformat(), "source_service": "identity-service",
        "source_component": "test", "event_type": event_type, "origin": ORIGIN, **fields,
    }


# ---- envelope
@pytest.mark.parametrize("bad", [
    {"event_type": "made.up"},
    {"origin": "PRODUCTION"},
    {"source_service": "attacker"},
    {"attributes": {"username": "alice"}},
    {"attributes": {"reason_code": "free text with spaces"}},
    {"actor_ref": "did:example:raw-subject identifier"},
    {"tenant": "other"},
    {"risk_level": "LOW"},
    {"raw_vc": {"a": 1}},
    {"occurred_at": (NOW + timedelta(hours=1)).isoformat()},
    {"occurred_at": (NOW - timedelta(days=120)).isoformat()},
    {"occurred_at": "2026-11-05T10:00:00"},
])
def test_unsafe_or_unknown_fields_are_refused(bad):
    with pytest.raises(ValueError):
        SecurityEvent.model_validate({**wire(1), **bad})


def test_every_rule_uses_known_event_types():
    known = set(EVENT_TYPES)
    for rule in RULES:
        assert set(rule.trigger) <= known and set(rule.counted_types) <= known


def test_every_required_domain_uses_known_event_types():
    for _producer, types in REQUIRED_DOMAINS.values():
        assert set(types) <= set(EVENT_TYPES)


# ---- ingest API
def test_producer_without_the_service_token_is_refused(client, store):
    response = client.post("/api/v1/fraud/intel/ingest", json={"source": "identity-service", "environment": "t", "events": []})
    assert response.status_code == 401
    assert client.post(
        "/api/v1/fraud/intel/ingest", headers={"X-Internal-Service-Token": "wrong-token-of-sufficient-length-00"},
        json={"source": "identity-service", "environment": "t", "events": []},
    ).status_code == 401


def test_duplicate_is_counted_once(client, store):
    first = ingest(client, [wire(1), wire(1)]).json()
    assert first == {"accepted": 1, "duplicates": 1, "rejected": 0}
    assert ingest(client, [wire(1)]).json()["duplicates"] == 1
    assert metrics(store, ORIGIN, 1, NOW + timedelta(seconds=1))["event_counts"][0]["count"] == 1


def test_one_bad_event_does_not_sink_the_batch(client, store):
    result = ingest(client, [wire(1), {**wire(2), "password": "x"}]).json()
    assert result == {"accepted": 1, "duplicates": 0, "rejected": 1}
    assert store.sources.find_one({"_id": "identity-service"})["rejected"] == 1


def test_event_claiming_another_source_is_rejected(client, store):
    result = ingest(client, [{**wire(1), "source_service": "recovery-service"}]).json()
    assert result["rejected"] == 1


def test_oversized_batch_is_refused(client, store):
    assert ingest(client, [wire(i) for i in range(501)]).status_code == 422


def test_late_event_lands_in_its_own_hour_and_keeps_both_timestamps(store):
    earlier = NOW - timedelta(hours=5)
    store.ingest(event(1, at=earlier), NOW)
    row = store.events.find_one({"_id": "event:00000001"})
    assert row["occurred_at"] == earlier and row["ingested_at"] == NOW
    assert store.buckets.rows[0]["hour"] == earlier.replace(minute=0, second=0, microsecond=0)


def test_store_outage_is_a_503_never_zero(client, admin, monkeypatch):
    runtime.use(None)

    def down():
        raise IntelUnavailableError("UNAVAILABLE")

    monkeypatch.setattr(runtime, "store", down)
    for path in ("metrics", "health", "incidents", "anomalies", "risk", "model"):
        response = client.get(f"/api/v1/fraud/intel/{path}")
        assert response.status_code == 503, path
    assert ingest(client, [wire(1)]).status_code == 503


def test_posture_still_answers_and_marks_monitoring_unknown_in_an_outage(client, admin, monkeypatch):
    def down():
        raise IntelUnavailableError("UNAVAILABLE")

    monkeypatch.setattr(runtime, "store", down)
    body = client.get("/api/v1/fraud/intel/posture").json()
    assert body["monitoring_coverage"] is None
    assert body["verified_control_coverage"]["denominator"] > 0


@pytest.mark.parametrize("path", ["health", "metrics", "incidents", "anomalies", "risk", "rules", "posture", "model"])
def test_reads_need_an_administrator(client, path):
    assert client.get(f"/api/v1/fraud/intel/{path}").status_code == 401


# ---- detection
def _failures(store, count, ref="actor:aaaaaaaaaaaa", start=1):
    for i in range(count):
        store.ingest(event(start + i, actor_ref=ref), NOW)


def test_below_threshold_is_only_a_raw_signal(store):
    _failures(store, 4)
    assert store.incidents.rows == []


def test_threshold_opens_one_incident_and_groups_later_signals(store):
    _failures(store, 8)
    assert len(store.incidents.rows) == 1
    incident = store.incidents.rows[0]
    assert incident["rule_id"] == "AUTH-01" and incident["detection_state"] == "SUSPICIOUS_ACTIVITY"
    assert incident["status"] == "NEW" and incident["signal_count"] == 4 and incident["suppressed_alerts"] == 3
    assert incident["delivery"] == "IN_APP_ONLY"


def test_success_after_a_burst_is_a_suspected_attack_not_a_confirmed_one(store):
    _failures(store, 5)
    store.ingest(event(50, "auth.login.success", actor_ref="actor:aaaaaaaaaaaa"), NOW)
    suspected = [i for i in store.incidents.rows if i["rule_id"] == "AUTH-03"]
    assert suspected and suspected[0]["detection_state"] == "SUSPECTED_ATTACK"
    assert suspected[0]["status"] == "NEW"


def test_old_failures_outside_the_window_do_not_count(store):
    for i in range(5):
        store.ingest(event(i + 1, actor_ref="actor:aaaaaaaaaaaa", at=NOW - timedelta(hours=2 + i)), NOW)
    assert store.incidents.rows == []


def test_synthetic_and_operational_never_mix(store):
    for i in range(3):
        store.ingest(event(i + 1, actor_ref="actor:aaaaaaaaaaaa"), NOW)
    for i in range(2):
        store.ingest(event(i + 10, actor_ref="actor:aaaaaaaaaaaa", origin="OPERATIONAL"), NOW)
    assert store.incidents.rows == []
    assert metrics(store, "OPERATIONAL", 1, NOW + timedelta(seconds=1))["rates"][0]["numerator"] == 2


# ---- incidents
def test_incident_lifecycle_keeps_history_and_reopens_a_new_case(store):
    _failures(store, 5)
    incident_id = store.incidents.rows[0]["_id"]
    store.transition(incident_id, "TRIAGED", "looking", "admin-1", NOW)
    done = store.transition(incident_id, "FALSE_POSITIVE", "owner forgot password", "admin-1", NOW)
    assert [h["status"] for h in done["history"]] == ["NEW", "TRIAGED", "FALSE_POSITIVE"]
    assert done["open"] is False
    _failures(store, 5, start=100)
    assert len(store.incidents.rows) == 2


def test_illegal_transition_is_refused(store):
    _failures(store, 5)
    incident_id = store.incidents.rows[0]["_id"]
    with pytest.raises(IncidentConflictError):
        store.transition(incident_id, "CLOSED", "skip triage", "admin-1", NOW)


def test_transition_records_the_server_side_actor(client, store, admin):
    _failures(store, 5)
    incident_id = store.incidents.rows[0]["_id"]
    body = client.post(f"/api/v1/fraud/intel/incidents/{incident_id}/transition", json={"status": "TRIAGED", "note": "looking"}).json()
    assert body["history"][-1]["by"] == "admin-1"
    assert client.post(f"/api/v1/fraud/intel/incidents/{incident_id}/transition", json={"status": "TRIAGED", "note": "x", "by": "someone"}).status_code == 422


# ---- metrics
def test_zero_denominator_is_na_not_zero(store):
    rates = {r["name"]: r for r in metrics(store, ORIGIN, 24, NOW)["rates"]}
    assert rates["Sign-in failure rate"]["value"] is None
    assert rates["Sign-in failure rate"]["denominator"] == 0


def test_rate_has_traceable_numerator_and_denominator(store):
    _failures(store, 1)
    for i in range(3):
        store.ingest(event(20 + i, "auth.login.success", actor_ref="actor:bbbbbbbbbbbb"), NOW)
    rate = metrics(store, ORIGIN, 1, NOW + timedelta(seconds=1))["rates"][0]
    assert (rate["numerator"], rate["denominator"], rate["value"]) == (1, 4, 25.0)


def test_per_minute_request_counts_form_the_denominator(store):
    store.ingest(event(1, "api.request", source="api-gateway", count=2000), NOW)
    store.ingest(event(2, "authz.denied", source="api-gateway"), NOW)
    rates = {r["name"]: r for r in metrics(store, ORIGIN, 1, NOW + timedelta(seconds=1))["rates"]}
    assert rates["Refused calls"]["value"] == 0.5


# ---- anomalies
def _history(store, hours, value, types=("authz.denied",)):
    start = NOW.replace(minute=0, second=0, microsecond=0)
    number = 1000
    for offset in range(1, hours + 1):
        for t in types:
            for _ in range(value + offset % 2):
                number += 1
                store.buckets.update_one(
                    {"_id": f"{offset}|{t}"},
                    {"$inc": {"count": 1}, "$setOnInsert": {"hour": start - timedelta(hours=offset), "origin": ORIGIN, "event_type": t}},
                    upsert=True,
                )


def _series(result, name):
    return next(s for s in result["series"] if s["series"] == name)


def test_cold_start_says_insufficient_baseline(store):
    _history(store, 10, 3)
    item = _series(anomalies(store, ORIGIN, NOW), "Refused calls")
    assert item["state"] == "INSUFFICIENT_BASELINE" and item["modified_z"] is None


def test_no_data_at_all_is_insufficient_not_normal(store):
    assert {s["state"] for s in anomalies(store, ORIGIN, NOW)["series"]} == {"INSUFFICIENT_BASELINE"}


def test_a_real_spike_is_reported_with_its_baseline(store):
    _history(store, 72, 3)
    for i in range(60):
        store.ingest(event(i + 1, "authz.denied", source="api-gateway"), NOW)
    item = _series(anomalies(store, ORIGIN, NOW), "Refused calls")
    assert item["state"] == "ANOMALY" and item["method"] == ANOMALY_METHOD
    assert item["median"] is not None and item["modified_z"] >= 3.5 and item["baseline_hours"] >= 48


def test_small_rise_on_a_quiet_series_is_not_an_anomaly(store):
    _history(store, 72, 0)
    for i in range(6):
        store.ingest(event(i + 1, "authz.denied", source="api-gateway"), NOW)
    assert _series(anomalies(store, ORIGIN, NOW), "Refused calls")["state"] == "NORMAL"


def test_slow_drift_does_not_alarm(store):
    _history(store, 72, 20)
    for i in range(22):
        store.ingest(event(i + 1, "authz.denied", source="api-gateway"), NOW)
    assert _series(anomalies(store, ORIGIN, NOW), "Refused calls")["state"] == "NORMAL"


# ---- coverage
def test_silent_source_lowers_monitoring_coverage(store):
    store.record_source("identity-service", "t", {"backlog": 0, "dropped": 0, "delivery_failures": 0}, 1, 0, 0, NOW)
    store.ingest(event(1, "auth.login.failure", actor_ref="actor:aaaaaaaaaaaa"), NOW)
    result = monitoring_coverage(store, ORIGIN, NOW)
    states = {d["domain"]: d["state"] for d in result["domains"]}
    assert states["Authentication"] == "VERIFIED"
    assert states["Credential revocation"] == "NO_EVENTS_SEEN"
    assert states["Guardian recovery"] == "SOURCE_MISSING"
    assert result["numerator"] == 1 and result["denominator"] == len(REQUIRED_DOMAINS)


def test_stale_source_is_not_verified(store):
    store.record_source("identity-service", "t", {"backlog": 0, "dropped": 0, "delivery_failures": 0}, 1, 0, 0, NOW - timedelta(hours=1))
    store.ingest(event(1, "auth.login.failure", actor_ref="actor:aaaaaaaaaaaa"), NOW)
    states = {d["domain"]: d["state"] for d in monitoring_coverage(store, ORIGIN, NOW)["domains"]}
    assert states["Authentication"] == "SOURCE_STALE"


def test_posture_counts_only_l3_and_keeps_open_findings_visible(store):
    body = posture(store, ORIGIN, NOW)
    verified = body["verified_control_coverage"]
    assert 0 < verified["numerator"] < verified["denominator"]
    assert all(item["level"] not in ("L3", "L4") for item in body["not_verified"])
    assert body["open_findings"]["critical_and_high"]
    assert body["test_pass_rate"]["denominator"] == body["test_pass_rate"]["numerator"] + body["test_pass_rate"]["failed"]
    assert "secure" not in " ".join(k for k in body)


# ---- risk contract
def test_recovery_risk_uses_real_history_and_outage_is_503(client, store, monkeypatch):
    subject = "recovery:" + "a" * 64
    headers = {"X-Internal-Service-Token": TOKEN}
    body = {"did": subject, "action": "recovery_request"}
    clean = client.post("/api/v1/fraud/evaluate", headers=headers, json=body).json()
    assert clean["risk_level"] == "LOW" and clean["data_quality"] == "PLATFORM_HISTORY"
    for i in range(5):
        store.ingest(event(i + 1, "recovery.proof_rejected", source="recovery-service", resource_ref=subject), NOW)
    risky = client.post("/api/v1/fraud/evaluate", headers=headers, json=body).json()
    assert risky["risk_level"] != "LOW" and "FAILED_ATTEMPTS" in risky["reason_codes"]
    assert risky["assessment_mode"] == "RULE_BASED" and "probability" in risky["score_semantics"].lower()
    assert store.assessments.rows[-1]["subject_scope"] == subject

    def down():
        raise IntelUnavailableError("UNAVAILABLE")

    monkeypatch.setattr(runtime, "store", down)
    assert client.post("/api/v1/fraud/evaluate", headers=headers, json=body).status_code == 503


def test_model_status_stays_not_trained(client, store, admin):
    body = client.get("/api/v1/fraud/intel/model").json()
    assert body["model_status"] == "NOT_TRAINED" and body["metrics"] is None
    assert body["detection_mode"] == "RULE_BASED_AND_STATISTICAL"
