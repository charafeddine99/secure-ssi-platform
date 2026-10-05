from __future__ import annotations

from typing import Any, Mapping, Sequence
from app.domain.dcql import (
    DcqlClaimMatch,
    DcqlClaimQuery,
    DcqlCredentialMatch,
    DcqlCredentialQuery,
    DcqlCredentialSet,
    DcqlEvaluationResult,
    DcqlQuery,
    MalformedDcqlQueryError,
    UnsupportedDcqlFeatureError,
)

# Supported credential formats in the V2.1 Project Profile
SUPPORTED_FORMATS: frozenset[str] = frozenset({"w3c_vc", "ldp_vc", "jwt_vc_json"})


class DcqlEngine:
    """
    Authoritative DCQL Evaluation Engine conforming to OpenID for Verifiable Presentations 1.0 Final.
    Evaluates DCQL queries against stored/candidate credentials in a holder wallet or verifier pipeline.
    """

    @staticmethod
    def extract_value_at_path(data: Mapping[str, Any], path: Sequence[str]) -> tuple[bool, Any]:
        """
        Traverses a nested mapping following the path segments.
        Returns (True, value) if the path exists, or (False, None) if not found.
        """
        current: Any = data
        for segment in path:
            if not isinstance(current, Mapping):
                return False, None
            if segment not in current:
                return False, None
            current = current[segment]
        return True, current

    @classmethod
    def evaluate_credential_query(
        cls,
        query: DcqlCredentialQuery,
        candidate: Mapping[str, Any],
    ) -> tuple[bool, Mapping[str, Any], str | None]:
        """
        Evaluates a single candidate credential against a DcqlCredentialQuery.
        Returns (is_match, matched_claims_dict, failure_reason).
        """
        # 1. Format validation
        fmt = (query.format or "w3c_vc").lower()
        if fmt not in SUPPORTED_FORMATS:
            return False, {}, f"Unsupported credential format '{query.format}' in query '{query.id}'."

        # 2. Type matching (meta.type_values)
        if query.type_values:
            raw_types = candidate.get("type", [])
            cand_types: set[str] = set()
            if isinstance(raw_types, str):
                cand_types.add(raw_types)
            elif isinstance(raw_types, Sequence):
                cand_types = {str(t) for t in raw_types}

            for req_type in query.type_values:
                if req_type not in cand_types:
                    return (
                        False,
                        {},
                        f"Credential missing requested type '{req_type}' (present: {list(cand_types)}).",
                    )

        # 3. Claims path extraction and optional value matching
        matched_claims: dict[str, Any] = {}
        for claim_req in query.claims:
            found, val = cls.extract_value_at_path(candidate, claim_req.path)
            if not found:
                path_str = ".".join(claim_req.path)
                return False, {}, f"Claim path '{path_str}' not present in credential."

            # Optional value matching
            if claim_req.values is not None:
                matched_val = False
                for expected in claim_req.values:
                    if val == expected or str(val).strip() == str(expected).strip():
                        matched_val = True
                        break
                if not matched_val:
                    return (
                        False,
                        {},
                        f"Claim '{claim_req.id}' value {val!r} does not match allowed values {list(claim_req.values)}.",
                    )

            matched_claims[claim_req.id] = val

        return True, matched_claims, None

    @classmethod
    def evaluate(
        cls,
        query: DcqlQuery | Mapping[str, Any],
        candidate_credentials: Sequence[Mapping[str, Any]],
    ) -> DcqlEvaluationResult:
        """
        Evaluates all candidate credentials against the DCQL query.
        Returns a structured DcqlEvaluationResult.
        Fail-closed: Returns is_satisfied=False on any mismatch, malformed query, or lack of credentials.
        """
        if isinstance(query, Mapping):
            try:
                typed_query = DcqlQuery.from_dict(query)
            except MalformedDcqlQueryError as err:
                return DcqlEvaluationResult(
                    is_satisfied=False,
                    matched_credentials=(),
                    unsatisfied_reason=f"MALFORMED_DCQL_QUERY: {err}",
                )
            except Exception as err:
                return DcqlEvaluationResult(
                    is_satisfied=False,
                    matched_credentials=(),
                    unsatisfied_reason=f"DCQL_PARSE_ERROR: {err}",
                )
        else:
            typed_query = query

        if not candidate_credentials:
            return DcqlEvaluationResult(
                is_satisfied=False,
                matched_credentials=(),
                unsatisfied_reason="NO_CANDIDATE_CREDENTIALS_AVAILABLE",
            )

        # Map query_id -> list of (credential, matched_claims)
        query_matches: dict[str, list[DcqlCredentialMatch]] = {
            q.id: [] for q in typed_query.credentials
        }

        for q in typed_query.credentials:
            for cand in candidate_credentials:
                matched, claims, _ = cls.evaluate_credential_query(q, cand)
                if matched:
                    cand_id = str(cand.get("id") or cand.get("@id") or f"cred_{len(query_matches[q.id])}")
                    match_obj = DcqlCredentialMatch(
                        query_id=q.id,
                        credential_id=cand_id,
                        credential=dict(cand),
                        matched_claims=claims,
                    )
                    query_matches[q.id].append(match_obj)

        # Evaluate credential_sets satisfaction
        all_matched_list: list[DcqlCredentialMatch] = []
        selected_query_ids: set[str] = set()

        if typed_query.credential_sets:
            for cset in typed_query.credential_sets:
                set_satisfied = False
                chosen_option: tuple[str, ...] | None = None

                for option in cset.options:
                    # An option is satisfied if EVERY query_id in option has at least one match
                    if all(len(query_matches.get(qid, [])) > 0 for qid in option):
                        set_satisfied = True
                        chosen_option = option
                        break

                if not set_satisfied and cset.required:
                    return DcqlEvaluationResult(
                        is_satisfied=False,
                        matched_credentials=(),
                        unsatisfied_reason=(
                            f"UNSATISFIED_CREDENTIAL_SET: Requirement '{cset.purpose or 'required_set'}' "
                            f"could not be satisfied by wallet credentials."
                        ),
                    )

                if chosen_option:
                    for qid in chosen_option:
                        if qid not in selected_query_ids:
                            selected_query_ids.add(qid)
                            all_matched_list.extend(query_matches[qid])
        else:
            # Default behavior: All requested credential queries must be satisfied
            for q in typed_query.credentials:
                if not query_matches[q.id]:
                    return DcqlEvaluationResult(
                        is_satisfied=False,
                        matched_credentials=(),
                        unsatisfied_reason=(
                            f"UNSATISFIED_CREDENTIAL_QUERY: No matching credential found for query '{q.id}' "
                            f"(requested types: {list(q.type_values)})."
                        ),
                    )
                all_matched_list.extend(query_matches[q.id])

        return DcqlEvaluationResult(
            is_satisfied=True,
            matched_credentials=tuple(all_matched_list),
            unsatisfied_reason=None,
            details={
                "selectedQueryIds": list(selected_query_ids or [q.id for q in typed_query.credentials]),
                "totalMatches": len(all_matched_list),
            },
        )


