# UX Copy & Content Guidelines
**Document ID:** `DOC-DES-09-COPY`  
**Version:** 2.0  
**Date:** October 2026  
**Status:** Canonical Content Guidelines  

---

## 1. Content Philosophy & Voice

Digital identity software operates at the intersection of legal status, personal privacy, and advanced cryptography. The tone of voice for the **Secure SSI Platform** is:
- **Authoritative & Sober:** We speak with institutional gravity and clarity. No playful marketing jargon or vague assurances.
- **Truthful & Transparent:** We never exaggerate cryptographic guarantees or hide protocol realities behind misleading user-friendly metaphors.
- **Actionable & Direct:** When an error or security failure occurs, we answer three questions immediately:
  1. *What happened?*
  2. *Why did it happen?*
  3. *What is your next step?*

---

## 2. Mandatory Cryptographic Honesty & Consent Copy Rules

### 2.1 The Selective Disclosure & eddsa-jcs-2022 Reality
The platform implements W3C VC 2.0 Data Integrity proofs with **`eddsa-jcs-2022`** (Ed25519 signature over canonical JCS JSON). 
- **Cryptographic Fact:** A signature over JCS canonical JSON binds every claim in the credential subject. It is cryptographically impossible to redact or selectively disclose individual claims without invalidating the signature (unlike ZKP or BBS+ suites).
- **Prohibited UX Copy:**
  - ❌ *"Only selected attributes will be shared."*
  - ❌ *"Cryptographic selective disclosure enabled."*
  - ❌ *"Unchecked fields are encrypted and hidden from the verifier."*
- **Mandatory Canonical UX Copy:**
  - ✅ **Notice Banner (Amber):**  
    > *"This profile sends the complete signed credential. The current Data Integrity proof does not support claim-level cryptographic selective disclosure, so unselected claims cannot be hidden."*
  - ✅ **Consent Checkbox:**  
    > *"I understand that approving shares this entire signed credential, including every claim listed above."*
  - ✅ **Submission Button:**  
    > *"Approve full credential"* (not "Share selected claims").

---

## 3. Systematic UX Copy Audit & Canonical Terminology

### 3.1 Terminology Harmonization Table

| Concept | Prohibited / Deprecated Term | Canonical English Term | Canonical Turkish Term |
| :--- | :--- | :--- | :--- |
| Verified Credential | "Digital Badge", "Card", "Pass" | **Verifiable Credential (VC)** | **Doğrulanabilir Kimlik Bilgisi** |
| Signed Presentation | "Share", "Send Data", "Upload" | **Verifiable Presentation (VP)** | **Doğrulanabilir Sunum (VP)** |
| Verification Decision | "Validated", "Looked Good", "OK" | **Authoritative Verification: ACCEPTED** | **Yetkili Doğrulama: ONAYLANDI** |
| Verification Rejection| "Denied", "Failed", "Bad Data" | **Verification Failed: REJECTED** | **Doğrulama Başarısız: REDDEDİLDİ** |
| Suspicious Session | "Flagged", "Risky", "Blocked" | **Session Quarantined: ANOMALY** | **Oturum Karantinada: ANOMALİ** |
| Revocation Registry | "Blacklist", "Revoke DB", "Cancelled"| **Bitstring Status List v1.0** | **Bitstring Durum Listesi v1.0** |
| Social Recovery | "Forgot Password", "Reset Account" | **Guardian Quorum Social Recovery** | **Vasi Çoğunluklu Sosyal Kurtarma**|
| Subject Identifier | "Account Number", "User ID" | **Decentralized Identifier (DID)** | **Merkeziyetsiz Kimlik Tanımlayıcı (DID)** |

---

## 4. Screen-by-Screen Copy Dictionary

### 4.1 Navigation & Global Labels

| Key | English (EN) | Türkçe (TR) |
| :--- | :--- | :--- |
| `nav.wallet` | Citizen Wallet | Yurttaş Cüzdanı |
| `nav.issuer` | Issuer Portal | Kimlik Sağlayıcı Portalı |
| `nav.verifier` | Verifier Terminal | Doğrulayıcı Terminali |
| `nav.guardian` | Guardian Console | Vasi Kurtarma Konsolu |
| `nav.admin` | Security Cockpit | Güvenlik ve Yönetim |
| `nav.ecosystem` | Trust Registry | Güven Ekosistemi |
| `nav.docs` | Architecture Specs | Mimari ve Standartlar |

