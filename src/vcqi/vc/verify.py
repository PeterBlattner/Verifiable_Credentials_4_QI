"""The verification pipeline: everything a recipient checks, in order.

Verification here is deliberately more than "does the signature check out". A signature
answers one question, and it is not the question a laboratory receiving a certificate
actually has. The full sequence is:

1. is the document shaped like a credential at all;
2. was it signed by the key its issuer publishes, for the purpose of asserting claims;
3. is it inside its validity period;
4. has it been revoked or suspended since it was issued;
5. does its issuer connect, through recognition, to something the verifier trusts;
6. does that recognition actually cover issuing this kind of document, at the time it
   was issued;
7. does the document validate against the schema that recognition names;
8. does what it claims fall inside the capability it was issued under, and if it claims
   the CIPM MRA logo, is that claim justified;
9. does its traceability chain hold, all the way down to an institute that realises the
   unit;
10. is the stated uncertainty consistent with the budget offered to support it.

Steps 1 to 4 are generic. Step 5 is the Recognized Entities contribution. Steps 6 to 10
are where the quality infrastructure lives, and they are the ones that turn a document
that merely verifies into a document a metrologist can rely on.

Every step returns a structured result rather than a boolean, so the interface can show
which check decided the outcome. A step that cannot be evaluated is reported as skipped,
never silently passed.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from jsonschema import Draft202012Validator

from vcqi.crypto.jcs import canonicalize
from vcqi.crypto.multibase import verify_digest_multibase
from vcqi.domain.scope import (
    DeclaredCapability,
    MeasurementClaim,
    UncertaintyFloor,
    evaluate_scope,
)
from vcqi.domain.dcc import parse_dcc_administrative, parse_dcc_result
from vcqi.domain.uncertainty import parse_input_quantities
from vcqi.vc.model import artefact_payload
from vcqi.vc.checks import (
    CheckOutcome,
    check_proof,
    check_shape,
    check_status,
    check_validity_period,
    credential_types,
    issuer_id,
    parse_timestamp,
)
from vcqi.vc.recognition import DEFAULT_MAX_DEPTH, RecognitionChain, discover_recognition
from vcqi.vc.resolver import DocumentStore, Resolver

__all__ = ["Step", "VerificationReport", "verify_credential", "REQUIRED_ACTIONS"]

#: What an issuer has to be recognised to do in order to issue each kind of document.
REQUIRED_ACTIONS = {
    "CalibrationCertificateCredential": "issue",
    "TestReportCredential": "issue",
    "ProductConformityCredential": "issue",
    "RecognizedEntityCredential": "accredit",
}

#: How far a verifier follows traceability before stopping. The chains in this
#: demonstration are three deep; a real one is rarely more than five.
MAX_TRACEABILITY_DEPTH = 5

PASS, FAIL, WARN, SKIP = "pass", "fail", "warn", "skip"


@dataclass
class Step:
    """One step of the verification pipeline.

    Attributes:
        id: Stable identifier, so the interface and the tests can refer to a step
            without matching on its wording.
        title: Short description of what was checked.
        status: One of pass, fail, warn or skip.
        detail: Human-readable explanation of the outcome.
        evidence: Structured supporting data.
        children: Nested steps, used where one step contains a sequence of its own,
            such as each hop of a recognition chain.
    """

    id: str
    title: str
    status: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)
    children: list[Step] = field(default_factory=list)

    @classmethod
    def from_outcome(
        cls, step_id: str, title: str, outcome: CheckOutcome
    ) -> Step:
        """Build a step from a generic check outcome.

        Args:
            step_id: Stable identifier for the step.
            title: Short description of what was checked.
            outcome: The outcome to wrap.

        Returns:
            The step.
        """
        return cls(
            id=step_id,
            title=title,
            status=PASS if outcome.passed else FAIL,
            detail=outcome.detail,
            evidence=outcome.evidence,
        )

    def to_json(self) -> dict[str, Any]:
        """Return the step as a JSON-compatible dictionary.

        Returns:
            The step and, recursively, its children.
        """
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "evidence": self.evidence,
            "children": [child.to_json() for child in self.children],
        }


@dataclass
class VerificationReport:
    """Everything a verifier concluded about one credential.

    Attributes:
        credential_id: Identifier of the credential that was checked.
        credential_type: Its most specific type.
        issuer: Identifier of its issuer.
        steps: The pipeline steps, in the order they were run.
        fetches: Every document retrieval the verifier made.
        verified_at: The instant verification was evaluated against.
    """

    credential_id: str
    credential_type: str
    issuer: str | None
    steps: list[Step] = field(default_factory=list)
    fetches: list[dict[str, Any]] = field(default_factory=list)
    verified_at: str = ""

    @property
    def failures(self) -> list[Step]:
        """Return every step that failed, including nested ones.

        Returns:
            The failing steps, outermost first.
        """

        def walk(steps: list[Step]) -> list[Step]:
            found: list[Step] = []
            for step in steps:
                if step.status == FAIL:
                    found.append(step)
                found.extend(walk(step.children))
            return found

        return walk(self.steps)

    @property
    def outcome(self) -> str:
        """Return the overall outcome.

        Returns:
            ``verified`` when nothing failed, ``rejected`` otherwise.
        """
        return "rejected" if any(step.status == FAIL for step in self.steps) else "verified"

    def to_json(self) -> dict[str, Any]:
        """Return the report as a JSON-compatible dictionary.

        Returns:
            The outcome, every step, and the retrieval log.
        """
        return {
            "credentialId": self.credential_id,
            "credentialType": self.credential_type,
            "issuer": self.issuer,
            "outcome": self.outcome,
            "verifiedAt": self.verified_at,
            "steps": [step.to_json() for step in self.steps],
            "fetches": self.fetches,
            "failureSummary": [
                {"id": step.id, "title": step.title, "detail": step.detail}
                for step in self.failures
            ],
        }


def _most_specific_type(credential: dict[str, Any]) -> str:
    """Return the type that says what a credential actually is.

    Args:
        credential: The credential to inspect.

    Returns:
        The first type other than VerifiableCredential.
    """
    types = [name for name in credential_types(credential) if name != "VerifiableCredential"]
    return types[0] if types else "VerifiableCredential"


def _payload(credential: dict[str, Any]) -> dict[str, Any]:
    """Return the domain-specific part of a credential subject.

    The three domain credential types each wrap their content in a differently named
    member. This returns whichever one is present so the rest of the pipeline can be
    written once.

    Args:
        credential: The credential to inspect.

    Returns:
        The calibration, testing or conformity object, empty when there is none.
    """
    subject = credential.get("credentialSubject")
    if not isinstance(subject, dict):
        return {}
    for member in ("calibration", "testing", "conformity"):
        value = subject.get(member)
        if isinstance(value, dict):
            return value
    return {}


def _capability_reference(credential: dict[str, Any]) -> dict[str, Any] | None:
    """Return the capability a credential claims to have been issued under.

    Args:
        credential: The credential to inspect.

    Returns:
        The reference object, or None when the credential claims none.
    """
    reference = _payload(credential).get("capabilityReference")
    return reference if isinstance(reference, dict) else None


def _capability_from_document(document: dict[str, Any]) -> DeclaredCapability | None:
    """Build a declared capability from a retrieved registry entry.

    The verifier deliberately reads the capability out of the document it fetched from
    the registry, rather than from its own copy of the domain model. A verifier that
    consulted its own idea of what a CMC says would not be checking anything.

    Args:
        document: The retrieved CMC entry or accreditation scope.

    Returns:
        The capability, or None when the document states no numeric capability.
    """
    floor_source = document.get("expandedUncertainty") or document.get(
        "bestMeasurementCapability"
    )
    required = ("measurand", "unit", "rangeMinimum", "rangeMaximum")
    if not isinstance(floor_source, dict) or any(name not in document for name in required):
        return None
    try:
        floor = UncertaintyFloor(
            absolute=float(floor_source["absoluteTerm"]),
            relative=float(floor_source["relativeTerm"]),
            coverage_factor=float(floor_source.get("coverageFactor", 2.0)),
        )
        return DeclaredCapability(
            label=str(document.get("identifier", document.get("id", "capability"))),
            measurand=str(document["measurand"]),
            unit=str(document["unit"]),
            range_minimum=float(document["rangeMinimum"]),
            range_maximum=float(document["rangeMaximum"]),
            conditions=str(document.get("conditions", "")),
            uncertainty_floor=floor,
        )
    except (KeyError, TypeError, ValueError):
        return None


def _first_result(credential: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first calibration result of a certificate.

    Args:
        credential: The credential to inspect.

    Returns:
        The result object, or None when the credential reports none.
    """
    results = _payload(credential).get("results")
    if isinstance(results, list) and results and isinstance(results[0], dict):
        return results[0]
    return None


