"""
Secure SSI Platform - SQLite Database Layer
Handles permanent relational persistence for:
- Users (Accounts, DIDs, Seed Phrases, EVM Wallets)
- Verifiable Credentials (W3C JSON-LD, Claims, Status, Ed25519 Proofs)
- Emergency Recovery Guardians (EIP-4337 Multi-Sig)
- Audit & Security Logs (AI Fraud Assessments & Quarantine events)
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

DB_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "secure_ssi_database.db"
)

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def initialize_database():
    """Initializes tables and seeds initial academic & government credentials if empty."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        student_id TEXT,
        department TEXT,
        did TEXT UNIQUE NOT NULL,
        wallet_address TEXT UNIQUE NOT NULL,
        seed_phrase TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # 2. Verifiable Credentials table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS credentials (
        id TEXT PRIMARY KEY,
        user_did TEXT NOT NULL,
        wallet_address TEXT NOT NULL,
        credential_type TEXT NOT NULL,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        issuer TEXT NOT NULL,
        issuer_name TEXT NOT NULL,
        issued_date TEXT NOT NULL,
        expiry_date TEXT,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        claims_json TEXT NOT NULL,
        proof_value TEXT NOT NULL,
        ai_risk_score INTEGER DEFAULT 0,
        zkp_predicate TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # 3. Emergency Recovery Guardians table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS guardians (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wallet_address TEXT NOT NULL,
        guardian_name TEXT NOT NULL,
        guardian_role TEXT NOT NULL,
        guardian_did TEXT NOT NULL,
        guardian_address TEXT,
        approved INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """)

    # 4. Audit & AI Fraud logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        actor_did TEXT,
        target_wallet TEXT,
        risk_score INTEGER,
        details_json TEXT,
        created_at TEXT NOT NULL
    );
    """)

    conn.commit()

    # Seed initial user and credentials if database is freshly created
    cursor.execute("SELECT COUNT(*) FROM users WHERE email = 'b210109591@subu.edu.tr'")
    if cursor.fetchone()[0] == 0:
        now_iso = datetime.now(timezone.utc).isoformat()
        demo_did = "did:key:z6MkuBesnaStudentKey2026SUBUEVM"
        demo_wallet = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

        cursor.execute("""
        INSERT INTO users (email, password_hash, name, student_id, department, did, wallet_address, seed_phrase, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "b210109591@subu.edu.tr",
            hash_password("123456"),
            "Charaf Eddine Bessanane",
            "B210109591",
            "Bilgisayar Mühendisliği",
            demo_did,
            demo_wallet,
            "apple banana cherry dolphin eagle falcon gorilla horizon island jungle knight leopard",
            now_iso
        ))

        # Seed initial 6 government & academic credentials
        initial_creds = [
            (
                "urn:uuid:subu-diploma-2026-b210109591",
                demo_did,
                demo_wallet,
                "UniversityDegreeCredential",
                "Bilgisayar Mühendisliği Lisans Diploması",
                "EDUCATION",
                "did:web:subu.edu.tr",
                "Sakarya Uygulamalı Bilimler Üniversitesi",
                "2026-06-25",
                "Süresiz",
                "ACTIVE",
                json.dumps({
                    "Öğrenci Adı": "Charaf Eddine Bessanane",
                    "Öğrenci No": "B210109591",
                    "Fakülte": "Teknoloji Fakültesi",
                    "Bölüm": "Bilgisayar Mühendisliği",
                    "Derece": "Lisans (B.Sc.)",
                    "GPA": "3.82 / 4.00",
                    "Mezuniyet": "Yüksek Onur Derecesi",
                    "T.C. Kimlik": "12345678901"
                }),
                "z3s9PqRtXvM8SUBUSignedProofValueValidW3C2026Ed25519",
                8,
                "GPA >= 3.00 && Derece == 'Lisans'",
                now_iso
            ),
            (
                "urn:uuid:nvi-kimlik-kart-2026-tr",
                demo_did,
                demo_wallet,
                "NationalIdCredential",
                "T.C. Dijital Ulusal Kimlik Kartı",
                "IDENTITY",
                "did:gov:tr:nvi",
                "T.C. Nüfus ve Vatandaşlık İşleri Genel Müdürlüğü",
                "2024-01-15",
                "2034-01-15",
                "ACTIVE",
                json.dumps({
                    "T.C. Kimlik No": "12345678901",
                    "Adı Soyadı": "Charaf Eddine Bessanane",
                    "Uyruk": "T.C.",
                    "Doğum Yeri": "Sakarya",
                    "Doğum Tarihi": "2003-11-12",
                    "Anne Adı": "Fatma",
                    "Baba Adı": "Mustafa",
                    "Seri No": "A24K98120"
                }),
                "z3sNVITurkeyNationalIdVerifiedEd25519Seal2026",
                5,
                "Uyruk == 'T.C.' && Kimlik Kartı Aktif",
                now_iso
            ),
            (
                "urn:uuid:egm-pasaport-2026-tur",
                demo_did,
                demo_wallet,
                "PassportCredential",
                "Biyometrik Dijital Pasaport",
                "TRAVEL",
                "did:gov:tr:egm-pasaport",
                "Emniyet Genel Müdürlüğü Pasaport Dairesi",
                "2024-05-10",
                "2034-05-10",
                "ACTIVE",
                json.dumps({
                    "Pasaport No": "U12345678",
                    "Ad Soyad": "Charaf Eddine Bessanane",
                    "Ülke Kodu": "TUR",
                    "Doğum Tarihi": "2003-11-12",
                    "Cinsiyet": "E",
                    "Pasaport Türü": "Bordo (Umuma Mahsus)",
                    "Biyometrik Çip İmzası": "0x7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1f"
                }),
                "z3sPassportBiometricChipVerifiedEd25519GovTR",
                11,
                "Yaş >= 18 (Reşitlik İspatı)",
                now_iso
            ),
            (
                "urn:uuid:trafik-ehliyet-2026-tr",
                demo_did,
                demo_wallet,
                "DriverLicenseCredential",
                "Dijital Sürücü Belgesi (Ehliyet)",
                "TRANSPORT",
                "did:gov:tr:trafik-tescil",
                "Emniyet Trafik Tescil Başkanlığı",
                "2023-08-20",
                "2033-08-20",
                "ACTIVE",
                json.dumps({
                    "Belge No": "TR-548912",
                    "Sürücü Adı": "Charaf Eddine Bessanane",
                    "Sınıflar": "B (Otomobil), A2 (Motosiklet)",
                    "Kan Grubu": "A Rh(+)",
                    "Ceza Puanı": "0"
                }),
                "z3sTrafficDirectorateDriverLicenseValidProofEd25519",
                6,
                "B Sınıfı Yetki == Aktif",
                now_iso
            ),
            (
                "urn:uuid:enabiz-saglik-2026-tr",
                demo_did,
                demo_wallet,
                "HealthCertificateCredential",
                "E-Nabız Dijital Sağlık ve Aşı Kartı",
                "HEALTH",
                "did:gov:tr:saglik-bakanligi",
                "T.C. Sağlık Bakanlığı E-Nabız",
                "2025-02-14",
                "2027-02-14",
                "ACTIVE",
                json.dumps({
                    "Hasta Adı": "Charaf Eddine Bessanane",
                    "Kan Grubu": "A Rh(+)",
                    "Aşı Durumu": "Tam Doz (3 Doz Tamamlandı)",
                    "Kronik Rahatsızlık": "Yok",
                    "Organ Bağışı": "Onaylı Bağışçı"
                }),
                "z3sHealthMinistryVaccineProofSignatureEd25519",
                9,
                "Kan Grubu == 'A Rh(+)' && Aşı Durumu == 'Tam'",
                now_iso
            ),
            (
                "urn:uuid:bddk-banka-kyc-2026",
                demo_did,
                demo_wallet,
                "BankKycCredential",
                "Banka KYC & Finansal Güvenlik Belgesi",
                "FINANCE",
                "did:bank:tr:bddk-finans",
                "BDDK ve Finansal Güven Kuruluşu",
                "2025-09-01",
                "2026-09-01",
                "ACTIVE",
                json.dumps({
                    "Müşteri Adı": "Charaf Eddine Bessanane",
                    "Onaylı IBAN": "TR56 0006 2000 0001 2345 6789 01",
                    "Kredi Güven Skoru": "1780 (Çok Yüksek / A+)",
                    "KYC Doğrulama Düzeyi": "Seviye-3 (Biyometrik Onaylı)"
                }),
                "z3sBankingKYCFTier3VerifiedSignatureEd25519",
                14,
                "Kredi Skoru >= 1500 && KYC Seviyesi >= 3",
                now_iso
            )
        ]

        cursor.executemany("""
        INSERT INTO credentials (
            id, user_did, wallet_address, credential_type, title, category,
            issuer, issuer_name, issued_date, expiry_date, status,
            claims_json, proof_value, ai_risk_score, zkp_predicate, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_creds)

        # Seed initial 3 guardians for social recovery
        initial_guardians = [
            (demo_wallet, "Dr. Danışman Hoca", "Akademik / Resmi Vasi", "did:key:z6MkuGuardian1Danisman", "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", 1, now_iso),
            (demo_wallet, "Nüfus & Güven Kurumu", "Kurumsal Onaycı", "did:key:z6MkuGuardian2Kurumsal", "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC", 1, now_iso),
            (demo_wallet, "Güvenilir Temsilci", "Bireysel Vasi", "did:key:z6MkuGuardian3Temsilci", "0x90F79bf6EB2c4f870365E785982E1f101E93b906", 0, now_iso)
        ]
        cursor.executemany("""
        INSERT INTO guardians (wallet_address, guardian_name, guardian_role, guardian_did, guardian_address, approved, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, initial_guardians)

        conn.commit()

    conn.close()

# Database helper functions
def db_register_user(name: str, student_id: str, email: str, department: str, password: str, did: str, wallet_address: str, seed_phrase: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    pwd_hash = hash_password(password)

    cursor.execute("""
    INSERT INTO users (email, password_hash, name, student_id, department, did, wallet_address, seed_phrase, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (email, pwd_hash, name, student_id, department, did, wallet_address, seed_phrase, now_iso))
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    return {
        "id": user_id,
        "email": email,
        "name": name,
        "studentId": student_id,
        "department": department,
        "did": did,
        "walletAddress": wallet_address,
        "seedPhrase": seed_phrase
    }

def db_authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)

    cursor.execute("SELECT * FROM users WHERE email = ? AND password_hash = ?", (email, pwd_hash))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "studentId": row["student_id"],
            "department": row["department"],
            "did": row["did"],
            "walletAddress": row["wallet_address"],
            "seedPhrase": row["seed_phrase"]
        }
    return None

