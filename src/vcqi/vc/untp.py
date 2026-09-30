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
failure is the content. Every value the projection does supply that the source does not
literally state -- a code chosen from one of UNTP's lists -- is recorded too, as a
judgement, so nothing in the output is unaccounted for. :class:`Finding` has the four
kinds.

What the probe finds, against UNTP 0.7.0. It was run against 0.6.0 first, and change sets
24 and 28 of docs/history/PLAN-2026.md have both results:

* The envelope reaches calibration. ``attestationType`` includes ``calibration``;
  ``conformance`` is optional, so a calibration is no longer forced into a verdict it
  does not give; ``conformityTopic`` is an open list, and UNTP's own topic vocabulary has
  ``metrology-and-measurement``; ``specifiedCondition`` carries the conditions of
  measurement as text.
* ``assessmentLevel`` has no code for the CIPM MRA. UNTP defines ``authority-globalmra``
  as accreditation under the Global Accreditation Cooperation MRA, which is the other
  arrangement. 0.6.0 enumerated ``GlobalMRA`` without defining it, and this project read
  it as the CIPM MRA; that reading is withdrawn.
* The uncertainty still does not arrive. ``Measure`` is ``additionalProperties: false``
  and holds a value, a unit and two tolerances. A tolerance is a limit -- UNTP's own
  example reads "10kg + 0.1kg" -- where an Expanded Uncertainty at k=2 is a coverage
  interval, so writing one into the other would restate a 95 % statement as a certainty.
  The value travels rounded as the certificate reports it, and without its uncertainty.
* Identifiers UNTP requires are missing on our side: one for the measurand, one for the
  scheme, and one for a standard named by its designation.
* ``Measure.unit`` is a UNECE Recommendation 20 code, expanded against UN/CEFACT's code
  list rather than the SI identifiers the BIPM publishes: two registers for one unit.
* UNTP types ``statusListIndex`` as an integer, while its own description of the member
  and the W3C Bitstring Status List Recommendation both say a string. The status entry is
  carried as W3C writes it, and the conflict recorded.

The recognitions go the same way, into UNTP's Digital Identity Anchor, one per entity a
recognition lists (:func:`project_recognition`). The entity, its registrar, its entry on
the registrar's site and its capabilities arrive, the capabilities as a list of links.
What a verifier acts on does not: the recognised actions, the ``outputValidation``
schemas a document issued under them must satisfy, and each action's own validity. UNTP
also requires a registration number and a first-registration date no recognition
states, and its register types stop at accreditation, so the CIPM MRA has none.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from vcqi.config import CONTEXT_CREDENTIALS_V2
from vcqi.domain.uncertainty import rounded_to_uncertainty

#: The UNTP release this projection targets. Pinned, with the schema and context vendored
#: beside it, so the result recorded in the harmonisation chapter cannot drift under us.
UNTP_VERSION = "0.7.0"

#: The versioned context. From 0.7.0 on, UNTP publishes one context for every credential
#: type at ``vocabulary.uncefact.org``, and the Playground reads the version from it.
UNTP_DCC_CONTEXT = f"https://vocabulary.uncefact.org/untp/{UNTP_VERSION}/context/"

#: The context array of a projected credential, which the schema fixes in this order.
UNTP_CONTEXT = [CONTEXT_CREDENTIALS_V2, UNTP_DCC_CONTEXT]

#: The type arrays the Playground matches on, first to accept the upload at all and then
#: to select a schema: a certificate becomes a Digital Conformity Credential, and each
#: entity a recognition lists becomes a Digital Identity Anchor of its own.
UNTP_DCC_TYPE = ["VerifiableCredential", "DigitalConformityCredential"]
UNTP_DIA_TYPE = ["VerifiableCredential", "DigitalIdentityAnchor"]

_VENDOR = Path(__file__).resolve().parent.parent / "vendor"

#: The vendored schemas, the copies the Playground bundles: the DCC taken from the UNTP
#: specification repository at tag ``v0.7.0``, the DIA from the Playground's own bundle,
#: whose manifest ties it to the same tag by the content hash below. Vendored rather than
#: fetched, so the check runs with no network and a change to a published schema is a
#: visible diff.
SCHEMA_PATH = _VENDOR / "untp" / f"untp-dcc-schema-{UNTP_VERSION}.json"
DIA_SCHEMA_PATH = _VENDOR / "untp" / f"untp-dia-schema-{UNTP_VERSION}.json"
SCHEMA_PATHS = {
    "DigitalConformityCredential": SCHEMA_PATH,
    "DigitalIdentityAnchor": DIA_SCHEMA_PATH,
}

#: The vendored contexts a projected credential names, by the URL it names them with.
#: Used by :mod:`vcqi.vc.jsonld_terms` to check every term expands, offline.
CONTEXT_PATHS = {
    CONTEXT_CREDENTIALS_V2: _VENDOR / "w3c" / "credentials-v2.jsonld",
    UNTP_DCC_CONTEXT: _VENDOR / "untp" / f"untp-context-{UNTP_VERSION}.jsonld",
}

#: The content hash of each vendored file, computed as the Playground's artefact manifest
#: computes it (see :func:`content_sha256`), so the two can be compared by eye.
VENDORED_CONTENT_SHA256 = {
    SCHEMA_PATH.name: "10869cc870bdf9e1d499c46a319c78fcdae7b1a4f37d837a84d34a4aaffb0883",
    DIA_SCHEMA_PATH.name: (
        "0f125c2e8c6f0b01c79c7bf05ece2e33a88982edf023ee90479454b60b6b5eea"
    ),
    CONTEXT_PATHS[UNTP_DCC_CONTEXT].name: (
        "3c0f6d7e6fdd4e54fc167c98a8ae232739c582fab845522bf81e7c67c881714f"
    ),
    CONTEXT_PATHS[CONTEXT_CREDENTIALS_V2].name: (
        "b463c8d6a066214123ddd9827b135e1b50e1fc73322cc52a9b12a4f1fc7d86cf"
    ),
}

