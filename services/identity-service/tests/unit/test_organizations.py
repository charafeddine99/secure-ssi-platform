"""Organizations, memberships, invitations, capabilities and tenant isolation (offline, in-memory)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_current_principal, get_step_up_service
from app.api.v1.organizations import get_organization_service
from app.application.services import organization_service as module
from app.application.services.organization_service import OrganizationService, validate_redirect_uris
from app.application.services.step_up_service import StepUpService
from app.config.step_up_settings import StepUpSettings
from app.domain.auth import AuthenticatedPrincipal
from app.domain.organization import OrganizationForbiddenError, OrganizationStateError, OrgPermission, permissions_for
from app.domain.permissions import Role, permissions_for_roles
from app.infrastructure.persistence.memory_db import MemoryDatabase
from app.main import app


class Clock:
    def __init__(self) -> None:
        self.value = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.value


def person(user_id: str, email: str, *roles: Role) -> AuthenticatedPrincipal:
    roles = roles or (Role.HOLDER,)
    return AuthenticatedPrincipal(id=user_id, username=email, display_name=email, roles=roles,
                                  permissions=permissions_for_roles(roles), authentication_source="test",
                                  session_id=f"s-{user_id}")


ALICE = person("a" * 24, "alice@uni.example")
BOB = person("b" * 24, "bob@uni.example")
CAROL = person("c" * 24, "carol@corp.example")
REVIEWER = person("d" * 24, "reviewer@platform.example", Role.ADMIN)
MALLORY = person("e" * 24, "mallory@elsewhere.example")

APPLICATION = {
    "legalName": "Example University", "organizationType": "UNIVERSITY", "jurisdiction": "TR",
    "registrationReference": "listed on yok.gov.tr", "officialDomain": "uni.example",
    "website": "https://uni.example", "officialContact": "rectorate@uni.example (official line)",
    "applicantTitle": "Registrar", "authorityEvidence": "Signed authorization letter, ref 2026/14",
    "requestedCapabilities": ["ISSUER"], "intendedUse": "Issue diplomas to graduates",
}
APPROVE = {"decision": "APPROVE", "entityVerified": True, "entityEvidence": "Listed on the official YOK list",
           "representativeVerified": True, "representativeEvidence": "Letter confirmed by phone", "note": "ok"}


class World:
    def __init__(self) -> None:
        module._indexes_ready = False
        self.clock = Clock()
        self.events: list[tuple[str, str]] = []
        self.service = OrganizationService(MemoryDatabase(), clock=self.clock,
                                           record=lambda kind, subject, actor, meta: self.events.append((kind, meta.get("organizationId", ""))),
                                           production=False)
        self.who = ALICE
        step_up = StepUpService(factors=None, tokens=None, settings=StepUpSettings(
            environment="test", required=False, dual_control_required=False, token_secret="s" * 40,
            factor_key=b"f" * 32), issuer="t", clock=self.clock)
        app.dependency_overrides.update({
            get_organization_service: lambda: self.service,
            get_current_principal: lambda: self.who,
            get_step_up_service: lambda: step_up,
        })
        self.client = TestClient(app, raise_server_exceptions=False)

    def as_(self, principal: AuthenticatedPrincipal) -> TestClient:
        self.who = principal
        return self.client

    def active_org(self, applicant: AuthenticatedPrincipal = ALICE, name: str = "Example University") -> str:
        created = self.as_(applicant).post("/api/v1/organizations/applications", json={**APPLICATION, "legalName": name})
        assert created.status_code == 201, created.text
        org = created.json()["organizationId"]
        assert self.as_(REVIEWER).post(f"/api/v1/trust-review/organizations/{org}/decision", json=APPROVE).status_code == 200
        return org

    def invite_and_join(self, org: str, admin: AuthenticatedPrincipal, member: AuthenticatedPrincipal, roles: list[str]) -> str:
        made = self.as_(admin).post(f"/api/v1/organizations/{org}/invitations", json={"email": member.username, "roles": roles})
        assert made.status_code == 201, made.text
        joined = self.as_(member).post("/api/v1/organization-invitations/accept", json={"invitationCode": made.json()["invitationCode"]})
        assert joined.status_code == 200, joined.text
        return joined.json()["membershipId"]


@pytest.fixture
def world():
    state = World()
    yield state
    app.dependency_overrides.clear()


def test_application_waits_for_review_and_gives_no_power_meanwhile(world: World) -> None:
    created = world.as_(ALICE).post("/api/v1/organizations/applications", json=APPLICATION)
    assert created.status_code == 201 and created.json()["status"] == "SUBMITTED"
    org = created.json()["organizationId"]
    mine = world.as_(ALICE).get("/api/v1/organizations/mine").json()
    assert mine[0]["membership"]["status"] == "PENDING" and mine[0]["membership"]["roles"] == ["ORG_ADMIN"]
    assert world.as_(ALICE).get(f"/api/v1/organizations/{org}").status_code == 200  # can follow the application
    refused = world.as_(ALICE).post(f"/api/v1/organizations/{org}/invitations", json={"email": "x@uni.example", "roles": ["ORG_AUDITOR"]})
    assert refused.status_code == 404  # no active membership yet: nothing to act on


def test_approval_needs_both_entity_and_representative_checks(world: World) -> None:
    org = world.as_(ALICE).post("/api/v1/organizations/applications", json=APPLICATION).json()["organizationId"]
    half = world.as_(REVIEWER).post(f"/api/v1/trust-review/organizations/{org}/decision",
                                    json={**APPROVE, "representativeVerified": False})
    assert half.status_code == 409 and half.json()["error"]["code"] == "ORGANIZATION_STATE_CONFLICT"
    assert world.as_(REVIEWER).post(f"/api/v1/trust-review/organizations/{org}/decision", json=APPROVE).json()["status"] == "ACTIVE"
    assert world.as_(ALICE).get("/api/v1/organizations/mine").json()[0]["membership"]["status"] == "ACTIVE"
    assert ("ORGANIZATION_DECIDED", org) in world.events


def test_only_platform_reviewers_decide_and_never_for_their_own_organization(world: World) -> None:
    org = world.as_(ALICE).post("/api/v1/organizations/applications", json=APPLICATION).json()["organizationId"]
    assert world.as_(ALICE).post(f"/api/v1/trust-review/organizations/{org}/decision", json=APPROVE).status_code == 403
    assert world.as_(ALICE).get("/api/v1/trust-review/organizations").status_code == 403
    admin_applicant = person("f" * 24, "admin@uni.example", Role.ADMIN)
    own = world.as_(admin_applicant).post("/api/v1/organizations/applications", json=APPLICATION).json()["organizationId"]
    refused = world.as_(admin_applicant).post(f"/api/v1/trust-review/organizations/{own}/decision", json=APPROVE)
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "ORGANIZATION_PERMISSION_DENIED"


def test_one_organization_cannot_see_or_touch_another(world: World) -> None:
    uni = world.active_org(ALICE, "Example University")
    corp = world.active_org(CAROL, "Example Corp")
    for path in (f"/api/v1/organizations/{corp}", f"/api/v1/organizations/{corp}/members",
                 f"/api/v1/organizations/{corp}/capabilities", f"/api/v1/organizations/{corp}/invitations"):
        answer = world.as_(ALICE).get(path)
        assert answer.status_code == 404, path  # 404, not 403: the other tenant is invisible
    carol_member = world.as_(CAROL).get(f"/api/v1/organizations/{corp}/members").json()[0]["membershipId"]
    assert world.as_(ALICE).delete(f"/api/v1/organizations/{corp}/members/{carol_member}").status_code == 404
    assert world.as_(ALICE).delete(f"/api/v1/organizations/{uni}/members/{carol_member}").status_code == 404
    assert len(world.as_(CAROL).get(f"/api/v1/organizations/{corp}/members").json()) == 1


def test_invitations_are_bound_single_use_expiring_and_revocable(world: World) -> None:
    org = world.active_org()
    made = world.as_(ALICE).post(f"/api/v1/organizations/{org}/invitations", json={"email": "bob@uni.example", "roles": ["ISSUER_OPERATOR"]})
    code = made.json()["invitationCode"]
    assert "codeHash" not in str(made.json()) and code not in str(world.service._db["organization_invitations"].documents)
    assert world.as_(MALLORY).post("/api/v1/organization-invitations/accept", json={"invitationCode": code}).status_code == 400
    joined = world.as_(BOB).post("/api/v1/organization-invitations/accept", json={"invitationCode": code})
    assert joined.status_code == 200 and joined.json()["roles"] == ["ISSUER_OPERATOR"]
    replay = world.as_(BOB).post("/api/v1/organization-invitations/accept", json={"invitationCode": code})
    assert replay.status_code == 400 and replay.json()["error"]["code"] == "INVITATION_INVALID"
    late = world.as_(ALICE).post(f"/api/v1/organizations/{org}/invitations", json={"email": "carol@corp.example", "roles": ["ORG_AUDITOR"]}).json()
    world.clock.value += timedelta(hours=73)
    assert world.as_(CAROL).post("/api/v1/organization-invitations/accept", json={"invitationCode": late["invitationCode"]}).status_code == 400
    world.clock.value -= timedelta(hours=73)
    pulled = world.as_(ALICE).post(f"/api/v1/organizations/{org}/invitations", json={"email": "carol@corp.example", "roles": ["ORG_AUDITOR"]}).json()
    assert world.as_(ALICE).delete(f"/api/v1/organizations/{org}/invitations/{pulled['invitation']['invitationId']}").status_code == 204
    assert world.as_(CAROL).post("/api/v1/organization-invitations/accept", json={"invitationCode": pulled["invitationCode"]}).status_code == 400


def test_roles_limit_what_members_can_do(world: World) -> None:
    org = world.active_org()
    world.invite_and_join(org, ALICE, BOB, ["VERIFIER_OPERATOR"])
    assert world.as_(BOB).get(f"/api/v1/organizations/{org}").status_code == 200
    assert world.as_(BOB).post(f"/api/v1/organizations/{org}/invitations", json={"email": "z@uni.example", "roles": ["ORG_ADMIN"]}).status_code == 403
    bob_id = [m for m in world.as_(ALICE).get(f"/api/v1/organizations/{org}/members").json() if m["userId"] == BOB.id][0]["membershipId"]
    assert world.as_(BOB).put(f"/api/v1/organizations/{org}/members/{bob_id}/roles", json={"roles": ["ORG_ADMIN"]}).status_code == 403
    assert world.as_(ALICE).put(f"/api/v1/organizations/{org}/members/{bob_id}/roles", json={"roles": ["NOT_A_ROLE"]}).status_code == 409


def test_last_administrator_stays(world: World) -> None:
    org = world.active_org()
    alice_id = world.as_(ALICE).get(f"/api/v1/organizations/{org}/members").json()[0]["membershipId"]
    assert world.as_(ALICE).delete(f"/api/v1/organizations/{org}/members/{alice_id}").status_code == 409
    assert world.as_(ALICE).put(f"/api/v1/organizations/{org}/members/{alice_id}/roles", json={"roles": ["ORG_AUDITOR"]}).status_code == 409


def test_capabilities_are_approved_by_the_platform_not_by_the_organization(world: World) -> None:
    org = world.active_org()
    requested = world.as_(ALICE).post(f"/api/v1/organizations/{org}/capabilities", json={
        "type": "ISSUER", "credentialTypes": ["UniversityDegree"], "purpose": "Diplomas for graduates"})
    assert requested.status_code == 201 and requested.json()["status"] == "PENDING"
    cap = requested.json()["capabilityId"]
    assert world.as_(ALICE).post(f"/api/v1/trust-review/capabilities/{cap}/decision", json={"decision": "APPROVE", "note": "self"}).status_code == 403
    world.invite_and_join(org, ALICE, BOB, ["ISSUER_OPERATOR"])
    with pytest.raises(OrganizationStateError):  # issuing needs an ACTIVE issuer capability
        world.service.access(BOB, org, OrgPermission.CREDENTIAL_ISSUE)
    assert world.as_(REVIEWER).post(f"/api/v1/trust-review/capabilities/{cap}/decision", json={"decision": "APPROVE", "note": "ok"}).json()["status"] == "ACTIVE"
    world.service.access(BOB, org, OrgPermission.CREDENTIAL_ISSUE)
    with pytest.raises(OrganizationForbiddenError):  # an issuer operator's role does not include verifying
        world.service.access(BOB, org, OrgPermission.PRESENTATION_VERIFY)


def test_member_and_admin_of_a_reviewed_organization_cannot_review_it(world: World) -> None:
    org = world.active_org()
    staff_reviewer = person("9" * 24, "it@uni.example", Role.ADMIN)
    world.invite_and_join(org, ALICE, staff_reviewer, ["ORG_AUDITOR"])
    cap = world.as_(ALICE).post(f"/api/v1/organizations/{org}/capabilities", json={
        "type": "ISSUER", "credentialTypes": ["UniversityDegree"], "purpose": "Diplomas"}).json()["capabilityId"]
    assert world.as_(staff_reviewer).post(f"/api/v1/trust-review/capabilities/{cap}/decision", json={"decision": "APPROVE", "note": "staff"}).status_code == 403


def test_suspension_stops_actions_but_keeps_reading(world: World) -> None:
    org = world.active_org()
    suspend = {**APPROVE, "decision": "SUSPEND", "note": "registry check"}
    assert world.as_(REVIEWER).post(f"/api/v1/trust-review/organizations/{org}/decision", json=suspend).json()["status"] == "SUSPENDED"
    assert world.as_(ALICE).get(f"/api/v1/organizations/{org}").status_code == 200
    assert world.as_(ALICE).post(f"/api/v1/organizations/{org}/invitations", json={"email": "bob@uni.example", "roles": ["ORG_AUDITOR"]}).status_code == 409
    assert world.as_(ALICE).post(f"/api/v1/organizations/{org}/capabilities", json={
        "type": "ISSUER", "credentialTypes": ["UniversityDegree"], "purpose": "Diplomas"}).status_code == 409


def test_removed_membership_loses_access_at_once(world: World) -> None:
    org = world.active_org()
    bob_member = world.invite_and_join(org, ALICE, BOB, ["ORG_AUDITOR"])
    assert world.as_(BOB).get(f"/api/v1/organizations/{org}").status_code == 200
    assert world.as_(ALICE).delete(f"/api/v1/organizations/{org}/members/{bob_member}").status_code == 204
    assert world.as_(BOB).get(f"/api/v1/organizations/{org}").status_code == 404


def test_roles_in_two_organizations_do_not_mix(world: World) -> None:
    uni = world.active_org(ALICE, "Example University")
    corp = world.active_org(CAROL, "Example Corp")
    world.invite_and_join(uni, ALICE, BOB, ["ORG_AUDITOR"])
    world.invite_and_join(corp, CAROL, BOB, ["ORG_ADMIN"])
    assert world.as_(BOB).post(f"/api/v1/organizations/{corp}/invitations", json={"email": "q@corp.example", "roles": ["ORG_AUDITOR"]}).status_code == 201
    assert world.as_(BOB).post(f"/api/v1/organizations/{uni}/invitations", json={"email": "q@uni.example", "roles": ["ORG_AUDITOR"]}).status_code == 403
    orgs = {item["organization"]["organizationId"]: item["membership"]["roles"] for item in world.as_(BOB).get("/api/v1/organizations/mine").json()}
    assert orgs == {uni: ["ORG_AUDITOR"], corp: ["ORG_ADMIN"]}


def test_verifier_redirect_uris_must_be_exact(world: World) -> None:
    org = world.active_org()
    body = {"type": "VERIFIER", "credentialTypes": ["UniversityDegree"], "purpose": "Check degrees", "clientId": "verifier.uni.example"}
    for bad in (["https://uni.example/*"], ["https://uni.example/cb#x"], ["not-a-uri"], []):
        assert world.as_(ALICE).post(f"/api/v1/organizations/{org}/capabilities", json={**body, "redirectUris": bad}).status_code == 409
    ok = world.as_(ALICE).post(f"/api/v1/organizations/{org}/capabilities", json={**body, "redirectUris": ["https://uni.example/callback"]})
    assert ok.status_code == 201 and ok.json()["redirectUris"] == ["https://uni.example/callback"]
    with pytest.raises(OrganizationStateError):
        validate_redirect_uris(["http://uni.example/callback"], production=True)


def test_permission_matrix_keeps_duties_apart() -> None:
    assert OrgPermission.CREDENTIAL_ISSUE not in permissions_for(["ORG_ADMIN"])
    assert OrgPermission.MEMBERSHIP_INVITE not in permissions_for(["ISSUER_MANAGER", "VERIFIER_MANAGER"])
    assert permissions_for(["VERIFIER_OPERATOR"]) == {OrgPermission.ORGANIZATION_READ, OrgPermission.PRESENTATION_VERIFY}


def test_unknown_application_fields_and_client_supplied_ids_are_refused(world: World) -> None:
    forged = world.as_(ALICE).post("/api/v1/organizations/applications", json={**APPLICATION, "status": "ACTIVE"})
    assert forged.status_code == 422
    sneaky = world.as_(ALICE).post("/api/v1/organizations/applications", json={**APPLICATION, "applicantUserId": BOB.id})
    assert sneaky.status_code == 422


def _unused(_: Any) -> None:  # keeps the import list honest for linters
    return None