def build_dcql_query_from_types_and_fields(
    requested_types: Sequence[str],
    requested_fields: Sequence[str],
    *,
    query_id: str = "query_1",
    purpose: str | None = None,
) -> DcqlQuery:
    """
    Constructs a standard, strongly typed OID4VP 1.0 DCQL query from credential types and claim names.
    If multiple requested_types are provided, they are modeled as alternative queries in credential_sets.
    """
    claims = [
        DcqlClaimQuery(
            id=f"claim_{f.replace(' ', '_').lower()}",
            path=("credentialSubject", f),
        )
        for f in requested_fields
    ]
    unique_types = list(dict.fromkeys(requested_types)) if requested_types else ["VerifiableCredential"]
    if len(unique_types) == 1:
        cred_query = DcqlCredentialQuery(
            id=query_id,
            format="w3c_vc",
            type_values=(unique_types[0],),
            claims=tuple(claims),
            meta={"type_values": [unique_types[0]]},
        )
        cset = DcqlCredentialSet(
            options=((query_id,),),
            purpose=purpose or "Verification of requested credentials",
            required=True,
        )
        return DcqlQuery(
            credentials=(cred_query,),
            credential_sets=(cset,),
        )

    # Multiple alternative types: assemble individual credential queries and alternative options in credential_sets
    cred_queries: list[DcqlCredentialQuery] = []
    options: list[tuple[str, ...]] = []
    for idx, ctype in enumerate(unique_types, start=1):
        qid = f"{query_id}_{idx}"
        cq = DcqlCredentialQuery(
            id=qid,
            format="w3c_vc",
            type_values=(ctype,),
            claims=tuple(claims),
            meta={"type_values": [ctype]},
        )
        cred_queries.append(cq)
        options.append((qid,))

    cset = DcqlCredentialSet(
        options=tuple(options),
        purpose=purpose or "Verification of requested credentials (alternative accepted types)",
        required=True,
    )
    return DcqlQuery(
        credentials=tuple(cred_queries),
        credential_sets=(cset,),
    )


