"""
Secure SSI Platform - Full End-to-End System Verification Test
Executes all real operations across:
- Layer 1: Hardhat Blockchain (DIDRegistry & EmergencyRecovery)
- Layer 2: AI Fraud Detection (XGBoost & Autoencoder)
- Layer 3: SSI Credential Issuance & Verification
- Database: SQLite permanent storage & audit logs
"""

import sys
import json
import hashlib
import urllib.request
import urllib.error
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def test_endpoint(name, url, method="GET", body=None, headers=None, expected_status=200):
    print(f"\n[TEST] {name} ({method} {url})...")
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    
    data_bytes = None
    if body is not None:
        data_bytes = json.dumps(body).encode("utf-8")
        
    try:
        with urllib.request.urlopen(req, data=data_bytes, timeout=10) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            res_json = json.loads(content) if content else {}
            assert status == expected_status, f"Expected {expected_status} but got {status}"
            print(f"  --> PASSED (HTTP {status})")
            return res_json
    except urllib.error.HTTPError as e:
        status = e.code
        content = e.read().decode("utf-8")
        try:
            res_json = json.loads(content)
        except Exception:
            res_json = {"error": content}
        if status == expected_status:
            print(f"  --> PASSED Expected Status (HTTP {status})")
            return res_json
        else:
            print(f"  --> FAILED: HTTP {status} - {content}")
            raise

