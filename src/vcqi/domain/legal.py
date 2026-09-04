"""Legal metrology: conformity decisions, and what makes one defensible.

Legal metrology asks a different question from the rest of this demonstration, and the
difference is the reason this module exists separately from `domain.scope`.

A calibration asks *what is the error of this instrument, and with what uncertainty*, and
answers with metrological information. A verification asks *does this instrument comply
with the legally prescribed requirements, yes or no*, and answers with a decision that
has legal effect. A weighing instrument can be perfectly well calibrated and not legally
verified for use in trade, and the two statements are not substitutes.

What connects them is that a verification is only as good as the standards it was made
with. So legal metrology rests on the calibration and traceability infrastructure without
being part of it, and this module reflects that: it decides conformity, and it takes the
uncertainty of that decision from the same GUM machinery the calibration side uses.

Two rules decide whether a verification stands up:

* the observed error must lie inside the maximum permissible error, which is what the
  decision means;
* the uncertainty of the verification must be small enough not to put the decision in
  doubt, conventionally ``U <= MPE / 3``.

The second is the one people forget. A verification made with worn reference weights can
reach the right verdict and still not support it.

Every requirement here follows OIML R 76 for non-automatic weighing instruments. The
instrument, the organisations and the certificate numbers are invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

__all__ = [
    "AccuracyClass",
    "CLASS_I",
    "CLASS_II",
    "CLASS_III",
    "CLASS_IIII",
    "TestPoint",
    "ConformityCheck",
    "ConformityVerdict",
    "DesignationScope",
    "DESIGNATION_SCOPES",
    "designation_by_id",
    "designation_url",
    "maximum_permissible_error",
    "evaluate_conformity",
    "UNCERTAINTY_RATIO",
]

#: The uncertainty of a verification must not exceed this fraction of the maximum
#: permissible error. Below it the decision is supported; above it the measurement is not
#: good enough to say whether the instrument complies, whatever verdict was recorded.
UNCERTAINTY_RATIO = 3.0

#: Verification of an instrument already in service is allowed twice the maximum
#: permissible error of initial verification, because an instrument is expected to drift
#: within its interval and is not required to remain as good as new.
IN_SERVICE_FACTOR = 2.0


@dataclass(frozen=True)
class AccuracyClass:
    """One OIML R 76 accuracy class.

    Attributes:
        name: The class designation, for example ``III``.
        minimum_intervals: Smallest number of verification scale intervals allowed.
        maximum_intervals: Largest number allowed.
        bands: The maximum permissible error of initial verification, as pairs of
            (upper bound in verification scale intervals, error in verification scale
            intervals). The first band whose bound the load does not exceed applies.
    """

    name: str
    minimum_intervals: int
    maximum_intervals: int
    bands: tuple[tuple[float, float], ...]


#: The four accuracy classes of OIML R 76. Every one has the same shape, three bands
#: rising in half-interval steps, and they differ only in where the bands fall. Class III
#: is the one this demonstration uses: it covers most instruments used in trade, such as
#: shop scales and platform scales. The others are defined because a designation that
#: covers one class and not another is only meaningful if the others exist.
CLASS_I = AccuracyClass(
    name="I",
    minimum_intervals=50000,
    maximum_intervals=1000000,
    bands=((50000.0, 0.5), (200000.0, 1.0), (1000000.0, 1.5)),
)
CLASS_II = AccuracyClass(
    name="II",
    minimum_intervals=100,
    maximum_intervals=100000,
    bands=((5000.0, 0.5), (20000.0, 1.0), (100000.0, 1.5)),
)
CLASS_III = AccuracyClass(
    name="III",
    minimum_intervals=500,
    maximum_intervals=10000,
    bands=((500.0, 0.5), (2000.0, 1.0), (10000.0, 1.5)),
)
CLASS_IIII = AccuracyClass(
    name="IIII",
    minimum_intervals=100,
    maximum_intervals=1000,
    bands=((50.0, 0.5), (200.0, 1.0), (1000.0, 1.5)),
)

_CLASSES = {
    definition.name: definition
    for definition in (CLASS_I, CLASS_II, CLASS_III, CLASS_IIII)
}


def maximum_permissible_error(
    load: float,
    *,
    scale_interval: float,
    accuracy_class: str = "III",
    in_service: bool = True,
) -> float:
    """Return the maximum permissible error at a load.

    The error is expressed in verification scale intervals and grows in steps with the
    load, which is why a verification tests several points rather than one: an
    instrument can be comfortably inside the limit at one load and outside it at another.

    Args:
        load: The applied load, in the unit of the instrument.
        scale_interval: The verification scale interval e, in the same unit.
        accuracy_class: The OIML R 76 accuracy class.
        in_service: True for subsequent verification of an instrument already in use,
            which is allowed twice the error of initial verification.

    Returns:
        The maximum permissible error, in the unit of the instrument.

    Raises:
        ValueError: If the accuracy class is unknown or the scale interval is not
            positive.
    """
    if scale_interval <= 0.0:
        raise ValueError("the verification scale interval must be positive")
    definition = _CLASSES.get(accuracy_class)
    if definition is None:
        raise ValueError(f"unknown accuracy class {accuracy_class!r}")

    intervals = abs(load) / scale_interval
    for upper, error in definition.bands:
        if intervals <= upper:
            limit = error * scale_interval
            break
    else:
        limit = definition.bands[-1][1] * scale_interval

    return limit * (IN_SERVICE_FACTOR if in_service else 1.0)


@dataclass(frozen=True)
class TestPoint:
    """One load at which the instrument was tested.

    Attributes:
        load: The applied load, in ``unit``.
        indication_error: Indication minus applied load, in ``unit``. Signed, because
            which way an instrument reads wrong matters to whoever is being weighed for.
        expanded_uncertainty: The Expanded Uncertainty U of the error determination.
        coverage_factor: The coverage factor k that U is stated at.
        unit: Unit symbol.
    """

    #: pytest collects any class whose name begins with Test, and this is a test point
    #: on a weighing instrument rather than a test of anything.
    __test__: ClassVar[bool] = False

    load: float
    indication_error: float
    expanded_uncertainty: float
    coverage_factor: float
    unit: str

    def to_json(self, *, scale_interval: float, accuracy_class: str, in_service: bool) -> dict[str, Any]:
        """Render the test point as it appears on a verification certificate.

        Args:
            scale_interval: The verification scale interval e.
            accuracy_class: The OIML R 76 accuracy class.
            in_service: Whether this is a subsequent verification.

        Returns:
            A JSON-compatible object including the limit that applies at this load.
        """
        limit = maximum_permissible_error(
            self.load,
            scale_interval=scale_interval,
            accuracy_class=accuracy_class,
            in_service=in_service,
        )
        return {
            "type": "VerificationTestPoint",
            "load": self.load,
            "unit": self.unit,
            "indicationError": self.indication_error,
            "maximumPermissibleError": limit,
            "expandedUncertainty": self.expanded_uncertainty,
            "coverageFactor": self.coverage_factor,
            "verdict": "pass" if abs(self.indication_error) <= limit else "fail",
        }


@dataclass(frozen=True)
class ConformityCheck:
    """The outcome of one condition at one test point.

    Attributes:
        key: Stable identifier of the condition.
        load: The load the condition was evaluated at.
        title: Short description of what was checked.
        passed: Whether the condition holds.
        detail: Human-readable explanation, including the numbers compared.
    """

    key: str
    load: float
    title: str
    passed: bool
    detail: str

    def to_json(self) -> dict[str, Any]:
        """Return the check as a JSON-compatible dictionary.

        Returns:
            The identifier, load, title, outcome and explanation.
        """
        return {
            "key": self.key,
            "load": self.load,
            "title": self.title,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ConformityVerdict:
    """Whether a recorded conformity decision is supported by the measurements.

    Attributes:
        decision: The decision the certificate records.
        implied_decision: The decision the test points actually support.
        checks: Every condition evaluated, in order.
    """

    decision: str
    implied_decision: str
    checks: list[ConformityCheck]

    @property
    def decision_follows(self) -> bool:
        """Return whether the recorded decision matches the one the numbers support.

        Returns:
            True when the certificate says what its own measurements say.
        """
        return self.decision == self.implied_decision

    @property
    def adequately_measured(self) -> bool:
        """Return whether every point was measured well enough to decide on.

        Returns:
            True when no uncertainty condition failed.
        """
        return all(check.passed for check in self.checks if check.key == "uncertainty")

    @property
    def failures(self) -> list[ConformityCheck]:
        """Return the conditions that did not hold.

        Returns:
            The failing checks, in evaluation order.
        """
        return [check for check in self.checks if not check.passed]

    def to_json(self) -> dict[str, Any]:
        """Return the verdict as a JSON-compatible dictionary.

        Returns:
            Both decisions and every individual check.
        """
        return {
            "decision": self.decision,
            "impliedDecision": self.implied_decision,
            "decisionFollows": self.decision_follows,
            "adequatelyMeasured": self.adequately_measured,
            "checks": [check.to_json() for check in self.checks],
        }


def evaluate_conformity(
    test_points: list[dict[str, Any]],
    *,
    decision: str,
    scale_interval: float,
    accuracy_class: str = "III",
    in_service: bool = True,
) -> ConformityVerdict:
    """Decide whether a recorded conformity decision is supported by its test points.

    Two independent things are checked at every load, and they fail in different ways.
    An error outside the maximum permissible error means the instrument does not comply,
    so a certificate recording a pass is simply wrong. An uncertainty too large relative
    to that limit means the verification cannot tell either way, so the certificate is
    not wrong so much as unsupported, and that is worth reporting differently.

    Args:
        test_points: The test points as they appear on the certificate.
        decision: The overall decision the certificate records.
        scale_interval: The verification scale interval e.
        accuracy_class: The OIML R 76 accuracy class.
        in_service: Whether this is a subsequent verification.

    Returns:
        The verdict, carrying every condition so a reader can see which load decided it.
    """
    checks: list[ConformityCheck] = []
    all_within = True

    for entry in test_points:
        try:
            load = float(entry["load"])
            error = float(entry["indicationError"])
            uncertainty = float(entry["expandedUncertainty"])
            unit = str(entry.get("unit", ""))
        except (KeyError, TypeError, ValueError) as problem:
            checks.append(
                ConformityCheck(
                    key="readable",
                    load=0.0,
                    title="Test point is readable",
                    passed=False,
                    detail=f"the test point could not be read: {problem}",
                )
            )
            all_within = False
            continue

        limit = maximum_permissible_error(
            load,
            scale_interval=scale_interval,
            accuracy_class=accuracy_class,
            in_service=in_service,
        )
        stated_limit = entry.get("maximumPermissibleError")
        if isinstance(stated_limit, (int, float)):
            checks.append(
                ConformityCheck(
                    key="limit",
                    load=load,
                    title=f"Stated limit at {load:g} {unit} is the one OIML R 76 gives",
                    passed=abs(float(stated_limit) - limit) <= 1e-12,
                    detail=(
                        f"certificate states MPE = {float(stated_limit):g} {unit}, "
                        f"class {accuracy_class} at {load / scale_interval:g} e gives "
                        f"{limit:g} {unit}"
                    ),
                )
            )

        within = abs(error) <= limit
        all_within = all_within and within
        checks.append(
            ConformityCheck(
                key="error",
                load=load,
                title=f"Error at {load:g} {unit} is inside the maximum permissible error",
                passed=within,
                detail=(
                    f"observed {error:+g} {unit}, limit {limit:g} {unit}"
                    + ("" if within else f", exceeded by {abs(error) - limit:g} {unit}")
                ),
            )
        )

        adequate = uncertainty <= limit / UNCERTAINTY_RATIO
        checks.append(
            ConformityCheck(
                key="uncertainty",
                load=load,
                title=f"Verification at {load:g} {unit} was measured well enough to decide on",
                passed=adequate,
                detail=(
                    f"U = {uncertainty:g} {unit}, and the limit permits at most "
                    f"MPE/{UNCERTAINTY_RATIO:g} = {limit / UNCERTAINTY_RATIO:g} {unit}"
                    + (
                        ""
                        if adequate
                        else ", so the reference standards were not good enough to "
                        "support a decision at this load"
                    )
                ),
            )
        )

    return ConformityVerdict(
        decision=decision,
        implied_decision="pass" if all_within else "fail",
        checks=checks,
    )


@dataclass(frozen=True)
class DesignationScope:
    """What a verification body has been authorised by the regulator to verify.

    A designation is the legal-metrology counterpart of an accreditation scope, and it
    carries the same warning: being designated is not the same as being designated for
    this. It is deliberately shaped like an accreditation scope so that the verification
    pipeline can check it with the machinery already there.

    Attributes:
        identifier: The designation number.
        authority: DID of the legal-metrology authority that granted it.
        authority_name: Human-readable name of that authority.
        organisation: DID of the designated body.
        organisation_name: Human-readable name of that body.
        jurisdiction: Where the designation has effect.
        legal_basis: The legislation the designation is granted under.
        instrument_category: What kind of instrument is covered.
        accuracy_classes: The OIML accuracy classes covered.
        maximum_capacity: Largest instrument capacity covered, in ``unit``.
        unit: Unit of the capacity bound.
        activities: Which verification activities are covered.
        methods: The Recommendations or standards the designation covers.
        valid_from: Start of validity, as an ISO 8601 date.
        valid_until: End of validity, as an ISO 8601 date.
    """

    identifier: str
    authority: str
    authority_name: str
    organisation: str
    organisation_name: str
    jurisdiction: str
    legal_basis: str
    instrument_category: str
    accuracy_classes: tuple[str, ...]
    maximum_capacity: float
    unit: str
    activities: tuple[str, ...]
    methods: tuple[str, ...]
    valid_from: str
    valid_until: str

    @property
    def url(self) -> str:
        """Return the address at which this designation is published.

        Returns:
            The URL a credential uses when it references this designation.
        """
        return designation_url(self.identifier)

    def covers(self, accuracy_class: str, capacity: float) -> bool:
        """Report whether an instrument falls inside this designation.

        Args:
            accuracy_class: The accuracy class of the instrument.
            capacity: The maximum capacity of the instrument, in ``unit``.

        Returns:
            True when both the class and the capacity are covered.
        """
        return accuracy_class in self.accuracy_classes and capacity <= self.maximum_capacity

    def to_json(self) -> dict[str, Any]:
        """Return the designation as the authority would publish it.

        Returns:
            A JSON-compatible dictionary. ``methods`` is present so that the existing
            scope check, which already understands a capability expressed as a list of
            methods, can adjudicate a designation without special-casing.
        """
        return {
            "id": self.url,
            "type": "DesignationScope",
            "identifier": self.identifier,
            "authority": self.authority,
            "authorityName": self.authority_name,
            "organisation": self.organisation,
            "organisationName": self.organisation_name,
            "jurisdiction": self.jurisdiction,
            "legalBasis": self.legal_basis,
            "instrumentCategory": self.instrument_category,
            "accuracyClasses": list(self.accuracy_classes),
            "maximumCapacity": self.maximum_capacity,
            "unit": self.unit,
            "activities": list(self.activities),
            "methods": list(self.methods),
            "validFrom": self.valid_from,
            "validUntil": self.valid_until,
        }


def designation_url(identifier: str) -> str:
    """Return the published address of a designation.

    Args:
        identifier: The designation number.

    Returns:
        The URL the legal-metrology authority serves it at.
    """
    return f"https://metas.example/designations/{identifier.replace(' ', '-')}"


#: The designations granted in the demonstration world.
DESIGNATION_SCOPES: tuple[DesignationScope, ...] = (
    DesignationScope(
        identifier="EV 042",
        authority="did:web:metas.example",
        authority_name="Federal Institute of Metrology (demonstration)",
        organisation="did:web:verifybody.example",
        organisation_name="Gotthard Verification Services AG (demonstration)",
        jurisdiction="CH",
        legal_basis="Measuring Instruments Ordinance (demonstration)",
        instrument_category="Non-automatic weighing instruments",
        accuracy_classes=("III",),
        maximum_capacity=30.0,
        unit="kg",
        activities=("Initial verification", "Subsequent verification", "Verification after repair"),
        methods=("OIML R 76, non-automatic weighing instruments",),
        valid_from="2025-01-01",
        valid_until="2029-12-31",
    ),
)

_BY_IDENTIFIER = {scope.identifier: scope for scope in DESIGNATION_SCOPES}
_BY_URL = {scope.url: scope for scope in DESIGNATION_SCOPES}


def designation_by_id(reference: str) -> DesignationScope | None:
    """Look up a designation by identifier or by published URL.

    Args:
        reference: A designation number, or the URL a credential references it by.

    Returns:
        The designation, or None when nothing is published under that reference.
    """
    return _BY_IDENTIFIER.get(reference) or _BY_URL.get(reference)
