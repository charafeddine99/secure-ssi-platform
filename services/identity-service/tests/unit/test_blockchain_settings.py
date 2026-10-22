from pathlib import Path

from app.config import blockchain_settings


def test_settings_loader_handles_shallow_container_package_path(monkeypatch, tmp_path):
    container_module_path = Path("/app/app/config/blockchain_settings.py")
    assert len(container_module_path.resolve().parents) == 4

    monkeypatch.setattr(
        blockchain_settings,
        "__file__",
        str(container_module_path),
    )
    monkeypatch.setattr(
        blockchain_settings.Path,
        "cwd",
        classmethod(lambda _cls: tmp_path),
    )

    settings = blockchain_settings.load_blockchain_settings(environ={})

    assert settings.rpc_url == "http://127.0.0.1:8545"


def test_blockchain_is_disabled_and_has_no_default_signer():
    settings = blockchain_settings.load_blockchain_settings(environ={})

    assert settings.enabled is False
    assert settings.private_key == ""


def test_blockchain_requires_explicit_opt_in_and_signer():
    settings = blockchain_settings.load_blockchain_settings(
        environ={
            "BLOCKCHAIN_ENABLED": "true",
            "BLOCKCHAIN_PRIVATE_KEY": "test-only-explicit-key",
        }
    )

    assert settings.enabled is True
    assert settings.private_key == "test-only-explicit-key"
