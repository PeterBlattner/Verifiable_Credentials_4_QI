"""Tests for transmitting the dependency on input quantities to a customer.

The claim these make good is the one chapter 6 rests on: a certificate that carries its
dependency structure lets a recipient combine it correctly with another, and a
certificate that carries only a value and an Expanded Uncertainty does not, however
careful the recipient is.
"""

from __future__ import annotations

import math

import metas_unclib as mu
import pytest

from vcqi.actors.registry import TRUST_ANCHORS
from vcqi.actors.scenarios import DEMO_NOW, build_world
from vcqi.domain.gtc_archive import build_gtc_archive, gtc_available
from vcqi.domain.uncertainty import (
    evaluate,
    from_certificate,
    from_expanded_uncertainty,
    normal,
    parse_input_quantities,
    rectangular,
    seeded_input_id,
    to_unclib_binary,
    to_unclib_xml,
)
from vcqi.vc.model import artefact_document, artefact_payload, uncertainty_representations
from vcqi.vc.verify import verify_credential

gtc_required = pytest.mark.skipif(not gtc_available(), reason="GTC is not installed")


@pytest.fixture(scope="module")
def world():
    """Build the demonstration world once."""
    return build_world()


def _parent():
    """Return a result standing in for a certificate of a national institute."""
    return evaluate(
        lambda q: q["standard"] + q["repeatability"],
        [
            normal("standard", "National standard", 10000.0007, 3.0e-4, unit="ohm"),
            normal("repeatability", "Repeatability", 0.0, 4.0e-4, unit="ohm"),
        ],
        unit="ohm",
        context="parent",
    )


def _child(parent, *, classical: bool):
    """Return a laboratory result built on that certificate, either way round."""
    reference = (
        from_expanded_uncertainty(
            "reference",
            "Transfer standard",
            parent.value,
            parent.expanded_uncertainty,
            unit="ohm",
        )
        if classical
        else from_certificate("reference", "Transfer standard", to_unclib_xml(parent), unit="ohm")
    )
    return evaluate(
        lambda q: q["reference"] * q["ratio"] + q["drift"],
        [
            reference,
            normal("ratio", "Bridge ratio", 1.0000031, 4.0e-8),
            rectangular("drift", "Drift", 0.0, 1.0e-4, unit="ohm"),
        ],
        unit="ohm",
        context="child",
    )


class TestSeededIdentifiers:
    """Identifiers are reproducible without becoming accidentally shared."""

    def test_same_label_and_context_gives_the_same_identifier(self) -> None:
        """Two runs of the demonstration produce the same documents."""
        assert seeded_input_id("Drift", "AC-1") == seeded_input_id("Drift", "AC-1")

    def test_context_separates_identical_labels(self) -> None:
        """Two budgets that both say "drift" are not thereby talking about one effect.

        Without this, every certificate in the world would share its wording-identical
        influences and results with nothing to do with each other would come out
        perfectly correlated.
        """
        assert seeded_input_id("Drift", "AC-1") != seeded_input_id("Drift", "AC-2")

    def test_identifier_is_sixteen_bytes(self) -> None:
        """The identifier is four words, which UncLib reads as a 16 byte value."""
        assert len(seeded_input_id("Drift", "AC-1")) == 4


class TestSerialisation:
    """The dependency structure survives being written down and read back."""

    def test_round_trip_preserves_identity(self) -> None:
        """Two independent loads of one certificate remain the same quantity.

        This is the property everything else depends on. If it did not hold, a shared
        reference standard would stop being shared the moment it was transmitted.
        """
        parent = _parent()
        xml = to_unclib_xml(parent)
        first = mu.ustorage.from_xml_string(xml)
        second = mu.ustorage.from_xml_string(xml)
        assert float(mu.get_stdunc(first - second)) == pytest.approx(0.0, abs=1e-15)

    def test_influences_are_readable_without_the_library(self) -> None:
        """A plain XML parser recovers every influence and its sensitivity."""
        parent = _parent()
        influences = parse_input_quantities(to_unclib_xml(parent))
        assert [item.description for item in influences] == [
            "National standard",
            "Repeatability",
        ]
        combined = math.sqrt(sum(item.uncertainty_contribution**2 for item in influences))
        assert combined == pytest.approx(parent.standard_uncertainty)

    def test_binary_is_smaller_than_xml(self) -> None:
        """The binary form exists because the XML form does not scale."""
        parent = _parent()
        assert len(to_unclib_binary(parent)) < len(to_unclib_xml(parent).encode("utf-8"))

    def test_child_carries_the_influences_of_its_parent(self) -> None:
        """A result built in dependency mode transmits what it inherited."""
        parent = _parent()
        child = _child(parent, classical=False)
        parent_ids = {item.identifier for item in parse_input_quantities(to_unclib_xml(parent))}
        child_ids = {item.identifier for item in parse_input_quantities(to_unclib_xml(child))}
        assert parent_ids <= child_ids

    def test_classical_child_carries_none_of_them(self) -> None:
        """A result built from the printed numbers inherits no identifiers."""
        parent = _parent()
        child = _child(parent, classical=True)
        parent_ids = {item.identifier for item in parse_input_quantities(to_unclib_xml(parent))}
        child_ids = {item.identifier for item in parse_input_quantities(to_unclib_xml(child))}
        assert not (parent_ids & child_ids)

    def test_unreadable_xml_is_rejected(self) -> None:
        """Malformed dependency data raises rather than being partly believed."""
        with pytest.raises(ValueError):
            parse_input_quantities("not xml at all")
        with pytest.raises(ValueError):
            from_certificate("k", "label", "not xml at all")


