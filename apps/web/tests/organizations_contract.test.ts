import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  acceptInvitation,
  applyForOrganization,
  decideOrganization,
  inviteMember,
  listMyOrganizations,
  ORG_ROLES,
  requestCapability,
  TRUST_REVIEW_ACTION,
} from "../src/api/organizations.ts";
import { NAVIGATION } from "../src/routes/navigation.ts";

// Contract for organizations, memberships, invitations and trust review (identity-service).
const originalFetch = globalThis.fetch;
const originalLocalStorage = globalThis.localStorage;
globalThis.localStorage = {
  getItem: () => "1", setItem: () => undefined, removeItem: () => undefined, clear: () => undefined, key: () => null, length: 0,
} as Storage;
let checks = 0;
const check = (condition: boolean, message: string): void => {
  assert.equal(condition, true, message);
  checks += 1;
};
const calls: Array<{ url: string; init: RequestInit }> = [];
const reply = (body: unknown, status = 200) => async (input: unknown, init: RequestInit = {}) => {
  calls.push({ url: String(input), init });
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
};
const sent = (i: number) => JSON.parse(String(calls[i].init.body));

try {
  const domain = readFileSync(new URL("../../../services/identity-service/app/domain/organization.py", import.meta.url), "utf8");
  const api = readFileSync(new URL("../../../services/identity-service/app/api/v1/organizations.py", import.meta.url), "utf8");
  check(ORG_ROLES.every((role) => domain.includes(`${role} = "${role}"`)), "organization roles match the identity service");
  check(api.includes(`action="${TRUST_REVIEW_ACTION}"`), "the trust-review step-up action matches the identity service");

  globalThis.fetch = reply([]);
  await listMyOrganizations();
  check(calls[0].url.endsWith("/api/v1/identity/organizations/mine"), "memberships come from the gateway");

  globalThis.fetch = reply({ organizationId: "org_x" }, 201);
  await applyForOrganization({ legalName: "Example University", organizationType: "UNIVERSITY", jurisdiction: "TR", registrationReference: "  ", officialContact: "rectorate", applicantTitle: "Registrar", authorityEvidence: "letter", requestedCapabilities: ["ISSUER"], intendedUse: "diplomas" });
  check(!("registrationReference" in sent(1)), "empty optional fields are not sent");
  check(!("status" in sent(1)) && !("applicantUserId" in sent(1)), "the client never sends status or applicant id");

  globalThis.fetch = reply({ invitation: {}, invitationCode: "c".repeat(43) }, 201);
  await inviteMember("org_abc12345", " new@uni.example ", ["ISSUER_OPERATOR"]);
  check(sent(2).email === "new@uni.example" && JSON.stringify(sent(2).roles) === '["ISSUER_OPERATOR"]', "invitation sends a trimmed address and roles");

  globalThis.fetch = reply({ membershipId: "mem_x" });
  await acceptInvitation(`  ${"c".repeat(43)}  `);
  check(sent(3).invitationCode === "c".repeat(43) && calls[3].url.endsWith("/organization-invitations/accept"), "the code goes in the body, trimmed");

  globalThis.fetch = reply({ capabilityId: "cap_x" }, 201);
  await requestCapability("org_abc12345", { type: "VERIFIER", credentialTypes: ["UniversityDegree"], purpose: "Check degrees", clientId: "verifier.example", redirectUris: ["https://verifier.example/cb"] });
  check(JSON.stringify(sent(4).redirectUris) === '["https://verifier.example/cb"]', "redirect URIs are sent as exact strings");

  globalThis.fetch = reply({ organizationId: "org_abc12345" });
  await decideOrganization("org_abc12345", { decision: "APPROVE", entityVerified: true, entityEvidence: "registry", representativeVerified: true, representativeEvidence: "call", note: "ok" }, "step-up-1");
  check(new Headers(calls[5].init.headers).get("X-Step-Up-Token") === "step-up-1", "trust-review decisions forward the step-up token");

  check(Object.values(NAVIGATION).every((items) => items.some((item) => item.to === "/organizations")), "every role can reach Organizations");
  check(NAVIGATION.ADMIN.some((item) => item.to === "/admin/trust-review" && item.permission === "trust-review:decide"), "trust review is permission-gated");
} finally {
  globalThis.fetch = originalFetch;
  globalThis.localStorage = originalLocalStorage;
}
console.log(`Organization contract checks passed: ${checks}`);