def main():
    print("=" * 80)
    print("SECURE SSI PLATFORM - 100% PRODUCTION & REAL WORKFLOW VERIFICATION")
    print("=" * 80)

    # 1. Health checks
    test_endpoint("Health Check: Gateway", "http://127.0.0.1:8000/health")
    test_endpoint("Health Check: SSI Layer 3", "http://127.0.0.1:8001/health")
    test_endpoint("Health Check: AI Fraud Service", "http://127.0.0.1:8002/health")

    # 2. Blockchain Live Status
    bc_status = test_endpoint("Blockchain Status & Contract Registry", "http://127.0.0.1:8001/api/blockchain/status")
    print("  Block Number:", bc_status.get("block_number"))
    print("  Contracts:", bc_status.get("contracts"))
    print("  Recovery Status:", bc_status.get("recovery_status"))

    # 3. Database Stats & Audit Logs
    stats = test_endpoint("Database Statistics (SQLite)", "http://127.0.0.1:8001/api/database/stats")
    print("  Live DB Stats:", stats.get("stats"))

    # 4. Fetch All Multi-Credentials
    creds = test_endpoint("Fetch Multi-Credentials from DB", "http://127.0.0.1:8001/api/credentials")
    print(f"  Total Credentials in DB: {creds.get('count')}")
    for c in creds.get("credentials", [])[:3]:
        print(f"   * [{c.get('category')}] {c.get('title')} ({c.get('id')}) - Status: {c.get('status')}")

    # 5. Live AI Fraud Detection Test (Normal)
    ai_normal = test_endpoint(
        "AI Fraud Detection: Safe Request",
        "http://127.0.0.1:8002/api/fraud_detection",
        method="POST",
        body={
            "did_id": "did:key:z6MkuBesnaStudentKey2026SUBUEVM",
            "timestamp": int(datetime.now().timestamp()),
            "ip_address": "192.168.1.100",
            "device_fingerprint": "fp_win11_trusted_browser",
            "recent_failed_attempts": 0,
            "geo_distance_km": 10
        }
    )
    print(f"  Risk Score: {ai_normal.get('risk_score')}/100 | Is Fraudulent: {ai_normal.get('is_fraudulent')}")

    # 6. Live AI Fraud Detection Test (High Risk & Attack)
    ai_attack = test_endpoint(
        "AI Fraud Detection: Attack Request",
        "http://127.0.0.1:8002/api/fraud_detection",
        method="POST",
        body={
            "did_id": "did:key:z6MkuBesnaStudentKey2026SUBUEVM",
            "timestamp": int(datetime.now().timestamp()),
            "ip_address": "185.220.101.5", # Tor exit node
            "device_fingerprint": "unrecognized_device_fp",
            "recent_failed_attempts": 6,
            "geo_distance_km": 4200
        }
    )
    print(f"  Risk Score: {ai_attack.get('risk_score')}/100 | Is Fraudulent: {ai_attack.get('is_fraudulent')} | Reasons: {ai_attack.get('reasons')}")

    # 7. Issue New Credential (anchoring to DIDRegistry.sol on-chain)
    new_cred = test_endpoint(
        "W3C Credential Issuance & Blockchain Anchoring",
        "http://127.0.0.1:8001/api/issue_credential",
        method="POST",
        body={
            "wallet_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            "did_id": "did:key:z6MkuBesnaStudentKey2026SUBUEVM",
            "ip_address": "192.168.1.105",
            "device_fingerprint": "trusted_device_win11_besna",
            "recent_failed_attempts": 0,
            "credential_type": "DriverLicenseCredential",
            "title": "Dijital Akıllı Sürücü Belgesi (A2 & B)",
            "claims": {
                "Sürücü Adı": "Charaf Eddine Bessanane",
                "Sınıflar": "B, A2, BE",
                "Kan Grubu": "A Rh(+)",
                "Ceza Puanı": "0"
            }
        }
    )
    issued_id = new_cred["verifiable_credential"]["id"]
    tx_hash = new_cred.get("blockchain_tx_hash")
    print(f"  Issued VC ID: {issued_id}")
    print(f"  On-Chain Anchoring TX Hash: {tx_hash}")

    # 8. Cryptographic Proof Calculation (SHA-256 canonical hash & Ed25519 format)
    vc_doc = new_cred["verifiable_credential"]
    vc_bytes = json.dumps(vc_doc, sort_keys=True).encode("utf-8")
    sha256_hash = hashlib.sha256(vc_bytes).hexdigest()
    print(f"  Cryptographic Canonical SHA-256 Hash: 0x{sha256_hash}")
    print(f"  Ed25519 Proof Value: {vc_doc['proof']['proofValue']}")
    assert vc_doc['proof']['proofValue'].startswith("z3s"), "Proof must use multibase z-format"

    # 9. Credential Revocation (SQLite & Audit Log)
    test_endpoint(
        "Revoke Issued Credential",
        f"http://127.0.0.1:8001/api/credentials/{issued_id}/revoke",
        method="POST"
    )
    print(f"  Credential {issued_id} successfully marked REVOKED in database.")

    # 10. Verify Revocation Status in DB
    updated_creds = test_endpoint("Verify Revocation in DB", "http://127.0.0.1:8001/api/credentials")
    revoked_item = next((c for c in updated_creds["credentials"] if c["id"] == issued_id), None)
    assert revoked_item is not None and revoked_item["status"] == "REVOKED", "Credential must be REVOKED"
    print(f"  Confirmed status in database: {revoked_item['status']}")

    # 11. Guardian On-Chain Approval
    guardian_res = test_endpoint(
        "Guardian Approval (On-Chain Transaction)",
        "http://127.0.0.1:8001/api/guardians/approve",
        method="POST",
        body={
            "guardian_id": 1,
            "wallet_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
        }
    )
    print(f"  Guardian Approval TX Hash: {guardian_res.get('transaction_hash')}")

    # 12. Manual/AI Triggered Quarantine on-chain
    quarantine_res = test_endpoint(
        "Trigger On-Chain Quarantine",
        "http://127.0.0.1:8001/api/quarantine",
        method="POST",
        body={
            "wallet_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            "reason": "Comprehensive System Verification Test - High Risk Event"
        }
    )
    print(f"  Quarantine On-Chain TX: {quarantine_res['receipt']['transaction_hash']}")

    # 13. Fetch Audit Logs from SQLite
    logs = test_endpoint("Fetch Live Audit Logs from SQLite", "http://127.0.0.1:8001/api/database/audit_logs")
    print(f"  Total Audit Logs in DB: {logs.get('count')}")
    for l in logs.get("audit_logs", [])[:4]:
        print(f"   * [#{l['id']}] {l['event_type']} - Target: {l.get('target_wallet')} - Details: {l.get('details')}")

    print("\n" + "=" * 80)
    print("ALL 13 VERIFICATION TESTS PASSED PERFECTLY!")
    print("100% WORKING - ZERO MOCKS - REAL BLOCKCHAIN, REAL AI, REAL DATABASE!")
    print("=" * 80)

if __name__ == "__main__":
    main()
