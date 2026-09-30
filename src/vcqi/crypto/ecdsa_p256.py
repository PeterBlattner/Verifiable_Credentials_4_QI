"""Deterministic ECDSA over NIST P-256, and the arithmetic behind a public key.

Why deterministic: the demonstrator is meant to be inspected. Its credentials get read
on screen, pasted into issues, and diffed between runs to show that changing one digit
of a measurement result changes the signature. Randomised ECDSA would make every run
produce a different ``proofValue`` even when nothing changed, which buries that signal
in noise. RFC 6979 derives the per-signature nonce from the private key and the message
instead, so identical inputs always produce an identical signature.

Signing and verification are both delegated to ``cryptography``, whose ECDSA has taken
``deterministic_signing=True`` since 43.0. This module used to sign with its own
RFC 6979 implementation, written when the library had no such mode. The two gave
byte-identical signatures, and the library's is constant-time and about a hundred times
faster (issue #70). The RFC 6979 vectors in ``tests/test_ecdsa_p256.py`` and the W3C's
``ecdsa-jcs-2019`` vector in ``tests/test_w3c_vectors.py`` pin that it still does what
the demonstration relies on.

What stays here is :func:`public_point`, which the keys chapter uses to show that a
public key is nothing but the private key times the curve's generator.

.. warning::
   :func:`public_point` uses ordinary Python integers and is not constant-time. It is
   there to be read, and every key it meets in this project is either derived from a
   published seed or handed over by the caller. Never use it with a real key.
"""

from __future__ import annotations

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

__all__ = ["sign_deterministic", "public_point", "P256"]


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


def sign_deterministic(private_scalar: int, message: bytes) -> bytes:
    """Sign a message with deterministic ECDSA over P-256 and SHA-256.

    Args:
        private_scalar: The signer's private key as an integer.
        message: The message to sign. It is hashed with SHA-256 internally, so callers
            pass the message itself rather than its digest.

    Returns:
        The signature as the 64 byte concatenation of r and s, each 32 bytes
        big-endian. This is the fixed-width form Data Integrity proofs carry, as
        opposed to the DER encoding the library returns.

    Raises:
        ValueError: If the scalar is outside [1, n), where it is not a P-256 key.
    """
    key = ec.derive_private_key(private_scalar, ec.SECP256R1())
    der = key.sign(message, ec.ECDSA(hashes.SHA256(), deterministic_signing=True))
    r, s = decode_dss_signature(der)
    return r.to_bytes(P256.size, "big") + s.to_bytes(P256.size, "big")


def public_point(private_scalar: int) -> tuple[int, int]:
    """Compute the public key belonging to a private key.

    This is the whole of what makes a keypair asymmetric, and it is one line of
    arithmetic: multiply the curve generator by the private scalar. Doing it takes a few
    milliseconds in the plain integers below, and a fraction of one in OpenSSL. Undoing
    it, recovering the scalar from the resulting point, is the elliptic curve discrete
    logarithm problem, and nobody knows how to do it for P-256 in any useful amount of
    time.

    That asymmetry is the only reason a public key can be published safely.

    Args:
        private_scalar: The private key, an integer in the range [1, n).

    Returns:
        The public key as the affine coordinates (x, y) of the point d times G.

    Raises:
        ValueError: If the scalar is outside the valid range for the group, where the
            result would either be the point at infinity or a repeat of another key.
    """
    if not 1 <= private_scalar < P256.n:
        raise ValueError(
            f"a private key must lie in [1, n) with n = {P256.n}; got {private_scalar}"
        )
    point = _scalar_multiply(private_scalar, (P256.gx, P256.gy))
    assert point is not None, "a scalar below the group order cannot give infinity"
    return point
