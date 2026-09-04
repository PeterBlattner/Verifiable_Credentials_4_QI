"""Tests for the metrology domain: uncertainty budgets, scope decisions, status lists."""

from __future__ import annotations

import math

import pytest

from vcqi.domain.accreditation import scope_by_id
from vcqi.domain.kcdb import cmc_by_id
from vcqi.domain.scope import (
    DeclaredCapability,
    MeasurementClaim,
    UncertaintyFloor,
    evaluate_scope,
)
from vcqi.domain.uncertainty import (
    evaluate,
    format_measurement,
    from_expanded_uncertainty,
    normal,
    rectangular,
)
from vcqi.vc.status import BitstringStatusList, read_status


class TestUncertainty:
    """Propagation follows the GUM and reports at k = 2."""

    def test_rectangular_distribution_divides_by_root_three(self) -> None:
        """A tolerance band becomes a Standard Uncertainty of a over root three."""
        contribution = rectangular("drift", "Drift", 0.0, 5.0e-4, unit="ohm")
        assert contribution.standard_uncertainty == pytest.approx(5.0e-4 / math.sqrt(3.0))

    def test_certificate_value_divides_by_the_coverage_factor(self) -> None:
        """An Expanded Uncertainty from a certificate enters a budget as U over k."""
        contribution = from_expanded_uncertainty(
            "ref", "Reference", 10000.0, 1.1e-3, coverage_factor=2.0, unit="ohm"
        )
        assert contribution.standard_uncertainty == pytest.approx(5.5e-4)

    def test_product_propagates_as_root_sum_of_squares(self) -> None:
        """For a product of independent quantities the relative uncertainties combine."""
        result = evaluate(
            lambda q: q["a"] * q["b"],
            [
                normal("a", "A", 100.0, 1.0, unit="ohm"),
                normal("b", "B", 2.0, 0.02),
            ],
            unit="ohm",
        )
        expected_relative = math.sqrt((1.0 / 100.0) ** 2 + (0.02 / 2.0) ** 2)
        assert result.value == pytest.approx(200.0)
        assert result.standard_uncertainty == pytest.approx(200.0 * expected_relative)
        assert result.expanded_uncertainty == pytest.approx(2.0 * result.standard_uncertainty)

    def test_correlated_inputs_are_not_double_counted(self) -> None:
        """A quantity subtracted from itself has zero uncertainty.

        This is the property a hand-written root-sum-square gets wrong, and the reason
        the budget rather than the bare number is what belongs in a credential.
        """
        result = evaluate(
            lambda q: q["a"] - q["a"],
            [normal("a", "A", 10.0, 0.5, unit="ohm")],
            unit="ohm",
        )
        assert result.standard_uncertainty == pytest.approx(0.0, abs=1e-15)

    def test_budget_indices_sum_to_one(self) -> None:
        """Every contribution to the variance is accounted for."""
        result = evaluate(
            lambda q: q["a"] * q["b"] + q["c"],
            [
                normal("a", "A", 10000.0, 5.5e-4, unit="ohm"),
                normal("b", "B", 1.000003, 2.6e-6),
                rectangular("c", "C", 0.0, 5.0e-4, unit="ohm"),
            ],
            unit="ohm",
        )
        assert sum(line.index for line in result.budget) == pytest.approx(1.0)

    def test_sensitivity_coefficient_of_a_product(self) -> None:
        """The sensitivity to one factor of a product is the other factor."""
        result = evaluate(
            lambda q: q["a"] * q["b"],
            [normal("a", "A", 4.0, 0.1), normal("b", "B", 3.0, 0.1)],
            unit="",
        )
        by_key = {line.key: line for line in result.budget}
        assert by_key["a"].sensitivity_coefficient == pytest.approx(3.0)
        assert by_key["b"].sensitivity_coefficient == pytest.approx(4.0)

    def test_duplicate_keys_are_rejected(self) -> None:
        """Two contributions cannot share a key, or one would silently shadow the other."""
        with pytest.raises(ValueError, match="unique"):
            evaluate(
                lambda q: q["a"],
                [normal("a", "A", 1.0, 0.1), normal("a", "Also A", 2.0, 0.1)],
                unit="",
            )

    @pytest.mark.parametrize(
        ("value", "expanded", "expected"),
        [
            (10000.0012, 0.0011313708, "10000.0012 +/- 0.0011 ohm (k = 2)"),
            (10000.032, 0.052, "10000.032 +/- 0.052 ohm (k = 2)"),
            (0.28, 0.02, "0.280 +/- 0.020 ohm (k = 2)"),
        ],
    )
    def test_reporting_rounds_only_at_the_end(
        self, value: float, expanded: float, expected: str
    ) -> None:
        """U is shown to two significant figures and the value matched to it."""
        assert format_measurement(value, expanded, "ohm") == expected


