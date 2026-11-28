"""Versioned detection rules. Deterministic and explainable; nothing here is learned.

ATT&CK ids are a reference vocabulary, not a claim of detection coverage.
"""

from dataclasses import dataclass, field

RULESET_VERSION = "ssi-rules-1.1"
SUSPICIOUS = "SUSPICIOUS_ACTIVITY"
SUSPECTED = "SUSPECTED_ATTACK"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    category: str
    state: str
    severity: str
    confidence: str
    trigger: tuple[str, ...]
    group: str
    threshold: int
    window_seconds: int
    counted: tuple[str, ...] = ()
    attack: tuple[str, ...] = ()
    reference: str = ""
    explanation: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def counted_types(self) -> tuple[str, ...]:
        return self.counted or self.trigger


RULES: tuple[Rule, ...] = (
    Rule("AUTH-01", "Repeated failed sign-in for one account", "Authentication abuse", SUSPICIOUS, "MEDIUM", "MEDIUM",
         ("auth.login.failure",), "actor_ref", 5, 300, attack=("T1110.001",),
         explanation="Five failed sign-ins for one account in five minutes. A forgotten password can do this too."),
    Rule("AUTH-02", "Many rejected sign-ins from one source", "Authentication abuse", SUSPICIOUS, "MEDIUM", "LOW",
         ("gateway.login.rejected",), "source_ref", 10, 300, attack=("T1110.003", "T1110.004"),
         explanation="Ten rejected sign-ins from one source in five minutes. Behind a proxy, one source can be many people."),
    Rule("AUTH-03", "Sign-in success right after a failure burst", "Authentication abuse", SUSPECTED, "HIGH", "MEDIUM",
         ("auth.login.success",), "actor_ref", 5, 600, counted=("auth.login.failure",), attack=("T1110", "T1078"),
         explanation="A success after at least five failures in ten minutes suggests a guessed password. The owner may also have remembered it."),
    Rule("MFA-01", "Repeated failed step-up", "MFA abuse", SUSPICIOUS, "MEDIUM", "MEDIUM",
         ("auth.stepup.failure",), "actor_ref", 3, 300, attack=("T1621",),
         explanation="Three failed step-up attempts by one account in five minutes."),
    Rule("SES-01", "Rejected session or token reuse", "Token misuse", SUSPICIOUS, "MEDIUM", "LOW",
         ("auth.session.rejected",), "source_ref", 20, 300, attack=("T1550",),
         explanation="Twenty calls with an invalid session from one source in five minutes. Expired sessions cause this too."),
    Rule("API-01", "Authorization probing", "API authorization probing", SUSPICIOUS, "MEDIUM", "LOW",
         ("authz.denied",), "source_ref", 10, 300, reference="OWASP API1:2023, API5:2023",
         explanation="Ten refused calls from one source in five minutes, a pattern consistent with BOLA or BFLA probing."),
    Rule("API-02", "Sustained rate limiting", "Resource abuse", SUSPICIOUS, "LOW", "MEDIUM",
         ("api.rate_limited",), "source_ref", 20, 60, attack=("T1499",), reference="OWASP API4:2023",
         explanation="Twenty rate-limited calls from one source in a minute."),
    Rule("VCI-01", "OID4VCI token or proof failures", "Issuance abuse", SUSPICIOUS, "MEDIUM", "LOW",
         ("oid4vci.token.failure", "oid4vci.credential.failure"), "source_ref", 5, 300,
         explanation="Five failed token or credential calls from one source in five minutes. SSI-specific; no ATT&CK mapping is claimed."),
    Rule("VP-01", "Repeated rejected presentations", "Presentation abuse", SUSPICIOUS, "MEDIUM", "LOW",
         ("presentation.rejected",), "resource_ref", 3, 600,
         explanation="Three rejected presentations on one subject in ten minutes, for example a revoked credential shown again."),
    Rule("VP-02", "OID4VP request failures", "Presentation abuse", SUSPICIOUS, "MEDIUM", "LOW",
         ("oid4vp.request.failure",), "source_ref", 5, 300,
         explanation="Five failed OID4VP calls from one source in five minutes, including replays and bad handles."),
    Rule("WAL-01", "Wallet ownership refused", "Object authorization probing", SUSPICIOUS, "MEDIUM", "MEDIUM",
         ("wallet.ownership.rejected",), "actor_ref", 3, 600, reference="OWASP API1:2023",
         explanation="Three refused attempts by one account to use another wallet in ten minutes."),
    Rule("REC-01", "Repeated invalid Guardian proofs", "Recovery abuse", SUSPECTED, "HIGH", "MEDIUM",
         ("recovery.proof_rejected",), "resource_ref", 3, 3600,
         explanation="Three rejected Guardian proofs on one wallet within an hour."),
    Rule("REC-02", "Unauthorized recovery attempt", "Recovery abuse", SUSPICIOUS, "HIGH", "HIGH",
         ("recovery.unauthorized",), "resource_ref", 1, 3600,
         explanation="The recovery service refused an action by someone not allowed to take it, such as self-approval."),
    Rule("REC-03", "Recovery soon after a weakened policy", "Recovery abuse", SUSPECTED, "HIGH", "MEDIUM",
         ("recovery.requested",), "resource_ref", 1, 86400, counted=("recovery.policy_weakened",),
         explanation="A recovery was requested within a day of a weaker policy or Guardian change being scheduled. Setting up a policy does not count."),
    Rule("REC-04", "Invalid recovery share", "Integrity", SUSPICIOUS, "HIGH", "HIGH",
         ("recovery.share_invalid",), "resource_ref", 1, 3600,
         explanation="A stored recovery share failed validation."),
    Rule("KEY-01", "Key marked compromised", "Key management", SUSPICIOUS, "HIGH", "HIGH",
         ("key.compromised",), "resource_ref", 1, 3600, attack=("T1552",),
         explanation="Two administrators marked a key compromised. This needs follow-up by definition."),
    Rule("KEY-02", "Refused key access", "Key management", SUSPICIOUS, "HIGH", "MEDIUM",
         ("key.unauthorized_access", "key.signing_rejected"), "actor_ref", 3, 600,
         explanation="Three refused key operations by one account in ten minutes."),
    Rule("KEY-03", "Key provider mismatch", "Integrity", SUSPICIOUS, "HIGH", "HIGH",
         ("key.provider_mismatch",), "resource_ref", 1, 3600,
         explanation="A key's stored state did not match its provider."),
    Rule("TRU-01", "Burst of trust registry changes", "Privileged activity", SUSPICIOUS, "MEDIUM", "LOW",
         ("trust.changed",), "actor_ref", 5, 600, attack=("T1098",),
         explanation="Five trust registry changes by one administrator in ten minutes."),
    Rule("ADM-01", "Issuer scope changed", "Privileged activity", SUSPICIOUS, "LOW", "LOW",
         ("admin.scope_changed",), "actor_ref", 3, 600, attack=("T1098",),
         explanation="Three issuer scope changes by one administrator in ten minutes."),
    Rule("BKP-01", "Backup failed verification", "Integrity", SUSPICIOUS, "HIGH", "HIGH",
         ("backup.verify_failed",), "resource_ref", 1, 3600, attack=("T1565",),
         explanation="A platform backup failed its integrity check."),
    Rule("BKP-02", "Repeated rejected wallet restore", "Backup abuse", SUSPICIOUS, "MEDIUM", "LOW",
         ("wallet.restore.rejected",), "actor_ref", 3, 3600,
         explanation="Three rejected wallet restores by one account in an hour."),
)

RULES_BY_TRIGGER: dict[str, tuple[Rule, ...]] = {}
for _rule in RULES:
    for _type in _rule.trigger:
        RULES_BY_TRIGGER[_type] = (*RULES_BY_TRIGGER.get(_type, ()), _rule)