def _step_recognition(chain: RecognitionChain) -> Step:
    """Render a recognition chain as a step with one child per hop.

    Args:
        chain: The traversal outcome.

    Returns:
        The step.
    """
    children = [
        Step(
            id=f"recognition.hop.{index}",
            title=(
                f"{hop.issuer} is recognised in {hop.recognized_in}"
                if hop.recognized_in
                else f"{hop.issuer} could not be placed"
            ),
            status=PASS if all(outcome.passed for _, outcome in hop.checks) else FAIL,
            detail="; ".join(outcome.detail for _, outcome in hop.checks),
            evidence=hop.to_json(),
        )
        for index, hop in enumerate(chain.hops, start=1)
    ]

    if chain.succeeded:
        route = " -> ".join(hop.issuer for hop in chain.hops) or "(direct)"
        detail = (
            f"reached the trusted identifier {chain.anchor} "
            f"after {len(chain.hops)} recognition step(s): {route} -> {chain.anchor}"
        )
        status = PASS
    else:
        detail = chain.error or "no route to a trusted identifier"
        status = FAIL

    return Step(
        id="recognition",
        title="Issuer connects to a trusted identifier",
        status=status,
        detail=detail,
        evidence={"chain": chain.to_json()},
        children=children,
    )


def _step_action(
    credential: dict[str, Any], chain: RecognitionChain
) -> tuple[Step, dict[str, Any] | None]:
    """Check that the recognition actually covers issuing this document.

    Reaching a trust anchor is not the end of the question. An accreditation body may be
    recognised to accredit without being recognised to issue calibration certificates,
    and a laboratory accredited for testing is not thereby accredited for calibration.
    The recognised action, and the period it was recognised for, both have to match.

    Args:
        credential: The credential being verified.
        chain: The recognition chain established for its issuer.

    Returns:
        The step, and the matched action when one was found.
    """
    issuer = issuer_id(credential) or ""
    credential_type = _most_specific_type(credential)
    required = REQUIRED_ACTIONS.get(credential_type)

    if not chain.succeeded:
        return (
            Step(
                id="action",
                title="Recognition covers this kind of document",
                status=SKIP,
                detail="not evaluated, because no recognition chain was established",
            ),
            None,
        )
    if required is None:
        return (
            Step(
                id="action",
                title="Recognition covers this kind of document",
                status=SKIP,
                detail=f"no action requirement is defined for {credential_type}",
            ),
            None,
        )
    if not chain.hops:
        return (
            Step(
                id="action",
                title="Recognition covers this kind of document",
                status=PASS,
                detail=f"{issuer} is a trust anchor, so no recognised action is required",
            ),
            None,
        )

    _, actions = chain.entity_for(issuer)
    candidates = [action for action in actions if action.get("action") == required]
    if not candidates:
        offered = sorted({str(action.get("action")) for action in actions})
        return (
            Step(
                id="action",
                title="Recognition covers this kind of document",
                status=FAIL,
                detail=(
                    f"{issuer} is recognised to {', '.join(offered) or 'do nothing'}, "
                    f"but issuing a {credential_type} requires being recognised to "
                    f"{required}"
                ),
                evidence={"required": required, "offered": offered},
            ),
            None,
        )

    # When the certificate names the capability it was issued under, the recognised
    # action for that specific capability is the one that has to authorise it.
    reference = _capability_reference(credential)
    matched = candidates[0]
    if reference is not None:
        for action in candidates:
            capability = action.get("capabilityReference")
            if isinstance(capability, dict) and capability.get("id") == reference.get("id"):
                matched = action
                break
        else:
            covered = [
                str(action.get("capabilityReference", {}).get("identifier"))
                for action in candidates
            ]
            return (
                Step(
                    id="action",
                    title="Recognition covers this kind of document",
                    status=FAIL,
                    detail=(
                        f"the certificate claims to have been issued under "
                        f"{reference.get('identifier', reference.get('id'))}, which is "
                        f"not among the capabilities {issuer} is recognised for "
                        f"({', '.join(covered)})"
                    ),
                    evidence={"claimed": reference, "recognised": covered},
                ),
                None,
            )

    issued_at = parse_timestamp(credential.get("validFrom"))
    action_from = parse_timestamp(matched.get("validFrom"))
    action_until = parse_timestamp(matched.get("validUntil"))
    if issued_at is not None:
        if action_from is not None and issued_at < action_from:
            return (
                Step(
                    id="action",
                    title="Recognition covers this kind of document",
                    status=FAIL,
                    detail=(
                        f"the document was issued on {credential.get('validFrom')}, "
                        f"before the recognition began on {matched.get('validFrom')}"
                    ),
                    evidence={"action": matched},
                ),
                None,
            )
        if action_until is not None and issued_at > action_until:
            return (
                Step(
                    id="action",
                    title="Recognition covers this kind of document",
                    status=FAIL,
                    detail=(
                        f"the document was issued on {credential.get('validFrom')}, "
                        f"after the recognition ended on {matched.get('validUntil')}"
                    ),
                    evidence={"action": matched},
                ),
                None,
            )

    return (
        Step(
            id="action",
            title="Recognition covers this kind of document",
            status=PASS,
            detail=(
                f"{issuer} was recognised to {required} under "
                f"{matched.get('capabilityReference', {}).get('identifier', 'this recognition')} "
                f"when the document was issued"
            ),
            evidence={"action": matched},
        ),
        matched,
    )


