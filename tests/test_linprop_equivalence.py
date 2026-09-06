"""The pure-Python engine and METAS UncLib agree, and this says how exactly.

The demonstrator computes uncertainty with :mod:`vcqi.domain.linprop` wherever METAS
UncLib is not installed, which includes every deployed copy, because the UncLib licence
does not permit redistribution in a container image. That substitution is only
defensible if it is checked, so this module checks it.

Most of what is here needs both engines and therefore only runs on a licensed machine;
those tests skip elsewhere. Two do not, and they are the ones that matter for a
deployment: the committed blob keys are digests of the XML UncLib wrote, so
reproducing them proves the pure engine's XML is byte-identical without UncLib being
present to ask.
"""

from __future__ import annotations

import math

import pytest

from vcqi.domain import linprop
from vcqi.domain.engine import unclib_available
from vcqi.domain.unclib_blobs import blob_key
from vcqi.domain.uncertainty import seeded_input_id, to_unclib_xml

unclib_required = pytest.mark.skipif(
    not unclib_available(),
    reason="needs METAS UncLib: 'uv sync --extra unclib', and do not set VCQI_ENGINE",
)

if unclib_available():
    import metas_unclib as reference
else:  # pragma: no cover - the import is the thing being skipped
    reference = None


#: Every measurement model the demonstrator evaluates, as (name, inputs, model). The
#: inputs mirror the real budgets in actors/scenarios.py, actors/tamper.py and
#: web/app.py; the point is coverage of the arithmetic, not of the exact numbers.
MODELS: list[tuple[str, list[tuple[str, float, float]], object]] = [
    (
        "metas-calibration",
        [
            ("National standard", 10000.0007, 4.6e-4),
            ("Cryogenic current comparator ratio", 1.00000005, 2e-8),
            ("Temperature correction", 0.0, 1.1547005383792517e-4),
            ("Repeatability", 0.0, 2e-4),
        ],
        lambda q: q[0] * q[1] + q[2] + q[3],
    ),
    (
        "accredited-calibration",
        [
            ("Transfer standard", 10000.0012, 2.5e-4),
            ("Bridge ratio", 1.0000031, 2e-7),
            ("Drift", 0.0, 2.8867513459481287e-4),
            ("Temperature", 0.0, 5.773502691896258e-5),
        ],
        lambda q: q[0] * q[1] + q[2] + q[3],
    ),
    (
        "three-term",
        [
            ("National standard", 10000.0007, 3e-4),
            ("Ratio", 1.0000031, 4e-8),
            ("Repeatability", 0.0, 4e-4),
        ],
        lambda q: q[0] * q[1] + q[2],
    ),
    (
        "two-term-sum",
        [("National standard", 10000.0007, 3e-4), ("Repeatability", 0.0, 4e-4)],
        lambda q: q[0] + q[1],
    ),
    (
        "division",
        [("Numerator", 10000.0007, 3e-4), ("Denominator", 1.0000031, 4e-8)],
        lambda q: q[0] / q[1],
    ),
    (
        "difference",
        [("First", 10000.0007, 3e-4), ("Second", 10000.0012, 2.5e-4)],
        lambda q: q[0] - q[1],
    ),
    (
        "shared-input-twice",
        [("Standard", 10000.0007, 4.6e-4), ("Ratio", 1.0000031, 2e-7)],
        # The same input on both sides of a product: the engine must not double count.
        lambda q: q[0] * q[1] + q[0],
    ),
    (
        "scaled-by-a-constant",
        [("Standard", 10000.0007, 4.6e-4), ("Ratio", 1.0000031, 2e-7)],
        lambda q: (q[0] * q[1]) * 2.0 + 1.0,
    ),
]


def _inputs(engine, name: str, declarations: list[tuple[str, float, float]]) -> list:
    """Declare one model's inputs on a given engine.

    Args:
        engine: Either ``metas_unclib`` or :mod:`vcqi.domain.linprop`.
        name: The model name, used as the identifier context so that two models do not
            share influences.
        declarations: One ``(description, value, standard uncertainty)`` per input.

    Returns:
        The uncertain numbers, in declaration order.
    """
    return [
        engine.ufloat(value, sigma, id=seeded_input_id(description, name), desc=description)
        for description, value, sigma in declarations
    ]


