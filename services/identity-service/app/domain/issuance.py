from dataclasses import dataclass


class CredentialIssuanceError(Exception):
    """Base class for controlled issuance failures."""


class CredentialAlreadyIssuedError(CredentialIssuanceError):
    """The credential id already exists."""


class IssuanceStatusSlotConflictError(CredentialIssuanceError):
    """The selected status-list slot was reserved concurrently."""


class IssuanceValidationError(CredentialIssuanceError):
    """The unsigned credential cannot enter the issuance lifecycle."""


@dataclass(frozen=True)
class IssuanceStatistics:
    succeeded: int
    failed: int
    rollover_count: int
