/** Fields the Identity Service actually issues for each supported profile. */
export const REQUEST_PROFILES: Record<string, { label: string; fields: Array<{ id: string; label: string }> }> = {
  UniversityAffiliationCredential: {
    label: "Higher education affiliation",
    fields: [
      { id: "affiliation", label: "Affiliation" },
      { id: "programCode", label: "Programme code" },
      { id: "degree", label: "Degree" },
      { id: "graduationYear", label: "Graduation year" },
    ],
  },
  QualifiedElectronicAttestationCredential: {
    label: "Qualified electronic attestation (QEAA)",
    fields: [
      { id: "Sertifika Sahibi", label: "Certificate holder" },
      { id: "Unvan", label: "Title" },
      { id: "Yetki Kapsami", label: "Scope of authority" },
    ],
  },
};

/** Accept a bare VP or an object wrapping it in `presentation`. */
export function extractPresentation(text: string): Record<string, unknown> | string {
  let parsed: unknown;
  try { parsed = JSON.parse(text); } catch { return "The presentation must be valid JSON."; }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return "The presentation must be a JSON object.";
  const obj = parsed as Record<string, unknown>;
  const vp = obj.presentation && typeof obj.presentation === "object" && !Array.isArray(obj.presentation) ? obj.presentation as Record<string, unknown> : obj;
  const types = Array.isArray(vp.type) ? vp.type : [vp.type];
  if (!types.includes("VerifiablePresentation")) return "The JSON does not contain a VerifiablePresentation.";
  return vp;
}
