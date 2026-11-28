/** Converts between the server's JSON options and the browser WebAuthn API. */

type Json = Record<string, unknown>;

function toBuffer(value: string): ArrayBuffer {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0)).buffer;
}

function toText(value: ArrayBuffer | null | undefined): string | undefined {
  if (!value) return undefined;
  let binary = "";
  for (const byte of new Uint8Array(value)) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

const descriptors = (items: unknown) =>
  ((items as Array<{ id: string; type: string }> | undefined) ?? []).map((item) => ({ ...item, id: toBuffer(item.id) }));

export const webAuthnAvailable = (): boolean =>
  typeof window !== "undefined" && typeof window.PublicKeyCredential === "function";

export async function createSecurityKey(options: Json): Promise<Json> {
  const user = options.user as { id: string };
  const created = await navigator.credentials.create({
    publicKey: {
      ...options,
      challenge: toBuffer(options.challenge as string),
      user: { ...user, id: toBuffer(user.id) },
      excludeCredentials: descriptors(options.excludeCredentials),
    } as unknown as PublicKeyCredentialCreationOptions,
  }) as PublicKeyCredential | null;
  if (!created) throw new Error("The security key was not created.");
  const response = created.response as AuthenticatorAttestationResponse;
  return {
    id: created.id,
    rawId: toText(created.rawId),
    type: created.type,
    clientExtensionResults: created.getClientExtensionResults(),
    response: {
      clientDataJSON: toText(response.clientDataJSON),
      attestationObject: toText(response.attestationObject),
      transports: response.getTransports?.() ?? [],
    },
  };
}

export async function assertSecurityKey(options: Json): Promise<Json> {
  const asserted = await navigator.credentials.get({
    publicKey: {
      ...options,
      challenge: toBuffer(options.challenge as string),
      allowCredentials: descriptors(options.allowCredentials),
    } as unknown as PublicKeyCredentialRequestOptions,
  }) as PublicKeyCredential | null;
  if (!asserted) throw new Error("The security key did not respond.");
  const response = asserted.response as AuthenticatorAssertionResponse;
  return {
    id: asserted.id,
    rawId: toText(asserted.rawId),
    type: asserted.type,
    clientExtensionResults: asserted.getClientExtensionResults(),
    response: {
      clientDataJSON: toText(response.clientDataJSON),
      authenticatorData: toText(response.authenticatorData),
      signature: toText(response.signature),
      userHandle: toText(response.userHandle),
    },
  };
}
