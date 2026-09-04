"""Multibase, multicodec and multihash encodings used by Verifiable Credentials.

Three encodings appear in the credentials this demonstrator produces:

* ``publicKeyMultibase`` in a DID document verification method, which is a Multikey:
  the multicodec identifier for the key type followed by the key material, encoded as
  base58btc with a ``z`` prefix;
* ``proofValue`` in a Data Integrity proof, which is the raw signature encoded as
  base58btc with a ``z`` prefix;
* ``digestMultibase`` when one document references another by content, which is a
  SHA-256 multihash encoded as unpadded base64url with a ``u`` prefix.
"""

from __future__ import annotations

import base64
import hashlib

__all__ = [
    "base58btc_encode",
    "base58btc_decode",
    "multibase_encode_base58btc",
    "multibase_decode",
    "encode_p256_multikey",
    "decode_p256_multikey",
    "digest_multibase",
    "verify_digest_multibase",
]

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {char: value for value, char in enumerate(_BASE58_ALPHABET)}

# Multicodec identifier 0x1200 (p256-pub) as an unsigned LEB128 varint.
_P256_PUB_PREFIX = bytes([0x80, 0x24])

# Multihash prefix for SHA-256 with a 32 byte digest: code 0x12, length 0x20.
_SHA256_MULTIHASH_PREFIX = bytes([0x12, 0x20])


def base58btc_encode(data: bytes) -> str:
    """Encode bytes using the Bitcoin base58 alphabet.

    Args:
        data: The bytes to encode.

    Returns:
        The base58btc representation, with one leading ``1`` per leading zero byte.
    """
    leading_zeros = len(data) - len(data.lstrip(b"\x00"))
    number = int.from_bytes(data, "big")
    digits = ""
    while number > 0:
        number, remainder = divmod(number, 58)
        digits = _BASE58_ALPHABET[remainder] + digits
    return "1" * leading_zeros + digits


def base58btc_decode(text: str) -> bytes:
    """Decode a base58btc string.

    Args:
        text: The base58btc representation.

    Returns:
        The decoded bytes.

    Raises:
        ValueError: If the text contains a character outside the base58 alphabet.
    """
    leading_ones = len(text) - len(text.lstrip("1"))
    number = 0
    for char in text:
        try:
            number = number * 58 + _BASE58_INDEX[char]
        except KeyError:
            raise ValueError(f"{char!r} is not a base58btc character") from None
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\x00" * leading_ones + body


def multibase_encode_base58btc(data: bytes) -> str:
    """Encode bytes as multibase base58btc.

    Args:
        data: The bytes to encode.

    Returns:
        The encoding, prefixed with the multibase character ``z``.
    """
    return "z" + base58btc_encode(data)


def multibase_decode(text: str) -> bytes:
    """Decode a multibase string in one of the base encodings used here.

    Args:
        text: A multibase string beginning with ``z`` (base58btc) or ``u``
            (unpadded base64url).

    Returns:
        The decoded bytes.

    Raises:
        ValueError: If the multibase prefix is not one this demonstrator uses.
    """
    if not text:
        raise ValueError("empty multibase string")
    prefix, body = text[0], text[1:]
    if prefix == "z":
        return base58btc_decode(body)
    if prefix == "u":
        padding = "=" * (-len(body) % 4)
        return base64.urlsafe_b64decode(body + padding)
    raise ValueError(f"unsupported multibase prefix {prefix!r}")


def encode_p256_multikey(compressed_public_key: bytes) -> str:
    """Encode a compressed NIST P-256 public key as a Multikey.

    Args:
        compressed_public_key: The 33 byte SEC1 compressed point.

    Returns:
        The ``publicKeyMultibase`` value for a Multikey verification method.

    Raises:
        ValueError: If the key material is not 33 bytes long.
    """
    if len(compressed_public_key) != 33:
        raise ValueError(
            f"expected a 33 byte compressed P-256 point, got {len(compressed_public_key)}"
        )
    return multibase_encode_base58btc(_P256_PUB_PREFIX + compressed_public_key)


def decode_p256_multikey(text: str) -> bytes:
    """Recover a compressed P-256 public key from a Multikey.

    Args:
        text: A ``publicKeyMultibase`` value.

    Returns:
        The 33 byte SEC1 compressed point.

    Raises:
        ValueError: If the value does not carry the p256-pub multicodec prefix.
    """
    raw = multibase_decode(text)
    if not raw.startswith(_P256_PUB_PREFIX):
        raise ValueError("multikey does not carry the p256-pub multicodec prefix")
    key = raw[len(_P256_PUB_PREFIX) :]
    if len(key) != 33:
        raise ValueError(f"expected 33 bytes of key material, got {len(key)}")
    return key


def digest_multibase(data: bytes) -> str:
    """Return the SHA-256 ``digestMultibase`` value for some bytes.

    The digest is wrapped as a multihash before encoding, so a consumer can tell which
    hash function produced it without being told out of band.

    Args:
        data: The bytes to digest, normally a canonicalized document.

    Returns:
        The multihash encoded as unpadded base64url with the multibase prefix ``u``.
    """
    multihash = _SHA256_MULTIHASH_PREFIX + hashlib.sha256(data).digest()
    return "u" + base64.urlsafe_b64encode(multihash).decode("ascii").rstrip("=")


def verify_digest_multibase(data: bytes, expected: str) -> bool:
    """Check bytes against a ``digestMultibase`` value.

    Args:
        data: The bytes to check, normally a canonicalized document.
        expected: The ``digestMultibase`` value the reference claims.

    Returns:
        True if the bytes hash to the expected digest, False otherwise. A malformed
        expected value returns False rather than raising, because a verifier meets
        these values as untrusted input.
    """
    try:
        return digest_multibase(data) == expected
    except ValueError:
        return False
