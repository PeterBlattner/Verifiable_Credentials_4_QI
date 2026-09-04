"""Tests for the ecdsa-jcs-2019 Data Integrity proof implementation."""

from __future__ import annotations

import copy
from datetime import datetime, timezone

import pytest

from vcqi.config import CONTEXT_CREDENTIALS_V2, CRYPTOSUITE
from vcqi.crypto.dataintegrity import (
    ProofError,
    canonical_form,
    format_timestamp,
    proof_verification_method,
    sign_document,
    verify_proof,
)
from vcqi.crypto.keys import derive_key, public_key_from_multikey

CREATED = datetime(2026, 4, 10, 20, 8, 22, tzinfo=timezone.utc)


@pytest.fixture()
def key():
    """Return the demonstration key of the national metrology institute."""
    return derive_key("did:web:metas.example")


@pytest.fixture()
def credential():
    """Return a minimal unsecured credential to sign in tests."""
    return {
        "@context": [CONTEXT_CREDENTIALS_V2],
        "type": ["VerifiableCredential"],
        "issuer": "did:web:metas.example",
        "validFrom": "2026-01-01T00:00:00Z",
        "credentialSubject": {"id": "urn:instrument:standard-resistor", "value": 10000.0012},
    }


def test_sign_then_verify(key, credential) -> None:
    """A freshly signed credential verifies against the published public key."""
    secured, _ = sign_document(credential, key, created=CREATED)
    public_key = public_key_from_multikey(key.public_key_multibase)
    trace = verify_proof(secured, public_key)
    assert trace.proof_value == secured["proof"]["proofValue"]


def test_proof_shape(key, credential) -> None:
    """The proof carries the members the Data Integrity specification requires."""
    secured, _ = sign_document(credential, key, created=CREATED)
    proof = secured["proof"]
    assert proof["type"] == "DataIntegrityProof"
    assert proof["cryptosuite"] == CRYPTOSUITE
    assert proof["created"] == "2026-04-10T20:08:22Z"
    assert proof["proofPurpose"] == "assertionMethod"
    assert proof["verificationMethod"] == "did:web:metas.example#issuance-key-1"
    assert proof["proofValue"].startswith("z")


def test_signing_is_reproducible(key, credential) -> None:
    """Signing the same credential twice gives byte-identical output.

    This is what makes the demonstration diffable: any change in the proof value is
    caused by a change in the credential, never by a fresh random nonce.
    """
    first, _ = sign_document(credential, key, created=CREATED)
    second, _ = sign_document(copy.deepcopy(credential), key, created=CREATED)
    assert first == second


def test_trace_reports_what_was_signed(key, credential) -> None:
    """The trace exposes the canonical forms and the two digests that were signed."""
    secured, trace = sign_document(credential, key, created=CREATED)
    assert trace.canonical_document == canonical_form(secured)
    assert trace.canonical_document.startswith('{"@context":')
    assert len(trace.proof_config_hash) == 64
    assert len(trace.document_hash) == 64
    assert trace.signing_input == trace.proof_config_hash + trace.document_hash


def test_tampering_with_a_value_breaks_the_proof(key, credential) -> None:
    """Changing a measured value invalidates the signature."""
    secured, _ = sign_document(credential, key, created=CREATED)
    secured["credentialSubject"]["value"] = 10000.0013

    public_key = public_key_from_multikey(key.public_key_multibase)
    with pytest.raises(ProofError, match="does not verify"):
        verify_proof(secured, public_key)


def test_tampering_with_the_proof_purpose_breaks_the_proof(key, credential) -> None:
    """The proof configuration is signed too, so its members cannot be edited."""
    secured, _ = sign_document(credential, key, created=CREATED)
    secured["proof"]["proofPurpose"] = "authentication"

    public_key = public_key_from_multikey(key.public_key_multibase)
    with pytest.raises(ProofError, match="does not verify"):
        verify_proof(secured, public_key)


def test_substituted_context_is_rejected(key, credential) -> None:
    """A verifier refuses a proof whose configuration restates a different context."""
    secured, _ = sign_document(credential, key, created=CREATED)
    secured["@context"] = ["https://malicious.example/context/v1"]

    public_key = public_key_from_multikey(key.public_key_multibase)
    with pytest.raises(ProofError, match="restate the document context"):
        verify_proof(secured, public_key)


def test_wrong_key_does_not_verify(key, credential) -> None:
    """A credential signed by one actor does not verify under another actor's key."""
    secured, _ = sign_document(credential, key, created=CREATED)
    other = derive_key("did:web:callab.example")

    public_key = public_key_from_multikey(other.public_key_multibase)
    with pytest.raises(ProofError, match="does not verify"):
        verify_proof(secured, public_key)


def test_reordered_members_still_verify(key, credential) -> None:
    """Canonicalization means member order carries no meaning.

    Someone can pretty-print or re-serialize a credential on the way to a verifier
    without breaking it, which is the entire point of canonicalizing before hashing.
    """
    secured, _ = sign_document(credential, key, created=CREATED)
    reordered = {name: secured[name] for name in reversed(list(secured))}

    public_key = public_key_from_multikey(key.public_key_multibase)
    verify_proof(reordered, public_key)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"proof": None}, "has no proof"),
        ({"proof": [{"type": "DataIntegrityProof"}]}, "single proof"),
        ({"proof": {"type": "DataIntegrityProof"}}, "no proofValue"),
    ],
)
def test_malformed_proofs_are_rejected(key, credential, mutation, message) -> None:
    """Malformed proofs raise rather than being silently treated as unverified."""
    secured, _ = sign_document(credential, key, created=CREATED)
    secured.update(mutation)

    public_key = public_key_from_multikey(key.public_key_multibase)
    with pytest.raises(ProofError, match=message):
        verify_proof(secured, public_key)


def test_unsupported_cryptosuite_is_rejected(key, credential) -> None:
    """A verifier only accepts the cryptosuite it actually implements."""
    secured, _ = sign_document(credential, key, created=CREATED)
    secured["proof"]["cryptosuite"] = "ecdsa-rdfc-2019"

    public_key = public_key_from_multikey(key.public_key_multibase)
    with pytest.raises(ProofError, match="unsupported cryptosuite"):
        verify_proof(secured, public_key)


def test_verification_method_is_readable_before_verification(key, credential) -> None:
    """The verification method can be read out so a key can be resolved first."""
    secured, _ = sign_document(credential, key, created=CREATED)
    assert proof_verification_method(secured) == key.verification_method_id


def test_format_timestamp_drops_sub_second_precision() -> None:
    """Timestamps are UTC with second resolution, as the data model expects."""
    moment = datetime(2026, 4, 10, 20, 8, 22, 123456, tzinfo=timezone.utc)
    assert format_timestamp(moment) == "2026-04-10T20:08:22Z"


def test_format_timestamp_reads_naive_values_as_utc() -> None:
    """A naive datetime is interpreted as UTC rather than local time."""
    assert format_timestamp(datetime(2026, 4, 10, 20, 8, 22)) == "2026-04-10T20:08:22Z"
