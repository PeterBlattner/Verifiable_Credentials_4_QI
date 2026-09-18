"""Project a quality-infrastructure credential into the UNTP Digital Conformity Credential.

This is a probe, not a conformance target. Nothing in the quality infrastructure obliges
a calibration certificate to be a UN/CEFACT Digital Conformity Credential, and the W3C
Verifiable Credentials specification is the one this project actually answers to. The
question here is narrower and worth asking on its own: if you take a certificate this
project issues and express it in UNTP's vocabulary, what arrives and what is left on the
platform?

The mapping is made faithfully and then stopped. Where UNTP requires a member the source
document does not state, the member is **omitted** and the omission recorded, rather than
filled with the nearest plausible value. A required field satisfied by invention is not a
mapping; it is a misstatement, and the schema failure that follows from leaving it out is
the finding. This is the same discipline as :mod:`vcqi.actors.tamper`, where the expected
failure is the content.

What the probe found, against ``untp-dcc-schema-0.6.0``:

* UNTP's envelope anticipates this work more than its reputation suggests.
  ``attestationType`` includes ``calibration``; ``assessmentLevel`` includes
  ``GlobalMRA`` and ``Accredited``, which is the CIPM MRA and accreditation distinction
  this project spends four chapters on; and ``authorisation`` is described as the
  national accreditation authority standing behind the body. Those land cleanly.
* What does not arrive is the measurement. ``conformance`` is a required boolean, and a
  calibration does not pass or fail -- it reports a value. ``conformityTopic`` is
  required and is a *sustainability* topic code, so neither a calibration of a resistance
  standard nor a kettle certified to IEC 60335-1 has an honest value to put there.
* ``Metric`` and ``Measure`` are ``additionalProperties: false``, so uncertainty cannot be
  added at the only two places it could go. The nearest member is ``Metric.accuracy``, a
  plain fraction meaning "within this much of the claimed value". An Expanded Uncertainty
  at k=2 is a coverage interval, not a bound, and writing one into the other would quietly
  restate a 95% statement as a certainty. So it is dropped, and the projected value
  carries no uncertainty at all, which is the honest depiction of what the format holds.
* ``Measure.unit`` draws on UNECE Recommendation 20 codes rather than the resolvable SI
  unit identifiers the BIPM now publishes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from vcqi.config import CONTEXT_CREDENTIALS_V2

#: The UNTP release this projection targets. Pinned, with the schema vendored beside it,
#: so the result recorded in the harmonisation chapter cannot drift under us.
UNTP_VERSION = "0.6.0"

#: The versioned vocabulary URL. The UNTP Playground detects a credential's version by
#: looking for a ``test.uncefact.org`` URL in ``@context`` carrying a semantic version,
#: so the major-version alias published elsewhere would leave it reporting ``unknown``.
UNTP_DCC_CONTEXT = f"https://test.uncefact.org/vocabulary/untp/dcc/{UNTP_VERSION}/"

#: The context array of a projected credential.
UNTP_CONTEXT = [CONTEXT_CREDENTIALS_V2, UNTP_DCC_CONTEXT]

#: The type array the Playground matches on to select a schema.
UNTP_DCC_TYPE = ["VerifiableCredential", "DigitalConformityCredential"]

#: The vendored copy of the schema the Playground fetches for this version. Vendored
#: rather than fetched, so the check runs with no network and so the published schema
#: changing under us is a visible diff rather than a silent change of result.
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "vendor" / "untp" / (
    f"untp-dcc-schema-{UNTP_VERSION}.json"
)


@lru_cache(maxsize=1)
def untp_schema() -> dict[str, Any]:
    """Load the pinned UNTP Digital Conformity Credential schema.

    Returns:
        The JSON Schema, as published for :data:`UNTP_VERSION`.
    """
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def schema_errors(credential: dict[str, Any]) -> list[dict[str, str]]:
    """Validate a credential against the pinned UNTP schema.

    This is the Playground's UNTP Schema Validation step, run here instead of there.
    The Playground fetches the same document and compiles it with AJV; the errors agree
    because the schema does, which is the point of pinning it.

    Args:
        credential: The credential to validate.

    Returns:
        One entry per error, with the path in the document and the message, sorted by
        path so the result is stable.
    """
    validator = Draft202012Validator(untp_schema())
    return [
        {
            "path": "/".join(str(step) for step in error.absolute_path) or "(root)",
            "message": error.message,
        }
        for error in sorted(
            validator.iter_errors(credential), key=lambda item: list(item.absolute_path)
        )
    ]


@dataclass(frozen=True)
class Omission:
    """One thing the source document says that the projection could not carry.

    Attributes:
        path: Where it would have gone in the UNTP document, or ``(no equivalent)`` when
            UNTP has no such place at all.
        source: The member of the source credential that was left behind.
        reason: Why it was left behind rather than approximated.
        required: Whether UNTP requires the omitted member, and the projection therefore
            fails schema validation because of it.
    """

    path: str
    source: str
    reason: str
    required: bool = False

    def to_json(self) -> dict[str, Any]:
        """Render the omission for the interface.

        Returns:
            A JSON-compatible object.
        """
        return {
            "path": self.path,
            "source": self.source,
            "reason": self.reason,
            "required": self.required,
        }


@dataclass(frozen=True)
class Projection:
    """A credential expressed in UNTP terms, with an account of what it cost.

    Attributes:
        credential: The unsecured UNTP Digital Conformity Credential, ready to be signed.
        omissions: Everything the mapping could not carry, in the order encountered.
    """

    credential: dict[str, Any]
    omissions: tuple[Omission, ...] = field(default_factory=tuple)

    @property
    def blocking(self) -> tuple[Omission, ...]:
        """Return the omissions that make the projection fail UNTP schema validation.

        Returns:
            The omissions of members UNTP marks required.
        """
        return tuple(item for item in self.omissions if item.required)


def project_calibration_certificate(source: dict[str, Any]) -> Projection:
    """Express a calibration certificate as an UNTP Digital Conformity Credential.

    Args:
        source: A signed or unsigned ``CalibrationCertificateCredential``.

    Returns:
        The projection and the account of what it could not carry.
    """
    subject = source.get("credentialSubject", {})
    calibration = subject.get("calibration", {})
    results = calibration.get("results") or [{}]
    result = results[0]
    omissions: list[Omission] = []

    assessment: dict[str, Any] = {
        "type": ["ConformityAssessment", "Declaration"],
        "id": source.get("id"),
        "name": f"Calibration {calibration.get('certificateNumber', '')}".strip(),
        "assessmentDate": calibration.get("performedOn"),
        "assessedProduct": [_product(subject)],
    }

    measurand = calibration.get("measurand")
    if measurand is not None and result.get("value") is not None:
        assessment["declaredValue"] = [
            {
                "type": ["Metric"],
                "metricName": str(measurand),
                "metricValue": {
                    "type": ["Measure"],
                    "value": result["value"],
                    "unit": str(calibration.get("unit", result.get("unit", ""))),
                },
            }
        ]
        omissions.append(
            Omission(
                path="assessment[0].declaredValue[0].metricValue.unit",
                source="calibration.unit",
                reason=(
                    "UNTP draws units from UNECE Recommendation 20 codes. The symbol is "
                    "carried through unchanged, which is not the same thing, and is not "
                    "a resolvable SI unit identifier either."
                ),
            )
        )
        omissions.append(
            Omission(
                path="assessment[0].declaredValue[0].accuracy",
                source="calibration.results[0].expandedUncertainty",
                reason=(
                    "Metric is additionalProperties: false, so uncertainty has no member "
                    "to occupy. The nearest is accuracy, a fraction meaning the value is "
                    "within that much of the claim -- a bound, where an Expanded "
                    "Uncertainty at k=2 is a coverage interval. Writing one into the "
                    "other would restate a 95 per cent statement as a certainty, so the "
                    "value travels with no uncertainty at all."
                ),
            )
        )

    omissions.append(
        Omission(
            path="assessment[0].conformance",
            source="(nothing in the source)",
            reason=(
                "UNTP requires a boolean. A calibration does not pass or fail; it reports "
                "a value with an uncertainty, and whether that is good enough is a "
                "judgement for whoever is using the instrument."
            ),
            required=True,
        )
    )
    omissions.append(
        Omission(
            path="assessment[0].conformityTopic",
            source="(nothing in the source)",
            reason=(
                "UNTP requires one of fifteen sustainability topic codes. A calibration "
                "of a resistance standard is none of them."
            ),
            required=True,
        )
    )
    for member, reason in (
        (
            "calibration.uncertaintyBudget",
            "UNTP has no uncertainty budget: no contributions, no sensitivity "
            "coefficients, no distributions, no coverage factor.",
        ),
        (
            "calibration.traceableTo",
            "UNTP has no traceability chain. A conformity attestation stands on its "
            "issuer's accreditation, not on an unbroken chain of comparisons to the SI.",
        ),
        (
            "calibration.conditions",
            "UNTP has no member for the conditions a measurement was made under, which "
            "is what decides whether a result applies to the reader's situation.",
        ),
        (
            "calibration.mraLogoAsserted",
            "Partly carried: assessmentLevel GlobalMRA says the same thing about the "
            "assessment, but not as a claim a verifier can adjudicate against a CMC.",
        ),
    ):
        if _has(source, member):
            omissions.append(Omission(path="(no equivalent)", source=member, reason=reason))

    attestation: dict[str, Any] = {
        "type": ["ConformityAttestation", "Attestation"],
        "id": source.get("id"),
        "name": source.get("name"),
        "assessorLevel": "3rdParty",
        "assessmentLevel": _assessment_level(calibration),
        "attestationType": "calibration",
        "assessment": [assessment],
    }
    _attach(attestation, subject.get("owner"), calibration.get("capabilityReference"))
    return Projection(_envelope(source, attestation), tuple(omissions))


def project_product_conformity(source: dict[str, Any]) -> Projection:
    """Express a certificate of conformity as an UNTP Digital Conformity Credential.

    This is the case UNTP was built for -- a third-party attestation that a product meets
    a standard -- and almost all of it arrives. What does not is the one member UNTP
    requires and the quality infrastructure has no value for.

    Args:
        source: A signed or unsigned ``ProductConformityCredential``.

    Returns:
        The projection and the account of what it could not carry.
    """
    subject = source.get("credentialSubject", {})
    conformity = subject.get("conformity", {})
    omissions: list[Omission] = []

    assessment: dict[str, Any] = {
        "type": ["ConformityAssessment", "Declaration"],
        "id": source.get("id"),
        "name": conformity.get("conformityStatement"),
        "assessmentDate": conformity.get("issuedOn"),
        "conformance": True,
        "assessedProduct": [_product(subject)],
    }
    standard = conformity.get("standard")
    if isinstance(standard, str):
        assessment["referenceStandard"] = {
            "type": ["Standard"],
            "name": standard,
            "issuingParty": {"name": standard.split()[0]},
        }
        omissions.append(
            Omission(
                path="assessment[0].referenceStandard.issuingParty.id",
                source="conformity.standard",
                reason=(
                    "UNTP requires the body behind a standard as a resolvable URI. The "
                    "certificate names its standard the way certificates do, as the "
                    "designation IEC 60335-1, and carries no identifier for the IEC. "
                    "Supplying one would be inventing a fact the source does not state."
                ),
                required=True,
            )
        )

    omissions.append(
        Omission(
            path="assessment[0].conformityTopic",
            source="(nothing in the source)",
            reason=(
                "UNTP requires one of fifteen sustainability topic codes. A kettle "
                "certified to IEC 60335-1 is an electrical safety statement, and "
                "social.safety in that list is an occupational health and safety code "
                "about the people doing the work, not about the product."
            ),
            required=True,
        )
    )
    if _has(source, "conformity.testReports"):
        omissions.append(
            Omission(
                path="auditableEvidence.hashDigest",
                source="conformity.testReports[0].digestMultibase",
                reason=(
                    "The reference is carried, but a SecureLink states its digest as bare "
                    "hex under a two-value hashMethod enumeration, not as the multihash "
                    "that says which algorithm produced it inside the value itself."
                ),
            )
        )

    attestation: dict[str, Any] = {
        "type": ["ConformityAttestation", "Attestation"],
        "id": source.get("id"),
        "name": source.get("name"),
        "assessorLevel": "3rdParty",
        "assessmentLevel": "Accredited",
        "attestationType": "certification",
        "assessment": [assessment],
    }
    _attach(attestation, subject.get("holder"), conformity.get("capabilityReference"))

    reports = conformity.get("testReports")
    if isinstance(reports, list) and reports and isinstance(reports[0], dict):
        attestation["auditableEvidence"] = {
            "type": ["SecureLink", "Link"],
            "linkURL": reports[0].get("id"),
            "linkName": "Test report supporting this certificate",
            "linkType": "https://test.uncefact.org/vocabulary/linkTypes/dcc",
        }

    return Projection(_envelope(source, attestation), tuple(omissions))


#: Which projection handles which source credential type.
PROJECTIONS = {
    "CalibrationCertificateCredential": project_calibration_certificate,
    "ProductConformityCredential": project_product_conformity,
}


def project(source: dict[str, Any]) -> Projection:
    """Project whichever credential type this is into UNTP terms.

    Args:
        source: The source credential.

    Returns:
        The projection.

    Raises:
        ValueError: If no projection is defined for this credential type.
    """
    for name in source.get("type", []):
        handler = PROJECTIONS.get(name)
        if handler is not None:
            return handler(source)
    raise ValueError(f"no UNTP projection for {source.get('type')}")


def _attach(
    attestation: dict[str, Any],
    party: dict[str, Any] | None,
    capability: dict[str, Any] | None,
) -> None:
    """Add the party and the accreditation members an attestation shares across types.

    Args:
        attestation: The ConformityAttestation being built, modified in place.
        party: The owner or holder reference from the source credential.
        capability: The ``capabilityReference`` member of the source credential.
    """
    rendered = _party(party)
    if rendered is not None:
        attestation["issuedToParty"] = rendered
    scheme = _scheme(capability)
    if scheme is not None:
        attestation["scope"] = scheme
    authorisation = _authorisation(capability)
    if authorisation:
        attestation["authorisation"] = authorisation


def _party(reference: dict[str, Any] | None) -> dict[str, Any] | None:
    """Render an organisation reference as an UNTP party object.

    Args:
        reference: An owner, holder or client reference from a source credential.

    Returns:
        The party object, or None when there is nothing to render.
    """
    if not isinstance(reference, dict):
        return None
    party: dict[str, Any] = {}
    for member in ("id", "name"):
        if isinstance(reference.get(member), str):
            party[member] = reference[member]
    return party or None


def _issuer(source: dict[str, Any]) -> dict[str, Any]:
    """Render the issuer as an UNTP CredentialIssuer.

    ``recognizedIn`` is not carried here. UNTP puts no such member on the issuer; the
    equivalent statement goes on the attestation as ``authorisation``, which is where
    :func:`_authorisation` puts it.

    Args:
        source: The source credential.

    Returns:
        The CredentialIssuer object.
    """
    issuer = source.get("issuer")
    if not isinstance(issuer, dict):
        return {"type": ["CredentialIssuer"], "id": str(issuer)}
    rendered: dict[str, Any] = {"type": ["CredentialIssuer"], "id": issuer.get("id")}
    if isinstance(issuer.get("name"), str):
        rendered["name"] = issuer["name"]
    return rendered


def _authorisation(capability: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Render the accreditation the work was performed under as an UNTP Endorsement.

    UNTP describes ``authorisation`` as the authority under which a claim is issued, and
    gives a national accreditation body authorising a test laboratory as its example.
    That is what ``capabilityReference`` names, so this is one of the mappings that
    arrives intact.

    Args:
        capability: The ``capabilityReference`` member of the source credential.

    Returns:
        A single-item list of Endorsement objects, or an empty list.
    """
    if not isinstance(capability, dict) or not isinstance(capability.get("id"), str):
        return []
    identifier = str(capability.get("identifier") or capability["id"])
    return [
        {
            "type": ["Endorsement"],
            "id": capability["id"],
            "name": f"{capability.get('type', 'Capability')} {identifier}",
            "issuingAuthority": {"id": capability["id"], "name": identifier},
        }
    ]


