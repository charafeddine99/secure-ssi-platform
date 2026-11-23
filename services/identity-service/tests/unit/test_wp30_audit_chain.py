"""Audit chain: edits, removals and reordering are detected."""

from datetime import UTC, datetime

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.infrastructure.persistence.audit_chain import (
    GENESIS,
    AuditChain,
    derive_chain_key,
)


class _Cursor(list):
    def sort(self, field, direction):
        return _Cursor(sorted(self, key=lambda d: d[field], reverse=direction < 0))

    def limit(self, count):
        return _Cursor(self[:count])


class _Collection:
    def __init__(self):
        self.rows = []
        self.collisions = 0

    def insert_one(self, document):
        if self.collisions:
            self.collisions -= 1
            raise DuplicateKeyError("uq_audit_events_chain_seq chainSeq")
        self.rows.append(dict(document))

    def count_documents(self, filters):
        return len([r for r in self.rows if not filters or "chainSeq" in r])

    def find(self, _filter):
        return _Cursor(r for r in self.rows if "chainSeq" in r)


def _event(name="LOGIN"):
    now = datetime(2026, 11, 4, 12, 0, 0, 123456, tzinfo=UTC)
    return {"_id": ObjectId(), "eventType": name, "metadata": {"a": "b"}, "createdAt": now}


def _filled(count=3):
    collection = _Collection()
    chain = AuditChain(collection, derive_chain_key(b"k" * 32))
    for _ in range(count):
        chain.insert(_event())
    return collection, chain


def test_a_clean_chain_is_intact() -> None:
    collection, chain = _filled()
    report = chain.verify()
    assert (report.status, report.checked, report.unchained) == ("INTACT", 3, 0)
    assert collection.rows[0]["chainPrev"] == GENESIS


def test_edit_is_detected() -> None:
    collection, chain = _filled()
    collection.rows[1]["metadata"]["a"] = "changed"
    report = chain.verify()
    assert (report.status, report.first_broken_sequence) == ("BROKEN", 2)


def test_removal_from_the_middle_is_detected() -> None:
    collection, chain = _filled()
    del collection.rows[1]
    assert chain.verify().status == "BROKEN"


def test_a_different_key_cannot_confirm_the_chain() -> None:
    collection, _ = _filled()
    other = AuditChain(collection, derive_chain_key(b"z" * 32))
    assert other.verify().status == "BROKEN"


def test_stored_time_precision_does_not_break_the_chain() -> None:
    collection, chain = _filled(1)
    row = collection.rows[0]
    row["createdAt"] = row["createdAt"].replace(microsecond=123000, tzinfo=None)
    assert chain.verify().status == "INTACT"


def test_every_millisecond_value_survives_storage() -> None:
    collection, chain = _Collection(), None
    chain = AuditChain(collection, derive_chain_key(b"k" * 32))
    for millisecond in range(0, 1000, 7):
        event = _event()
        event["createdAt"] = event["createdAt"].replace(microsecond=millisecond * 1000 + 456)
        chain.insert(event)
    for row in collection.rows:
        stored = row["createdAt"].microsecond // 1000 * 1000
        row["createdAt"] = row["createdAt"].replace(microsecond=stored, tzinfo=None)
    assert chain.verify().status == "INTACT"


def test_concurrent_writer_retries_with_the_next_sequence() -> None:
    collection, chain = _filled(1)
    collection.collisions = 2
    chain.insert(_event())
    assert [r["chainSeq"] for r in collection.rows] == [1, 2]


def test_a_duplicate_event_id_is_not_retried() -> None:
    collection, chain = _filled(1)

    def refuse(_document):
        raise DuplicateKeyError("_id_ dup")

    collection.insert_one = refuse
    with pytest.raises(DuplicateKeyError):
        chain.insert(_event())


def test_older_events_are_counted_as_unchained() -> None:
    collection, chain = _filled(1)
    collection.rows.append(_event("OLD"))
    assert chain.verify().unchained == 1
