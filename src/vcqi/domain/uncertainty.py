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

import hashlib
import math
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from vcqi.config import COVERAGE_FACTOR, DEMO_SEED
from vcqi.domain.engine import mu, unclib_available
from vcqi.domain.unclib_blobs import blob_for

__all__ = [
    "Contribution",
    "BudgetLine",
    "InputQuantity",
    "MeasurementResult",
    "normal",
    "rectangular",
    "from_expanded_uncertainty",
    "from_certificate",
    "from_quantity",
    "evaluate",
    "format_measurement",
    "seeded_input_id",
    "to_unclib_xml",
    "to_unclib_binary",
    "parse_input_quantities",
]


def seeded_input_id(label: str, context: str = "") -> list[int]:
    """Derive a reproducible identifier for an input quantity from the demo seed.

    UncLib gives every input quantity a fresh GUID, which is exactly right: two
    measurements that happen to describe a contribution the same way are not thereby
    the same physical influence. It also means no two runs of this demonstration would
    produce the same documents, which would make the whole thing undiffable.

    So the demonstration seeds them instead, and the ``context`` is not optional in
    spirit. Seeding on the label alone makes every budget that says "temperature
    correction" share one identifier, and results that have nothing to do with each
    other come out perfectly correlated. Passing the certificate as the context keeps
    each measurement's own influences distinct, while influences genuinely inherited
    from another certificate keep the identifiers they arrived with.

    In production this whole function should not exist: let UncLib generate random
    GUIDs, or two unrelated laboratories will collide the moment they choose the same
    wording.

    Args:
        label: Name of the input quantity.
        context: What distinguishes this use of that name, normally the certificate the
            budget belongs to.

    Returns:
        Four little-endian words, the form UncLib accepts as a 16 byte identifier.
    """
    material = DEMO_SEED + b"|" + context.encode("utf-8") + b"|" + label.encode("utf-8")
    digest = hashlib.sha256(material).digest()[:16]
    return [int.from_bytes(digest[index : index + 4], "little") for index in range(0, 16, 4)]


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
        uncertain_number: An existing uncertain number to use as this input, instead of
            creating a fresh one. This is what makes traceability real rather than
            asserted: when a laboratory loads the dependency representation from the
            certificate above it, the input quantities keep their original identifiers,
            so a later calculation involving both certificates sees them as the same
            physical influences and handles the correlation correctly.
    """

    key: str
    label: str
    value: float
    standard_uncertainty: float
    unit: str = ""
    distribution: str = "normal"
    note: str = ""
    uncertain_number: Any = None


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
        budget: The contributions that make up the combined Standard Uncertainty, one
            line per input of the measurement model.
        uncertain_number: The underlying metas_unclib object, retained so the result can
            be serialised with its full dependency structure. Never rendered into JSON
            directly; see to_unclib_xml.
    """

    value: float
    standard_uncertainty: float
    unit: str
    coverage_factor: float = COVERAGE_FACTOR
    budget: list[BudgetLine] = field(default_factory=list)
    uncertain_number: Any = None

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


def from_certificate(
    key: str,
    label: str,
    unclib_xml: str,
    *,
    unit: str = "",
    note: str = "",
) -> Contribution:
    """Build a contribution from the dependency representation of a certificate.

    This is the alternative to :func:`from_expanded_uncertainty`, and the difference
    between them is the whole point of transmitting dependencies at all.

    ``from_expanded_uncertainty`` takes the two numbers a paper certificate prints and
    declares a *new* input quantity from them. It gets the right answer for this
    measurement, and loses everything about where the number came from. Two results
    built that way from the same reference standard look statistically independent, and
    a customer combining them will overstate their uncertainty.

    ``from_certificate`` deserialises the uncertain number the issuing laboratory
    actually computed. Its input quantities arrive with their original identifiers, so
    the reference standard inside it stays the *same* influence wherever it reappears,
    and correlations come out right without anyone having to notice they were there.

    Args:
        key: Identifier used inside the model function.
        label: Human-readable description for the budget table.
        unclib_xml: The METAS UncLib XML from the certificate.
        unit: Unit symbol of the quantity.
        note: Optional provenance, normally the identifier of that certificate.

    Returns:
        The contribution, carrying the deserialised uncertain number.

    Raises:
        ValueError: If the XML cannot be read as an uncertain number.
    """
    try:
        u_variable_input = mu.ustorage.from_xml_string(unclib_xml)
    except Exception as error:  # the wrapper raises .NET-derived exceptions
        raise ValueError(f"could not read the dependency representation: {error}") from error

    return Contribution(
        key=key,
        label=label,
        value=float(mu.get_value(u_variable_input)),
        standard_uncertainty=float(mu.get_stdunc(u_variable_input)),
        unit=unit,
        distribution="from certificate",
        note=note,
        uncertain_number=u_variable_input,
    )


