"""WP-28 platform backup archive codec and configuration (no database)."""

import base64
import struct
import zlib
from datetime import UTC, datetime

import bson
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.application.services.platform_backup_service import (
    MAGIC,
    MAX_PLAINTEXT_BYTES,
    RESTORE_TARGET_PATTERN,
    PlatformBackupIntegrityError,
    decode_archive,
    encode_archive,
    load_platform_backup_settings,
    parse_plaintext,
)

KEY = bytes(range(32))
HEADER = {
    "format": "secure-ssi-platform-backup",
    "formatVersion": 2,
    "backupId": "pbk_wp28_unit_000000001",
    "sourceDatabase": "wp28_test_source",
    "schemaVersion": 2,
    "createdAt": "2026-11-03T10:00:00Z",
    "cipher": "AES-256-GCM",
    "compression": "zlib",
    "keyId": "unit",
}


def _plaintext() -> bytes:
    created = datetime(2026, 11, 3, tzinfo=UTC)
    return b"".join(
        bson.encode(record)
        for record in (
            {"t": "collection", "c": "users", "i": [{"name": "_id_", "key": [["_id", 1]]}]},
            {"t": "document", "c": "users", "d": {"_id": 1, "createdAt": created}},
            {"t": "document", "c": "users", "d": {"_id": 2, "createdAt": created}},
        )
    )


def test_round_trip_preserves_bson_types_and_counts() -> None:
    archive = encode_archive(header=HEADER, plaintext=_plaintext(), key=KEY)
    header, plaintext = decode_archive(archive, key=KEY, expected_backup_id=HEADER["backupId"])
    contents = parse_plaintext(plaintext)

    assert header["backupId"] == HEADER["backupId"]
    assert contents.collections[0].name == "users" and contents.collections[0].documents == 2
    assert contents.documents["users"][0]["createdAt"].year == 2026
    assert b"users" not in archive  # nothing readable without the key


@pytest.mark.parametrize("offset", [-1, -20, 40])
def test_any_flipped_byte_is_rejected(offset: int) -> None:
    archive = bytearray(encode_archive(header=HEADER, plaintext=_plaintext(), key=KEY))
    archive[offset] ^= 0x01
    with pytest.raises(PlatformBackupIntegrityError):
        decode_archive(bytes(archive), key=KEY)


def test_wrong_key_wrong_backup_id_and_truncation_are_rejected() -> None:
    archive = encode_archive(header=HEADER, plaintext=_plaintext(), key=KEY)
    with pytest.raises(PlatformBackupIntegrityError, match="wrong key"):
        decode_archive(archive, key=bytes(32))
    with pytest.raises(PlatformBackupIntegrityError, match="another backup"):
        decode_archive(archive, key=KEY, expected_backup_id="pbk_other_backup_0000001")
    with pytest.raises(PlatformBackupIntegrityError):
        decode_archive(archive[:30], key=KEY)
    with pytest.raises(PlatformBackupIntegrityError):
        decode_archive(b"PK\x03\x04" + archive, key=KEY)


def test_header_swap_and_cipher_downgrade_are_rejected() -> None:
    archive = encode_archive(header=HEADER, plaintext=_plaintext(), key=KEY)
    other = encode_archive(header={**HEADER, "backupId": "pbk_wp28_unit_000000002"}, plaintext=b"", key=KEY)
    # splice header of `other` onto the body of `archive`: AAD binds the header.
    length = struct.unpack(">I", archive[8:12])[0]
    other_length = struct.unpack(">I", other[8:12])[0]
    spliced = other[: 12 + other_length] + archive[12 + length :]
    with pytest.raises(PlatformBackupIntegrityError):
        decode_archive(spliced, key=KEY)
    downgraded = encode_archive(header={**HEADER, "cipher": "NONE"}, plaintext=b"", key=KEY)
    with pytest.raises(PlatformBackupIntegrityError, match="not supported"):
        decode_archive(downgraded, key=KEY)


def test_decompression_bomb_is_rejected() -> None:
    header_bytes = b'{"backupId":"pbk_wp28_unit_000000001","cipher":"AES-256-GCM","compression":"zlib","format":"secure-ssi-platform-backup","formatVersion":2}'
    nonce = bytes(12)
    bomb = zlib.compress(b"\x00" * (MAX_PLAINTEXT_BYTES + 1024), 9)
    ciphertext = AESGCM(KEY).encrypt(nonce, bomb, MAGIC + header_bytes)
    archive = MAGIC + struct.pack(">I", len(header_bytes)) + header_bytes + nonce + ciphertext
    with pytest.raises(PlatformBackupIntegrityError, match="size limit"):
        decode_archive(archive, key=KEY)


def test_malformed_plaintext_is_rejected() -> None:
    with pytest.raises(PlatformBackupIntegrityError):
        parse_plaintext(b"\x05\x00\x00\x00\x00garbage")
    with pytest.raises(PlatformBackupIntegrityError):
        parse_plaintext(bson.encode({"t": "shell", "c": "x"}))


def test_settings_are_fail_closed_and_redacted() -> None:
    key = base64.b64encode(bytes(range(32))).decode()
    assert not load_platform_backup_settings({}).enabled
    assert not load_platform_backup_settings(
        {"IDENTITY_PLATFORM_BACKUP_ENABLED": "true", "IDENTITY_PLATFORM_BACKUP_KEY_BASE64": key}
    ).enabled
    assert not load_platform_backup_settings(
        {
            "IDENTITY_PLATFORM_BACKUP_ENABLED": "true",
            "IDENTITY_PLATFORM_BACKUP_DIR": "/var/lib/backups",
            "IDENTITY_PLATFORM_BACKUP_KEY_BASE64": base64.b64encode(b"short").decode(),
        }
    ).enabled
    enabled = load_platform_backup_settings(
        {
            "IDENTITY_PLATFORM_BACKUP_ENABLED": "true",
            "IDENTITY_PLATFORM_BACKUP_DIR": "/var/lib/backups",
            "IDENTITY_PLATFORM_BACKUP_KEY_BASE64": key,
        }
    )
    assert enabled.enabled and enabled.key_id != "none"
    assert key not in repr(enabled) and "redacted" in repr(enabled)


@pytest.mark.parametrize(
    ("name", "accepted"),
    [
        ("restore_drill_20261103", True),
        ("secure_identity", False),
        ("restore_drill_", False),
        ("restore_drill_../admin", False),
        ("RESTORE_DRILL_ABCD", False),
        ("admin", False),
    ],
)
def test_restore_target_naming_policy(name: str, accepted: bool) -> None:
    assert bool(RESTORE_TARGET_PATTERN.fullmatch(name)) is accepted
