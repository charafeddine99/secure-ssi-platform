#!/usr/bin/env python3
"""
================================================================================
SECURE SELF-SOVEREIGN IDENTITY (SSI) PLATFORM
ACADEMIC GRADUATION DEMONSTRATION & ORCHESTRATION ENGINE (SPRINT 23)
================================================================================
Purpose:
  Provides a one-click startup, status monitoring, automated golden-path scenario
  execution, and demo reset capabilities for thesis defense presentation.

Usage:
  python scripts/start_demo.py status      # Check health of all services
  python scripts/start_demo.py flow        # Run automated 8-step graduation demo flow
  python scripts/start_demo.py start-local # Instructions and commands to launch local stack
  python scripts/start_demo.py reset       # Reset local demo data fixtures
================================================================================
"""

import sys
import os
import time
import json
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent

# ANSI styling
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

SERVICES = [
    {"name": "Frontend Web Cockpit", "port": 5173, "url": "http://localhost:5173"},
    {"name": "API Gateway", "port": 8000, "url": "http://localhost:8000/health"},
    {"name": "Identity Service (W3C VC / DID)", "port": 8001, "url": "http://localhost:8001/health"},
    {"name": "Fraud Detection Service (AI)", "port": 8002, "url": "http://localhost:8002/health"},
    {"name": "Recovery Service (3/5 Shamir)", "port": 8003, "url": "http://localhost:8003/health"}
]

DEMO_ACCOUNTS = [
    {
        "role": "HOLDER",
        "name": "Demo Holder (Student / Citizen)",
        "email": "holder@example.test",
        "pass": "Holder-Prototype-2026!",
        "portal": "http://localhost:5173/wallet",
        "actions": "Inspect did:key, receive credentials, selective disclosure"
    },
    {
        "role": "ISSUER",
        "name": "Demo University Authority",
        "email": "issuer@example.test",
        "pass": "Issuer-Prototype-2026!",
        "portal": "http://localhost:5173/issuer",
        "actions": "Issue W3C VC 2.0 degree, manage status list, revoke credentials"
    },
    {
        "role": "VERIFIER",
        "name": "Demo Company Compliance",
        "email": "verifier@example.test",
        "pass": "Verifier-Prototype-2026!",
        "portal": "http://localhost:5173/verifier",
        "actions": "Create OID4VP presentation request, 9-point trust validation"
    },
    {
        "role": "GUARDIAN",
        "name": "Demo Quorum Guardian #1",
        "email": "admin@example.test",
        "pass": "Admin-Prototype-2026!",
        "portal": "http://localhost:5173/guardian",
        "actions": "Approve social recovery petitions with Shamir key shares"
    },
    {
        "role": "ADMIN",
        "name": "Demo Platform Administrator",
        "email": "admin@example.test",
        "pass": "Admin-Prototype-2026!",
        "portal": "http://localhost:5173/admin",
        "actions": "Platform overview, smart contract events, AI threat stream"
    }
]


def check_url(url, timeout=3):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SSI-Demo-Check"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 204, 304)
    except Exception:
        return False


def cmd_status():
    print(f"\n{BOLD}{CYAN}=== SECURE SSI PLATFORM: SERVICE HEALTH MONITOR ==={RESET}\n")
    all_ok = True
    for s in SERVICES:
        alive = check_url(s["url"])
        status_badge = f"{GREEN}[ONLINE - HTTP 200]{RESET}" if alive else f"{RED}[OFFLINE]{RESET}"
        if not alive:
            all_ok = False
        print(f"  {s['name']:<35} [Port {s['port']:<4}] -> {status_badge}")
        print(f"    URL: {s['url']}")

    print(f"\n{BOLD}Documented Demo Accounts [DEMO ENVIRONMENT]:{RESET}")
    print(f"{'Role':<10} {'Email':<24} {'Password':<24} {'Portal'}")
    print("-" * 80)
    for a in DEMO_ACCOUNTS:
        print(f"{a['role']:<10} {a['email']:<24} {a['pass']:<24} {a['portal']}")

    return 0 if all_ok else 1


def cmd_flow():
    print(f"\n{BOLD}{CYAN}=== LAUNCHING AUTOMATED 8-STEP GOLDEN SSI DEMO SCENARIO ==={RESET}\n")
    demo_script = ROOT_DIR / "scripts" / "demo_runner.py"
    if not demo_script.exists():
        print(f"{RED}Error: demo_runner.py not found at {demo_script}{RESET}")
        return 1

    py_exe = sys.executable
    print(f"{BLUE}Executing {demo_script} using Python interpreter: {py_exe}{RESET}\n")
    res = subprocess.run([py_exe, str(demo_script)])
    return res.returncode


def cmd_reset():
    print(f"\n{BOLD}{YELLOW}=== RESETTING DEMO DATA & LOCAL STORAGE STATE ==={RESET}\n")
    print("1. Local demo fallback credentials in web cockpit will reset on page reload.")
    print("2. Browser LocalStorage keys to clear: 'secure_ssi_user', 'ssi_access_token', 'secure_ssi_token'.")
    print("3. Backend synthetic users are stateless (Argon2id in-memory registry) and require no DB purge.")
    
    # Check if local test sqlite db exists and clean backup if requested
    db_file = ROOT_DIR / "services" / "identity-service" / "secure_ssi_database.db"
    if db_file.exists():
        print(f"  • Found local identity SQLite database: {db_file.name}")
        print(f"  • Preserving database with zero-leakage invariant.")
    
    print(f"\n{GREEN}✔ Demo environment reset instructions complete.{RESET}\n")
    return 0


def cmd_start_local():
    print(f"\n{BOLD}{CYAN}=== SECURE SSI PLATFORM: LOCAL STARTUP GUIDE ==={RESET}\n")
    print(f"{BOLD}Option A: Native Local Host (Recommended for Windows):{RESET}")
    print("  Terminal 1 (Vite Web UI):")
    print("    cd apps/web && npm run dev")
    print("    -> Available at: http://localhost:5173\n")
    print("  Terminal 2 (API Gateway):")
    print("    cd services/api-gateway && ..\\..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000\n")
    print("  Terminal 3 (Identity Service):")
    print("    cd services/identity-service")
    print("    $env:FRAUD_INTERNAL_SERVICE_TOKEN = \"local-dev-fraud-service-token-not-for-production\"")
    print("    ..\\..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001\n")
    print("  Terminal 4 (Fraud Service):")
    print("    cd services/fraud-service")
    print("    $env:FRAUD_INTERNAL_SERVICE_TOKEN = \"local-dev-fraud-service-token-not-for-production\"")
    print("    ..\\..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002\n")
    print("  Terminal 5 (Recovery Service):")
    print("    cd services/recovery-service && ..\\..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8003\n")
    print(f"{BOLD}Option B: Docker Compose (When Docker is installed):{RESET}")
    print("    docker compose up --build")
    print("    -> Frontend at: http://localhost:3000")
    print("    -> Gateway at: http://localhost:8000\n")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Secure SSI Platform Demo Runner")
    parser.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "flow", "reset", "start-local"],
        help="Action to perform (default: status)"
    )
    args = parser.parse_args()

    if args.action == "status":
        sys.exit(cmd_status())
    elif args.action == "flow":
        sys.exit(cmd_flow())
    elif args.action == "reset":
        sys.exit(cmd_reset())
    elif args.action == "start-local":
        sys.exit(cmd_start_local())


if __name__ == "__main__":
    main()
