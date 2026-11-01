"""Revocation anchoring is optional, environment-driven and never blocks the revocation."""

from app.api.v1 import dependencies
from app.infrastructure import cache_and_anchor


class _Manager:
    @property
    def database(self):
        raise RuntimeError("must not be touched when anchoring is disabled")


def test_scheduler_is_off_unless_blockchain_is_enabled(monkeypatch):
    monkeypatch.delenv("BLOCKCHAIN_ENABLED", raising=False)
    assert dependencies.get_revocation_anchor_scheduler(manager=_Manager()) is None


def test_scheduler_failure_is_swallowed_and_logged(monkeypatch):
    monkeypatch.setenv("BLOCKCHAIN_ENABLED", "true")
    anchor = dependencies.get_revocation_anchor_scheduler(manager=_Manager())
    assert anchor is not None
    anchor("urn:uuid:1", "reason")  # database access fails inside; must not raise


def test_quarantine_client_reads_environment_settings(monkeypatch):
    monkeypatch.setenv("BLOCKCHAIN_RPC_URL", "http://chain.invalid:8546")
    client = cache_and_anchor.BlockchainAnchorClient()
    assert client.rpc_url == "http://chain.invalid:8546"
