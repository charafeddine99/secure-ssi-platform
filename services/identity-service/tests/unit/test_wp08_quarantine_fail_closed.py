from unittest.mock import MagicMock

import pytest

from app.application.services.oid4vp_service import _read_quarantine_status
from app.infrastructure.cache_and_anchor import BlockchainAnchorClient


def test_quarantine_lookup_exception_is_indeterminate() -> None:
    quarantine_service = MagicMock()
    quarantine_service.is_quarantined.side_effect = TimeoutError(
        "lookup timed out"
    )

    status, reason = _read_quarantine_status(
        quarantine_service,
        "did:example:holder-1",
    )

    assert status is None
    assert reason == "QUARANTINE_LOOKUP_FAILED:TimeoutError"


def test_quarantine_lookup_rejects_missing_or_non_boolean_result() -> None:
    assert _read_quarantine_status(object(), "did:example:holder-1") == (
        None,
        "QUARANTINE_LOOKUP_UNAVAILABLE",
    )
    assert _read_quarantine_status(
        MagicMock(is_quarantined=MagicMock(return_value=None)),
        "did:example:holder-1",
    ) == (None, "QUARANTINE_LOOKUP_INVALID_RESULT")


def test_quarantine_lookup_preserves_boolean_results() -> None:
    clear_service = MagicMock(is_quarantined=MagicMock(return_value=False))
    quarantined_service = MagicMock(is_quarantined=MagicMock(return_value=True))

    assert _read_quarantine_status(clear_service, "did:example:holder-1") == (
        False,
        None,
    )
    assert _read_quarantine_status(
        quarantined_service,
        "did:example:holder-1",
    ) == (True, None)


def test_optional_anchor_status_is_not_quarantine_authority() -> None:
    client = BlockchainAnchorClient()
    bridge = MagicMock()
    bridge.is_quarantined_on_chain.side_effect = TimeoutError("RPC timed out")
    client._bridge = bridge

    assert client.is_quarantined("0x0000000000000000000000000000000000000001") is False
    bridge.is_quarantined_on_chain.assert_not_called()

    client._quarantined_subjects.add("did:key:z6MkuLocalQuarantine")
    assert client.is_quarantined("did:key:z6MkuLocalQuarantine") is True
