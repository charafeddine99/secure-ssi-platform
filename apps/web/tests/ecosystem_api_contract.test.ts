import {
  fetchOid4vciIssuerMetadata,
  fetchPublicTrustedIssuers,
} from "../src/services/api.ts";

let assertions = 0;

function equal(actual: unknown, expected: unknown, message: string): void {
  assertions += 1;
  if (actual !== expected) throw new Error(`${message}: expected ${String(expected)}, received ${String(actual)}`);
}

function ok(value: unknown, message: string): asserts value {
  assertions += 1;
  if (!value) throw new Error(message);
}

async function rejects(action: () => Promise<unknown>, message: string): Promise<void> {
  assertions += 1;
  try {
    await action();
  } catch {
    return;
  }
  throw new Error(message);
}

async function runTests(): Promise<void> {
  const previousFetch = globalThis.fetch;
  const requests: Array<{ url: string; signal: AbortSignal | null | undefined }> = [];
  let status = 200;
  let response: unknown = {
    credential_issuer: "https://issuer.example.test",
    credential_configurations_supported: { UniversityDegree: { format: "ldp_vc" } },
  };

  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    requests.push({ url: String(input), signal: init?.signal });
    return new Response(JSON.stringify(response), { status, headers: { "Content-Type": "application/json" } });
  }) as typeof globalThis.fetch;

  try {
    const controller = new AbortController();
    const metadata = await fetchOid4vciIssuerMetadata(controller.signal);
    equal(metadata.credential_issuer, "https://issuer.example.test", "Issuer metadata is mapped from the service response");
    equal(requests[0]?.url, "http://127.0.0.1:8000/api/v1/oid4vci/.well-known/openid-credential-issuer", "Metadata uses the gateway route");
    ok(requests[0]?.signal instanceof AbortSignal, "Metadata requests have an abortable timeout signal");

    response = [{
      id: "issuer-1",
      issuerDid: "did:web:issuer.example.test",
      organizationName: "Example Institution",
      trustStatus: "ACTIVE",
      roles: ["ISSUER"],
      permittedCredentialTypes: ["UniversityDegree"],
      validFrom: "2026-01-01T00:00:00Z",
    }];
    const issuers = await fetchPublicTrustedIssuers();
    equal(issuers.length, 1, "Trusted issuer records are returned from the service response");
    equal(issuers[0]?.issuerDid, "did:web:issuer.example.test", "Camel-case Trust Registry DID is mapped");
    equal(issuers[0]?.organizationName, "Example Institution", "Camel-case Trust Registry name is mapped");
    equal(issuers[0]?.permittedCredentialTypes[0], "UniversityDegree", "Camel-case permitted types are mapped");
    equal(requests[1]?.url, "http://127.0.0.1:8000/api/v1/identity/trust-registry/issuers?limit=100", "Issuer directory uses the gateway route");
    ok(requests[1]?.signal instanceof AbortSignal, "Trust registry requests have an abortable timeout signal");

    response = [{
      id: "issuer-2",
      issuer_did: "did:web:legacy.example.test",
      organization_name: "Legacy Example Institution",
      trust_status: "ACTIVE",
      roles: ["ISSUER"],
      permitted_credential_types: ["UniversityDegree"],
      valid_from: "2026-01-01T00:00:00Z",
    }];
    const legacyIssuers = await fetchPublicTrustedIssuers();
    equal(legacyIssuers[0]?.organizationName, "Legacy Example Institution", "Legacy snake-case issuer fields remain accepted");

    status = 503;
    await rejects(() => fetchPublicTrustedIssuers(), "Trust Registry failures must not be treated as an empty directory");

    status = 200;
    response = { issuers: [] };
    await rejects(() => fetchPublicTrustedIssuers(), "Malformed Trust Registry payloads must be rejected");

    response = { credential_issuer: "https://issuer.example.test" };
    await rejects(() => fetchOid4vciIssuerMetadata(), "Incomplete issuer metadata must be rejected");
  } finally {
    globalThis.fetch = previousFetch;
  }

  console.log(`Ecosystem API contract: ${assertions} assertions passed.`);
}

void runTests();
