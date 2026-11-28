"""The legacy-to-organization migration plan is read-only and never guesses ambiguous mappings."""

from copy import deepcopy

from app.infrastructure.persistence.memory_db import MemoryDatabase
from app.tools.organization_migration_plan import build_plan


def seeded() -> MemoryDatabase:
    db = MemoryDatabase()
    users = [
        {"_id": "u1", "roles": ["issuer"], "enabled": True, "issuerDid": "did:web:uni.example"},
        {"_id": "u2", "roles": ["verifier"], "enabled": True},
        {"_id": "u3", "roles": ["issuer"], "enabled": False},
        {"_id": "u4", "roles": ["holder"], "enabled": True},
        {"_id": "u5", "roles": ["issuer"], "enabled": True, "issuerDid": "did:web:shared.example"},
        {"_id": "u6", "roles": ["issuer"], "enabled": True, "issuerDid": "did:web:shared.example"},
    ]
    for user in users:
        db["users"].documents.append(user)
    for row in [
        {"userId": "u1", "organization": "Example University", "status": "APPROVED"},
        {"userId": "u2", "organization": "  example   university ", "status": "APPROVED"},
        {"userId": "u5", "organization": "Alpha Corp", "status": "APPROVED"},
        {"userId": "u6", "organization": "Beta Corp", "status": "APPROVED"},
    ]:
        db["onboarding_requests"].documents.append(row)
    return db


def test_plan_groups_consistent_accounts_and_flags_the_rest() -> None:
    db = seeded()
    before = deepcopy({name: c.documents for name, c in db.collections.items()})
    plan = build_plan(db)
    assert plan["mode"].startswith("dry-run")
    assert plan["legacyAccounts"] == 5  # the holder is not a legacy organization account
    uni = [p for p in plan["proposedOrganizations"] if p["proposedLegalName"] == "Example University"][0]
    assert {m["userId"] for m in uni["members"]} == {"u1", "u2"}
    assert {c["type"] for c in uni["capabilities"]} == {"ISSUER", "VERIFIER"}
    assert all(c["status"] == "PENDING" for c in uni["capabilities"]) and uni["orgAdmin"] is None
    assert uni["status"] == "SUBMITTED" and uni["organizationType"] == "OTHER_INSTITUTION"
    assert "Example University" in plan["flaggedSpellingMerges"]
    assert any(item["userId"] == "u3" for item in plan["manualReview"] if "userId" in item)
    assert any(c["issuerDid"] == "did:web:shared.example" for c in plan["conflicts"] if "issuerDid" in c)
    assert not any(p["proposedLegalName"] in {"Alpha Corp", "Beta Corp"} for p in plan["proposedOrganizations"])
    after = {name: c.documents for name, c in db.collections.items()}
    assert before == after  # nothing written


def test_registry_name_fills_a_missing_onboarding_name_only_when_unambiguous() -> None:
    db = MemoryDatabase()
    db["users"].documents.append({"_id": "u9", "roles": ["issuer"], "enabled": True, "issuerDid": "did:web:reg.example"})
    db["trust_registry"].documents.append({"issuerDid": "did:web:reg.example", "organizationName": "Registry Org"})
    plan = build_plan(db)
    assert plan["proposedOrganizations"][0]["members"][0]["userId"] == "u9"
    db["trust_registry"].documents.append({"issuerDid": "did:web:reg.example", "organizationName": "Other Org"})
    assert build_plan(db)["manualReview"][0]["userId"] == "u9"
