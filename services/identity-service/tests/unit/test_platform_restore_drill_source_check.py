from app.tools.platform_restore_drill import (
    APPEND_ONLY_COLLECTIONS,
    compare_source,
)


def test_identical_counts_pass() -> None:
    counts = {"audit_events": 10, "audit_outbox": 10, "credentials": 3}
    result = compare_source(counts, dict(counts))
    assert result == {"unchanged": True, "changed": [], "appendOnlyGrowth": {}}


def test_append_only_growth_is_reported_but_passes() -> None:
    before = {"audit_events": 10, "audit_outbox": 10, "credentials": 3}
    after = {"audit_events": 12, "audit_outbox": 12, "credentials": 3}
    result = compare_source(before, after)
    assert result["unchanged"] is True
    assert result["appendOnlyGrowth"] == {"audit_events": 2, "audit_outbox": 2}


def test_any_other_change_fails() -> None:
    before = {"audit_events": 10, "credentials": 3, "wallets": 2}
    after = {"audit_events": 10, "credentials": 4, "users": 1, "wallets": 2}
    result = compare_source(before, after)
    assert result["unchanged"] is False
    assert result["changed"] == ["credentials", "users"]


def test_append_only_collections_must_not_shrink_or_disappear() -> None:
    before = {"audit_events": 10, "audit_outbox": 10}
    assert compare_source(before, {"audit_events": 9, "audit_outbox": 10})[
        "changed"
    ] == ["audit_events"]
    assert compare_source(before, {"audit_events": 10})["changed"] == [
        "audit_outbox"
    ]


def test_only_the_audit_log_collections_are_append_only() -> None:
    assert APPEND_ONLY_COLLECTIONS == {"audit_events", "audit_outbox"}
