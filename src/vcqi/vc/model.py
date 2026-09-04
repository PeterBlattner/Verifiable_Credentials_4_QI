"""Builders for the credential shapes this demonstration uses.

Four credential types carry the story:

``RecognizedEntityCredential``
    Straight from the Recognized Entities specification. A recognising authority lists
    the entities it recognises and what each is recognised to do. Both the CIPM MRA and
    an ISO/IEC 17025 accreditation fit this shape without stretching it.

``CalibrationCertificateCredential``
    A calibration certificate. It states results with their Expanded Uncertainty,
    references the capability it was issued under, and points at the certificate one
    level up the traceability chain.

``TestReportCredential``
    A test report, which references the calibration certificate of the equipment used,
    so that the traceability of a test result can be followed to the SI.

``ProductConformityCredential``
    The certificate of conformity of the Product Conformity use case, which references
    the test reports it rests on.

The credential subjects are kept deliberately readable rather than being modelled on
the PTB Digital Calibration Certificate schema. See ARCHITECTURE.md for what a DCC
alignment would change.
"""

from __future__ import annotations

from typing import Any

from vcqi.config import CONTEXT_CREDENTIALS_V2, CONTEXT_VCQI_V1
from vcqi.crypto.jcs import canonicalize
from vcqi.crypto.multibase import digest_multibase
from vcqi.domain.uncertainty import MeasurementResult

__all__ = [
    "CREDENTIAL_CONTEXT",
    "issuer_reference",
    "credential_reference",
    "recognized_entity_credential",
    "recognized_action",
    "calibration_certificate_credential",
    "test_report_credential",
    "product_conformity_credential",
    "status_entry",
    "budget_to_json",
    "measurement_result_to_json",
]

#: Every credential carries the base data model context plus the terms this
#: demonstration adds. Nothing dereferences these; see ARCHITECTURE.md.
CREDENTIAL_CONTEXT: list[str] = [CONTEXT_CREDENTIALS_V2, CONTEXT_VCQI_V1]


def issuer_reference(
    did: str,
    name: str,
    *,
    recognized_in: str | None = None,
) -> dict[str, Any]:
    """Build the issuer member of a credential.

    Args:
        did: Identifier of the issuing organisation.
        name: Display name of the issuer.
        recognized_in: URL of the RecognizedEntityCredential in which this issuer
            appears, or None for an issuer that is itself a root of trust. This single
            member is what turns an isolated credential into a chain a verifier can
            walk without being told anything in advance.

    Returns:
        The issuer object.
    """
    issuer: dict[str, Any] = {"id": did, "type": "RecognizedIssuer", "name": name}
    if recognized_in is not None:
        issuer["recognizedIn"] = {
            "id": recognized_in,
            "type": "RecognizedEntityCredential",
        }
    return issuer


def credential_reference(credential: dict[str, Any], *, relation: str) -> dict[str, Any]:
    """Reference another credential by identifier and by content digest.

    The digest matters. Without it a reference names a document but says nothing about
    which version of it, so a laboratory could point at a certificate that has since
    been reissued with different numbers. With it, the reference is only satisfied by
    the exact document that was seen when the reference was made.

    Args:
        credential: The credential being referenced, secured or not.
        relation: The type to record for the reference, for example
            ``CalibrationCertificateCredential``.

    Returns:
        A reference carrying the identifier, the type and the content digest.
    """
    unsecured = {name: value for name, value in credential.items() if name != "proof"}
    return {
        "id": credential["id"],
        "type": relation,
        "digestMultibase": digest_multibase(canonicalize(unsecured)),
    }


def status_entry(
    status_list_credential: str,
    index: int,
    *,
    purpose: str = "revocation",
) -> dict[str, Any]:
    """Build the credentialStatus member pointing into a status list.

    Args:
        status_list_credential: URL of the BitstringStatusListCredential.
        index: Position of this credential in the list.
        purpose: Either ``revocation`` for a permanent withdrawal or ``suspension``
            for a temporary one. The distinction matters here: an accreditation is
            typically suspended pending corrective action, not revoked outright.

    Returns:
        The credentialStatus object.
    """
    return {
        "id": f"{status_list_credential}#{index}",
        "type": "BitstringStatusListEntry",
        "statusPurpose": purpose,
        "statusListIndex": str(index),
        "statusListCredential": status_list_credential,
    }


