"""The OIML certification system: Recommendations, and the types evaluated against them.

Under the OIML-CS a certification body in a Member State -- an Issuing Authority -- may
issue an OIML certificate stating that a *type* of measuring instrument meets the
requirements of a specific OIML Recommendation. The technical work behind it is done by a
Test Laboratory recognised within the scheme, which performs the type evaluation and
issues a report the Issuing Authority reviews.

Two things about that make it worth modelling here, and neither has a counterpart
elsewhere in this demonstration.

**The Recommendation is the scope.** An accreditation scope and a CMC are declarations an
organisation writes about itself, which is why ``domain/scope.py`` had to invent a
machine-checkable form for them. A Recommendation is a numbered, edition-controlled
document published by somebody else, and the OIML is working towards machine-readable
versions of them. So the bound on what an Issuing Authority may certify is a reference to
a document rather than a paraphrase of one, which is a stronger position to argue from.

**The subject is a type, not an artefact.** ``domain/instruments.py`` models one physical
object with a serial number, because a calibration certificate is a statement about that
object at that time. A type certificate covers a design, so the same document travels with
every instrument built to it. :class:`InstrumentType` is separate for that reason rather
than for convenience: giving ``Instrument`` an optional serial number would have made the
distinction disappear into a nullable field.

What this module does not model, deliberately:

- **Legal effect.** An OIML certificate is evidence and not permission. The demonstration
  carries that on the credential itself, in ``legalEffect``, and does not model the
  national authority that would convert one into the other. See ``ARCHITECTURE.md``.
- **Scheme A and Scheme B.** The OIML-CS has both. What distinguishes them was not
  established from a primary source while this was written, so nothing here depends on the
  difference and chapter 11 says so rather than guessing.
- **Utilizers and Associates.** Two of the scheme's four stakeholder categories, out of
  scope for the same reason the national layer is.

Every identifier, type designation and numeric value below is invented. The Recommendation
numbers are real; the requirements attributed to them here are not taken from the
published documents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vcqi.config import OIML_ORIGIN
from vcqi.domain.scope import DeclaredCapability, UncertaintyFloor

__all__ = [
    "Recommendation",
    "InstrumentType",
    "RECOMMENDATIONS",
    "INSTRUMENT_TYPES",
    "recommendation_by_id",
    "recommendation_url",
    "instrument_type_by_id",
]


def recommendation_url(number: str) -> str:
    """Return the address a Recommendation is published at.

    Args:
        number: The Recommendation number, for example ``R 46``.

    Returns:
        The URL, with the space in the number replaced by a hyphen.
    """
    return f"{OIML_ORIGIN}/recommendations/{number.replace(' ', '-')}"


@dataclass(frozen=True)
class Recommendation:
    """One OIML Recommendation, reduced to the parts a scope check needs.

    A real Recommendation is a document of a hundred pages or more. What a verifier needs
    from it is narrower: which quantity is regulated, over what range, to what accuracy
    class, and how much measurement uncertainty the evaluating laboratory is allowed to
    have before its verdict stops meaning anything.

    Attributes:
        number: The Recommendation number, for example ``R 46``.
        edition: Year of the edition, because a certificate is issued against one
            edition and editions are not interchangeable.
        title: Title of the Recommendation.
        instrument_category: The kind of instrument it governs.
        regulated_quantity: The quantity the instrument measures, for prose.
        regulated_unit: Unit of that quantity.
        measurand: Machine-readable identifier of the quantity a type evaluation
            actually reports, which is the *error* of the instrument rather than the
            quantity it measures. A meter under evaluation is not asked what energy it
            recorded; it is asked how far its reading was from the truth.
        unit: Unit symbol the reported error and its range are expressed in.
        range_minimum: Most negative error the Recommendation admits, in ``unit``.
        range_maximum: Most positive error it admits, in ``unit``.
        accuracy_classes: The classes it defines, most accurate first.
        conditions: The reference conditions its requirements are stated at.
        evaluation_uncertainty: The smallest Expanded Uncertainty the scheme recognises
            for an evaluation against this Recommendation. Expressed as an uncertainty
            floor, and checked in the same direction a CMC is: a laboratory claiming
            better than the scheme recognises is the suspicious case, not the reassuring
            one. Whether the uncertainty is *small enough* to support a verdict is a
            different question, and this demonstration does not add a step for it.
        machine_readable: Whether a machine-actionable form of the requirements exists.
            ``False`` everywhere today, which is the point of the chapter 11 item.
    """

    number: str
    edition: str
    title: str
    instrument_category: str
    regulated_quantity: str
    regulated_unit: str
    measurand: str
    unit: str
    range_minimum: float
    range_maximum: float
    accuracy_classes: tuple[str, ...]
    conditions: str
    evaluation_uncertainty: UncertaintyFloor
    machine_readable: bool = False

    @property
    def identifier(self) -> str:
        """Return the number and edition together, as a certificate cites them."""
        return f"OIML {self.number}:{self.edition}"

    @property
    def url(self) -> str:
        """Return the address this Recommendation is published at."""
        return recommendation_url(self.number)

    def as_capability(self) -> DeclaredCapability:
        """Express the Recommendation as a capability a claim can be checked against.

        This is what lets the existing ``scope.*`` verification steps do the work: an
        Issuing Authority recognised for this Recommendation may certify a type whose
        evaluated quantity falls inside it, and a type evaluation whose uncertainty is
        too large to support a verdict fails the same check a calibration would.

        Returns:
            The capability, labelled with the Recommendation identifier.
        """
        return DeclaredCapability(
            label=f"Recommendation {self.identifier}",
            measurand=self.measurand,
            unit=self.unit,
            range_minimum=self.range_minimum,
            range_maximum=self.range_maximum,
            conditions=self.conditions,
            uncertainty_floor=self.evaluation_uncertainty,
        )

    def to_json(self) -> dict[str, Any]:
        """Return the form published in the registry and embedded in a credential.

        The member names follow what a verifier already looks for in a CMC entry or an
        accreditation scope -- ``measurand``, ``unit``, ``rangeMinimum``,
        ``rangeMaximum`` and an uncertainty block -- so that the existing capability
        check reads this document without being taught a third shape.

        ``methods`` carries the Recommendation identifier for the same reason: a
        certificate states the Recommendation it was issued against, and the method path
        of the capability check is what compares the two.
        """
        return {
            "id": self.url,
            "type": "OimlRecommendation",
            "number": self.number,
            "edition": self.edition,
            "identifier": self.identifier,
            "title": self.title,
            "instrumentCategory": self.instrument_category,
            "regulatedQuantity": self.regulated_quantity,
            "regulatedUnit": self.regulated_unit,
            "measurand": self.measurand,
            "unit": self.unit,
            "rangeMinimum": self.range_minimum,
            "rangeMaximum": self.range_maximum,
            "evaluationUncertainty": self.evaluation_uncertainty.to_json(),
            "accuracyClasses": list(self.accuracy_classes),
            "conditions": self.conditions,
            "methods": [f"{self.identifier}, {self.title}"],
            "machineReadable": self.machine_readable,
        }


@dataclass(frozen=True)
class InstrumentType:
    """A design, rather than an instance of one.

    The distinction matters to a verifier. A calibration certificate names a serial
    number and says what that object did on one day. A type certificate names a design
    and says what any instrument built to it will do, which is why the same certificate
    travels with every unit shipped and why it stays valid for a decade rather than a
    year.

    Attributes:
        id: Stable identifier used as the credential subject.
        kind: What the design is, for example ``ActiveElectricalEnergyMeter``.
        name: Human-readable description.
        manufacturer: DID of the organisation that makes it.
        manufacturer_name: Human-readable name of that organisation.
        type_designation: The manufacturer's designation for the type.
        accuracy_class: The class from the Recommendation the type is evaluated to.
        modules: Named modules the type is composed of, which the OIML-CS treats as
            separately certifiable. Empty where the type is evaluated whole.
    """

    id: str
    kind: str
    name: str
    manufacturer: str
    manufacturer_name: str
    type_designation: str
    accuracy_class: str
    modules: tuple[str, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, Any]:
        """Return the JSON-LD form spread into a credential subject.

        Shaped like ``Instrument.to_json`` so the two read alike in a document, and so a
        reader who has followed a calibration certificate recognises the pattern.
        """
        document: dict[str, Any] = {
            "id": self.id,
            "type": self.kind,
            "name": self.name,
            "manufacturer": {
                "id": self.manufacturer,
                "type": "Organization",
                "name": self.manufacturer_name,
            },
            "typeDesignation": self.type_designation,
            "accuracyClass": self.accuracy_class,
        }
        if self.modules:
            document["modules"] = list(self.modules)
        return document


#: The Recommendations this demonstration knows about.
#:
#: R 46 is the one the worked example uses, because a type evaluation of an electricity
#: meter needs calibrated electrical standards -- which is exactly what METAS and Alpine
#: Calibration already provide in this world, so the traceability into the test is real
#: rather than asserted.
#:
#: R 60 is here unevaluated, and on purpose. It is the Recommendation the OIML has named
#: as the pilot for its machine-readable work, and it is what the Issuing Authority in
#: this demonstration is *not* recognised for -- which is what makes the scope check
#: something other than a formality.
RECOMMENDATIONS: tuple[Recommendation, ...] = (
    Recommendation(
        number="R 46",
        edition="2012",
        title="Active electrical energy meters",
        instrument_category="Electricity meter",
        regulated_quantity="Active electrical energy",
        regulated_unit="kWh",
        # What the evaluation reports is the meter's percentage error, so that is the
        # quantity the capability check compares. The range is the widest error any
        # accuracy class in the Recommendation admits; the class narrows it further, and
        # the individual test results carry their own limits.
        measurand="ac.active.energy.error",
        unit="%",
        range_minimum=-2.0,
        range_maximum=2.0,
        accuracy_classes=("A", "B", "C"),
        conditions=(
            "Reference conditions: 230 V, 50 Hz, unity power factor, 23 degrees Celsius"
        ),
        # The smallest uncertainty the scheme recognises for an evaluation against R 46:
        # 0.02 percentage points, plus 5 percent of the error being reported, at k = 2.
        evaluation_uncertainty=UncertaintyFloor(
            absolute=0.02, relative=0.05, coverage_factor=2.0
        ),
    ),
    Recommendation(
        number="R 60",
        edition="2017",
        title="Metrological regulation for load cells",
        instrument_category="Load cell",
        regulated_quantity="Force",
        regulated_unit="N",
        measurand="force.relative.error",
        unit="%",
        range_minimum=-1.0,
        range_maximum=1.0,
        accuracy_classes=("A", "B", "C", "D"),
        conditions="Reference conditions per the Recommendation",
        evaluation_uncertainty=UncertaintyFloor(
            absolute=0.01, relative=0.05, coverage_factor=2.0
        ),
    ),
)

#: The instrument types this demonstration certifies.
INSTRUMENT_TYPES: tuple[InstrumentType, ...] = (
    InstrumentType(
        id="urn:type:meterworks:mw-e3:rev-b",
        kind="ActiveElectricalEnergyMeter",
        name="Meterworks MW-E3 three-phase static electricity meter",
        manufacturer="did:web:meterworks.example",
        manufacturer_name="Meterworks Instrumentation AG (demonstration)",
        type_designation="MW-E3 rev B",
        accuracy_class="B",
        modules=("measuring module MW-M1", "display module MW-D1"),
    ),
)

_RECOMMENDATIONS_BY_NUMBER: dict[str, Recommendation] = {
    recommendation.number: recommendation for recommendation in RECOMMENDATIONS
}
_TYPES_BY_ID: dict[str, InstrumentType] = {
    instrument_type.id: instrument_type for instrument_type in INSTRUMENT_TYPES
}


def recommendation_by_id(reference: str) -> Recommendation | None:
    """Look up a Recommendation by number, identifier or URL.

    Three forms because three callers hold three different things: a scenario holds the
    number, a credential holds the identifier, and a verifier holds whatever URL the
    credential pointed at.

    Args:
        reference: ``R 46``, ``OIML R 46:2012``, or the published URL.

    Returns:
        The Recommendation, or ``None`` when nothing matches.
    """
    direct = _RECOMMENDATIONS_BY_NUMBER.get(reference)
    if direct is not None:
        return direct
    for recommendation in RECOMMENDATIONS:
        if reference in (recommendation.identifier, recommendation.url):
            return recommendation
    return None


def instrument_type_by_id(type_id: str) -> InstrumentType | None:
    """Look up an instrument type by its identifier.

    Args:
        type_id: The ``urn:type:`` identifier.

    Returns:
        The type, or ``None`` when it is not one of the demonstration's types.
    """
    return _TYPES_BY_ID.get(type_id)
