class RemoteBackupKeyWrapper:
    """Envelope encryption: each archive's data key is wrapped inside the KMS,
    and this service only ever holds that one data key while using it."""

    def __init__(self, kms, key_reference: str) -> None:
        self._kms = kms
        self._reference = key_reference

    @property
    def key_reference(self) -> str:
        return self._reference

    def wrap(self, data_key: bytes) -> str:
        return self._kms.wrap_data_key(
            data_key,
            provider_key_reference=self._reference,
        )

    def unwrap(self, wrapped: str) -> bytes:
        data_key = self._kms.unwrap_data_key(
            wrapped,
            provider_key_reference=self._reference,
        )
        if len(data_key) != 32:
            raise ValueError("The unwrapped key has the wrong length.")
        return data_key
