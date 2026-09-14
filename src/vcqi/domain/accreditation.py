"""Accreditation scopes issued by an accreditation body under the Global ACI MRA.

An accreditation scope is the accreditation-body counterpart of a CMC: it states which
activity a laboratory is competent to perform, over which levels, and for calibration
work the smallest Expanded Uncertainty it may claim. That last figure is usually called
the best measurement capability.

Where it stops resembling a CMC is in its shape. A CMC entry is one row. A published
calibration scope is a **table** -- a real one runs to dozens of rows over several pages
-- and the rows are keyed by more than the quantity: by whether the object calibrated is
a measuring instrument or a material measure, by the conditions the capability was
demonstrated under, and by a coverage column that is sometimes an interval, sometimes a
list of fixed values and sometimes a nominal with a tolerance. ``SCS 0123`` below is
modelled on that structure rather than on a convenient subset of it, which is why it is
the only scope here with rows and why the scope check has to choose one before it can
adjudicate anything. See :mod:`vcqi.domain.scope` for the grammars.

The three scopes here cover the three roles the demonstration needs: a calibration
laboratory under ISO/IEC 17025, a testing laboratory under the same standard, and a
product certification body under ISO/IEC 17065, which is the conformity assessment body
of the Product Conformity use case in the Recognized Entities specification. Only the
first states measurement capabilities; the other two are bounded by the methods they
list, which is what a testing or certification scope actually does.

Every identifier is fictional and deliberately shaped like, but not equal to, the
numbering a real accreditation body uses. The *shape* of the calibration rows is taken
from a published scope; none of the values are.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vcqi.config import SAS_ORIGIN
from vcqi.domain.scope import (
    ConditionBand,
    Interval,
    Points,
    ScopeRow,
    UncertaintyFloor,
)

__all__ = [
    "AccreditationScope",
    "ACCREDITATION_SCOPES",
    "scope_by_id",
    "scope_url",
    "scopes_for_organisation",
]


#: The band a row covering direct current is declared under. Written as its own constant
#: because three rows share it and because ``DC`` is a frequency of zero rather than the
#: absence of a frequency -- a distinction the verifier has to be able to make, since a
#: certificate stating no frequency at all is a different case again.
DIRECT_CURRENT = ConditionBand(
    quantity="frequency", minimum=0.0, maximum=0.0, unit="Hz", text="DC"
)


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
        conditions: Conditions the scope as a whole is valid under. Prose, and for a
            calibration scope the per-row :class:`~vcqi.domain.scope.ConditionBand` is
            what actually decides anything.
        valid_from: Start of validity, as an ISO 8601 date.
        valid_until: End of validity, as an ISO 8601 date.
        rows: The capability table, in register order, for a calibration scope. Empty
            for a testing or certification scope, which is bounded by its methods.
        methods: Standards or methods the scope covers, for testing and certification.
        language_precedence: Which language version governs when the versions of the
            register disagree, or None when the register says nothing. A published scope
            really does carry a line like this, which makes it the one place in this
            demonstration where a precedence rule already exists rather than being an
            open question.
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
    rows: tuple[ScopeRow, ...] = ()
    methods: tuple[str, ...] = ()
    language_precedence: str | None = None

    @property
    def url(self) -> str:
        """Return the address at which this scope is published.

        Returns:
            The URL a credential uses when it references this accreditation.
        """
        return scope_url(self.identifier)

    def as_rows(self) -> tuple[ScopeRow, ...]:
        """Return the capability table the scope check selects from.

        Returns:
            The rows, in register order. Empty for a scope that declares no measurement
            capability and therefore cannot be checked numerically.
        """
        return self.rows

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
        if self.rows:
            document["rows"] = [row.to_json() for row in self.rows]
        if self.methods:
            document["methods"] = list(self.methods)
        if self.language_precedence is not None:
            document["languagePrecedence"] = self.language_precedence
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
#:
#: ``SCS 0123`` has four rows and every one of them is there to be awkward in a way a
#: published scope is awkward. Row 1 covers fixed values rather than an interval, and
#: carries remarks that no model here reads. Row 2 has a strict upper bound and a better
#: capability than row 1 for the same quantity, because calibrating a resistance is not
#: calibrating an ohmmeter. Rows 3 and 4 are identical except for the frequency band, and
#: declare different capabilities -- which is the case that makes the conditions an axis
#: to match on rather than prose to print.
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
        conditions="(23.0 +/- 2.0) degC, four-terminal connection",
        valid_from="2024-07-01",
        valid_until="2029-06-30",
        language_precedence=(
            "In case of contradictions between the language versions of this scope, "
            "the French version applies."
        ),
        rows=(
            ScopeRow(
                label="SCS 0123 row 1",
                measurand="dc.resistance",
                unit="ohm",
                object_category="measuringInstrument",
                coverage=Points(values=(10.0, 100.0, 1.0e3, 1.0e4, 1.0e5)),
                floor=UncertaintyFloor(absolute=1.0e-3, relative=5.0e-6),
                condition=DIRECT_CURRENT,
                remarks=(
                    "The stated uncertainties are valid for the fixed values only.",
                    "On-site calibration is also covered, with appropriate measurement "
                    "uncertainty.",
                ),
            ),
            ScopeRow(
                label="SCS 0123 row 2",
                measurand="dc.resistance",
                unit="ohm",
                object_category="materialMeasure",
                coverage=Interval(minimum=1.0, maximum=2.2e5, upper="exclusive"),
                floor=UncertaintyFloor(absolute=5.0e-4, relative=2.0e-6),
                condition=DIRECT_CURRENT,
                remarks=("Resistances in the form of cylindrical rods.",),
            ),
            ScopeRow(
                label="SCS 0123 row 3",
                measurand="ac.resistance",
                unit="ohm",
                object_category="materialMeasure",
                coverage=Interval(minimum=1.0e-3, maximum=1.0),
                floor=UncertaintyFloor(absolute=0.0, relative=2.6e-4),
                condition=ConditionBand(
                    quantity="frequency",
                    minimum=0.0,
                    maximum=2.5,
                    unit="Hz",
                    text="DC ... 2,5 Hz",
                ),
            ),
            ScopeRow(
                label="SCS 0123 row 4",
                measurand="ac.resistance",
                unit="ohm",
                object_category="materialMeasure",
                coverage=Interval(minimum=1.0e-3, maximum=1.0),
                floor=UncertaintyFloor(absolute=0.0, relative=8.1e-4),
                condition=ConditionBand(
                    quantity="frequency",
                    minimum=2.5,
                    maximum=20.0,
                    unit="Hz",
                    text="2,5 Hz ... 20 Hz",
                ),
            ),
        ),
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
        activity="Products certification",
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