def _step_output_validation(
    credential: dict[str, Any], action: dict[str, Any] | None, resolver: Resolver
) -> Step:
    """Validate the credential against the schema its recognition names.

    Args:
        credential: The credential being verified.
        action: The recognised action that authorised it, if one was matched.
        resolver: Used to retrieve the schema.

    Returns:
        The step.
    """
    if action is None:
        return Step(
            id="output-validation",
            title="Document matches the schema its recognition names",
            status=SKIP,
            detail="not evaluated, because no recognised action was matched",
        )

    reference = action.get("outputValidation")
    if not isinstance(reference, dict) or not isinstance(reference.get("id"), str):
        return Step(
            id="output-validation",
            title="Document matches the schema its recognition names",
            status=SKIP,
            detail="the recognition names no output schema",
        )

    schema_url = reference["id"]
    schema = resolver.fetch(schema_url)
    if schema is None:
        return Step(
            id="output-validation",
            title="Document matches the schema its recognition names",
            status=FAIL,
            detail=f"the schema at {schema_url} could not be retrieved",
            evidence={"schema": schema_url},
        )

    expected_digest = reference.get("digestMultibase")
    if isinstance(expected_digest, str):
        if not verify_digest_multibase(canonicalize(schema), expected_digest):
            return Step(
                id="output-validation",
                title="Document matches the schema its recognition names",
                status=FAIL,
                detail=(
                    f"the schema at {schema_url} does not match the digest recorded in "
                    f"the recognition, so it has been changed since recognition was granted"
                ),
                evidence={"schema": schema_url, "expectedDigest": expected_digest},
            )

    errors = sorted(
        Draft202012Validator(schema).iter_errors(credential), key=lambda e: list(e.path)
    )
    if errors:
        return Step(
            id="output-validation",
            title="Document matches the schema its recognition names",
            status=FAIL,
            detail="; ".join(
                f"{'/'.join(str(part) for part in error.path) or 'document'}: {error.message}"
                for error in errors[:4]
            ),
            evidence={"schema": schema_url, "errorCount": len(errors)},
        )

    return Step(
        id="output-validation",
        title="Document matches the schema its recognition names",
        status=PASS,
        detail=(
            f"validates against {schema_url}, whose content digest matches the one "
            f"recorded in the recognition"
        ),
        evidence={"schema": schema_url},
    )


