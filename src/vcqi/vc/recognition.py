"""Chain traversal from an unknown issuer up to a trust anchor.

This implements the discovery algorithm of the Recognized Entities specification.

The situation it solves is the one a market surveillance authority is actually in. A
certificate arrives from an organisation it has never heard of. Checking the signature
proves only that the document has not been altered since whoever made it made it; it
says nothing about whether that party had any business issuing it. The authority has to
get from an unknown identifier to something it already trusts, without a bilateral
agreement and without a central registry it has to be told about in advance.

The specification gives two ways to do that.

**Credential-based discovery** follows the ``recognizedIn`` member on the issuer, which
points at the recognition credential the issuer claims to appear in. The verifier
fetches it, verifies it as a credential in its own right, confirms the issuer really is
listed there, and then asks the same question about *that* credential's issuer. Each
step moves one level up the hierarchy, and the loop ends when it reaches an identifier
the verifier already trusts.

**Identifier-based discovery** is the fallback for an issuer that does not carry a
pointer. The verifier resolves the issuer identifier, looks for a service typed as both
``WhoisService`` and ``PathService``, and retrieves a presentation in which the issuer
describes itself. If that presentation contains a recognition credential listing the
issuer, traversal continues from there as before.

Two safeguards matter, because the documents being followed are supplied by the party
being checked: traversal stops at a configured maximum depth, and a credential already
seen is never followed twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from vcqi.vc.checks import (
    CheckOutcome,
    check_proof,
    check_status,
    check_validity_period,
    credential_types,
    issuer_id,
)
from vcqi.vc.resolver import Resolver

__all__ = ["RecognitionHop", "RecognitionChain", "discover_recognition", "DEFAULT_MAX_DEPTH"]

#: How many recognition credentials a verifier is willing to follow. Real hierarchies
#: are shallow; a deep chain is a sign of a loop or of someone spending a verifier's
#: time on its behalf.
DEFAULT_MAX_DEPTH = 5


@dataclass(frozen=True)
class RecognitionHop:
    """One step from a credential to the recognition credential above it.

    Attributes:
        credential_id: Identifier of the credential this step started from.
        credential_type: Its most specific type.
        issuer: Identifier of the issuer whose standing is in question.
        recognized_in: The recognition credential the issuer pointed at, or None when
            the pointer was found by resolving the issuer identifier instead.
        discovery: Which mechanism was used, ``credential`` or ``identifier``.
        entity: The RecognizedEntity entry naming the issuer, when one was found.
        actions: What that entry recognises the issuer to do.
        checks: The checks applied to the recognition credential at this step.
    """

    credential_id: str
    credential_type: str
    issuer: str
    recognized_in: str | None
    discovery: str
    entity: dict[str, Any] | None
    actions: list[dict[str, Any]]
    checks: list[tuple[str, CheckOutcome]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        """Return the step as a JSON-compatible dictionary.

        Returns:
            The step, with each check flattened for display.
        """
        return {
            "credentialId": self.credential_id,
            "credentialType": self.credential_type,
            "issuer": self.issuer,
            "recognizedIn": self.recognized_in,
            "discovery": self.discovery,
            "entity": self.entity,
            "actions": self.actions,
            "checks": [
                {"name": name, "passed": outcome.passed, "detail": outcome.detail}
                for name, outcome in self.checks
            ],
        }


@dataclass
class RecognitionChain:
    """The outcome of trying to reach a trust anchor from a credential.

    Attributes:
        hops: The steps taken, in the order they were taken.
        anchor: The trusted identifier the chain reached, or None on failure.
        succeeded: Whether an anchor was reached with every check passing.
        error: Why traversal stopped, when it did not succeed.
        credentials: The recognition credentials that were fetched, by identifier.
    """

    hops: list[RecognitionHop] = field(default_factory=list)
    anchor: str | None = None
    succeeded: bool = False
    error: str | None = None
    credentials: dict[str, dict[str, Any]] = field(default_factory=dict)

    def entity_for(self, issuer: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """Return what the chain recognises one issuer to be and to do.

        Args:
            issuer: Identifier of the issuer to look up.

        Returns:
            A tuple of the RecognizedEntity entry and its recognised actions, both
            empty when the chain never established anything about that issuer.
        """
        for hop in self.hops:
            if hop.issuer == issuer and hop.entity is not None:
                return hop.entity, hop.actions
        return None, []

    def to_json(self) -> dict[str, Any]:
        """Return the chain as a JSON-compatible dictionary.

        Returns:
            The outcome, the anchor reached and every step taken.
        """
        return {
            "succeeded": self.succeeded,
            "anchor": self.anchor,
            "error": self.error,
            "depth": len(self.hops),
            "hops": [hop.to_json() for hop in self.hops],
        }


def _most_specific_type(credential: dict[str, Any]) -> str:
    """Return the type of a credential that says what it actually is.

    Args:
        credential: The credential to inspect.

    Returns:
        The first type other than VerifiableCredential, or that name when there is
        no other.
    """
    types = [name for name in credential_types(credential) if name != "VerifiableCredential"]
    return types[0] if types else "VerifiableCredential"


def _recognized_in(credential: dict[str, Any]) -> str | None:
    """Return the recognition credential the issuer of a credential points at.

    Args:
        credential: The credential to inspect.

    Returns:
        The URL, or None when the issuer carries no pointer.
    """
    issuer = credential.get("issuer")
    if not isinstance(issuer, dict):
        return None
    reference = issuer.get("recognizedIn")
    if not isinstance(reference, dict):
        return None
    target = reference.get("id")
    return target if isinstance(target, str) else None


def _find_entity(
    recognition: dict[str, Any], issuer: str
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Find an issuer among the entities a recognition credential lists.

    Args:
        recognition: The recognition credential.
        issuer: Identifier of the issuer to look for.

    Returns:
        The matching entry and its recognised actions, both empty when the issuer is
        not listed. Being pointed at by a credential is not the same as appearing in
        it, and only the second one counts.
    """
    subjects = recognition.get("credentialSubject")
    if isinstance(subjects, dict):
        subjects = [subjects]
    if not isinstance(subjects, list):
        return None, []

    for entry in subjects:
        if not isinstance(entry, dict) or entry.get("id") != issuer:
            continue
        actions = entry.get("recognizedTo", [])
        if isinstance(actions, dict):
            actions = [actions]
        if not isinstance(actions, list):
            actions = []
        return entry, [item for item in actions if isinstance(item, dict)]
    return None, []


