"""The checks that apply to any credential, whatever it says.

These four are what "verify a credential" means before any domain knowledge is
involved: is it the right shape, was it really signed by the key its issuer publishes,
is it inside its validity period, and has it been withdrawn since. They are separated
out here because both the verification pipeline and the recognition chain traversal
need them, and a chain is only as good as the checks applied to every link in it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from vcqi.crypto.dataintegrity import (
    ProofError,
    ProofTrace,
    proof_verification_method,
    verify_proof,
)
from vcqi.vc.resolver import Resolver
from vcqi.vc.status import read_status

__all__ = [
    "CheckOutcome",
    "check_shape",
    "check_proof",
    "check_validity_period",
    "check_status",
    "parse_timestamp",
    "credential_types",
]

#: Members every Verifiable Credential must carry under the version 2 data model.
REQUIRED_MEMBERS = ("@context", "type", "issuer", "credentialSubject")


@dataclass(frozen=True)
class CheckOutcome:
    """The result of one check.

    Attributes:
        passed: Whether the check succeeded.
        detail: Human-readable explanation, phrased so it is worth reading whether the
            check passed or failed.
        evidence: Structured supporting data for the interface to display.
    """

    passed: bool
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


def parse_timestamp(value: Any) -> datetime | None:
    """Parse an XML Schema dateTime as it appears in a credential.

    Args:
        value: The member to parse, which may be absent or of the wrong type.

    Returns:
        The instant in UTC, or None when the value is missing or unparseable.
    """
    if not isinstance(value, str):
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def credential_types(credential: dict[str, Any]) -> list[str]:
    """Return the types of a credential as a list.

    Args:
        credential: The credential to inspect.

    Returns:
        The declared types, empty when the member is missing or malformed.
    """
    value = credential.get("type")
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def issuer_id(credential: dict[str, Any]) -> str | None:
    """Return the identifier of the issuer of a credential.

    The data model allows the issuer to be either a string or an object with an id, and
    a verifier has to handle both without guessing.

    Args:
        credential: The credential to inspect.

    Returns:
        The issuer identifier, or None when it is missing or malformed.
    """
    issuer = credential.get("issuer")
    if isinstance(issuer, str):
        return issuer
    if isinstance(issuer, dict) and isinstance(issuer.get("id"), str):
        return issuer["id"]
    return None


def check_shape(credential: dict[str, Any]) -> CheckOutcome:
    """Check that a document is shaped like a Verifiable Credential.

    Args:
        credential: The document to check.

    Returns:
        The outcome, naming any member that is missing.
    """
    missing = [member for member in REQUIRED_MEMBERS if member not in credential]
    types = credential_types(credential)

    if missing:
        return CheckOutcome(
            passed=False,
            detail=f"missing required member(s): {', '.join(missing)}",
            evidence={"missing": missing},
        )
    if "VerifiableCredential" not in types:
        return CheckOutcome(
            passed=False,
            detail="type does not include VerifiableCredential",
            evidence={"type": types},
        )
    specific = [name for name in types if name != "VerifiableCredential"]
    return CheckOutcome(
        passed=True,
        detail=(
            f"well-formed {' and '.join(specific) if specific else 'credential'} "
            f"issued by {issuer_id(credential)}"
        ),
        evidence={"type": types, "issuer": issuer_id(credential)},
    )


def check_proof(
    credential: dict[str, Any], resolver: Resolver
) -> tuple[CheckOutcome, ProofTrace | None]:
    """Verify the proof of a credential against the key its issuer publishes.

    The key is taken from the identifier named in the proof, resolved through the
    controller. Two further conditions matter beyond the signature arithmetic: the
    controller of the key has to be the issuer of the credential, and the controller
    has to have authorised that key for asserting claims. Without the first, anyone
    could sign a credential in someone else's name; without the second, a key published
    only for logging in would be enough to issue certificates.

    Args:
        credential: The secured credential.
        resolver: Used to resolve the verification method.

    Returns:
        The outcome and, when verification succeeded, the trace of what was hashed.
    """
    try:
        method_id = proof_verification_method(credential)
    except ProofError as error:
        return CheckOutcome(passed=False, detail=str(error)), None

    controller, _, _ = method_id.partition("#")
    issuer = issuer_id(credential)
    if issuer is None:
        return CheckOutcome(passed=False, detail="credential names no issuer"), None
    if controller != issuer:
        return (
            CheckOutcome(
                passed=False,
                detail=(
                    f"proof was made with a key controlled by {controller}, but the "
                    f"credential claims to be issued by {issuer}"
                ),
                evidence={"controller": controller, "issuer": issuer},
            ),
            None,
        )

    public_key = resolver.resolve_public_key(method_id)
    if public_key is None:
        return (
            CheckOutcome(
                passed=False,
                detail=f"{method_id} does not resolve to a published key",
                evidence={"verificationMethod": method_id},
            ),
            None,
        )

    if method_id not in resolver.assertion_methods(issuer):
        return (
            CheckOutcome(
                passed=False,
                detail=f"{issuer} does not authorise {method_id} for asserting claims",
                evidence={"verificationMethod": method_id},
            ),
            None,
        )

    try:
        trace = verify_proof(credential, public_key)
    except ProofError as error:
        return (
            CheckOutcome(
                passed=False,
                detail=str(error),
                evidence={"verificationMethod": method_id},
            ),
            None,
        )

    return (
        CheckOutcome(
            passed=True,
            detail=f"signature verifies against the key {issuer} publishes as {method_id}",
            evidence={
                "verificationMethod": method_id,
                "cryptosuite": credential["proof"].get("cryptosuite"),
                "documentHash": trace.document_hash,
                "proofConfigHash": trace.proof_config_hash,
            },
        ),
        trace,
    )


def check_validity_period(credential: dict[str, Any], now: datetime) -> CheckOutcome:
    """Check that a credential is inside its validity period.

    Args:
        credential: The credential to check.
        now: The instant to check against.

    Returns:
        The outcome, naming the bound that was crossed when it fails.
    """
    valid_from = parse_timestamp(credential.get("validFrom"))
    valid_until = parse_timestamp(credential.get("validUntil"))
    evidence = {
        "validFrom": credential.get("validFrom"),
        "validUntil": credential.get("validUntil"),
        "verifiedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if valid_from is not None and now < valid_from:
        return CheckOutcome(
            passed=False,
            detail=f"not valid until {credential['validFrom']}",
            evidence=evidence,
        )
    if valid_until is not None and now > valid_until:
        return CheckOutcome(
            passed=False,
            detail=f"expired on {credential['validUntil']}",
            evidence=evidence,
        )
    if valid_from is None and valid_until is None:
        return CheckOutcome(
            passed=True, detail="credential states no validity period", evidence=evidence
        )
    return CheckOutcome(
        passed=True,
        detail=(
            f"inside its validity period "
            f"({credential.get('validFrom', 'unbounded')} to "
            f"{credential.get('validUntil', 'unbounded')})"
        ),
        evidence=evidence,
    )


def check_status(credential: dict[str, Any], resolver: Resolver) -> CheckOutcome:
    """Check whether a credential has been revoked or suspended since issue.

    A signature says what was true when the credential was made. Only the status list
    says whether it is still true now, which is why an unchecked status is a hole
    rather than a detail.

    Args:
        credential: The credential to check.
        resolver: Used to retrieve the published status list.

    Returns:
        The outcome. A credential with no status member passes, since an issuer that
        publishes no status list has simply not taken on the ability to withdraw.
    """
    entry = credential.get("credentialStatus")
    if entry is None:
        return CheckOutcome(passed=True, detail="issuer publishes no status list")
    if not isinstance(entry, dict):
        return CheckOutcome(passed=False, detail="credentialStatus is malformed")

    list_url = entry.get("statusListCredential")
    purpose = entry.get("statusPurpose", "revocation")
    raw_index = entry.get("statusListIndex")
    if not isinstance(list_url, str) or raw_index is None:
        return CheckOutcome(passed=False, detail="credentialStatus is incomplete")
    try:
        index = int(raw_index)
    except (TypeError, ValueError):
        return CheckOutcome(passed=False, detail=f"statusListIndex {raw_index!r} is not an integer")

    # `retrieve`, not `fetch`: a stapled status list is a stale status list, and a
    # holder who kept a copy from before its revocation would replay it forever.
    status_credential = resolver.retrieve(list_url)
    if status_credential is None:
        return CheckOutcome(
            passed=False,
            detail=f"status list {list_url} could not be retrieved",
            evidence={"statusListCredential": list_url},
        )

    # The status list is itself a credential, so it gets verified too. Otherwise
    # anyone able to substitute it could quietly un-revoke a withdrawn certificate.
    proof_outcome, _ = check_proof(status_credential, resolver)
    if not proof_outcome.passed:
        return CheckOutcome(
            passed=False,
            detail=f"status list did not verify: {proof_outcome.detail}",
            evidence={"statusListCredential": list_url},
        )

    subject = status_credential.get("credentialSubject", {})
    if not isinstance(subject, dict) or subject.get("statusPurpose") != purpose:
        return CheckOutcome(
            passed=False,
            detail=(
                f"credential points at a {subject.get('statusPurpose')!r} list but "
                f"declares purpose {purpose!r}"
            ),
            evidence={"statusListCredential": list_url},
        )

    try:
        marked = read_status(subject.get("encodedList", ""), index)
    except ValueError as error:
        return CheckOutcome(passed=False, detail=f"status list is unreadable: {error}")

    evidence = {
        "statusListCredential": list_url,
        "statusListIndex": index,
        "statusPurpose": purpose,
        "marked": marked,
    }
    if marked:
        return CheckOutcome(
            passed=False,
            detail=f"credential is marked as {purpose} at position {index} of the list",
            evidence=evidence,
        )
    return CheckOutcome(
        passed=True,
        detail=f"not marked for {purpose} at position {index} of the published list",
        evidence=evidence,
    )
