"""Data Integrity proofs using the ecdsa-jcs-2019 cryptosuite.

A Data Integrity proof binds a signature to a document by hashing two things
separately and signing their concatenation:

1. the *proof configuration*, which is the proof object itself minus its signature, so
   that the purpose, the key and the creation time cannot be altered after the fact;
2. the *unsecured document*, which is the credential minus its proof.

Both are canonicalized first, because two JSON documents that a reader would call
identical can differ byte for byte. Canonicalization is what makes a signature
verifiable by someone who re-serialized the document along the way.

Every intermediate value is returned in a :class:`ProofTrace` so the web interface can
show the reader exactly what was hashed and signed, rather than asking them to take the
result on faith.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from vcqi.config import CRYPTOSUITE
from vcqi.crypto.ecdsa_p256 import P256, sign_deterministic
from vcqi.crypto.jcs import canonicalize, canonicalize_str
from vcqi.crypto.keys import DemoKey
from vcqi.crypto.multibase import multibase_decode, multibase_encode_base58btc

__all__ = [
    "ProofError",
    "ProofTrace",
    "sign_document",
    "verify_proof",
    "proof_verification_method",
    "format_timestamp",
    "canonical_form",
]

PROOF_TYPE = "DataIntegrityProof"


class ProofError(Exception):
    """Raised when a proof is missing, malformed, or uses unsupported parameters."""


@dataclass(frozen=True)
class ProofTrace:
    """Every intermediate value produced while signing or verifying a document.

    Attributes:
        proof_config: The proof object without its proofValue member.
        canonical_proof_config: The proof configuration in RFC 8785 canonical form.
        proof_config_hash: Hex SHA-256 digest of the canonical proof configuration.
        canonical_document: The document without its proof, in canonical form.
        document_hash: Hex SHA-256 digest of the canonical document.
        signing_input: Hex of the 64 bytes actually signed, being the two digests
            concatenated in that order.
        proof_value: The multibase-encoded signature.
    """

    proof_config: dict[str, Any]
    canonical_proof_config: str
    proof_config_hash: str
    canonical_document: str
    document_hash: str
    signing_input: str
    proof_value: str


def format_timestamp(moment: datetime) -> str:
    """Format an instant the way the Verifiable Credentials data model expects.

    Args:
        moment: The instant to format. A naive value is read as UTC.

    Returns:
        An XML Schema dateTime in UTC with no sub-second component, for example
        2026-04-10T20:08:22Z.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_parts(document: dict[str, Any], proof_config: dict[str, Any]) -> ProofTrace:
    """Canonicalize and hash the two halves of the signing input.

    Args:
        document: The unsecured document, with no proof member.
        proof_config: The proof object with no proofValue member.

    Returns:
        A trace with everything filled in except proof_value, which is left empty.
    """
    canonical_config = canonicalize(proof_config)
    canonical_document = canonicalize(document)
    config_digest = hashlib.sha256(canonical_config).digest()
    document_digest = hashlib.sha256(canonical_document).digest()
    return ProofTrace(
        proof_config=proof_config,
        canonical_proof_config=canonical_config.decode("utf-8"),
        proof_config_hash=config_digest.hex(),
        canonical_document=canonical_document.decode("utf-8"),
        document_hash=document_digest.hex(),
        signing_input=(config_digest + document_digest).hex(),
        proof_value="",
    )


def sign_document(
    document: dict[str, Any],
    key: DemoKey,
    *,
    created: datetime,
    proof_purpose: str = "assertionMethod",
    challenge: str | None = None,
    domain: str | None = None,
) -> tuple[dict[str, Any], ProofTrace]:
    """Attach a Data Integrity proof to a document.

    Args:
        document: The document to secure. Any existing proof member is replaced.
        key: The signing key. Its verification method identifier goes into the proof.
        created: When the proof was created.
        proof_purpose: Why the proof was made. Credentials assert claims, so the
            default is assertionMethod.
        challenge: A value supplied by whoever asked for this document, signed into the
            proof so the result answers one request and cannot be replayed against
            another. Only presentations use it; a credential is not a reply to anything.
        domain: Who the document is being presented to, signed in for the same reason:
            it stops a presentation made for one verifier being forwarded to a second.

    Returns:
        A tuple of the secured document and the trace of intermediate values.

    Note:
        Both optional members go into the proof configuration, which is canonicalized
        and hashed along with everything else, so they are covered by the signature
        rather than merely travelling beside it. Verification needs no change to read
        them: ``verify_document`` rebuilds the configuration from every proof member
        except ``proofValue``, so an added member is included automatically -- and a
        tampered one therefore breaks the signature.
    """
    unsecured = {name: value for name, value in document.items() if name != "proof"}

    proof_config: dict[str, Any] = {
        "type": PROOF_TYPE,
        "cryptosuite": CRYPTOSUITE,
        "created": format_timestamp(created),
        "verificationMethod": key.verification_method_id,
        "proofPurpose": proof_purpose,
    }
    if challenge is not None:
        proof_config["challenge"] = challenge
    if domain is not None:
        proof_config["domain"] = domain
    # The proof configuration repeats the context of the document. Under this suite that
    # is redundant and it is worth being exact about why, because the obvious reason is
    # the wrong one: `ecdsa-jcs-2019` canonicalizes the JSON, so `@context` is an ordinary
    # member of the document and is already inside the document hash. Nothing could show
    # the same claims under different term definitions without breaking that hash first.
    # The restatement is kept because it is what an RDF canonicalization suite would need
    # -- there the context is consumed and discarded before hashing, and the proof
    # configuration is the only place it survives -- so a document signed here carries the
    # member a reader of `ecdsa-rdfc-2019` would look for.
    if "@context" in unsecured:
        proof_config["@context"] = unsecured["@context"]

    trace = _hash_parts(unsecured, proof_config)
    private_value = key.private_key.private_numbers().private_value
    signature = sign_deterministic(private_value, bytes.fromhex(trace.signing_input))
    proof_value = multibase_encode_base58btc(signature)

    secured = dict(unsecured)
    secured["proof"] = {**proof_config, "proofValue": proof_value}
    filled = ProofTrace(
        proof_config=proof_config,
        canonical_proof_config=trace.canonical_proof_config,
        proof_config_hash=trace.proof_config_hash,
        canonical_document=trace.canonical_document,
        document_hash=trace.document_hash,
        signing_input=trace.signing_input,
        proof_value=proof_value,
    )
    return secured, filled