def _step_scope(credential: dict[str, Any], resolver: Resolver) -> Step:
    """Decide whether what the document claims falls inside its declared capability.

    This is the check that has no counterpart in a general purpose credential wallet,
    and the one a metrologist cares about most. A certificate can be perfectly signed by
    a genuinely recognised institute and still claim something that institute has never
    demonstrated it can do.

    Args:
        credential: The credential being verified.
        resolver: Used to retrieve the registry entry.

    Returns:
        The step, with one child per condition evaluated.
    """
    reference = _capability_reference(credential)
    if reference is None or not isinstance(reference.get("id"), str):
        return Step(
            id="scope",
            title="Claim falls inside the declared capability",
            status=SKIP,
            detail="the document names no capability to check against",
        )

    document = resolver.fetch(reference["id"])
    if document is None:
        return Step(
            id="scope",
            title="Claim falls inside the declared capability",
            status=FAIL,
            detail=f"the capability at {reference['id']} could not be retrieved",
            evidence={"capability": reference},
        )

    capability = _capability_from_document(document)
    result = _first_result(credential)

    if capability is None or result is None:
        return _step_scope_by_method(credential, document, reference)

    try:
        claim = MeasurementClaim(
            measurand=str(_payload(credential).get("measurand")),
            unit=str(result.get("unit")),
            value=float(result["value"]),
            expanded_uncertainty=float(result["expandedUncertainty"]),
            coverage_factor=float(result["coverageFactor"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        return Step(
            id="scope",
            title="Claim falls inside the declared capability",
            status=FAIL,
            detail=f"the reported result could not be read: {error}",
            evidence={"capability": reference},
        )

    verdict = evaluate_scope(capability, claim)
    children = [
        Step(
            id=f"scope.{check.key}",
            title=check.title,
            status=PASS if check.passed else FAIL,
            detail=check.detail,
        )
        for check in verdict.checks
    ]

    return Step(
        id="scope",
        title="Claim falls inside the declared capability",
        status=PASS if verdict.within_scope else FAIL,
        detail=(
            f"the reported result is inside {capability.label}"
            if verdict.within_scope
            else f"the reported result is outside {capability.label}: "
            + "; ".join(check.detail for check in verdict.failures)
        ),
        evidence={"capability": reference, "verdict": verdict.to_json()},
        children=children,
    )


def _step_scope_by_method(
    credential: dict[str, Any], document: dict[str, Any], reference: dict[str, Any]
) -> Step:
    """Check a scope that lists methods rather than a measurand and a range.

    Testing and certification scopes do not state an uncertainty floor. What bounds them
    is the list of standards they cover, so the check is whether the standard the
    document was issued against appears in that list.

    Args:
        credential: The credential being verified.
        document: The retrieved accreditation scope.
        reference: The capability reference from the credential.

    Returns:
        The step.
    """
    standard = _payload(credential).get("standard")
    methods = document.get("methods")
    if not isinstance(standard, str) or not isinstance(methods, list):
        return Step(
            id="scope",
            title="Claim falls inside the declared capability",
            status=SKIP,
            detail="the capability states neither a numeric range nor a list of methods",
            evidence={"capability": reference},
        )

    covered = any(isinstance(method, str) and standard in method for method in methods)
    return Step(
        id="scope",
        title="Claim falls inside the declared capability",
        status=PASS if covered else FAIL,
        detail=(
            f"{standard} is covered by {document.get('identifier')}"
            if covered
            else f"{standard} is not among the methods {document.get('identifier')} covers"
        ),
        evidence={"capability": reference, "standard": standard, "methods": methods},
    )


def _step_mra_logo(credential: dict[str, Any], scope_step: Step) -> Step:
    """Decide whether a claim to CIPM MRA coverage is justified.

    Under the arrangement, an institute may apply the logo only to results covered by a
    published CMC. Today that is a matter of institutional discipline, checked by
    nobody in particular at the point of use. Here it is decided from the certificate
    and the registry, by whoever received the document.

    Args:
        credential: The credential being verified.
        scope_step: The outcome of the capability check.

    Returns:
        The step.
    """
    payload = _payload(credential)
    asserted = payload.get("mraLogoAsserted")

    if asserted is None:
        return Step(
            id="mra-logo",
            title="CIPM MRA logo is used legitimately",
            status=SKIP,
            detail="the document makes no claim to CIPM MRA coverage",
        )
    if not asserted:
        return Step(
            id="mra-logo",
            title="CIPM MRA logo is used legitimately",
            status=PASS,
            detail=(
                "the document does not claim CIPM MRA coverage, which is correct for a "
                "document that is not a certificate of a national metrology institute"
            ),
        )

    reference = _capability_reference(credential) or {}
    if reference.get("type") != "KcdbCmcEntry":
        return Step(
            id="mra-logo",
            title="CIPM MRA logo is used legitimately",
            status=FAIL,
            detail=(
                "the document claims CIPM MRA coverage but is issued under "
                f"{reference.get('type', 'no capability')} rather than a published CMC"
            ),
            evidence={"capability": reference},
        )
    if scope_step.status != PASS:
        return Step(
            id="mra-logo",
            title="CIPM MRA logo is used legitimately",
            status=FAIL,
            detail=(
                "the document claims CIPM MRA coverage, but the result it reports is "
                f"not covered by {reference.get('identifier')}. The calibration may "
                "still be sound; what is not supported is the claim of international "
                "recognition."
            ),
            evidence={"capability": reference},
        )
    return Step(
        id="mra-logo",
        title="CIPM MRA logo is used legitimately",
        status=PASS,
        detail=(
            f"the reported result is covered by {reference.get('identifier')}, so the "
            f"CIPM MRA logo is justified"
        ),
        evidence={"capability": reference},
    )


def _step_uncertainty(credential: dict[str, Any]) -> Step:
    """Check that the stated uncertainty is consistent with the budget offered for it.

    Two conditions have to hold for the arithmetic on a certificate to make sense: the
    Expanded Uncertainty must be the coverage factor times the Standard Uncertainty, and
    the Standard Uncertainty must be the quadrature sum of the contributions listed.
    Neither is checkable at all unless the budget travels with the result, which is the
    argument for carrying it in the credential.

    Args:
        credential: The credential being verified.

    Returns:
        The step.
    """
    payload = _payload(credential)
    result = _first_result(credential)
    budget = payload.get("uncertaintyBudget")

    if result is None or not isinstance(budget, list) or not budget:
        return Step(
            id="uncertainty",
            title="Stated uncertainty is consistent with its budget",
            status=SKIP,
            detail="the document reports no uncertainty budget",
        )

    try:
        standard = float(result["standardUncertainty"])
        expanded = float(result["expandedUncertainty"])
        coverage = float(result["coverageFactor"])
        contributions = [float(line["uncertaintyContribution"]) for line in budget]
    except (KeyError, TypeError, ValueError) as error:
        return Step(
            id="uncertainty",
            title="Stated uncertainty is consistent with its budget",
            status=FAIL,
            detail=f"the uncertainty budget could not be read: {error}",
        )

    combined = math.sqrt(sum(value * value for value in contributions))
    children: list[Step] = []

    expected_expanded = coverage * standard
    coverage_ok = math.isclose(expanded, expected_expanded, rel_tol=1e-9, abs_tol=0.0)
    children.append(
        Step(
            id="uncertainty.coverage",
            title="Expanded Uncertainty equals k times the Standard Uncertainty",
            status=PASS if coverage_ok else FAIL,
            detail=(
                f"U = {expanded:.6g} and k * u = {expected_expanded:.6g} "
                f"with k = {coverage:g}"
            ),
        )
    )

    budget_ok = math.isclose(combined, standard, rel_tol=1e-6, abs_tol=0.0)
    children.append(
        Step(
            id="uncertainty.budget",
            title="Standard Uncertainty is the quadrature sum of the contributions",
            status=PASS if budget_ok else FAIL,
            detail=(
                f"u = {standard:.6g} and the quadrature sum of the "
                f"{len(contributions)} contributions is {combined:.6g}"
            ),
        )
    )

    everything_ok = coverage_ok and budget_ok
    return Step(
        id="uncertainty",
        title="Stated uncertainty is consistent with its budget",
        status=PASS if everything_ok else FAIL,
        detail=(
            f"the budget accounts for the stated {result.get('reported')}"
            if everything_ok
            else "the stated uncertainty is not supported by the budget given for it"
        ),
        evidence={
            "standardUncertainty": standard,
            "expandedUncertainty": expanded,
            "coverageFactor": coverage,
            "quadratureSum": combined,
        },
        children=children,
    )


def _traceability_references(credential: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect the credentials this one rests on.

    Args:
        credential: The credential to inspect.

    Returns:
        The references, in the order they appear.
    """
    payload = _payload(credential)
    references: list[dict[str, Any]] = []

    single = payload.get("traceableTo")
    if isinstance(single, dict):
        references.append(single)
    for member in ("equipmentTraceability", "testReports"):
        value = payload.get(member)
        if isinstance(value, list):
            references.extend(item for item in value if isinstance(item, dict))
    return references


def _step_inherited_uncertainty(
    credential: dict[str, Any], parent: dict[str, Any]
) -> Step:
    """Check that a certificate inherited what its parent actually stated.

    A laboratory that quietly enters a smaller figure than its reference certificate
    reports would produce a budget that adds up perfectly and an Expanded Uncertainty
    that is nonetheless too small. The only way to catch it is to compare the inherited
    line against the certificate it names.

    Args:
        credential: The certificate being verified.
        parent: The certificate it declares traceability to.

    Returns:
        The step.
    """
    budget = _payload(credential).get("uncertaintyBudget")
    parent_result = _first_result(parent)
    parent_id = parent.get("id")

    if not isinstance(budget, list) or parent_result is None:
        return Step(
            id="traceability.inherited",
            title="Inherited uncertainty matches the parent certificate",
            status=SKIP,
            detail="there is no budget line to compare against the parent certificate",
        )

    line = next(
        (
            item
            for item in budget
            if isinstance(item, dict) and item.get("source") == parent_id
        ),
        None,
    )
    if line is None:
        return Step(
            id="traceability.inherited",
            title="Inherited uncertainty matches the parent certificate",
            status=WARN,
            detail=(
                f"no budget line names {parent_id} as its source, so what was inherited "
                f"from it cannot be checked"
            ),
        )

    try:
        claimed = float(line["standardUncertainty"])
        parent_expanded = float(parent_result["expandedUncertainty"])
        parent_coverage = float(parent_result["coverageFactor"])
    except (KeyError, TypeError, ValueError) as error:
        return Step(
            id="traceability.inherited",
            title="Inherited uncertainty matches the parent certificate",
            status=FAIL,
            detail=f"the inherited contribution could not be read: {error}",
        )

    expected = parent_expanded / parent_coverage
    matches = math.isclose(claimed, expected, rel_tol=1e-9, abs_tol=0.0)
    return Step(
        id="traceability.inherited",
        title="Inherited uncertainty matches the parent certificate",
        status=PASS if matches else FAIL,
        detail=(
            f"the budget carries u = {claimed:.6g} from {parent_id}, and that "
            f"certificate reports U = {parent_expanded:.6g} at k = {parent_coverage:g}, "
            f"giving u = {expected:.6g}"
        ),
        evidence={"claimed": claimed, "expected": expected, "parent": parent_id},
    )


def _step_traceability(
    credential: dict[str, Any],
    *,
    store: DocumentStore,
    resolver: Resolver,
    now: datetime,
    trusted_issuers: frozenset[str] | set[str],
    max_depth: int,
    depth: int,
    visited: set[str],
) -> Step:
    """Follow what a credential rests on, verifying each document it names.

    Args:
        credential: The credential being verified.
        store: The published documents.
        resolver: Used to retrieve referenced credentials.
        now: The instant to evaluate validity against.
        trusted_issuers: Identifiers the verifier trusts directly.
        max_depth: Recognition depth limit passed down to nested verifications.
        depth: How deep into the traceability chain this call is.
        visited: Identifiers already verified, to stop a cycle.

    Returns:
        The step, with one child per referenced document.
    """
    references = _traceability_references(credential)
    if not references:
        payload = _payload(credential)
        if payload.get("mraLogoAsserted"):
            return Step(
                id="traceability",
                title="Traceability chain holds",
                status=PASS,
                detail=(
                    "the chain ends here: the issuer is a national metrology institute "
                    "realising the unit against its own national standards"
                ),
            )
        return Step(
            id="traceability",
            title="Traceability chain holds",
            status=SKIP,
            detail="the document declares no traceability references",
        )

    if depth >= MAX_TRACEABILITY_DEPTH:
        return Step(
            id="traceability",
            title="Traceability chain holds",
            status=FAIL,
            detail=f"stopped after following {MAX_TRACEABILITY_DEPTH} levels",
        )

    children: list[Step] = []
    for index, reference in enumerate(references, start=1):
        target = reference.get("id")
        if not isinstance(target, str):
            children.append(
                Step(
                    id=f"traceability.{index}",
                    title="Referenced document",
                    status=FAIL,
                    detail="the reference names no identifier",
                )
            )
            continue

        referenced = resolver.fetch(target)
        if referenced is None:
            children.append(
                Step(
                    id=f"traceability.{index}",
                    title=f"Referenced document {target}",
                    status=FAIL,
                    detail=f"{target} could not be retrieved",
                )
            )
            continue

        unsecured = {
            name: value for name, value in referenced.items() if name != "proof"
        }
        expected_digest = reference.get("digestMultibase")
        if isinstance(expected_digest, str) and not verify_digest_multibase(
            canonicalize(unsecured), expected_digest
        ):
            children.append(
                Step(
                    id=f"traceability.{index}",
                    title=f"Referenced document {target}",
                    status=FAIL,
                    detail=(
                        f"{target} does not match the content digest recorded in the "
                        f"reference, so it is not the document that was referenced"
                    ),
                    evidence={"expectedDigest": expected_digest},
                )
            )
            continue

        if target in visited:
            children.append(
                Step(
                    id=f"traceability.{index}",
                    title=f"Referenced document {target}",
                    status=PASS,
                    detail="already verified earlier in this chain",
                )
            )
            continue

        nested = verify_credential(
            referenced,
            store=store,
            now=now,
            trusted_issuers=trusted_issuers,
            max_depth=max_depth,
            resolver=resolver,
            depth=depth + 1,
            visited=visited,
        )
        child = Step(
            id=f"traceability.{index}",
            title=f"{nested.credential_type} {target}",
            status=PASS if nested.outcome == "verified" else FAIL,
            detail=(
                f"verified, issued by {nested.issuer}"
                if nested.outcome == "verified"
                else "; ".join(step.detail for step in nested.failures[:3])
            ),
            evidence={"report": nested.to_json()},
            children=nested.steps,
        )
        if _payload(credential).get("uncertaintyBudget"):
            child.children.append(_step_inherited_uncertainty(credential, referenced))
            child.children.append(_step_shared_inputs(credential, referenced))
            if any(item.status == FAIL for item in child.children[-2:]):
                child.status = FAIL
        children.append(child)

    everything_ok = all(child.status in (PASS, SKIP, WARN) for child in children)
    return Step(
        id="traceability",
        title="Traceability chain holds",
        status=PASS if everything_ok else FAIL,
        detail=(
            f"followed {len(children)} referenced document(s), all of which verify"
            if everything_ok
            else "at least one referenced document did not verify"
        ),
        children=children,
    )


def verify_credential(
    credential: dict[str, Any],
    *,
    store: DocumentStore,
    now: datetime,
    trusted_issuers: frozenset[str] | set[str],
    presented: list[dict[str, Any]] | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
    resolver: Resolver | None = None,
    depth: int = 0,
    visited: set[str] | None = None,
) -> VerificationReport:
    """Run the full verification pipeline over one credential.

    Args:
        credential: The credential to verify.
        store: The published documents the verifier can retrieve.
        now: The instant to evaluate validity periods against.
        trusted_issuers: Identifiers the verifier trusts without further evidence.
        presented: Documents the holder supplied alongside the credential, which the
            resolver prefers over retrieving them.
        max_depth: How many recognition credentials to follow.
        resolver: An existing resolver to reuse, so that a nested verification shares
            one retrieval log with its parent.
        depth: How deep into a traceability chain this call is.
        visited: Identifiers already verified, to stop a cycle.

    Returns:
        The report.
    """
    if resolver is None:
        resolver = Resolver.with_presented(store, presented or [])
    if visited is None:
        visited = set()

    identifier = credential.get("id")
    identifier = identifier if isinstance(identifier, str) else "(unidentified)"
    visited.add(identifier)

    report = VerificationReport(
        credential_id=identifier,
        credential_type=_most_specific_type(credential),
        issuer=issuer_id(credential),
        verified_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    shape = check_shape(credential)
    report.steps.append(Step.from_outcome("shape", "Document is a Verifiable Credential", shape))
    if not shape.passed:
        report.fetches = [record.to_json() for record in resolver.log]
        return report

    proof_outcome, _ = check_proof(credential, resolver)
    report.steps.append(
        Step.from_outcome("proof", "Proof verifies against the published key", proof_outcome)
    )
    report.steps.append(
        Step.from_outcome(
            "validity", "Document is inside its validity period", check_validity_period(credential, now)
        )
    )
    report.steps.append(
        Step.from_outcome(
            "status", "Document has not been revoked or suspended", check_status(credential, resolver)
        )
    )

    chain = discover_recognition(
        credential,
        resolver=resolver,
        trusted_issuers=trusted_issuers,
        now=now,
        max_depth=max_depth,
    )
    report.steps.append(_step_recognition(chain))

    action_step, action = _step_action(credential, chain)
    report.steps.append(action_step)
    report.steps.append(_step_output_validation(credential, action, resolver))

    scope_step = _step_scope(credential, resolver)
    report.steps.append(scope_step)
    report.steps.append(_step_mra_logo(credential, scope_step))
    # The representations sit under the uncertainty step, so the top-level list stays
    # the same eleven checks however many ways the certificate offers its uncertainty.
    uncertainty_step = _step_uncertainty(credential)
    representations_step = _step_representations(credential, resolver)
    uncertainty_step.children.append(representations_step)
    if representations_step.status == FAIL:
        uncertainty_step.status = FAIL
        uncertainty_step.detail = representations_step.detail
    report.steps.append(uncertainty_step)
    report.steps.append(
        _step_traceability(
            credential,
            store=store,
            resolver=resolver,
            now=now,
            trusted_issuers=trusted_issuers,
            max_depth=max_depth,
            depth=depth,
            visited=visited,
        )
    )

    report.fetches = [record.to_json() for record in resolver.log]
    return report


def _representations(credential: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the uncertainty representations a certificate offers.

    Args:
        credential: The credential to inspect.

    Returns:
        The representations, empty when the certificate reports classically only.
    """
    result = _first_result(credential)
    if result is None:
        return []
    value = result.get("uncertaintyRepresentations")
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _representation_bytes(
    representation: dict[str, Any], resolver: Resolver
) -> tuple[bytes | None, str]:
    """Recover the raw payload a representation stands for.

    Args:
        representation: One entry from uncertaintyRepresentations.
        resolver: Used when the payload is published separately.

    Returns:
        The raw bytes and a description of where they came from, the bytes being None
        when the payload could not be obtained.
    """
    inline = representation.get("content")
    if isinstance(inline, str):
        return inline.encode("utf-8"), "carried inside the credential"

    address = representation.get("id")
    if not isinstance(address, str):
        return None, "the representation neither carries content nor names an address"

    document = resolver.fetch(address)
    if document is None:
        return None, f"{address} could not be retrieved"
    payload = artefact_payload(document)
    if payload is None:
        return None, f"{address} is not a readable uncertainty artefact"
    return payload, f"fetched from {address}"


def _reconstruct(unclib_xml: str) -> tuple[float, float]:
    """Recompute a value and its Standard Uncertainty from a dependency representation.

    Done by arithmetic on the transmitted sensitivities rather than by handing the XML
    back to the library, so that the check is independent of the tool that wrote it.

    Args:
        unclib_xml: The dependency representation.

    Returns:
        The stated value and the Standard Uncertainty implied by the influences.

    Raises:
        ValueError: If the document cannot be parsed.
    """
    influences = parse_input_quantities(unclib_xml)
    combined = math.sqrt(sum(item.uncertainty_contribution**2 for item in influences))
    try:
        root = ElementTree.fromstring(unclib_xml)
    except ElementTree.ParseError as error:
        raise ValueError(str(error)) from error
    text = root.findtext("./Value")
    return (float(text) if text else 0.0), combined


def _step_agreement(
    credential: dict[str, Any],
    dependency_value: float | None,
    dependency_uncertainty: float | None,
    dcc_result: dict[str, Any] | None = None,
) -> Step:
    """Check that every carrier of this result tells the same story.

    A certificate that offers the same measurement three ways can offer it three
    *different* ways, and the signature will not notice: it stops anyone editing a
    carrier after issue and says nothing about them being inconsistent when written. So
    each one is read and compared against the printed line.

    The PTB/DKD DCC states an *Expanded* uncertainty with its coverage factor, so it has
    to be divided by k before being compared with the printed Standard Uncertainty.
    Getting that the wrong way round is exactly the sort of error this check exists to
    catch, so the tests assert the direction explicitly.

    Args:
        credential: The credential being verified.
        dependency_value: The value the dependency representation states.
        dependency_uncertainty: The Standard Uncertainty its influences imply.
        dcc_result: The quantity read out of the PTB/DKD DCC, when one is carried.

    Returns:
        The step, naming whichever carrier disagrees.
    """
    result = _first_result(credential)
    has_dependency = dependency_value is not None and dependency_uncertainty is not None
    if result is None or (not has_dependency and dcc_result is None):
        return Step(
            id="uncertainty.agreement",
            title="Every carrier of this result tells the same story",
            status=SKIP,
            detail="the certificate offers only one carrier, so there is nothing to compare",
        )

    try:
        stated_value = float(result["value"])
        stated_uncertainty = float(result["standardUncertainty"])
    except (KeyError, TypeError, ValueError) as error:
        return Step(
            id="uncertainty.agreement",
            title="Every carrier of this result tells the same story",
            status=FAIL,
            detail=f"the printed result could not be read: {error}",
        )

    children: list[Step] = []
    evidence: dict[str, Any] = {
        "printedValue": stated_value,
        "printedStandardUncertainty": stated_uncertainty,
    }

    if has_dependency:
        matches = math.isclose(
            stated_value, dependency_value, rel_tol=1e-9, abs_tol=1e-12
        ) and math.isclose(
            stated_uncertainty, dependency_uncertainty, rel_tol=1e-6, abs_tol=0.0
        )
        children.append(
            Step(
                id="uncertainty.agreement.dependencies",
                title="The dependency representation agrees with the printed line",
                status=PASS if matches else FAIL,
                detail=(
                    f"printed {stated_value:.10g} with u = {stated_uncertainty:.6g}; the "
                    f"dependency representation gives {dependency_value:.10g} with "
                    f"u = {dependency_uncertainty:.6g}"
                ),
            )
        )
        evidence["dependencyValue"] = dependency_value
        evidence["dependencyStandardUncertainty"] = dependency_uncertainty

    if dcc_result is not None:
        coverage = float(dcc_result.get("coverageFactor") or 0.0)
        dcc_value = float(dcc_result.get("value"))
        # The PTB/DKD DCC states U; the printed line states u. Divide before comparing.
        dcc_standard = (
            float(dcc_result.get("expandedUncertainty")) / coverage if coverage else None
        )
        matches = (
            dcc_standard is not None
            and math.isclose(stated_value, dcc_value, rel_tol=1e-9, abs_tol=1e-12)
            and math.isclose(stated_uncertainty, dcc_standard, rel_tol=1e-6, abs_tol=0.0)
        )
        children.append(
            Step(
                id="uncertainty.agreement.dcc",
                title="The PTB/DKD DCC agrees with the printed line",
                status=PASS if matches else FAIL,
                detail=(
                    f"printed {stated_value:.10g} with u = {stated_uncertainty:.6g}; the "
                    f"PTB/DKD DCC gives {dcc_value:.10g} with "
                    f"U = {float(dcc_result.get('expandedUncertainty')):.6g} at "
                    f"k = {coverage:g}, so u = "
                    f"{dcc_standard:.6g}" if dcc_standard is not None
                    else "the PTB/DKD DCC states no usable coverage factor"
                ),
            )
        )
        evidence["dccValue"] = dcc_value
        evidence["dccStandardUncertainty"] = dcc_standard

    failed = [child for child in children if child.status == FAIL]
    return Step(
        id="uncertainty.agreement",
        title="Every carrier of this result tells the same story",
        status=FAIL if failed else PASS,
        detail=(
            f"{len(children)} carrier(s) checked against the printed result, all agreeing"
            if not failed
            else "; ".join(child.detail for child in failed)
        ),
        evidence=evidence,
        children=children,
    )


def _step_duplication(credential: dict[str, Any], dcc_xml: str | None) -> Step:
    """Check the facts the credential and the PTB/DKD DCC both state.

    Putting a standardised document inside a credential duplicates most of it. Who
    calibrated, for whom, when, and under what number are all said twice, in different
    vocabularies, and there is no mechanism that keeps them together. The signature
    covers both copies and is perfectly happy for them to contradict each other.

    Reading both is what turns that redundancy from a liability into an asset: every
    duplicated field becomes somewhere an inconsistent issuer gets caught. The
    alternative designs are to not duplicate at all, by making the PTB/DKD DCC the credential
    subject, or to declare which copy governs; see ARCHITECTURE.md.

    Args:
        credential: The credential being verified.
        dcc_xml: The PTB/DKD DCC it carries, when it carries one.

    Returns:
        The step, with one child per duplicated fact.
    """
    if dcc_xml is None:
        return Step(
            id="uncertainty.duplication",
            title="Facts stated twice agree with each other",
            status=SKIP,
            detail="the certificate carries no second document to disagree with",
        )

    try:
        administrative = parse_dcc_administrative(dcc_xml)
    except ValueError as error:
        return Step(
            id="uncertainty.duplication",
            title="Facts stated twice agree with each other",
            status=FAIL,
            detail=str(error),
        )

    payload = _payload(credential)
    subject = credential.get("credentialSubject")
    subject = subject if isinstance(subject, dict) else {}
    issuer = credential.get("issuer")
    issuer = issuer if isinstance(issuer, dict) else {}
    owner = subject.get("owner")
    owner = owner if isinstance(owner, dict) else {}

    duplicated = [
        (
            "certificate number",
            payload.get("certificateNumber"),
            administrative.get("uniqueIdentifier"),
        ),
        ("calibrating laboratory", issuer.get("id"), administrative.get("calibrationLaboratoryId")),
        ("laboratory name", issuer.get("name"), administrative.get("calibrationLaboratory")),
        ("customer", owner.get("id"), administrative.get("customerId")),
        ("customer name", owner.get("name"), administrative.get("customer")),
        ("date of calibration", payload.get("performedOn"), administrative.get("beginPerformanceDate")),
    ]

    children = [
        Step(
            id=f"uncertainty.duplication.{index}",
            title=title,
            status=PASS if credential_side == dcc_side else FAIL,
            detail=(
                f"credential says {credential_side!r}, PTB/DKD DCC says {dcc_side!r}"
            ),
        )
        for index, (title, credential_side, dcc_side) in enumerate(duplicated, start=1)
    ]

    failed = [child for child in children if child.status == FAIL]
    return Step(
        id="uncertainty.duplication",
        title="Facts stated twice agree with each other",
        status=FAIL if failed else PASS,
        detail=(
            f"the credential and the PTB/DKD DCC state {len(children)} facts twice and "
            f"agree on all of them"
            if not failed
            else (
                f"{len(failed)} of {len(children)} duplicated facts disagree: "
                + "; ".join(child.title for child in failed)
            )
        ),
        evidence={"comparedFields": len(children)},
        children=children,
    )


def _step_representations(credential: dict[str, Any], resolver: Resolver) -> Step:
    """Check that every uncertainty representation is intact and self-consistent.

    Two things are checked here. Each representation has to match the digest recorded
    for it, whether it travelled inside the credential or was fetched; that is what lets
    the dependency data live outside the credential without escaping the signature.

    And where a certificate offers both a classical statement and a dependency
    representation, the two have to agree. A certificate whose printed uncertainty
    differs from the one its own dependency data implies is telling two stories, and the
    recipient is expected to act on the second.

    Args:
        credential: The credential being verified.
        resolver: Used to retrieve any separately published representation.

    Returns:
        The step, with one child per representation plus the agreement check.
    """
    representations = _representations(credential)
    if not representations:
        return Step(
            id="uncertainty.representations",
            title="Uncertainty representations are intact",
            status=SKIP,
            detail=(
                "the certificate states its uncertainty classically only, which is what "
                "an issuer without such a tool would produce"
            ),
        )

    children: list[Step] = []
    dependency_value: float | None = None
    dependency_uncertainty: float | None = None
    dcc_result: dict[str, Any] | None = None
    dcc_xml: str | None = None

    for index, representation in enumerate(representations, start=1):
        kind = str(representation.get("format", "unknown"))
        step_id = f"uncertainty.representations.{index}"

        if representation.get("type") == "ClassicalStatement":
            children.append(
                Step(
                    id=step_id,
                    title=kind,
                    status=PASS,
                    detail=str(representation.get("reported", "classical statement")),
                )
            )
            continue

        payload, where = _representation_bytes(representation, resolver)
        if payload is None:
            children.append(Step(id=step_id, title=kind, status=FAIL, detail=where))
            continue

        expected = representation.get("digestMultibase")
        if isinstance(expected, str) and not verify_digest_multibase(payload, expected):
            children.append(
                Step(
                    id=step_id,
                    title=kind,
                    status=FAIL,
                    detail=(
                        f"{where}, but it does not match the digest recorded in the "
                        f"credential, so it is not the data that was signed for"
                    ),
                )
            )
            continue

        detail = f"{where}, {len(payload)} bytes, digest matches"
        if kind == "PTB-DKD-DCC-XML" and dcc_result is None:
            try:
                dcc_xml = payload.decode("utf-8")
                dcc_result = parse_dcc_result(dcc_xml)
                detail += (
                    f", stating {dcc_result['value']:.10g} {dcc_result['unit']}"
                    f" in D-SI notation"
                )
            except (ValueError, UnicodeDecodeError) as error:
                children.append(
                    Step(
                        id=step_id,
                        title=kind,
                        status=FAIL,
                        detail=f"{where}, but could not be read: {error}",
                    )
                )
                continue
        if kind == "METAS-UncLib-XML" and dependency_value is None:
            try:
                text = payload.decode("utf-8")
                dependency_value, dependency_uncertainty = _reconstruct(text)
                detail += f", {len(parse_input_quantities(text))} input quantities"
            except (ValueError, UnicodeDecodeError) as error:
                children.append(
                    Step(
                        id=step_id,
                        title=kind,
                        status=FAIL,
                        detail=f"{where}, but could not be parsed: {error}",
                    )
                )
                continue

        children.append(Step(id=step_id, title=kind, status=PASS, detail=detail))

    children.append(
        _step_agreement(credential, dependency_value, dependency_uncertainty, dcc_result)
    )
    children.append(_step_duplication(credential, dcc_xml))

    failed = [child for child in children if child.status == FAIL]
    return Step(
        id="uncertainty.representations",
        title="Uncertainty representations are intact",
        status=FAIL if failed else PASS,
        detail=(
            f"{len(representations)} representation(s) offered, all intact and in agreement"
            if not failed
            else "; ".join(child.detail for child in failed[:2])
        ),
        children=children,
    )


def _input_identifiers(credential: dict[str, Any]) -> set[str]:
    """Return the input quantity identifiers a certificate declares.

    Args:
        credential: The credential to inspect.

    Returns:
        The identifiers, empty when the certificate carries no dependency
        representation. Read from the summary in the credential, which the signature
        covers, rather than from the payload.
    """
    identifiers: set[str] = set()
    for representation in _representations(credential):
        for entry in representation.get("inputQuantities", []) or []:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                identifiers.add(entry["id"])
    return identifiers


def _step_shared_inputs(credential: dict[str, Any], parent: dict[str, Any]) -> Step:
    """Check that a certificate really inherits the influences of its parent.

    Everything else about traceability is an assertion the verifier takes on trust: a
    name, a digest over a document, a line in a budget. This is the one check where the
    claim is visible in the arithmetic. If the laboratory genuinely built on the
    certificate above it, the influences of that certificate are present in its own
    result and carry the same identifiers. If it did not, they are absent, and no amount
    of correct paperwork puts them there.

    Args:
        credential: The certificate being verified.
        parent: The certificate it declares traceability to.

    Returns:
        The step.
    """
    child_inputs = _input_identifiers(credential)
    parent_inputs = _input_identifiers(parent)

    if not child_inputs or not parent_inputs:
        return Step(
            id="traceability.shared-inputs",
            title="Inherited influences are present in this result",
            status=SKIP,
            detail=(
                "one of the two certificates transmits no dependency representation, so "
                "the inheritance can only be taken on trust"
            ),
        )

    shared = parent_inputs & child_inputs
    missing = parent_inputs - child_inputs
    parent_id = parent.get("id")
    return Step(
        id="traceability.shared-inputs",
        title="Inherited influences are present in this result",
        status=PASS if not missing else FAIL,
        detail=(
            f"all {len(shared)} input quantities of {parent_id} reappear in this result "
            f"with the same identifiers"
            if not missing
            else (
                f"{len(missing)} of the {len(parent_inputs)} input quantities of "
                f"{parent_id} are absent here, so this result was not built on that "
                f"certificate however much it says it was"
            )
        ),
        evidence={
            "sharedCount": len(shared),
            "missingCount": len(missing),
            "shared": sorted(shared)[:8],
        },
    )
