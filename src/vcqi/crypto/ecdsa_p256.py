"""Deterministic ECDSA over NIST P-256, following RFC 6979.

Why this exists: the demonstrator is meant to be inspected. Its credentials get read
on screen, pasted into issues, and diffed between runs to show that changing one digit
of a measurement result changes the signature. Randomised ECDSA would make every run
produce a different ``proofValue`` even when nothing changed, which buries that signal
in noise. RFC 6979 derives the per-signature nonce from the private key and the message
instead, so identical inputs always produce an identical signature.

Signature verification is delegated to ``cryptography``. Only signing is implemented
here, and only because the library does not expose a deterministic mode.

.. warning::
   This implementation uses ordinary Python integers and is not constant-time. It is
   safe here only because every key in this project is derived from a published seed
   and protects nothing. Never sign with a real key using this code.
"""

from __future__ import annotations

import hashlib
import hmac

__all__ = ["sign_deterministic", "P256"]


class _P256Curve:
    """Domain parameters of the NIST P-256 curve, as given in FIPS 186-4."""

    p = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
    a = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC
    b = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
    gx = 0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296
    gy = 0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5
    n = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
    #: Length of the group order in bytes, which is also the length of r and of s.
    size = 32


P256 = _P256Curve()

_Point = tuple[int, int] | None


def _point_add(first: _Point, second: _Point) -> _Point:
    """Add two points on the curve in affine coordinates.

    Args:
        first: The first point, or None for the point at infinity.
        second: The second point, or None for the point at infinity.

    Returns:
        The sum, or None for the point at infinity.
    """
    if first is None:
        return second
    if second is None:
        return first

    x1, y1 = first
    x2, y2 = second
    if x1 == x2 and (y1 + y2) % P256.p == 0:
        return None

    if first == second:
        slope = (3 * x1 * x1 + P256.a) * pow(2 * y1, -1, P256.p) % P256.p
    else:
        slope = (y2 - y1) * pow(x2 - x1, -1, P256.p) % P256.p

    x3 = (slope * slope - x1 - x2) % P256.p
    y3 = (slope * (x1 - x3) - y1) % P256.p
    return x3, y3


def _scalar_multiply(scalar: int, point: _Point) -> _Point:
    """Multiply a curve point by a scalar using double-and-add.

    Args:
        scalar: The multiplier.
        point: The point to multiply, or None for the point at infinity.

    Returns:
        The resulting point, or None for the point at infinity.
    """
    result: _Point = None
    addend = point
    while scalar:
        if scalar & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        scalar >>= 1
    return result


def _int_to_octets(value: int) -> bytes:
    """Encode an integer as a fixed-width big-endian octet string.

    Args:
        value: A non-negative integer below the group order.

    Returns:
        The 32 byte encoding required by RFC 6979.
    """
    return value.to_bytes(P256.size, "big")


def _bits_to_int(data: bytes) -> int:
    """Convert an octet string to an integer, keeping the leftmost qlen bits.

    Args:
        data: The octet string, normally a hash output.

    Returns:
        The integer value of the leftmost bits.
    """
    value = int.from_bytes(data, "big")
    excess = len(data) * 8 - P256.n.bit_length()
    return value >> excess if excess > 0 else value


def _bits_to_octets(data: bytes) -> bytes:
    """Reduce an octet string modulo the group order and re-encode it.

    Args:
        data: The octet string, normally a hash output.

    Returns:
        The 32 byte encoding of the reduced value.
    """
    return _int_to_octets(_bits_to_int(data) % P256.n)


def _generate_nonce(private_scalar: int, digest: bytes) -> int:
    """Derive the per-signature nonce k as specified in RFC 6979 section 3.2.

    Args:
        private_scalar: The signer's private key.
        digest: The SHA-256 digest of the message being signed.

    Returns:
        A nonce in the range [1, n).
    """
    v = b"\x01" * 32
    k = b"\x00" * 32
    prefix = _int_to_octets(private_scalar) + _bits_to_octets(digest)

    k = hmac.new(k, v + b"\x00" + prefix, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + prefix, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()

    while True:
        v = hmac.new(k, v, hashlib.sha256).digest()
        candidate = _bits_to_int(v)
        if 1 <= candidate < P256.n:
            return candidate
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def sign_deterministic(private_scalar: int, message: bytes) -> bytes:
    """Sign a message with deterministic ECDSA over P-256 and SHA-256.

    Args:
        private_scalar: The signer's private key as an integer.
        message: The message to sign. It is hashed with SHA-256 internally, so callers
            pass the message itself rather than its digest.

    Returns:
        The signature as the 64 byte concatenation of r and s, each 32 bytes
        big-endian. This is the fixed-width form Data Integrity proofs carry, as
        opposed to the DER encoding used elsewhere.
    """
    digest = hashlib.sha256(message).digest()
    scalar_digest = _bits_to_int(digest)

    nonce = _generate_nonce(private_scalar, digest)
    while True:
        point = _scalar_multiply(nonce, (P256.gx, P256.gy))
        assert point is not None, "nonce below the group order cannot give infinity"
        r = point[0] % P256.n
        if r != 0:
            s = pow(nonce, -1, P256.n) * (scalar_digest + r * private_scalar) % P256.n
            if s != 0:
                return _int_to_octets(r) + _int_to_octets(s)
        # RFC 6979 says to keep drawing from the generator if r or s comes out zero.
        # Neither has ever been observed for P-256; the branch exists for correctness.
        nonce = _generate_nonce(private_scalar, digest + b"\x00")
