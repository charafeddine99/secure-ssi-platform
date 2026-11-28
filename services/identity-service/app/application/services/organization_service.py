"""Organization applications, verification review, memberships, invitations and capabilities.

Authorization is decided here, on the server, for every call, in this order: the organization exists and
the caller has an ACTIVE membership in it (otherwise 404, so other tenants' organizations are invisible),
the membership's roles grant the permission, the organization is ACTIVE (reads are still allowed while it
is SUSPENDED), and, for issuing or verifying, the matching capability is ACTIVE. The organization context
always comes from the request path and is re-checked against the stored membership; nothing about
organizations is carried in the access token, so removing a membership takes effect on the next request.

Platform decisions (approving an organization or a capability) need the platform permission
``trust-review:decide``, and the reviewer may not be a member or the applicant of that organization:
nobody approves their own organization or capability.
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from urllib.parse import urlsplit

from pymongo import ASCENDING, IndexModel

from app.domain.auth import AuthenticatedPrincipal
from app.domain.organization import (
    CAPABILITY_FOR_PERMISSION,
    CapabilityStatus,
    CapabilityType,
    InvitationInvalidError,
    MembershipStatus,
    OrganizationForbiddenError,
    OrganizationNotFoundError,
    OrganizationStateError,
    OrganizationStatus,
    OrganizationType,
    OrgPermission,
    OrgRole,
    parse_roles,
    permissions_for,
)

ORGANIZATIONS = "organizations"
MEMBERSHIPS = "organization_memberships"
CAPABILITIES = "organization_capabilities"
INVITATIONS = "organization_invitations"
INVITATION_LIFETIME = timedelta(hours=72)
_CLIENT_ID = re.compile(r"^[A-Za-z0-9._:/-]{3,200}$")
_DID = re.compile(r"^did:[a-z0-9]+:[A-Za-z0-9._:%-]{1,2000}$")
_TYPE = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
_INDEXES = {
    MEMBERSHIPS: [IndexModel([("organizationId", ASCENDING), ("userId", ASCENDING)], unique=True,
                             name="uq_membership_org_user"),
                  IndexModel([("userId", ASCENDING)], name="ix_membership_user")],
    INVITATIONS: [IndexModel([("codeHash", ASCENDING)], unique=True, name="uq_invitation_code"),
                  IndexModel([("organizationId", ASCENDING)], name="ix_invitation_org")],
    CAPABILITIES: [IndexModel([("organizationId", ASCENDING)], name="ix_capability_org")],
    ORGANIZATIONS: [IndexModel([("status", ASCENDING)], name="ix_organization_status")],
}
_indexes_ready = False

Recorder = Callable[[str, str, str, dict[str, str]], None]


def _digest(code: str) -> str:
    return sha256(code.encode()).hexdigest()


def _roles(values: list[str]) -> list[str]:
    try:
        return [role.value for role in parse_roles(values)]
    except ValueError as error:
        raise OrganizationStateError("Unknown or missing organization role.") from error


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def validate_redirect_uris(values: list[str], *, production: bool) -> list[str]:
    """Exact URIs only (RFC 9700 2.1): absolute, no fragment, no wildcard; HTTPS outside development."""
    cleaned: list[str] = []
    for value in values:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"https", "http"}
            or not parts.hostname
            or parts.fragment
            or "*" in value
            or any(ch.isspace() for ch in value)
            or len(value) > 2000
            or (production and parts.scheme != "https")
        ):
            raise OrganizationStateError("Each redirect URI must be an exact absolute HTTPS URI without a fragment.")
        cleaned.append(value)
    if not cleaned or len(cleaned) > 10 or len(set(cleaned)) != len(cleaned):
        raise OrganizationStateError("Give one to ten different redirect URIs.")
    return cleaned


class OrganizationService:
    def __init__(self, database: Any, *, clock: Callable[[], datetime], record: Recorder,
                 production: bool = False) -> None:
        self._db = database
        self._clock = clock
        self._record = record
        self._production = production
        global _indexes_ready
        if not _indexes_ready:
            for name, indexes in _INDEXES.items():
                self._db[name].create_indexes(indexes)
            _indexes_ready = True

    # ---------------------------------------------------------------- applications
    def apply(self, principal: AuthenticatedPrincipal, *, legal_name: str, organization_type: str,
              jurisdiction: str, registration_reference: str | None, official_domain: str | None,
              website: str | None, official_contact: str, applicant_title: str, authority_evidence: str,
              requested_capabilities: list[str], intended_use: str) -> dict[str, Any]:
        """Any signed-in person may apply on behalf of an organization; nothing is active until reviewed."""
        now = self._now()
        organization = {
            "_id": "org_" + secrets.token_urlsafe(12),
            "legalName": legal_name.strip(),
            "organizationType": OrganizationType(organization_type).value,
            "jurisdiction": jurisdiction.strip(),
            # Type-specific: a trade-registry (MERSİS) number for a company, a DETSİS number for a public
            # body, an official list or founding law for a university. Optional, checked by a reviewer.
            "registrationReference": (registration_reference or "").strip() or None,
            "officialDomain": (official_domain or "").strip().casefold() or None,
            "website": (website or "").strip() or None,
            "officialContact": official_contact.strip(),
            "status": OrganizationStatus.SUBMITTED.value,
            "application": {
                "applicantUserId": principal.id,
                "applicantTitle": applicant_title.strip(),
                "authorityEvidence": authority_evidence.strip(),
                "requestedCapabilities": sorted({CapabilityType(c).value for c in requested_capabilities}),
                "intendedUse": intended_use.strip(),
                "submittedAt": now,
            },
            "review": None,
            "history": [{"status": OrganizationStatus.SUBMITTED.value, "by": principal.id, "at": now}],
            "createdAt": now,
            "updatedAt": now,
        }
        self._db[ORGANIZATIONS].insert_one(organization)
        self._db[MEMBERSHIPS].insert_one({
            "_id": "mem_" + secrets.token_urlsafe(12), "organizationId": organization["_id"],
            "userId": principal.id, "roles": [OrgRole.ORG_ADMIN.value],
            "status": MembershipStatus.PENDING.value, "invitedBy": None, "createdAt": now, "acceptedAt": None,
        })
        self._record("ORGANIZATION_APPLIED", organization["_id"], principal.id, {"organizationId": organization["_id"]})
        return organization

    def my_organizations(self, principal: AuthenticatedPrincipal) -> list[dict[str, Any]]:
        out = []
        for membership in self._db[MEMBERSHIPS].find({"userId": principal.id}):
            if membership["status"] == MembershipStatus.REMOVED.value:
                continue
            organization = self._db[ORGANIZATIONS].find_one({"_id": membership["organizationId"]})
            if organization is not None:
                out.append({"organization": organization, "membership": membership})
        return out

    # ---------------------------------------------------------------- access checks
    def access(self, principal: AuthenticatedPrincipal, organization_id: str, permission: OrgPermission,
               ) -> tuple[dict[str, Any], dict[str, Any]]:
        organization = self._db[ORGANIZATIONS].find_one({"_id": organization_id})
        membership = self._db[MEMBERSHIPS].find_one({"organizationId": organization_id, "userId": principal.id})
        if organization is None or membership is None or membership["status"] != MembershipStatus.ACTIVE.value:
            raise OrganizationNotFoundError("Organization not found.")
        if permission not in permissions_for(membership["roles"]):
            raise OrganizationForbiddenError("Your role in this organization does not allow this.")
        read_only = permission in {OrgPermission.ORGANIZATION_READ, OrgPermission.AUDIT_READ}
        if organization["status"] != OrganizationStatus.ACTIVE.value and not (
            read_only and organization["status"] == OrganizationStatus.SUSPENDED.value
        ):
            raise OrganizationStateError(f"The organization is {organization['status'].lower()}.")
        capability_type = CAPABILITY_FOR_PERMISSION.get(permission)
        if capability_type is not None and self._db[CAPABILITIES].find_one({
            "organizationId": organization_id, "type": capability_type.value, "status": CapabilityStatus.ACTIVE.value,
        }) is None:
            raise OrganizationStateError(f"The organization has no active {capability_type.value.lower()} capability.")
        return organization, membership

    def get(self, principal: AuthenticatedPrincipal, organization_id: str) -> dict[str, Any]:
        membership = self._db[MEMBERSHIPS].find_one({"organizationId": organization_id, "userId": principal.id})
        organization = self._db[ORGANIZATIONS].find_one({"_id": organization_id})
        # The applicant can follow their own pending application.
        if organization is not None and membership is not None and membership["status"] == MembershipStatus.PENDING.value:
            return organization
        return self.access(principal, organization_id, OrgPermission.ORGANIZATION_READ)[0]

    # ---------------------------------------------------------------- members
    def members(self, principal: AuthenticatedPrincipal, organization_id: str) -> list[dict[str, Any]]:
        self.access(principal, organization_id, OrgPermission.ORGANIZATION_READ)
        return [m for m in self._db[MEMBERSHIPS].find({"organizationId": organization_id})
                if m["status"] != MembershipStatus.REMOVED.value]

    def set_roles(self, principal: AuthenticatedPrincipal, organization_id: str, membership_id: str,
                  roles: list[str]) -> dict[str, Any]:
        self.access(principal, organization_id, OrgPermission.MEMBERSHIP_ROLES_ASSIGN)
        target = self._member(organization_id, membership_id)
        chosen = _roles(roles)
        if OrgRole.ORG_ADMIN.value in target["roles"] and OrgRole.ORG_ADMIN.value not in chosen:
            self._keep_an_admin(organization_id, membership_id)
        self._db[MEMBERSHIPS].update_one({"_id": membership_id, "organizationId": organization_id},
                                         {"$set": {"roles": chosen, "updatedAt": self._now()}})
        self._record("MEMBERSHIP_CHANGED", target["userId"], principal.id, {"organizationId": organization_id})
        return {**target, "roles": chosen}

    def remove_member(self, principal: AuthenticatedPrincipal, organization_id: str, membership_id: str) -> None:
        self.access(principal, organization_id, OrgPermission.MEMBERSHIP_REMOVE)
        target = self._member(organization_id, membership_id)
        if OrgRole.ORG_ADMIN.value in target["roles"]:
            self._keep_an_admin(organization_id, membership_id)
        self._db[MEMBERSHIPS].update_one({"_id": membership_id, "organizationId": organization_id},
                                         {"$set": {"status": MembershipStatus.REMOVED.value, "updatedAt": self._now()}})
        self._record("MEMBERSHIP_CHANGED", target["userId"], principal.id, {"organizationId": organization_id})

    def _member(self, organization_id: str, membership_id: str) -> dict[str, Any]:
        target = self._db[MEMBERSHIPS].find_one({"_id": membership_id, "organizationId": organization_id})
        if target is None or target["status"] != MembershipStatus.ACTIVE.value:
            raise OrganizationNotFoundError("Member not found.")
        return target

    def _keep_an_admin(self, organization_id: str, leaving_id: str) -> None:
        others = [m for m in self._db[MEMBERSHIPS].find({"organizationId": organization_id})
                  if m["_id"] != leaving_id and m["status"] == MembershipStatus.ACTIVE.value
                  and OrgRole.ORG_ADMIN.value in m["roles"]]
        if not others:
            raise OrganizationStateError("An organization must keep at least one active administrator.")

    # ---------------------------------------------------------------- invitations
    def invite(self, principal: AuthenticatedPrincipal, organization_id: str, email: str,
               roles: list[str]) -> tuple[str, dict[str, Any]]:
        """The code is returned once; only its digest is stored. Bound to one address and one organization."""
        self.access(principal, organization_id, OrgPermission.MEMBERSHIP_INVITE)
        chosen = _roles(roles)
        code = secrets.token_urlsafe(32)
        now = self._now()
        invitation = {
            "_id": "inv_" + secrets.token_urlsafe(12), "organizationId": organization_id,
            "email": email.strip().casefold(), "roles": chosen, "codeHash": _digest(code),
            "status": "OPEN", "invitedBy": principal.id, "createdAt": now,
            "expiresAt": now + INVITATION_LIFETIME, "usedAt": None, "usedBy": None,
        }
        self._db[INVITATIONS].insert_one(invitation)
        self._record("MEMBERSHIP_INVITED", organization_id, principal.id, {"organizationId": organization_id})
        return code, invitation

    def invitations(self, principal: AuthenticatedPrincipal, organization_id: str) -> list[dict[str, Any]]:
        self.access(principal, organization_id, OrgPermission.MEMBERSHIP_INVITE)
        return list(self._db[INVITATIONS].find({"organizationId": organization_id}))

    def revoke_invitation(self, principal: AuthenticatedPrincipal, organization_id: str, invitation_id: str) -> None:
        self.access(principal, organization_id, OrgPermission.MEMBERSHIP_INVITE)
        result = self._db[INVITATIONS].update_one(
            {"_id": invitation_id, "organizationId": organization_id, "status": "OPEN"},
            {"$set": {"status": "REVOKED", "revokedAt": self._now(), "revokedBy": principal.id}})
        if result.matched_count != 1:
            raise OrganizationNotFoundError("Open invitation not found.")

    def accept_invitation(self, principal: AuthenticatedPrincipal, code: str) -> dict[str, Any]:
        now = self._now()
        invitation = self._db[INVITATIONS].find_one({"codeHash": _digest(code)})
        if (
            invitation is None
            or invitation["status"] != "OPEN"
            or _aware(invitation["expiresAt"]) <= now
            or invitation["email"] != principal.username.strip().casefold()
        ):
            # The same answer for unknown, used, revoked, expired and someone else's invitation.
            raise InvitationInvalidError("This invitation is not valid for your account.")
        organization = self._db[ORGANIZATIONS].find_one({"_id": invitation["organizationId"]})
        if organization is None or organization["status"] != OrganizationStatus.ACTIVE.value:
            raise InvitationInvalidError("This invitation is not valid for your account.")
        claimed = self._db[INVITATIONS].update_one(
            {"_id": invitation["_id"], "status": "OPEN"},
            {"$set": {"status": "USED", "usedAt": now, "usedBy": principal.id}})
        if claimed.matched_count != 1:
            raise InvitationInvalidError("This invitation is not valid for your account.")
        existing = self._db[MEMBERSHIPS].find_one({"organizationId": organization["_id"], "userId": principal.id})
        fields = {"roles": invitation["roles"], "status": MembershipStatus.ACTIVE.value,
                  "invitedBy": invitation["invitedBy"], "acceptedAt": now, "updatedAt": now}
        if existing is None:
            membership = {"_id": "mem_" + secrets.token_urlsafe(12), "organizationId": organization["_id"],
                          "userId": principal.id, "createdAt": now, **fields}
            self._db[MEMBERSHIPS].insert_one(membership)
        else:
            self._db[MEMBERSHIPS].update_one({"_id": existing["_id"]}, {"$set": fields})
            membership = {**existing, **fields}
        self._record("MEMBERSHIP_JOINED", principal.id, principal.id, {"organizationId": organization["_id"]})
        return membership

    # ---------------------------------------------------------------- capabilities
    def request_capability(self, principal: AuthenticatedPrincipal, organization_id: str, capability: str,
                           *, credential_types: list[str], purpose: str, issuer_did: str | None = None,
                           client_id: str | None = None, redirect_uris: list[str] | None = None) -> dict[str, Any]:
        self.access(principal, organization_id, OrgPermission.ORGANIZATION_MANAGE)
        kind = CapabilityType(capability)
        if not credential_types or any(not _TYPE.fullmatch(t) for t in credential_types):
            raise OrganizationStateError("List the credential types this capability covers.")
        details: dict[str, Any] = {"credentialTypes": sorted(set(credential_types)), "purpose": purpose.strip()}
        if kind is CapabilityType.ISSUER:
            if issuer_did and not _DID.fullmatch(issuer_did):
                raise OrganizationStateError("The issuer identifier must be a DID.")
            details["issuerDid"] = issuer_did
        else:
            if not client_id or not _CLIENT_ID.fullmatch(client_id):
                raise OrganizationStateError("A verifier needs a client identifier.")
            details["clientId"] = client_id
            details["redirectUris"] = validate_redirect_uris(redirect_uris or [], production=self._production)
        if self._db[CAPABILITIES].find_one({"organizationId": organization_id, "type": kind.value,
                                            "status": {"$in": ["PENDING", "ACTIVE"]}}):
            raise OrganizationStateError(f"An {kind.value.lower()} capability is already pending or active.")
        now = self._now()
        record = {"_id": "cap_" + secrets.token_urlsafe(12), "organizationId": organization_id, "type": kind.value,
                  "status": CapabilityStatus.PENDING.value, "details": details, "requestedBy": principal.id,
                  "history": [{"status": "PENDING", "by": principal.id, "at": now}], "createdAt": now, "updatedAt": now}
        self._db[CAPABILITIES].insert_one(record)
        self._record("CAPABILITY_REQUESTED", organization_id, principal.id,
                     {"organizationId": organization_id, "capability": kind.value})
        return record

    def capabilities(self, principal: AuthenticatedPrincipal, organization_id: str) -> list[dict[str, Any]]:
        self.access(principal, organization_id, OrgPermission.ORGANIZATION_READ)
        return list(self._db[CAPABILITIES].find({"organizationId": organization_id}))

    # ---------------------------------------------------------------- platform review
    def review_queue(self, status: str) -> list[dict[str, Any]]:
        return list(self._db[ORGANIZATIONS].find({"status": OrganizationStatus(status).value}).sort("createdAt", 1).limit(200))

    def capability_queue(self, status: str) -> list[dict[str, Any]]:
        return list(self._db[CAPABILITIES].find({"status": CapabilityStatus(status).value}).sort("createdAt", 1).limit(200))

    def decide_organization(self, reviewer: AuthenticatedPrincipal, organization_id: str, decision: str, *,
                            entity_verified: bool, entity_evidence: str, representative_verified: bool,
                            representative_evidence: str, note: str) -> dict[str, Any]:
        """Two separate checks: does the organization exist, and may the applicant act for it."""
        organization = self._db[ORGANIZATIONS].find_one({"_id": organization_id})
        if organization is None:
            raise OrganizationNotFoundError("Organization not found.")
        self._not_involved(reviewer, organization_id, organization)
        allowed = {
            "APPROVE": ({"SUBMITTED"}, "ACTIVE"), "REJECT": ({"SUBMITTED"}, "REJECTED"),
            "SUSPEND": ({"ACTIVE"}, "SUSPENDED"), "REINSTATE": ({"SUSPENDED"}, "ACTIVE"),
            "REVOKE": ({"ACTIVE", "SUSPENDED"}, "REVOKED"),
        }
        if decision not in allowed or organization["status"] not in allowed[decision][0]:
            raise OrganizationStateError(f"Cannot {decision.lower()} an organization that is {organization['status'].lower()}.")
        if decision == "APPROVE" and not (entity_verified and representative_verified):
            raise OrganizationStateError("Approval needs both the organization and the applicant's authority verified.")
        new_status = allowed[decision][1]
        now = self._now()
        review = {"decision": decision, "entityVerified": entity_verified, "entityEvidence": entity_evidence.strip(),
                  "representativeVerified": representative_verified,
                  "representativeEvidence": representative_evidence.strip(), "note": note.strip(),
                  "reviewerId": reviewer.id, "decidedAt": now}
        result = self._db[ORGANIZATIONS].update_one(
            {"_id": organization_id, "status": organization["status"]},
            {"$set": {"status": new_status, "review": review, "updatedAt": now,
                      "history": [*organization.get("history", []), {"status": new_status, "by": reviewer.id, "at": now}]}})
        if result.matched_count != 1:
            raise OrganizationStateError("The organization changed meanwhile. Reload and try again.")
        if decision == "APPROVE":
            applicant = organization["application"]["applicantUserId"]
            self._db[MEMBERSHIPS].update_one(
                {"organizationId": organization_id, "userId": applicant, "status": MembershipStatus.PENDING.value},
                {"$set": {"status": MembershipStatus.ACTIVE.value, "acceptedAt": now}})
        self._record("ORGANIZATION_DECIDED", organization_id, reviewer.id,
                     {"organizationId": organization_id, "decision": decision})
        return {**organization, "status": new_status, "review": review}

    def decide_capability(self, reviewer: AuthenticatedPrincipal, capability_id: str, decision: str,
                          note: str) -> dict[str, Any]:
        capability = self._db[CAPABILITIES].find_one({"_id": capability_id})
        if capability is None:
            raise OrganizationNotFoundError("Capability not found.")
        organization = self._db[ORGANIZATIONS].find_one({"_id": capability["organizationId"]})
        self._not_involved(reviewer, capability["organizationId"], organization)
        allowed = {"APPROVE": ({"PENDING"}, "ACTIVE"), "REJECT": ({"PENDING"}, "REJECTED"),
                   "SUSPEND": ({"ACTIVE"}, "SUSPENDED"), "REINSTATE": ({"SUSPENDED"}, "ACTIVE"),
                   "REVOKE": ({"ACTIVE", "SUSPENDED"}, "REVOKED")}
        if decision not in allowed or capability["status"] not in allowed[decision][0]:
            raise OrganizationStateError(f"Cannot {decision.lower()} a capability that is {capability['status'].lower()}.")
        if decision in {"APPROVE", "REINSTATE"} and (organization is None or organization["status"] != "ACTIVE"):
            raise OrganizationStateError("Only an active organization can hold an active capability.")
        new_status = allowed[decision][1]
        now = self._now()
        result = self._db[CAPABILITIES].update_one(
            {"_id": capability_id, "status": capability["status"]},
            {"$set": {"status": new_status, "decisionNote": note.strip(), "decidedBy": reviewer.id, "updatedAt": now,
                      "history": [*capability.get("history", []), {"status": new_status, "by": reviewer.id, "at": now}]}})
        if result.matched_count != 1:
            raise OrganizationStateError("The capability changed meanwhile. Reload and try again.")
        self._record("CAPABILITY_DECIDED", capability["organizationId"], reviewer.id,
                     {"organizationId": capability["organizationId"], "capability": capability["type"],
                      "decision": decision})
        return {**capability, "status": new_status}

    def _not_involved(self, reviewer: AuthenticatedPrincipal, organization_id: str, organization: dict | None) -> None:
        applicant = (organization or {}).get("application", {}).get("applicantUserId")
        member = self._db[MEMBERSHIPS].find_one({"organizationId": organization_id, "userId": reviewer.id})
        if applicant == reviewer.id or member is not None:
            raise OrganizationForbiddenError("You cannot review an organization you belong to or applied for.")

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC)
