BASE58_BTC_ALPHABET = (
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
)


def encode_base58_btc(payload: bytes) -> str:
    if not payload:
        raise ValueError("Cannot base58-btc encode an empty payload.")

    number = int.from_bytes(payload, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58_BTC_ALPHABET[remainder] + encoded

    leading_zeroes = len(payload) - len(payload.lstrip(b"\x00"))
    return f"z{'1' * leading_zeroes}{encoded}"


def decode_base58_btc(value: str) -> bytes:
    if not isinstance(value, str) or not value.startswith("z") or len(value) < 2:
        raise ValueError("A base58-btc multibase value is required.")

    encoded = value[1:]
    number = 0
    try:
        for character in encoded:
            number = number * 58 + BASE58_BTC_ALPHABET.index(character)
    except ValueError as error:
        raise ValueError("The base58-btc value contains an invalid character.") from error

    decoded = (
        number.to_bytes((number.bit_length() + 7) // 8, "big")
        if number
        else b""
    )
    leading_zeroes = len(encoded) - len(encoded.lstrip("1"))
    return b"\x00" * leading_zeroes + decoded