def recognized_action(
    action: str,
    recognized_by: str,
    *,
    output_validation: dict[str, Any] | None = None,
    capability_reference: dict[str, Any] | None = None,
    valid_from: str | None = None,
    valid_until: str | None = None,
    description: str = "",
) -> dict[str, Any]:
    """Build one RecognizedAction inside a recognised entity.

    Args:
        action: What the entity may do, for example ``issue`` or ``accredit``.
        recognized_by: Identifier of the recognising authority.
        output_validation: Reference to a JSON Schema that documents produced under
            this recognition must validate against.
        capability_reference: Reference to the CMC entry or accreditation scope that
            bounds the recognition. A JSON Schema can express a measurand and a range,
            but not an uncertainty floor that varies with the measured level, so the
            numeric part of the scope has to be reachable separately.
        valid_from: Start of validity of this action, if narrower than the credential.
        valid_until: End of validity of this action, if narrower than the credential.
        description: Human-readable summary of what is recognised.

    Returns:
        The RecognizedAction object.
    """
    entry: dict[str, Any] = {
        "type": "RecognizedAction",
        "action": action,
        "recognizedBy": recognized_by,
    }
    if description:
        entry["description"] = description
    if output_validation is not None:
        entry["outputValidation"] = output_validation
    if capability_reference is not None:
        entry["capabilityReference"] = capability_reference
    if valid_from is not None:
        entry["validFrom"] = valid_from
    if valid_until is not None:
        entry["validUntil"] = valid_until
    return entry