def db_get_user_by_did(did: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE did = ?", (did,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "studentId": row["student_id"],
            "department": row["department"],
            "did": row["did"],
            "walletAddress": row["wallet_address"]
        }
    return None

def db_save_credential(cred: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
    INSERT OR REPLACE INTO credentials (
        id, user_did, wallet_address, credential_type, title, category,
        issuer, issuer_name, issued_date, expiry_date, status,
        claims_json, proof_value, ai_risk_score, zkp_predicate, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        cred["id"],
        cred.get("user_did", ""),
        cred.get("wallet_address", ""),
        cred.get("credential_type", "IdentityVerificationCredential"),
        cred.get("title", "Doğrulanabilir Belge"),
        cred.get("category", "IDENTITY"),
        cred.get("issuer", ""),
        cred.get("issuer_name", ""),
        cred.get("issued_date", now_iso[:10]),
        cred.get("expiry_date", "2034-01-01"),
        cred.get("status", "ACTIVE"),
        json.dumps(cred.get("claims", {})),
        cred.get("proof_value", ""),
        cred.get("ai_risk_score", 0),
        cred.get("zkp_predicate", ""),
        now_iso
    ))
    conn.commit()
    conn.close()

def get_hidden_fields_for_category(category: str) -> List[str]:
    mapping = {
        "IDENTITY": ["T.C. Kimlik No", "Anne Adı", "Baba Adı", "Seri No"],
        "TRAVEL": ["Pasaport No", "Doğum Tarihi", "Biyometrik Çip İmzası"],
        "TRANSPORT": ["Belge No", "Ceza Puanı"],
        "HEALTH": ["Kronik Rahatsızlık", "Organ Bağışı"],
        "FINANCE": ["Onaylı IBAN"],
        "EDUCATION": ["Öğrenci No", "Giriş Yılı"]
    }
    return mapping.get(category, ["T.C. Kimlik No"])

