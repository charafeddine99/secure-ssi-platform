from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


class DcqlError(Exception):
    """Base exception for DCQL query parsing and evaluation."""


class MalformedDcqlQueryError(DcqlError):
    """Raised when a DCQL query does not conform to the specification."""


class UnsupportedDcqlFeatureError(DcqlError):
    """Raised when a DCQL query uses features outside the project profile."""


@dataclass(frozen=True)
class DcqlClaimQuery:
    """
    Defines an individual claim to be selected from a credential.
    Corresponds to an element in the 'claims' array of a DCQL credential query.
    """
    id: str
    path: tuple[str, ...]
    values: tuple[Any, ...] | None = None

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.id, str):
            raise MalformedDcqlQueryError("Claim query 'id' must be a non-empty string.")
        if not self.path or not isinstance(self.path, tuple):
            raise MalformedDcqlQueryError(f"Claim query '{self.id}' path must be a non-empty sequence of path keys.")
        for segment in self.path:
            if not isinstance(segment, str) or not segment.strip():
                raise MalformedDcqlQueryError(f"Claim query '{self.id}' contains an invalid path segment: {segment!r}")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "path": list(self.path),
        }
        if self.values is not None:
            result["values"] = list(self.values)
        return result


@dataclass(frozen=True)
class DcqlCredentialQuery:
    """
    Specifies a requested verifiable credential and its required claims.
    """
    id: str
    format: str = "w3c_vc"
    type_values: tuple[str, ...] = field(default_factory=tuple)
    claims: tuple[DcqlClaimQuery, ...] = field(default_factory=tuple)
    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.id, str):
            raise MalformedDcqlQueryError("Credential query 'id' must be a non-empty string.")
        if not self.format or not isinstance(self.format, str):
            raise MalformedDcqlQueryError(f"Credential query '{self.id}' format must be specified.")
        # Ensure claim IDs within this query are unique
        claim_ids: set[str] = set()
        for claim in self.claims:
            if claim.id in claim_ids:
                raise MalformedDcqlQueryError(
                    f"Duplicate claim query id '{claim.id}' in credential query '{self.id}'."
                )
            claim_ids.add(claim.id)

    def to_dict(self) -> dict[str, Any]:
        meta_dict = dict(self.meta)
        if self.type_values and "type_values" not in meta_dict:
            meta_dict["type_values"] = list(self.type_values)
        return {
            "id": self.id,
            "format": self.format,
            "meta": meta_dict,
            "claims": [c.to_dict() for c in self.claims],
        }


@dataclass(frozen=True)
class DcqlCredentialSet:
    """
    Logical grouping of credential queries with options (alternatives/combinations).
    """
    options: tuple[tuple[str, ...], ...]
    purpose: str | None = None
    required: bool = True

    def __post_init__(self) -> None:
        if not self.options or not isinstance(self.options, tuple):
            raise MalformedDcqlQueryError("Credential set 'options' must be a non-empty sequence of option tuples.")
        for opt in self.options:
            if not opt or not isinstance(opt, tuple):
                raise MalformedDcqlQueryError("Each credential set option must be a non-empty sequence of query IDs.")
            for q_id in opt:
                if not isinstance(q_id, str) or not q_id.strip():
                    raise MalformedDcqlQueryError("Credential set option item must be a valid query ID string.")

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "options": [list(opt) for opt in self.options],
            "required": self.required,
        }
        if self.purpose:
            res["purpose"] = self.purpose
        return res


