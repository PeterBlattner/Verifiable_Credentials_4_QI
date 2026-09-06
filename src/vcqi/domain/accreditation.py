"""Accreditation scopes issued by an accreditation body under the Global ACI MRA.

An accreditation scope is the accreditation-body counterpart of a CMC: it states which
activity a laboratory is competent to perform, over which range, and for calibration
work the smallest Expanded Uncertainty it may claim. That last figure is usually called
the best measurement capability.

The three scopes here cover the three roles the demonstration needs: a calibration
laboratory under ISO/IEC 17025, a testing laboratory under the same standard, and a
product certification body under ISO/IEC 17065, which is the conformity assessment body
of the Product Conformity use case in the Recognized Entities specification.

Every identifier is fictional and deliberately shaped like, but not equal to, the
numbering a real accreditation body uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vcqi.config import SAS_ORIGIN
from vcqi.domain.scope import DeclaredCapability, UncertaintyFloor

__all__ = [
    "AccreditationScope",
    "ACCREDITATION_SCOPES",
    "scope_by_id",
    "scope_url",
    "scopes_for_organisation",
]


@dataclass(frozen=True)
class AccreditationScope:
    """One accreditation scope granted to one organisation.

    Attributes:
        identifier: The accreditation number, for example ``SCS 0123``.
        body: DID of the accreditation body that granted it.
        body_name: Human-readable name of that body.
        organisation: DID of the accredited organisation.
        organisation_name: Human-readable name of that organisation.
        standard: The conformity assessment standard, for example ``ISO/IEC 17025``.
        activity: What the organisation is accredited to do.
        field: The technical field the scope covers.
        measurand: Machine-readable identifier of the measured quantity, or None for a
            scope that is not expressed in terms of a single measurand.
        unit: Unit symbol for the range, or None when no range applies.
        range_minimum: Lowest covered level, in ``unit``, or None.
        range_maximum: Highest covered level, in ``unit``, or None.
        conditions: Conditions the scope is valid under.
        best_capability: Smallest Expanded Uncertainty the laboratory may claim, or
            None for a testing or certification scope where no such figure applies.
        methods: Standards or methods the scope covers, for testing and certification.
        valid_from: Start of validity, as an ISO 8601 date.
        valid_until: End of validity, as an ISO 8601 date.
    """

    identifier: str
    body: str
    body_name: str
    organisation: str
    organisation_name: str
    standard: str
    activity: str
    field: str
    conditions: str
    valid_from: str
    valid_until: str
    measurand: str | None = None
    unit: str | None = None
    range_minimum: float | None = None
    range_maximum: float | None = None
    best_capability: UncertaintyFloor | None = None
    methods: tuple[str, ...] = ()

    @property
    def url(self) -> str:
        """Return the address at which this scope is published.

        Returns:
            The URL a credential uses when it references this accreditation.
        """
        return scope_url(self.identifier)

    def as_capability(self) -> DeclaredCapability | None:
        """Return the scope in the form the scope check consumes.

        Returns:
            The declared capability, or None for a scope that states no measurand,
            range and uncertainty floor and therefore cannot be checked numerically.
        """
        if (
            self.measurand is None
            or self.unit is None
            or self.range_minimum is None
            or self.range_maximum is None
            or self.best_capability is None
        ):
            return None
        return DeclaredCapability(
            label=f"accreditation {self.identifier}",
            measurand=self.measurand,
            unit=self.unit,
            range_minimum=self.range_minimum,
            range_maximum=self.range_maximum,
            conditions=self.conditions,
            uncertainty_floor=self.best_capability,
        )

    def to_json(self) -> dict[str, Any]:
        """Return the scope as the accreditation body would publish it.

        Returns:
            A JSON-compatible dictionary. Members that do not apply to the scope are
            omitted rather than being present and null, so that a JSON Schema can
            distinguish a calibration scope from a testing one.
        """
        document: dict[str, Any] = {
            "id": self.url,
            "type": "AccreditationScope",
            "identifier": self.identifier,
            "accreditationBody": self.body,
            "accreditationBodyName": self.body_name,
            "organisation": self.organisation,
            "organisationName": self.organisation_name,
            "conformityAssessmentStandard": self.standard,
            "activity": self.activity,
            "field": self.field,
            "conditions": self.conditions,
            "validFrom": self.valid_from,
            "validUntil": self.valid_until,
        }
        if self.measurand is not None:
            document["measurand"] = self.measurand
        if self.unit is not None:
            document["unit"] = self.unit
        if self.range_minimum is not None:
            document["rangeMinimum"] = self.range_minimum
        if self.range_maximum is not None:
            document["rangeMaximum"] = self.range_maximum
        if self.best_capability is not None:
            document["bestMeasurementCapability"] = {
                **self.best_capability.to_json(),
                "description": self.best_capability.describe(self.unit or ""),
            }
        if self.methods:
            document["methods"] = list(self.methods)
        return document


def scope_url(identifier: str) -> str:
    """Return the published address of an accreditation scope.

    Args:
        identifier: The accreditation number, for example ``SCS 0123``.

    Returns:
        The URL the accreditation body serves that scope at.
    """
    return f"{SAS_ORIGIN}/accreditation/{identifier.replace(' ', '-')}"


#: The accreditation scopes granted in the demonstration world.
ACCREDITATION_SCOPES: tuple[AccreditationScope, ...] = (
    AccreditationScope(
        identifier="SCS 0123",
        body="did:web:sas.example",
        body_name="Swiss Accreditation Service (demonstration)",
        organisation="did:web:callab.example",
        organisation_name="Alpine Calibration Laboratory AG (demonstration)",
        standard="ISO/IEC 17025:2017",
        activity="Calibration",
        field="Electricity and Magnetism, DC resistance",
        conditions="(23.0 +/- 2.0) degC, DC, four-terminal connection",
        valid_from="2024-07-01",
        valid_until="2029-06-30",
        measurand="dc.resistance",
        unit="ohm",
        range_minimum=1.0,
        range_maximum=1.0e6,
        best_capability=UncertaintyFloor(absolute=1.0e-3, relative=5.0e-6),
    ),
    AccreditationScope(
        identifier="STS 0456",
        body="did:web:sas.example",
        body_name="Swiss Accreditation Service (demonstration)",
        organisation="did:web:testlab.example",
        organisation_name="Helvetia Testing Services GmbH (demonstration)",
        standard="ISO/IEC 17025:2017",
        activity="Testing",
        field="Electrical safety of household and similar appliances",
        conditions="Laboratory ambient conditions",
        valid_from="2024-09-01",
        valid_until="2029-08-31",
        methods=(
            "IEC 60335-1 clause 16, leakage current and electric strength",
            "IEC 60335-1 clause 29, insulation resistance",
        ),
    ),
    AccreditationScope(
        identifier="SCESp 0789",
        body="did:web:sas.example",
        body_name="Swiss Accreditation Service (demonstration)",
        organisation="did:web:cab.example",
        organisation_name="Confoederatio Product Certification AG (demonstration)",
        standard="ISO/IEC 17065:2012",
        activity="Product certification",
        field="Low voltage electrical equipment",
        conditions="Certification against the referenced product standards",
        valid_from="2024-04-01",
        valid_until="2029-03-31",
        methods=("IEC 60335-1, safety of household and similar electrical appliances",),
    ),
)

_BY_IDENTIFIER = {scope.identifier: scope for scope in ACCREDITATION_SCOPES}
_BY_URL = {scope.url: scope for scope in ACCREDITATION_SCOPES}


def scope_by_id(reference: str) -> AccreditationScope | None:
    """Look up an accreditation scope by identifier or by published URL.

    Args:
        reference: An accreditation number such as ``SCS 0123``, or the URL a
            credential references it by.

    Returns:
        The scope, or None when nothing is published under that reference.
    """
    return _BY_IDENTIFIER.get(reference) or _BY_URL.get(reference)


def scopes_for_organisation(organisation: str) -> tuple[AccreditationScope, ...]:
    """Return every scope granted to one organisation.

    Args:
        organisation: DID of the accredited organisation.

    Returns:
        The granted scopes, in registry order.
    """
    return tuple(
        scope for scope in ACCREDITATION_SCOPES if scope.organisation == organisation
    )
