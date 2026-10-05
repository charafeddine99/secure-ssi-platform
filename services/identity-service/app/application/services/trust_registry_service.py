from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
import uuid

from app.application.ports.trust_registry import TrustRegistryRepository
from app.domain.persistence import AuditEvent, AuditEventType, DuplicateEntityError
from app.domain.trust_registry import (
    TrustEvaluationResult,
    TrustRecord,
    TrustRole,
    TrustStatus,
)
from app.infrastructure.persistence.mappers import new_object_id
from app.infrastructure.persistence.repositories import MongoAuditEventRepository


class TrustRegistryService:
    def __init__(
        self,
        repository: TrustRegistryRepository,
        audit_repository: MongoAuditEventRepository | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit = audit_repository
        self._clock = clock or (lambda: datetime.now(UTC))

    def register_trusted_issuer(
        self,
        *,
        actor_id: str,
        issuer_did: str,
        organization_name: str,
        roles: tuple[TrustRole, ...] = (TrustRole.ISSUER,),
        permitted_credential_types: tuple[str, ...] = ("VerifiableCredential",),
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        trust_source: str = "LOCAL_TRUST_REGISTRY",
        trust_anchor: str | None = None,
        audit_metadata: dict[str, Any] | None = None,
    ) -> TrustRecord:
        now = self._clock().astimezone(UTC)
        clean_did = issuer_did.strip()
        if not clean_did or not clean_did.startswith("did:"):
            raise ValueError(f"Malformed or invalid issuer DID: '{issuer_did}'")
        clean_org = organization_name.strip()
        if not clean_org:
            raise ValueError("Organization name cannot be empty.")

        existing = self._repository.get_by_issuer_did(clean_did)
        if existing is not None:
            raise DuplicateEntityError(
                f"Trust record for issuer '{clean_did}' already exists."
            )

        v_from = valid_from.astimezone(UTC) if valid_from else now
        v_until = valid_until.astimezone(UTC) if valid_until else (now + timedelta(days=365))

        record = TrustRecord(
            id=new_object_id(),
            issuer_did=clean_did,
            organization_name=clean_org,
            trust_status=TrustStatus.ACTIVE,
            roles=roles,
            permitted_credential_types=permitted_credential_types,
            valid_from=v_from,
            valid_until=v_until,
            trust_source=trust_source,
            trust_anchor=trust_anchor,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
            audit_metadata=audit_metadata or {},
            version=1,
        )

        persisted = self._repository.add(record)

        if self._audit is not None:
            self._audit.append(
                AuditEvent(
                    id=new_object_id(),
                    event_type=AuditEventType.TRUST_RECORD_CREATED,
                    subject_id=clean_did,
                    actor_id=actor_id,
                    correlation_id=f"trust:{clean_did}",
                    metadata={
                        "record_id": persisted.id,
                        "issuer_did": clean_did,
                        "organization_name": clean_org,
                        "status": persisted.trust_status.value,
                        "trust_source": trust_source,
                    },
                    created_at=now,
                    updated_at=now,
                    version=1,
                )
            )

        return persisted

    def update_trust_record(
        self,
        *,
        actor_id: str,
        record_id: str,
        organization_name: str | None = None,
        trust_status: TrustStatus | None = None,
        roles: tuple[TrustRole, ...] | None = None,
        permitted_credential_types: tuple[str, ...] | None = None,
        valid_until: datetime | None = None,
        audit_metadata: dict[str, Any] | None = None,
    ) -> TrustRecord:
        record = self._repository.get_by_id(record_id)
        if record is None:
            raise ValueError(f"Trust record '{record_id}' not found.")

        now = self._clock().astimezone(UTC)
        meta = dict(record.audit_metadata)
        if audit_metadata:
            meta.update(audit_metadata)

        updated_record = TrustRecord(
            id=record.id,
            issuer_did=record.issuer_did,
            organization_name=organization_name if organization_name is not None else record.organization_name,
            trust_status=trust_status if trust_status is not None else record.trust_status,
            roles=roles if roles is not None else record.roles,
            permitted_credential_types=permitted_credential_types if permitted_credential_types is not None else record.permitted_credential_types,
            valid_from=record.valid_from,
            valid_until=valid_until if valid_until is not None else record.valid_until,
            trust_source=record.trust_source,
            trust_anchor=record.trust_anchor,
            created_at=record.created_at,
            updated_at=now,
            created_by=record.created_by,
            audit_metadata=meta,
            version=record.version,
        )

        persisted = self._repository.update(updated_record, expected_version=record.version)

        if self._audit is not None:
            self._audit.append(
                AuditEvent(
                    id=new_object_id(),
                    event_type=AuditEventType.TRUST_RECORD_UPDATED,
                    subject_id=persisted.issuer_did,
                    actor_id=actor_id,
                    correlation_id=f"trust:{persisted.issuer_did}",
                    metadata={
                        "record_id": persisted.id,
                        "issuer_did": persisted.issuer_did,
                        "status": persisted.trust_status.value,
                    },
                    created_at=now,
                    updated_at=now,
                    version=1,
                )
            )

        return persisted

    def suspend_issuer(
        self,
        *,
        actor_id: str,
        issuer_did: str,
        reason: str,
    ) -> TrustRecord:
        record = self._repository.get_by_issuer_did(issuer_did)
        if record is None:
            raise ValueError(f"Trust record for '{issuer_did}' not found.")

        now = self._clock().astimezone(UTC)
        meta = dict(record.audit_metadata)
        meta["suspension_reason"] = reason

        updated = TrustRecord(
            id=record.id,
            issuer_did=record.issuer_did,
            organization_name=record.organization_name,
            trust_status=TrustStatus.SUSPENDED,
            roles=record.roles,
            permitted_credential_types=record.permitted_credential_types,
            valid_from=record.valid_from,
            valid_until=record.valid_until,
            trust_source=record.trust_source,
            trust_anchor=record.trust_anchor,
            created_at=record.created_at,
            updated_at=now,
            created_by=record.created_by,
            audit_metadata=meta,
            version=record.version,
        )

        persisted = self._repository.update(updated, expected_version=record.version)

        if self._audit is not None:
            self._audit.append(
                AuditEvent(
                    id=new_object_id(),
                    event_type=AuditEventType.TRUST_RECORD_DEACTIVATED,
                    subject_id=issuer_did,
                    actor_id=actor_id,
                    correlation_id=f"trust:{issuer_did}",
                    metadata={
                        "record_id": persisted.id,
                        "reason": reason,
                        "status": TrustStatus.SUSPENDED.value,
                    },
                    created_at=now,
                    updated_at=now,
                    version=1,
                )
            )

        return persisted

    def revoke_issuer(
        self,
        *,
        actor_id: str,
        issuer_did: str,
        reason: str,
    ) -> TrustRecord:
        record = self._repository.get_by_issuer_did(issuer_did)
        if record is None:
            raise ValueError(f"Trust record for '{issuer_did}' not found.")

        now = self._clock().astimezone(UTC)
        meta = dict(record.audit_metadata)
        meta["revocation_reason"] = reason

        updated = TrustRecord(
            id=record.id,
            issuer_did=record.issuer_did,
            organization_name=record.organization_name,
            trust_status=TrustStatus.REVOKED,
            roles=record.roles,
            permitted_credential_types=record.permitted_credential_types,
            valid_from=record.valid_from,
            valid_until=record.valid_until,
            trust_source=record.trust_source,
            trust_anchor=record.trust_anchor,
            created_at=record.created_at,
            updated_at=now,
            created_by=record.created_by,
            audit_metadata=meta,
            version=record.version,
        )

        persisted = self._repository.update(updated, expected_version=record.version)

        if self._audit is not None:
            self._audit.append(
                AuditEvent(
                    id=new_object_id(),
                    event_type=AuditEventType.TRUST_RECORD_REVOKED,
                    subject_id=issuer_did,
                    actor_id=actor_id,
                    correlation_id=f"trust:{issuer_did}",
                    metadata={
                        "record_id": persisted.id,
                        "reason": reason,
                        "status": TrustStatus.REVOKED.value,
                    },
                    created_at=now,
                    updated_at=now,
                    version=1,
                )
            )

        return persisted

    def get_trust_record(self, issuer_did: str) -> TrustRecord | None:
        try:
            return self._repository.get_by_issuer_did(issuer_did)
        except Exception:
            return None

    def get_trust_record_by_id(self, record_id: str) -> TrustRecord | None:
        try:
            return self._repository.get_by_id(record_id)
        except Exception:
            return None

    def list_trust_records(
        self,
        status: TrustStatus | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[TrustRecord]:
        try:
            return self._repository.list_all(status=status, limit=limit, skip=skip)
        except Exception:
            return []

    def evaluate_issuer_trust(
        self,
        *,
        issuer_did: str,
        credential_types: list[str] | tuple[str, ...] | None = None,
        at_time: datetime | None = None,
    ) -> TrustEvaluationResult:
        """
        Authoritative Trust Registry Evaluation.
        Fail-closed: Returns is_trusted = False for any unknown, inactive, expired,
        out-of-scope, malformed, or repository failure state.
        """
        clean_did = (issuer_did or "").strip()
        if not clean_did or not clean_did.startswith("did:"):
            return TrustEvaluationResult(
                is_trusted=False,
                issuer_did=clean_did,
                status=None,
                reason="MALFORMED_ISSUER_DID",
            )

        now = (at_time or self._clock()).astimezone(UTC)

        try:
            record = self._repository.get_by_issuer_did(clean_did)
        except Exception:
            return TrustEvaluationResult(
                is_trusted=False,
                issuer_did=clean_did,
                status=None,
                reason="TRUST_REGISTRY_UNAVAILABLE",
            )

        if record is None:
            return TrustEvaluationResult(
                is_trusted=False,
                issuer_did=clean_did,
                status=None,
                reason="ISSUER_NOT_IN_TRUST_REGISTRY",
            )

        # Status check
        if record.trust_status == TrustStatus.SUSPENDED:
            return TrustEvaluationResult(
                is_trusted=False,
                issuer_did=clean_did,
                status=record.trust_status,
                reason="ISSUER_TRUST_SUSPENDED",
                trust_record_id=record.id,
                trust_source=record.trust_source,
            )
        if record.trust_status == TrustStatus.REVOKED:
            return TrustEvaluationResult(
                is_trusted=False,
                issuer_did=clean_did,
                status=record.trust_status,
                reason="ISSUER_TRUST_REVOKED",
                trust_record_id=record.id,
                trust_source=record.trust_source,
            )

        # Validity window checks
        v_from = record.valid_from.astimezone(UTC) if record.valid_from.tzinfo else record.valid_from.replace(tzinfo=UTC)
        if now < v_from:
            return TrustEvaluationResult(
                is_trusted=False,
                issuer_did=clean_did,
                status=record.trust_status,
                reason="ISSUER_TRUST_NOT_YET_VALID",
                trust_record_id=record.id,
                trust_source=record.trust_source,
            )

        if record.valid_until is not None:
            v_until = record.valid_until.astimezone(UTC) if record.valid_until.tzinfo else record.valid_until.replace(tzinfo=UTC)
            if now > v_until:
                return TrustEvaluationResult(
                    is_trusted=False,
                    issuer_did=clean_did,
                    status=record.trust_status,
                    reason="ISSUER_TRUST_EXPIRED",
                    trust_record_id=record.id,
                    trust_source=record.trust_source,
                )

        # Scope check
        types_to_check = tuple(credential_types) if credential_types else ()
        if types_to_check and not record.allows_any_credential_type(types_to_check):
            return TrustEvaluationResult(
                is_trusted=False,
                issuer_did=clean_did,
                status=record.trust_status,
                reason="ISSUER_TRUST_OUT_OF_SCOPE",
                trust_record_id=record.id,
                trust_source=record.trust_source,
            )

        # Matched types
        matched = tuple(
            t for t in types_to_check if record.allows_credential_type(t)
        ) if types_to_check else record.permitted_credential_types

        return TrustEvaluationResult(
            is_trusted=True,
            issuer_did=clean_did,
            status=record.trust_status,
            reason="ISSUER_TRUST_VALID",
            trust_record_id=record.id,
            trust_source=record.trust_source,
            matched_types=matched,
        )

    def seed_default_demo_issuers(self) -> None:
        """
        Idempotently seeds synthetic demo issuers for academic demonstration.
        Does NOT claim government or real-world accreditation.
        """
        now = self._clock().astimezone(UTC)
        seeds = [
            (
                "did:web:issuer.example",
                "Demo Technical University",
                (TrustRole.ISSUER,),
                (
                    "VerifiableCredential",
                    "UniversityAffiliation",
                    "UniversityAffiliationCredential",
                    "EducationalID",
                    "DegreeCredential",
                    "TranscriptCredential",
                ),
                "DEMO_ACCREDITATION_BOARD",
                "urn:trust-anchor:demo-academic-consortium",
            ),
            (
                "did:web:demo-municipality.example",
                "Demo Metropolitan Municipality",
                (TrustRole.ISSUER,),
                (
                    "VerifiableCredential",
                    "ProofOfResidency",
                    "CitizenID",
                ),
                "DEMO_MUNICIPAL_REGISTRY",
                "urn:trust-anchor:demo-public-sector",
            ),
            (
                "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP",
                "Demo Synthetic Ed25519 Issuer",
                (TrustRole.ISSUER,),
                (
                    "VerifiableCredential",
                    "SyntheticAffiliation",
                ),
                "LOCAL_TEST_REGISTRY",
                None,
            ),
        ]

        for did, name, roles, types, source, anchor in seeds:
            try:
                existing = self._repository.get_by_issuer_did(did)
                if existing is None:
                    self.register_trusted_issuer(
                        actor_id="system@platform.local",
                        issuer_did=did,
                        organization_name=name,
                        roles=roles,
                        permitted_credential_types=types,
                        valid_from=now - timedelta(days=30),
                        valid_until=now + timedelta(days=365 * 5),
                        trust_source=source,
                        trust_anchor=anchor,
                        audit_metadata={"seeded": True, "environment": "DEMO_LAB"},
                    )
            except Exception:
                pass
