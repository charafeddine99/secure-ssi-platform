const SESSION_ID_PATTERN = /^[A-Za-z0-9_-]{8,128}$/;

/** True for a by-reference request (OpenID4VP request_uri, signed request object). */
export function hasRequestUri(rawUri: string): boolean {
  const trimmed = rawUri.trim();
  if (!trimmed.startsWith("openid4vp://")) return false;
  try {
    return new URL(trimmed.replace(/^openid4vp:\/\//, "https://placeholder/")).searchParams.has("request_uri");
  } catch {
    return false;
  }
}

/**
 * Resolve the local session handle from the project's supported OID4VP QR forms.
 * The returned identifier is only a lookup key; the consent page loads the
 * authoritative request from the Identity Service before showing any action.
 */
export function parseOid4vpRequestSessionId(rawUri: string): string {
  const trimmed = rawUri.trim();
  if (!trimmed.startsWith("openid4vp://")) {
    throw new Error("Expected an openid4vp:// authorization request.");
  }

  const url = new URL(trimmed.replace(/^openid4vp:\/\//, "https://placeholder/"));
  const requestUri = url.searchParams.get("request_uri");
  let sessionId: string | null;

  if (requestUri) {
    // A request_uri points at a signed request object. Its host and signature
    // are checked by the server (resolveOid4vpRequestLink); guessing the
    // session from the URL path would trust any site.
    throw new Error("This link must be checked by the wallet service first.");
  } else {
    const requiredParameters = [
      "client_id",
      "response_uri",
      "response_type",
      "response_mode",
      "nonce",
      "state",
      "dcql_query",
    ];
    if (requiredParameters.some((name) => !url.searchParams.get(name))) {
      throw new Error("Inline OID4VP request is missing required project-profile parameters.");
    }
    if (url.searchParams.get("response_type") !== "vp_token") {
      throw new Error("This wallet supports the OID4VP vp_token response type only.");
    }
    if (url.searchParams.get("response_mode") !== "direct_post") {
      throw new Error("This wallet supports the OID4VP direct_post response mode only.");
    }

    try {
      const query = JSON.parse(url.searchParams.get("dcql_query") ?? "") as {
        credentials?: unknown;
      };
      if (!query || !Array.isArray(query.credentials) || query.credentials.length === 0) {
        throw new Error("DCQL request must contain at least one credential query.");
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        throw new Error("Inline OID4VP request contains malformed DCQL JSON.");
      }
      throw error;
    }

    sessionId = url.searchParams.get("state");
  }

  if (!sessionId || !SESSION_ID_PATTERN.test(sessionId)) {
    throw new Error("The OID4VP request does not contain a valid verification session identifier.");
  }
  return sessionId;
}
