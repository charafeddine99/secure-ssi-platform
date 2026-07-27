import json
import unittest
from pathlib import Path


SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas" / "v1"
EXPECTED_SCHEMAS = {
    "anchor-request.schema.json",
    "api-error.schema.json",
    "credential-verification-result.schema.json",
    "credential-issuance-request.schema.json",
    "data-integrity-proof.schema.json",
    "recovery-request.schema.json",
    "risk-assessment-request.schema.json",
    "risk-assessment-result.schema.json",
    "verifiable-credential.schema.json",
}


class SharedSchemaCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema_files = sorted(SCHEMA_ROOT.glob("*.schema.json"))

    def test_expected_versioned_schema_catalog_exists(self) -> None:
        self.assertEqual({path.name for path in self.schema_files}, EXPECTED_SCHEMAS)

    def test_schemas_have_required_contract_metadata(self) -> None:
        ids: set[str] = set()
        for path in self.schema_files:
            with self.subTest(schema=path.name):
                schema = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    schema["$schema"],
                    "https://json-schema.org/draft/2020-12/schema",
                )
                self.assertTrue(schema["$id"].endswith(f"/v1/{path.name}"))
                self.assertNotIn(schema["$id"], ids)
                ids.add(schema["$id"])
                self.assertEqual(schema["type"], "object")
                self.assertFalse(schema["additionalProperties"])
                self.assertIsInstance(schema["title"], str)
                self.assertIsInstance(schema["description"], str)

    def test_required_fields_are_declared_and_present_in_examples(self) -> None:
        for path in self.schema_files:
            with self.subTest(schema=path.name):
                schema = json.loads(path.read_text(encoding="utf-8"))
                properties = schema["properties"]
                required = schema["required"]
                example = schema["examples"][0]
                self.assertTrue(set(required).issubset(properties))
                self.assertTrue(set(required).issubset(example))
                self.assertTrue(set(example).issubset(properties))

    def test_relative_schema_references_resolve(self) -> None:
        for path in self.schema_files:
            schema = json.loads(path.read_text(encoding="utf-8"))
            for value in self._walk(schema):
                if not isinstance(value, dict) or "$ref" not in value:
                    continue
                reference = value["$ref"]
                if reference.startswith("#") or "://" in reference:
                    continue
                with self.subTest(schema=path.name, reference=reference):
                    self.assertTrue((SCHEMA_ROOT / reference).is_file())

    def test_vc_profile_pins_context_type_and_proof_suite(self) -> None:
        credential_schema = json.loads(
            (SCHEMA_ROOT / "verifiable-credential.schema.json").read_text(
                encoding="utf-8"
            )
        )
        proof_schema = json.loads(
            (SCHEMA_ROOT / "data-integrity-proof.schema.json").read_text(
                encoding="utf-8"
            )
        )

        context_items = credential_schema["properties"]["@context"][
            "prefixItems"
        ]
        type_items = credential_schema["properties"]["type"]["prefixItems"]
        self.assertEqual(
            [item["const"] for item in context_items],
            [
                "https://www.w3.org/ns/credentials/v2",
                "https://secure-ssi.example/contexts/university-affiliation/v1",
            ],
        )
        self.assertEqual(
            [item["const"] for item in type_items],
            [
                "VerifiableCredential",
                "UniversityAffiliationCredential",
            ],
        )
        self.assertEqual(
            proof_schema["properties"]["cryptosuite"]["const"],
            "eddsa-jcs-2022",
        )
        self.assertEqual(
            proof_schema["properties"]["proofPurpose"]["const"],
            "assertionMethod",
        )

    @staticmethod
    def _walk(value: object) -> list[object]:
        values = [value]
        if isinstance(value, dict):
            for nested in value.values():
                values.extend(SharedSchemaCatalogTests._walk(nested))
        elif isinstance(value, list):
            for nested in value:
                values.extend(SharedSchemaCatalogTests._walk(nested))
        return values


if __name__ == "__main__":
    unittest.main()
