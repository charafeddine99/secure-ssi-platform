import importlib
from pathlib import Path

import app.core.config as config


def test_config_import_does_not_require_writable_application_directory(monkeypatch) -> None:
    def deny_directory_creation(*_args, **_kwargs) -> None:
        raise OSError("application filesystem is read-only")

    monkeypatch.setattr(Path, "mkdir", deny_directory_creation)

    reloaded = importlib.reload(config)

    assert reloaded.MODEL_DIR == reloaded.BASE_DIR / "models"