### 4.2 Buttons & Actions

| Key | English (EN) | Türkçe (TR) |
| :--- | :--- | :--- |
| `btn.sign_in` | Authenticate Session | Oturumu Doğrula |
| `btn.issue_vc` | Cryptographically Sign & Issue | Kriptografik İmzala ve İhraç Et |
| `btn.revoke_vc` | Revoke Credential in Status List | Durum Listesinde İptal Et |
| `btn.create_qr` | Generate Verification QR | Doğrulama QR Kodu Üret |
| `btn.approve_vp` | Approve Full Credential | Tam Kimlik Belgesini Onayla |
| `btn.reject_vp` | Reject Request | Talebi Reddet |
| `btn.sign_recovery`| Sign Recovery Authorization | Kurtarma Yetkisini İmzala |
| `btn.retry_submission`| Retry Transmission | İletimi Yeniden Dene |
| `btn.copy_did` | Copy DID to Clipboard | DID'yi Panoya Kopyala |

### 4.3 Form Labels & Helper Text

| Key | English (EN) | Türkçe (TR) |
| :--- | :--- | :--- |
| `form.subject_did` | Subject DID (did:jwk or did:key) | Alıcı DID (did:jwk veya did:key) |
| `form.expiry_date` | Expiration Date (ISO-8601) | Geçerlilik Bitiş Tarihi (ISO-8601) |
| `form.purpose` | Purpose of Verification Request | Doğrulama Talebinin Amacı |
| `form.guardian_did`| Designated Guardian DID | Atanan Vasi DID Adresi |
| `form.quorum_thresh`| Quorum Threshold | Çoğunluk Eşiği |

---

## 5. Error & Recovery Messaging Framework

All error messages follow the **What / Why / Next-Step** format:

### Scenario 1: Revocation Check Failure (Fail-Closed)
- **What:** Credential status could not be verified.
- **Why:** The Bitstring Status List endpoint was unreachable or returned an authoritative revocation flag.
- **Next-Step:** The presentation has failed closed. Contact the issuing authority to verify your credential status.
- *Turkish:* "Kimlik belgesi durumu doğrulanamadı. Bitstring Durum Listesi erişilemez veya belge iptal edilmiş. Sunum güvenlik nedeniyle reddedildi. Lütfen ihraç eden kurumla iletişime geçin."

### Scenario 2: Direct Post Transmission Network Disruption
- **What:** Presentation transmission interrupted.
- **Why:** Connection to the verifier's direct_post endpoint timed out after cryptographic signing.
- **Next-Step:** Your signed presentation is preserved in local memory. Click "Retry Transmission" to submit without re-authorizing.
- *Turkish:* "Doğrulayıcıya veri iletimi kesildi. Kriptografik imza yerel bellekte korundu. Yeniden izin vermeden iletmek için 'İletimi Yeniden Dene' butonuna tıklayın."

### Scenario 3: AI Anomaly / Quarantine Alert
- **What:** Verification session placed in quarantine.
- **Why:** Machine learning anomaly score (0.78) exceeded the platform security threshold (0.65) due to velocity mismatch.
- **Next-Step:** Request out-of-band physical identification from the subject before granting privileged access.
- *Turkish:* "Doğrulama oturumu karantinaya alındı. Yapay zeka anomali puanı (0.78) güvenlik eşiğini (0.65) aştı. Ayrıcalıklı erişim vermeden önce fiziksel kimlik kontrolü yapılması önerilir."

---

## 6. Empty States & First-Use Microcopy

### Wallet Empty State:
- **Title:** "No Credentials in Wallet" / "Cüzdanda Kimlik Belgesi Yok"
- **Description:** "Your decentralized wallet holds cryptographically signed credentials from trusted universities, employers, and government agencies."
- **Action:** "Scan Issuance Offer" / "Teklif QR Kodu Tara"

### Verifier History Empty State:
- **Title:** "No Verification History" / "Doğrulama Kaydı Bulunmuyor"
- **Description:** "When you create OID4VP presentation requests and subjects present credentials, full audit trails will appear here."
- **Action:** "Create Verification Request" / "Yeni Doğrulama Talebi Oluştur"