def evaluate(
    model: Callable[[dict[str, Any]], Any],
    contributions: Sequence[Contribution],
    *,
    unit: str,
    coverage_factor: float = COVERAGE_FACTOR,
    context: str = "",
) -> MeasurementResult:
    """Propagate uncertainty through a measurement model and build its budget.

    Args:
        model: The measurement model. It receives a mapping from contribution key to
            the corresponding uncertain number and returns the measurand.
        contributions: The input quantities of the model.
        unit: Unit symbol of the measurand.
        coverage_factor: The coverage factor k used to expand the result.
        context: What this budget belongs to, normally a certificate number. It scopes
            the seeded identifiers of the inputs declared here, so that two budgets
            using the same wording for their own effects do not end up sharing an
            influence. Contributions loaded from another certificate are unaffected:
            they keep the identifiers they arrived with.

    Returns:
        The result, with the combined Standard Uncertainty and one budget line per
        input quantity.

    Raises:
        ValueError: If two contributions share the same key.
    """
    keys = [item.key for item in contributions]
    if len(set(keys)) != len(keys):
        raise ValueError("contribution keys must be unique within a budget")

    u_variable_inputs = {}
    for item in contributions:
        if item.uncertain_number is not None:
            # Continue the parent's quantity rather than declaring a new one, so its
            # input identifiers travel onward into this result.
            u_variable_inputs[item.key] = item.uncertain_number
        else:
            u_variable_inputs[item.key] = mu.ufloat(
                item.value,
                item.standard_uncertainty,
                id=seeded_input_id(item.label, context),
                desc=item.label,
            )
    u_variable_result = model(u_variable_inputs)

    value = float(mu.get_value(u_variable_result))
    combined = float(mu.get_stdunc(u_variable_result))
    variance = combined * combined

    budget: list[BudgetLine] = []
    for item in contributions:
        u_variable_input = u_variable_inputs[item.key]
        component = float(mu.get_unc_component(u_variable_result, u_variable_input)[0][0])
        # Read the input back from the object rather than from the declaration, so that
        # a contribution loaded from a certificate reports what it actually carries.
        input_value = float(mu.get_value(u_variable_input))
        input_uncertainty = float(mu.get_stdunc(u_variable_input))
        sensitivity = component / input_uncertainty if input_uncertainty else 0.0
        budget.append(
            BudgetLine(
                key=item.key,
                label=item.label,
                value=input_value,
                standard_uncertainty=input_uncertainty,
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
        uncertain_number=u_variable_result,
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


@dataclass(frozen=True)
class InputQuantity:
    """One elementary influence a result depends on, as transmitted to a customer.

    This is the row of a dependency representation. It is what the flat budget of a
    paper certificate cannot carry: not just how much the influence contributed here,
    but which influence it was, so that the same one can be recognised elsewhere.

    Attributes:
        identifier: The identifier UncLib gives the influence, as it appears in the XML.
        description: Human-readable name of the influence.
        value: Best estimate of the influence.
        standard_uncertainty: The Standard Uncertainty u of the influence.
        distribution: The assumed distribution.
        sensitivity_coefficient: Partial derivative of the result with respect to it.
        uncertainty_contribution: Its contribution to the Standard Uncertainty of the
            result, being the sensitivity times u.
    """

    identifier: str
    description: str
    value: float
    standard_uncertainty: float
    distribution: str
    sensitivity_coefficient: float
    uncertainty_contribution: float

    def to_json(self) -> dict[str, Any]:
        """Return the influence as a JSON-compatible dictionary.

        Returns:
            The identifier, description and the numbers describing its contribution.
        """
        return {
            "id": self.identifier,
            "description": self.description,
            "value": self.value,
            "standardUncertainty": self.standard_uncertainty,
            "distribution": self.distribution,
            "sensitivityCoefficient": self.sensitivity_coefficient,
            "uncertaintyContribution": self.uncertainty_contribution,
        }


def to_unclib_xml(result: MeasurementResult) -> str:
    """Serialise a result with its full dependency structure as METAS UncLib XML.

    Args:
        result: The evaluated result. It must carry its uncertain number.

    Returns:
        The XML document, which states the value, every input quantity it depends on
        with that quantity identifier and distribution, and the sensitivity to each.

    Raises:
        ValueError: If the result was built without retaining its uncertain number.
    """
    if result.uncertain_number is None:
        raise ValueError("this result carries no uncertain number to serialise")
    return mu.ustorage.to_xml_string(result.uncertain_number)


def _unclib_binary_from_library(result: MeasurementResult) -> bytes:
    """Ask the library itself for the compact binary form.

    Separated out so that the blob generator can wrap it, and so that the only call
    into UncLib's undocumented serialisation is in one place.

    Args:
        result: The evaluated result, carrying its uncertain number.

    Returns:
        The serialised bytes.
    """
    return bytes(mu.ustorage.to_byte_array(result.uncertain_number))


def to_unclib_binary(result: MeasurementResult) -> bytes | None:
    """Serialise a result with its dependency structure in the compact binary form.

    The binary form says exactly what the XML says. It exists because a result with
    thousands of input quantities, which is ordinary in areas such as radiofrequency
    scattering parameters, produces an XML document too large to be comfortable.

    Only METAS UncLib writes this layout; it is not documented and the pure-Python
    engine does not reproduce it. Where UncLib is absent, the bytes it wrote for this
    same result are looked up among the committed blobs, keyed by the XML the result
    serialises to. That keeps a deployed certificate carrying genuine UncLib output
    without the deployment carrying UncLib.

    Args:
        result: The evaluated result. It must carry its uncertain number.

    Returns:
        The serialised bytes, or None when this engine cannot produce them and no blob
        was recorded for this result. A caller should then omit the representation
        rather than publish a substitute.

    Raises:
        ValueError: If the result was built without retaining its uncertain number.
    """
    if result.uncertain_number is None:
        raise ValueError("this result carries no uncertain number to serialise")
    if unclib_available():
        return _unclib_binary_from_library(result)
    return blob_for(to_unclib_xml(result))


def parse_input_quantities(unclib_xml: str) -> list[InputQuantity]:
    """Read the influences a result depends on out of its UncLib XML.

    A customer receiving a certificate would do exactly this: parse the dependency
    representation and see, one line per influence, what the result rests on. Doing it
    here with a plain XML parser rather than through the library makes the point that
    the representation is inspectable by anyone, not only by a holder of the same tool.

    Args:
        unclib_xml: The XML from a dependency representation.

    Returns:
        One entry per input quantity, in document order.

    Raises:
        ValueError: If the document cannot be parsed.
    """
    try:
        root = ElementTree.fromstring(unclib_xml)
    except ElementTree.ParseError as error:
        raise ValueError(f"could not parse the dependency representation: {error}") from error

    quantities: list[InputQuantity] = []
    for depends_on in root.iterfind("./Dependencies/DependsOn"):
        node = depends_on.find("./Input")
        if node is None:
            continue
        distribution = node.find("./Distribution")
        kind = "unknown"
        mean, sigma = 0.0, 0.0
        if distribution is not None:
            for name, value in distribution.attrib.items():
                if name.endswith("type"):
                    kind = value
            mean = _float_of(distribution.findtext("./mu"))
            sigma = _float_of(distribution.findtext("./sigma"))
        jacobi = _float_of(depends_on.findtext("./Jacobi"))
        quantities.append(
            InputQuantity(
                identifier=(node.findtext("./Id") or "").strip(),
                description=(node.findtext("./Description") or "").strip(),
                value=mean,
                standard_uncertainty=sigma,
                distribution=kind,
                sensitivity_coefficient=jacobi,
                uncertainty_contribution=jacobi * sigma,
            )
        )
    return quantities


def _float_of(text: str | None) -> float:
    """Read a number out of an XML element, tolerating an absent one.

    Args:
        text: The element text, or None when the element was missing.

    Returns:
        The value, or 0.0 when there was nothing to read.
    """
    try:
        return float(text) if text is not None else 0.0
    except ValueError:
        return 0.0


def from_quantity(
    key: str,
    label: str,
    uncertain_number: Any,
    *,
    unit: str = "",
    note: str = "",
) -> Contribution:
    """Build a contribution from an uncertain number that already exists.

    Use this where one physical quantity genuinely enters two measurements. A national
    standard is one artefact whose realisation is one quantity, and two comparisons made
    against it are correlated through it. Declaring it separately in each budget would
    describe two different standards that happen to have the same value, which is a
    different and untrue statement.

    Args:
        key: Identifier used inside the model function.
        label: Human-readable description for the budget table.
        uncertain_number: The existing quantity.
        unit: Unit symbol of the quantity.
        note: Optional provenance.

    Returns:
        The contribution, carrying the existing quantity and therefore its identifier.
    """
    return Contribution(
        key=key,
        label=label,
        value=float(mu.get_value(uncertain_number)),
        standard_uncertainty=float(mu.get_stdunc(uncertain_number)),
        unit=unit,
        distribution="shared quantity",
        note=note,
        uncertain_number=uncertain_number,
    )