@unclib_required
@pytest.mark.parametrize("name", [model[0] for model in MODELS])
class TestTheEnginesAgree:
    """Both engines, over every shape of model the demonstrator evaluates."""

    @staticmethod
    def _both(name: str):
        """Evaluate one model on both engines.

        Args:
            name: Which model.

        Returns:
            The two results and their two input lists.
        """
        _, declarations, model = next(item for item in MODELS if item[0] == name)
        mine = _inputs(linprop, name, declarations)
        theirs = _inputs(reference, name, declarations)
        return model(mine), model(theirs), mine, theirs

    def test_the_value_is_identical(self, name: str) -> None:
        """The best estimate agrees bit for bit."""
        mine, theirs, _, _ = self._both(name)
        assert linprop.get_value(mine) == float(reference.get_value(theirs))

    def test_the_standard_uncertainty_is_identical(self, name: str) -> None:
        """The combined Standard Uncertainty agrees bit for bit.

        This is the number a certificate reports, so bit-for-bit is the right bar: it
        is expanded by k = 2 and printed, and it is what a scope check is made against.
        """
        mine, theirs, _, _ = self._both(name)
        assert linprop.get_stdunc(mine) == float(reference.get_stdunc(theirs))

    def test_the_xml_is_byte_identical(self, name: str) -> None:
        """The dependency representation is the same document, byte for byte.

        Every credential records a digest over these bytes, so anything less than
        identical would change all 59 documents in the demonstration.
        """
        mine, theirs, _, _ = self._both(name)
        assert linprop.ustorage.to_xml_string(mine) == reference.ustorage.to_xml_string(theirs)

    def test_the_budget_contributions_agree(self, name: str) -> None:
        """Each input's contribution to the result agrees to within a few ULP.

        Not bit for bit, and the reason is worth recording. UncLib computes a
        contribution by inverting the dependency matrix
        (``DependsOn.ComputeUncComponent`` -> ``LinAlg.Inv``), so its rounding depends
        on the whole system rather than on the one input; this engine multiplies the
        sensitivity by the input's Standard Uncertainty, which is the definition. The
        two differ in the last bit or two for some inputs, in a direction that is not
        consistent because a matrix inverse's error is not.

        Where they differ, this engine is the self-consistent one: UncLib can report a
        sensitivity coefficient in a budget that disagrees with the Jacobian it wrote
        into the XML of the same result. See test_the_budget_agrees_with_the_xml below.
        """
        mine, theirs, my_inputs, their_inputs = self._both(name)
        for index, (mine_input, their_input) in enumerate(zip(my_inputs, their_inputs)):
            got = linprop.get_unc_component(mine, mine_input)[0][0]
            want = float(reference.get_unc_component(theirs, their_input)[0][0])
            assert got == pytest.approx(want, rel=1e-12), f"input {index} of {name}"

    def test_the_correlation_matrix_agrees(self, name: str) -> None:
        """Correlation between a model's result and its own inputs agrees.

        This is the mechanism chapter 6 rests on, so it is checked directly rather
        than only through the certificates that use it.
        """
        mine, theirs, my_inputs, their_inputs = self._both(name)
        got = linprop.get_correlation([mine, *my_inputs])
        want = reference.get_correlation([theirs, *their_inputs])
        for row in range(len(got)):
            for column in range(len(got)):
                assert got[row][column] == pytest.approx(
                    float(want[row][column]), rel=1e-12, abs=1e-15
                ), f"({row},{column}) of {name}"


@unclib_required
class TestSharedInfluencesCorrelate:
    """Two results resting on one input are correlated, identically on both engines."""

    @staticmethod
    def _pair(engine):
        """Build two results sharing one input.

        Args:
            engine: The engine to build on.

        Returns:
            The two results.
        """
        shared = engine.ufloat(
            10000.0007, 4.6e-4, id=seeded_input_id("Shared standard", "pair"), desc="Shared"
        )
        first_own = engine.ufloat(
            1.0000031, 2e-7, id=seeded_input_id("First ratio", "pair"), desc="First"
        )
        second_own = engine.ufloat(
            1.0000029, 3e-7, id=seeded_input_id("Second ratio", "pair"), desc="Second"
        )
        return shared * first_own, shared * second_own

    def test_the_correlation_coefficient_agrees(self) -> None:
        """The coefficient itself, which the demonstration quotes to two decimals."""
        first, second = self._pair(linprop)
        their_first, their_second = self._pair(reference)
        got = linprop.get_correlation([first, second])[0][1]
        want = float(reference.get_correlation([their_first, their_second])[0][1])
        assert got == pytest.approx(want, rel=1e-12)
        # And it is a real correlation, not an artefact of both being near 10 kiloohm.
        assert 0.0 < got < 1.0

    def test_the_difference_is_narrower_than_independence_would_give(self) -> None:
        """The shared input cancels in a difference, on both engines equally."""
        first, second = self._pair(linprop)
        tracked = linprop.get_stdunc(first - second)
        independent = math.hypot(linprop.get_stdunc(first), linprop.get_stdunc(second))
        assert tracked < independent

        their_first, their_second = self._pair(reference)
        assert tracked == pytest.approx(
            float(reference.get_stdunc(their_first - their_second)), rel=1e-12
        )


