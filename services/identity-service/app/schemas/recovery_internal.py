from pydantic import BaseModel, ConfigDict, Field


class StrictInternalModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, str_strip_whitespace=True
    )


class ManagedKeyRecoveryRequest(StrictInternalModel):
    recovery_request_id: str = Field(
        alias="recoveryRequestId", pattern=r"^recovery_[A-Za-z0-9_-]{16,80}$"
    )
    wallet_id: str = Field(
        alias="walletId", pattern=r"^wallet_[A-Za-z0-9_-]{16,80}$"
    )
    owner_user_id: str = Field(alias="ownerUserId", min_length=1, max_length=128)
    reason: str = Field(
        pattern=r"^(ACCOUNT_COMPROMISE|LOST_ACCESS|DEVICE_LOSS|KEY_LOSS)$"
    )


class ManagedKeyRecoveryResponse(StrictInternalModel):
    predecessor_key_id: str = Field(alias="predecessorKeyId")
    successor_key_id: str = Field(alias="successorKeyId")
    predecessor_did: str = Field(alias="predecessorDid")
    successor_did: str = Field(alias="successorDid")
    provider: str
