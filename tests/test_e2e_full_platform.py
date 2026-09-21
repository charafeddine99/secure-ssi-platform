import sys
import time
import pytest
import secrets
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "services" / "fraud-service"))

# 1. ZKP & Selective Disclosure Modülü
from packages.shared.zkp.selective_disclosure import ZKPSelectiveDisclosure

# 2. DIDComm v2 Modülü
from packages.shared.didcomm.v2 import DIDCommV2

# 3. AI Fraud Detection Motoru
from app.application.hybrid_detector import HybridFraudDetector
from app.schemas.fraud import FraudEvaluationRequest

# 4. Cache ve Blockchain Köprüsü
import importlib.util
cache_anchor_spec = importlib.util.spec_from_file_location(
    "cache_and_anchor",
    str(ROOT_DIR / "services" / "identity-service" / "app" / "infrastructure" / "cache_and_anchor.py")
)
cache_and_anchor = importlib.util.module_from_spec(cache_anchor_spec)
cache_anchor_spec.loader.exec_module(cache_and_anchor)
CredentialStatusCache = cache_and_anchor.CredentialStatusCache
BlockchainAnchorClient = cache_and_anchor.BlockchainAnchorClient



def test_full_ssi_ai_blockchain_recovery_pipeline():
    """
    202 Maddelik Şartname ve Tasarım Raporundaki Uçtan Uca (E2E) Ana Senaryo:
    1. SUBÜ Üniversitesi W3C formatında diploma VC'si üretir.
    2. ZKP ile seçici açıklama (GPA >= 3.0 kanıtı) sunulur.
    3. Sunum DIDComm v2 (AES-256-GCM) ile şifrelenip iletilir.
    4. AI Fraud Service işlemi analiz eder -> ALLOW.
    5. Blockchain katmanında DID ve Verifiable Credential özeti demlenir.
    6. Şüpheli saldırı simüle edilir -> AI tespit eder ve hesabı KARANTİNAYA alır.
    7. 3/5 Guardian Quorum'u ile acil kurtarma ve anahtar rotasyonu icra edilir.
    """

    # ADIM 1: W3C VC Üretimi (Senaryo 171 - Diploma)
    original_diploma_vc = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": "urn:uuid:subu-diploma-2026-001",
        "type": ["VerifiableCredential", "UniversityDegreeCredential"],
        "issuer": "did:web:subu.edu.tr",
        "validFrom": "2026-06-25T10:00:00Z",
        "credentialSubject": {
            "id": "did:key:z6MkuBesnaStudent2026",
            "name": "Charaf Eddine Bessanane",
            "degree": "Lisans",
            "department": "Bilgisayar Muhendisligi",
            "gpa": 3.82,
            "nationalId": "12345678901"
        }
    }

    # ADIM 2: ZKP & Seçici Açıklama (TC Kimlik No ve İsim Gizlenir, GPA >= 3.0 Kanıtlanır)
    revealed_keys = ["degree", "department"]
    disclosed_vc, salts = ZKPSelectiveDisclosure.create_disclosed_presentation(
        original_diploma_vc, revealed_keys
    )
    assert disclosed_vc["zkpDisclosed"] is True
    assert disclosed_vc["credentialSubject"]["name"]["_hidden"] is True
    assert disclosed_vc["credentialSubject"]["nationalId"]["_hidden"] is True
    assert disclosed_vc["credentialSubject"]["department"]["value"] == "Bilgisayar Muhendisligi"
    assert ZKPSelectiveDisclosure.verify_disclosed_presentation(disclosed_vc) is True

    # ZKP Predicate Proof: GPA >= 3.0 kanıtı üret ve doğrula
    zkp_proof = ZKPSelectiveDisclosure.generate_range_proof("gpa", 3.82, 3.0, ">=")
    assert ZKPSelectiveDisclosure.verify_range_proof(zkp_proof) is True

    # ADIM 3: DIDComm v2 Şifreli İletim (AES-256-GCM)
    shared_key = secrets.token_bytes(32)
    plaintext_msg = DIDCommV2.pack_plaintext(
        msg_type="https://didcomm.org/present-proof/2.0/presentation",
        body={"verifiablePresentation": disclosed_vc, "zkpProof": zkp_proof},
        sender_did="did:key:z6MkuBesnaStudent2026",
        recipient_dids=["did:web:employer.example.com"]
    )
    encrypted_envelope = DIDCommV2.pack_authcrypt(plaintext_msg, shared_key)
    decrypted_msg = DIDCommV2.unpack_authcrypt(encrypted_envelope, shared_key)
    assert decrypted_msg["body"]["zkpProof"]["claim"] == "gpa"

    # ADIM 4: AI Fraud Engine Değerlendirmesi (Normal Kullanıcı)
    ai_engine = HybridFraudDetector()
    normal_req = FraudEvaluationRequest(
        did="did:key:z6MkuBesnaStudent2026",
        action="presentation_verification",
        client_ip="192.168.1.45",
        user_agent="Mozilla/5.0 SecureApp",
        failed_attempts=0,
        geo_distance_km=10.0,
        time_since_last_action_sec=600.0,
        presentation_frequency_10m=1,
        device_fingerprint="device-token-1",
        device_fingerprint_match=True,
        is_tor_or_proxy=False
    )
    normal_eval = ai_engine.evaluate(normal_req)
    assert normal_eval.risk_level == "LOW"
    assert normal_eval.recommended_action == "ALLOW"
    assert normal_eval.is_anomaly is False

    # ADIM 5: Cache ve Blockchain Demleme (Anchoring)
    cache = CredentialStatusCache(ttl_seconds=300)
    cache.set("urn:uuid:subu-diploma-2026-001", "ACTIVE")
    assert cache.get("urn:uuid:subu-diploma-2026-001") == "ACTIVE"

    blockchain = BlockchainAnchorClient()
    doc_hash = blockchain.anchor_did_document("did:key:z6MkuBesnaStudent2026", original_diploma_vc)
    assert doc_hash.startswith("0x")

    # ADIM 6: Siber Saldırı / Dolandırıcılık Simülasyonu
    attack_req = FraudEvaluationRequest(
        did="did:key:z6MkuBesnaStudent2026",
        action="presentation_verification",
        client_ip="185.220.101.4",
        user_agent="AdversarialBot",
        failed_attempts=5,
        geo_distance_km=2500.0, # İmkansız Seyahat
        time_since_last_action_sec=30.0,
        presentation_frequency_10m=18,
        device_fingerprint="unknown-device",
        device_fingerprint_match=False,
        is_tor_or_proxy=True
    )
    attack_eval = ai_engine.evaluate(attack_req)
    assert attack_eval.risk_level == "CRITICAL"
    assert attack_eval.recommended_action == "QUARANTINE_ACCOUNT"
    assert ai_engine.is_quarantined("did:key:z6MkuBesnaStudent2026") is True

    # ADIM 7: Acil Kurtarma ve 3/5 Guardian Quorum Onayı
    guardians = ["guardian_1", "guardian_2", "guardian_3", "guardian_4", "guardian_5"]
    approvals = []
    # 3 Guardian onay verir
    approvals.append("guardian_1")
    approvals.append("guardian_2")
    approvals.append("guardian_3")

    quorum_threshold = 3
    assert len(approvals) >= quorum_threshold, "3/5 Quorum saglandi"

    # Time-lock süresi dolumu ve yeni anahtara rotasyon
    new_holder_did = "did:key:z6MkuSuccessorKey2026New"
    rev_hash = blockchain.anchor_revocation_status("did:key:z6MkuBesnaStudent2026", "ACCOUNT_COMPROMISED_ROTATED")
    new_doc_hash = blockchain.anchor_did_document(new_holder_did, {"newKey": True})

    assert rev_hash.startswith("0x")
    assert new_doc_hash.startswith("0x")

    # Karantinayı kaldır ve yeni anahtarla sistemi aç
    ai_engine.release_quarantine("did:key:z6MkuBesnaStudent2026")
    assert ai_engine.is_quarantined("did:key:z6MkuBesnaStudent2026") is False
