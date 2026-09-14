"""Tests for the metrology domain: uncertainty budgets, scope decisions, status lists."""

from __future__ import annotations

import math

import pytest

from vcqi.domain.accreditation import scope_by_id
from vcqi.domain.kcdb import cmc_by_id
from vcqi.domain.scope import (
    ConditionBand,
    DeclaredCapability,
    Interval,
    MeasurementClaim,
    Points,
    ScopeRow,
    UncertaintyFloor,
    Window,
    evaluate_scope,
    scope_row_from_json,
    select_row,
    union_capabilities,
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
        row = next(
            row
            for row in accreditation.as_rows()
            if row.object_category == "materialMeasure"
            and row.measurand == "dc.resistance"
        )
        assert row.coverage.span()[1] > cmc.range_maximum
        assert row.floor.evaluate(1.0e4) > cmc.uncertainty_floor.evaluate(1.0e4)

    def test_testing_scope_has_no_numeric_capability(self) -> None:
        """A testing scope states methods rather than a table of capabilities."""
        accreditation = scope_by_id("STS 0456")
        assert accreditation is not None
        assert accreditation.as_rows() == ()
        assert accreditation.methods


class TestScopeRowGrammars:
    """A published scope says which levels it covers in more than one way."""

    def test_a_strict_upper_bound_excludes_its_own_bound(self) -> None:
        """``1 ohm ... < 220 kohm`` does not cover 220 kohm.

        A model with inclusive bounds only would grant a laboratory the one level its
        accreditation body wrote the ``<`` to exclude.
        """
        interval = Interval(minimum=1.0, maximum=2.2e5, upper="exclusive")
        assert interval.covers(2.19999e5)
        assert not interval.covers(2.2e5)
        assert Interval(minimum=1.0, maximum=2.2e5).covers(2.2e5)

    def test_fixed_values_do_not_cover_the_gaps_between_them(self) -> None:
        """A row of fixed values has not declared the interval they span."""
        points = Points(values=(19.2, 192.0))
        assert points.covers(19.2)
        assert points.covers(192.0)
        assert not points.covers(100.0)
        assert points.span() == (19.2, 192.0)

    def test_a_fixed_value_tolerates_the_reading_it_produces(self) -> None:
        """The point is a nominal; the certificate reports what was measured."""
        points = Points(values=(19.2,), match_tolerance=1.0e-3)
        assert points.covers(19.2003)
        assert not points.covers(19.3)

    def test_a_window_is_a_nominal_with_a_tolerance(self) -> None:
        """``(22,5 +/- 2,5) uohm`` covers its band and nothing outside it."""
        window = Window(nominal=22.5e-6, tolerance=2.5e-6)
        assert window.covers(20.0e-6) and window.covers(25.0e-6)
        assert not window.covers(25.1e-6)

    def test_a_single_term_floor_renders_as_one_term(self) -> None:
        """A register writing ``125 x 10^-6 R`` did not write a quadrature sum."""
        assert UncertaintyFloor(0.0, 125.0e-6).describe("ohm") == (
            "U = 125 x 10^-6 x value, k = 2"
        )
        assert UncertaintyFloor(0.2, 0.0).describe("dB") == "U = 0.2 dB, k = 2"
        assert "sqrt" in UncertaintyFloor(1.0e-3, 5.0e-6).describe("ohm")

    def test_a_row_survives_the_round_trip_through_json(self) -> None:
        """What the register publishes is what a verifier rebuilds.

        The verifier reads the fetched document rather than its own copy of the domain
        model, so anything this loses is a check that silently stops happening.
        """
        row = ScopeRow(
            label="row",
            measurand="dc.resistance",
            unit="ohm",
            object_category="materialMeasure",
            coverage=Interval(minimum=1.0, maximum=2.2e5, upper="exclusive"),
            floor=UncertaintyFloor(absolute=5.0e-4, relative=2.0e-6),
            condition=ConditionBand("frequency", 0.0, 0.0, "Hz", "DC"),
            remarks=("Cylindrical rods only.",),
        )
        assert scope_row_from_json(row.to_json()) == row


class TestSelectingTheRowThatApplies:
    """Which row applies is a check of its own, with its own failure."""

    @staticmethod
    def _claim(**overrides: object) -> MeasurementClaim:
        """Return a claim against the demonstration calibration scope.

        Args:
            **overrides: Members to replace on the default claim.

        Returns:
            The claim.
        """
        defaults: dict[str, object] = {
            "measurand": "dc.resistance",
            "unit": "ohm",
            "value": 10000.03,
            "expanded_uncertainty": 5.2e-2,
            "coverage_factor": 2.0,
            "nominal": 1.0e4,
            "object_category": "measuringInstrument",
            "conditions": {"frequency": 0.0},
            "condition_units": {"frequency": "Hz"},
        }
        defaults.update(overrides)
        return MeasurementClaim(**defaults)  # type: ignore[arg-type]

    @pytest.fixture()
    def rows(self) -> tuple[ScopeRow, ...]:
        """Return the published rows of the calibration scope.

        Returns:
            The rows, in register order.
        """
        scope = scope_by_id("SCS 0123")
        assert scope is not None
        return scope.as_rows()

    def test_the_instrument_row_is_chosen_for_an_instrument(self, rows) -> None:
        """Calibrating an ohmmeter is not calibrating a resistance."""
        selection = select_row(rows, self._claim())
        assert selection.row is not None
        assert selection.row.object_category == "measuringInstrument"
        assert selection.level_source == "nominal value"

    def test_a_material_measure_selects_a_different_row(self, rows) -> None:
        """Same quantity, same level, different row and a different capability."""
        instrument = select_row(rows, self._claim()).row
        artefact = select_row(
            rows, self._claim(object_category="materialMeasure")
        ).row
        assert instrument is not None and artefact is not None
        assert artefact.label != instrument.label
        assert artefact.floor.evaluate(1.0e4) < instrument.floor.evaluate(1.0e4)

    def test_two_rows_differing_only_by_frequency_are_told_apart(self, rows) -> None:
        """The case that makes conditions an axis rather than prose."""
        slow = select_row(
            rows,
            self._claim(
                measurand="ac.resistance",
                value=0.5,
                nominal=0.5,
                object_category="materialMeasure",
                conditions={"frequency": 1.0},
            ),
        ).row
        fast = select_row(
            rows,
            self._claim(
                measurand="ac.resistance",
                value=0.5,
                nominal=0.5,
                object_category="materialMeasure",
                conditions={"frequency": 10.0},
            ),
        ).row
        assert slow is not None and fast is not None
        assert slow.label != fast.label
        assert slow.floor.relative != fast.floor.relative

    def test_a_certificate_stating_no_condition_matches_no_banded_row(
        self, rows
    ) -> None:
        """Not stating a frequency is not the same as stating direct current."""
        selection = select_row(
            rows, self._claim(conditions={}, condition_units={})
        )
        assert selection.row is None
        assert any("states no frequency" in r.reason for r in selection.rejections)

    def test_a_condition_in_another_unit_is_not_compared(self, rows) -> None:
        """Ten kilohertz is not ten hertz, and nothing here converts it."""
        selection = select_row(
            rows,
            self._claim(
                measurand="ac.resistance",
                value=0.5,
                nominal=0.5,
                object_category="materialMeasure",
                conditions={"frequency": 10.0},
                condition_units={"frequency": "kHz"},
            ),
        )
        assert selection.row is None

    def test_a_level_between_the_fixed_values_selects_nothing(self, rows) -> None:
        """The failure the old single-row model could not produce."""
        selection = select_row(rows, self._claim(value=500.0, nominal=500.0))
        assert selection.row is None
        assert [r.label for r in selection.rejections] == [row.label for row in rows]

    def test_every_rejection_says_which_row_and_why(self, rows) -> None:
        """A refusal that does not say which row it looked at is not a finding."""
        selection = select_row(rows, self._claim(measurand="capacitance", unit="F"))
        assert selection.row is None
        assert len(selection.rejections) == len(rows)
        assert all(rejection.reason for rejection in selection.rejections)


class TestCollapsingAScopeForASchema:
    """What an offline schema can say about a table, and what it loses."""

    def test_one_branch_per_quantity(self) -> None:
        """A scope covering two quantities cannot be one constant."""
        scope = scope_by_id("SCS 0123")
        assert scope is not None
        capabilities = union_capabilities(scope.as_rows(), label="SCS 0123")
        assert {capability.measurand for capability in capabilities} == {
            "dc.resistance",
            "ac.resistance",
        }

    def test_the_union_is_permissive_rather_than_strict(self) -> None:
        """Every collapse has to lose in the direction that admits too much.

        A schema stricter than the register would refuse certificates the accreditation
        body allows, and the verifier would never get as far as the row that permits
        them.
        """
        scope = scope_by_id("SCS 0123")
        assert scope is not None
        capabilities = union_capabilities(scope.as_rows(), label="SCS 0123")
        direct = next(c for c in capabilities if c.measurand == "dc.resistance")
        rows = [row for row in scope.as_rows() if row.measurand == "dc.resistance"]
        assert direct.coverage.span()[1] >= max(row.coverage.span()[1] for row in rows)
        assert direct.uncertainty_floor.evaluate(1.0e4) <= min(
            row.floor.evaluate(1.0e4) for row in rows
        )

    def test_a_scope_with_no_rows_collapses_to_nothing(self) -> None:
        """A testing scope has no capability table, and gets no calibration schema."""
        scope = scope_by_id("STS 0456")
        assert scope is not None
        assert union_capabilities(scope.as_rows(), label="STS 0456") == ()


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