def _scheme(capability: dict[str, Any] | None) -> dict[str, Any] | None:
    """Render the accreditation scope as an UNTP ConformityAssessmentScheme.

    Args:
        capability: The ``capabilityReference`` member of the source credential.

    Returns:
        The scheme object, or None when there is nothing to render.
    """
    if not isinstance(capability, dict) or not isinstance(capability.get("id"), str):
        return None
    identifier = str(capability.get("identifier") or capability["id"])
    return {
        "type": ["ConformityAssessmentScheme", "Standard"],
        "id": capability["id"],
        "name": identifier,
        "issuingParty": {"id": capability["id"], "name": identifier},
    }


def _product(subject: dict[str, Any]) -> dict[str, Any]:
    """Render the credential subject as an UNTP ProductVerification.

    Args:
        subject: The ``credentialSubject`` of the source credential.

    Returns:
        The ProductVerification object.
    """
    product: dict[str, Any] = {}
    for member, target in (("id", "id"), ("name", "name"), ("serialNumber", "registeredId")):
        value = subject.get(member)
        if isinstance(value, str):
            product[target] = value
    return {"type": ["ProductVerification"], "product": product}


def _assessment_level(calibration: dict[str, Any]) -> str:
    """Choose the UNTP assurance level a calibration was performed under.

    UNTP's enumeration happens to name both halves of the arrangement this project is
    about: ``GlobalMRA`` for work covered by an international arrangement, ``Accredited``
    for work covered by a national accreditation.

    Args:
        calibration: The ``calibration`` member of a calibration certificate.

    Returns:
        The assurance code.
    """
    if calibration.get("mraLogoAsserted"):
        return "GlobalMRA"
    if calibration.get("accredited"):
        return "Accredited"
    return "Unspecified"


def _envelope(source: dict[str, Any], attestation: dict[str, Any]) -> dict[str, Any]:
    """Wrap an attestation in the UNTP credential envelope.

    Args:
        source: The source credential, for the members that carry across unchanged.
        attestation: The ConformityAttestation to carry.

    Returns:
        The unsecured UNTP credential.
    """
    credential: dict[str, Any] = {
        "@context": list(UNTP_CONTEXT),
        "id": source.get("id"),
        "type": list(UNTP_DCC_TYPE),
        "issuer": _issuer(source),
        "credentialSubject": attestation,
    }
    for member in ("validFrom", "validUntil"):
        if member in source:
            credential[member] = source[member]
    return credential


def _has(source: dict[str, Any], path: str) -> bool:
    """Report whether a dotted path is present under the credential subject.

    Args:
        source: The source credential.
        path: A dotted path relative to ``credentialSubject``, for example
            ``calibration.traceableTo``.

    Returns:
        True when every step of the path resolves.
    """
    node: Any = source.get("credentialSubject", {})
    for step in path.split("."):
        if not isinstance(node, dict) or step not in node:
            return False
        node = node[step]
    return True
