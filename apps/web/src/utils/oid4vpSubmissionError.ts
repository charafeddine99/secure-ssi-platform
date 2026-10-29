export type Oid4vpSubmissionStage = "consent" | "presentation" | "direct-post";

import { isApiError } from "../lib/http.ts";

export function isFetchNetworkFailure(error: unknown): boolean {
  if (isApiError(error)) return error.kind === "network" || error.kind === "timeout";
  return error instanceof TypeError && /failed to fetch|networkerror|load failed|fetch failed/i.test(error.message);
}

export function getOid4vpSubmissionErrorMessage(
  error: unknown,
  stage: Oid4vpSubmissionStage,
): string {
  if (isFetchNetworkFailure(error)) {
    if (stage === "consent") {
      return "The wallet could not confirm the consent decision. No presentation was created or sent. Check the verifier request before trying again.";
    }
    if (stage === "presentation") {
      return "Consent may have been recorded, but the wallet could not confirm that a signed presentation was created. Check the verifier request before trying again.";
    }
    return "The wallet could not confirm whether the verifier received the presentation. Retry delivery only with the same prepared presentation.";
  }

  return error instanceof Error ? error.message : "Failed to submit the presentation.";
}
