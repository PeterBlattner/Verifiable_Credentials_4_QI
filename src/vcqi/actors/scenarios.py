"""Builds the whole demonstration world: every credential, signed and published.

The world is one supply chain followed end to end.

A national metrology institute calibrates the 10 kilohm transfer standard of an
accredited calibration laboratory and issues a certificate carrying the CIPM MRA logo.
The laboratory uses that standard to calibrate the reference multimeter of a testing
laboratory, and its certificate states what it inherited from the institute and what it
added of its own. The testing laboratory measures a kettle with that multimeter and
issues a test report. A certification body issues a certificate of conformity on the
strength of the report. A market surveillance authority in an importing country meets
the certificate of conformity, knows none of these organisations, and trusts only the
BIPM and Global ACI.

Two independent structures run through that chain, and keeping them apart is the point
of the whole demonstration:

*Recognition* runs upward from any issuer to a trust anchor, through
``RecognizedEntityCredential`` documents. It answers "may this organisation issue this
kind of document at all?"

*Traceability* runs downward from the SI through each calibration, through
``traceableTo`` references. It answers "where does this number come from, and what is
its uncertainty?"

Everything is built from a fixed seed at fixed timestamps, so the whole world is
reproducible byte for byte.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vcqi.crypto.dataintegrity import ProofTrace, sign_document
from vcqi.crypto.xmldsig import C14N_ALGORITHM, SIGNATURE_ALGORITHM
from vcqi.domain import accreditation as accreditation_registry
from vcqi.domain import arrangement as arrangement_registry
from vcqi.domain import kcdb as kcdb_registry
from vcqi.domain.engine import mu
from vcqi.domain.instruments import SHARED_REFERENCE_PAIR, instrument_by_id
from vcqi.domain.oiml import RECOMMENDATIONS, instrument_type_by_id, recommendation_by_id
from vcqi.domain.dcc import to_dcc_xml
from vcqi.domain.external_dcc import EXTERNAL_DCC_INDEX, external_dcc_bytes
from vcqi.domain.gtc_archive import build_gtc_archive
from vcqi.domain.uncertainty import (
    MeasurementResult,
    evaluate,
    from_certificate,
    from_expanded_uncertainty,
    from_quantity,
    normal,
    seeded_input_id,
    rectangular,
    to_unclib_xml,
)
from vcqi.actors.registry import ACTORS, actor_by_did, actor_key, did_document, whois_url
from vcqi.vc.model import (
    CREDENTIAL_CONTEXT,
    artefact_document,
    calibration_certificate_credential,
    credential_reference,
    external_document_credential,
    issuer_reference,
    oiml_certificate_credential,
    product_conformity_credential,
    recognized_action,
    recognized_entity_credential,
    status_entry,
    test_report_credential,
    type_evaluation_report_credential,
    uncertainty_representations,
)
from vcqi.vc.resolver import DocumentStore
from vcqi.vc.schema import (
    calibration_certificate_schema,
    schema_reference,
    test_report_schema,
)
from vcqi.vc.status import BitstringStatusList, status_list_credential

__all__ = ["World", "build_world", "BIPM_RECOGNITION", "GLOBAL_ACI_RECOGNITION", "SAS_RECOGNITION"]

# Addresses are fixed in advance because credentials reference each other by URL and
# some of those references point forward in build order.
BIPM_RECOGNITION = "https://bipm.example/recognition/cipm-mra-signatories-2026"
GLOBAL_ACI_RECOGNITION = "https://global-aci.example/recognition/global-aci-mra-signatories-2026"
SAS_RECOGNITION = "https://sas.example/recognition/accredited-bodies-2026"

METAS_CERTIFICATE = "https://metas.example/certificates/METAS-2026-0417"
#: The one certificate in this world that exists only as an external document.
METAS_EXTERNAL = "https://metas.example/certificates/METAS-2026-0420"
CALLAB_CERTIFICATE = "https://callab.example/certificates/AC-2026-1182"
METAS_CHECK_A = "https://metas.example/certificates/METAS-2026-0418"
METAS_CHECK_B = "https://metas.example/certificates/METAS-2026-0419"
TESTLAB_REPORT = "https://testlab.example/reports/HTS-2026-3391"
CAB_CERTIFICATE = "https://cab.example/certificates/CPC-2026-0055"

OIML_IA_RECOGNITION = "https://oiml.example/recognition/issuing-authorities-2021"
OIML_TL_RECOGNITION = "https://oiml.example/recognition/test-laboratories-2021"
OIML_EVALUATION = "https://testlab.example/oiml/evaluations/HTS-TE-2024-0114"
OIML_CERTIFICATE = "https://legal-ia.example/oiml/R46-2024-CH1-0037"

BIPM_STATUS = "https://bipm.example/status/recognition"
GLOBAL_ACI_STATUS = "https://global-aci.example/status/recognition"
SAS_STATUS = "https://sas.example/status/accreditation"
METAS_STATUS = "https://metas.example/status/certificates"
CALLAB_STATUS = "https://callab.example/status/certificates"
TESTLAB_STATUS = "https://testlab.example/status/reports"
CAB_STATUS = "https://cab.example/status/certificates"
# Two lists, and two purposes. A recognition is withdrawn by suspending it; a
# certificate is withdrawn by revoking it. Collapsing them would make "this document is
# listed" mean two different things depending on which document it was.
#
# The laboratory's type evaluation reports go on the revocation list it already has for
# its test reports. One issuer, one list: `_register` keys a status list by the issuer's
# domain, so a second list for the same actor would silently replace the first.
OIML_RECOGNITION_STATUS = "https://oiml.example/status/recognition"
OIML_CERTIFICATE_STATUS = "https://legal-ia.example/status/certificates"

CMC_SCHEMA_BASE = "https://bipm.example/schemas"
ACCREDITATION_SCHEMA_BASE = "https://sas.example/schemas"
OIML_SCHEMA_BASE = "https://oiml.example/schemas"

#: Position of each credential in the status list of its issuer.
STATUS_INDEX = {
    BIPM_RECOGNITION: 1,
    GLOBAL_ACI_RECOGNITION: 1,
    SAS_RECOGNITION: 1,
    METAS_CERTIFICATE: 7,
    METAS_EXTERNAL: 12,
    CALLAB_CERTIFICATE: 3,
    TESTLAB_REPORT: 5,
    CAB_CERTIFICATE: 2,
    OIML_IA_RECOGNITION: 1,
    OIML_TL_RECOGNITION: 2,
    OIML_EVALUATION: 6,
    OIML_CERTIFICATE: 4,
}


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """Build a UTC instant.

    Args:
        year: Calendar year.
        month: Calendar month.
        day: Day of month.
        hour: Hour of day.
        minute: Minute of hour.

    Returns:
        The instant, with UTC attached.
    """
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _stamp(moment: datetime) -> str:
    """Format an instant as an XML Schema dateTime in UTC.

    Args:
        moment: The instant to format.

    Returns:
        The timestamp, for example ``2026-02-12T09:00:00Z``.
    """
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


# Fixed timestamps for the whole scenario.
RECOGNITION_FROM = _utc(2026, 1, 1)
RECOGNITION_UNTIL = _utc(2031, 1, 1)
METAS_CALIBRATED_ON = "2026-02-10"
METAS_ISSUED = _utc(2026, 2, 12, 9, 0)
METAS_EXPIRES = _utc(2027, 2, 12, 9, 0)
CALLAB_CALIBRATED_ON = "2026-03-18"
CALLAB_ISSUED = _utc(2026, 3, 20, 10, 30)
CALLAB_EXPIRES = _utc(2027, 3, 20, 10, 30)
TESTLAB_TESTED_ON = "2026-05-06"
TESTLAB_ISSUED = _utc(2026, 5, 8, 14, 0)
TESTLAB_EXPIRES = _utc(2031, 5, 8, 14, 0)
CAB_ISSUED_ON = "2026-06-01"
CAB_ISSUED = _utc(2026, 6, 1, 8, 0)
CAB_EXPIRES = _utc(2031, 5, 31, 8, 0)

# The legal-metrology layer has its own timeline, and it has to. OIML has run its
# certification system for decades and the recognitions here predate the 2026 dates the
# rest of the world uses -- so an OIML certificate issued in 2024 is issued under a
# recognition that already existed, which is the whole point. Dating them from 2026
# alongside Global ACI made the action check reject that certificate, correctly.
OIML_RECOGNITION_FROM = _utc(2021, 4, 1)
OIML_RECOGNITION_UNTIL = _utc(2031, 4, 1)
OIML_EVALUATED_ON = "2024-08-14"
OIML_EVALUATION_ISSUED = _utc(2024, 9, 2, 11, 0)
OIML_EVALUATION_EXPIRES = _utc(2034, 9, 2, 11, 0)
OIML_CERTIFICATE_ISSUED_ON = "2024-09-30"
OIML_CERTIFICATE_ISSUED = _utc(2024, 9, 30, 9, 0)
# A type certificate is valid for about a decade, where a calibration certificate is
# valid for a year. That difference is what makes long-term validation bite here.
OIML_CERTIFICATE_EXPIRES = _utc(2034, 9, 30, 9, 0)

#: The instant the demonstration treats as "now" when nothing else is specified.
DEMO_NOW = _utc(2026, 9, 4, 12, 0)


@dataclass
class World:
    """Everything the demonstration publishes, indexed for the interface.

    Attributes:
        store: Every document, addressed the way a verifier would address it.
        credentials: The signed credentials, by short name.
        traces: The signing trace of each credential, by the same short name.
        results: The evaluated measurement results, by short name.
        schemas: The generated JSON Schemas, by URL.
    """

    store: DocumentStore = field(default_factory=DocumentStore)
    credentials: dict[str, dict[str, Any]] = field(default_factory=dict)
    traces: dict[str, ProofTrace] = field(default_factory=dict)
    results: dict[str, MeasurementResult] = field(default_factory=dict)
    schemas: dict[str, dict[str, Any]] = field(default_factory=dict)
    artefacts: dict[str, tuple[str, bytes]] = field(default_factory=dict)

    def publish_artefacts(self, artefacts: dict[str, tuple[str, bytes]]) -> None:
        """Publish dependency data that a credential references rather than carries.

        Args:
            artefacts: Raw payloads keyed by address, with their media type.
        """
        for address, (media_type, payload) in artefacts.items():
            self.artefacts[address] = (media_type, payload)
            self.store.publish(
                address, artefact_document(media_type, payload), "uncertainty-data"
            )

    def credential(self, name: str) -> dict[str, Any]:
        """Return one signed credential by short name.

        Args:
            name: The short name, for example ``metas-calibration``.

        Returns:
            The signed credential.

        Raises:
            KeyError: If no credential is registered under that name.
        """
        return self.credentials[name]

    def _register(
        self,
        name: str,
        credential: dict[str, Any],
        trace: ProofTrace,
        kind: str = "credential",
    ) -> dict[str, Any]:
        """Record a signed credential and publish it at its own identifier.

        Args:
            name: Short name for the interface.
            credential: The signed credential.
            trace: The signing trace.
            kind: What sort of document this is, for the retrieval log.

        Returns:
            The credential, so callers can chain.
        """
        self.credentials[name] = credential
        self.traces[name] = trace
        self.store.publish(credential["id"], credential, kind)
        return credential


def _national_standard() -> Any:
    """Return the realisation of the national standard, as one persistent quantity.

    The institute has one 10 kilohm national standard, and every comparison it makes is
    against that one artefact. Modelling it as a single quantity rather than declaring
    it afresh in each budget is not a convenience: two certificates issued against it
    are genuinely correlated through it, and that is only true if it is genuinely the
    same quantity.

    Returns:
        The uncertain number standing for the realised value, in ohm.
    """
    return mu.ufloat(
        10000.0007,
        4.6e-4,
        id=seeded_input_id("National standard, scaled from the quantum Hall resistance", "METAS"),
        desc="National standard, scaled from the quantum Hall resistance",
    )


def _metas_result() -> MeasurementResult:
    """Evaluate the calibration the national metrology institute performed.

    The institute realises the ohm itself, so the top contribution is its own national
    standard rather than a certificate from anyone else. This is where the traceability
    chain ends.

    Returns:
        The measured resistance of the transfer standard with its budget, in ohm.
    """
    contributions = [
        from_quantity(
            "national_standard",
            "National standard, scaled from the quantum Hall resistance",
            _national_standard(),
            unit="ohm",
        ),
        normal("ratio", "Cryogenic current comparator ratio", 1.00000005, 2.0e-8),
        rectangular(
            "temperature", "Temperature correction to 23 degC", 0.0, 2.0e-4, unit="ohm"
        ),
        normal("repeatability", "Repeatability of the comparison", 0.0, 2.0e-4, unit="ohm"),
    ]
    return evaluate(
        lambda q: q["national_standard"] * q["ratio"] + q["temperature"] + q["repeatability"],
        contributions,
        unit="ohm",
        context="METAS-2026-0417",
    )


def _callab_result(
    parent: MeasurementResult,
    *,
    ratio: float = 1.0000031,
    ratio_uncertainty: float = 2.6e-6,
    drift_half_width: float = 5.0e-4,
    temperature_half_width: float = 2.0e-4,
    context: str = "AC-2026-1182",
    classical: bool = False,
) -> MeasurementResult:
    """Evaluate a calibration the accredited laboratory performed.

    The first contribution is the result the institute certified. How it is entered is
    the whole subject of chapter 6.

    In the default *dependency* mode the laboratory loads the dependency representation
    from the certificate, so the input quantities of the institute arrive with their own
    identifiers and remain recognisable in everything computed from them.

    In *classical* mode the laboratory has only the printed value and Expanded
    Uncertainty, so it declares a fresh input quantity from those two numbers. The
    Expanded Uncertainty that comes out is identical. What is lost is the ability of
    anyone downstream to see that this result and another one rest on the same standard.

    Args:
        parent: The result from the certificate of the national metrology institute.
        ratio: The bridge ratio for this particular comparison.
        ratio_uncertainty: The Standard Uncertainty of that ratio.
        drift_half_width: Half-width of the drift interval, in ohm.
        temperature_half_width: Half-width of the temperature interval, in ohm.
        context: The certificate this budget belongs to, which scopes the identifiers
            of the effects the laboratory declares for itself. Two comparisons made with
            the same transfer standard share that standard and nothing else.
        classical: Enter the parent as a value and an Expanded Uncertainty instead of
            loading its dependency representation.

    Returns:
        The measured resistance with its budget, in ohm.
    """
    if classical:
        reference = from_expanded_uncertainty(
            "transfer_standard",
            "Transfer standard, from certificate METAS-2026-0417",
            parent.value,
            parent.expanded_uncertainty,
            coverage_factor=parent.coverage_factor,
            unit="ohm",
            note=METAS_CERTIFICATE,
        )
    else:
        reference = from_certificate(
            "transfer_standard",
            "Transfer standard, from certificate METAS-2026-0417",
            to_unclib_xml(parent),
            unit="ohm",
            note=METAS_CERTIFICATE,
        )

    contributions = [
        reference,
        normal("ratio", "Resistance bridge ratio", ratio, ratio_uncertainty),
        rectangular(
            "drift",
            "Drift of the transfer standard since its calibration",
            0.0,
            drift_half_width,
            unit="ohm",
        ),
        rectangular(
            "temperature",
            "Temperature correction to 23 degC",
            0.0,
            temperature_half_width,
            unit="ohm",
        ),
    ]
    return evaluate(
        lambda q: q["transfer_standard"] * q["ratio"] + q["drift"] + q["temperature"],
        contributions,
        unit="ohm",
        context=context,
    )



def _dcc_for(
    result: MeasurementResult,
    *,
    certificate_number: str,
    performed_on: str,
    issued: datetime,
    measurand: str,
    conditions: str,
    instrument: Any,
    laboratory: Any,
    customer: Any,
    reference_certificate: str | None = None,
) -> str:
    """Express one calibration as a PTB/DKD DCC.

    Every calibration certificate here carries one, alongside its readable subject and
    its dependency representations. The point of carrying all of them is that they are
    not alternatives: the dependency representations describe the result, and the PTB/DKD
    PTB/DKD DCC describes the document the result appears in.

    Args:
        result: The evaluated measurement result.
        certificate_number: The certificate number.
        performed_on: Date the calibration was performed.
        issued: When the certificate was issued.
        measurand: Machine-readable identifier of the measured quantity.
        conditions: The stated measurement conditions.
        instrument: The calibrated artefact.
        laboratory: The issuing organisation.
        customer: The organisation it was issued to.
        reference_certificate: The certificate of the reference standard used, if any.

    Returns:
        The document as an XML string.
    """
    return to_dcc_xml(
        result,
        certificate_number=certificate_number,
        performed_on=performed_on,
        issued_on=issued.strftime("%Y-%m-%d"),
        measurand=measurand,
        conditions=conditions,
        instrument=instrument.to_json(),
        laboratory={"id": laboratory.did, "name": laboratory.legal_name},
        customer={"id": customer.did, "name": customer.legal_name},
        reference_certificate=reference_certificate,
    )


def _build_schemas(world: World) -> dict[str, dict[str, Any]]:
    """Generate and publish the schemas that bound what each entity may issue.

    Args:
        world: The world being built.

    Returns:
        A mapping from a short key to the generated schema.
    """
    schemas: dict[str, dict[str, Any]] = {}

    for entry in kcdb_registry.CMC_ENTRIES:
        schema_id = f"{CMC_SCHEMA_BASE}/calibration-certificate-{entry.identifier}.json"
        schema = calibration_certificate_schema(
            entry.as_capability(),
            schema_id=schema_id,
            title=f"Calibration certificate within CMC {entry.identifier}",
        )
        schemas[entry.identifier] = schema
        world.schemas[schema_id] = schema
        world.store.publish(schema_id, schema, "schema")

    for scope in accreditation_registry.ACCREDITATION_SCOPES:
        slug = scope.identifier.replace(" ", "-")
        schema_id = f"{ACCREDITATION_SCHEMA_BASE}/{slug}.json"
        capability = scope.as_capability()
        if capability is not None:
            schema = calibration_certificate_schema(
                capability,
                schema_id=schema_id,
                title=f"Calibration certificate within accreditation {scope.identifier}",
            )
        elif scope.activity == "Testing":
            schema = test_report_schema(
                schema_id=schema_id,
                title=f"Test report within accreditation {scope.identifier}",
                standard="IEC 60335-1",
            )
        else:
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": schema_id,
                "title": f"Certificate of conformity within accreditation {scope.identifier}",
                "description": (
                    "Requires the certificate to reference at least one test report, so "
                    "that a conformity claim always rests on stated evidence."
                ),
                "type": "object",
                "required": ["type", "credentialSubject"],
                "properties": {
                    "type": {
                        "type": "array",
                        "contains": {"const": "ProductConformityCredential"},
                    },
                    "credentialSubject": {
                        "type": "object",
                        "required": ["conformity"],
                        "properties": {
                            "conformity": {
                                "type": "object",
                                "required": ["standard", "testReports"],
                                "properties": {
                                    "testReports": {"type": "array", "minItems": 1}
                                },
                            }
                        },
                    },
                },
            }
        schemas[scope.identifier] = schema
        world.schemas[schema_id] = schema
        world.store.publish(schema_id, schema, "schema")

    # The OIML schemas. These are what `outputValidation` on the two recognitions points
    # at, and they are the one place in this demonstration where that mechanism has a
    # real document behind it rather than an invented one -- an OIML Recommendation is
    # numbered, edition-controlled and published by somebody else. What is still invented
    # is the schema: the Recommendation is not machine-readable yet, so these encode a
    # reading of it rather than the thing itself. That gap is the chapter 11 item.
    recommendation = recommendation_by_id("R 46")
    assert recommendation is not None

    evaluation_schema_id = f"{OIML_SCHEMA_BASE}/type-evaluation-{recommendation.number.replace(' ', '-')}.json"
    evaluation_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": evaluation_schema_id,
        "title": f"Type evaluation report against {recommendation.identifier}",
        "description": (
            "Requires the report to cite the Recommendation it evaluated against and to "
            "reference the calibration of the equipment it measured with. A type "
            "evaluation that cannot say what it measured with is not traceable, however "
            "well it is signed."
        ),
        "type": "object",
        "required": ["type", "credentialSubject"],
        "properties": {
            "type": {
                "type": "array",
                "contains": {"const": "TypeEvaluationReportCredential"},
            },
            "credentialSubject": {
                "type": "object",
                "required": ["typeEvaluation"],
                "properties": {
                    "typeEvaluation": {
                        "type": "object",
                        "required": [
                            "recommendation",
                            "results",
                            "equipmentTraceability",
                        ],
                        "properties": {
                            "recommendation": {
                                "type": "object",
                                "required": ["identifier"],
                                "properties": {
                                    "identifier": {"const": recommendation.identifier}
                                },
                            },
                            "results": {"type": "array", "minItems": 1},
                            "equipmentTraceability": {"type": "array", "minItems": 1},
                        },
                    }
                },
            },
        },
    }
    schemas["oiml-evaluation"] = evaluation_schema
    world.schemas[evaluation_schema_id] = evaluation_schema
    world.store.publish(evaluation_schema_id, evaluation_schema, "schema")

    certificate_schema_id = f"{OIML_SCHEMA_BASE}/certificate-{recommendation.number.replace(' ', '-')}.json"
    certificate_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": certificate_schema_id,
        "title": f"OIML certificate against {recommendation.identifier}",
        "description": (
            "Requires the certificate to cite the Recommendation, to reference the type "
            "evaluation report it rests on, and to state that it carries no legal "
            "effect. The last of those is a schema requirement rather than a convention "
            "so that a certificate which quietly drops the disclaimer fails validation "
            "instead of reading as an approval."
        ),
        "type": "object",
        "required": ["type", "credentialSubject"],
        "properties": {
            "type": {
                "type": "array",
                "contains": {"const": "OimlCertificateCredential"},
            },
            "credentialSubject": {
                "type": "object",
                "required": ["oimlCertificate"],
                "properties": {
                    "oimlCertificate": {
                        "type": "object",
                        "required": [
                            "certificateNumber",
                            "recommendation",
                            "testReport",
                            "legalEffect",
                        ],
                        "properties": {
                            "recommendation": {
                                "type": "object",
                                "required": ["identifier"],
                                "properties": {
                                    "identifier": {"const": recommendation.identifier}
                                },
                            },
                            "testReport": {
                                "type": "object",
                                "required": ["id", "digestMultibase"],
                            },
                            "legalEffect": {"const": "none"},
                        },
                    }
                },
            },
        },
    }
    schemas["oiml-certificate"] = certificate_schema
    world.schemas[certificate_schema_id] = certificate_schema
    world.store.publish(certificate_schema_id, certificate_schema, "schema")

    return schemas


def _publish_registries(world: World) -> None:
    """Publish the CMC entries and accreditation scopes as retrievable documents.

    Args:
        world: The world being built.
    """
    for recommendation in RECOMMENDATIONS:
        world.store.publish(
            recommendation.url, recommendation.to_json(), "registry-entry"
        )
    for entry in kcdb_registry.CMC_ENTRIES:
        world.store.publish(entry.url, entry.to_json(), "registry-entry")
    for scope in accreditation_registry.ACCREDITATION_SCOPES:
        world.store.publish(scope.url, scope.to_json(), "registry-entry")


def _publish_did_documents(world: World) -> None:
    """Publish a DID document for every actor, at both addresses it resolves from.

    Args:
        world: The world being built.
    """
    for actor in ACTORS:
        document = did_document(actor.did)
        world.store.publish(actor.did, document, "did-document")
        # did:web resolves to a well-known path, and the interface links to it so a
        # reader can see that the identifier really is just a name for a location.
        world.store.publish(
            f"https://{actor.domain}/.well-known/did.json", document, "did-document"
        )


def _status_lists(world: World) -> None:
    """Build and publish an empty status list for every issuer.

    Nothing is revoked or suspended in the base world. The lists exist so that the
    failure demonstrations have something real to flip, rather than simulating
    revocation by deleting a document.

    Args:
        world: The world being built.
    """
    definitions = [
        (BIPM_STATUS, "did:web:bipm.example", "suspension", "Recognition of national metrology institutes"),
        (GLOBAL_ACI_STATUS, "did:web:global-aci.example", "suspension", "Recognition of accreditation bodies"),
        (SAS_STATUS, "did:web:sas.example", "suspension", "Accreditations granted by the accreditation body"),
        (METAS_STATUS, "did:web:metas.example", "revocation", "Calibration certificates of the institute"),
        (CALLAB_STATUS, "did:web:callab.example", "revocation", "Calibration certificates of the laboratory"),
        (TESTLAB_STATUS, "did:web:testlab.example", "revocation", "Test reports and type evaluation reports of the laboratory"),
        (CAB_STATUS, "did:web:cab.example", "revocation", "Certificates of conformity"),
        (OIML_RECOGNITION_STATUS, "did:web:oiml.example", "suspension", "Recognition of Issuing Authorities and Test Laboratories"),
        (OIML_CERTIFICATE_STATUS, "did:web:legal-ia.example", "revocation", "OIML certificates of type evaluation"),
    ]
    for url, did, purpose, description in definitions:
        actor = actor_by_did(did)
        assert actor is not None, f"status list for unknown actor {did}"
        credential = status_list_credential(
            credential_id=url,
            issuer=issuer_reference(did, actor.legal_name),
            valid_from=_stamp(RECOGNITION_FROM),
            status_list=BitstringStatusList(purpose=purpose),
            description=description,
        )
        signed, trace = sign_document(credential, actor_key(did), created=RECOGNITION_FROM)
        world._register(f"status-{actor.domain}", signed, trace, kind="status-list")


def _recognition_credentials(world: World, schemas: dict[str, dict[str, Any]]) -> None:
    """Build the three recognition credentials that form the trust hierarchy.

    Args:
        world: The world being built.
        schemas: The generated schemas, keyed by CMC or accreditation identifier.
    """
    valid_from, valid_until = _stamp(RECOGNITION_FROM), _stamp(RECOGNITION_UNTIL)

    # BIPM recognises national metrology institutes, scoped by their published CMCs.
    institutes = []
    for did in ("did:web:metas.example", "did:web:ptb.example"):
        actor = actor_by_did(did)
        assert actor is not None
        actions = [
            recognized_action(
                "issue",
                "did:web:bipm.example",
                description=(
                    f"Issue calibration certificates for {entry.service} carrying the "
                    f"CIPM MRA logo, within CMC {entry.identifier}."
                ),
                output_validation=schema_reference(schemas[entry.identifier]),
                capability_reference={
                    "id": entry.url,
                    "type": "KcdbCmcEntry",
                    "identifier": entry.identifier,
                },
                valid_from=valid_from,
                valid_until=valid_until,
            )
            for entry in kcdb_registry.cmcs_for_institute(did)
        ]
        institutes.append(
            {
                "id": did,
                "type": "RecognizedEntity",
                "name": actor.name,
                "legalName": actor.legal_name,
                "url": actor.url,
                "description": actor.description,
                "sameAs": [f"https://bipm.example/nmi/{actor.country}"],
                "recognizedTo": actions,
            }
        )

    bipm = actor_by_did("did:web:bipm.example")
    assert bipm is not None
    credential = recognized_entity_credential(
        credential_id=BIPM_RECOGNITION,
        issuer=issuer_reference("did:web:bipm.example", bipm.legal_name),
        valid_from=valid_from,
        valid_until=valid_until,
        subjects=institutes,
        name="CIPM MRA signatories, 2026 edition",
        description=(
            "National metrology institutes participating in the CIPM MRA, each scoped "
            "to the calibration and measurement capabilities it has published in the "
            "key comparison database."
        ),
        credential_status=status_entry(
            BIPM_STATUS, STATUS_INDEX[BIPM_RECOGNITION], purpose="suspension"
        ),
    )
    signed, trace = sign_document(
        credential, actor_key("did:web:bipm.example"), created=RECOGNITION_FROM
    )
    world._register("bipm-recognition", signed, trace)

    # Global ACI recognises accreditation bodies.
    sas = actor_by_did("did:web:sas.example")
    ilac = actor_by_did("did:web:global-aci.example")
    assert sas is not None and ilac is not None
    credential = recognized_entity_credential(
        credential_id=GLOBAL_ACI_RECOGNITION,
        issuer=issuer_reference("did:web:global-aci.example", ilac.legal_name),
        valid_from=valid_from,
        valid_until=valid_until,
        subjects=[
            {
                "id": "did:web:sas.example",
                "type": "RecognizedEntity",
                "name": sas.name,
                "legalName": sas.legal_name,
                "url": sas.url,
                "description": sas.description,
                # One action per main scope, because a main scope is what the
                # arrangement actually recognises: an activity paired with the document
                # it is assessed against. Two of these three share ISO/IEC 17025 and
                # differ only in activity, so a list of standards could not tell them
                # apart -- and signatory status for one of them can begin, lapse or be
                # withdrawn without touching the others.
                "recognizedTo": [
                    recognized_action(
                        "accredit",
                        "did:web:global-aci.example",
                        description=(
                            f"Accredit conformity assessment bodies for "
                            f"{signatory.main_scope.activity.lower()} against "
                            f"{signatory.main_scope.standard}, under the Global ACI "
                            f"multilateral recognition arrangement."
                        ),
                        main_scope=signatory.main_scope.to_json(),
                        valid_from=f"{signatory.signed_on}T00:00:00Z",
                        valid_until=valid_until,
                    )
                    for signatory in arrangement_registry.scopes_for_signatory(
                        "did:web:sas.example"
                    )
                ],
            }
        ],
        name="Global ACI MRA signatories, 2026 edition",
        description=(
            "Accreditation bodies that are signatories to the Global ACI multilateral "
            "recognition arrangement, with the main scopes -- an activity and the "
            "normative document it is assessed against -- each one is a signatory for."
        ),
        credential_status=status_entry(
            GLOBAL_ACI_STATUS, STATUS_INDEX[GLOBAL_ACI_RECOGNITION], purpose="suspension"
        ),
    )
    signed, trace = sign_document(
        credential, actor_key("did:web:global-aci.example"), created=RECOGNITION_FROM
    )
    world._register("global-aci-recognition", signed, trace)

    # The accreditation body recognises the bodies it has accredited. Its own issuer
    # object points upward at Global ACI, which is the link that makes the chain traversable.
    accredited = []
    for scope in accreditation_registry.ACCREDITATION_SCOPES:
        actor = actor_by_did(scope.organisation)
        assert actor is not None
        # The pair this accreditation is granted under, which is what the hop above has
        # to have recognised the body for. Asserting the standard agrees keeps the two
        # registries from drifting apart quietly.
        main_scope = arrangement_registry.main_scope_by_activity(scope.activity)
        assert main_scope.standard == scope.standard
        accredited.append(
            {
                "id": scope.organisation,
                "type": "RecognizedEntity",
                "name": actor.name,
                "legalName": actor.legal_name,
                "url": actor.url,
                "description": actor.description,
                "recognizedTo": [
                    recognized_action(
                        "issue",
                        "did:web:sas.example",
                        description=(
                            f"{scope.activity} within accreditation {scope.identifier}, "
                            f"{scope.field}, under {scope.standard}."
                        ),
                        output_validation=schema_reference(schemas[scope.identifier]),
                        capability_reference={
                            "id": scope.url,
                            "type": "AccreditationScope",
                            "identifier": scope.identifier,
                        },
                        main_scope=main_scope.to_json(),
                        valid_from=f"{scope.valid_from}T00:00:00Z",
                        valid_until=f"{scope.valid_until}T23:59:59Z",
                    )
                ],
            }
        )

    credential = recognized_entity_credential(
        credential_id=SAS_RECOGNITION,
        issuer=issuer_reference(
            "did:web:sas.example", sas.legal_name, recognized_in=GLOBAL_ACI_RECOGNITION
        ),
        valid_from=valid_from,
        valid_until=valid_until,
        subjects=accredited,
        name="Accredited bodies, 2026 edition",
        description=(
            "Laboratories and certification bodies accredited by this body, each scoped "
            "to its published accreditation."
        ),
        credential_status=status_entry(
            SAS_STATUS, STATUS_INDEX[SAS_RECOGNITION], purpose="suspension"
        ),
    )
    signed, trace = sign_document(
        credential, actor_key("did:web:sas.example"), created=RECOGNITION_FROM
    )
    world._register("sas-recognition", signed, trace)


def _calibration_certificates(world: World) -> None:
    """Build the two calibration certificates that carry the traceability chain.

    Args:
        world: The world being built.
    """
    metas = actor_by_did("did:web:metas.example")
    callab = actor_by_did("did:web:callab.example")
    testlab = actor_by_did("did:web:testlab.example")
    assert metas is not None and callab is not None and testlab is not None

    standard = instrument_by_id("urn:instrument:callab:standard-resistor:SR10K-0042")
    multimeter = instrument_by_id("urn:instrument:testlab:multimeter:DMM-1177")
    assert standard is not None and multimeter is not None

    cmc = kcdb_registry.cmc_by_id("CH-EM-0042")
    assert cmc is not None

    metas_result = _metas_result()
    world.results["metas-calibration"] = metas_result

    metas_representations, metas_artefacts = uncertainty_representations(
        metas_result,
        credential_id=METAS_CERTIFICATE,
        gtc_archive=build_gtc_archive(metas_result),
        dcc_xml=_dcc_for(
            metas_result,
            certificate_number="METAS-2026-0417",
            performed_on=METAS_CALIBRATED_ON,
            issued=METAS_ISSUED,
            measurand="dc.resistance",
            conditions=cmc.conditions,
            instrument=standard,
            laboratory=metas,
            customer=callab,
        ),
    )
    world.publish_artefacts(metas_artefacts)

    credential = calibration_certificate_credential(
        credential_id=METAS_CERTIFICATE,
        representations=metas_representations,
        issuer=issuer_reference(
            "did:web:metas.example", metas.legal_name, recognized_in=BIPM_RECOGNITION
        ),
        valid_from=_stamp(METAS_ISSUED),
        valid_until=_stamp(METAS_EXPIRES),
        certificate_number="METAS-2026-0417",
        performed_on=METAS_CALIBRATED_ON,
        instrument=standard.to_json(),
        owner={"id": callab.did, "name": callab.legal_name},
        measurand="dc.resistance",
        conditions=cmc.conditions,
        result=metas_result,
        nominal_value=1.0e4,
        capability_reference={
            "id": cmc.url,
            "type": "KcdbCmcEntry",
            "identifier": cmc.identifier,
        },
        mra_logo_asserted=True,
        accredited=False,
        traceable_to=None,
        credential_status=status_entry(METAS_STATUS, STATUS_INDEX[METAS_CERTIFICATE]),
    )
    metas_certificate, trace = sign_document(
        credential, actor_key("did:web:metas.example"), created=METAS_ISSUED
    )
    world._register("metas-calibration", metas_certificate, trace)

    # The accredited laboratory now calibrates its customer's multimeter against the
    # standard it just had calibrated. It loads the dependency representation from the
    # certificate rather than re-entering the two printed numbers, so the input
    # quantities of the institute travel onward into everything it issues.
    callab_result = _callab_result(metas_result)
    world.results["callab-calibration"] = callab_result

    scope = accreditation_registry.scope_by_id("SCS 0123")
    assert scope is not None

    callab_representations, callab_artefacts = uncertainty_representations(
        callab_result,
        credential_id=CALLAB_CERTIFICATE,
        gtc_archive=build_gtc_archive(callab_result),
        dcc_xml=_dcc_for(
            callab_result,
            certificate_number="AC-2026-1182",
            performed_on=CALLAB_CALIBRATED_ON,
            issued=CALLAB_ISSUED,
            measurand="dc.resistance",
            conditions=scope.conditions,
            instrument=multimeter,
            laboratory=callab,
            customer=testlab,
            reference_certificate=METAS_CERTIFICATE,
        ),
    )
    world.publish_artefacts(callab_artefacts)

    credential = calibration_certificate_credential(
        credential_id=CALLAB_CERTIFICATE,
        representations=callab_representations,
        issuer=issuer_reference(
            "did:web:callab.example", callab.legal_name, recognized_in=SAS_RECOGNITION
        ),
        valid_from=_stamp(CALLAB_ISSUED),
        valid_until=_stamp(CALLAB_EXPIRES),
        certificate_number="AC-2026-1182",
        performed_on=CALLAB_CALIBRATED_ON,
        instrument=multimeter.to_json(),
        owner={"id": testlab.did, "name": testlab.legal_name},
        measurand="dc.resistance",
        conditions=scope.conditions,
        result=callab_result,
        nominal_value=1.0e4,
        capability_reference={
            "id": scope.url,
            "type": "AccreditationScope",
            "identifier": scope.identifier,
        },
        # A calibration laboratory carries its accreditation symbol, not the CIPM MRA
        # logo. The logo belongs to the institutes that signed the arrangement.
        mra_logo_asserted=False,
        accredited=True,
        traceable_to={
            **credential_reference(
                metas_certificate, relation="CalibrationCertificateCredential"
            ),
            "instrument": standard.id,
            "note": (
                "The transfer standard used for this calibration was itself calibrated "
                "by a national metrology institute under the CIPM MRA."
            ),
        },
        credential_status=status_entry(CALLAB_STATUS, STATUS_INDEX[CALLAB_CERTIFICATE]),
    )
    signed, trace = sign_document(
        credential, actor_key("did:web:callab.example"), created=CALLAB_ISSUED
    )
    world._register("callab-calibration", signed, trace)


def _shared_reference_pair(world: World, unused: MeasurementResult) -> None:
    """Issue two certificates from one institute against one national standard.

    This is the material chapter 6 works with. Both check standards were compared with
    the same national standard, so the uncertainty that standard contributes is common
    to both results and cancels in their difference.

    Whether the customer can take advantage of that depends entirely on what was
    transmitted. The dependency representation makes the shared influence recognisable
    by its identifier; the printed value and Expanded Uncertainty do not, and no care at
    the customer end recovers it afterwards.

    Args:
        world: The world being built.
        unused: Kept so the call site reads the same; the pair shares the national
            standard directly rather than the certificate of the transfer standard.
    """
    metas = actor_by_did("did:web:metas.example")
    callab = actor_by_did("did:web:callab.example")
    assert metas is not None and callab is not None

    cmc = kcdb_registry.cmc_by_id("CH-EM-0042")
    assert cmc is not None

    u_variable_standard = _national_standard()

    for instrument, number, address, ratio, index in (
        (SHARED_REFERENCE_PAIR[0], "METAS-2026-0418", METAS_CHECK_A, 1.00000315, 10),
        (SHARED_REFERENCE_PAIR[1], "METAS-2026-0419", METAS_CHECK_B, 0.99999785, 11),
    ):
        result = evaluate(
            lambda q: q["national_standard"] * q["ratio"] + q["temperature"] + q["repeatability"],
            [
                from_quantity(
                    "national_standard",
                    "National standard, scaled from the quantum Hall resistance",
                    u_variable_standard,
                    unit="ohm",
                ),
                normal("ratio", "Cryogenic current comparator ratio", ratio, 2.0e-8),
                rectangular(
                    "temperature", "Temperature correction to 23 degC", 0.0, 2.0e-4, unit="ohm"
                ),
                normal(
                    "repeatability", "Repeatability of the comparison", 0.0, 2.0e-4, unit="ohm"
                ),
            ],
            unit="ohm",
            context=number,
        )
        world.results[f"metas-{instrument.serial_number}"] = result

        representations, artefacts = uncertainty_representations(
            result,
            credential_id=address,
            gtc_archive=build_gtc_archive(result),
            dcc_xml=_dcc_for(
                result,
                certificate_number=number,
                performed_on=METAS_CALIBRATED_ON,
                issued=METAS_ISSUED,
                measurand="dc.resistance",
                conditions=cmc.conditions,
                instrument=instrument,
                laboratory=metas,
                customer=callab,
            ),
        )
        world.publish_artefacts(artefacts)

        credential = calibration_certificate_credential(
            credential_id=address,
            representations=representations,
            issuer=issuer_reference(
                "did:web:metas.example", metas.legal_name, recognized_in=BIPM_RECOGNITION
            ),
            valid_from=_stamp(METAS_ISSUED),
            valid_until=_stamp(METAS_EXPIRES),
            certificate_number=number,
            performed_on=METAS_CALIBRATED_ON,
            instrument=instrument.to_json(),
            owner={"id": callab.did, "name": callab.legal_name},
            measurand="dc.resistance",
            conditions=cmc.conditions,
            result=result,
            nominal_value=1.0e4,
            capability_reference={
                "id": cmc.url,
                "type": "KcdbCmcEntry",
                "identifier": cmc.identifier,
            },
            mra_logo_asserted=True,
            accredited=False,
            traceable_to=None,
            credential_status=status_entry(METAS_STATUS, index),
        )
        signed, trace = sign_document(
            credential, actor_key("did:web:metas.example"), created=METAS_ISSUED
        )
        world._register(f"metas-{instrument.serial_number}", signed, trace)


def _external_document_certificate(world: World) -> None:
    """Issue the certificate that exists only as a document outside its credential.

    Everything else the institute issues carries its PTB/DKD DCC as a passenger beside a
    readable subject. This one carries a URL, a digest and four facts of index, and the
    document -- the DKD's own published example for standard resistors, adapted to this
    world -- is published separately with its own ``ds:Signature`` over it.

    Two integrity mechanisms therefore cover overlapping content, which is the situation
    every other certificate here avoids by signing once. It is built deliberately, so the
    chapter can show what each one does and does not settle.

    Args:
        world: The world being built.
    """
    metas = actor_by_did("did:web:metas.example")
    testlab = actor_by_did("did:web:testlab.example")
    assert metas is not None and testlab is not None

    cmc = kcdb_registry.cmc_by_id("CH-EM-0042")
    assert cmc is not None

    key = actor_key("did:web:metas.example")
    document = external_dcc_bytes(key)
    address = f"{METAS_EXTERNAL}/certificate.dcc.xml"
    world.publish_artefacts({address: ("application/xml", document)})

    index = EXTERNAL_DCC_INDEX
    credential = external_document_credential(
        credential_id=METAS_EXTERNAL,
        issuer=issuer_reference(
            "did:web:metas.example", metas.legal_name, recognized_in=BIPM_RECOGNITION
        ),
        valid_from=_stamp(METAS_ISSUED),
        valid_until=_stamp(METAS_EXPIRES),
        document_url=address,
        document=document,
        document_format="PTB-DKD-DCC-XML",
        specification="https://www.ptb.de/dcc/",
        media_type="application/xml",
        schema_version=index.schema_version,
        namespace=index.namespace,
        quantity_format=index.quantity_format,
        certificate_number=index.certificate_number,
        performed_on=index.performed_on,
        measurand=index.measurand,
        unit=index.unit,
        capability_reference={
            "id": cmc.url,
            "type": "KcdbCmcEntry",
            "identifier": cmc.identifier,
        },
        xml_signature={
            "canonicalization": C14N_ALGORITHM,
            "algorithm": SIGNATURE_ALGORITHM,
            "keyDiscovery": "ds:KeyValue, inline, with no certificate chain",
            "note": (
                "The document carries its own signature as well. It proves the bytes "
                "have not changed and says nothing about who made them, because there "
                "is no chain to follow and no identifier to resolve."
            ),
        },
        credential_status=status_entry(METAS_STATUS, STATUS_INDEX[METAS_EXTERNAL]),
    )
    signed, trace = sign_document(credential, key, created=METAS_ISSUED)
    world._register("metas-external-dcc", signed, trace)


def _test_report_and_conformity(world: World) -> None:
    """Build the test report and the certificate of conformity that rests on it.

    Args:
        world: The world being built.
    """
    testlab = actor_by_did("did:web:testlab.example")
    cab = actor_by_did("did:web:cab.example")
    manufacturer = actor_by_did("did:web:manufacturer.example")
    assert testlab is not None and cab is not None and manufacturer is not None

    product = instrument_by_id("urn:product:acme:kettle:KT-2200-revC")
    multimeter = instrument_by_id("urn:instrument:testlab:multimeter:DMM-1177")
    assert product is not None and multimeter is not None

    testing_scope = accreditation_registry.scope_by_id("STS 0456")
    certification_scope = accreditation_registry.scope_by_id("SCESp 0789")
    assert testing_scope is not None and certification_scope is not None

    calibration = world.credential("callab-calibration")

    credential = test_report_credential(
        credential_id=TESTLAB_REPORT,
        issuer=issuer_reference(
            "did:web:testlab.example", testlab.legal_name, recognized_in=SAS_RECOGNITION
        ),
        valid_from=_stamp(TESTLAB_ISSUED),
        valid_until=_stamp(TESTLAB_EXPIRES),
        report_number="HTS-2026-3391",
        performed_on=TESTLAB_TESTED_ON,
        product=product.to_json(),
        client={"id": manufacturer.did, "name": manufacturer.legal_name},
        standard="IEC 60335-1",
        tests=[
            {
                "type": "TestResult",
                "clause": "IEC 60335-1 clause 16.3",
                "characteristic": "Insulation resistance",
                "value": 12.4,
                "unit": "Mohm",
                "expandedUncertainty": 0.4,
                "coverageFactor": 2,
                "requirement": "not less than 2 Mohm",
                "verdict": "pass",
            },
            {
                "type": "TestResult",
                "clause": "IEC 60335-1 clause 16.2",
                "characteristic": "Leakage current",
                "value": 0.28,
                "unit": "mA",
                "expandedUncertainty": 0.02,
                "coverageFactor": 2,
                "requirement": "not more than 0.75 mA",
                "verdict": "pass",
            },
        ],
        capability_reference={
            "id": testing_scope.url,
            "type": "AccreditationScope",
            "identifier": testing_scope.identifier,
        },
        equipment_traceability=[
            {
                **credential_reference(
                    calibration, relation="CalibrationCertificateCredential"
                ),
                "equipment": multimeter.id,
                "note": (
                    "Measurements were made with this multimeter, whose accredited "
                    "calibration certificate is referenced here by content digest."
                ),
            }
        ],
        credential_status=status_entry(TESTLAB_STATUS, STATUS_INDEX[TESTLAB_REPORT]),
    )
    report, trace = sign_document(
        credential, actor_key("did:web:testlab.example"), created=TESTLAB_ISSUED
    )
    world._register("testlab-report", report, trace)

    credential = product_conformity_credential(
        credential_id=CAB_CERTIFICATE,
        issuer=issuer_reference(
            "did:web:cab.example", cab.legal_name, recognized_in=SAS_RECOGNITION
        ),
        valid_from=_stamp(CAB_ISSUED),
        valid_until=_stamp(CAB_EXPIRES),
        certificate_number="CPC-2026-0055",
        issued_on=CAB_ISSUED_ON,
        product=product.to_json(),
        holder={"id": manufacturer.did, "name": manufacturer.legal_name},
        standard="IEC 60335-1",
        capability_reference={
            "id": certification_scope.url,
            "type": "AccreditationScope",
            "identifier": certification_scope.identifier,
        },
        test_reports=[
            {
                **credential_reference(report, relation="TestReportCredential"),
                "issuer": testlab.did,
            }
        ],
        credential_status=status_entry(CAB_STATUS, STATUS_INDEX[CAB_CERTIFICATE]),
    )
    signed, trace = sign_document(
        credential, actor_key("did:web:cab.example"), created=CAB_ISSUED
    )
    world._register("cab-conformity", signed, trace)


def _oiml_certification(world: World, schemas: dict[str, dict[str, Any]]) -> None:
    """Build the OIML-CS branch: two recognitions, an evaluation, and a certificate.

    This is the part of the demonstration that reaches two roots of trust from one
    document, and the shape is worth reading carefully because it is not the shape of
    the other two branches.

    The Issuing Authority is recognised by OIML to certify against R 46, and only R 46.
    The laboratory is recognised by OIML to evaluate against it -- and is *separately*
    accredited by SAS under ISO/IEC 17025, which it already was. One laboratory, one
    identifier, two arrangements above it, and nothing in either arrangement aware of
    the other.

    The evaluation report then references the calibration certificate of the multimeter
    it measured with, by content digest. So a verifier following the certificate goes up
    to OIML through recognition and down to the BIPM through evidence, and the two paths
    have nothing in common but the laboratory in the middle.

    Args:
        world: The world being built.
        schemas: The generated schemas, keyed by identifier.
    """
    oiml = actor_by_did("did:web:oiml.example")
    issuing_authority = actor_by_did("did:web:legal-ia.example")
    testlab = actor_by_did("did:web:testlab.example")
    meterworks = actor_by_did("did:web:meterworks.example")
    assert None not in (oiml, issuing_authority, testlab, meterworks)

    recommendation = recommendation_by_id("R 46")
    meter_type = instrument_type_by_id("urn:type:meterworks:mw-e3:rev-b")
    multimeter = instrument_by_id("urn:instrument:testlab:multimeter:DMM-1177")
    assert recommendation is not None and meter_type is not None
    assert multimeter is not None

    valid_from = _stamp(OIML_RECOGNITION_FROM)
    valid_until = _stamp(OIML_RECOGNITION_UNTIL)
    capability = {
        "id": recommendation.url,
        "type": "OimlRecommendation",
        "identifier": recommendation.identifier,
    }

    # --- OIML recognises an Issuing Authority ---------------------------------------
    credential = recognized_entity_credential(
        credential_id=OIML_IA_RECOGNITION,
        issuer=issuer_reference("did:web:oiml.example", oiml.legal_name),
        valid_from=valid_from,
        valid_until=valid_until,
        subjects=[
            {
                "id": issuing_authority.did,
                "type": "RecognizedEntity",
                "name": issuing_authority.name,
                "legalName": issuing_authority.legal_name,
                "url": issuing_authority.url,
                "description": issuing_authority.description,
                "recognizedTo": [
                    recognized_action(
                        "certify",
                        "did:web:oiml.example",
                        output_validation=schema_reference(schemas["oiml-certificate"]),
                        capability_reference=capability,
                        description=(
                            f"Issue OIML certificates of type evaluation against "
                            f"{recommendation.identifier}, {recommendation.title}. The "
                            f"Recommendation is the bound: a certificate against any "
                            f"other one is outside this recognition."
                        ),
                        valid_from=valid_from,
                        valid_until=valid_until,
                    )
                ],
            }
        ],
        name="OIML-CS Issuing Authorities, 2021 edition",
        description=(
            "Certification bodies in OIML Member States approved to issue OIML "
            "certificates, and the Recommendations each is approved for. Recognition "
            "here establishes that a type was evaluated against an international "
            "Recommendation. It establishes no legal permission anywhere: an OIML "
            "Recommendation is not law."
        ),
        credential_status=status_entry(
            OIML_RECOGNITION_STATUS,
            STATUS_INDEX[OIML_IA_RECOGNITION],
            purpose="suspension",
        ),
    )
    signed, trace = sign_document(
        credential, actor_key("did:web:oiml.example"), created=OIML_RECOGNITION_FROM
    )
    world._register("oiml-ia-recognition", signed, trace)

    # --- OIML recognises a Test Laboratory ------------------------------------------
    #
    # The same laboratory SAS accredited. Its description says so, and the two
    # recognitions are deliberately not cross-referenced: neither arrangement knows the
    # other exists, which is exactly the situation chapter 11 says nobody has agreed how
    # to compose.
    credential = recognized_entity_credential(
        credential_id=OIML_TL_RECOGNITION,
        issuer=issuer_reference("did:web:oiml.example", oiml.legal_name),
        valid_from=valid_from,
        valid_until=valid_until,
        subjects=[
            {
                "id": testlab.did,
                "type": "RecognizedEntity",
                "name": testlab.name,
                "legalName": testlab.legal_name,
                "url": testlab.url,
                "description": testlab.description,
                "sameAs": SAS_RECOGNITION,
                "recognizedTo": [
                    recognized_action(
                        "evaluate",
                        "did:web:oiml.example",
                        output_validation=schema_reference(schemas["oiml-evaluation"]),
                        capability_reference=capability,
                        description=(
                            f"Perform type evaluation and testing against "
                            f"{recommendation.identifier}, using equipment whose "
                            f"calibration is traceable and can be demonstrated."
                        ),
                        valid_from=valid_from,
                        valid_until=valid_until,
                    )
                ],
            }
        ],
        name="OIML-CS Test Laboratories, 2021 edition",
        description=(
            "Laboratories recognised within the OIML certification system to perform "
            "type evaluation, and the Recommendations each is recognised for. A "
            "laboratory here is typically also accredited under ISO/IEC 17025 by a "
            "national accreditation body; that is a separate recognition under a "
            "separate arrangement, and this one does not depend on it."
        ),
        credential_status=status_entry(
            OIML_RECOGNITION_STATUS,
            STATUS_INDEX[OIML_TL_RECOGNITION],
            purpose="suspension",
        ),
    )
    signed, trace = sign_document(
        credential, actor_key("did:web:oiml.example"), created=OIML_RECOGNITION_FROM
    )
    world._register("oiml-tl-recognition", signed, trace)

    # --- The laboratory evaluates the type ------------------------------------------
    #
    # The results are plain values with an Expanded Uncertainty rather than
    # MeasurementResult objects. A type evaluation asks whether a design meets a limit,
    # not what value to propagate onward, so there is nothing downstream that needs the
    # dependency structure -- and carrying one would mean publishing a binary UncLib
    # form, which cannot be regenerated without a licence.
    calibration = world.credential("callab-calibration")
    credential = type_evaluation_report_credential(
        credential_id=OIML_EVALUATION,
        issuer=issuer_reference(
            "did:web:testlab.example", testlab.legal_name, recognized_in=OIML_TL_RECOGNITION
        ),
        valid_from=_stamp(OIML_EVALUATION_ISSUED),
        valid_until=_stamp(OIML_EVALUATION_EXPIRES),
        report_number="HTS-TE-2024-0114",
        performed_on=OIML_EVALUATED_ON,
        instrument_type=meter_type.to_json(),
        client={"id": meterworks.did, "name": meterworks.legal_name},
        recommendation=recommendation.to_json(),
        tests=[
            {
                "type": "TypeEvaluationResult",
                "clause": f"{recommendation.identifier} clause 5.2",
                "characteristic": "Percentage error at 5 A, unity power factor",
                "value": 0.31,
                "unit": "%",
                "expandedUncertainty": 0.08,
                "coverageFactor": 2,
                "requirement": "within plus or minus 1.0 % for class B",
                "verdict": "pass",
            },
            {
                "type": "TypeEvaluationResult",
                "clause": f"{recommendation.identifier} clause 5.2",
                "characteristic": "Percentage error at 0.5 A, power factor 0.5 inductive",
                "value": -0.74,
                "unit": "%",
                "expandedUncertainty": 0.12,
                "coverageFactor": 2,
                "requirement": "within plus or minus 1.5 % for class B",
                "verdict": "pass",
            },
            {
                "type": "TypeEvaluationResult",
                "clause": f"{recommendation.identifier} clause 6.3",
                "characteristic": "Error variation under influence of ambient temperature",
                "value": 0.19,
                "unit": "%",
                "expandedUncertainty": 0.06,
                "coverageFactor": 2,
                "requirement": "within plus or minus 0.5 % for class B",
                "verdict": "pass",
            },
        ],
        capability_reference=capability,
        equipment_traceability=[
            {
                **credential_reference(
                    calibration, relation="CalibrationCertificateCredential"
                ),
                "equipment": multimeter.id,
                "note": (
                    "The reference measurements were made with this multimeter, whose "
                    "accredited calibration certificate is referenced here by content "
                    "digest. That certificate is traceable to a national standard, so "
                    "the evaluation is traceable and not merely signed."
                ),
            }
        ],
        credential_status=status_entry(TESTLAB_STATUS, STATUS_INDEX[OIML_EVALUATION]),
    )
    evaluation, trace = sign_document(
        credential, actor_key("did:web:testlab.example"), created=OIML_EVALUATION_ISSUED
    )
    world._register("oiml-evaluation", evaluation, trace)

    # --- The Issuing Authority issues the certificate -------------------------------
    credential = oiml_certificate_credential(
        credential_id=OIML_CERTIFICATE,
        issuer=issuer_reference(
            "did:web:legal-ia.example",
            issuing_authority.legal_name,
            recognized_in=OIML_IA_RECOGNITION,
        ),
        valid_from=_stamp(OIML_CERTIFICATE_ISSUED),
        valid_until=_stamp(OIML_CERTIFICATE_EXPIRES),
        certificate_number="R46/2024-CH1-0037",
        issued_on=OIML_CERTIFICATE_ISSUED_ON,
        instrument_type=meter_type.to_json(),
        applicant={"id": meterworks.did, "name": meterworks.legal_name},
        recommendation=recommendation.to_json(),
        characteristics={
            "type": "OimlCharacteristics",
            "accuracyClass": meter_type.accuracy_class,
            "measurand": recommendation.measurand,
            "unit": recommendation.unit,
            "ratedVoltage": "230/400 V",
            "ratedFrequency": "50 Hz",
            "currentRange": "0.25 A to 100 A",
            "temperatureRange": "-25 to +55 degrees Celsius",
        },
        test_report={
            **credential_reference(
                evaluation, relation="TypeEvaluationReportCredential"
            ),
            "issuer": testlab.did,
            "note": (
                "The type evaluation this certificate rests on. Reviewing it is the "
                "Issuing Authority's defined job under the OIML-CS, so it is referenced "
                "as a document a verifier can fetch rather than as a number it can only "
                "read."
            ),
        },
        capability_reference=capability,
        credential_status=status_entry(
            OIML_CERTIFICATE_STATUS, STATUS_INDEX[OIML_CERTIFICATE]
        ),
    )
    signed, trace = sign_document(
        credential,
        actor_key("did:web:legal-ia.example"),
        created=OIML_CERTIFICATE_ISSUED,
    )
    world._register("oiml-certificate", signed, trace)


def _whois_presentations(world: World) -> None:
    """Publish, for each recognised actor, a presentation describing itself.

    This is what identifier-based discovery dereferences. A verifier that has an issuer
    identifier but no recognition credential to go with it can resolve the identifier,
    find the whois service in the DID document, and retrieve the recognition credential
    from the issuer itself rather than having to know where to look.

    Args:
        world: The world being built.
    """
    membership = {
        "did:web:metas.example": "bipm-recognition",
        "did:web:ptb.example": "bipm-recognition",
        "did:web:sas.example": "global-aci-recognition",
        "did:web:callab.example": "sas-recognition",
        "did:web:testlab.example": "sas-recognition",
        "did:web:cab.example": "sas-recognition",
        "did:web:legal-ia.example": "oiml-ia-recognition",
    }
    for did, credential_name in membership.items():
        url = whois_url(did)
        presentation = {
            "@context": CREDENTIAL_CONTEXT,
            "id": url,
            "type": ["VerifiablePresentation"],
            "holder": did,
            "verifiableCredential": [world.credential(credential_name)],
        }
        signed, _ = sign_document(
            presentation,
            actor_key(did),
            created=RECOGNITION_FROM,
            proof_purpose="authentication",
        )
        world.store.publish(url, signed, "presentation")


def build_world() -> World:
    """Build and sign every document in the demonstration.

    Returns:
        The populated world. Building is deterministic, so two calls produce identical
        documents.
    """
    world = World()
    _publish_did_documents(world)
    _publish_registries(world)
    schemas = _build_schemas(world)
    _status_lists(world)
    _recognition_credentials(world, schemas)
    _calibration_certificates(world)
    _shared_reference_pair(world, world.results['metas-calibration'])
    _external_document_certificate(world)
    _test_report_and_conformity(world)
    _oiml_certification(world, schemas)
    _whois_presentations(world)
    return world


def dump(destination: Path) -> int:
    """Write every document in the world to a directory as formatted JSON.

    Because the build is deterministic, two dumps of an unchanged code base are
    identical, so the directory can be committed and diffed. That turns any change in a
    credential into a reviewable change rather than something noticed later.

    Args:
        destination: Directory to write into. Created if it does not exist.

    Returns:
        The number of documents written.
    """
    import json
    import re

    world = build_world()
    destination.mkdir(parents=True, exist_ok=True)

    written = 0
    for url, document in world.store.contents().items():
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", url).strip("_")[:120]
        (destination / f"{name}.json").write_text(
            json.dumps(document, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        written += 1
    return written


def _main() -> None:
    """Command line entry point for inspecting the generated world."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Build the demonstration world.")
    parser.add_argument(
        "--dump",
        metavar="DIRECTORY",
        help="write every published document to this directory as JSON",
    )
    parser.add_argument(
        "--show", metavar="NAME", help="print one credential by its short name"
    )
    arguments = parser.parse_args()

    if arguments.dump:
        count = dump(Path(arguments.dump))
        print(f"wrote {count} documents to {arguments.dump}")
        return

    world = build_world()
    if arguments.show:
        print(json.dumps(world.credential(arguments.show), indent=2, ensure_ascii=False))
        return

    print(f"{len(world.credentials)} signed credentials, "
          f"{len(world.store.contents())} documents published")
    for name, credential in world.credentials.items():
        print(f"  {name:24s} {credential['id']}")


if __name__ == "__main__":
    _main()
