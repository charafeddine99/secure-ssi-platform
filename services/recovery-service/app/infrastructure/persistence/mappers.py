from typing import Any

from app.domain.recovery import (
    Guardian,
    GuardianStatus,
    RecoveryApproval,
    RecoveryAuditEvent,
    RecoveryAuditEventType,
    RecoveryChallenge,
    RecoveryDecision,
    RecoveryFailure,
    RecoveryLease,
    RecoveryNonce,
    RecoveryOperation,
    RecoveryPolicy,
    RecoveryPolicySnapshot,
    RecoveryQuorum,
    RecoveryReason,
    RecoveryRequest,
    RecoveryResult,
    RecoverySecretShareMetadata,
    RecoverySession,
    RecoveryState,
)


def guardian_to_document(value: Guardian) -> dict[str, Any]:
    return {
        "_id": value.guardian_id,
        "guardianId": value.guardian_id,
        "ownerUserId": value.owner_user_id,
        "walletId": value.wallet_id,
        "guardianUserId": value.guardian_user_id,
        "guardianDid": value.guardian_did,
        "displayName": value.display_name,
        "verificationMethod": value.verification_method,
        "status": value.status.value,
        "createdAt": value.created_at,
        "updatedAt": value.updated_at,
        "suspendedAt": value.suspended_at,
        "revokedAt": value.revoked_at,
        "removedAt": value.removed_at,
        "version": value.version,
    }


def guardian_from_document(value: dict[str, Any]) -> Guardian:
    return Guardian(
        guardian_id=value["guardianId"],
        owner_user_id=value["ownerUserId"],
        wallet_id=value["walletId"],
        guardian_user_id=value["guardianUserId"],
        guardian_did=value["guardianDid"],
        display_name=value["displayName"],
        verification_method=value["verificationMethod"],
        status=GuardianStatus(value["status"]),
        created_at=value["createdAt"],
        updated_at=value["updatedAt"],
        suspended_at=value.get("suspendedAt"),
        revoked_at=value.get("revokedAt"),
        removed_at=value.get("removedAt"),
        version=value["version"],
    )


def policy_to_document(value: RecoveryPolicy) -> dict[str, Any]:
    return {
        "_id": value.policy_id,
        "policyId": value.policy_id,
        "walletId": value.wallet_id,
        "ownerUserId": value.owner_user_id,
        "minimumApprovals": value.minimum_approvals,
        "maximumGuardians": value.maximum_guardians,
        "approvalWindowSeconds": value.approval_window_seconds,
        "timeLockSeconds": value.time_lock_seconds,
        "recoveryExpirationSeconds": value.recovery_expiration_seconds,
        "maximumAttempts": value.maximum_attempts,
        "cooldownSeconds": value.cooldown_seconds,
        "allowCancellation": value.allow_cancellation,
        "allowSelfGuardian": value.allow_self_guardian,
        "version": value.version,
        "createdAt": value.created_at,
        "updatedAt": value.updated_at,
    }


def policy_from_document(value: dict[str, Any]) -> RecoveryPolicy:
    return RecoveryPolicy(
        policy_id=value["policyId"],
        wallet_id=value["walletId"],
        owner_user_id=value["ownerUserId"],
        minimum_approvals=value["minimumApprovals"],
        maximum_guardians=value["maximumGuardians"],
        approval_window_seconds=value["approvalWindowSeconds"],
        time_lock_seconds=value["timeLockSeconds"],
        recovery_expiration_seconds=value["recoveryExpirationSeconds"],
        maximum_attempts=value["maximumAttempts"],
        cooldown_seconds=value["cooldownSeconds"],
        allow_cancellation=value["allowCancellation"],
        allow_self_guardian=value.get("allowSelfGuardian", False),
        version=value["version"],
        created_at=value["createdAt"],
        updated_at=value["updatedAt"],
    )