def recognized_entity_credential(
    *,
    credential_id: str,
    issuer: dict[str, Any],
    valid_from: str,
    valid_until: str,
    subjects: list[dict[str, Any]],
    name: str,
    description: str,
    credential_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a RecognizedEntityCredential listing the entities an authority recognises.

    Args:
        credential_id: URL the credential is published at. Chain traversal fetches it
            by this identifier, so it has to be resolvable.
        issuer: The issuer object, from :func:`issuer_reference`.
        valid_from: Start of validity, as an XML Schema dateTime.
        valid_until: End of validity, as an XML Schema dateTime.
        subjects: The recognised entities, each with its recognised actions.
        name: Display name of the list.
        description: One sentence on what the list means.
        credential_status: Optional credentialStatus member.

    Returns:
        The unsecured credential, ready to be signed.
    """
    credential: dict[str, Any] = {
        "@context": CREDENTIAL_CONTEXT,
        "id": credential_id,
        "type": ["VerifiableCredential", "RecognizedEntityCredential"],
        "name": name,
        "description": description,
        "issuer": issuer,
        "validFrom": valid_from,
        "validUntil": valid_until,
        "credentialSubject": subjects,
    }
    if credential_status is not None:
        credential["credentialStatus"] = credential_status
    return credential


def budget_to_json(result: MeasurementResult) -> list[dict[str, Any]]:
    """Render an uncertainty budget for inclusion in a credential.

    Carrying the budget rather than only the number is what lets the next laboratory in
    the chain reuse the result correctly, and lets a verifier check that a stated
    Expanded Uncertainty is consistent with the contributions claimed to produce it.

    Args:
        result: The evaluated measurement result.

    Returns:
        One JSON-compatible object per contribution.
    """
    return [
        {
            "type": "UncertaintyContribution",
            "quantity": line.label,
            "value": line.value,
            "unit": line.unit,
            "standardUncertainty": line.standard_uncertainty,
            "distribution": line.distribution,
            "sensitivityCoefficient": line.sensitivity_coefficient,
            "uncertaintyContribution": line.uncertainty_contribution,
            "index": line.index,
            **({"source": line.note} if line.note else {}),
        }
        for line in result.budget
    ]


def measurement_result_to_json(
    result: MeasurementResult, *, nominal_value: float
) -> dict[str, Any]:
    """Render a measurement result as it appears on a certificate.

    Args:
        result: The evaluated measurement result.
        nominal_value: Nominal value of the artefact, in the unit of the result.

    Returns:
        A JSON-compatible object carrying the value, the Expanded Uncertainty, the
        coverage factor and the conventional reported form.
    """
    return {
        "type": "CalibrationResult",
        "nominalValue": nominal_value,
        "value": result.value,
        "standardUncertainty": result.standard_uncertainty,
        "expandedUncertainty": result.expanded_uncertainty,
        "coverageFactor": result.coverage_factor,
        "relativeExpandedUncertainty": result.relative_expanded_uncertainty,
        "unit": result.unit,
        "reported": result.format(),
    }


def calibration_certificate_credential(
    *,
    credential_id: str,
    issuer: dict[str, Any],
    valid_from: str,
    valid_until: str,
    certificate_number: str,
    performed_on: str,
    instrument: dict[str, Any],
    owner: dict[str, Any],
    measurand: str,
    conditions: str,
    result: MeasurementResult,
    nominal_value: float,
    capability_reference: dict[str, Any],
    mra_logo_asserted: bool,
    accredited: bool,
    traceable_to: dict[str, Any] | None = None,
    credential_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a calibration certificate as a verifiable credential.

    Args:
        credential_id: URL the certificate is published at.
        issuer: The issuer object, from :func:`issuer_reference`.
        valid_from: Start of validity, as an XML Schema dateTime.
        valid_until: End of validity, as an XML Schema dateTime.
        certificate_number: The certificate number as printed on a paper certificate.
        performed_on: Date the calibration was performed, as an ISO 8601 date.
        instrument: The calibrated artefact, from ``Instrument.to_json``.
        owner: Reference to the organisation the artefact belongs to.
        measurand: Machine-readable identifier of the measured quantity.
        conditions: Conditions the calibration was performed under.
        result: The evaluated measurement result with its budget.
        nominal_value: Nominal value of the artefact, in the unit of the result.
        capability_reference: Reference to the CMC entry or accreditation scope the
            certificate was issued under.
        mra_logo_asserted: Whether the certificate claims coverage by the CIPM MRA.
            This is the claim a verifier adjudicates against the referenced CMC, and it
            is stated explicitly so that the claim can be checked rather than inferred
            from the presence of an image.
        accredited: Whether the certificate claims to be accredited work.
        traceable_to: Reference to the certificate one level up the traceability chain,
            or None when the issuer realises the unit itself.
        credential_status: Optional credentialStatus member.

    Returns:
        The unsecured credential, ready to be signed.
    """
    calibration: dict[str, Any] = {
        "type": "Calibration",
        "certificateNumber": certificate_number,
        "performedOn": performed_on,
        "measurand": measurand,
        "unit": result.unit,
        "conditions": conditions,
        "results": [measurement_result_to_json(result, nominal_value=nominal_value)],
        "uncertaintyBudget": budget_to_json(result),
        "capabilityReference": capability_reference,
        "mraLogoAsserted": mra_logo_asserted,
        "accredited": accredited,
    }
    if traceable_to is not None:
        calibration["traceableTo"] = traceable_to

    credential: dict[str, Any] = {
        "@context": CREDENTIAL_CONTEXT,
        "id": credential_id,
        "type": ["VerifiableCredential", "CalibrationCertificateCredential"],
        "name": f"Calibration certificate {certificate_number}",
        "issuer": issuer,
        "validFrom": valid_from,
        "validUntil": valid_until,
        "credentialSubject": {
            **instrument,
            "owner": owner,
            "calibration": calibration,
        },
    }
    if credential_status is not None:
        credential["credentialStatus"] = credential_status
    return credential


def test_report_credential(
    *,
    credential_id: str,
    issuer: dict[str, Any],
    valid_from: str,
    valid_until: str,
    report_number: str,
    performed_on: str,
    product: dict[str, Any],
    client: dict[str, Any],
    standard: str,
    tests: list[dict[str, Any]],
    capability_reference: dict[str, Any],
    equipment_traceability: list[dict[str, Any]],
    credential_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a test report as a verifiable credential.

    Args:
        credential_id: URL the report is published at.
        issuer: The issuer object, from :func:`issuer_reference`.
        valid_from: Start of validity, as an XML Schema dateTime.
        valid_until: End of validity, as an XML Schema dateTime.
        report_number: The report number as printed on a paper report.
        performed_on: Date the testing was performed, as an ISO 8601 date.
        product: The product under test, from ``Instrument.to_json``.
        client: Reference to the organisation that commissioned the testing.
        standard: The product standard the tests were performed against.
        tests: The individual test results.
        capability_reference: Reference to the accreditation scope the report was
            issued under.
        equipment_traceability: References to the calibration certificates of the
            equipment used, which is what carries traceability into a test result.
        credential_status: Optional credentialStatus member.

    Returns:
        The unsecured credential, ready to be signed.
    """
    credential: dict[str, Any] = {
        "@context": CREDENTIAL_CONTEXT,
        "id": credential_id,
        "type": ["VerifiableCredential", "TestReportCredential"],
        "name": f"Test report {report_number}",
        "issuer": issuer,
        "validFrom": valid_from,
        "validUntil": valid_until,
        "credentialSubject": {
            **product,
            "client": client,
            "testing": {
                "type": "Testing",
                "reportNumber": report_number,
                "performedOn": performed_on,
                "standard": standard,
                "results": tests,
                "capabilityReference": capability_reference,
                "equipmentTraceability": equipment_traceability,
                "accredited": True,
            },
        },
    }
    if credential_status is not None:
        credential["credentialStatus"] = credential_status
    return credential


def product_conformity_credential(
    *,
    credential_id: str,
    issuer: dict[str, Any],
    valid_from: str,
    valid_until: str,
    certificate_number: str,
    issued_on: str,
    product: dict[str, Any],
    holder: dict[str, Any],
    standard: str,
    capability_reference: dict[str, Any],
    test_reports: list[dict[str, Any]],
    credential_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a certificate of conformity as a verifiable credential.

    This is the leaf of the Product Conformity use case: the document a market
    surveillance authority meets at the border, issued by a body it has never dealt
    with, about a product it has never seen.

    Args:
        credential_id: URL the certificate is published at.
        issuer: The issuer object, from :func:`issuer_reference`.
        valid_from: Start of validity, as an XML Schema dateTime.
        valid_until: End of validity, as an XML Schema dateTime.
        certificate_number: The certificate number.
        issued_on: Date of issue, as an ISO 8601 date.
        product: The certified product, from ``Instrument.to_json``.
        holder: Reference to the organisation the certificate was issued to.
        standard: The product standard certified against.
        capability_reference: Reference to the accreditation scope of the certification
            body.
        test_reports: References to the test reports the certification rests on.
        credential_status: Optional credentialStatus member.

    Returns:
        The unsecured credential, ready to be signed.
    """
    credential: dict[str, Any] = {
        "@context": CREDENTIAL_CONTEXT,
        "id": credential_id,
        "type": ["VerifiableCredential", "ProductConformityCredential"],
        "name": f"Certificate of conformity {certificate_number}",
        "issuer": issuer,
        "validFrom": valid_from,
        "validUntil": valid_until,
        "credentialSubject": {
            **product,
            "holder": holder,
            "conformity": {
                "type": "ConformityAssessment",
                "certificateNumber": certificate_number,
                "issuedOn": issued_on,
                "standard": standard,
                "conformityStatement": (
                    f"The product conforms to {standard} for the characteristics assessed."
                ),
                "capabilityReference": capability_reference,
                "testReports": test_reports,
            },
        },
    }
    if credential_status is not None:
        credential["credentialStatus"] = credential_status
    return credential
