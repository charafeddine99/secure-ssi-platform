from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import run_tests


def test_runner_uses_repository_paths_and_working_directory() -> None:
    with patch.object(run_tests.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
        exit_code, results = run_tests.run_services(("packages/shared/tests",))

    assert exit_code == 0
    assert results == {"packages/shared/tests": 0}
    args, kwargs = run.call_args
    assert args[0][0:3] == [run_tests.sys.executable, "-m", "pytest"]
    assert Path(args[0][3]) == run_tests.REPOSITORY_ROOT / "packages/shared/tests"
    assert kwargs["cwd"] == run_tests.REPOSITORY_ROOT
    assert kwargs["check"] is False


def test_runner_continues_after_a_failure_and_preserves_first_exit_code() -> None:
    return_codes = iter((1, 0))
    with patch.object(
        run_tests.subprocess,
        "run",
        side_effect=lambda *args, **kwargs: SimpleNamespace(returncode=next(return_codes)),
    ) as run:
        exit_code, results = run_tests.run_services(
            ("services/identity-service", "services/recovery-service")
        )

    assert run.call_count == 2
    assert results == {"services/identity-service": 1, "services/recovery-service": 0}
    assert exit_code == 1


def test_runner_reports_interrupt_and_no_tests_exit_codes() -> None:
    assert run_tests.PYTEST_EXIT_CODES[2] == "test execution was interrupted"
    assert run_tests.PYTEST_EXIT_CODES[5] == "no tests were collected"