#: UNTP's conformity topic vocabulary, and the two topics this projection uses. The
#: names and the choice are UNTP's and ours respectively; the choice is recorded as a
#: judgement wherever it is made.
TOPIC_VOCABULARY = "https://vocabulary.uncefact.org/conformity-topics/"
TOPICS = {
    "metrology-and-measurement": "Metrology and Measurement",
    "product-safety-standards": "Product Safety Standards",
}

#: UNECE Recommendation 20 codes for the unit symbols the demonstration writes. Only the
#: ones it needs: a symbol missing from here is reported, never passed through, because
#: the symbol is not a code UNTP has.
REC20 = {"ohm": "OHM"}

#: Where the attestation and its assessment sit in the document, as finding paths.
SUBJECT = "credentialSubject"
ASSESSMENT = f"{SUBJECT}/conformityAssessment/0"

#: The four kinds of :class:`Finding`.
DROPPED = "dropped"
REQUIRED = "required"
CONFLICT = "conflict"
JUDGEMENT = "judgement"
KINDS = (DROPPED, REQUIRED, CONFLICT, JUDGEMENT)
BLOCKING_KINDS = frozenset({REQUIRED, CONFLICT})

#: Resolves a URL to the document published there, or None. The projection uses it only
#: to name a party by reading the document that names it.
Lookup = Callable[[str], "dict[str, Any] | None"]

_REQUIRED_MESSAGE = re.compile(r"^'(.+)' is a required property$")


