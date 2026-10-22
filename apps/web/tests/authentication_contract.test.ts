import assert from "node:assert/strict";
import {
  authenticateBackend,
  DEMO_AUTH_ENABLED,
  DEMO_CREDENTIALS,
  resolveBackendSession,
  revokeBackendToken
} from "../src/context/AuthContext.ts";

const originalFetch = globalThis.fetch;
let checks = 0;
const check = (condition: boolean, message: string): void => {
  assert.equal(condition, true, message);
  checks += 1;
};

try {
  check(!DEMO_AUTH_ENABLED, "demo authentication is disabled outside an explicitly enabled Vite development build");
  check(Object.keys(DEMO_CREDENTIALS).length === 0, "demo credentials are not exposed in a non-demo build");

  let calls: Array<{ url: string; init: RequestInit }> = [];
  globalThis.fetch = async (input, init = {}) => {
    calls.push({ url: String(input), init });
    return new Response(JSON.stringify({
      accessToken: "valid-token-from-identity-service",
      user: {
        id: "usr_configured_issuer",
        username: "issuer@example.test",
        displayName: "Configured Issuer",
        roles: ["issuer"],
        permissions: ["auth:self:read", "credentials:sign", "credentials:revoke"]
      }
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  };

  const session = await authenticateBackend("issuer@example.test", "correct-password");
  check(session?.accessToken === "valid-token-from-identity-service", "valid credentials return the backend token");
  check(session?.user.role === "ISSUER", "role is derived from the backend principal");
  check(
    session?.user.permissions.join(",") === "auth:self:read,credentials:sign,credentials:revoke",
    "permissions are retained only from the backend principal"
  );
  check(session?.user.did === "" && session?.user.walletAddress === "", "missing identity and wallet data are not fabricated");
  check(calls.length === 1 && calls[0].init.method === "POST", "login makes one backend authentication request");
  check(
    JSON.parse(String(calls[0].init.body)).username === "issuer@example.test",
    "login submits the entered username to the backend"
  );

  calls = [];
  globalThis.fetch = async (input, init = {}) => {
    calls.push({ url: String(input), init });
    return new Response(JSON.stringify({ error: { code: "INVALID_CREDENTIALS" } }), { status: 401 });
  };
  const invalid = await authenticateBackend("issuer@example.test", "wrong-password");
  check(invalid === null, "invalid credentials do not create a session");
  check(calls.length === 1, "a backend 401 is not bypassed by trying another authentication path");

  calls = [];
  globalThis.fetch = async () => new Response(JSON.stringify({
    accessToken: "token-without-permissions",
    user: {
      id: "usr_configured_issuer",
      username: "issuer@example.test",
      displayName: "Configured Issuer",
      roles: ["issuer"]
    }
  }), { status: 200, headers: { "Content-Type": "application/json" } });
  let permissionlessSessionRejected = false;
  try {
    await authenticateBackend("issuer@example.test", "correct-password");
  } catch (error) {
    permissionlessSessionRejected = error instanceof Error && error.message.includes("invalid sign-in response");
  }
  check(permissionlessSessionRejected, "a sign-in response without server permissions cannot establish a frontend session");

  calls = [];
  globalThis.fetch = async (input, init = {}) => {
    calls.push({ url: String(input), init });
    return new Response(JSON.stringify({ error: { code: "ACCESS_TOKEN_EXPIRED" } }), { status: 401 });
  };
  let expiredRejected = false;
  try {
    await resolveBackendSession("expired-token");
  } catch (error) {
    expiredRejected = error instanceof Error && error.message.includes("rejected the access token");
  }
  check(expiredRejected, "expired or otherwise unauthorized bearer tokens cannot restore a session");
  check(new Headers(calls[0].init.headers).get("Authorization") === "Bearer expired-token", "session restoration sends only the stored bearer token");

  calls = [];
  globalThis.fetch = async (input, init = {}) => {
    calls.push({ url: String(input), init });
    return new Response(JSON.stringify({ error: { code: "AUTHENTICATION_REQUIRED" } }), { status: 401 });
  };
  let missingRejected = false;
  try {
    await resolveBackendSession("");
  } catch (error) {
    missingRejected = error instanceof Error;
  }
  check(missingRejected, "a missing token cannot restore an authenticated user");
  check(calls.length === 0, "a missing token is rejected before any protected request is sent");

  calls = [];
  globalThis.fetch = async (input, init = {}) => {
    calls.push({ url: String(input), init });
    return new Response(JSON.stringify({ status: "SUCCESS" }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  };
  await revokeBackendToken("active-token");
  check(calls.length === 1 && calls[0].init.method === "POST", "logout revokes the active backend token");
  check(new Headers(calls[0].init.headers).get("Authorization") === "Bearer active-token", "token revocation targets the signed-in bearer session");
} finally {
  globalThis.fetch = originalFetch;
}

console.log(`Authentication contract checks passed: ${checks}`);
