"""JSON Schemas that bound what a recognised entity may issue.

The Recognized Entities specification lets a recognition carry an ``outputValidation``
reference: a schema that documents produced under that recognition are expected to
validate against. That is a good fit for the structural half of a CMC or an
accreditation scope, and this module generates such a schema from a declared
capability.

It is a deliberately partial fit, and the demonstration says so rather than papering
over it. A schema can pin the measurand, the unit and the range, because those are
fixed values and bounds. It cannot express the rule that actually matters most, that
the claimed Expanded Uncertainty must not be smaller than a floor which itself varies
with the measured level. The best a schema can do is the weakest form of that rule: the
floor at the bottom of the range, which every in-scope claim must clear but which a
wildly optimistic claim at the top of the range would also clear.

So ``outputValidation`` catches the gross errors offline, and the exact decision needs
the signed registry entry as well. Both checks appear in the verification pipeline, and
seeing the schema pass while the registry check fails is one of the more instructive
moments in the demonstration.

**Two carriers, one authorisation.** What a recognition authorises is a measurement, not
a JSON shape, and this world issues the same calibration two ways: with the result in the
credential, and as a credential pointing at an external document that holds it. A schema
naming only the first would refuse the second, and would be refusing it for the wrong
reason -- not because the institute may not do it, but because the schema was written
before it did. So the generated schema accepts either carrier, and insists on what each
one must state: a result inside the declared bounds, or a digest of the document that
holds it.

**A scope is a table, and a schema is a constant.** An accreditation scope covers
several quantities over rows whose shapes a schema has no way to say: fixed values
rather than an interval, a strict upper bound, a capability that differs with the
frequency it was demonstrated at. The schema takes one branch per quantity and, inside a
branch, the union of its rows -- the widest level any of them touches and the smallest
uncertainty any of them permits. Every one of those collapses loses something, and they
all lose it in the permissive direction, which is the safe one: the schema admits claims
the register will refuse, never the reverse. The consequence is that the richer a scope
gets, the more of the decision belongs to the register alone.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vcqi.crypto.jcs import canonicalize
from vcqi.crypto.multibase import digest_multibase
from vcqi.domain.scope import DeclaredCapability

__all__ = [
    "calibration_certificate_schema",
    "test_report_schema",
    "schema_reference",
]


def calibration_certificate_schema(
    capabilities: Sequence[DeclaredCapability],
    *,
    schema_id: str,
    title: str,
) -> dict[str, Any]:
    """Generate the schema a calibration certificate must validate against.

    Args:
        capabilities: The capabilities being expressed -- one for a CMC entry, and one
            per quantity for an accreditation scope published as a table. The schema
            admits a certificate matching any of them.
        schema_id: URL the schema is published at.
        title: Human-readable title for the schema.

    Returns:
        A JSON Schema draft 2020-12 document.

    Raises:
        ValueError: If no capability is given. A schema bounding nothing would validate
            everything, which is worse than having no schema at all.
    """
    if not capabilities:
        raise ValueError("a schema needs at least one capability to bound")

    branches: list[dict[str, Any]] = []
    for capability in capabilities:
        span_minimum, _ = capability.coverage.span()
        weakest_floor = capability.uncertainty_floor.evaluate(span_minimum)
        branches.append(_carried_result(capability, weakest_floor))
        branches.append(_referenced_document(capability))

    described = "; ".join(
        f"{capability.label}, "
        f"{capability.uncertainty_floor.describe(capability.unit)}"
        for capability in capabilities
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_id,
        "title": title,
        "anyOf": branches,
        "description": (
            f"Structural bounds of {described}. The measurand, unit, span and coverage "
            f"factor are expressed here. The uncertainty floor is not: it varies with "
            f"the measured level, and only its value at the bottom of the span can be "
            f"stated as a constant bound. Neither is the shape of the capability: a "
            f"scope published as a table collapses here to the widest level any row "
            f"touches and the smallest uncertainty any row permits, so fixed values, "
            f"strict bounds and condition bands all disappear. A certificate that "
            f"validates against this schema is therefore not yet known to be inside "
            f"scope; the registry entry decides that, and the richer the scope the more "
            f"of the decision is left to it."
        ),
    }


def _carried_result(
    capability: DeclaredCapability, weakest_floor: float
) -> dict[str, Any]:
    """Return the branch for a certificate carrying its result in the credential.

    Args:
        capability: The CMC entry or accreditation scope being expressed.
        weakest_floor: The uncertainty floor at the bottom of the range, which is the
            strongest constant bound a schema can state.

    Returns:
        A JSON Schema subschema.
    """
    floor = capability.uncertainty_floor
    return {
        "title": "The result carried in the credential",
        "type": "object",
        "required": ["type", "credentialSubject"],
        "properties": {
            "type": {
                "type": "array",
                "contains": {"const": "CalibrationCertificateCredential"},
            },
            "credentialSubject": {
                "type": "object",
                "required": ["calibration"],
                "properties": {
                    "calibration": {
                        "type": "object",
                        "required": ["measurand", "unit", "results"],
                        "properties": {
                            "measurand": {"const": capability.measurand},
                            "unit": {"const": capability.unit},
                            "results": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "object",
                                    "required": [
                                        "value",
                                        "unit",
                                        "expandedUncertainty",
                                        "coverageFactor",
                                    ],
                                    "properties": {
                                        "value": {
                                            "type": "number",
                                            "minimum": capability.coverage.span()[0],
                                            "maximum": capability.coverage.span()[1],
                                        },
                                        "unit": {"const": capability.unit},
                                        "coverageFactor": {
                                            "const": floor.coverage_factor
                                        },
                                        "expandedUncertainty": {
                                            "type": "number",
                                            "minimum": weakest_floor,
                                        },
                                    },
                                },
                            },
                        },
                    }
                },
            },
        },
    }


def _referenced_document(capability: DeclaredCapability) -> dict[str, Any]:
    """Return the branch for a credential pointing at an external document.

    Notice how much less there is to say. The measurand and the unit can still be
    pinned, because the credential states them. Nothing about the result can be, because
    the result is not here. What the schema insists on instead is that the reference is
    a reference: a digest has to be present, or the credential would be pointing at a
    document that could be swapped after issue.

    Args:
        capability: The CMC entry or accreditation scope being expressed.

    Returns:
        A JSON Schema subschema.
    """
    return {
        "title": "The result held in a document the credential points at",
        "type": "object",
        "required": ["type", "credentialSubject", "relatedResource"],
        "properties": {
            "type": {
                "type": "array",
                "contains": {"const": "ExternalDocumentCredential"},
            },
            "credentialSubject": {
                "type": "object",
                "required": ["externalDocument"],
                "properties": {
                    "externalDocument": {
                        "type": "object",
                        "required": ["format", "measurand", "unit"],
                        "properties": {
                            "measurand": {"const": capability.measurand},
                            "unit": {"const": capability.unit},
                        },
                    }
                },
            },
            "relatedResource": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "object", "required": ["id", "digestMultibase"]},
            },
        },
    }


def test_report_schema(*, schema_id: str, title: str, standard: str) -> dict[str, Any]:
    """Generate the schema a test report must validate against.

    A testing scope has no uncertainty floor, so the schema can express essentially all
    of it: the standard tested against, and the requirement that the equipment used is
    traceable to a calibration certificate rather than merely asserted to be in order.

    Args:
        schema_id: URL the schema is published at.
        title: Human-readable title for the schema.
        standard: The product standard the scope covers.

    Returns:
        A JSON Schema draft 2020-12 document.
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_id,
        "title": title,
        "description": (
            f"Structural bounds for test reports issued against {standard}. Requires "
            f"at least one reference to the calibration certificate of the equipment "
            f"used, so that a report cannot claim accredited status while leaving its "
            f"traceability unstated."
        ),
        "type": "object",
        "required": ["type", "credentialSubject"],
        "properties": {
            "type": {"type": "array", "contains": {"const": "TestReportCredential"}},
            "credentialSubject": {
                "type": "object",
                "required": ["testing"],
                "properties": {
                    "testing": {
                        "type": "object",
                        "required": ["standard", "results", "equipmentTraceability"],
                        "properties": {
                            "standard": {"const": standard},
                            "results": {"type": "array", "minItems": 1},
                            "equipmentTraceability": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "object",
                                    "required": ["id", "digestMultibase"],
                                },
                            },
                        },
                    }
                },
            },
        },
    }


def schema_reference(schema: dict[str, Any]) -> dict[str, Any]:
    """Build the outputValidation reference to a schema.

    The digest lets a verifier confirm it fetched the same schema the recognition was
    made against, so that the bounds cannot be relaxed after the fact by editing the
    published file.

    Args:
        schema: The JSON Schema document.

    Returns:
        A reference carrying the schema identifier, its type and its content digest.
    """
    return {
        "id": schema["$id"],
        "type": "JsonSchema",
        "digestMultibase": digest_multibase(canonicalize(schema)),
    }