def db_get_credentials(user_did: Optional[str] = None, wallet_address: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_did and wallet_address:
        cursor.execute("SELECT * FROM credentials WHERE user_did = ? OR wallet_address = ? ORDER BY created_at DESC", (user_did, wallet_address))
    elif user_did:
        cursor.execute("SELECT * FROM credentials WHERE user_did = ? ORDER BY created_at DESC", (user_did,))
    elif wallet_address:
        cursor.execute("SELECT * FROM credentials WHERE wallet_address = ? ORDER BY created_at DESC", (wallet_address,))
    else:
        cursor.execute("SELECT * FROM credentials ORDER BY created_at DESC")

    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        claims = {}
        try:
            claims = json.loads(r["claims_json"])
        except Exception:
            pass

        cat = r["category"]
        result.append({
            "id": r["id"],
            "title": r["title"],
            "category": cat,
            "type": r["credential_type"],
            "issuer": r["issuer"],
            "issuerName": r["issuer_name"],
            "issuedDate": r["issued_date"],
            "expiryDate": r["expiry_date"],
            "status": r["status"],
            "claims": claims,
            "proofValue": r["proof_value"],
            "aiRiskScore": r["ai_risk_score"],
            "zkpRule": {
                "description": f"{r['title']} Doğrulama Kuralı",
                "predicate": r["zkp_predicate"] or "Kriptografik Ed25519 İspatı",
                "hiddenFields": get_hidden_fields_for_category(cat)
            }
        })
    return result

def db_revoke_credential(credential_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE credentials SET status = 'REVOKED' WHERE id = ?", (credential_id,))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    if rows_affected > 0:
        db_log_event(
            event_type="CREDENTIAL_REVOKED",
            actor_did="did:gov:tr:authority",
            target_wallet="",
            risk_score=0,
            details={"credential_id": credential_id, "action": "REVOCATION_STATUS_LIST_UPDATED"}
        )
    return rows_affected > 0

def db_get_guardians(wallet_address: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guardians WHERE wallet_address = ?", (wallet_address,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r["id"],
            "name": r["guardian_name"],
            "role": r["guardian_role"],
            "did": r["guardian_did"],
            "approved": bool(r["approved"])
        }
        for r in rows
    ]

def db_approve_guardian(guardian_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE guardians SET approved = 1 WHERE id = ?", (guardian_id,))
    conn.commit()
    conn.close()
    db_log_event(
        event_type="GUARDIAN_APPROVED",
        actor_did=f"guardian:{guardian_id}",
        target_wallet="",
        risk_score=0,
        details={"guardian_id": guardian_id, "threshold_met": True}
    )
    return True

def db_log_event(event_type: str, actor_did: str = "", target_wallet: str = "", risk_score: int = 0, details: Optional[Dict[str, Any]] = None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
        INSERT INTO audit_logs (event_type, actor_did, target_wallet, risk_score, details_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (event_type, actor_did, target_wallet, risk_score, json.dumps(details or {}), now_iso))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Audit log error: {e}")

def db_get_audit_logs(limit: int = 50) -> List[Dict[str, Any]]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r["id"],
                "event_type": r["event_type"],
                "actor_did": r["actor_did"],
                "target_wallet": r["target_wallet"],
                "risk_score": r["risk_score"],
                "details": json.loads(r["details_json"]) if r["details_json"] else {},
                "created_at": r["created_at"]
            }
            for r in rows
        ]
    except Exception:
        return []

def db_get_stats() -> Dict[str, int]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM credentials")
    creds_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM guardians")
    guardians_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM audit_logs")
    logs_count = cursor.fetchone()[0]
    conn.close()

    return {
        "users": users_count,
        "credentials": creds_count,
        "guardians": guardians_count,
        "audit_logs": logs_count
    }