def _discover_via_identifier(
    issuer: str, resolver: Resolver
) -> tuple[dict[str, Any] | None, str | None]:
    """Try to find a recognition credential by resolving the issuer identifier.

    Args:
        issuer: Identifier of the issuer.
        resolver: Used to resolve the identifier and fetch the presentation.

    Returns:
        A tuple of the recognition credential and its identifier, both None when
        nothing usable was published.
    """
    document = resolver.resolve_did_document(issuer)
    if document is None:
        return None, None

    endpoint: str | None = None
    for service in document.get("service", []):
        if not isinstance(service, dict):
            continue
        types = service.get("type", [])
        types = [types] if isinstance(types, str) else types
        if "WhoisService" in types and "PathService" in types:
            candidate = service.get("serviceEndpoint")
            if isinstance(candidate, str):
                endpoint = candidate
                break
    if endpoint is None:
        return None, None

    presentation = resolver.fetch(endpoint)
    if not isinstance(presentation, dict):
        return None, None

    held = presentation.get("verifiableCredential", [])
    if isinstance(held, dict):
        held = [held]
    for credential in held:
        if not isinstance(credential, dict):
            continue
        if "RecognizedEntityCredential" not in credential_types(credential):
            continue
        entity, _ = _find_entity(credential, issuer)
        if entity is not None:
            identifier = credential.get("id")
            return credential, identifier if isinstance(identifier, str) else endpoint
    return None, None