def content_sha256(document: Any) -> str:
    """Hash a JSON document by its content rather than its bytes.

    Keys sorted at every level, no whitespace, UTF-8: what the Playground's artefact
    manifest hashes. Line endings and indentation therefore do not matter, which they
    must not, since git normalises the one and the publishers differ on the other.

    Args:
        document: A parsed JSON document.

    Returns:
        The SHA-256 of its canonical form, as hex.
    """
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@lru_cache(maxsize=None)
def untp_schema(kind: str = "DigitalConformityCredential") -> dict[str, Any]:
    """Load one of the pinned UNTP schemas.

    Args:
        kind: The UNTP credential type, a key of :data:`SCHEMA_PATHS`.

    Returns:
        The JSON Schema, as published for :data:`UNTP_VERSION`.
    """
    return json.loads(SCHEMA_PATHS[kind].read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def vendored_contexts() -> dict[str, dict[str, Any]]:
    """Load the contexts a projected credential names, from the vendored copies.

    Returns:
        Each context document, keyed by the URL the credential names it with.
    """
    return {
        url: json.loads(path.read_text(encoding="utf-8"))
        for url, path in CONTEXT_PATHS.items()
    }


def schema_errors(credential: dict[str, Any]) -> list[dict[str, str]]:
    """Validate a credential against the pinned UNTP schema.

    This is the Playground's UNTP Schema Validation step, run here instead of there. The
    Playground compiles the same document with AJV, with every error reported and formats
    not validated; this validator has no format checker either, so the two agree because
    the schema does, which is the point of pinning it.

    Args:
        credential: The credential to validate. Its type chooses the schema: a Digital
            Identity Anchor against the DIA schema, anything else against the DCC's.

    Returns:
        One entry per error, sorted so the result is stable: ``path`` is where the
        validator reports it, and ``member`` is the member at fault -- the same path, with
        the missing property added for a ``required`` error. ``member`` is what a
        :class:`Finding` path is compared with.
    """
    types = credential.get("type") or []
    kind = "DigitalIdentityAnchor" if "DigitalIdentityAnchor" in types else (
        "DigitalConformityCredential"
    )
    validator = Draft202012Validator(untp_schema(kind))
    errors = []
    for error in validator.iter_errors(credential):
        steps = [str(step) for step in error.absolute_path]
        missing = None
        if error.validator == "required":
            missing = _REQUIRED_MESSAGE.match(error.message)
        member = steps + [missing.group(1)] if missing else steps
        errors.append(
            {
                "path": "/".join(steps) or "(root)",
                "member": "/".join(member) or "(root)",
                "message": error.message,
            }
        )
    return sorted(errors, key=lambda item: (item["member"], item["message"]))


@dataclass(frozen=True)
class Finding:
    """One thing the projection had to decide, and what it decided.

    Attributes:
        kind: ``dropped`` -- the source states it and UNTP has no place for it, or has a
            place the projection deliberately leaves empty; ``required`` -- UNTP requires
            it and the source does not state it, so the schema fails; ``conflict`` --
            carried as the source states it, and refused by the schema; ``judgement`` --
            a value the source does not literally state, supplied and recorded.
        path: Where it is, or would have been, in the UNTP document, ``/``-separated from
            the credential root; ``(no equivalent)`` when UNTP has no such place.
        source: The member of the source credential it concerns.
        reason: Why the projection did what it did.
    """

    kind: str
    path: str
    source: str
    reason: str

    def __post_init__(self) -> None:
        """Reject a kind the interface would not know how to show.

        Raises:
            ValueError: If ``kind`` is not one of :data:`KINDS`.
        """
        if self.kind not in KINDS:
            raise ValueError(f"unknown finding kind {self.kind!r}")

    @property
    def blocking(self) -> bool:
        """Return whether this finding makes the projection fail the UNTP schema.

        Returns:
            True for ``required`` and ``conflict``.
        """
        return self.kind in BLOCKING_KINDS

    def to_json(self) -> dict[str, Any]:
        """Render the finding for the interface.

        Returns:
            A JSON-compatible object.
        """
        return {
            "kind": self.kind,
            "path": self.path,
            "source": self.source,
            "reason": self.reason,
            "blocking": self.blocking,
        }


@dataclass(frozen=True)
class Projection:
    """A credential expressed in UNTP terms, with an account of what it cost.

    Attributes:
        credential: The unsecured UNTP Digital Conformity Credential, ready to be signed.
        findings: Everything the mapping had to decide, in the order encountered.
    """

    credential: dict[str, Any]
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def blocking(self) -> tuple[Finding, ...]:
        """Return the findings that make the projection fail UNTP schema validation.

        Returns:
            The ``required`` and ``conflict`` findings.
        """
        return tuple(item for item in self.findings if item.blocking)


def project_calibration_certificate(
    source: dict[str, Any], lookup: Lookup | None = None
) -> Projection:
    """Express a calibration certificate as an UNTP Digital Conformity Credential.

    Args:
        source: A signed or unsigned ``CalibrationCertificateCredential``.
        lookup: Resolves a URL to the document published there, used to name the body
            that recognised the issuer. Without it, that endorsement is left out and
            recorded.

    Returns:
        The projection and the account of what it had to decide.
    """
    subject = source.get("credentialSubject", {})
    calibration = subject.get("calibration", {})
    findings: list[Finding] = []

    assessment: dict[str, Any] = {
        "type": ["ConformityAssessment"],
        "id": _fragment(source, "assessment"),
        "name": f"Calibration {calibration.get('certificateNumber', '')}".strip(),
        "assessmentDate": calibration.get("performedOn"),
    }

    capability = calibration.get("capabilityReference")
    criterion = _criterion(capability)
    if criterion is not None:
        assessment["assessmentCriteria"] = [criterion]
        if isinstance(capability, dict) and capability.get("digestMultibase"):
            findings.append(
                Finding(
                    DROPPED,
                    f"{ASSESSMENT}/assessmentCriteria/0",
                    "calibration.capabilityReference.digestMultibase",
                    "A criterion is an identifier and a name, with no member for a digest, "
                    "so the reference arrives without the digest that pins the version of "
                    "the scope it was issued under.",
                )
            )
    else:
        findings.append(
            Finding(
                REQUIRED,
                f"{ASSESSMENT}/assessmentCriteria",
                "calibration.capabilityReference",
                "UNTP requires the criteria an assessment was made against. The "
                "certificate names no capability it was issued within, so there is nothing "
                "to carry.",
            )
        )

    performances = [
        _performance(result, calibration, index, findings)
        for index, result in enumerate(calibration.get("results") or [])
        if isinstance(result, dict)
    ]
    if performances:
        assessment["assessedPerformance"] = performances
    else:
        findings.append(
            Finding(
                REQUIRED,
                f"{ASSESSMENT}/assessedPerformance",
                "calibration.results",
                "UNTP requires the assessed performance, and the certificate reports no "
                "result to put there.",
            )
        )

    assessment["conformityTopic"] = [_topic("metrology-and-measurement")]
    findings.append(
        Finding(
            JUDGEMENT,
            f"{ASSESSMENT}/conformityTopic/0",
            "(the credential type)",
            "The certificate states no topic; its type does. UNTP's topic vocabulary "
            "defines metrology-and-measurement as the accuracy and traceability of "
            "measurements and calibrations to national and international measurement "
            "standards, which is what a calibration certificate is about.",
        )
    )

    conditions = calibration.get("conditions")
    if isinstance(conditions, str):
        assessment["specifiedCondition"] = [conditions]
    if _has(source, "calibration.conditionQuantities"):
        findings.append(
            Finding(
                DROPPED,
                f"{ASSESSMENT}/specifiedCondition",
                "calibration.conditionQuantities",
                "The conditions arrive as the certificate words them. Their structured "
                "form -- a quantity, a value and a unit each, which is what a program "
                "would test a reader's situation against -- has no member, since "
                "specifiedCondition is a list of strings.",
            )
        )

    findings.append(
        Finding(
            DROPPED,
            f"{ASSESSMENT}/conformance",
            "(nothing in the source)",
            "Optional in UNTP, and left out. A calibration does not pass or fail; it "
            "reports a value with an uncertainty, and whether that is good enough is a "
            "judgement for whoever is using the instrument.",
        )
    )
    for member, reason in (
        (
            "calibration.uncertaintyBudget",
            "UNTP has no uncertainty budget: no contributions, no sensitivity "
            "coefficients, no distributions, no coverage factor. An evidence link could "
            "point at the representation that holds one, but could not say what it is.",
        ),
        (
            "calibration.traceableTo",
            "UNTP has no traceability chain. An evidence link could point at the "
            "certificate this one rests on, but could not say that it is the next step "
            "towards the SI rather than any supporting document.",
        ),
        (
            "calibration.mraLogoAsserted",
            "Partly carried: the endorsement names the recognition behind the issuer and "
            "assessmentLevel says authority-peer. The claim itself -- that this "
            "certificate carries the CIPM MRA logo -- has no member, so a verifier cannot "
            "adjudicate it against the CMC as [chapter](#verification) does.",
        ),
    ):
        if _has(source, member):
            findings.append(Finding(DROPPED, "(no equivalent)", member, reason))

    assessment["assessedProduct"] = [_product(subject, findings, item_number=True)]

    level, level_reason = _assessment_level(calibration)
    findings.append(
        Finding(
            JUDGEMENT,
            f"{SUBJECT}/assessmentLevel",
            "calibration.mraLogoAsserted",
            level_reason,
        )
    )
    if calibration.get("mraLogoAsserted"):
        scheme_reason = (
            "UNTP requires the scheme the attestation is made under, by identifier. The "
            "certificate claims the CIPM MRA by carrying its logo, so the arrangement is "
            "known by name, but nothing here gives the arrangement an identifier. The "
            "recognition credential lists its signatories; it is not the arrangement, and "
            "its address here would name the wrong thing."
        )
    else:
        scheme_reason = (
            "UNTP requires the scheme the attestation is made under, by identifier. The "
            "certificate rests on an accreditation, which travels as an endorsement, and "
            "names no scheme."
        )
    attestation = _attestation(
        source,
        level=level,
        attestation_type="calibration",
        party=subject.get("owner"),
        assessment=assessment,
        endorsements=[_recognition(source, lookup, findings)],
        scheme_reason=scheme_reason,
        source_member="calibration",
        findings=findings,
    )
    return Projection(_envelope(source, attestation, findings), tuple(findings))


def project_product_conformity(
    source: dict[str, Any], lookup: Lookup | None = None
) -> Projection:
    """Express a certificate of conformity as an UNTP Digital Conformity Credential.

    This is the case UNTP was built for -- a third-party attestation that a product meets
    a standard -- and most of it arrives. What does not is identifiers the certificate
    never had and measured values it never reported.

    Args:
        source: A signed or unsigned ``ProductConformityCredential``.
        lookup: Resolves a URL to the document published there, used to name the bodies
            behind the endorsements. Without it, they are left out and recorded.

    Returns:
        The projection and the account of what it had to decide.
    """
    subject = source.get("credentialSubject", {})
    conformity = subject.get("conformity", {})
    findings: list[Finding] = []

    assessment: dict[str, Any] = {
        "type": ["ConformityAssessment"],
        "id": _fragment(source, "assessment"),
        "name": f"Certification {conformity.get('certificateNumber', '')}".strip(),
    }
    statement = conformity.get("conformityStatement")
    if isinstance(statement, str):
        assessment["description"] = statement
    assessment["assessmentDate"] = conformity.get("issuedOn")

    standard = conformity.get("standard")
    if isinstance(standard, str):
        assessment["assessmentCriteria"] = [{"type": ["Criterion"], "name": standard}]
        findings.append(
            Finding(
                REQUIRED,
                f"{ASSESSMENT}/assessmentCriteria/0/id",
                "conformity.standard",
                f"UNTP identifies a criterion by URI. The certificate names its standard "
                f"the way certificates do, by the designation {standard}, and carries no "
                f"identifier for it. Supplying one would be inventing a fact the source "
                f"does not state.",
            )
        )
    else:
        findings.append(
            Finding(
                REQUIRED,
                f"{ASSESSMENT}/assessmentCriteria",
                "conformity.standard",
                "UNTP requires the criteria an assessment was made against, and the "
                "certificate names no standard.",
            )
        )
    findings.append(
        Finding(
            REQUIRED,
            f"{ASSESSMENT}/assessedPerformance",
            "(nothing in the source)",
            "UNTP requires the assessed performance. A certificate of conformity states a "
            "verdict against a standard and reports no measured values; those are in the "
            "test report it rests on, which travels as evidence.",
        )
    )

    assessment["conformityTopic"] = [_topic("product-safety-standards")]
    findings.append(
        Finding(
            JUDGEMENT,
            f"{ASSESSMENT}/conformityTopic/0",
            "conformity.standard",
            "The certificate states no topic; its standard does. IEC 60335-1 is the safety "
            "standard for household electrical appliances, and UNTP's topic vocabulary "
            "defines product-safety-standards as consumer safety through compliance with "
            "product safety requirements, testing and hazard prevention.",
        )
    )
    assessment["conformance"] = True
    assessment["assessedProduct"] = [_product(subject, findings, item_number=False)]

    reports = [
        report
        for report in conformity.get("testReports") or []
        if isinstance(report, dict) and isinstance(report.get("id"), str)
    ]
    if reports:
        assessment["evidence"] = [
            _link(
                report["id"],
                "Test report supporting this certificate",
                report.get("digestMultibase"),
            )
            for report in reports
        ]
        if any("issuer" in report for report in reports):
            findings.append(
                Finding(
                    DROPPED,
                    f"{ASSESSMENT}/evidence",
                    "conformity.testReports[].issuer",
                    "A link has no member for who issued what it points at. The digest "
                    "pins the report, and the report's own proof names its issuer.",
                )
            )

    capability = conformity.get("capabilityReference")
    findings.append(
        Finding(
            JUDGEMENT,
            f"{SUBJECT}/assessmentLevel",
            "conformity.capabilityReference",
            "The certificate rests on an accreditation, and the accreditation body behind "
            "it is a signatory of the Global Accreditation Cooperation MRA, which is how "
            "UNTP defines authority-globalmra.",
        )
    )
    attestation = _attestation(
        source,
        level="authority-globalmra",
        attestation_type="certification",
        party=subject.get("holder"),
        assessment=assessment,
        endorsements=[
            _recognition(source, lookup, findings),
            _accreditation(capability, lookup, findings, "conformity.capabilityReference"),
        ],
        scheme_reason=(
            "UNTP requires the conformity scheme the attestation is made under, by "
            "identifier. The certificate names its standard and its accreditation, not the "
            "certification scheme, so there is nothing to carry."
        ),
        source_member="conformity",
        findings=findings,
    )
    return Projection(_envelope(source, attestation, findings), tuple(findings))


def project_recognition(source: dict[str, Any], subject: str | None) -> Projection:
    """Express one entity of a recognition as an UNTP Digital Identity Anchor.

    A W3C Recognized Entities credential lists several entities, each recognised to do
    particular things -- issue, accredit -- within a named capability and against a
    schema the documents it issues must satisfy. An UNTP anchor names one registered
    entity and a list of scopes. So a recognition becomes one anchor per entity. What
    arrives is the entity, its registrar and its capabilities as links; what does not is
    the part a verifier can check a document against.

    Args:
        source: A signed or unsigned ``RecognizedEntityCredential``.
        subject: The DID of the recognised entity to anchor.

    Returns:
        The projection and the account of what it had to decide.

    Raises:
        ValueError: If ``subject`` is missing or not an entity the recognition lists.
    """
    subjects = source.get("credentialSubject")
    entries = subjects if isinstance(subjects, list) else [subjects]
    entity = next(
        (item for item in entries if isinstance(item, dict) and item.get("id") == subject),
        None,
    )
    if subject is None or entity is None:
        listed = [item.get("id") for item in entries if isinstance(item, dict)]
        raise ValueError(f"name one of the recognised entities {listed}, not {subject!r}")

    findings: list[Finding] = []
    actions = [item for item in entity.get("recognizedTo") or [] if isinstance(item, dict)]
    capabilities = [
        item["capabilityReference"]
        for item in actions
        if isinstance(item.get("capabilityReference"), dict)
        and isinstance(item["capabilityReference"].get("id"), str)
    ]

    registered: dict[str, Any] = {"type": ["RegisteredIdentity"], "id": subject}
    name = entity.get("legalName") or entity.get("name")
    if isinstance(name, str):
        registered["registeredName"] = name
    findings.append(
        Finding(
            REQUIRED,
            f"{SUBJECT}/registeredId",
            "(nothing in the source)",
            "UNTP identifies the entity by its number in the register. The recognition "
            "names the entity by its DID and lists it; it gives no registration number, "
            "and one taken from an address would be a guess.",
        )
    )
    findings.append(
        Finding(
            REQUIRED,
            f"{SUBJECT}/registeredDate",
            "(nothing in the source)",
            "UNTP wants the date the entity was first registered. The recognition states "
            "when this edition, and each recognised action, is valid -- not when the "
            "entity was first recognised.",
        )
    )
    same_as = entity.get("sameAs")
    if isinstance(same_as, list) and same_as and isinstance(same_as[0], str):
        registered["publicInformation"] = same_as[0]
    registered["idScheme"] = {
        "type": ["IdentifierScheme"],
        "id": source.get("id"),
        "name": source.get("name"),
    }
    findings.append(
        Finding(
            JUDGEMENT,
            f"{SUBJECT}/idScheme",
            "(the recognition itself)",
            "UNTP names the register the entity is listed in. The recognition is that "
            "list, so it serves as the register -- a reading, since it names no "
            "identifier scheme of its own.",
        )
    )
    registrar = _party(source.get("issuer"))
    if registrar is not None:
        registered["registrar"] = registrar

    kinds = {str(item.get("type")) for item in capabilities}
    every_action_scoped = bool(capabilities) and len(capabilities) == len(actions)
    if every_action_scoped and kinds == {"AccreditationScope"}:
        registered["registerType"] = "accreditation"
        findings.append(
            Finding(
                JUDGEMENT,
                f"{SUBJECT}/registerType",
                "recognizedTo[].capabilityReference",
                "Every capability the entity is recognised for is an accreditation "
                "scope, so the register is a register of accreditations, which is what "
                "UNTP's accreditation code names.",
            )
        )
    else:
        findings.append(
            Finding(
                REQUIRED,
                f"{SUBJECT}/registerType",
                "(the arrangement behind the recognition)",
                "UNTP's register types are product, facility, business, trademark, land "
                "and accreditation. This recognition rests on an arrangement none of them "
                "names -- peer recognition, not accreditation -- and choosing the nearest "
                "would misstate it.",
            )
        )

    if capabilities:
        registered["registrationScope"] = list(
            dict.fromkeys(item["id"] for item in capabilities)
        )
        if any(item.get("digestMultibase") for item in capabilities):
            findings.append(
                Finding(
                    DROPPED,
                    f"{SUBJECT}/registrationScope",
                    "recognizedTo[].capabilityReference.digestMultibase",
                    "The scopes arrive as bare addresses, so the digests that pin the "
                    "version of each scope the entity was recognised under do not.",
                )
            )
    for member, reason in (
        (
            "action",
            "What the entity is recognised to do -- issue, accredit, evaluate -- has no "
            "member. A scope says where, not what.",
        ),
        (
            "outputValidation",
            "The schemas a document issued under the recognition must satisfy, pinned "
            "by digest, have no member. They are what [chapter](#verification) checks "
            "a certificate against, so this is the part of a recognition a verifier "
            "can act on.",
        ),
        (
            "validFrom",
            "Each recognised action carries its own validity; the anchor has only the "
            "credential's, so an action that lapses early cannot say so.",
        ),
    ):
        if any(member in item for item in actions):
            findings.append(
                Finding(DROPPED, "(no equivalent)", f"recognizedTo[].{member}", reason)
            )
    if isinstance(entity.get("url"), str):
        findings.append(
            Finding(
                DROPPED,
                SUBJECT,
                "credentialSubject.url",
                "The entity's own website has no member on a registered identity.",
            )
        )

    credential = _envelope(
        source,
        registered,
        findings,
        untp_type=UNTP_DIA_TYPE,
        identifier=f"{source.get('id')}#{subject}",
        name=f"{source.get('name')}: {entity.get('name') or subject}",
    )
    return Projection(credential, tuple(findings))


#: Which projection handles which certificate type. A recognition goes through
#: :func:`project_recognition` instead, since it needs an entity named.
PROJECTIONS: dict[str, Callable[[dict[str, Any], Lookup | None], Projection]] = {
    "CalibrationCertificateCredential": project_calibration_certificate,
    "ProductConformityCredential": project_product_conformity,
}


def project(
    source: dict[str, Any], lookup: Lookup | None = None, subject: str | None = None
) -> Projection:
    """Project whichever credential type this is into UNTP terms.

    Args:
        source: The source credential.
        lookup: Resolves a URL to the document published there. See
            :func:`project_calibration_certificate`.
        subject: For a recognition, the DID of the entity to anchor.

    Returns:
        The projection.

    Raises:
        ValueError: If no projection is defined for this credential type, or a
            recognition's entity is missing or unknown.
    """
    types = source.get("type", [])
    if "RecognizedEntityCredential" in types:
        return project_recognition(source, subject)
    for name in types:
        handler = PROJECTIONS.get(name)
        if handler is not None:
            return handler(source, lookup)
    raise ValueError(f"no UNTP projection for {source.get('type')}")


def _attestation(
    source: dict[str, Any],
    *,
    level: str,
    attestation_type: str,
    party: Any,
    assessment: dict[str, Any],
    endorsements: list[dict[str, Any] | None],
    scheme_reason: str,
    source_member: str,
    findings: list[Finding],
) -> dict[str, Any]:
    """Build the ConformityAttestation both projections share the shape of.

    Args:
        source: The source credential.
        level: The ``assessmentLevel`` code, already recorded as a judgement.
        attestation_type: The ``attestationType`` code.
        party: The owner or holder reference the certificate was issued to.
        assessment: The one ConformityAssessment.
        endorsements: The endorsements that could be built; None entries are skipped.
        scheme_reason: Why ``referenceScheme`` is left out.
        source_member: The source member the attestation is drawn from, for findings.
        findings: The findings so far, appended to.

    Returns:
        The attestation.
    """
    issued_to = _party(party)
    attestation: dict[str, Any] = {
        "type": ["ConformityAttestation"],
        "id": _fragment(source, "attestation"),
        "name": source.get("name"),
        "assessorLevel": _assessor_level(source, issued_to),
        "assessmentLevel": level,
        "attestationType": attestation_type,
    }
    if issued_to is not None:
        attestation["issuedToParty"] = issued_to
    else:
        findings.append(
            Finding(
                REQUIRED,
                f"{SUBJECT}/issuedToParty",
                f"{source_member} owner or holder",
                "UNTP requires the party the attestation was issued to, and the "
                "certificate names none.",
            )
        )
    built = [endorsement for endorsement in endorsements if endorsement is not None]
    if built:
        attestation["authorisation"] = built
    findings.append(
        Finding(
            REQUIRED, f"{SUBJECT}/referenceScheme", "(nothing in the source)", scheme_reason
        )
    )
    attestation["conformityAssessment"] = [assessment]
    return attestation


def _assessor_level(source: dict[str, Any], issued_to: dict[str, Any] | None) -> str:
    """Say whether the assessment was made by a third party, from who issued it to whom.

    Derived rather than chosen: an issuer that is not the party the certificate was
    issued to assessed something that is not its own.

    Args:
        source: The source credential.
        issued_to: The rendered party the attestation was issued to.

    Returns:
        ``3rdParty``, ``self``, or ``unspecified`` when either side is unnamed.
    """
    issuer = source.get("issuer")
    issuer_id = issuer.get("id") if isinstance(issuer, dict) else issuer
    if not isinstance(issuer_id, str) or issued_to is None:
        return "unspecified"
    return "self" if issued_to.get("id") == issuer_id else "3rdParty"


def _assessment_level(calibration: dict[str, Any]) -> tuple[str, str]:
    """Choose the UNTP assurance level a calibration was performed under.

    Args:
        calibration: The ``calibration`` member of a calibration certificate.

    Returns:
        The code, and why it was chosen, for the judgement finding.
    """
    if calibration.get("mraLogoAsserted"):
        return (
            "authority-peer",
            "UNTP has no code for the CIPM MRA. The nearest is authority-peer, peer "
            "assessment under a government or intergovernmental mandate: CMCs are "
            "peer-reviewed under the CIPM, an intergovernmental body. authority-globalmra "
            "would be wrong, since UNTP defines it as accreditation under the Global "
            "Accreditation Cooperation MRA.",
        )
    if calibration.get("accredited"):
        return (
            "authority-globalmra",
            "The certificate rests on an accreditation, and the accreditation body behind "
            "it is a signatory of the Global Accreditation Cooperation MRA, which is how "
            "UNTP defines authority-globalmra.",
        )
    return (
        "no-endorsement",
        "The certificate claims neither the CIPM MRA nor an accreditation.",
    )


def _recognition(
    source: dict[str, Any], lookup: Lookup | None, findings: list[Finding]
) -> dict[str, Any] | None:
    """Render the recognition behind the issuer as an Endorsement.

    UNTP describes ``authorisation`` as the authority under which a claim is issued. In
    this world that is the recognition the issuer's ``recognizedIn`` points at, and the
    authority is whoever issued that recognition -- named by reading it, never by
    guessing from its address.

    Args:
        source: The source credential.
        lookup: Resolves the recognition's URL, or None.
        findings: The findings so far, appended to.

    Returns:
        The Endorsement, or None when it cannot be named.
    """
    issuer = source.get("issuer")
    reference = issuer.get("recognizedIn") if isinstance(issuer, dict) else None
    if not isinstance(reference, dict) or not isinstance(reference.get("id"), str):
        return None
    return _endorsement(reference["id"], None, lookup, findings, "issuer.recognizedIn")


def _accreditation(
    capability: Any, lookup: Lookup | None, findings: list[Finding], member: str
) -> dict[str, Any] | None:
    """Render the accreditation scope a certificate was issued within as an Endorsement.

    Args:
        capability: The ``capabilityReference`` member of the source credential.
        lookup: Resolves the scope's URL, or None.
        findings: The findings so far, appended to.
        member: The source member, for findings.

    Returns:
        The Endorsement, or None when it cannot be named.
    """
    if not isinstance(capability, dict) or not isinstance(capability.get("id"), str):
        return None
    return _endorsement(
        capability["id"], capability.get("digestMultibase"), lookup, findings, member
    )


def _endorsement(
    url: str,
    digest: str | None,
    lookup: Lookup | None,
    findings: list[Finding],
    member: str,
) -> dict[str, Any] | None:
    """Build an Endorsement whose authority is the issuer of the document it rests on.

    Args:
        url: The recognition or scope the endorsement rests on.
        digest: Its ``digestMultibase`` in the source, if the source pins it.
        lookup: Resolves ``url``, or None.
        findings: The findings so far, appended to.
        member: The source member, for findings.

    Returns:
        The Endorsement, or None -- recorded -- when its issuer cannot be read.
    """
    document = lookup(url) if lookup is not None else None
    authority = _party(document.get("issuer")) if isinstance(document, dict) else None
    if authority is None:
        findings.append(
            Finding(
                DROPPED,
                f"{SUBJECT}/authorisation",
                member,
                "The authority is named only inside the document this points at, and the "
                "projection could not read it. Naming it from the address alone would be a "
                "guess, so the endorsement is left out.",
            )
        )
        return None
    name = document.get("name") if isinstance(document.get("name"), str) else url
    return {
        "name": name,
        "issuingAuthority": authority,
        "endorsementEvidence": _link(url, name, digest),
    }


def _envelope(
    source: dict[str, Any],
    subject: dict[str, Any],
    findings: list[Finding],
    *,
    untp_type: list[str] = UNTP_DCC_TYPE,
    identifier: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Wrap a credential subject in the UNTP credential envelope.

    ``credentialSchema`` does not travel: it names the data model of the source type,
    which the UNTP document is not an instance of. The status entry does, exactly as the
    source states it.

    Args:
        source: The source credential, for the members that carry across unchanged.
        subject: The ConformityAttestation or RegisteredIdentity to carry.
        findings: The findings so far, appended to.
        untp_type: The UNTP type array of the document.
        identifier: The document's identifier, when it is not the source's own -- one
            recognition becomes several anchors, and each needs its own.
        name: The document's name, when it is not the source's own.

    Returns:
        The unsecured UNTP credential.
    """
    credential: dict[str, Any] = {
        "@context": list(UNTP_CONTEXT),
        "type": list(untp_type),
        "id": identifier if identifier is not None else source.get("id"),
        "issuer": _issuer(source),
    }
    if name is None and isinstance(source.get("name"), str):
        name = source["name"]
    if name is not None:
        credential["name"] = name
    else:
        findings.append(
            Finding(
                REQUIRED,
                "name",
                "name",
                "UNTP requires a name for the credential, and the source has none.",
            )
        )
    for member in ("validFrom", "validUntil"):
        if member in source:
            credential[member] = source[member]
    status = source.get("credentialStatus")
    if isinstance(status, dict):
        credential["credentialStatus"] = dict(status)
        if not isinstance(status.get("statusListIndex"), int):
            findings.append(
                Finding(
                    CONFLICT,
                    "credentialStatus/statusListIndex",
                    "credentialStatus.statusListIndex",
                    "Carried as the source states it. The W3C Bitstring Status List "
                    "Recommendation says the index MUST be \"an arbitrary size integer "
                    "greater than or equal to 0, expressed as a string in base 10\", and "
                    "UNTP's own description of the member says the same, but its schema "
                    "types it as an integer. Converting it would make the document break "
                    "the W3C Recommendation this project answers to.",
                )
            )
    credential["credentialSubject"] = subject
    return credential


def _issuer(source: dict[str, Any]) -> dict[str, Any]:
    """Render the issuer as an UNTP CredentialIssuer.

    ``recognizedIn`` is not carried here. UNTP puts no such member on the issuer; the
    equivalent statement goes on the attestation as ``authorisation``.

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


def _party(reference: Any) -> dict[str, Any] | None:
    """Render an organisation reference as an UNTP Party.

    Typed, because the 0.7.0 context defines a party's members only inside the Party
    type; an untyped party would have them dropped on expansion.

    Args:
        reference: An owner, holder or issuer reference.

    Returns:
        The Party, or None unless the reference has both an identifier and a name.
    """
    if not isinstance(reference, dict):
        return None
    identifier, name = reference.get("id"), reference.get("name")
    if not isinstance(identifier, str) or not isinstance(name, str):
        return None
    return {"type": ["Party"], "id": identifier, "name": name}


def _criterion(capability: Any) -> dict[str, Any] | None:
    """Render the capability a calibration was issued within as an UNTP Criterion.

    A CMC is what the certificate is checked against in the verification chapter,
    through its ``outputValidation`` schema, so it serves as the criterion. So does an
    accreditation scope, which lists the laboratory's CMCs.

    Args:
        capability: The ``capabilityReference`` member of the source credential.

    Returns:
        The Criterion, or None when there is nothing to render.
    """
    if not isinstance(capability, dict) or not isinstance(capability.get("id"), str):
        return None
    labels = {"KcdbCmcEntry": "CMC", "AccreditationScope": "Accreditation scope"}
    identifier = str(capability.get("identifier") or capability["id"])
    label = labels.get(str(capability.get("type")))
    return {
        "type": ["Criterion"],
        "id": capability["id"],
        "name": f"{label} {identifier}" if label else identifier,
    }


def _performance(
    result: dict[str, Any],
    calibration: dict[str, Any],
    index: int,
    findings: list[Finding],
) -> dict[str, Any]:
    """Render one calibration result as an UNTP Performance.

    Args:
        result: One entry of ``calibration.results``.
        calibration: The ``calibration`` member, for the measurand and the unit.
        index: The result's position, which is also its position in the output.
        findings: The findings so far, appended to.

    Returns:
        The Performance.
    """
    path = f"{ASSESSMENT}/assessedPerformance/{index}"
    performance: dict[str, Any] = {}
    measurand = calibration.get("measurand")
    if measurand is not None:
        performance["metric"] = {"type": ["PerformanceMetric"], "name": str(measurand)}
        findings.append(
            Finding(
                REQUIRED,
                f"{path}/metric/id",
                "calibration.measurand",
                f"UNTP identifies a metric by URI. The certificate names its measurand "
                f"with a local code, {measurand}, and there is no identifier to put there: "
                f"digital identifiers for quantities are still being defined at ISO and "
                f"IEC. Supplying one would be inventing it.",
            )
        )

    value = result.get("value")
    expanded = result.get("expandedUncertainty")
    measure: dict[str, Any] = {}
    if isinstance(value, (int, float)):
        rounded = isinstance(expanded, (int, float))
        measure["value"] = rounded_to_uncertainty(value, expanded) if rounded else value
    symbol = str(result.get("unit") or calibration.get("unit") or "")
    code = REC20.get(symbol)
    if code is not None:
        measure["unit"] = code
        findings.append(
            Finding(
                JUDGEMENT,
                f"{path}/measure/unit",
                f"calibration.results[{index}].unit",
                f"Translated from the symbol {symbol} to the UNECE Recommendation 20 code "
                f"{code}, which the context expands against UN/CEFACT's code list. The SI "
                f"identifier the BIPM publishes for the same unit is a different register, "
                f"and UNTP has no member for it.",
            )
        )
    else:
        findings.append(
            Finding(
                REQUIRED,
                f"{path}/measure/unit",
                f"calibration.results[{index}].unit",
                f"UNTP requires a UNECE Recommendation 20 code, and {symbol or 'no unit'} "
                f"has no entry in this projection's table. Passing the symbol through "
                f"would state a code UNTP does not have.",
            )
        )
    performance["measure"] = measure
    if isinstance(expanded, (int, float)):
        findings.append(
            Finding(
                DROPPED,
                f"{path}/measure",
                f"calibration.results[{index}].expandedUncertainty",
                "Measure is additionalProperties: false and holds a value, a unit and two "
                "tolerances. A tolerance is a limit -- UNTP's own example reads \"10kg + "
                "0.1kg\" -- where an Expanded Uncertainty at k=2 is a coverage interval, "
                "so writing one into the other would restate a 95 per cent statement as a "
                "certainty. The value travels without it, rounded to the decimal place the "
                "certificate reports, so that the digits a floating-point computation "
                "leaves behind do not read as precision; a JSON number cannot keep "
                "trailing zeros.",
            )
        )
    return performance


def _product(
    subject: dict[str, Any], findings: list[Finding], *, item_number: bool
) -> dict[str, Any]:
    """Render the credential subject as an UNTP ProductVerification.

    Args:
        subject: The ``credentialSubject`` of the source credential.
        findings: The findings so far, appended to.
        item_number: Whether ``serialNumber`` identifies one item. True for an instrument
            that was calibrated; False for a product certified as a type, where the member
            states what the certificate covers rather than identifying anything.

    Returns:
        The ProductVerification object.
    """
    product: dict[str, Any] = {"type": ["Product"]}
    for member, target in (("id", "id"), ("name", "name"), ("model", "modelNumber")):
        value = subject.get(member)
        if isinstance(value, str):
            product[target] = value
    serial = subject.get("serialNumber")
    if isinstance(serial, str):
        if item_number:
            product["itemNumber"] = serial
        else:
            findings.append(
                Finding(
                    DROPPED,
                    f"{ASSESSMENT}/assessedProduct/0/product",
                    "credentialSubject.serialNumber",
                    f"The certificate covers a type, and the member says so -- "
                    f"\"{serial}\" -- rather than identifying an item. UNTP's item, batch "
                    f"and model numbers are all identifiers, so it has no place.",
                )
            )
    if isinstance(subject.get("manufacturer"), str):
        findings.append(
            Finding(
                DROPPED,
                f"{ASSESSMENT}/assessedProduct/0/product",
                "credentialSubject.manufacturer",
                "The product in a conformity assessment is an identifier, a name and three "
                "kinds of number. Who made it has no member here.",
            )
        )
    return {"product": product}


def _topic(key: str) -> dict[str, Any]:
    """Render one of UNTP's conformity topics.

    Args:
        key: The topic's local name in UNTP's vocabulary, a key of :data:`TOPICS`.

    Returns:
        The ConformityTopic.
    """
    return {
        "type": ["ConformityTopic"],
        "id": f"{TOPIC_VOCABULARY}{key}",
        "name": TOPICS[key],
    }


def _link(url: str, name: str, digest: str | None) -> dict[str, Any]:
    """Render a reference as an UNTP Link.

    No ``linkType``: UNTP 0.7.0 publishes no code list for it, and a made-up one would be
    exactly the plausible value the projection does not supply.

    Args:
        url: The target.
        name: A name for the target.
        digest: The target's ``digestMultibase``, if the source pins it.

    Returns:
        The Link.
    """
    link: dict[str, Any] = {"linkURL": url, "linkName": name}
    if digest:
        link["digestMultibase"] = digest
    return link


def _fragment(source: dict[str, Any], name: str) -> str | None:
    """Derive an identifier for a node inside the credential from the credential's own.

    The credential, the attestation it carries and the assessment inside that are three
    things, and one identifier for all of them would merge them into one node for any
    reader that treats the document as linked data.

    Args:
        source: The source credential.
        name: The fragment.

    Returns:
        The credential identifier with the fragment, or None when it has none.
    """
    identifier = source.get("id")
    return f"{identifier}#{name}" if isinstance(identifier, str) else None


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
