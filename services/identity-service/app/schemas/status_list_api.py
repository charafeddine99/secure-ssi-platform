from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _StatusListApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class StatusListCredentialSubject(_StatusListApiModel):
    id: str
    type: Literal["BitstringStatusList"]
    statusPurpose: Literal["revocation"]
    encodedList: str
    ttl: Annotated[int, Field(ge=1_000)]


class StatusListProof(_StatusListApiModel):
    type: Literal["DataIntegrityProof"]
    cryptosuite: Literal["eddsa-jcs-2022"]
    created: str
    verificationMethod: str
    proofPurpose: Literal["assertionMethod"]
    proofValue: str


class BitstringStatusListCredentialResponse(_StatusListApiModel):
    context: list[str] = Field(alias="@context")
    id: str
    type: list[str]
    issuer: str
    validFrom: str
    credentialSubject: StatusListCredentialSubject
    proof: StatusListProof


class StatusListMetadataResponse(_StatusListApiModel):
    statusListId: str
    statusListCredential: str
    statusPurpose: Literal["revocation"]
    issuer: str
    listLength: int
    capacity: int
    assignedEntries: int
    revokedEntries: int
    utilization: Annotated[float, Field(ge=0, le=1)]
    active: bool
    version: int
    etag: str
    publishedAt: datetime
    ttlSeconds: int
    cacheControl: str


class StatusListVersionSummary(_StatusListApiModel):
    version: int
    etag: str
    contentHash: str
    assignedEntries: int
    revokedEntries: int
    publishedAt: datetime


class StatusListHistoryResponse(_StatusListApiModel):
    statusListId: str
    statusListCredential: str
    active: bool
    latestVersion: int
    versions: list[StatusListVersionSummary]