def request_to_document(value: RecoveryRequest) -> dict[str, Any]:
    session = value.session
    return {
        "_id": value.request_id,
        "requestId": value.request_id,
        "ownerUserId": value.owner_user_id,
        "walletId": value.wallet_id,
        "reason": value.reason.value,
        "operation": value.operation.value,
        "policy": {
            "policyId": value.policy.policy_id,
            "policyVersion": value.policy.policy_version,
            "minimumApprovals": value.policy.minimum_approvals,
            "maximumGuardians": value.policy.maximum_guardians,
            "approvalWindowSeconds": value.policy.approval_window_seconds,
            "timeLockSeconds": value.policy.time_lock_seconds,
            "recoveryExpirationSeconds": value.policy.recovery_expiration_seconds,
            "maximumAttempts": value.policy.maximum_attempts,
            "allowCancellation": value.policy.allow_cancellation,
            "guardianIds": list(value.policy.guardian_ids),
            "shareVersion": value.policy.share_version,
            "secretCommitment": value.policy.secret_commitment,
        },
        "challenge": {"value": value.challenge.value, "digest": value.challenge.digest},
        "nonce": {"value": value.nonce.value, "digest": value.nonce.digest},
        "session": {
            "sessionId": session.session_id,
            "state": session.state.value,
            "createdAt": session.created_at,
            "updatedAt": session.updated_at,
            "approvalExpiresAt": session.approval_expires_at,
            "expiresAt": session.expires_at,
            "quorum": {
                "required": session.quorum.required,
                "approvals": session.quorum.approvals,
                "rejections": session.quorum.rejections,
                "reachedAt": session.quorum.reached_at,
            },
            "attemptCount": session.attempt_count,
            "quorumReachedAt": session.quorum_reached_at,
            "timeLockStartedAt": session.time_lock_started_at,
            "executableAfter": session.executable_after,
            "lease": _lease_to_document(session.lease),
            "result": _result_to_document(session.result),
            "failure": _failure_to_document(session.failure),
        },
        "state": session.state.value,
        "approvalExpiresAt": session.approval_expires_at,
        "expiresAt": session.expires_at,
        "executableAfter": session.executable_after,
        "leaseExpiresAt": None if session.lease is None else session.lease.expires_at,
        "createdAt": value.created_at,
        "updatedAt": value.updated_at,
        "version": value.version,
    }


def request_from_document(value: dict[str, Any]) -> RecoveryRequest:
    policy = value["policy"]
    session = value["session"]
    quorum = session["quorum"]
    return RecoveryRequest(
        request_id=value["requestId"],
        owner_user_id=value["ownerUserId"],
        wallet_id=value["walletId"],
        reason=RecoveryReason(value["reason"]),
        operation=RecoveryOperation(value["operation"]),
        policy=RecoveryPolicySnapshot(
            policy_id=policy["policyId"],
            policy_version=policy["policyVersion"],
            minimum_approvals=policy["minimumApprovals"],
            maximum_guardians=policy["maximumGuardians"],
            approval_window_seconds=policy["approvalWindowSeconds"],
            time_lock_seconds=policy["timeLockSeconds"],
            recovery_expiration_seconds=policy["recoveryExpirationSeconds"],
            maximum_attempts=policy["maximumAttempts"],
            allow_cancellation=policy["allowCancellation"],
            guardian_ids=tuple(policy["guardianIds"]),
            share_version=policy["shareVersion"],
            secret_commitment=policy["secretCommitment"],
        ),
        challenge=RecoveryChallenge(**value["challenge"]),
        nonce=RecoveryNonce(**value["nonce"]),
        session=RecoverySession(
            session_id=session["sessionId"],
            state=RecoveryState(session["state"]),
            created_at=session["createdAt"],
            updated_at=session["updatedAt"],
            approval_expires_at=session["approvalExpiresAt"],
            expires_at=session["expiresAt"],
            quorum=RecoveryQuorum(
                required=quorum["required"],
                approvals=quorum["approvals"],
                rejections=quorum["rejections"],
                reached_at=quorum.get("reachedAt"),
            ),
            attempt_count=session.get("attemptCount", 0),
            quorum_reached_at=session.get("quorumReachedAt"),
            time_lock_started_at=session.get("timeLockStartedAt"),
            executable_after=session.get("executableAfter"),
            lease=_lease_from_document(session.get("lease")),
            result=_result_from_document(session.get("result")),
            failure=_failure_from_document(session.get("failure")),
        ),
        created_at=value["createdAt"],
        updated_at=value["updatedAt"],
        version=value["version"],
    )


def approval_to_document(value: RecoveryApproval) -> dict[str, Any]:
    return {
        "_id": value.approval_id,
        "approvalId": value.approval_id,
        "requestId": value.request_id,
        "sessionId": value.session_id,
        "guardianId": value.guardian_id,
        "guardianUserId": value.guardian_user_id,
        "walletId": value.wallet_id,
        "decision": value.decision.value,
        "challengeDigest": value.challenge_digest,
        "proofDigest": value.proof_digest,
        "decidedAt": value.decided_at,
        "createdAt": value.created_at,
        "version": value.version,
    }


