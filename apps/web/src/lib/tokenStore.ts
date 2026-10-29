/**
 * Browser session marker.
 *
 * The access token is never stored in JavaScript-readable storage (OWASP
 * HTML5 Security cheat sheet). The API Gateway keeps it in an HttpOnly,
 * SameSite=Strict cookie. This module only remembers *that* a session was
 * started, so protected requests can fail before any network call when the
 * user never signed in. The marker is not a credential.
 */

const SESSION_MARKER_KEY = "ssi_session_active";
// Pre-cookie clients stored bearer tokens under these keys; remove them.
const LEGACY_TOKEN_KEYS = ["ssi_access_token", "secure_ssi_token", "secure_ssi_user"] as const;

function storage(): Storage | null {
  try {
    return typeof globalThis.localStorage === "undefined" ? null : globalThis.localStorage;
  } catch {
    return null;
  }
}

function purgeLegacyTokens(store: Storage): void {
  try {
    for (const key of LEGACY_TOKEN_KEYS) store.removeItem(key);
  } catch {
    // ignore
  }
}

export function hasSessionMarker(): boolean {
  const store = storage();
  if (!store) return false;
  purgeLegacyTokens(store);
  try {
    return store.getItem(SESSION_MARKER_KEY) === "1";
  } catch {
    return false;
  }
}

export function markSession(): void {
  const store = storage();
  if (!store) return;
  purgeLegacyTokens(store);
  try {
    store.setItem(SESSION_MARKER_KEY, "1");
  } catch {
    // Storage may be blocked (private mode); the cookie session still works for this page.
  }
}

export function clearSessionMarker(): void {
  const store = storage();
  if (!store) return;
  purgeLegacyTokens(store);
  try {
    store.removeItem(SESSION_MARKER_KEY);
  } catch {
    // ignore
  }
}

/** Per-account wallet identifier cache, same key format as the previous client. */
export function readCachedWalletId(userId: string): string | null {
  try {
    return storage()?.getItem(`ssi_holder_wallet_id:${userId}`) ?? null;
  } catch {
    return null;
  }
}

export function storeCachedWalletId(userId: string, walletId: string): void {
  try {
    storage()?.setItem(`ssi_holder_wallet_id:${userId}`, walletId);
  } catch {
    // ignore
  }
}

export function clearCachedWalletId(userId: string): void {
  try {
    storage()?.removeItem(`ssi_holder_wallet_id:${userId}`);
  } catch {
    // ignore
  }
}
