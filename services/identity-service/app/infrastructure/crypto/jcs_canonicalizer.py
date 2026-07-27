import copy
import hashlib
from collections.abc import Mapping
from typing import Any

import rfc8785

from app.domain.exceptions import CanonicalizationError


class JcsCanonicalizer:
    """RFC 8785 adapter for the local eddsa-jcs-2022 profile."""

    def canonicalize_document(self, document: Mapping[str, Any]) -> bytes:
        try:
            return rfc8785.dumps(copy.deepcopy(dict(document)))
        except (rfc8785.CanonicalizationError, TypeError, ValueError) as error:
            raise CanonicalizationError(
                "The document cannot be canonicalized with RFC 8785."
            ) from error

    def calculate_digest(self, document: Mapping[str, Any]) -> bytes:
        return hashlib.sha256(self.canonicalize_document(document)).digest()

    def create_signing_input(
        self,
        credential_without_proof: Mapping[str, Any],
        proof_configuration: Mapping[str, Any],
    ) -> bytes:
        unsecured = copy.deepcopy(dict(credential_without_proof))
        unsecured.pop("proof", None)
        proof_options = copy.deepcopy(dict(proof_configuration))
        proof_options.pop("proofValue", None)

        proof_config_hash = self.calculate_digest(proof_options)
        credential_hash = self.calculate_digest(unsecured)
        return proof_config_hash + credential_hash


_DEFAULT_CANONICALIZER = JcsCanonicalizer()


def canonicalize_document(document: Mapping[str, Any]) -> bytes:
    return _DEFAULT_CANONICALIZER.canonicalize_document(document)


def calculate_digest(document: Mapping[str, Any]) -> bytes:
    return _DEFAULT_CANONICALIZER.calculate_digest(document)


def create_signing_input(
    credential_without_proof: Mapping[str, Any],
    proof_configuration: Mapping[str, Any],
) -> bytes:
    return _DEFAULT_CANONICALIZER.create_signing_input(
        credential_without_proof,
        proof_configuration,
    )
