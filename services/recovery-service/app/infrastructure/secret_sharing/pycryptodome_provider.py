import base64
import json
from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
from secrets import token_bytes, token_urlsafe

from Crypto.Hash import HMAC, SHA256
from Crypto.Protocol.SecretSharing import Shamir
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.application.ports.secret_sharing import (
    SecretSharingContext,
    SplitSecretResult,
)
from app.domain.recovery import RecoverySecretShareMetadata, SecretShareError


class PyCryptodomeSecretSharingProvider:
    """Development Shamir adapter with authenticated encrypted envelopes."""

    def __init__(self, master_key: bytes) -> None:
        if len(master_key) != 32:
            raise SecretShareError("Secret-share envelope key must be 32 bytes.")
        self._master_key = master_key

    def validate_threshold(self, *, threshold: int, share_count: int) -> None:
        if not 1 <= threshold <= share_count <= 32:
            raise SecretShareError("Secret-share threshold is invalid.")

    def split(
        self,
        secret: bytes,
        *,
        threshold: int,
        guardian_ids: tuple[str, ...],
        context: SecretSharingContext,
        created_at: datetime,
    ) -> SplitSecretResult:
        self.validate_threshold(threshold=threshold, share_count=len(guardian_ids))
        if len(secret) != 16:
            raise SecretShareError("The recovery authorization secret must be 16 bytes.")
        if len(set(guardian_ids)) != len(guardian_ids):
            raise SecretShareError("Guardian share assignments are duplicated.")
        commitment = self._commit(secret, context)
        raw_shares = Shamir.split(threshold, len(guardian_ids), secret)
        envelopes = tuple(
            self._seal(
                guardian_id=guardian_id,
                share_index=index,
                raw_share=raw_share,
                threshold=threshold,
                share_count=len(guardian_ids),
                context=context,
                created_at=created_at,
            )
            for guardian_id, (index, raw_share) in zip(guardian_ids, raw_shares)
        )
        return SplitSecretResult(commitment=commitment, shares=envelopes)

    def validate_share(
        self,
        share: RecoverySecretShareMetadata,
        *,
        context: SecretSharingContext,
    ) -> None:
        self._open(share, context=context)

    def combine(
        self,
        shares: tuple[RecoverySecretShareMetadata, ...],
        *,
        threshold: int,
        context: SecretSharingContext,
        expected_commitment: str,
    ) -> bytes:
        self.validate_threshold(threshold=threshold, share_count=len(shares))
        if len(shares) < threshold:
            raise SecretShareError("Insufficient recovery shares.")
        if len({share.share_id for share in shares}) != len(shares):
            raise SecretShareError("Duplicate recovery share detected.")
        if len({share.guardian_id for share in shares}) != len(shares):
            raise SecretShareError("A Guardian cannot contribute twice.")
        if len({share.share_index for share in shares}) != len(shares):
            raise SecretShareError("Duplicate recovery share index detected.")
        opened = sorted(
            (
                share.share_index,
                self._open(share, context=context),
            )
            for share in shares
        )
        secret = Shamir.combine(opened[:threshold])
        if not compare_digest(self._commit(secret, context), expected_commitment):
            raise SecretShareError("Recovery share commitment does not match.")
        return secret

    def _seal(
        self,
        *,
        guardian_id: str,
        share_index: int,
        raw_share: bytes,
        threshold: int,
        share_count: int,
        context: SecretSharingContext,
        created_at: datetime,
    ) -> RecoverySecretShareMetadata:
        share_id = f"share_{token_urlsafe(18)}"
        metadata = {
            "shareId": share_id,
            "recoveryRequestId": context.recovery_request_id,
            "policyId": context.policy_id,
            "policyVersion": context.policy_version,
            "shareVersion": context.share_version,
            "guardianId": guardian_id,
            "shareIndex": share_index,
            "threshold": threshold,
            "shareCount": share_count,
            "envelopeVersion": 1,
        }
        aad = _canonical(metadata)
        encryption_key, integrity_key = self._keys(context)
        integrity = HMAC.new(integrity_key, aad + raw_share, digestmod=SHA256).digest()
        plaintext = raw_share + integrity
        nonce = token_bytes(12)
        ciphertext = AESGCM(encryption_key).encrypt(nonce, plaintext, aad)
        return RecoverySecretShareMetadata(
            share_id=share_id,
            recovery_request_id=context.recovery_request_id,
            policy_id=context.policy_id,
            policy_version=context.policy_version,
            share_version=context.share_version,
            guardian_id=guardian_id,
            share_index=share_index,
            threshold=threshold,
            share_count=share_count,
            envelope_version=1,
            integrity_digest=sha256(integrity).hexdigest(),
            encrypted_envelope=_b64(nonce + ciphertext),
            created_at=created_at,
        )

    def _open(
        self,
        share: RecoverySecretShareMetadata,
        *,
        context: SecretSharingContext,
    ) -> bytes:
        if (
            share.recovery_request_id != context.recovery_request_id
            or share.policy_id != context.policy_id
            or share.policy_version != context.policy_version
            or share.share_version != context.share_version
        ):
            raise SecretShareError("Recovery share belongs to another policy version.")
        metadata = {
            "shareId": share.share_id,
            "recoveryRequestId": share.recovery_request_id,
            "policyId": share.policy_id,
            "policyVersion": share.policy_version,
            "shareVersion": share.share_version,
            "guardianId": share.guardian_id,
            "shareIndex": share.share_index,
            "threshold": share.threshold,
            "shareCount": share.share_count,
            "envelopeVersion": share.envelope_version,
        }
        aad = _canonical(metadata)
        try:
            envelope = _unb64(share.encrypted_envelope)
            nonce, ciphertext = envelope[:12], envelope[12:]
            if len(nonce) != 12 or len(ciphertext) < 48:
                raise SecretShareError("Recovery share envelope is malformed.")
            encryption_key, integrity_key = self._keys(context)
            plaintext = AESGCM(encryption_key).decrypt(nonce, ciphertext, aad)
        except (InvalidTag, ValueError) as error:
            raise SecretShareError("Recovery share envelope authentication failed.") from error
        raw_share, integrity = plaintext[:16], plaintext[16:]
        if len(raw_share) != 16 or len(integrity) != 32:
            raise SecretShareError("Recovery share plaintext is malformed.")
        expected = HMAC.new(integrity_key, aad + raw_share, digestmod=SHA256).digest()
        if not compare_digest(integrity, expected) or not compare_digest(
            sha256(integrity).hexdigest(), share.integrity_digest
        ):
            raise SecretShareError("Recovery share integrity check failed.")
        return raw_share

    def _commit(self, secret: bytes, context: SecretSharingContext) -> str:
        _, integrity_key = self._keys(context)
        binding = _canonical(
            {
                "policyId": context.policy_id,
                "recoveryRequestId": context.recovery_request_id,
                "policyVersion": context.policy_version,
                "shareVersion": context.share_version,
                "purpose": "recovery-authorization",
            }
        )
        return HMAC.new(integrity_key, binding + secret, digestmod=SHA256).hexdigest()

    def _keys(self, context: SecretSharingContext) -> tuple[bytes, bytes]:
        salt = sha256(context.policy_id.encode()).digest()
        material = HKDF(
            algorithm=hashes.SHA256(),
            length=64,
            salt=salt,
            info=(
                f"secure-ssi-recovery-envelope:{context.policy_version}:"
                f"{context.share_version}"
            ).encode(),
        ).derive(self._master_key)
        return material[:32], material[32:]

    def __repr__(self) -> str:
        return "PyCryptodomeSecretSharingProvider(master_key=<redacted>)"


def _canonical(value: dict[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