def proof_verification_method(document: dict[str, Any]) -> str:
    """Return the verification method identifier that the proof of a document names.

    A verifier needs this before it can resolve a key, so it is read out separately
    from the rest of verification.

    Args:
        document: A secured document.

    Returns:
        The DID URL of the verification method.

    Raises:
        ProofError: If the document carries no single well-formed proof.
    """
    proof = document.get("proof")
    if isinstance(proof, list):
        raise ProofError("this demonstrator secures each document with a single proof")
    if not isinstance(proof, dict):
        raise ProofError("document has no proof")
    method = proof.get("verificationMethod")
    if not isinstance(method, str):
        raise ProofError("proof does not name a verification method")
    return method


def verify_proof(
    document: dict[str, Any], public_key: ec.EllipticCurvePublicKey
) -> ProofTrace:
    """Verify the Data Integrity proof of a document.

    Args:
        document: The secured document.
        public_key: The public key resolved from the verification method of the proof.

    Returns:
        The trace of intermediate values, so a caller can show what was checked.

    Raises:
        ProofError: If the proof is missing, malformed, uses an unsupported
            cryptosuite, restates the context inconsistently, or does not verify.
    """
    proof = document.get("proof")
    if isinstance(proof, list):
        raise ProofError("this demonstrator secures each document with a single proof")
    if not isinstance(proof, dict):
        raise ProofError("document has no proof")

    proof_value = proof.get("proofValue")
    if not isinstance(proof_value, str):
        raise ProofError("proof carries no proofValue")
    if proof.get("type") != PROOF_TYPE:
        raise ProofError("unsupported proof type " + repr(proof.get("type")))
    if proof.get("cryptosuite") != CRYPTOSUITE:
        raise ProofError("unsupported cryptosuite " + repr(proof.get("cryptosuite")))

    proof_config = {name: value for name, value in proof.items() if name != "proofValue"}
    unsecured = {name: value for name, value in document.items() if name != "proof"}

    if "@context" in proof_config and proof_config["@context"] != unsecured.get("@context"):
        raise ProofError("proof configuration does not restate the document context")

    trace = _hash_parts(unsecured, proof_config)

    try:
        signature = multibase_decode(proof_value)
    except ValueError as error:
        raise ProofError("proofValue is not valid multibase: " + str(error)) from error
    if len(signature) != 2 * P256.size:
        raise ProofError(
            "expected a {} byte signature, got {}".format(2 * P256.size, len(signature))
        )

    r = int.from_bytes(signature[: P256.size], "big")
    s = int.from_bytes(signature[P256.size :], "big")
    try:
        public_key.verify(
            encode_dss_signature(r, s),
            bytes.fromhex(trace.signing_input),
            ec.ECDSA(hashes.SHA256()),
        )
    except InvalidSignature as error:
        raise ProofError("signature does not verify against the document") from error

    return ProofTrace(
        proof_config=proof_config,
        canonical_proof_config=trace.canonical_proof_config,
        proof_config_hash=trace.proof_config_hash,
        canonical_document=trace.canonical_document,
        document_hash=trace.document_hash,
        signing_input=trace.signing_input,
        proof_value=proof_value,
    )


def canonical_form(document: dict[str, Any]) -> str:
    """Return the canonical form of a document without its proof.

    Useful for showing a reader what gets hashed, and for computing the content digest
    that one credential uses when it references another.

    Args:
        document: A document, secured or not.

    Returns:
        The RFC 8785 canonical form of the document with any proof removed.
    """
    return canonicalize_str(
        {name: value for name, value in document.items() if name != "proof"}
    )
