"""The signer and verifier against the W3C's own test vector for ``ecdsa-jcs-2019``.

Everything this demonstration signs is checked by the verifier written beside the signer,
so a misreading of the specification shared by both would pass unnoticed in both. The
UNTP Playground was tried as an outside check and cannot give one: its verifier has no
suite for any W3C Recommendation cryptosuite, and its enveloped-JWT route rejects a
``did:key`` issuer (docs/history/PLAN-2026.md, change set 29).

The Recommendation itself can. VC Data Integrity ECDSA Cryptosuites v1.0 (W3C
Recommendation, 15 May 2025), Appendix A.5, publishes the computation for
``ecdsa-jcs-2019`` with P-256 step by step: a key pair, an unsigned credential, the
proof configuration, both canonical forms, both hashes, the signature and the signed
credential. The files are vendored unchanged from ``w3c/vc-di-ecdsa`` under
``tests/vectors/w3c-vc-di-ecdsa/``.

The Recommendation says signatures SHOULD be deterministic, and they are here, per RFC
6979. So the strongest form of the check is available: not merely that the W3C's
signature verifies, but that signing the same credential with the same key produces the
W3C's signature, byte for byte. Every intermediate is compared on the way, so a failure
names the step where the reading diverges.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from vcqi.crypto.dataintegrity import ProofError, ProofTrace, sign_document, verify_proof
from vcqi.crypto.keys import DemoKey, public_key_from_multikey
from vcqi.crypto.multibase import encode_p256_multikey, multibase_decode
from vcqi.vc.checks import check_proof
from vcqi.vc.resolver import DocumentStore, Resolver

VECTORS = Path(__file__).resolve().parent / "vectors" / "w3c-vc-di-ecdsa"
JCS_P256 = VECTORS / "ecdsa-jcs-2019-p256"

#: The multicodec prefix of a P-256 private key, ``p256-priv`` (0x1306) as a varint.
P256_PRIVATE_PREFIX = bytes([0x86, 0x26])


def _text(name: str) -> str:
    """Read one of the vector's text files exactly as published.

    Args:
        name: The file name in the ``ecdsa-jcs-2019-p256`` directory.

    Returns:
        Its content. The files carry no trailing newline, and none is stripped, so a
        stray byte added to one is a failure rather than something tolerated.
    """
    return (JCS_P256 / name).read_bytes().decode("utf-8")


def _json(path: Path) -> dict[str, Any]:
    """Read one of the vector's JSON files.

    Args:
        path: The file.

    Returns:
        The parsed document.
    """
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def key() -> DemoKey:
    """The vector's key pair, as the signer here takes a key.

    Returns:
        A key whose identifier is the vector's ``did:key`` and whose private scalar is
        the vector's secret key.
    """
    pair = _json(VECTORS / "p256KeyPair.json")
    secret = multibase_decode(pair["secretKeyMultibase"])
    assert secret[:2] == P256_PRIVATE_PREFIX, "not a P-256 private key"
    private_key = ec.derive_private_key(int.from_bytes(secret[2:], "big"), ec.SECP256R1())
    public = pair["publicKeyMultibase"]
    return DemoKey(
        did=f"did:key:{public}",
        fragment=public,
        private_key=private_key,
        public_key_multibase=public,
    )


@pytest.fixture(scope="module")
def trace(key: DemoKey) -> tuple[dict[str, Any], ProofTrace]:
    """Sign the vector's unsigned credential the way everything here is signed.

    Args:
        key: The vector's key pair.

    Returns:
        The signed credential and the trace of every intermediate value.
    """
    config = _json(JCS_P256 / "proofConfigJCSECDSAP256.json")
    created = datetime.fromisoformat(config["created"].replace("Z", "+00:00"))
    assert created.tzinfo == timezone.utc
    return sign_document(_json(VECTORS / "unsigned.json"), key, created=created)


def test_the_secret_key_derives_the_published_public_key(key: DemoKey) -> None:
    compressed = key.private_key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint
    )
    assert encode_p256_multikey(compressed) == key.public_key_multibase


def test_the_proof_configuration_is_the_published_one(
    trace: tuple[dict[str, Any], ProofTrace],
) -> None:
    _, steps = trace
    assert steps.proof_config == _json(JCS_P256 / "proofConfigJCSECDSAP256.json")


@pytest.mark.parametrize(
    ("step", "published"),
    [
        ("canonical_document", "canonDocJCSECDSAP256.txt"),
        ("document_hash", "docHashJCSECDSAP256.txt"),
        ("canonical_proof_config", "proofCanonJCSECDSAP256.txt"),
        ("proof_config_hash", "proofHashJCSECDSAP256.txt"),
        ("signing_input", "combinedHashJCSECDSAP256.txt"),
    ],
)
def test_every_intermediate_value_is_the_published_one(
    trace: tuple[dict[str, Any], ProofTrace], step: str, published: str
) -> None:
    # In the order the Recommendation computes them, so the first failure is the step
    # where the reading diverges. The combined hash is the proof configuration's hash
    # followed by the document's, and it is what the signature is over.
    _, steps = trace
    assert getattr(steps, step) == _text(published), step


def test_signing_reproduces_the_published_signature(
    trace: tuple[dict[str, Any], ProofTrace],
) -> None:
    # Only possible because both sides sign deterministically, as the Recommendation
    # says they SHOULD: with a random nonce the two signatures would differ and both
    # still be valid.
    signed, steps = trace
    raw = multibase_decode(steps.proof_value)

    assert raw.hex() == _text("sigHexJCSECDSAP256.txt")
    assert steps.proof_value == _text("sigBTC58JCSECDSAP256.txt")
    assert signed == _json(JCS_P256 / "signedJCSECDSAP256.json")


def test_the_published_credential_verifies(key: DemoKey) -> None:
    signed = _json(JCS_P256 / "signedJCSECDSAP256.json")

    verify_proof(signed, public_key_from_multikey(key.public_key_multibase))

    # And with the key the resolver reads out of the did:key itself, fetching nothing.
    resolver = Resolver(DocumentStore())
    resolved = resolver.resolve_public_key(signed["proof"]["verificationMethod"])
    assert resolved is not None
    verify_proof(signed, resolved)
    assert all(record.source == "self-describing" for record in resolver.log)


def test_the_full_check_refuses_it_for_the_issuer_binding_alone(key: DemoKey) -> None:
    # The vector demonstrates the cryptosuite, so its issuer is an https URL and its key
    # a did:key nobody bound to it. This verifier requires the key's controller to be
    # the issuer -- without that, anyone could sign in someone else's name -- and checks
    # that before the signature. So the full check refuses the W3C's example, for that
    # reason and no other; the signature itself verified above.
    signed = _json(JCS_P256 / "signedJCSECDSAP256.json")

    outcome, _ = check_proof(signed, Resolver(DocumentStore()))

    assert not outcome.passed
    assert outcome.evidence == {"controller": key.did, "issuer": signed["issuer"]}


def test_a_one_character_change_is_refused(key: DemoKey) -> None:
    altered = copy.deepcopy(_json(JCS_P256 / "signedJCSECDSAP256.json"))
    altered["credentialSubject"]["alumniOf"] = "The School of Example"

    with pytest.raises(ProofError):
        verify_proof(altered, public_key_from_multikey(key.public_key_multibase))
