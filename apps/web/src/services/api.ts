/**
 * Compatibility barrel. The API client is split by domain under src/api/ and
 * uses one gateway-only HTTP client (src/lib/http.ts) with the existing bearer token.
 */
export * from "../lib/http.ts";
export * from "../api/session.ts";
export * from "../api/wallet.ts";
export * from "../api/issuance.ts";
export * from "../api/presentation.ts";
export * from "../api/status.ts";
export * from "../api/recovery.ts";
export * from "../api/admin.ts";
