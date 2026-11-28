"""Fail-closed verification for Guardian recovery challenge proofs."""

import base64
import json
import re
from datetime import datetime
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


RECOVERY_PROOF_AUDIENCE = "secure-ssi-platform:guardian-recovery"
_BASE58_BTC_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE64URL = re.compile(r"^[A-Za-z0-9_-]+$")
_ED25519_MULTICODEC = b"\xed\x01"


class GuardianProofError(ValueError):
    """A Guardian proof is malformed, unsupported, stale, or invalid."""


class GuardianDecisionProofVerifier:
    """Verify a short-lived EdDSA JWT bound to one Guardian decision."""

    def verify(
        self,
        proof: str,
        *,
        guardian_did: str,
        verification_method: str,
        guardian_id: str,
        request_id: str,
        session_id: str,
        wallet_id: str,
        decision: str,
        challenge: str,
        policy_hash: str,
        now: datetime,
    ) -> None:
        self._verify(
            proof,
            token_type="guardian-recovery+jwt",
            guardian_did=guardian_did,
            verification_method=verification_method,
            expected_claims={
                "iss": guardian_did,
                "sub": guardian_id,
                "aud": RECOVERY_PROOF_AUDIENCE,
                "requestId": request_id,
                "sessionId": session_id,
                "walletId": wallet_id,
                "decision": decision,
                "challenge": challenge,
                "policyHash": policy_hash,
            },
            now=now,
        )

    def verify_binding(
        self,
        proof: str,
        *,
        guardian_did: str,
        verification_method: str,
        guardian_id: str,
        wallet_id: str,
        challenge: str,
        now: datetime,
    ) -> None:
        """Proves possession of the key behind a DID, for one invitation."""
        self._verify(
            proof,
            token_type="guardian-binding+jwt",
            guardian_did=guardian_did,
            verification_method=verification_method,
            expected_claims={
                "iss": guardian_did,
                "sub": guardian_id,
                "aud": RECOVERY_PROOF_AUDIENCE,
                "walletId": wallet_id,
                "challenge": challenge,
            },
            now=now,
        )

    def _verify(
        self,
        proof: str,
        *,
        token_type: str,
        guardian_did: str,
        verification_method: str,
        expected_claims: dict[str, str],
        now: datetime,
    ) -> None:
        if not isinstance(proof, str) or len(proof) > 4096:
            raise GuardianProofError("Guardian proof is invalid.")
        parts = proof.split(".")
        if len(parts) != 3:
            raise GuardianProofError("Guardian proof is invalid.")
        header_part, payload_part, signature_part = parts
        header = self._json_segment(header_part)
        claims = self._json_segment(payload_part)
        signature = self._decode_segment(signature_part)
        if not isinstance(header, dict) or set(header) != {"alg", "typ", "kid"}:
            raise GuardianProofError("Guardian proof is invalid.")
        if (
            header.get("alg") != "EdDSA"
            or header.get("typ") != token_type
            or header.get("kid") != verification_method
        ):
            raise GuardianProofError("Guardian proof is invalid.")
        if not isinstance(claims, dict):
            raise GuardianProofError("Guardian proof is invalid.")

        if any(claims.get(name) != value for name, value in expected_claims.items()):
            raise GuardianProofError("Guardian proof is invalid.")
        if set(claims) != {*expected_claims, "iat", "exp", "jti"}:
            raise GuardianProofError("Guardian proof is invalid.")

        issued_at = claims.get("iat")
        expires_at = claims.get("exp")
        token_id = claims.get("jti")
        if (
            type(issued_at) is not int
            or type(expires_at) is not int
            or not isinstance(token_id, str)
            or not 16 <= len(token_id) <= 128
        ):
            raise GuardianProofError("Guardian proof is invalid.")
        now_seconds = int(now.timestamp())
        if (
            issued_at > now_seconds + 30
            or expires_at <= now_seconds
            or expires_at <= issued_at
            or expires_at - issued_at > 120
        ):
            raise GuardianProofError("Guardian proof is invalid or expired.")

        public_key = self._did_key_public_key(guardian_did, verification_method)
        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                signature, signing_input
            )
        except (InvalidSignature, ValueError) as error:
            raise GuardianProofError("Guardian proof is invalid.") from error

    @classmethod
    def _did_key_public_key(cls, did: str, verification_method: str) -> bytes:
        if not did.startswith("did:key:z"):
            raise GuardianProofError("Guardian DID method is not supported for signing.")
        multibase = did[len("did:key:"):]
        if verification_method != f"{did}#{multibase}":
            raise GuardianProofError("Guardian verification method is not authorized.")
        decoded = cls._decode_base58(multibase[1:])
        if not decoded.startswith(_ED25519_MULTICODEC):
            raise GuardianProofError("Guardian DID key type is not supported.")
        public_key = decoded[len(_ED25519_MULTICODEC):]
        if len(public_key) != 32:
            raise GuardianProofError("Guardian DID key is invalid.")
        return public_key

    @classmethod
    def _decode_base58(cls, value: str) -> bytes:
        number = 0
        try:
            for character in value:
                number = number * 58 + _BASE58_BTC_ALPHABET.index(character)
        except ValueError as error:
            raise GuardianProofError("Guardian DID encoding is invalid.") from error
        decoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
        leading_zeroes = len(value) - len(value.lstrip("1"))
        return b"\x00" * leading_zeroes + decoded

    @classmethod
    def _json_segment(cls, value: str) -> Any:
        try:
            decoded = cls._decode_segment(value)
            return json.loads(
                decoded.decode("utf-8"),
                object_pairs_hook=cls._reject_duplicate_properties,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise GuardianProofError("Guardian proof is invalid.") from error

    @staticmethod
    def _decode_segment(value: str) -> bytes:
        if not value or _BASE64URL.fullmatch(value) is None:
            raise GuardianProofError("Guardian proof is invalid.")
        try:
            decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        except (ValueError, base64.binascii.Error) as error:
            raise GuardianProofError("Guardian proof is invalid.") from error
        if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
            raise GuardianProofError("Guardian proof is invalid.")
        return decoded

    @staticmethod
    def _reject_duplicate_properties(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON property.")
            result[key] = value
        return result
