"""Dry-run plan for moving legacy issuer/verifier accounts into organizations. Never writes anything.

    python -m app.tools.organization_migration_plan [--output plan.json]

Legacy accounts carry a global ``issuer`` or ``verifier`` role. This reads them, their onboarding requests
(organization name), their issuer DID scope and the trust registry, and proposes one organization per
consistent group with the members' proposed roles and the capabilities to review. Anything that could put
a person in the wrong organization is not proposed but listed for manual review:

- the same issuer DID under different organization names (or the reverse);
- an account with no organization name and no issuer DID;
- an organization name that differs only by case/spacing from another (merged, but flagged).

Nobody becomes ORG_ADMIN automatically, every proposed capability starts as PENDING for trust review, and
user ids, DIDs, credentials, wallets and keys are never changed. Applying a plan is a separate, owner-approved
step (snapshot first, isolated database first).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from typing import Any


def _norm(name: str | None) -> str | None:
    if not name or not name.strip():
        return None
    return re.sub(r"\s+", " ", name.strip()).casefold()


def build_plan(database: Any) -> dict[str, Any]:
    legacy = [u for u in database["users"].find({}) if {"issuer", "verifier"} & set(u.get("roles", []))]
    onboarding = {row.get("userId"): row for row in database["onboarding_requests"].find({})}
    registry: dict[str, set[str]] = defaultdict(set)
    for row in database["trust_registry"].find({}):
        did = row.get("issuerDid") or row.get("issuer_did")
        name = _norm(row.get("organizationName") or row.get("organization_name"))
        if did and name:
            registry[did].add(name)
    groups: dict[str, dict[str, Any]] = {}
    manual: list[dict[str, Any]] = []
    did_names: dict[str, set[str]] = defaultdict(set)
    spellings: dict[str, set[str]] = defaultdict(set)
    for user in legacy:
        user_id = str(user.get("_id"))
        did = user.get("issuerDid")
        request = onboarding.get(user_id) or {}
        raw = request.get("organization")
        name = _norm(raw)
        if name is None and did and len(registry.get(did, set())) == 1:
            name = next(iter(registry[did]))
        if name is None:
            manual.append({"userId": user_id, "reason": "no organization name and no unambiguous issuer DID"})
            continue
        if raw:
            spellings[name].add(raw.strip())
        if did:
            did_names[did].add(name)
        group = groups.setdefault(name, {"proposedLegalName": (raw or name).strip(), "members": [],
                                         "issuerDids": set(), "capabilities": set()})
        roles = []
        if "issuer" in user.get("roles", []):
            roles.append("ISSUER_MANAGER")
            group["capabilities"].add("ISSUER")
        if "verifier" in user.get("roles", []):
            roles.append("VERIFIER_MANAGER")
            group["capabilities"].add("VERIFIER")
        group["members"].append({"userId": user_id, "proposedRoles": roles, "enabled": bool(user.get("enabled", True)),
                                 "onboardingStatus": request.get("status")})
        if did:
            group["issuerDids"].add(did)
    conflicts = []
    for did, names in did_names.items():
        if len(names) > 1:
            conflicts.append({"issuerDid": did, "organizationNames": sorted(names),
                              "reason": "one issuer DID under several organization names"})
    for name, group in groups.items():
        if len(group["issuerDids"]) > 1:
            conflicts.append({"organizationName": name, "issuerDids": sorted(group["issuerDids"]),
                              "reason": "one organization name with several issuer DIDs"})
    blocked_names = {n for c in conflicts for n in c.get("organizationNames", [])} | {
        c["organizationName"] for c in conflicts if "organizationName" in c}
    proposals = []
    for name, group in sorted(groups.items()):
        entry = {
            "proposedLegalName": group["proposedLegalName"],
            "organizationType": "OTHER_INSTITUTION",  # to be set by a reviewer; never guessed
            "status": "SUBMITTED",  # still needs entity and representative verification
            "members": group["members"],
            "orgAdmin": None,  # chosen by the owner, never automatic
            "capabilities": [{"type": c, "status": "PENDING"} for c in sorted(group["capabilities"])],
            "issuerDids": sorted(group["issuerDids"]),
            "spellingsMerged": sorted(spellings.get(name, set())),
        }
        (manual if name in blocked_names else proposals).append(
            entry if name not in blocked_names else {"group": entry, "reason": "conflict, see conflicts"})
    return {
        "mode": "dry-run (nothing written)",
        "legacyAccounts": len(legacy),
        "proposedOrganizations": proposals,
        "manualReview": manual,
        "conflicts": conflicts,
        "flaggedSpellingMerges": [p["proposedLegalName"] for p in proposals if len(p["spellingsMerged"]) > 1],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run organization migration plan (read-only).")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    from pymongo import MongoClient

    client = MongoClient(os.environ["IDENTITY_MONGO_URI"], tz_aware=True, serverSelectionTimeoutMS=5000)
    plan = build_plan(client[os.environ.get("IDENTITY_MONGO_DATABASE", "secure_identity")])
    text = json.dumps(plan, indent=1, default=str)
    if args.output == "-":
        print(text)
    else:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