@dataclass(frozen=True)
class DcqlQuery:
    """
    Authoritative DCQL Query model conforming to OpenID for Verifiable Presentations 1.0 Final.
    """
    credentials: tuple[DcqlCredentialQuery, ...]
    credential_sets: tuple[DcqlCredentialSet, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.credentials or not isinstance(self.credentials, tuple):
            raise MalformedDcqlQueryError("DCQL query must contain at least one credential query in 'credentials'.")
        
        # Verify unique credential query IDs
        cred_ids: set[str] = set()
        for cred in self.credentials:
            if cred.id in cred_ids:
                raise MalformedDcqlQueryError(f"Duplicate credential query id '{cred.id}' in DCQL query.")
            cred_ids.add(cred.id)

        # Verify that all query IDs referenced in credential_sets exist
        for cset in self.credential_sets:
            for opt in cset.options:
                for q_id in opt:
                    if q_id not in cred_ids:
                        raise MalformedDcqlQueryError(
                            f"Credential set references unknown credential query id '{q_id}'."
                        )

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "credentials": [c.to_dict() for c in self.credentials],
        }
        if self.credential_sets:
            res["credential_sets"] = [cs.to_dict() for cs in self.credential_sets]
        return res

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DcqlQuery:
        """
        Parses a raw dictionary into a typed DcqlQuery with strict validation.
        """
        if not isinstance(data, Mapping):
            raise MalformedDcqlQueryError("DCQL query must be a JSON object mapping.")

        raw_credentials = data.get("credentials")
        if not isinstance(raw_credentials, Sequence) or not raw_credentials:
            raise MalformedDcqlQueryError("DCQL query must contain a non-empty 'credentials' array.")

        parsed_creds: list[DcqlCredentialQuery] = []
        for raw_c in raw_credentials:
            if not isinstance(raw_c, Mapping):
                raise MalformedDcqlQueryError("Each credential entry in 'credentials' must be an object.")
            q_id = str(raw_c.get("id", "")).strip()
            if not q_id:
                raise MalformedDcqlQueryError("Credential query must have a non-empty 'id'.")
            fmt = str(raw_c.get("format", "w3c_vc")).strip()
            
            raw_meta = raw_c.get("meta")
            meta_dict = dict(raw_meta) if isinstance(raw_meta, Mapping) else {}
            type_vals: list[str] = []
            if "type_values" in meta_dict and isinstance(meta_dict["type_values"], Sequence):
                type_vals = [str(t).strip() for t in meta_dict["type_values"] if str(t).strip()]
            elif "type_value" in meta_dict:
                type_vals = [str(meta_dict["type_value"]).strip()]
            elif "vct_values" in meta_dict and isinstance(meta_dict["vct_values"], Sequence):
                type_vals = [str(t).strip() for t in meta_dict["vct_values"] if str(t).strip()]

            raw_claims = raw_c.get("claims", [])
            if not isinstance(raw_claims, Sequence):
                raise MalformedDcqlQueryError(f"Claims in query '{q_id}' must be an array.")

            parsed_claims: list[DcqlClaimQuery] = []
            for raw_cl in raw_claims:
                if not isinstance(raw_cl, Mapping):
                    raise MalformedDcqlQueryError(f"Claim entry in query '{q_id}' must be an object.")
                c_id = str(raw_cl.get("id", "")).strip()
                if not c_id:
                    raise MalformedDcqlQueryError(f"Claim entry in query '{q_id}' must have an 'id'.")
                raw_path = raw_cl.get("path")
                if not isinstance(raw_path, Sequence) or not raw_path:
                    raise MalformedDcqlQueryError(f"Claim '{c_id}' in query '{q_id}' must have a non-empty 'path'.")
                path_tuple = tuple(str(p).strip() for p in raw_path if str(p).strip())
                if not path_tuple:
                    raise MalformedDcqlQueryError(f"Claim '{c_id}' in query '{q_id}' has an invalid empty path.")

                raw_values = raw_cl.get("values")
                values_tuple = tuple(raw_values) if isinstance(raw_values, Sequence) else None

                parsed_claims.append(
                    DcqlClaimQuery(
                        id=c_id,
                        path=path_tuple,
                        values=values_tuple,
                    )
                )

            parsed_creds.append(
                DcqlCredentialQuery(
                    id=q_id,
                    format=fmt,
                    type_values=tuple(type_vals),
                    claims=tuple(parsed_claims),
                    meta=meta_dict,
                )
            )

        # Parse credential_sets if present
        raw_sets = data.get("credential_sets", [])
        parsed_sets: list[DcqlCredentialSet] = []
        if isinstance(raw_sets, Sequence):
            for raw_s in raw_sets:
                if not isinstance(raw_s, Mapping):
                    raise MalformedDcqlQueryError("Each entry in 'credential_sets' must be an object.")
                raw_options = raw_s.get("options")
                if not isinstance(raw_options, Sequence) or not raw_options:
                    raise MalformedDcqlQueryError("Credential set must contain a non-empty 'options' array.")
                
                options_list: list[tuple[str, ...]] = []
                for opt in raw_options:
                    if not isinstance(opt, Sequence) or not opt:
                        raise MalformedDcqlQueryError("Credential set option must be a non-empty array of query IDs.")
                    options_list.append(tuple(str(item).strip() for item in opt if str(item).strip()))

                parsed_sets.append(
                    DcqlCredentialSet(
                        options=tuple(options_list),
                        purpose=raw_s.get("purpose"),
                        required=bool(raw_s.get("required", True)),
                    )
                )

        return cls(
            credentials=tuple(parsed_creds),
            credential_sets=tuple(parsed_sets),
        )


@dataclass(frozen=True)
class DcqlClaimMatch:
    claim_id: str
    path: tuple[str, ...]
    value: Any


@dataclass(frozen=True)
class DcqlCredentialMatch:
    query_id: str
    credential_id: str
    credential: dict[str, Any]
    matched_claims: Mapping[str, Any]


@dataclass(frozen=True)
class DcqlEvaluationResult:
    """
    Result of evaluating candidate credentials in a wallet against a DCQL query.
    """
    is_satisfied: bool
    matched_credentials: tuple[DcqlCredentialMatch, ...]
    unsatisfied_reason: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "isSatisfied": self.is_satisfied,
            "matchedCredentials": [
                {
                    "queryId": m.query_id,
                    "credentialId": m.credential_id,
                    "matchedClaims": dict(m.matched_claims),
                }
                for m in self.matched_credentials
            ],
            "unsatisfiedReason": self.unsatisfied_reason,
            "details": dict(self.details),
        }