class TestBothModesAgree:
    """The two ways of entering a certificate differ in what they preserve, not in U."""

    def test_the_expanded_uncertainty_is_identical(self) -> None:
        """A certificate looks exactly the same either way.

        Which is the point: nothing on the face of the document reveals whether the
        laboratory preserved the dependency structure or discarded it.
        """
        parent = _parent()
        assert _child(parent, classical=False).expanded_uncertainty == pytest.approx(
            _child(parent, classical=True).expanded_uncertainty
        )

    def test_only_dependency_mode_stays_correlated_with_the_parent(self) -> None:
        """The information that is lost is the correlation, and only that."""
        parent = _parent()
        dependency = _child(parent, classical=False)
        classical = _child(parent, classical=True)

        correlated = mu.get_correlation(
            [parent.uncertain_number, dependency.uncertain_number]
        )[0][1]
        detached = mu.get_correlation([parent.uncertain_number, classical.uncertain_number])[0][1]

        assert correlated > 0.0
        assert detached == pytest.approx(0.0, abs=1e-15)


class TestRepresentations:
    """What a certificate offers, and how it is protected."""

    def test_classical_statement_is_always_first(self) -> None:
        """Every certificate says what a paper certificate would say."""
        representations, _ = uncertainty_representations(_parent(), credential_id="urn:x")
        assert representations[0]["type"] == "ClassicalStatement"

    def test_small_xml_travels_inline_and_binary_by_reference(self) -> None:
        """Both transport paths are exercised by an ordinary certificate."""
        representations, artefacts = uncertainty_representations(
            _parent(), credential_id="urn:x"
        )
        by_format = {item["format"]: item for item in representations}
        assert "content" in by_format["METAS-UncLib-XML"]
        assert by_format["METAS-UncLib-binary"]["id"] in artefacts

    def test_digests_are_over_the_raw_payload(self) -> None:
        """The digest covers the data itself, not the envelope it is published in."""
        from vcqi.crypto.multibase import verify_digest_multibase

        result = _parent()
        representations, artefacts = uncertainty_representations(result, credential_id="urn:x")
        by_format = {item["format"]: item for item in representations}

        inline = by_format["METAS-UncLib-XML"]
        assert verify_digest_multibase(inline["content"].encode("utf-8"), inline["digestMultibase"])

        referenced = by_format["METAS-UncLib-binary"]
        _, payload = artefacts[referenced["id"]]
        assert verify_digest_multibase(payload, referenced["digestMultibase"])

    def test_a_result_without_dependencies_offers_only_the_classical_statement(self) -> None:
        """An issuer with no such tool still produces a valid certificate."""
        from vcqi.domain.uncertainty import MeasurementResult

        bare = MeasurementResult(value=1.0, standard_uncertainty=0.1, unit="ohm")
        representations, artefacts = uncertainty_representations(bare, credential_id="urn:x")
        assert len(representations) == 1
        assert not artefacts

    @pytest.mark.parametrize(
        "media_type", ["application/xml", "application/json", "application/octet-stream"]
    )
    def test_artefact_envelope_round_trips(self, media_type: str) -> None:
        """Publishing wraps the payload without altering it."""
        payload = bytes(range(64))
        assert artefact_payload(artefact_document(media_type, payload)) == payload

    def test_malformed_envelope_returns_nothing(self) -> None:
        """A verifier meets these as untrusted input, so it reports rather than raises."""
        assert artefact_payload({"nope": True}) is None
        assert artefact_payload(
            {"@type": "UncertaintyData", "encoding": "base64", "data": "!!!"}
        ) is None


