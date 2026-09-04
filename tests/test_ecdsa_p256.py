"""RFC 6979 test vectors and a cross-check against the cryptography library."""

from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from vcqi.crypto.ecdsa_p256 import P256, sign_deterministic
from vcqi.crypto.keys import derive_key

# RFC 6979 appendix A.2.5: NIST P-256 with SHA-256.
RFC6979_PRIVATE_KEY = 0xC9AFA9D845BA75166B5C215767B1D6934E50C3DB36E89B127B8A622B120F6721
RFC6979_CASES = [
    (
        b"sample",
        0xEFD48B2AACB6A8FD1140DD9CD45E81D69D2C877B56AAF991C34D0EA84EAF3716,
        0xF7CB1C942D657C41D436C7A1B6E29F65F3E900DBB9AFF4064DC4AB2F843ACDA8,
    ),
    (
        b"test",
        0xF1ABB023518351CD71D881567B1EA663ED3EFCF6C5132B354F28D3B0B7D38367,
        0x019F4113742A2B14BD25926B49C649155F267E60D3814B4C0CC84250E46F0083,
    ),
]


@pytest.mark.parametrize(("message", "expected_r", "expected_s"), RFC6979_CASES)
def test_rfc6979_vectors(message: bytes, expected_r: int, expected_s: int) -> None:
    """Signatures match the published RFC 6979 test vectors exactly."""
    signature = sign_deterministic(RFC6979_PRIVATE_KEY, message)
    r = int.from_bytes(signature[: P256.size], "big")
    s = int.from_bytes(signature[P256.size :], "big")
    assert r == expected_r
    assert s == expected_s


def test_signature_is_reproducible() -> None:
    """The same key and message always give the same signature."""
    first = sign_deterministic(RFC6979_PRIVATE_KEY, b"reproducible")
    second = sign_deterministic(RFC6979_PRIVATE_KEY, b"reproducible")
    assert first == second


def test_signature_verifies_with_cryptography() -> None:
    """A signature produced here is accepted by an independent implementation."""
    key = derive_key("did:web:metas.example")
    private_numbers = key.private_key.private_numbers()
    message = b"a calibration certificate"

    signature = sign_deterministic(private_numbers.private_value, message)
    r = int.from_bytes(signature[: P256.size], "big")
    s = int.from_bytes(signature[P256.size :], "big")

    key.private_key.public_key().verify(
        encode_dss_signature(r, s), message, ec.ECDSA(hashes.SHA256())
    )


def test_altered_message_does_not_verify() -> None:
    """Changing one byte of the message invalidates the signature."""
    key = derive_key("did:web:metas.example")
    private_numbers = key.private_key.private_numbers()

    signature = sign_deterministic(private_numbers.private_value, b"10000.0012 ohm")
    r = int.from_bytes(signature[: P256.size], "big")
    s = int.from_bytes(signature[P256.size :], "big")

    with pytest.raises(InvalidSignature):
        key.private_key.public_key().verify(
            encode_dss_signature(r, s), b"10000.0013 ohm", ec.ECDSA(hashes.SHA256())
        )
