"""Deciding whether a stated measurement result falls inside a declared capability.

Two very similar declarations appear in the quality infrastructure:

* a **CMC** entry, which a National Metrology Institute publishes in the BIPM key
  comparison database and which bounds what it may claim under the CIPM MRA;
* an **accreditation scope**, which an accreditation body issues to a laboratory under
  ISO/IEC 17025 and which bounds what that laboratory may claim as accredited work.

Both say the same three things: which measurand, over which levels, and with what
smallest Expanded Uncertainty. So both are represented here as a
:class:`DeclaredCapability`, and one function decides whether a given result is covered.

The uncertainty bound runs in the direction people new to the field usually get
backwards. A capability states the *smallest* uncertainty an institute can achieve. A
certificate claiming a *larger* uncertainty is comfortably inside scope; a certificate
claiming a *smaller* one is claiming to have done better than it has ever demonstrated,
and is out of scope. Getting this check wrong in the permissive direction is exactly the
failure that lets an unjustified CIPM MRA logo through.

**A published scope is a table, not a row.** A CMC entry really is one row. An
accreditation scope is not: a real one runs to dozens of rows, and the rows use grammars
that a single minimum and maximum cannot hold. Three of them appear on the first page of
a published calibration scope:

* ``19,2 ohm ; 192 ohm`` -- discrete fixed levels, with a remark saying the stated
  uncertainty is valid at those levels only. That is not a range;
* ``1 ohm ... < 220 kohm`` -- an interval whose upper bound is strict;
* ``(22,5 +/- 2,5) uohm`` -- a nominal with a tolerance band.

And the row is keyed by more than the quantity. The same quantity over the same levels
carries a different capability at a different frequency, so the conditions are an axis
the verifier has to match on rather than prose it can print. The register also separates
calibrating a *measuring instrument* from calibrating a *material measure* -- VIM 3.1
and VIM 3.6 -- and gives the two different capabilities.

So a scope check is two decisions, not one: **which row applies**, and then **does the
claim fit that row**. :func:`select_row` makes the first, :func:`evaluate_scope` makes
the second, and keeping them apart is what lets a verifier say a claim was refused
because no row covered it rather than because its uncertainty was too small.

What no model here holds is the remarks column. "Resistances in form of cylindrical
rods" restricts a row, and "on-site calibration as well with appropriate measurement
uncertainty" extends one by an unstated amount. Modelling either would mean inventing a
rule no register has agreed, so the remarks travel as text and the verifier reports that
the row deciding the verdict carried words nobody read.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Union

__all__ = [
    "UncertaintyFloor",
    "Interval",
    "Points",
    "Window",
    "Coverage",
    "coverage_from_json",
    "ConditionBand",
    "condition_band_from_json",
    "ScopeRow",
    "scope_row_from_json",
    "DeclaredCapability",
    "MeasurementClaim",
    "RowRejection",
    "RowSelection",
    "select_row",
    "union_capability",
    "union_capabilities",
    "ScopeCheck",
    "ScopeVerdict",
    "evaluate_scope",
    "DEFAULT_POINT_TOLERANCE",
]


#: Relative tolerance used to decide which stated level a reading belongs to, when a row
#: covers discrete fixed levels rather than a continuous interval. Dimensionless.
#:
#: This number is a model artefact and no register states it. A row reading
#: ``19,2 ohm ; 192 ohm`` means "at these levels", and a certificate for a nominal
#: 19,2 ohm resistor reports something like 19,2003 ohm. Something has to decide how far
#: a level may sit from a stated point and still be that point, and nobody has written
#: down what. It is published inside the scope document rather than kept in this module,
#: so that a verifier reading the register can see the assumption it is inheriting.
DEFAULT_POINT_TOLERANCE = 1.0e-3


@dataclass(frozen=True)
class UncertaintyFloor:
    """The smallest Expanded Uncertainty a capability covers, as a function of level.

    CMC entries rarely state a single number. Below some level a fixed floor dominates,
    above it the uncertainty grows in proportion to the measured value, and the two are
    combined in quadrature. That is the form used here.

    A published accreditation scope is usually simpler and states one term only --
    ``125 x 10^-6 R``, or ``0,2 dB``, or ``1,2 %``. Both are this class with one term set
    to zero, and :meth:`describe` renders whichever terms are actually present rather
    than a quadrature sum with a zero inside it.

    Attributes:
        absolute: The fixed term, in the unit of the measurand.
        relative: The proportional term, dimensionless.
        coverage_factor: The coverage factor k the floor is expressed at. The CIPM MRA
            requires k = 2, and a claim stated at any other k cannot be compared
            without restating it first.
    """

    absolute: float
    relative: float
    coverage_factor: float = 2.0

    def evaluate(self, value: float) -> float:
        """Return the smallest covered Expanded Uncertainty at a measured level.

        Args:
            value: The measured value, in the unit of the measurand.

        Returns:
            The Expanded Uncertainty U at that level, in the same unit.
        """
        proportional = self.relative * abs(value)
        return math.sqrt(self.absolute * self.absolute + proportional * proportional)

    def describe(self, unit: str) -> str:
        """Render the floor the way a register would state it.

        A register writing ``125 x 10^-6 R`` has not written a quadrature sum, and
        printing one back at the reader would be putting words in its mouth. So a floor
        with one term set to zero renders as the single term it is.

        Args:
            unit: Unit symbol of the measurand.

        Returns:
            A human-readable description of the floor.
        """
        relative_ppm = self.relative * 1e6
        absolute_term = f"{self.absolute:g} {unit}".strip()
        relative_term = f"{relative_ppm:g} x 10^-6 x value"
        coverage = f", k = {self.coverage_factor:g}"
        if self.relative == 0.0:
            return f"U = {absolute_term}{coverage}"
        if self.absolute == 0.0:
            return f"U = {relative_term}{coverage}"
        return f"U = sqrt(({absolute_term})^2 + ({relative_term})^2){coverage}"

    def to_json(self) -> dict[str, Any]:
        """Return the floor as a JSON-compatible dictionary.

        Returns:
            The absolute and relative terms with the coverage factor.
        """
        return {
            "absoluteTerm": self.absolute,
            "relativeTerm": self.relative,
            "coverageFactor": self.coverage_factor,
        }


@dataclass(frozen=True)
class Interval:
    """A continuous band of levels, with bounds that may be open or closed.

    The strict bound is not pedantry. A published scope reads ``1 ohm ... < 220 kohm``,
    and a model that could only hold inclusive bounds would quietly grant a laboratory a
    level its accreditation body deliberately excluded.

    Attributes:
        minimum: Lowest covered level, in the unit of the row.
        maximum: Highest covered level, in the unit of the row.
        lower: ``inclusive`` or ``exclusive``.
        upper: ``inclusive`` or ``exclusive``.
        level_basis: Which level a claim is matched on. An interval bounds the reported
            value.
    """

    minimum: float
    maximum: float
    lower: str = "inclusive"
    upper: str = "inclusive"

    level_basis: str = field(default="value", init=False, repr=False)

    def covers(self, level: float) -> bool:
        """Return whether a level falls inside the interval.

        Args:
            level: The level to test, in the unit of the row.

        Returns:
            True when the level is inside, honouring strict bounds.
        """
        above = (
            level > self.minimum if self.lower == "exclusive" else level >= self.minimum
        )
        below = (
            level < self.maximum if self.upper == "exclusive" else level <= self.maximum
        )
        return above and below

    def describe(self, unit: str) -> str:
        """Render the interval the way a register would print it.

        Args:
            unit: Unit symbol of the row.

        Returns:
            A human-readable description of the covered levels.
        """
        low = f"> {self.minimum:g}" if self.lower == "exclusive" else f"{self.minimum:g}"
        high = f"< {self.maximum:g}" if self.upper == "exclusive" else f"{self.maximum:g}"
        return f"{low} ... {high} {unit}".strip()

    def to_json(self) -> dict[str, Any]:
        """Return the interval as a JSON-compatible dictionary.

        Returns:
            The bounds and whether each is inclusive.
        """
        return {
            "type": "Interval",
            "minimum": self.minimum,
            "maximum": self.maximum,
            "lowerBound": self.lower,
            "upperBound": self.upper,
        }

    def span(self) -> tuple[float, float]:
        """Return the lowest and highest level the coverage touches.

        Returns:
            The minimum and maximum, in the unit of the row.
        """
        return (self.minimum, self.maximum)


@dataclass(frozen=True)
class Points:
    """Discrete fixed levels, which is what a row of fixed values means.

    A register writing ``19,2 ohm ; 192 ohm`` alongside the remark that the stated
    uncertainty is valid for fixed values only has not declared the interval between
    them. It has declared two levels.

    Attributes:
        values: The covered levels, in the unit of the row.
        match_tolerance: Relative tolerance used to decide whether a level *is* one of
            the stated points. Dimensionless. See :data:`DEFAULT_POINT_TOLERANCE` for
            why this exists and why it is published rather than hidden.
        level_basis: Which level a claim is matched on. A fixed-value row is about the
            nominal of the calibrated object, not about the reading: a nominal 19,2 ohm
            resistor reports 19,2003 ohm and is still the 19,2 ohm point.
    """

    values: tuple[float, ...]
    match_tolerance: float = DEFAULT_POINT_TOLERANCE

    level_basis: str = field(default="nominal", init=False, repr=False)

    def covers(self, level: float) -> bool:
        """Return whether a level is one of the stated points.

        Args:
            level: The level to test, in the unit of the row.

        Returns:
            True when the level sits within the match tolerance of a stated point.
        """
        for point in self.values:
            allowance = (
                self.match_tolerance * abs(point) if point else self.match_tolerance
            )
            if abs(level - point) <= allowance:
                return True
        return False

    def describe(self, unit: str) -> str:
        """Render the points the way a register would print them.

        Args:
            unit: Unit symbol of the row.

        Returns:
            A human-readable description of the covered levels.
        """
        listed = " ; ".join(f"{value:g}" for value in self.values)
        tolerance = f"{self.match_tolerance * 100:g}"
        return (
            f"{listed} {unit}".strip()
            + f", fixed values only (matched within {tolerance} %)"
        )

    def to_json(self) -> dict[str, Any]:
        """Return the points as a JSON-compatible dictionary.

        Returns:
            The covered levels and the tolerance they are matched within.
        """
        return {
            "type": "Points",
            "values": list(self.values),
            "matchTolerance": self.match_tolerance,
        }

    def span(self) -> tuple[float, float]:
        """Return the lowest and highest level the coverage touches.

        Returns:
            The smallest and largest stated point, in the unit of the row.
        """
        return (min(self.values), max(self.values))


@dataclass(frozen=True)
class Window:
    """A nominal level with a tolerance band, as in ``(22,5 +/- 2,5) uohm``.

    Attributes:
        nominal: The centre of the band, in the unit of the row.
        tolerance: Half-width of the band, in the unit of the row.
        level_basis: Which level a claim is matched on. Like :class:`Points`, a window
            states which object the row is about rather than bounding a reading.
    """

    nominal: float
    tolerance: float

    level_basis: str = field(default="nominal", init=False, repr=False)

    def covers(self, level: float) -> bool:
        """Return whether a level falls inside the band.

        Args:
            level: The level to test, in the unit of the row.

        Returns:
            True when the level is within the tolerance of the nominal.
        """
        return abs(level - self.nominal) <= self.tolerance

    def describe(self, unit: str) -> str:
        """Render the window the way a register would print it.

        Args:
            unit: Unit symbol of the row.

        Returns:
            A human-readable description of the covered levels.
        """
        return f"({self.nominal:g} +/- {self.tolerance:g}) {unit}".strip()

    def to_json(self) -> dict[str, Any]:
        """Return the window as a JSON-compatible dictionary.

        Returns:
            The nominal and the tolerance.
        """
        return {"type": "Window", "nominal": self.nominal, "tolerance": self.tolerance}

    def span(self) -> tuple[float, float]:
        """Return the lowest and highest level the coverage touches.

        Returns:
            The band edges, in the unit of the row.
        """
        return (self.nominal - self.tolerance, self.nominal + self.tolerance)


#: The three grammars a register uses to say which levels a row covers.
Coverage = Union[Interval, Points, Window]


def coverage_from_json(document: Any) -> Coverage | None:
    """Rebuild a coverage from the form a register publishes it in.

    Args:
        document: The ``coverage`` member of a published scope row.

    Returns:
        The coverage, or None when the document states none this module understands.
        Returning None rather than raising is deliberate: an unreadable register entry
        should make a verifier decline to adjudicate, not crash.
    """
    if not isinstance(document, dict):
        return None
    try:
        shape = document.get("type")
        if shape == "Interval":
            return Interval(
                minimum=float(document["minimum"]),
                maximum=float(document["maximum"]),
                lower=str(document.get("lowerBound", "inclusive")),
                upper=str(document.get("upperBound", "inclusive")),
            )
        if shape == "Points":
            values = tuple(float(value) for value in document["values"])
            if not values:
                return None
            return Points(
                values=values,
                match_tolerance=float(
                    document.get("matchTolerance", DEFAULT_POINT_TOLERANCE)
                ),
            )
        if shape == "Window":
            return Window(
                nominal=float(document["nominal"]),
                tolerance=float(document["tolerance"]),
            )
    except (KeyError, TypeError, ValueError):
        return None
    return None


@dataclass(frozen=True)
class ConditionBand:
    """A measurement condition the row is declared under, as a band of one quantity.

    This exists because a published scope states the same quantity over the same levels
    twice, at two frequency bands, with two different capabilities. Treating the
    conditions as prose means taking whichever of those rows happens to come first,
    which is not a check.

    Attributes:
        quantity: Identifier of the conditioning quantity, for example ``frequency``.
        minimum: Lowest covered level of that quantity, in ``unit``.
        maximum: Highest covered level of that quantity, in ``unit``.
        unit: Unit symbol of the band, for example ``Hz``.
        text: How the register prints the band, for example ``DC ... 2,5 Hz``.
    """

    quantity: str
    minimum: float
    maximum: float
    unit: str
    text: str

    def covers(self, level: float | None) -> bool | None:
        """Return whether a stated condition falls inside the band.

        Args:
            level: The level the certificate states for this quantity, in ``unit``, or
                None when the certificate states none.

        Returns:
            True or False when the certificate states the quantity, and None when it
            does not -- which is not the same answer and must not be treated as one.
        """
        if level is None:
            return None
        return self.minimum <= level <= self.maximum

    def describe(self) -> str:
        """Render the band the way the register prints it.

        Returns:
            The register's own text, with the quantity named.
        """
        return f"{self.quantity} {self.text}"

    def to_json(self) -> dict[str, Any]:
        """Return the band as a JSON-compatible dictionary.

        Returns:
            The quantity, the bounds, the unit and the printed text.
        """
        return {
            "quantity": self.quantity,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "unit": self.unit,
            "text": self.text,
        }


def condition_band_from_json(document: Any) -> ConditionBand | None:
    """Rebuild a condition band from the form a register publishes it in.

    Args:
        document: The ``condition`` member of a published scope row.

    Returns:
        The band, or None when the document states none.
    """
    if not isinstance(document, dict):
        return None
    try:
        return ConditionBand(
            quantity=str(document["quantity"]),
            minimum=float(document["minimum"]),
            maximum=float(document["maximum"]),
            unit=str(document.get("unit", "")),
            text=str(document.get("text", "")),
        )
    except (KeyError, TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ScopeRow:
    """One row of a published accreditation scope.

    Attributes:
        label: Short identifier for messages, for example ``SCS 0123 row 2``.
        measurand: Identifier of the measured quantity, for example ``dc.resistance``.
        unit: Unit symbol the coverage and the floor are expressed in.
        object_category: What kind of object the row is about, in VIM terms:
            ``measuringInstrument`` (VIM 3.1) or ``materialMeasure`` (VIM 3.6). A
            register that separates calibrating an ohmmeter from calibrating a
            resistance is making exactly this distinction, and gives the two rows
            different capabilities.
        coverage: Which levels the row covers.
        floor: Smallest Expanded Uncertainty the row permits, at k as stated.
        condition: The condition band the row is declared under, or None for a row the
            register states without one.
        remarks: The register's own remarks column, verbatim. Never adjudicated; see the
            module docstring for why.
    """

    label: str
    measurand: str
    unit: str
    object_category: str
    coverage: Coverage
    floor: UncertaintyFloor
    condition: ConditionBand | None = None
    remarks: tuple[str, ...] = ()

    def as_capability(self) -> DeclaredCapability:
        """Return the row in the form the scope check consumes.

        Returns:
            The declared capability for this row alone.
        """
        return DeclaredCapability(
            label=self.label,
            measurand=self.measurand,
            unit=self.unit,
            coverage=self.coverage,
            conditions=self.condition.describe() if self.condition else "",
            uncertainty_floor=self.floor,
        )

    def to_json(self) -> dict[str, Any]:
        """Return the row as an accreditation body would publish it.

        Returns:
            A JSON-compatible dictionary. The remarks are present even when empty, so
            that a consumer can tell "no remarks" from "remarks not published".
        """
        document: dict[str, Any] = {
            "label": self.label,
            "measurand": self.measurand,
            "unit": self.unit,
            "objectCategory": self.object_category,
            "coverage": self.coverage.to_json(),
            "bestMeasurementCapability": {
                **self.floor.to_json(),
                "description": self.floor.describe(self.unit),
            },
            "remarks": list(self.remarks),
        }
        if self.condition is not None:
            document["condition"] = self.condition.to_json()
        return document


def scope_row_from_json(document: Any) -> ScopeRow | None:
    """Rebuild a scope row from the form a register publishes it in.

    Args:
        document: One entry of a published scope's ``rows``.

    Returns:
        The row, or None when it cannot be read.
    """
    if not isinstance(document, dict):
        return None
    coverage = coverage_from_json(document.get("coverage"))
    floor_source = document.get("bestMeasurementCapability")
    if coverage is None or not isinstance(floor_source, dict):
        return None
    try:
        floor = UncertaintyFloor(
            absolute=float(floor_source["absoluteTerm"]),
            relative=float(floor_source["relativeTerm"]),
            coverage_factor=float(floor_source.get("coverageFactor", 2.0)),
        )
        remarks = document.get("remarks", [])
        return ScopeRow(
            label=str(document.get("label", "row")),
            measurand=str(document["measurand"]),
            unit=str(document["unit"]),
            object_category=str(document.get("objectCategory", "")),
            coverage=coverage,
            floor=floor,
            condition=condition_band_from_json(document.get("condition")),
            remarks=(
                tuple(str(remark) for remark in remarks)
                if isinstance(remarks, list)
                else ()
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


@dataclass(frozen=True)
class DeclaredCapability:
    """What an institute or laboratory has declared it is able to do.

    One CMC entry is one of these. One *row* of an accreditation scope is one of these
    too, which is what lets a single check serve both registers.

    Attributes:
        label: Short identifier for messages, for example ``CMC CH-EM-0042``.
        measurand: Identifier of the measured quantity, for example ``dc.resistance``.
        unit: Unit symbol the coverage and the floor are expressed in.
        coverage: Which levels are covered, in whichever grammar the register used.
        conditions: Measurement conditions the declaration is valid under.
        uncertainty_floor: The smallest covered Expanded Uncertainty.
    """

    label: str
    measurand: str
    unit: str
    coverage: Coverage
    conditions: str
    uncertainty_floor: UncertaintyFloor


@dataclass(frozen=True)
class MeasurementClaim:
    """What a certificate actually states, reduced to the parts a scope check needs.

    Attributes:
        measurand: Identifier of the measured quantity.
        unit: Unit symbol of the reported value.
        value: The reported value, in ``unit``.
        expanded_uncertainty: The reported Expanded Uncertainty U, in ``unit``.
        coverage_factor: The coverage factor k the certificate reports U at.
        nominal: Nominal value of the calibrated object, in ``unit``, or None when the
            certificate states none. A fixed-value scope row is about this rather than
            about the reading.
        object_category: What kind of object was calibrated, in the VIM terms
            :class:`ScopeRow` uses, or an empty string when the certificate says
            nothing.
        conditions: Stated condition quantities, as identifier to level. Empty when the
            certificate states none numerically.
        condition_units: Unit symbol each stated condition is expressed in. A level
            compared against a band declared in another unit is not a comparison, so a
            band whose unit is absent from here is treated as unstated rather than as
            matching.
    """

    measurand: str
    unit: str
    value: float
    expanded_uncertainty: float
    coverage_factor: float
    nominal: float | None = None
    object_category: str = ""
    conditions: dict[str, float] = field(default_factory=dict)
    condition_units: dict[str, str] = field(default_factory=dict)

    def level_for(self, basis: str) -> tuple[float, str]:
        """Return the level a coverage of the given basis should be matched on.

        Args:
            basis: ``nominal`` or ``value``, from the coverage's ``level_basis``.

        Returns:
            The level and where it came from. A nominal-based coverage falls back to the
            reported value when the certificate states no nominal, and says so, because
            silently matching a reading against a fixed-value row is the kind of
            substitution that looks like a check and is not.
        """
        if basis == "nominal":
            if self.nominal is None:
                return (self.value, "reported value, no nominal stated")
            return (self.nominal, "nominal value")
        return (self.value, "reported value")


@dataclass(frozen=True)
class RowRejection:
    """Why one row of a scope was not the row that applies.

    Attributes:
        label: The row's label.
        reason: What did not match, with the values compared.
    """

    label: str
    reason: str

    def to_json(self) -> dict[str, Any]:
        """Return the rejection as a JSON-compatible dictionary.

        Returns:
            The row label and the reason.
        """
        return {"label": self.label, "reason": self.reason}


@dataclass(frozen=True)
class RowSelection:
    """Which row of a scope applies to a claim, and why the others did not.

    Attributes:
        row: The applicable row, or None when no row covers the claim.
        level: The level selection was decided on, in the unit of the claim, or None.
        level_source: Where that level came from, for the reader.
        rejections: One entry per row that did not apply, in register order.
        also_covered: Labels of any further rows that covered the claim. A well-formed
            register has none; when it has some, that is a defect in the register and
            the verifier should say so rather than silently take the first.
    """

    row: ScopeRow | None
    level: float | None
    level_source: str
    rejections: tuple[RowRejection, ...] = ()
    also_covered: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        """Return the selection as a JSON-compatible dictionary.

        Returns:
            The selected row label, the level it was decided on, and every rejection.
        """
        return {
            "selected": self.row.label if self.row else None,
            "level": self.level,
            "levelSource": self.level_source,
            "rejected": [rejection.to_json() for rejection in self.rejections],
            "alsoCovered": list(self.also_covered),
        }


def _rejection_reason(row: ScopeRow, claim: MeasurementClaim) -> str | None:
    """Return why a row does not apply to a claim, or None when it does.

    Args:
        row: The row being considered.
        claim: The claim stated on the certificate.

    Returns:
        A human-readable reason, or None when every condition of the row is met.
    """
    if row.measurand != claim.measurand:
        return f"covers {row.measurand}, the certificate states {claim.measurand}"
    if row.unit != claim.unit:
        return f"declared in {row.unit}, the certificate reports {claim.unit}"
    if claim.object_category and row.object_category != claim.object_category:
        return (
            f"is about a {row.object_category}, "
            f"the certificate is about a {claim.object_category}"
        )
    level, _ = claim.level_for(row.coverage.level_basis)
    if not row.coverage.covers(level):
        return f"covers {row.coverage.describe(row.unit)}, the claim sits at {level:g}"
    if row.condition is not None:
        stated = claim.conditions.get(row.condition.quantity)
        stated_unit = claim.condition_units.get(row.condition.quantity, "")
        if stated is not None and stated_unit != row.condition.unit:
            return (
                f"is declared for {row.condition.describe()} in {row.condition.unit}, "
                f"the certificate states {row.condition.quantity} in "
                f"{stated_unit or 'no unit'}"
            )
        covered = row.condition.covers(stated)
        if covered is None:
            return (
                f"is declared for {row.condition.describe()}, and the certificate "
                f"states no {row.condition.quantity} to compare"
            )
        if not covered:
            return (
                f"is declared for {row.condition.describe()}, the certificate states "
                f"{stated:g} {row.condition.unit}"
            )
    return None


def select_row(rows: tuple[ScopeRow, ...], claim: MeasurementClaim) -> RowSelection:
    """Decide which row of a published scope applies to a claim.

    This is a separate decision from whether the claim fits, and keeping it separate is
    the point. A certificate refused because no row of the scope covers what it did is a
    different finding from one refused because its uncertainty was smaller than the row
    permits, and a verifier reporting both as "outside scope" throws away the more
    useful half.

    Args:
        rows: The published rows, in register order.
        claim: The claim stated on the certificate.

    Returns:
        The selection, carrying the applicable row and a reason for every row that was
        not it.
    """
    matched: list[ScopeRow] = []
    rejections: list[RowRejection] = []
    for row in rows:
        reason = _rejection_reason(row, claim)
        if reason is None:
            matched.append(row)
        else:
            rejections.append(RowRejection(label=row.label, reason=reason))

    if not matched:
        return RowSelection(
            row=None,
            level=None,
            level_source="",
            rejections=tuple(rejections),
        )

    chosen = matched[0]
    level, source = claim.level_for(chosen.coverage.level_basis)
    return RowSelection(
        row=chosen,
        level=level,
        level_source=source,
        rejections=tuple(rejections),
        also_covered=tuple(row.label for row in matched[1:]),
    )


def union_capability(
    rows: tuple[ScopeRow, ...], *, label: str
) -> DeclaredCapability | None:
    """Collapse a whole scope into the one capability an offline schema can express.

    A JSON Schema attached to a recognition is a constant, and a scope is a table. The
    only honest constant over a table is its union: the widest span any row touches, and
    the smallest uncertainty any row permits. That is weaker than every individual row,
    and it gets weaker as the scope gets richer -- which is the argument for why the
    schema catches gross errors and the register decides the rest.

    Args:
        rows: The published rows.
        label: Label for the collapsed capability.

    Returns:
        The union, or None when the rows are empty or disagree about the measurand, the
        unit or the coverage factor, in which case no single constant describes them.
    """
    if not rows:
        return None
    measurands = {row.measurand for row in rows}
    units = {row.unit for row in rows}
    factors = {row.floor.coverage_factor for row in rows}
    if len(measurands) != 1 or len(units) != 1 or len(factors) != 1:
        return None
    spans = [row.coverage.span() for row in rows]
    return DeclaredCapability(
        label=label,
        measurand=measurands.pop(),
        unit=units.pop(),
        coverage=Interval(
            minimum=min(low for low, _ in spans),
            maximum=max(high for _, high in spans),
        ),
        conditions="; ".join(
            row.condition.describe() for row in rows if row.condition is not None
        ),
        uncertainty_floor=UncertaintyFloor(
            absolute=min(row.floor.absolute for row in rows),
            relative=min(row.floor.relative for row in rows),
            coverage_factor=factors.pop(),
        ),
    )


def union_capabilities(
    rows: tuple[ScopeRow, ...], *, label: str
) -> tuple[DeclaredCapability, ...]:
    """Collapse a scope into one capability per quantity it covers.

    A table may cover several quantities, and no single constant describes them all.
    Grouping by measurand and unit first is what lets an offline schema say "one of
    these" rather than giving up -- and the groups are what become the branches of that
    schema.

    Args:
        rows: The published rows.
        label: Label for the scope. Each group is labelled with its measurand when there
            is more than one, so that a message names the branch that decided it.

    Returns:
        One capability per quantity, in the order the quantities first appear. Empty
        when the scope publishes no rows.
    """
    groups: dict[tuple[str, str], list[ScopeRow]] = {}
    for row in rows:
        groups.setdefault((row.measurand, row.unit), []).append(row)

    capabilities: list[DeclaredCapability] = []
    for (measurand, _), grouped in groups.items():
        group_label = f"{label} ({measurand})" if len(groups) > 1 else label
        capability = union_capability(tuple(grouped), label=group_label)
        if capability is not None:
            capabilities.append(capability)
    return tuple(capabilities)


@dataclass(frozen=True)
class ScopeCheck:
    """The outcome of one condition within a scope decision.

    Attributes:
        key: Stable identifier of the condition, so the interface can refer to it.
        title: Short description of what was checked.
        passed: Whether the condition holds.
        detail: Human-readable explanation, including the numbers compared.
    """

    key: str
    title: str
    passed: bool
    detail: str

    def to_json(self) -> dict[str, Any]:
        """Return the check as a JSON-compatible dictionary.

        Returns:
            The identifier, title, outcome and explanation.
        """
        return {
            "key": self.key,
            "title": self.title,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ScopeVerdict:
    """The overall decision on whether a claim falls inside a declared capability.

    Attributes:
        capability: The declaration the claim was measured against.
        claim: The claim that was checked.
        checks: Every condition that was evaluated, in the order evaluated.
    """

    capability: DeclaredCapability
    claim: MeasurementClaim
    checks: list[ScopeCheck]

    @property
    def within_scope(self) -> bool:
        """Return whether every condition held.

        Returns:
            True only if no check failed.
        """
        return all(check.passed for check in self.checks)

    @property
    def failures(self) -> list[ScopeCheck]:
        """Return the conditions that did not hold.

        Returns:
            The failing checks, in evaluation order.
        """
        return [check for check in self.checks if not check.passed]

    def to_json(self) -> dict[str, Any]:
        """Return the verdict as a JSON-compatible dictionary.

        Returns:
            The overall outcome, the capability label and every individual check.
        """
        return {
            "withinScope": self.within_scope,
            "capability": self.capability.label,
            "checks": [check.to_json() for check in self.checks],
        }


def evaluate_scope(
    capability: DeclaredCapability, claim: MeasurementClaim
) -> ScopeVerdict:
    """Decide whether a stated result falls inside a declared capability.

    Args:
        capability: The declared CMC entry, or one row of an accreditation scope.
        claim: The result stated on the certificate.

    Returns:
        The verdict, carrying every condition that was evaluated so that a reader can
        see which one decided the outcome rather than only the final answer.
    """
    checks: list[ScopeCheck] = []

    checks.append(
        ScopeCheck(
            key="measurand",
            title="Measurand is covered",
            passed=claim.measurand == capability.measurand,
            detail=(
                f"certificate states {claim.measurand}, "
                f"{capability.label} covers {capability.measurand}"
            ),
        )
    )

    checks.append(
        ScopeCheck(
            key="unit",
            title="Unit matches the declaration",
            passed=claim.unit == capability.unit,
            detail=(
                f"certificate reports {claim.unit or 'a dimensionless value'}, "
                f"{capability.label} is declared in "
                f"{capability.unit or 'dimensionless terms'}"
            ),
        )
    )

    level, level_source = claim.level_for(capability.coverage.level_basis)
    in_range = capability.coverage.covers(level)
    checks.append(
        ScopeCheck(
            key="range",
            title="Level is inside the declared coverage",
            passed=in_range,
            detail=(
                f"certificate puts the calibration at {level:g} {capability.unit} "
                f"({level_source}), {capability.label} covers "
                f"{capability.coverage.describe(capability.unit)}"
            ),
        )
    )

    floor = capability.uncertainty_floor
    coverage_matches = claim.coverage_factor == floor.coverage_factor
    checks.append(
        ScopeCheck(
            key="coverage-factor",
            title="Coverage factor is comparable",
            passed=coverage_matches,
            detail=(
                f"certificate reports U at k = {claim.coverage_factor:g}, "
                f"{capability.label} is declared at k = {floor.coverage_factor:g}"
            ),
        )
    )

    # Only compare uncertainties that are expressed at the same coverage factor.
    # Comparing a k = 1 claim against a k = 2 declaration would wrongly pass a claim
    # twice as good as anything ever demonstrated.
    if coverage_matches and in_range:
        smallest = floor.evaluate(claim.value)
        checks.append(
            ScopeCheck(
                key="uncertainty",
                title="Claimed uncertainty is not smaller than the declared capability",
                passed=claim.expanded_uncertainty >= smallest,
                detail=(
                    f"certificate claims U = {claim.expanded_uncertainty:.6g} "
                    f"{capability.unit}, smallest covered at this level is "
                    f"{smallest:.6g} {capability.unit} "
                    f"[{floor.describe(capability.unit)}]"
                ),
            )
        )
    else:
        checks.append(
            ScopeCheck(
                key="uncertainty",
                title="Claimed uncertainty is not smaller than the declared capability",
                passed=False,
                detail=(
                    "not evaluated: the uncertainty floor can only be compared for a "
                    "level inside the declared coverage and stated at the same coverage "
                    "factor"
                ),
            )
        )

    return ScopeVerdict(capability=capability, claim=claim, checks=checks)