class TestScope:
    """A claim is inside a capability only if every condition holds."""

    @pytest.fixture()
    def capability(self) -> DeclaredCapability:
        """Return the resistance capability of the demonstration institute."""
        entry = cmc_by_id("CH-EM-0042")
        assert entry is not None
        return entry.as_capability()

    def test_floor_combines_absolute_and_relative_terms(self) -> None:
        """The uncertainty floor is the quadrature sum of its two terms."""
        floor = UncertaintyFloor(absolute=2.0e-4, relative=1.0e-7)
        assert floor.evaluate(1.0e4) == pytest.approx(math.sqrt(2.0e-4**2 + 1.0e-3**2))

    def test_claim_inside_the_capability_passes(self, capability) -> None:
        """A result at a covered level with a large enough uncertainty is in scope."""
        claim = MeasurementClaim("dc.resistance", "ohm", 10000.0012, 1.1e-3, 2.0)
        assert evaluate_scope(capability, claim).within_scope

    def test_uncertainty_smaller_than_the_floor_fails(self, capability) -> None:
        """Claiming better than the published capability is out of scope.

        The bound runs in the direction people new to this usually get backwards: the
        capability states the smallest achievable uncertainty, so a smaller claim is
        the failure, not a larger one.
        """
        claim = MeasurementClaim("dc.resistance", "ohm", 10000.0012, 5.0e-4, 2.0)
        verdict = evaluate_scope(capability, claim)
        assert not verdict.within_scope
        assert [check.key for check in verdict.failures] == ["uncertainty"]

    def test_larger_uncertainty_is_still_in_scope(self, capability) -> None:
        """A more cautious claim than the capability requires remains covered."""
        claim = MeasurementClaim("dc.resistance", "ohm", 10000.0012, 5.0e-2, 2.0)
        assert evaluate_scope(capability, claim).within_scope

    def test_level_above_the_range_fails(self, capability) -> None:
        """A level outside the published range is not covered at any uncertainty."""
        claim = MeasurementClaim("dc.resistance", "ohm", 1.0e7, 5.0, 2.0)
        verdict = evaluate_scope(capability, claim)
        assert not verdict.within_scope
        assert "range" in [check.key for check in verdict.failures]

    def test_different_measurand_fails(self, capability) -> None:
        """A capability for resistance says nothing about capacitance."""
        claim = MeasurementClaim("capacitance", "F", 1.0e-9, 1.0e-13, 2.0)
        verdict = evaluate_scope(capability, claim)
        assert not verdict.within_scope
        assert "measurand" in [check.key for check in verdict.failures]

    def test_mismatched_coverage_factor_is_not_compared(self, capability) -> None:
        """Uncertainties at different coverage factors are refused, not converted.

        Silently treating a k = 1 claim as comparable would pass a claim twice as good
        as anything the institute has demonstrated.
        """
        claim = MeasurementClaim("dc.resistance", "ohm", 10000.0012, 1.1e-3, 1.0)
        verdict = evaluate_scope(capability, claim)
        assert not verdict.within_scope
        keys = [check.key for check in verdict.failures]
        assert "coverage-factor" in keys and "uncertainty" in keys

    def test_accreditation_scope_is_wider_than_the_cmc(self) -> None:
        """The laboratory can work over a wider range but not as well as the institute."""
        cmc = cmc_by_id("CH-EM-0042")
        accreditation = scope_by_id("SCS 0123")
        assert cmc is not None and accreditation is not None
        laboratory = accreditation.as_capability()
        assert laboratory is not None
        assert laboratory.range_maximum > cmc.range_maximum
        assert laboratory.uncertainty_floor.evaluate(1.0e4) > cmc.uncertainty_floor.evaluate(1.0e4)

    def test_testing_scope_has_no_numeric_capability(self) -> None:
        """A testing scope states methods rather than a measurand and a range."""
        accreditation = scope_by_id("STS 0456")
        assert accreditation is not None
        assert accreditation.as_capability() is None
        assert accreditation.methods


class TestStatusList:
    """Status lists are readable, private and reproducible."""

    def test_set_bit_reads_back(self) -> None:
        """A position marked in the list reads back as marked."""
        status = BitstringStatusList()
        status.set(7)
        assert read_status(status.encoded_list, 7)
        assert not read_status(status.encoded_list, 8)

    def test_encoding_is_reproducible(self) -> None:
        """Two identical lists encode to identical bytes."""
        first, second = BitstringStatusList(), BitstringStatusList()
        first.set(3)
        second.set(3)
        assert first.encoded_list == second.encoded_list

    def test_list_meets_the_minimum_length(self) -> None:
        """A short list would leak how many credentials an issuer has issued."""
        with pytest.raises(ValueError, match="at least"):
            BitstringStatusList(length=1024)

    def test_position_outside_the_list_is_rejected(self) -> None:
        """Reading past the end of the list raises rather than returning false."""
        status = BitstringStatusList()
        with pytest.raises(IndexError):
            status.set(BitstringStatusList().length + 1)

    def test_malformed_encoding_is_rejected(self) -> None:
        """An unreadable list is an error, never an implicit "not revoked"."""
        with pytest.raises(ValueError):
            read_status("not-multibase", 0)
