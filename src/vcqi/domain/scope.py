"""Deciding whether a stated measurement result falls inside a declared capability.

Two very similar declarations appear in the quality infrastructure:

* a **CMC** entry, which a National Metrology Institute publishes in the BIPM key
  comparison database and which bounds what it may claim under the CIPM MRA;
* an **accreditation scope**, which an accreditation body issues to a laboratory under
  ISO/IEC 17025 and which bounds what that laboratory may claim as accredited work.

Both say the same three things: which measurand, over which range, and with what
smallest Expanded Uncertainty. So both are represented here as a
:class:`DeclaredCapability`, and one function decides whether a given result is covered.

The uncertainty bound runs in the direction people new to the field usually get
backwards. A capability states the *smallest* uncertainty an institute can achieve. A
certificate claiming a *larger* uncertainty is comfortably inside scope; a certificate
claiming a *smaller* one is claiming to have done better than it has ever demonstrated,
and is out of scope. Getting this check wrong in the permissive direction is exactly the
failure that lets an unjustified CIPM MRA logo through.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

__all__ = [
    "UncertaintyFloor",
    "DeclaredCapability",
    "MeasurementClaim",
    "ScopeCheck",
    "ScopeVerdict",
    "evaluate_scope",
]


@dataclass(frozen=True)
class UncertaintyFloor:
    """The smallest Expanded Uncertainty a capability covers, as a function of level.

    CMC entries rarely state a single number. Below some level a fixed floor dominates,
    above it the uncertainty grows in proportion to the measured value, and the two are
    combined in quadrature. That is the form used here.

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
            The Expanded Uncertainty floor U at that level, in the same unit.
        """
        proportional = self.relative * abs(value)
        return math.sqrt(self.absolute * self.absolute + proportional * proportional)

    def describe(self, unit: str) -> str:
        """Render the floor the way a CMC table would state it.

        Args:
            unit: Unit symbol of the measurand.

        Returns:
            A human-readable description of the quadrature sum.
        """
        relative_ppm = self.relative * 1e6
        return (
            f"U = sqrt(({self.absolute:g} {unit})^2 + ({relative_ppm:g} x 10^-6 x value)^2), "
            f"k = {self.coverage_factor:g}"
        )

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
class DeclaredCapability:
    """What an institute or laboratory has declared it is able to do.

    Attributes:
        label: Short identifier for messages, for example ``CMC CH-EM-0042``.
        measurand: Identifier of the measured quantity, for example ``dc.resistance``.
        unit: Unit symbol the range and the floor are expressed in.
        range_minimum: Lowest covered level of the measurand, in ``unit``.
        range_maximum: Highest covered level of the measurand, in ``unit``.
        conditions: Measurement conditions the declaration is valid under.
        uncertainty_floor: The smallest covered Expanded Uncertainty.
    """

    label: str
    measurand: str
    unit: str
    range_minimum: float
    range_maximum: float
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
    """

    measurand: str
    unit: str
    value: float
    expanded_uncertainty: float
    coverage_factor: float


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
        return {"key": self.key, "title": self.title, "passed": self.passed, "detail": self.detail}


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
        capability: The declared CMC entry or accreditation scope.
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
                f"{capability.label} is declared in {capability.unit or 'dimensionless terms'}"
            ),
        )
    )

    in_range = capability.range_minimum <= claim.value <= capability.range_maximum
    checks.append(
        ScopeCheck(
            key="range",
            title="Level is inside the declared range",
            passed=in_range,
            detail=(
                f"certificate reports {claim.value:g} {capability.unit}, "
                f"{capability.label} covers {capability.range_minimum:g} to "
                f"{capability.range_maximum:g} {capability.unit}"
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
                    f"certificate claims U = {claim.expanded_uncertainty:.6g} {capability.unit}, "
                    f"smallest covered at this level is {smallest:.6g} {capability.unit} "
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
                    "not evaluated: the uncertainty floor can only be compared for a level "
                    "inside the declared range and stated at the same coverage factor"
                ),
            )
        )

    return ScopeVerdict(capability=capability, claim=claim, checks=checks)
