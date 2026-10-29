import {
  UNIVERSITY_CONFIG_ID,
  defaultUniversityForm,
  parseOfferDraft,
  universityErrors,
  universitySubject,
} from "../src/pages/issuer/issuerLogic.ts";

let assertions = 0;

function equal(actual: unknown, expected: unknown, message: string): void {
  assertions += 1;
  if (actual !== expected) throw new Error(`${message}: expected ${String(expected)}, received ${String(actual)}`);
}

function ok(value: unknown, message: string): asserts value {
  assertions += 1;
  if (!value) throw new Error(message);
}

const valid = { affiliation: "student", programCode: "SYN-CS-301", degree: "Bachelor of Science", graduationYear: "2027" };

// A complete, allowlisted form has no problems and builds a numeric year.
equal(Object.keys(universityErrors(valid)).length, 0, "valid form reports no errors");
equal(universitySubject(valid).graduationYear, 2027, "graduationYear is sent as a number");

// The default form is incomplete on purpose: degree and programCode must be chosen.
const defaults = universityErrors(defaultUniversityForm(new Date("2026-10-28T00:00:00Z")));
ok(defaults.degree, "default form asks for a degree");
ok(defaults.programCode, "default form asks for a programme code");

// Values the Identity Service rejects are caught before an unclaimable offer exists.
ok(universityErrors({ ...valid, programCode: "CS-301" }).programCode, "programCode without SYN- prefix is rejected");
ok(universityErrors({ ...valid, degree: "BSc Computer Science" }).degree, "unknown degree is rejected");
ok(universityErrors({ ...valid, affiliation: "visitor" }).affiliation, "unknown affiliation is rejected");
ok(universityErrors({ ...valid, graduationYear: "1999" }).graduationYear, "year below range is rejected");

// The JSON path applies the same rules for this profile, and nothing extra for others.
const json = (subject: unknown) => JSON.stringify(subject);
ok("error" in parseOfferDraft(json({ ...universitySubject(valid), programCode: "CS-301" }), "", "", UNIVERSITY_CONFIG_ID), "JSON path rejects bad programCode");
ok("error" in parseOfferDraft(json({ ...universitySubject(valid), nickname: "x" }), "", "", UNIVERSITY_CONFIG_ID), "JSON path rejects extra attributes");
ok("error" in parseOfferDraft(json({ ...universitySubject(valid), graduationYear: "2027" }), "", "", UNIVERSITY_CONFIG_ID), "JSON path rejects a text year");
ok("subject" in parseOfferDraft(json(universitySubject(valid)), "", "", UNIVERSITY_CONFIG_ID), "JSON path accepts a valid subject");
ok("subject" in parseOfferDraft(json({ anything: "goes" }), "", "", "OtherCredential"), "other profiles keep the generic checks only");

console.log(`Issuer profile rules: ${assertions} passed, 0 failed.`);
