"""Deterministic demonstration keys and the DID documents that publish them.

Keys are derived from a fixed seed so that every run of the demonstrator produces the
same credentials, which makes screenshots stable and lets the JSON be diffed between
runs. That also means the private keys are effectively public: nothing produced here is
a secret, and nothing here should be reused outside the demonstration.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from vcqi.config import DEMO_SEED
from vcqi.crypto.multibase import decode_p256_multikey, encode_p256_multikey

__all__ = ["DemoKey", "derive_key", "build_did_document", "public_key_from_multikey"]

#: Order of the NIST P-256 group, from FIPS 186-4.
_P256_ORDER = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


@dataclass(frozen=True)
class DemoKey:
    """A deterministic P-256 key pair belonging to one demonstration actor.

    Attributes:
        did: The controller's decentralized identifier, for example
            ``did:web:metas.example``.
        fragment: The verification method fragment, for example ``issuance-key-1``.
        private_key: The derived P-256 private key.
        public_key_multibase: The Multikey form published in the DID document.
    """

    did: str
    fragment: str
    private_key: ec.EllipticCurvePrivateKey
    public_key_multibase: str

    @property
    def verification_method_id(self) -> str:
        """Return the absolute identifier of this verification method.

        Returns:
            The DID URL, for example ``did:web:metas.example#issuance-key-1``.
        """
        return f"{self.did}#{self.fragment}"


def derive_key(did: str, fragment: str = "issuance-key-1") -> DemoKey:
    """Derive an actor's demonstration key pair from the fixed seed.

    The private scalar comes from HMAC-SHA256 over the verification method identifier,
    with a counter that advances in the vanishingly unlikely case that the result falls
    outside the valid range for the P-256 group.

    Args:
        did: The controller's decentralized identifier.
        fragment: The verification method fragment.

    Returns:
        The derived key pair.
    """
    label = f"{did}#{fragment}".encode("utf-8")
    for counter in range(256):
        digest = hmac.new(DEMO_SEED, label + bytes([counter]), hashlib.sha256).digest()
        scalar = int.from_bytes(digest, "big")
        if 1 <= scalar < _P256_ORDER:
            private_key = ec.derive_private_key(scalar, ec.SECP256R1())
            compressed = private_key.public_key().public_bytes(
                Encoding.X962, PublicFormat.CompressedPoint
            )
            return DemoKey(
                did=did,
                fragment=fragment,
                private_key=private_key,
                public_key_multibase=encode_p256_multikey(compressed),
            )
    raise RuntimeError(f"could not derive a valid P-256 scalar for {label!r}")


def public_key_from_multikey(public_key_multibase: str) -> ec.EllipticCurvePublicKey:
    """Recover a P-256 public key from its Multikey form.

    Args:
        public_key_multibase: The ``publicKeyMultibase`` value from a DID document.

    Returns:
        The public key, ready to verify a signature.

    Raises:
        ValueError: If the value is not a well-formed P-256 Multikey.
    """
    compressed = decode_p256_multikey(public_key_multibase)
    return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), compressed)


def build_did_document(
    key: DemoKey,
    *,
    whois_endpoint: str | None = None,
) -> dict[str, Any]:
    """Build the DID document that publishes an actor's verification method.

    Args:
        key: The actor's demonstration key pair.
        whois_endpoint: Optional URL at which the actor publishes a verifiable
            presentation describing itself. When present the document advertises a
            service typed as both ``WhoisService`` and ``PathService``, which is what
            identifier-based discovery in Recognized Entities looks for.

    Returns:
        The DID document as a JSON-compatible dictionary.
    """
    document: dict[str, Any] = {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/multikey/v1",
        ],
        "id": key.did,
        "verificationMethod": [
            {
                "id": key.verification_method_id,
                "type": "Multikey",
                "controller": key.did,
                "publicKeyMultibase": key.public_key_multibase,
            }
        ],
        "assertionMethod": [key.verification_method_id],
        "authentication": [key.verification_method_id],
    }
    if whois_endpoint is not None:
        document["service"] = [
            {
                "id": f"{key.did}#whois",
                "type": ["WhoisService", "PathService"],
                "serviceEndpoint": whois_endpoint,
            }
        ]
    return document
