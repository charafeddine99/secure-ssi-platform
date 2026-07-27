from collections.abc import Iterable
from dataclasses import dataclass, field

from app.application.ports.user_provider import AuthenticationRecord
from app.domain.auth import User
from app.domain.permissions import Role


_ADMIN_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$HRxmXMXpVwZvsq2dKCZ16w"
    "$USjHeS9IWyYjp3flqsvWREdnNYotG/myvNUo3pG8i4M"
)
_ISSUER_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$5h0xKrclIR5DPWFzPH6VAA"
    "$p+KsASRqwCzM6P28YYzQ2OnsHzHv+LXAMBCZbDcjVHw"
)
_VERIFIER_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$bQUm3kCCkKmFuhAiFtHkEA"
    "$UcQpGn1esIQmMl0XjdYD4z/Y4lEZqsm3qpHPty5LDhU"
)
_HOLDER_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$zDEF7lUI60meaVJnxEzunQ"
    "$k6tHdFM7US6xhHSqBVhEXAO40FsXuCy2OkYanfVT038"
)
_DISABLED_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$xGozoZe0pIoiuH+je3PZqg"
    "$u99YJs82it5BNJwQUDdaWKDfk/cuDumgvk55RVVQvW0"
)
_FALLBACK_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$njpQUbrmZaUUG2184TKdzw"
    "$4YaNGMEQ1z2dgBJeEFG9EhImMCMGNsipWLV61AE+VtU"
)


@dataclass(frozen=True)
class LocalAuthenticationRecord:
    user: User
    password_hash: str = field(repr=False)


class LocalSyntheticUserProvider:
    """Immutable, non-persistent users containing only pre-hashed passwords."""

    authentication_source = "local-synthetic-fixture"

    def __init__(
        self,
        records: Iterable[AuthenticationRecord],
    ) -> None:
        records_by_id: dict[str, AuthenticationRecord] = {}
        records_by_username: dict[str, AuthenticationRecord] = {}
        for record in records:
            username_key = record.user.username.casefold()
            if (
                record.user.id in records_by_id
                or username_key in records_by_username
            ):
                raise ValueError("Synthetic authentication records must be unique.")
            records_by_id[record.user.id] = record
            records_by_username[username_key] = record
        self._records_by_id = records_by_id
        self._records_by_username = records_by_username

    @classmethod
    def default(
        cls,
        *,
        enabled: bool = True,
    ) -> "LocalSyntheticUserProvider":
        if not enabled:
            return cls(())
        return cls(
            (
                LocalAuthenticationRecord(
                    user=User(
                        id="usr_local_admin",
                        username="admin@example.test",
                        display_name="Local Admin",
                        roles=(Role.ADMIN,),
                    ),
                    password_hash=_ADMIN_HASH,
                ),
                LocalAuthenticationRecord(
                    user=User(
                        id="usr_local_issuer",
                        username="issuer@example.test",
                        display_name="Local Issuer",
                        roles=(Role.ISSUER,),
                    ),
                    password_hash=_ISSUER_HASH,
                ),
                LocalAuthenticationRecord(
                    user=User(
                        id="usr_local_verifier",
                        username="verifier@example.test",
                        display_name="Local Verifier",
                        roles=(Role.VERIFIER,),
                    ),
                    password_hash=_VERIFIER_HASH,
                ),
                LocalAuthenticationRecord(
                    user=User(
                        id="usr_local_holder",
                        username="holder@example.test",
                        display_name="Local Holder",
                        roles=(Role.HOLDER,),
                    ),
                    password_hash=_HOLDER_HASH,
                ),
                LocalAuthenticationRecord(
                    user=User(
                        id="usr_local_disabled",
                        username="disabled@example.test",
                        display_name="Disabled Local User",
                        roles=(Role.VERIFIER,),
                        enabled=False,
                    ),
                    password_hash=_DISABLED_HASH,
                ),
            )
        )

    def find_by_username(
        self,
        username: str,
    ) -> AuthenticationRecord | None:
        return self._records_by_username.get(username.strip().casefold())

    def find_by_id(self, user_id: str) -> AuthenticationRecord | None:
        return self._records_by_id.get(user_id)

    def fallback_password_hash(self) -> str:
        return _FALLBACK_HASH

    def __repr__(self) -> str:
        return (
            "LocalSyntheticUserProvider("
            f"users={len(self._records_by_id)}, password_hashes=<redacted>)"
        )
