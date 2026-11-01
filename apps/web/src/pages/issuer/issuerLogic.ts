import type { BadgeTone } from "../../components/ui/tones.ts";

export function offerTone(status: string): BadgeTone {
  switch (status.toUpperCase()) {
    case "CLAIMED": return "success";
    case "PENDING": case "OFFERED": return "info";
    case "EXPIRED": return "neutral";
    case "REVOKED": return "danger";
    default: return "neutral";
  }
}

export const UNIVERSITY_CONFIG_ID = "UniversityAffiliationCredential";

/**
 * Values the Identity Service accepts for UniversityAffiliationCredential
 * (oid4vci_service._university_claims and credential_validator). The backend
 * stays the authority; these only stop offers that could never be claimed.
 */
export const UNIVERSITY_AFFILIATIONS = ["student", "faculty", "alumni", "staff"] as const;
export const UNIVERSITY_DEGREES = ["Bachelor of Science", "Master of Science", "Doctor of Philosophy"] as const;
export const PROGRAM_CODE_PATTERN = /^SYN-[A-Z0-9-]{2,28}$/;
export const GRADUATION_YEAR_RANGE = { min: 2000, max: 2100 } as const;

export interface UniversityForm {
  affiliation: string;
  programCode: string;
  degree: string;
  graduationYear: string;
}

export function defaultUniversityForm(now = new Date()): UniversityForm {
  return { affiliation: "student", programCode: "SYN-", degree: "", graduationYear: String(now.getFullYear() + 1) };
}

/** Per-field problems for the university profile; empty object when valid. */
export function universityErrors(form: UniversityForm): Partial<Record<keyof UniversityForm, string>> {
  const errors: Partial<Record<keyof UniversityForm, string>> = {};
  if (!(UNIVERSITY_AFFILIATIONS as readonly string[]).includes(form.affiliation)) errors.affiliation = "Choose an affiliation.";
  if (!PROGRAM_CODE_PATTERN.test(form.programCode.trim())) {
    errors.programCode = "Use the form SYN- followed by 2–28 capital letters, digits or hyphens, e.g. SYN-CS-301.";
  }
  if (!(UNIVERSITY_DEGREES as readonly string[]).includes(form.degree)) errors.degree = "Choose a degree.";
  const year = Number(form.graduationYear);
  if (!Number.isInteger(year) || year < GRADUATION_YEAR_RANGE.min || year > GRADUATION_YEAR_RANGE.max) {
    errors.graduationYear = `Enter a year from ${GRADUATION_YEAR_RANGE.min} to ${GRADUATION_YEAR_RANGE.max}.`;
  }
  return errors;
}

export function universitySubject(form: UniversityForm): Record<string, unknown> {
  return {
    affiliation: form.affiliation,
    programCode: form.programCode.trim(),
    degree: form.degree,
    graduationYear: Number(form.graduationYear),
  };
}

function toUniversityForm(subject: Record<string, unknown>): UniversityForm {
  return {
    affiliation: String(subject.affiliation ?? ""),
    programCode: String(subject.programCode ?? ""),
    degree: String(subject.degree ?? ""),
    graduationYear: typeof subject.graduationYear === "number" ? String(subject.graduationYear) : String(subject.graduationYear ?? ""),
  };
}

/** Starting attribute sets matching the Identity Service validation per profile. */
export function subjectTemplate(configId: string): string {
  if (configId === UNIVERSITY_CONFIG_ID) {
    return JSON.stringify(universitySubject(defaultUniversityForm()), null, 2);
  }
  if (configId === "QualifiedElectronicAttestationCredential") {
    return JSON.stringify({ "Sertifika Sahibi": "", Unvan: "", "Yetki Kapsami": "" }, null, 2);
  }
  return "{\n  \n}";
}

/** Validate the issuer's draft. Returns a user-facing error or the parsed subject. */
export function parseOfferDraft(
  subjectJson: string,
  recipientDid: string,
  pin: string,
  configId = "",
): { subject: Record<string, unknown> } | { error: string } {
  let subject: unknown;
  try {
    subject = JSON.parse(subjectJson);
  } catch {
    return { error: "Subject data must be valid JSON." };
  }
  if (!subject || typeof subject !== "object" || Array.isArray(subject) || Object.keys(subject).length === 0) {
    return { error: "Subject data must be a non-empty JSON object." };
  }
  if ("id" in (subject as Record<string, unknown>)) {
    return { error: "Do not set \"id\"; the holder DID is bound from the wallet proof at claim time." };
  }
  if (configId === UNIVERSITY_CONFIG_ID) {
    const extra = Object.keys(subject as Record<string, unknown>).filter((key) => !["affiliation", "programCode", "degree", "graduationYear"].includes(key));
    if (extra.length > 0) return { error: `This credential type does not accept: ${extra.join(", ")}.` };
    const problems = universityErrors(toUniversityForm(subject as Record<string, unknown>));
    const first = Object.values(problems)[0];
    if (first) return { error: first };
    if (typeof (subject as Record<string, unknown>).graduationYear !== "number") {
      return { error: "graduationYear must be a number, not text." };
    }
  }
  if (recipientDid && !recipientDid.startsWith("did:")) return { error: "The recipient DID must start with did:." };
  if (pin && !/^\d{4,8}$/.test(pin)) return { error: "The transaction code must contain 4 to 8 digits." };
  return { subject: subject as Record<string, unknown> };
}
