"""WP-28: Admin recovery oversight and owner/Guardian timeline."""

from tests.integration.test_recovery_api import _configure, _headers, api  # noqa: F401
from tests.support import WALLET_ID


def _start(client, runtime) -> dict:
    created = client.post(
        "/api/v1/recovery/requests",
        headers=_headers(runtime.owner.user_id),
        json={"walletId": WALLET_ID, "reason": "DEVICE_LOSS"},
    )
    assert created.status_code == 201, created.text
    return created.json()


def _approve(client, runtime, body: dict, guardian_ids: list[str], index: int):
    return client.post(
        f"/api/v1/recovery/requests/{body['requestId']}/approve",
        headers=_headers(runtime.guardians[index].user_id),
        json={
            "guardianId": guardian_ids[index],
            "challenge": body["challenge"],
            "proof": runtime.sign_decision(
                guardian_id=guardian_ids[index],
                request_id=body["requestId"],
                challenge=body["challenge"],
            ),
        },
    )


def test_admin_oversight_lists_cases_without_guardian_challenge(api) -> None:
    client, runtime = api
    guardian_ids = _configure(client, runtime)
    body = _start(client, runtime)
    assert _approve(client, runtime, body, guardian_ids, 0).status_code == 200

    listed = client.get(
        "/api/v1/recovery/admin/requests", headers=_headers(runtime.admin.user_id, "admin")
    )
    detail = client.get(
        f"/api/v1/recovery/admin/requests/{body['requestId']}",
        headers=_headers(runtime.admin.user_id, "admin"),
    )

    assert listed.status_code == 200, listed.text
    [case] = listed.json()["items"]
    assert case["state"] == "PENDING_APPROVALS"
    assert case["approvalCount"] == 1 and case["minimumApprovals"] == 3
    assert detail.status_code == 200
    events = [item["eventType"] for item in detail.json()["timeline"]]
    assert events[:2] == ["RECOVERY_REQUESTED", "RECOVERY_APPROVED"]
    for response in (listed, detail):
        assert body["challenge"] not in response.text
        assert body["nonce"] not in response.text
        assert "challenge" not in response.text.casefold()
        assert "proof" not in response.text.casefold()


def test_oversight_is_admin_only_and_state_filter_works(api) -> None:
    client, runtime = api
    _configure(client, runtime)
    body = _start(client, runtime)

    for user, role in (
        (runtime.owner.user_id, "holder"),
        (runtime.guardians[0].user_id, "holder"),
        ("usr_wp28_issuer", "issuer"),
        ("usr_wp28_verifier", "verifier"),
    ):
        denied = client.get("/api/v1/recovery/admin/requests", headers=_headers(user, role))
        assert denied.status_code == 403, (role, denied.text)
        detail = client.get(
            f"/api/v1/recovery/admin/requests/{body['requestId']}",
            headers=_headers(user, role),
        )
        assert detail.status_code == 403
    unauthenticated = client.get("/api/v1/recovery/admin/requests")
    assert unauthenticated.status_code == 401

    admin = _headers(runtime.admin.user_id, "admin")
    pending = client.get("/api/v1/recovery/admin/requests?state=PENDING_APPROVALS", headers=admin)
    completed = client.get("/api/v1/recovery/admin/requests?state=COMPLETED", headers=admin)
    invalid = client.get("/api/v1/recovery/admin/requests?state=FORCE_APPROVED", headers=admin)
    assert len(pending.json()["items"]) == 1
    assert completed.json()["items"] == []
    assert invalid.status_code == 422


def test_admin_cannot_vote_or_bypass_quorum(api) -> None:
    client, runtime = api
    guardian_ids = _configure(client, runtime)
    body = _start(client, runtime)
    admin = _headers(runtime.admin.user_id, "admin")

    forged = client.post(
        f"/api/v1/recovery/requests/{body['requestId']}/approve",
        headers=admin,
        json={
            "guardianId": guardian_ids[0],
            "challenge": body["challenge"],
            "proof": runtime.sign_decision(
                guardian_id=guardian_ids[0],
                request_id=body["requestId"],
                challenge=body["challenge"],
            ),
        },
    )
    reconcile = client.post(
        f"/api/v1/recovery/requests/{body['requestId']}/reconcile", headers=admin
    )

    assert forged.status_code == 404
    assert reconcile.json()["state"] == "PENDING_APPROVALS"
    case = client.get(
        f"/api/v1/recovery/admin/requests/{body['requestId']}", headers=admin
    ).json()["case"]
    assert case["approvalCount"] == 0


def test_timeline_visible_to_owner_and_assigned_guardian_only(api) -> None:
    client, runtime = api
    guardian_ids = _configure(client, runtime)
    body = _start(client, runtime)
    _approve(client, runtime, body, guardian_ids, 1)
    path = f"/api/v1/recovery/requests/{body['requestId']}/timeline"

    owner = client.get(path, headers=_headers(runtime.owner.user_id))
    guardian = client.get(path, headers=_headers(runtime.guardians[1].user_id))
    stranger = client.get(path, headers=_headers("usr_wp28_unrelated_holder"))

    assert owner.status_code == 200 and guardian.status_code == 200
    approved = [i for i in owner.json()["items"] if i["eventType"] == "RECOVERY_APPROVED"]
    assert approved and approved[0]["guardianId"] == guardian_ids[1]
    assert approved[0]["decision"] == "APPROVE"
    assert stranger.status_code == 404
    assert runtime.guardians[1].user_id not in owner.text


def test_new_request_after_cancel_reject_or_expiry_under_same_policy(api) -> None:
    """Regression: a second request reused share version 1 and hit a conflict."""
    client, runtime = api
    guardian_ids = _configure(client, runtime)
    first = _start(client, runtime)
    cancelled = client.post(
        f"/api/v1/recovery/requests/{first['requestId']}/cancel",
        headers=_headers(runtime.owner.user_id),
    )
    assert cancelled.json()["state"] == "CANCELLED"

    second = _start(client, runtime)
    assert second["shareVersion"] == first["shareVersion"] + 1
    assert second["policyVersion"] == first["policyVersion"]
    for index in range(3):
        assert _approve(client, runtime, second, guardian_ids, index).status_code == 200
    runtime.clock.advance(seconds=10)
    done = client.post(
        f"/api/v1/recovery/requests/{second['requestId']}/reconcile",
        headers=_headers(runtime.admin.user_id, "admin"),
    )
    assert done.json()["state"] == "COMPLETED"
