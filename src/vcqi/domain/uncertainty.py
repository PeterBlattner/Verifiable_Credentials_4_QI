"""Measurement uncertainty for the traceability chain, evaluated per the GUM.

Every calibration in this demonstrator is a comparison against a reference standard
whose own uncertainty came from the certificate one level up the chain. That is what
metrological traceability means in practice, and it is why the credential chain and the
traceability chain have the same shape: each certificate consumes the uncertainty
stated by its parent and adds the contributions of its own measurement.

Propagation uses metas_unclib rather than a hand-written root-sum-square, for a reason
that matters to the argument this demonstrator makes. metas_unclib tracks where each
uncertainty came from, so when the same reference standard appears twice in a
calculation its contributions correlate correctly instead of being double counted. A
number alone cannot do that. A credential that carries the *budget*, not just the
result, keeps that information available to whoever uses the measurement next.

Terms follow the GUM strictly: ``u`` is the Standard Uncertainty, ``U`` is the Expanded
Uncertainty, and every reported ``U`` uses the coverage factor k = 2 required for
calibration certificates under the CIPM MRA.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import metas_unclib as mu

from vcqi.config import COVERAGE_FACTOR

__all__ = [
    "Contribution",
    "BudgetLine",
    "MeasurementResult",
    "normal",
    "rectangular",
    "from_expanded_uncertainty",
    "evaluate",
    "format_measurement",
]


@dataclass(frozen=True)
class Contribution:
    """One input quantity of an uncertainty budget.

    Attributes:
        key: Identifier used to refer to this quantity inside a model function.
        label: Human-readable description, as it should appear in the budget table.
        value: Best estimate of the quantity, in ``unit``.
        standard_uncertainty: The Standard Uncertainty u of the estimate, in ``unit``.
        unit: Unit symbol, or an empty string for a dimensionless quantity such as a
            bridge ratio.
        distribution: The assumed distribution, recorded so a reader can see how a
            stated tolerance was converted into a Standard Uncertainty.
        note: Optional provenance, for example the certificate the value came from.
    """

    key: str
    label: str
    value: float
    standard_uncertainty: float
    unit: str = ""
    distribution: str = "normal"
    note: str = ""


@dataclass(frozen=True)
class BudgetLine:
    """One row of an evaluated uncertainty budget.

    Attributes:
        key: Identifier of the input quantity.
        label: Human-readable description of the input quantity.
        value: Best estimate of the input quantity, in ``unit``.
        standard_uncertainty: The Standard Uncertainty u of the input, in ``unit``.
        unit: Unit of the input quantity.
        distribution: The assumed distribution of the input quantity.
        sensitivity_coefficient: Partial derivative of the result with respect to this
            input, so its unit is that of the result divided by ``unit``.
        uncertainty_contribution: The contribution of this input to the Standard
            Uncertainty of the result, in the unit of the result.
        index: Share of the variance of the result attributable to this input, as a
            fraction in the range 0 to 1.
        note: Optional provenance carried through from the input.
    """

    key: str
    label: str
    value: float
    standard_uncertainty: float
    unit: str
    distribution: str
    sensitivity_coefficient: float
    uncertainty_contribution: float
    index: float
    note: str = ""


@dataclass(frozen=True)
class MeasurementResult:
    """A measurement result with its Expanded Uncertainty and full budget.

    Attributes:
        value: Best estimate of the measurand, in ``unit``.
        standard_uncertainty: The combined Standard Uncertainty u, in ``unit``.
        unit: Unit symbol of the measurand.
        coverage_factor: The coverage factor k used to expand u.
        budget: The contributions that make up the combined Standard Uncertainty.
    """

    value: float
    standard_uncertainty: float
    unit: str
    coverage_factor: float = COVERAGE_FACTOR
    budget: list[BudgetLine] = field(default_factory=list)

    @property
    def expanded_uncertainty(self) -> float:
        """Return the Expanded Uncertainty U, in the unit of the measurand.

        Returns:
            The Standard Uncertainty multiplied by the coverage factor.
        """
        return self.coverage_factor * self.standard_uncertainty

    @property
    def relative_expanded_uncertainty(self) -> float:
        """Return U divided by the measured value, as a dimensionless ratio.

        CMC entries for quantities such as resistance are usually stated relatively,
        so this is the form in which a scope check is normally made.

        Returns:
            The relative Expanded Uncertainty, or 0.0 when the value is zero.
        """
        if self.value == 0.0:
            return 0.0
        return self.expanded_uncertainty / abs(self.value)

    def format(self, unit: str | None = None) -> str:
        """Render the result in the conventional reporting form.

        Args:
            unit: Override for the unit symbol, useful when a caller has rescaled the
                value for display.

        Returns:
            The result as ``value +/- U (k=2) unit``, with U rounded to two
            significant figures and the value rounded to match.
        """
        return format_measurement(
            self.value,
            self.expanded_uncertainty,
            unit if unit is not None else self.unit,
            self.coverage_factor,
        )


def normal(
    key: str,
    label: str,
    value: float,
    standard_uncertainty: float,
    *,
    unit: str = "",
    note: str = "",
) -> Contribution:
    """Build a contribution whose Standard Uncertainty is already known.

    Args:
        key: Identifier used inside the model function.
        label: Human-readable description for the budget table.
        value: Best estimate of the quantity, in ``unit``.
        standard_uncertainty: The Standard Uncertainty u, in ``unit``.
        unit: Unit symbol, empty for a dimensionless quantity.
        note: Optional provenance.

    Returns:
        The contribution.
    """
    return Contribution(
        key=key,
        label=label,
        value=value,
        standard_uncertainty=standard_uncertainty,
        unit=unit,
        distribution="normal",
        note=note,
    )


def rectangular(
    key: str,
    label: str,
    value: float,
    half_width: float,
    *,
    unit: str = "",
    note: str = "",
) -> Contribution:
    """Build a contribution from a tolerance band with no further information.

    A limit such as a drift specification or a resolution bound gives an interval
    rather than a Standard Uncertainty. The GUM treats such an interval as a
    rectangular distribution, whose Standard Uncertainty is the half-width divided by
    the square root of three.

    Args:
        key: Identifier used inside the model function.
        label: Human-readable description for the budget table.
        value: Best estimate of the quantity, in ``unit``.
        half_width: Half-width a of the interval, in ``unit``.
        unit: Unit symbol, empty for a dimensionless quantity.
        note: Optional provenance.

    Returns:
        The contribution, with u = a divided by the square root of three.
    """
    return Contribution(
        key=key,
        label=label,
        value=value,
        standard_uncertainty=half_width / math.sqrt(3.0),
        unit=unit,
        distribution="rectangular",
        note=note,
    )


def from_expanded_uncertainty(
    key: str,
    label: str,
    value: float,
    expanded_uncertainty: float,
    *,
    coverage_factor: float = COVERAGE_FACTOR,
    unit: str = "",
    note: str = "",
) -> Contribution:
    """Build a contribution from a value reported on a calibration certificate.

    Certificates report an Expanded Uncertainty, so the receiving laboratory has to
    divide by the coverage factor before the value can enter its own budget. This is
    the point at which one link of the traceability chain joins the next.

    Args:
        key: Identifier used inside the model function.
        label: Human-readable description for the budget table.
        value: The calibrated value, in ``unit``.
        expanded_uncertainty: The Expanded Uncertainty U from the certificate.
        coverage_factor: The coverage factor k the certificate used.
        unit: Unit symbol, empty for a dimensionless quantity.
        note: Optional provenance, normally the identifier of that certificate.

    Returns:
        The contribution, with u = U divided by k.
    """
    return Contribution(
        key=key,
        label=label,
        value=value,
        standard_uncertainty=expanded_uncertainty / coverage_factor,
        unit=unit,
        distribution="normal",
        note=note,
    )


def evaluate(
    model: Callable[[dict[str, Any]], Any],
    contributions: Sequence[Contribution],
    *,
    unit: str,
    coverage_factor: float = COVERAGE_FACTOR,
) -> MeasurementResult:
    """Propagate uncertainty through a measurement model and build its budget.

    Args:
        model: The measurement model. It receives a mapping from contribution key to
            the corresponding uncertain number and returns the measurand.
        contributions: The input quantities of the model.
        unit: Unit symbol of the measurand.
        coverage_factor: The coverage factor k used to expand the result.

    Returns:
        The result, with the combined Standard Uncertainty and one budget line per
        input quantity.

    Raises:
        ValueError: If two contributions share the same key.
    """
    keys = [item.key for item in contributions]
    if len(set(keys)) != len(keys):
        raise ValueError("contribution keys must be unique within a budget")

    u_variable_inputs = {
        item.key: mu.ufloat(item.value, item.standard_uncertainty, desc=item.label)
        for item in contributions
    }
    u_variable_result = model(u_variable_inputs)

    value = float(mu.get_value(u_variable_result))
    combined = float(mu.get_stdunc(u_variable_result))
    variance = combined * combined

    budget: list[BudgetLine] = []
    for item in contributions:
        u_variable_input = u_variable_inputs[item.key]
        component = float(mu.get_unc_component(u_variable_result, u_variable_input)[0][0])
        if item.standard_uncertainty == 0.0:
            sensitivity = 0.0
        else:
            sensitivity = component / item.standard_uncertainty
        budget.append(
            BudgetLine(
                key=item.key,
                label=item.label,
                value=item.value,
                standard_uncertainty=item.standard_uncertainty,
                unit=item.unit,
                distribution=item.distribution,
                sensitivity_coefficient=sensitivity,
                uncertainty_contribution=component,
                index=(component * component / variance) if variance > 0.0 else 0.0,
                note=item.note,
            )
        )

    return MeasurementResult(
        value=value,
        standard_uncertainty=combined,
        unit=unit,
        coverage_factor=coverage_factor,
        budget=budget,
    )


def format_measurement(
    value: float,
    expanded_uncertainty: float,
    unit: str,
    coverage_factor: float = COVERAGE_FACTOR,
) -> str:
    """Render a value and its Expanded Uncertainty in the conventional form.

    Rounding happens here and nowhere else. Intermediate results are carried at full
    precision throughout, and only the reported string is rounded, with U shown to two
    significant figures and the value shown to the same decimal place.

    Args:
        value: The measured value, in ``unit``.
        expanded_uncertainty: The Expanded Uncertainty U, in ``unit``.
        unit: Unit symbol, empty for a dimensionless quantity.
        coverage_factor: The coverage factor k that U corresponds to.

    Returns:
        A string such as ``10000.0012 +/- 0.0011 ohm (k = 2)``.
    """
    if expanded_uncertainty <= 0.0 or not math.isfinite(expanded_uncertainty):
        rendered_value, rendered_uncertainty = repr(value), repr(expanded_uncertainty)
    else:
        exponent = math.floor(math.log10(abs(expanded_uncertainty)))
        decimals = max(0, -(exponent - 1))
        rendered_value = f"{value:.{decimals}f}"
        rendered_uncertainty = f"{expanded_uncertainty:.{decimals}f}"

    suffix = f" {unit}" if unit else ""
    factor = f"{coverage_factor:g}"
    return f"{rendered_value} +/- {rendered_uncertainty}{suffix} (k = {factor})"