def approval_from_document(value: dict[str, Any]) -> RecoveryApproval:
    return RecoveryApproval(
        approval_id=value["approvalId"],
        request_id=value["requestId"],
        session_id=value["sessionId"],
        guardian_id=value["guardianId"],
        guardian_user_id=value["guardianUserId"],
        wallet_id=value["walletId"],
        decision=RecoveryDecision(value["decision"]),
        challenge_digest=value["challengeDigest"],
        proof_digest=value.get("proofDigest"),
        decided_at=value["decidedAt"],
        created_at=value["createdAt"],
        version=value["version"],
    )


def share_to_document(value: RecoverySecretShareMetadata) -> dict[str, Any]:
    return {
        "_id": value.share_id,
        "shareId": value.share_id,
        "recoveryRequestId": value.recovery_request_id,
        "policyId": value.policy_id,
        "policyVersion": value.policy_version,
        "shareVersion": value.share_version,
        "guardianId": value.guardian_id,
        "shareIndex": value.share_index,
        "threshold": value.threshold,
        "shareCount": value.share_count,
        "envelopeVersion": value.envelope_version,
        "integrityDigest": value.integrity_digest,
        "encryptedEnvelope": value.encrypted_envelope,
        "createdAt": value.created_at,
    }


def share_from_document(value: dict[str, Any]) -> RecoverySecretShareMetadata:
    return RecoverySecretShareMetadata(
        share_id=value["shareId"],
        recovery_request_id=value["recoveryRequestId"],
        policy_id=value["policyId"],
        policy_version=value["policyVersion"],
        share_version=value["shareVersion"],
        guardian_id=value["guardianId"],
        share_index=value["shareIndex"],
        threshold=value["threshold"],
        share_count=value["shareCount"],
        envelope_version=value["envelopeVersion"],
        integrity_digest=value["integrityDigest"],
        encrypted_envelope=value["encryptedEnvelope"],
        created_at=value["createdAt"],
    )


def audit_to_document(value: RecoveryAuditEvent) -> dict[str, Any]:
    return {
        "_id": value.event_id,
        "eventId": value.event_id,
        "eventType": value.event_type.value,
        "aggregateId": value.aggregate_id,
        "actorId": value.actor_id,
        "occurredAt": value.occurred_at,
        "metadata": dict(value.metadata),
    }


def audit_from_document(value: dict[str, Any]) -> RecoveryAuditEvent:
    return RecoveryAuditEvent(
        event_id=value["eventId"],
        event_type=RecoveryAuditEventType(value["eventType"]),
        aggregate_id=value["aggregateId"],
        actor_id=value["actorId"],
        occurred_at=value["occurredAt"],
        metadata=value.get("metadata", {}),
    )


def _lease_to_document(value: RecoveryLease | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "workerId": value.worker_id,
        "acquiredAt": value.acquired_at,
        "expiresAt": value.expires_at,
        "attempt": value.attempt,
    }


def _lease_from_document(value: dict[str, Any] | None) -> RecoveryLease | None:
    if value is None:
        return None
    return RecoveryLease(
        worker_id=value["workerId"],
        acquired_at=value["acquiredAt"],
        expires_at=value["expiresAt"],
        attempt=value["attempt"],
    )


def _result_to_document(value: RecoveryResult | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "predecessorKeyId": value.predecessor_key_id,
        "successorKeyId": value.successor_key_id,
        "predecessorDid": value.predecessor_did,
        "successorDid": value.successor_did,
        "provider": value.provider,
        "completedAt": value.completed_at,
        "keyRotationDurationMs": value.key_rotation_duration_ms,
    }


def _result_from_document(value: dict[str, Any] | None) -> RecoveryResult | None:
    if value is None:
        return None
    return RecoveryResult(
        predecessor_key_id=value["predecessorKeyId"],
        successor_key_id=value["successorKeyId"],
        predecessor_did=value["predecessorDid"],
        successor_did=value["successorDid"],
        provider=value["provider"],
        completed_at=value["completedAt"],
        key_rotation_duration_ms=value["keyRotationDurationMs"],
    )


def _failure_to_document(value: RecoveryFailure | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "code": value.code,
        "retryable": value.retryable,
        "occurredAt": value.occurred_at,
        "attempt": value.attempt,
    }


def _failure_from_document(value: dict[str, Any] | None) -> RecoveryFailure | None:
    if value is None:
        return None
    return RecoveryFailure(
        code=value["code"],
        retryable=value["retryable"],
        occurred_at=value["occurredAt"],
        attempt=value["attempt"],
    )