class TestSharedReference:
    """The demonstration the whole feature exists to make."""

    def test_the_pair_is_correlated_through_its_shared_standard(self, world) -> None:
        """Both check standards rest on the same transfer standard."""
        first = world.results["metas-SR10K-0091"].uncertain_number
        second = world.results["metas-SR10K-0092"].uncertain_number
        assert mu.get_correlation([first, second])[0][1] == pytest.approx(0.69, abs=0.02)

    def test_classical_reporting_overstates_the_difference(self, world) -> None:
        """Ignoring the shared influence inflates U(R1 - R2) by about 1.8 times."""
        first = world.results["metas-SR10K-0091"]
        second = world.results["metas-SR10K-0092"]

        tracked = float(mu.get_stdunc(first.uncertain_number - second.uncertain_number))
        naive = math.sqrt(first.standard_uncertainty**2 + second.standard_uncertainty**2)
        assert naive / tracked == pytest.approx(1.81, abs=0.03)

    def test_classical_reporting_understates_the_mean(self, world) -> None:
        """Direction depends on the operation, so ignoring correlation is not cautious.

        For a mean, positive correlation makes the result less certain rather than more.
        Discarding the dependency structure is not a conservative simplification; it is
        an error whose sign the recipient cannot even determine.
        """
        first = world.results["metas-SR10K-0091"]
        second = world.results["metas-SR10K-0092"]

        tracked = float(
            mu.get_stdunc((first.uncertain_number + second.uncertain_number) / 2.0)
        )
        naive = 0.5 * math.sqrt(
            first.standard_uncertainty**2 + second.standard_uncertainty**2
        )
        assert naive < tracked


class TestVerification:
    """The three checks the dependency representations make possible."""

    def _report(self, world, name):
        return verify_credential(
            world.credential(name),
            store=world.store,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
        )

    def _find(self, report, step_id):
        def walk(steps):
            for step in steps:
                if step.id == step_id:
                    return step
                found = walk(step.children)
                if found is not None:
                    return found
            return None

        return walk(report.steps)

    def test_representations_verify(self, world) -> None:
        """Inline and referenced representations both match their recorded digests."""
        step = self._find(self._report(world, "metas-calibration"), "uncertainty.representations")
        assert step is not None and step.status == "pass"

    def test_printed_result_agrees_with_the_dependencies(self, world) -> None:
        """The two stories a certificate tells are checked against each other."""
        step = self._find(self._report(world, "metas-calibration"), "uncertainty.agreement")
        assert step is not None and step.status == "pass"

    def test_inherited_influences_are_present(self, world) -> None:
        """Traceability is confirmed in the arithmetic, not only in the paperwork."""
        step = self._find(self._report(world, "callab-calibration"), "traceability.shared-inputs")
        assert step is not None and step.status == "pass"
        assert step.evidence["missingCount"] == 0
        assert step.evidence["sharedCount"] == 4

    def test_the_new_checks_nest_rather_than_lengthen_the_list(self, world) -> None:
        """Representations and agreement sit under the uncertainty step.

        The top level grew by one when legal metrology arrived, and by nothing when the
        dependency representations did, which is the distinction being asserted.
        """
        report = self._report(world, "callab-calibration")
        assert len(report.steps) == 12
        uncertainty = next(step for step in report.steps if step.id == "uncertainty")
        assert "uncertainty.representations" in [child.id for child in uncertainty.children]

    def test_every_certificate_still_verifies(self, world) -> None:
        """Adding representations broke nothing in the base world."""
        for name in ("metas-calibration", "callab-calibration", "metas-SR10K-0091", "cab-conformity"):
            assert self._report(world, name).outcome == "verified"


class TestGtc:
    """The optional second implementation, when it is installed."""

    def test_absent_gtc_is_reported_rather_than_failing(self) -> None:
        """Everything works without the extra; the archive is simply not built."""
        if gtc_available():
            pytest.skip("GTC is installed, so the absent path cannot be exercised")
        assert build_gtc_archive(_parent()) is None

    @gtc_required
    def test_archive_is_built_and_carried(self) -> None:
        """With the extra installed, the certificate gains a GTC representation."""
        result = _parent()
        archive = build_gtc_archive(result)
        assert archive is not None

        representations, _ = uncertainty_representations(
            result, credential_id="urn:x", gtc_archive=archive
        )
        assert any(item["format"] == "GTC-archive-JSON" for item in representations)
