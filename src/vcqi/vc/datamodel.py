"""The data model of each credential type, as a JSON Schema every credential cites.

A credential type fixes a shape: which members a document of that type has, which of
them it must have, and what kind of value each one holds. This module writes that shape
down once per type, and every credential names the result in ``credentialSchema`` -- the
data model's own member for it, profiled by the W3C *Verifiable Credentials JSON Schema*
specification with the type ``JsonSchema``.

**A data model is not a permission.** The project already has schemas, and they answer a
different question. The ``outputValidation`` schema a recognition names
(``vc/schema.py``) says what a recognised issuer *may* issue: this measurand, this unit,
this range. It is written by whoever grants the recognition, differs from one issuer to
the next, and a certificate outside it is a document its issuer was not entitled to
sign. The schemas here say what a document of a type *is*, the same for every issuer,
and a certificate outside one is not a well-formed certificate at all. A document can
satisfy the first and fail the second, or the reverse, and the verifier checks both.

**Self-contained, so that one digest covers everything.** The reference in a credential
carries a digest of the schema it names, which is what stops the schema being loosened
at its address after the credential was signed. A digest covers one document, though, and
a ``$ref`` to another address would leave whatever it points at unpinned -- swap that and
the model is loosened anyway. So each type's schema is one document: the envelope every
credential shares and the shapes several types reuse sit in its own ``$defs``, generated
here from one builder each so that the copies cannot drift apart. The root refers to the
envelope beside its own ``properties``, which puts what is particular to the type first
and what every type shares last. Validation never needs the network, and
:func:`validator_for` makes sure it never tries.

**Open, deliberately.** No schema here sets ``additionalProperties`` to false. A
credential is JSON-LD and is meant to be extended, and the JSON Schema specification for
credentials advises against closing a schema for exactly that reason. What keeps the
schemas honest instead is a test: it walks every credential the world issues and fails if
any member one carries is not declared here, so the box in chapter 3 cannot quietly leave
a field out.

**The verifier knows which model belongs to which type.** ``DATA_MODEL_URLS`` is that
knowledge. Without it an issuer could cite a permissive schema of its own and pass; with
it, a credential naming anything but the model published for its type fails.

``format`` is an annotation in draft 2020-12 and nothing here asserts it. A date written
as prose would pass; it would also fail every later step that reads the date.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Final

from jsonschema import Draft202012Validator
from referencing import Registry

from vcqi.config import (
    CONTEXT_CREDENTIALS_V2,
    CONTEXT_VCQI_V1,
    CRYPTOSUITE,
    DATA_MODEL_BASE,
)
from vcqi.crypto.jcs import canonicalize
from vcqi.crypto.multibase import digest_multibase, digest_sri

__all__ = [
    "DATA_MODEL_URLS",
    "JSON_SCHEMA_DIALECT",
    "data_model",
    "data_model_reference",
    "data_models",
    "validator_for",
]

#: The one JSON Schema version the credential profile requires every implementation to
#: support. A schema declaring any other is not evaluated; see ``vc/verify.py``.
JSON_SCHEMA_DIALECT: Final[str] = "https://json-schema.org/draft/2020-12/schema"

#: The data model published for each credential type, in the order the chain runs: the
#: arrangements at the top, then what they recognise, then the documents about somebody
#: in particular. Chapter 3 offers the types in this order.
DATA_MODEL_URLS: Final[dict[str, str]] = {
    "RecognizedEntityCredential": f"{DATA_MODEL_BASE}/recognized-entity-credential.json",
    "AccreditationScopeCredential": (
        f"{DATA_MODEL_BASE}/accreditation-scope-credential.json"
    ),
    "CalibrationCertificateCredential": (
        f"{DATA_MODEL_BASE}/calibration-certificate-credential.json"
    ),
    "ExternalDocumentCredential": f"{DATA_MODEL_BASE}/external-document-credential.json",
    "TestReportCredential": f"{DATA_MODEL_BASE}/test-report-credential.json",
    "ProductConformityCredential": (
        f"{DATA_MODEL_BASE}/product-conformity-credential.json"
    ),
    "TypeEvaluationReportCredential": (
        f"{DATA_MODEL_BASE}/type-evaluation-report-credential.json"
    ),
    "OimlCertificateCredential": f"{DATA_MODEL_BASE}/oiml-certificate-credential.json",
}


# ---------------------------------------------------------------- small shapes
#
# One-line constructors, so that the schemas below read as the shapes they describe
# rather than as nested dictionary literals. Each returns a new dictionary, never a
# shared one.

def _string(**extra: Any) -> dict[str, Any]:
    return {"type": "string", **extra}


def _number() -> dict[str, Any]:
    return {"type": "number"}


def _integer() -> dict[str, Any]:
    return {"type": "integer"}


def _boolean() -> dict[str, Any]:
    return {"type": "boolean"}


def _date() -> dict[str, Any]:
    return {"type": "string", "format": "date"}


def _instant() -> dict[str, Any]:
    return {"type": "string", "format": "date-time"}


def _url() -> dict[str, Any]:
    return {"type": "string", "format": "uri"}


def _const(value: Any) -> dict[str, Any]:
    return {"const": value}


def _ref(name: str) -> dict[str, Any]:
    return {"$ref": f"#/$defs/{name}"}


def _array(items: dict[str, Any], *, at_least: int | None = None) -> dict[str, Any]:
    shape: dict[str, Any] = {"type": "array", "items": items}
    if at_least is not None:
        shape["minItems"] = at_least
    return shape


def _object(
    properties: dict[str, Any], *, required: list[str] | None = None
) -> dict[str, Any]:
    """Return an object shape, requiring every member unless told otherwise.

    Requiring everything is the default because it is what the builders in
    ``vc/model.py`` do: almost every member is always written, and the few that are not
    are the ones a reader most needs to see marked optional.

    Args:
        properties: The members, in the order a credential writes them.
        required: The members that must be present, or None for all of them.

    Returns:
        A JSON Schema subschema.
    """
    return {
        "type": "object",
        "required": list(properties) if required is None else required,
        "properties": properties,
    }


def _optional(properties: dict[str, Any], *optional: str) -> dict[str, Any]:
    """Return an object shape requiring every member except the ones named.

    Args:
        properties: The members, in the order a credential writes them.
        *optional: The members that may be left out.

    Returns:
        A JSON Schema subschema.
    """
    return _object(
        properties, required=[name for name in properties if name not in optional]
    )


# ---------------------------------------------------------------- the envelope

def _verifiable_credential() -> dict[str, Any]:
    """Return what every credential in this world has, whatever its type.

    ``credentialSubject`` is required and not described: a recognition lists its subjects
    in an array and every other type states one object, so the envelope cannot say more
    than that one is there. ``proof`` is described and not required, so that a credential
    before signing -- the first panel in chapter 3 -- satisfies the same model as the
    credential after.

    Returns:
        A JSON Schema subschema.
    """
    return _optional(
        {
            "@context": {
                "type": "array",
                "items": _string(),
                "prefixItems": [_const(CONTEXT_CREDENTIALS_V2)],
                "contains": _const(CONTEXT_VCQI_V1),
            },
            "id": _url(),
            "type": {
                "type": "array",
                "items": _string(),
                "contains": _const("VerifiableCredential"),
            },
            "name": _string(),
            "description": _string(),
            "issuer": _optional(
                {
                    "id": _string(pattern="^did:"),
                    "type": _const("RecognizedIssuer"),
                    "name": _string(),
                    "recognizedIn": _object(
                        {"id": _url(), "type": _const("RecognizedEntityCredential")}
                    ),
                },
                "recognizedIn",
            ),
            "validFrom": _instant(),
            "validUntil": _instant(),
            "credentialSubject": {},
            "credentialStatus": _object(
                {
                    "id": _url(),
                    "type": _const("BitstringStatusListEntry"),
                    "statusPurpose": {"enum": ["revocation", "suspension"]},
                    "statusListIndex": _string(pattern="^[0-9]+$"),
                    "statusListCredential": _url(),
                }
            ),
            "credentialSchema": _object(
                {
                    "id": _url(),
                    "type": _const("JsonSchema"),
                    "digestSRI": _string(pattern="^sha256-"),
                    "digestMultibase": _string(),
                }
            ),
            "proof": _optional(
                {
                    "type": _const("DataIntegrityProof"),
                    "cryptosuite": _const(CRYPTOSUITE),
                    "created": _instant(),
                    "verificationMethod": _string(),
                    "proofPurpose": _const("assertionMethod"),
                    "@context": _array(_string()),
                    "proofValue": _string(pattern="^z"),
                },
                "@context",
            ),
        },
        "description",
        "credentialStatus",
        "proof",
    )


# ---------------------------------------------------------------- shared parts

def _organisation() -> dict[str, Any]:
    return _optional(
        {"id": _string(), "type": _const("Organization"), "name": _string()}, "type"
    )


def _capability_reference() -> dict[str, Any]:
    return _optional(
        {
            "id": _url(),
            "type": {
                "enum": ["KcdbCmcEntry", "AccreditationScope", "OimlRecommendation"]
            },
            "identifier": _string(),
            "digestMultibase": _string(),
            "queryEndpoint": _url(),
            "queryProtocol": _string(),
        },
        "digestMultibase",
        "queryEndpoint",
        "queryProtocol",
    )


def _credential_reference() -> dict[str, Any]:
    return _optional(
        {
            "id": _url(),
            "type": _string(),
            "digestMultibase": _string(),
            "issuer": _string(),
            "instrument": _string(),
            "equipment": _string(),
            "note": _string(),
        },
        "issuer",
        "instrument",
        "equipment",
        "note",
    )


def _uncertainty_floor() -> dict[str, Any]:
    return _object(
        {
            "absoluteTerm": _number(),
            "relativeTerm": _number(),
            "coverageFactor": _number(),
        }
    )


def _test_result() -> dict[str, Any]:
    return _object(
        {
            "type": {"enum": ["TestResult", "TypeEvaluationResult"]},
            "clause": _string(),
            "characteristic": _string(),
            "value": _number(),
            "unit": _string(),
            "expandedUncertainty": _number(),
            "coverageFactor": _number(),
            "requirement": _string(),
            "verdict": _string(),
        }
    )


def _oiml_recommendation() -> dict[str, Any]:
    return _object(
        {
            "id": _url(),
            "type": _const("OimlRecommendation"),
            "number": _string(),
            "edition": _string(),
            "identifier": _string(),
            "title": _string(),
            "instrumentCategory": _string(),
            "regulatedQuantity": _string(),
            "regulatedUnit": _string(),
            "measurand": _string(),
            "unit": _string(),
            "rangeMinimum": _number(),
            "rangeMaximum": _number(),
            "evaluationUncertainty": _ref("uncertaintyFloor"),
            "accuracyClasses": _array(_string()),
            "conditions": _string(),
            "methods": _array(_string()),
            "machineReadable": _boolean(),
        }
    )


#: The parts more than one type uses, by the name a ``$ref`` gives them, with the
#: parts each of them uses in turn.
_SHARED: Final[dict[str, tuple[Any, tuple[str, ...]]]] = {
    "organisation": (_organisation, ()),
    "capabilityReference": (_capability_reference, ()),
    "credentialReference": (_credential_reference, ()),
    "uncertaintyFloor": (_uncertainty_floor, ()),
    "testResult": (_test_result, ()),
    "oimlRecommendation": (_oiml_recommendation, ("uncertaintyFloor",)),
}


def _instrument() -> dict[str, Any]:
    """Return the members of a calibrated artefact or a tested product.

    These are spread into the credential subject rather than nested under it, so they
    are returned as members to merge rather than as an object.

    Returns:
        Property schemas, from ``Instrument.to_json``.
    """
    return {
        "id": _string(),
        "type": _string(),
        "name": _string(),
        "manufacturer": _string(),
        "model": _string(),
        "serialNumber": _string(),
        "objectCategory": {"enum": ["measuringInstrument", "materialMeasure"]},
        "nominalValue": _number(),
        "unit": _string(),
    }


_INSTRUMENT_OPTIONAL: Final[tuple[str, ...]] = ("objectCategory", "nominalValue", "unit")


def _instrument_type() -> dict[str, Any]:
    """Return the members of an evaluated design, spread into the subject.

    Returns:
        Property schemas, from ``InstrumentType.to_json``.
    """
    return {
        "id": _string(),
        "type": _string(),
        "name": _string(),
        "manufacturer": _ref("organisation"),
        "typeDesignation": _string(),
        "accuracyClass": _string(),
        "modules": _array(_string()),
    }


# ---------------------------------------------------------------- the eight types

def _recognized_entity() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    subject = _array(_ref("recognizedEntity"), at_least=1)
    local = {
        "recognizedEntity": _optional(
            {
                "id": _string(),
                "type": _const("RecognizedEntity"),
                "name": _string(),
                "legalName": _string(),
                "url": _url(),
                "description": _string(),
                # A list for the BIPM's entries and a single address for OIML's: the
                # specification allows either, so the model has to as well.
                "sameAs": {"anyOf": [_url(), _array(_url())]},
                "recognizedTo": _array(_ref("recognizedAction"), at_least=1),
            },
            "legalName",
            "url",
            "description",
            "sameAs",
        ),
        "recognizedAction": _optional(
            {
                "type": _const("RecognizedAction"),
                "action": _string(),
                "recognizedBy": _string(),
                "description": _string(),
                # "One or more data schemas", in the specification's words: one here,
                # but a recognition naming two is as well-formed as one naming one.
                "outputValidation": {
                    "anyOf": [
                        _ref("schemaReference"),
                        _array(_ref("schemaReference"), at_least=1),
                    ]
                },
                "capabilityReference": _ref("capabilityReference"),
                "mainScope": _object(
                    {
                        "activity": _string(),
                        "standard": _object({"id": _url(), "name": _string()}),
                    }
                ),
                "validFrom": _instant(),
                "validUntil": _instant(),
            },
            "description",
            "outputValidation",
            "capabilityReference",
            "mainScope",
            "validFrom",
            "validUntil",
        ),
        "schemaReference": _object(
            {
                "id": _url(),
                "type": _const("JsonSchema"),
                "digestMultibase": _string(),
            }
        ),
    }
    return subject, local, {}


def _accreditation_scope() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    subject = _optional(
        {
            "id": _url(),
            "type": _const("AccreditationScope"),
            "identifier": _string(),
            "accreditationBody": _string(),
            "accreditationBodyName": _string(),
            "organisation": _string(),
            "organisationName": _string(),
            "conformityAssessmentStandard": _string(),
            "activity": _string(),
            "field": _string(),
            "conditions": _string(),
            "validFrom": _date(),
            "validUntil": _date(),
            "rows": _array(_ref("scopeRow"), at_least=1),
            "queryEndpoint": _url(),
            "queryProtocol": _string(),
            "methods": _array(_string()),
            "languagePrecedence": _string(),
        },
        "rows",
        "queryEndpoint",
        "queryProtocol",
        "methods",
        "languagePrecedence",
    )
    bound = {"enum": ["inclusive", "exclusive"]}
    local = {
        "scopeRow": _optional(
            {
                "label": _string(),
                "measurand": _string(),
                "unit": _string(),
                "objectCategory": _string(),
                "coverage": {
                    "oneOf": [
                        _object(
                            {
                                "type": _const("Interval"),
                                "minimum": _number(),
                                "maximum": _number(),
                                "lowerBound": bound,
                                "upperBound": bound,
                            }
                        ),
                        _object(
                            {
                                "type": _const("Points"),
                                "values": _array(_number(), at_least=1),
                                "matchTolerance": _number(),
                            }
                        ),
                        _object(
                            {
                                "type": _const("Window"),
                                "nominal": _number(),
                                "tolerance": _number(),
                            }
                        ),
                    ]
                },
                "bestMeasurementCapability": {
                    "$ref": "#/$defs/uncertaintyFloor",
                    "properties": {"description": _string()},
                },
                "remarks": _array(_string()),
                "condition": _object(
                    {
                        "quantity": _string(),
                        "minimum": _number(),
                        "maximum": _number(),
                        "unit": _string(),
                        "text": _string(),
                    }
                ),
            },
            "condition",
        ),
    }
    return subject, local, {}


def _calibration_certificate() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    subject = _optional(
        {
            **_instrument(),
            "owner": _ref("organisation"),
            "calibration": _optional(
                {
                    "type": _const("Calibration"),
                    "certificateNumber": _string(),
                    "performedOn": _date(),
                    "measurand": _string(),
                    "unit": _string(),
                    "conditions": _string(),
                    "conditionQuantities": _array(
                        _object(
                            {
                                "quantity": _string(),
                                "value": _number(),
                                "unit": _string(),
                            }
                        )
                    ),
                    "results": _array(_ref("calibrationResult"), at_least=1),
                    "uncertaintyBudget": _array(_ref("uncertaintyContribution")),
                    "capabilityReference": _ref("capabilityReference"),
                    "mraLogoAsserted": _boolean(),
                    "accredited": _boolean(),
                    "traceableTo": _ref("credentialReference"),
                },
                "conditionQuantities",
                "traceableTo",
            ),
        },
        *_INSTRUMENT_OPTIONAL,
    )
    local = {
        "calibrationResult": _optional(
            {
                "type": _const("CalibrationResult"),
                "nominalValue": _number(),
                "value": _number(),
                "standardUncertainty": _number(),
                "expandedUncertainty": _number(),
                "coverageFactor": _number(),
                "relativeExpandedUncertainty": _number(),
                "unit": _string(),
                "reported": _string(),
                "uncertaintyRepresentations": _array(
                    _ref("uncertaintyRepresentation"), at_least=1
                ),
            },
            "uncertaintyRepresentations",
        ),
        "uncertaintyContribution": _optional(
            {
                "type": _const("UncertaintyContribution"),
                "quantity": _string(),
                "value": _number(),
                "unit": _string(),
                "standardUncertainty": _number(),
                "distribution": _string(),
                "sensitivityCoefficient": _number(),
                "uncertaintyContribution": _number(),
                "index": _number(),
                "source": _string(),
            },
            "source",
        ),
        # One shape for three kinds of representation, because they share most of their
        # members and differ in which they fill. Only what every one of them states is
        # required; the carrier -- inline ``content``, or an ``id`` with a ``byteCount``
        # -- is whichever the size of the payload chose.
        "uncertaintyRepresentation": _object(
            {
                "type": {
                    "enum": [
                        "ClassicalStatement",
                        "DependencyRepresentation",
                        "CertificateRepresentation",
                    ]
                },
                "format": _string(),
                "value": _number(),
                "standardUncertainty": _number(),
                "expandedUncertainty": _number(),
                "coverageFactor": _number(),
                "unit": _string(),
                "reported": _string(),
                "mediaType": _string(),
                "specification": _url(),
                "schemaVersion": _string(),
                "quantityFormat": _string(),
                "inputQuantityCount": _integer(),
                "inputQuantities": _array(
                    _object({"id": _string(), "description": _string()})
                ),
                "digestMultibase": _string(),
                "content": _string(),
                "id": _url(),
                "byteCount": _integer(),
                "available": _boolean(),
                "note": _string(),
                "signatureNote": _string(),
            },
            required=["type", "format", "note"],
        ),
    }
    return subject, local, {}


def _external_document() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    subject = _object(
        {
            "id": _url(),
            "externalDocument": _optional(
                {
                    "type": _const("ExternalCalibrationCertificate"),
                    "format": _string(),
                    "specification": _url(),
                    "mediaType": _string(),
                    "schemaVersion": _string(),
                    "namespace": _string(),
                    "quantityFormat": _string(),
                    "byteCount": _integer(),
                    "certificateNumber": _string(),
                    "performedOn": _date(),
                    "measurand": _string(),
                    "unit": _string(),
                    "capabilityReference": _ref("capabilityReference"),
                    "note": _string(),
                    "xmlSignature": _object(
                        {
                            "canonicalization": _string(),
                            "algorithm": _string(),
                            "keyDiscovery": _string(),
                            "note": _string(),
                        }
                    ),
                },
                "xmlSignature",
            ),
        }
    )
    root = {
        "relatedResource": _array(
            _object(
                {
                    "id": _url(),
                    "mediaType": _string(),
                    "digestSRI": _string(pattern="^sha256-"),
                    "digestMultibase": _string(),
                }
            ),
            at_least=1,
        )
    }
    return subject, {}, root


def _test_report() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    subject = _optional(
        {
            **_instrument(),
            "client": _ref("organisation"),
            "testing": _object(
                {
                    "type": _const("Testing"),
                    "reportNumber": _string(),
                    "performedOn": _date(),
                    "standard": _string(),
                    "results": _array(_ref("testResult"), at_least=1),
                    "capabilityReference": _ref("capabilityReference"),
                    "equipmentTraceability": _array(
                        _ref("credentialReference"), at_least=1
                    ),
                    "accredited": _boolean(),
                }
            ),
        },
        *_INSTRUMENT_OPTIONAL,
    )
    return subject, {}, {}


def _product_conformity() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    subject = _optional(
        {
            **_instrument(),
            "holder": _ref("organisation"),
            "conformity": _object(
                {
                    "type": _const("ConformityAssessment"),
                    "certificateNumber": _string(),
                    "issuedOn": _date(),
                    "standard": _string(),
                    "conformityStatement": _string(),
                    "capabilityReference": _ref("capabilityReference"),
                    "testReports": _array(_ref("credentialReference"), at_least=1),
                }
            ),
        },
        *_INSTRUMENT_OPTIONAL,
    )
    return subject, {}, {}


def _type_evaluation_report() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    subject = _optional(
        {
            **_instrument_type(),
            "client": _ref("organisation"),
            "typeEvaluation": _object(
                {
                    "type": _const("TypeEvaluation"),
                    "reportNumber": _string(),
                    "performedOn": _date(),
                    "recommendation": _ref("oimlRecommendation"),
                    "measurand": _string(),
                    "standard": _string(),
                    "results": _array(_ref("testResult"), at_least=1),
                    "capabilityReference": _ref("capabilityReference"),
                    "equipmentTraceability": _array(
                        _ref("credentialReference"), at_least=1
                    ),
                    "recognized": _boolean(),
                }
            ),
        },
        "modules",
    )
    return subject, {}, {}


def _oiml_certificate() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    subject = _optional(
        {
            **_instrument_type(),
            "applicant": _ref("organisation"),
            "oimlCertificate": _optional(
                {
                    "type": _const("OimlTypeApproval"),
                    "certificateNumber": _string(),
                    "issuedOn": _date(),
                    "recommendation": _ref("oimlRecommendation"),
                    "standard": _string(),
                    "characteristics": _object(
                        {
                            "type": _const("OimlCharacteristics"),
                            "accuracyClass": _string(),
                            "measurand": _string(),
                            "unit": _string(),
                            "ratedVoltage": _string(),
                            "ratedFrequency": _string(),
                            "currentRange": _string(),
                            "temperatureRange": _string(),
                        }
                    ),
                    "testReport": _ref("credentialReference"),
                    "capabilityReference": _ref("capabilityReference"),
                    # Not a free field: an OIML certificate never has legal effect, and
                    # the type says so rather than leaving it to each issuer.
                    "legalEffect": _const("none"),
                    "legalEffectNote": _string(),
                },
                "capabilityReference",
            ),
        },
        "modules",
    )
    return subject, {}, {}


#: Per type: the chip label and the one line under it, and the builder of what is
#: particular to the type. A title is a name, because chapter 3 puts it on a button.
_TYPES: Final[dict[str, tuple[str, str, Any]]] = {
    "RecognizedEntityCredential": (
        "Recognition",
        "An authority naming the entities it recognises, and what each may do.",
        _recognized_entity,
    ),
    "AccreditationScopeCredential": (
        "Accreditation scope",
        "What an accreditation covers, signed by the body that granted it.",
        _accreditation_scope,
    ),
    "CalibrationCertificateCredential": (
        "Calibration certificate",
        "A calibration, with its result, Expanded Uncertainty and budget inside.",
        _calibration_certificate,
    ),
    "ExternalDocumentCredential": (
        "Certificate by reference",
        "A credential vouching, by digest, for a certificate published elsewhere.",
        _external_document,
    ),
    "TestReportCredential": (
        "Test report",
        "Tests of a product against a standard, with the equipment used.",
        _test_report,
    ),
    "ProductConformityCredential": (
        "Certificate of conformity",
        "A statement that a product meets a standard, resting on test reports.",
        _product_conformity,
    ),
    "TypeEvaluationReportCredential": (
        "OIML type evaluation report",
        "An evaluation of an instrument design against an OIML Recommendation.",
        _type_evaluation_report,
    ),
    "OimlCertificateCredential": (
        "OIML certificate",
        "Type-evaluation evidence under the OIML-CS. Not a legal approval.",
        _oiml_certificate,
    ),
}


def _refs_in(schema: Any) -> set[str]:
    """Return the names of the ``$defs`` a schema refers to.

    Args:
        schema: Any part of a schema.

    Returns:
        The names after ``#/$defs/``.
    """
    found: set[str] = set()
    if isinstance(schema, dict):
        reference = schema.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            found.add(reference.removeprefix("#/$defs/"))
        for value in schema.values():
            found |= _refs_in(value)
    elif isinstance(schema, list):
        for value in schema:
            found |= _refs_in(value)
    return found


def data_model(type_name: str) -> dict[str, Any]:
    """Return the data model of one credential type.

    A new document on every call, so that a caller changing it -- the failure case that
    loosens one -- cannot change it for anybody else.

    Args:
        type_name: The credential type, for example ``CalibrationCertificateCredential``.

    Returns:
        A self-contained JSON Schema draft 2020-12 document.

    Raises:
        KeyError: If the type has no data model here.
    """
    title, description, build = _TYPES[type_name]
    subject, local, root = build()
    properties = {
        "type": {"contains": _const(type_name)},
        "credentialSubject": subject,
        **root,
    }
    definitions: dict[str, Any] = {"verifiableCredential": _verifiable_credential()}
    definitions.update(local)
    # Only the shared parts this type actually reaches, so that each box shows what its
    # type uses and nothing it does not.
    wanted = _refs_in([properties, local])
    while True:
        more = {
            dependency
            for name in wanted
            if name in _SHARED
            for dependency in _SHARED[name][1]
        } - wanted
        if not more:
            break
        wanted |= more
    for name, (builder, _) in _SHARED.items():
        if name in wanted:
            definitions[name] = builder()
    document: dict[str, Any] = {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": DATA_MODEL_URLS[type_name],
        "title": title,
        "description": description,
        "$ref": "#/$defs/verifiableCredential",
    }
    # The envelope already requires a type and a subject; only a member the type adds at
    # the top level needs requiring here.
    if root:
        document["required"] = list(root)
    document["properties"] = properties
    document["$defs"] = definitions
    return document


def data_models() -> dict[str, dict[str, Any]]:
    """Return every data model, keyed by the address it is published at.

    Returns:
        Mapping from URL to schema, in chain order.
    """
    return {url: data_model(type_name) for type_name, url in DATA_MODEL_URLS.items()}


@lru_cache(maxsize=None)
def _digests(type_name: str) -> tuple[str, str]:
    """Return both digests of a type's data model, over its canonical form.

    Args:
        type_name: The credential type.

    Returns:
        The ``digestSRI`` and the ``digestMultibase``.
    """
    canonical = canonicalize(data_model(type_name))
    return digest_sri(canonical), digest_multibase(canonical)


def data_model_reference(type_name: str) -> dict[str, Any]:
    """Return the ``credentialSchema`` member a credential of this type carries.

    Both digest spellings, as ``relatedResource`` already carries them: ``digestSRI``
    because the JSON Schema profile for credentials names it, ``digestMultibase`` because
    every other pinned reference in this project uses it. Both are over the RFC 8785
    canonical form, as the ``outputValidation`` references are, so that reformatting the
    published file does not break them and changing a single constraint does.

    Args:
        type_name: The credential type.

    Returns:
        The reference.
    """
    sri, multibase = _digests(type_name)
    return {
        "id": DATA_MODEL_URLS[type_name],
        "type": "JsonSchema",
        "digestSRI": sri,
        "digestMultibase": multibase,
    }


def validator_for(schema: dict[str, Any]) -> Draft202012Validator:
    """Return a validator that resolves nothing it was not handed.

    ``jsonschema`` retrieves an unknown ``$ref`` over HTTP unless it is given a registry.
    A verifier fetching whatever a schema points at would be fetching past the digest
    that pinned the schema, so the registry here is empty: a reference inside the
    document resolves, and one outside it is an error rather than a request.

    Args:
        schema: The data model.

    Returns:
        A draft 2020-12 validator.
    """
    return Draft202012Validator(schema, registry=Registry())