def convert_legacy_presentation_definition_to_dcql(pe: Mapping[str, Any]) -> DcqlQuery:
    """
    Translates legacy DIF Presentation Exchange v2 input_descriptors into a canonical DcqlQuery.
    Strictly marked as a legacy compatibility translation.
    """
    input_descriptors = pe.get("input_descriptors", [])
    cred_queries: list[DcqlCredentialQuery] = []
    options: list[str] = []

    for idx, desc in enumerate(input_descriptors):
        desc_id = str(desc.get("id") or f"query_{idx + 1}")
        options.append(desc_id)
        
        # Schema / Type extraction
        type_values: list[str] = []
        schema_entries = desc.get("schema", [])
        for s in schema_entries:
            uri = str(s.get("uri", ""))
            if uri:
                type_values.append(uri.rstrip("/").split("/")[-1])

        # Constraints fields extraction
        constraints = desc.get("constraints", {})
        fields = constraints.get("fields", [])
        claims: list[DcqlClaimQuery] = []
        for f_idx, f in enumerate(fields):
            paths = f.get("path", [])
            if paths:
                raw_path = paths[0]
                # Clean json path syntax e.g. "$.credentialSubject.degree" -> ["credentialSubject", "degree"]
                cleaned_segments = [seg for seg in raw_path.replace("$.", "").split(".") if seg]
                c_id = f"claim_{f_idx + 1}"
                
                # Check for filter.const or filter.enum
                filter_obj = f.get("filter")
                values = None
                if isinstance(filter_obj, Mapping):
                    if "const" in filter_obj:
                        values = (filter_obj["const"],)
                    elif "enum" in filter_obj and isinstance(filter_obj["enum"], Sequence):
                        values = tuple(filter_obj["enum"])

                if cleaned_segments:
                    claims.append(
                        DcqlClaimQuery(
                            id=c_id,
                            path=tuple(cleaned_segments),
                            values=values,
                        )
                    )

        cred_queries.append(
            DcqlCredentialQuery(
                id=desc_id,
                format="w3c_vc",
                type_values=tuple(type_values),
                claims=tuple(claims),
                meta={"type_values": type_values, "legacySource": "presentation_definition"},
            )
        )

    if not cred_queries:
        # Fallback minimal query
        cred_queries.append(
            DcqlCredentialQuery(
                id="legacy_fallback_query",
                format="w3c_vc",
                type_values=("VerifiableCredential",),
                claims=(),
            )
        )
        options = ["legacy_fallback_query"]

    cset = DcqlCredentialSet(
        options=(tuple(options),),
        purpose=pe.get("purpose", "Legacy Presentation Definition Compatibility"),
        required=True,
    )
    return DcqlQuery(
        credentials=tuple(cred_queries),
        credential_sets=(cset,),
    )
