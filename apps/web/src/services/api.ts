/**
 * Real Backend API Integration Client for Secure SSI Platform
 * Connects frontend directly to:
 * - API Gateway (Port 8000)
 * - SSI Core & SQLite Database (Port 8001)
 * - AI Fraud & Threat Detection Service (Port 8002)
 */

export const GATEWAY_BASE_URL = "http://localhost:8000";
export const SSI_CORE_BASE_URL = "http://localhost:8001";
export const FRAUD_BASE_URL = "http://localhost:8002";

export interface BackendCredential {
  id: string;
  user_did: string;
  wallet_address: string;
  credential_type: string;
  title: string;
  category: string;
  issuer: string;
  issuer_name: string;
  issued_date: string;
  expiry_date: string;
  status: "ACTIVE" | "REVOKED";
  claims: Record<string, any>;
  proof_value: string;
  ai_risk_score: number;
  zkp_predicate?: string;
  created_at: string;
}

export interface BackendGuardian {
  id: number;
  wallet_address: string;
  guardian_name: string;
  guardian_role: string;
  guardian_did: string;
  guardian_address: string;
  approved: number;
  created_at: string;
}

export interface BackendAuditLog {
  id: number;
  event_type: string;
  actor_did: string;
  target_wallet: string;
  risk_score: number;
  details: Record<string, any>;
  created_at: string;
}

export interface BlockchainStatus {
  status: string;
  connected: boolean;
  block_number: number;
  chain_id: number;
  contracts: {
    did_registry: string;
    emergency_recovery: string;
  };
}

export interface GatewayStatus {
  gateway_status: string;
  system_health: string;
  services: {
    identity_service: string;
    fraud_service: string;
    recovery_service: string;
  };
}

/**
 * Fetch credentials from real database
 */
export async function fetchCredentials(userDid?: string, walletAddress?: string): Promise<BackendCredential[]> {
  try {
    const params = new URLSearchParams();
    if (userDid) params.append("user_did", userDid);
    if (walletAddress) params.append("wallet_address", walletAddress);

    const res = await fetch(`${SSI_CORE_BASE_URL}/api/credentials?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.credentials || [];
  } catch (err) {
    console.warn("fetchCredentials fallback due to:", err);
    return [];
  }
}

/**
 * Issue new W3C Verifiable Credential via real SSI service
 */
export async function issueCredential(payload: {
  wallet_address: string;
  did_id: string;
  credential_type: string;
  title?: string;
  category?: string;
  claims: Record<string, any>;
}): Promise<{
  success: boolean;
  credential?: any;
  txHash?: string;
  error?: string;
}> {
  try {
    const res = await fetch(`${SSI_CORE_BASE_URL}/api/issue_credential`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        wallet_address: payload.wallet_address,
        did_id: payload.did_id,
        ip_address: "127.0.0.1",
        device_fingerprint: "enterprise-browser-eudi",
        recent_failed_attempts: 0,
        credential_type: payload.credential_type,
        claims: payload.claims
      })
    });

    const data = await res.json();
    if (!res.ok) {
      return { success: false, error: data.detail || "İhraç işlemi reddedildi." };
    }

    return {
      success: true,
      credential: data.credential,
      txHash: data.blockchain_anchor?.tx_hash
    };
  } catch (err: any) {
    return { success: false, error: err.message || "Bağlantı hatası" };
  }
}

/**
 * Revoke credential in real database
 */
export async function revokeCredential(credentialId: string): Promise<boolean> {
  try {
    const res = await fetch(`${SSI_CORE_BASE_URL}/api/credentials/${encodeURIComponent(credentialId)}/revoke`, {
      method: "POST"
    });
    return res.ok;
  } catch (err) {
    console.error("revokeCredential error:", err);
    return false;
  }
}

/**
 * Fetch Guardians list from real database
 */
export async function fetchGuardians(walletAddress?: string): Promise<BackendGuardian[]> {
  try {
    const params = new URLSearchParams();
    if (walletAddress) params.append("wallet_address", walletAddress);
    const res = await fetch(`${SSI_CORE_BASE_URL}/api/guardians?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.guardians || [];
  } catch (err) {
    console.warn("fetchGuardians fallback:", err);
    return [];
  }
}

/**
 * Approve Guardian on-chain
 */
export async function approveGuardian(guardianId: number, walletAddress: string): Promise<{
  success: boolean;
  onChainTx?: string;
  error?: string;
}> {
  try {
    const res = await fetch(`${SSI_CORE_BASE_URL}/api/guardians/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        guardian_id: guardianId,
        wallet_address: walletAddress
      })
    });
    const data = await res.json();
    return {
      success: res.ok,
      onChainTx: data.on_chain_tx_hash
    };
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}

/**
 * Fetch audit logs from SQLite
 */
export async function fetchAuditLogs(): Promise<BackendAuditLog[]> {
  try {
    const res = await fetch(`${SSI_CORE_BASE_URL}/api/database/audit_logs`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.audit_logs || [];
  } catch (err) {
    console.warn("fetchAuditLogs fallback:", err);
    return [];
  }
}

/**
 * Fetch blockchain status (Hardhat Node)
 */
export async function fetchBlockchainStatus(): Promise<BlockchainStatus | null> {
  try {
    const res = await fetch(`${SSI_CORE_BASE_URL}/api/blockchain/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("fetchBlockchainStatus fallback:", err);
    return null;
  }
}

/**
 * Fetch gateway status from Port 8000
 */
export async function fetchGatewayStatus(): Promise<GatewayStatus | null> {
  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/system/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("fetchGatewayStatus fallback:", err);
    return null;
  }
}

/**
 * Evaluate AI Fraud risk directly via Port 8002
 */
export async function evaluateAiRisk(context: {
  failed_attempts?: number;
  ip_risk?: number;
  device_anomaly?: number;
}): Promise<{
  risk_score: number;
  verdict: string;
  is_anomalous: boolean;
}> {
  try {
    const res = await fetch(`${FRAUD_BASE_URL}/api/fraud_detection`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recent_failed_attempts: context.failed_attempts ?? 0,
        ip_address: "127.0.0.1",
        device_fingerprint: "enterprise-eudi-browser",
        wallet_address: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
      })
    });
    if (res.ok) {
      const data = await res.json();
      return {
        risk_score: (data.risk_score || 4) / 100,
        verdict: data.risk_score > 70 ? "HIGH_RISK" : "LOW_RISK",
        is_anomalous: data.risk_score > 70
      };
    }
  } catch (err) {
    console.warn("AI Fraud API evaluate fallback:", err);
  }
  return {
    risk_score: 0.04,
    verdict: "LOW_RISK",
    is_anomalous: false
  };
}
