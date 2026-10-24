"""Run each Secure SSI Platform pytest tree independently.

Separate pytest invocations prevent multi-root ``app`` namespace collisions.
This runner reports test outcomes; it does not measure code coverage.
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent
SERVICES = (
    "services/identity-service",
    "services/recovery-service",
    "services/fraud-service",
    "services/api-gateway",
    "packages/shared/tests",
    "tests",
)

PYTEST_EXIT_CODES = {
    0: "all collected tests passed",
    1: "one or more tests failed",
    2: "test execution was interrupted",
    3: "pytest internal error",
    4: "pytest usage error",
    5: "no tests were collected",
    6: "pytest maximum warning threshold was exceeded",
}


def run_services(services: tuple[str, ...]) -> tuple[int, dict[str, int]]:
    results: dict[str, int] = {}
    aggregate_exit = 0

    for service in services:
        test_path = REPOSITORY_ROOT / service
        print(f"\n{'=' * 20} Running tests for {service} {'=' * 20}", flush=True)
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-q"],
            cwd=REPOSITORY_ROOT,
            check=False,
        )
        results[service] = proc.returncode
        # Keep the first non-zero pytest code while still running every suite.
        if aggregate_exit == 0 and proc.returncode != 0:
            aggregate_exit = proc.returncode

    return aggregate_exit, results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Secure SSI Platform pytest trees independently."
    )
    parser.add_argument(
        "--service",
        action="append",
        choices=SERVICES,
        help="run only this test tree; repeat to select multiple trees",
    )
    args = parser.parse_args(argv)
    services = tuple(args.service) if args.service else SERVICES

    aggregate_exit, results = run_services(services)

    print(f"\n{'=' * 20} Test Summary {'=' * 20}", flush=True)
    for service, code in results.items():
        if code == 0:
            status = "PASS"
        else:
            description = PYTEST_EXIT_CODES.get(code, "pytest/plugin-specific error")
            status = f"NON-PASS (exit {code}: {description})"
        print(f"  {service}: {status}", flush=True)
    print(f"Aggregate exit code: {aggregate_exit}", flush=True)
    return aggregate_exit

if __name__ == "__main__":
    sys.exit(main())