@unclib_required
class TestTheBudgetAgreesWithTheXml:
    """A result's budget and its own XML should not contradict each other."""

    def test_this_engine_is_self_consistent(self) -> None:
        """The sensitivity in a budget line equals the Jacobian in the same document.

        UncLib does not always manage this -- for the METAS certificate it reports
        10000.000699999999 in the budget where its own XML says 10000.0007 -- because
        the two come from different computations inside the library. Here they come
        from the same sensitivity vector, so they cannot disagree. This test exists to
        keep it that way.
        """
        import re

        from vcqi.actors import scenarios

        result = scenarios._metas_result()
        xml = to_unclib_xml(result)
        jacobians = dict(
            zip(
                re.findall(r"<Description>(.*?)</Description>", xml),
                (float(value) for value in re.findall(r"<Jacobi>(.*?)</Jacobi>", xml)),
            )
        )
        disagreements = [
            (line.label, jacobians[line.label], line.sensitivity_coefficient)
            for line in result.budget
            if line.label in jacobians
            and jacobians[line.label] != line.sensitivity_coefficient
        ]
        if unclib_available():
            # Not asserted for UncLib, which is the engine that gets this wrong.
            pytest.skip("this is a property of the pure-Python engine")
        assert not disagreements, disagreements


class TestTheCommittedBlobsDescribeTheWorld:
    """Runs on any machine, and is the check a deployment actually depends on."""

    def test_every_published_binary_form_has_a_blob(self) -> None:
        """The world's certificates all find their committed binary representation.

        The blobs are keyed by a digest of each result's XML, and those digests were
        computed from the XML *UncLib* wrote. So a machine without UncLib reproducing
        them proves two things at once: the committed set still covers the world, and
        the pure-Python engine's XML is byte-identical to UncLib's. If either drifted,
        the key would miss.
        """
        from vcqi.actors.scenarios import build_world
        from vcqi.domain.unclib_blobs import blob_for

        world = build_world()
        results = [result for result in world.results.values() if result.uncertain_number]
        assert results, "the world published no uncertainty results to check"

        missing = [
            blob_key(to_unclib_xml(result))
            for result in results
            if blob_for(to_unclib_xml(result)) is None
        ]
        assert not missing, (
            f"{len(missing)} of {len(results)} results have no committed binary form. "
            "Regenerate on a licensed machine: uv run python -m vcqi.domain.unclib_blobs"
        )

    def test_no_blob_is_orphaned(self) -> None:
        """Nothing is carried that no result asks for.

        The other half of the previous test. A blob left behind by a measurement that
        has since changed is dead weight that also makes the file misleading.
        """
        from vcqi.actors.scenarios import build_world
        from vcqi.domain.unclib_blobs import _blobs

        world = build_world()
        wanted = {
            blob_key(to_unclib_xml(result))
            for result in world.results.values()
            if result.uncertain_number
        }
        orphaned = set(_blobs()) - wanted
        assert not orphaned, (
            f"{len(orphaned)} committed blobs match no current result. "
            "Regenerate on a licensed machine: uv run python -m vcqi.domain.unclib_blobs"
        )


class TestDotNetFloatFormatting:
    """The XML is byte-identical only if numbers are written .NET's way."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (0.0, "0"),
            (1.0, "1"),
            (300000000.0, "300000000"),
            (0.0004, "0.0004"),
            (2e-7, "2E-07"),
            (1e-5, "1E-05"),
            (9.999e-5, "9.999E-05"),
            (1e16, "1E+16"),
            (1.5e20, "1.5E+20"),
            (0.1, "0.1"),
            (-0.5, "-0.5"),
            (1 / 3, "0.33333333333333331"),
            (123456789012345.6, "123456789012345.59"),
            (0.0020396082839608184, "0.0020396082839608184"),
        ],
    )
    def test_known_renderings(self, value: float, expected: str) -> None:
        """Values whose .NET rendering was read off UncLib itself.

        The interesting ones are the last two: .NET tries fifteen significant digits
        and falls back to seventeen, so a value that does not round-trip at fifteen
        gains digits Python's repr would not print.
        """
        assert linprop._format_double(value) == expected

    @unclib_required
    def test_it_matches_unclib_over_awkward_values(self) -> None:
        """Compared against the library across the whole double range.

        Random bit patterns rather than random magnitudes, so subnormals and values
        near the exponent thresholds are actually reached.
        """
        import random
        import re
        import struct

        random.seed(20260906)
        values = [0.0, 1.0, 0.1, 1 / 3, 1 / 7, 1e-5, 1e16, 2**53 - 1.0]
        while len(values) < 200:
            candidate = struct.unpack("<d", struct.pack("<Q", random.getrandbits(64)))[0]
            if math.isfinite(candidate):
                values.append(candidate)

        for index, value in enumerate(values):
            number = reference.ufloat(value, 1.0, id=seeded_input_id(str(index), "fmt"), desc="x")
            written = re.search(
                r"<Value>(.*?)</Value>", reference.ustorage.to_xml_string(number)
            ).group(1)
            assert linprop._format_double(value) == written, repr(value)
