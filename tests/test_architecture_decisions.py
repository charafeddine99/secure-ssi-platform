import re
import unittest
from pathlib import Path
from urllib.parse import unquote


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADR_ROOT = PROJECT_ROOT / "docs" / "adr"
LOCAL_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class ArchitectureDecisionTests(unittest.TestCase):
    def test_expected_decisions_are_accepted(self) -> None:
        expected = {
            "0001-did-methods-for-the-prototype.md": [
                "- **Status:** Accepted",
                "`did:web`",
                "`did:key`",
                "DID Core v1.0",
                "prohibited for real users",
            ],
            "0002-vc-data-model-and-proof-format.md": [
                "- **Status:** Accepted",
                "Verifiable Credentials Data Model v2.0",
                "`DataIntegrityProof`",
                "`eddsa-jcs-2022`",
                "Ed25519",
            ],
        }

        for filename, required_text in expected.items():
            with self.subTest(adr=filename):
                content = (ADR_ROOT / filename).read_text(encoding="utf-8")
                for text in required_text:
                    self.assertIn(text, content)

    def test_readme_marks_current_sprints_complete_and_policy_as_next(
        self,
    ) -> None:
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "[Completed] Select the prototype DID methods and credential proof format",
            readme,
        )
        self.assertIn(
            "[Completed] Build resolver validation and synthetic DID fixtures",
            readme,
        )
        self.assertIn(
            "[Completed] Define versioned VC fixture and verification-result models",
            readme,
        )
        self.assertIn(
            "[Completed] Prototype VC Data Model 2.0 signing and verification",
            readme,
        )
        self.assertIn(
            "[Completed] Add MongoDB-backed credential lifecycle status, irreversible revocation",
            readme,
        )
        self.assertIn(
            "[Completed] Add W3C-oriented Bitstring Status List publication",
            readme,
        )
        self.assertIn(
            "[Completed] Add issuance-time credential-status binding",
            readme,
        )
        self.assertIn(
            "[Completed] Add short-lived multi-credential Verifiable Presentations",
            readme,
        )
        self.assertIn(
            "[Completed] Add holder wallets, object ownership, opaque key references",
            readme,
        )
        self.assertIn(
            "[Next] Replace local fixture signing with an externally reviewed KMS/HSM",
            readme,
        )

    def test_all_local_markdown_links_resolve(self) -> None:
        for markdown_file in PROJECT_ROOT.rglob("*.md"):
            relative_path = markdown_file.relative_to(PROJECT_ROOT)
            if {".venv", "node_modules", "dist"}.intersection(relative_path.parts):
                continue
            content = markdown_file.read_text(encoding="utf-8")
            for raw_target in LOCAL_LINK_PATTERN.findall(content):
                target = raw_target.split("#", maxsplit=1)[0].strip()
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                resolved = markdown_file.parent / unquote(target)
                with self.subTest(
                    document=relative_path,
                    link=raw_target,
                ):
                    self.assertTrue(
                        resolved.exists(),
                        f"Broken local link: {raw_target}",
                    )


if __name__ == "__main__":
    unittest.main()