def discover_recognition(
    credential: dict[str, Any],
    *,
    resolver: Resolver,
    trusted_issuers: frozenset[str] | set[str],
    now: datetime,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> RecognitionChain:
    """Walk from a credential up to a trust anchor.

    Args:
        credential: The credential whose issuer is unknown to the verifier.
        resolver: Used to fetch recognition credentials and resolve identifiers.
        trusted_issuers: Identifiers the verifier trusts without further evidence.
        now: The instant to evaluate validity periods against.
        max_depth: How many recognition credentials to follow before giving up.

    Returns:
        The chain, successful or not. A failed chain still carries every step it
        managed, because knowing where a chain broke is more useful than knowing only
        that it did.
    """
    chain = RecognitionChain()
    current = credential
    seen: set[str] = set()

    while True:
        issuer = issuer_id(current)
        if issuer is None:
            chain.error = "credential names no issuer"
            return chain

        if issuer in trusted_issuers:
            chain.anchor = issuer
            chain.succeeded = True
            return chain

        if len(chain.hops) >= max_depth:
            chain.error = (
                f"gave up after following {max_depth} recognition credentials without "
                f"reaching a trusted identifier"
            )
            return chain

        current_id = current.get("id")
        current_id = current_id if isinstance(current_id, str) else "(unidentified)"

        pointer = _recognized_in(current)
        discovery = "credential"
        recognition: dict[str, Any] | None = None

        if pointer is not None:
            recognition = resolver.fetch(pointer)
            if recognition is None:
                chain.hops.append(
                    RecognitionHop(
                        credential_id=current_id,
                        credential_type=_most_specific_type(current),
                        issuer=issuer,
                        recognized_in=pointer,
                        discovery=discovery,
                        entity=None,
                        actions=[],
                        checks=[
                            (
                                "retrieval",
                                CheckOutcome(False, f"{pointer} could not be retrieved"),
                            )
                        ],
                    )
                )
                chain.error = f"the recognition credential at {pointer} could not be retrieved"
                return chain
        else:
            # No pointer, so fall back to asking the issuer about itself.
            recognition, pointer = _discover_via_identifier(issuer, resolver)
            discovery = "identifier"
            if recognition is None:
                chain.hops.append(
                    RecognitionHop(
                        credential_id=current_id,
                        credential_type=_most_specific_type(current),
                        issuer=issuer,
                        recognized_in=None,
                        discovery=discovery,
                        entity=None,
                        actions=[],
                        checks=[
                            (
                                "discovery",
                                CheckOutcome(
                                    False,
                                    f"{issuer} is not trusted, carries no recognizedIn "
                                    f"pointer, and publishes no usable whois service",
                                ),
                            )
                        ],
                    )
                )
                chain.error = f"no route from {issuer} towards a trusted identifier"
                return chain

        recognition_id = recognition.get("id")
        recognition_id = recognition_id if isinstance(recognition_id, str) else pointer or ""

        if recognition_id in seen:
            chain.error = f"recognition chain loops back to {recognition_id}"
            return chain
        seen.add(recognition_id)

        checks: list[tuple[str, CheckOutcome]] = []

        type_ok = "RecognizedEntityCredential" in credential_types(recognition)
        checks.append(
            (
                "type",
                CheckOutcome(
                    passed=type_ok,
                    detail=(
                        "the document pointed at is a RecognizedEntityCredential"
                        if type_ok
                        else "the document pointed at is not a RecognizedEntityCredential"
                    ),
                ),
            )
        )

        proof_outcome, _ = check_proof(recognition, resolver)
        checks.append(("proof", proof_outcome))
        checks.append(("validity", check_validity_period(recognition, now)))
        checks.append(("status", check_status(recognition, resolver)))

        entity, actions = _find_entity(recognition, issuer)
        checks.append(
            (
                "membership",
                CheckOutcome(
                    passed=entity is not None,
                    detail=(
                        f"{issuer} is listed as a recognized entity"
                        if entity is not None
                        else f"{issuer} does not appear in the credential it points at"
                    ),
                    evidence={"recognizedActions": [a.get("action") for a in actions]},
                ),
            )
        )

        hop = RecognitionHop(
            credential_id=current_id,
            credential_type=_most_specific_type(current),
            issuer=issuer,
            recognized_in=recognition_id,
            discovery=discovery,
            entity=entity,
            actions=actions,
            checks=checks,
        )
        chain.hops.append(hop)
        chain.credentials[recognition_id] = recognition

        failed = [name for name, outcome in checks if not outcome.passed]
        if failed:
            chain.error = (
                f"recognition of {issuer} through {recognition_id} failed: "
                + "; ".join(
                    outcome.detail for name, outcome in checks if not outcome.passed
                )
            )
            return chain

        current = recognition
