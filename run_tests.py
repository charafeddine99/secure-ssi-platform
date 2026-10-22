"""Run each Secure SSI Platform pytest tree independently.

Separate pytest invocations prevent multi-root ``app`` namespace collisions.
This runner reports test outcomes; it does not measure code coverage.
"""

import sys
import subprocess
from pathlib import Path

SERVICES = [
    "services/identity-service",
    "services/recovery-service",
    "services/fraud-service",
    "services/api-gateway",
    "packages/shared/tests",
    "tests",
]

def main() -> int:
    python_exe = sys.executable
    total_exit = 0
    results = {}

    for service in SERVICES:
        print(f"\n{'=' * 20} Running tests for {service} {'=' * 20}")
        proc = subprocess.run([python_exe, "-m", "pytest", service, "-q"], check=False)
        results[service] = proc.returncode
        if proc.returncode != 0:
            total_exit = proc.returncode

    print(f"\n{'=' * 20} Test Summary {'=' * 20}")
    for service, code in results.items():
        status = "PASSED" if code == 0 else f"FAILED (code {code})"
        print(f"  {service}: {status}")

    return total_exit

if __name__ == "__main__":
    sys.exit(main())
