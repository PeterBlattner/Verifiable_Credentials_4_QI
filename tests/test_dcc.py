"""Tests for the PTB/DKD DCC carrier and the redundancy it creates.

Two claims are being made good. That the generated document is genuinely shaped like a
PTB/DKD DCC — real namespaces, real elements, real D-SI — and that carrying it is not
free: it says most of the certificate a second time, and the only thing standing between
that and a self-contradicting document is a check that reads both copies.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree

import pytest

from vcqi.actors.registry import TRUST_ANCHORS
from vcqi.actors.scenarios import DEMO_NOW, build_world
from vcqi.actors.tamper import TAMPER_CASES
from vcqi.domain.dcc import (
    DCC_NAMESPACE,
    DCC_SCHEMA_VERSION,
    SI_NAMESPACE,
    dsi_unit,
    parse_dcc_administrative,
    parse_dcc_result,
    to_dcc_xml,
)
from vcqi.domain.instruments import instrument_by_id
from vcqi.vc.verify import verify_credential

NAMESPACES = {"dcc": DCC_NAMESPACE, "si": SI_NAMESPACE}


@pytest.fixture(scope="module")
def world():
    """Build the demonstration world once."""
    return build_world()


@pytest.fixture(scope="module")
def document(world) -> str:
    """Return the PTB/DKD DCC carried by the certificate of the institute."""
    return _carried(world, "metas-calibration")["content"]


def _carried(world, name: str) -> dict:
    """Return the PTB/DKD DCC representation from a credential."""
    results = world.credential(name)["credentialSubject"]["calibration"]["results"][0]
    return next(
        item
        for item in results["uncertaintyRepresentations"]
        if item["format"] == "PTB-DKD-DCC-XML"
    )


def _find(report, step_id):
    """Find a step anywhere in a verification report."""

    def walk(steps):
        for step in steps:
            if step.id == step_id:
                return step
            found = walk(step.children)
            if found is not None:
                return found
        return None

    return walk(report.steps)


class TestDsiUnits:
    """D-SI writes units its own way, and one case in particular catches people."""

    @pytest.mark.parametrize(
        ("symbol", "expected"),
        [("ohm", r"\ohm"), ("V", r"\volt"), ("m", r"\metre"), ("", r"\one")],
    )
    def test_units_are_backslashed_english_names(self, symbol: str, expected: str) -> None:
        """siunitx notation, not the symbol a certificate would print."""
        assert dsi_unit(symbol) == expected

    def test_the_kilogram_is_a_prefix_and_a_gram(self) -> None:
        """The one worth a test of its own.

        It is the SI base unit, and D-SI still writes it as a prefix token plus a base
        unit, so it is two tokens rather than one.
        """
        assert dsi_unit("kg") == r"\kilo\gram"
        assert dsi_unit("kg") != r"\kilogram"

    def test_an_unmapped_unit_raises_rather_than_guessing(self) -> None:
        """A certificate quietly stating the wrong unit is the worse failure."""
        with pytest.raises(ValueError, match="no D-SI notation"):
            dsi_unit("furlong")


class TestDocumentShape:
    """The generated document is shaped like a PTB/DKD DCC, not merely named one."""

    def test_it_parses_and_declares_both_namespaces(self, document: str) -> None:
        """The root is the DCC element and the schema version is stated."""
        root = ElementTree.fromstring(document)
        assert root.tag == f"{{{DCC_NAMESPACE}}}digitalCalibrationCertificate"
        assert root.get("schemaVersion") == DCC_SCHEMA_VERSION

    @pytest.mark.parametrize(
        "path",
        [
            "./dcc:administrativeData/dcc:coreData/dcc:uniqueIdentifier",
            "./dcc:administrativeData/dcc:coreData/dcc:beginPerformanceDate",
            "./dcc:administrativeData/dcc:items/dcc:item",
            "./dcc:administrativeData/dcc:calibrationLaboratory",
            "./dcc:administrativeData/dcc:customer",
            "./dcc:measurementResults/dcc:measurementResult/dcc:usedMethods",
            "./dcc:measurementResults/dcc:measurementResult/dcc:influenceConditions",
        ],
    )
    def test_the_real_element_paths_are_present(self, document: str, path: str) -> None:
        """Element names and nesting follow the published schema."""
        assert ElementTree.fromstring(document).find(path, NAMESPACES) is not None

    def test_the_quantity_is_expressed_in_dsi(self, document: str) -> None:
        """The measurement bottoms out in si:real with an expanded uncertainty."""
        root = ElementTree.fromstring(document)
        real = root.find(
            "./dcc:measurementResults/dcc:measurementResult/dcc:results/dcc:result"
            "/dcc:data/dcc:list/dcc:quantity/si:real",
            NAMESPACES,
        )
        assert real is not None
        assert real.find("si:value", NAMESPACES) is not None
        assert real.find("si:unit", NAMESPACES).text == r"\ohm"
        expanded = real.find("si:expandedUnc", NAMESPACES)
        assert expanded.find("si:uncertainty", NAMESPACES) is not None
        assert expanded.find("si:coverageFactor", NAMESPACES) is not None

    def test_the_signature_slot_is_left_empty(self, document: str) -> None:
        """A decision rather than an omission.

        The credential signs once and covers these bytes by digest, so there is one
        trust path instead of two that could disagree.
        """
        assert "Signature" not in document

    def test_an_unmapped_unit_stops_the_document_being_built(self, world) -> None:
        """The refusal propagates rather than producing a wrong certificate."""
        result = world.results["metas-calibration"]
        broken = type(result)(
            value=result.value,
            standard_uncertainty=result.standard_uncertainty,
            unit="furlong",
            coverage_factor=result.coverage_factor,
            budget=result.budget,
        )
        with pytest.raises(ValueError, match="no D-SI notation"):
            to_dcc_xml(
                broken,
                certificate_number="X",
                performed_on="2026-01-01",
                issued_on="2026-01-02",
                measurand="length",
                conditions="none",
                instrument=instrument_by_id(
                    "urn:instrument:callab:standard-resistor:SR10K-0042"
                ).to_json(),
                laboratory={"id": "did:web:metas.example", "name": "METAS"},
                customer={"id": "did:web:callab.example", "name": "Alpine"},
            )


class TestReadingItBack:
    """A verifier parses it without the tool that wrote it."""

    def test_the_quantity_round_trips(self, world, document: str) -> None:
        """Value, unit, U and k come back as they went in."""
        parsed = parse_dcc_result(document)
        result = world.results["metas-calibration"]
        assert parsed["value"] == pytest.approx(result.value)
        assert parsed["unit"] == r"\ohm"
        assert parsed["expandedUncertainty"] == pytest.approx(result.expanded_uncertainty)
        assert parsed["coverageFactor"] == pytest.approx(result.coverage_factor)

    def test_the_dcc_states_the_expanded_uncertainty_not_the_standard_one(
        self, world, document: str
    ) -> None:
        """The direction the comparison has to divide in.

        Confusing the two would make a certificate look twice as good or twice as bad as
        it is, which is precisely what the agreement check exists to catch, so the
        distinction is asserted rather than assumed.
        """
        parsed = parse_dcc_result(document)
        result = world.results["metas-calibration"]
        assert parsed["expandedUncertainty"] == pytest.approx(
            result.standard_uncertainty * result.coverage_factor
        )
        assert parsed["expandedUncertainty"] != pytest.approx(result.standard_uncertainty)

    def test_the_administrative_facts_come_back(self, document: str) -> None:
        """The duplicated fields are readable, which is what makes them checkable."""
        administrative = parse_dcc_administrative(document)
        assert administrative["uniqueIdentifier"] == "METAS-2026-0417"
        assert administrative["calibrationLaboratoryId"] == "did:web:metas.example"
        assert administrative["customerId"] == "did:web:callab.example"
        assert administrative["beginPerformanceDate"] == "2026-02-10"

    @pytest.mark.parametrize("broken", ["not xml at all", "<dcc:x/>", ""])
    def test_unreadable_documents_raise(self, broken: str) -> None:
        """A verifier meets these as untrusted input and must not half-believe them."""
        with pytest.raises(ValueError):
            parse_dcc_result(broken)


class TestCarried:
    """It travels inside the credential like every other representation."""

    def test_every_calibration_certificate_carries_one(self, world) -> None:
        """Both the institute and the laboratory issue one."""
        for name in ("metas-calibration", "callab-calibration", "metas-SR10K-0091"):
            assert _carried(world, name)["format"] == "PTB-DKD-DCC-XML"

    def test_it_is_digest_covered_like_the_others(self, world) -> None:
        """The signature reaches the document through the digest."""
        from vcqi.crypto.multibase import verify_digest_multibase

        carried = _carried(world, "metas-calibration")
        assert verify_digest_multibase(
            carried["content"].encode("utf-8"), carried["digestMultibase"]
        )

    def test_a_large_one_is_referenced_rather_than_inlined(self, world) -> None:
        """Both transport paths are exercised by the ordinary world.

        The laboratory certificate carries more input quantities, so its document goes
        over the inline threshold and is published separately.
        """
        assert "content" in _carried(world, "metas-calibration")
        assert "id" in _carried(world, "callab-calibration")


class TestVerification:
    """The two checks that make carrying it worth anything."""

    def _report(self, world, name):
        return verify_credential(
            world.credential(name),
            store=world.store,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
        )

    def test_all_carriers_agree_on_the_real_certificates(self, world) -> None:
        """Printed line, dependency representation and PTB/DKD DCC tell one story."""
        for name in ("metas-calibration", "callab-calibration"):
            step = _find(self._report(world, name), "uncertainty.agreement")
            assert step is not None and step.status == "pass"
            assert {child.id for child in step.children} >= {
                "uncertainty.agreement.dependencies",
                "uncertainty.agreement.dcc",
            }

    def test_the_duplicated_facts_agree(self, world) -> None:
        """Six facts said twice, and they match."""
        step = _find(self._report(world, "metas-calibration"), "uncertainty.duplication")
        assert step is not None and step.status == "pass"
        assert step.evidence["comparedFields"] == 6

    def test_the_duplication_check_is_skipped_without_a_dcc(self, world) -> None:
        """A certificate carrying one document cannot contradict itself.

        Searched at the top level only. A test report follows its traceability into a
        calibration certificate that *does* carry a PTB/DKD DCC, so a whole-tree search
        finds that one and answers a different question.
        """
        report = self._report(world, "testlab-report")
        uncertainty = next(step for step in report.steps if step.id == "uncertainty")
        duplication = [
            child
            for child in uncertainty.children
            if child.id == "uncertainty.duplication"
        ]
        assert duplication == [] or duplication[0].status == "skip"

    def test_every_certificate_still_verifies(self, world) -> None:
        """Adding a carrier broke nothing."""
        for name in ("metas-calibration", "callab-calibration", "cab-conformity"):
            assert self._report(world, name).outcome == "verified"


class TestFailureCases:
    """Two ways a certificate can contradict itself with every signature intact."""

    @pytest.mark.parametrize(
        "case",
        [case for case in TAMPER_CASES if case.key.startswith("dcc-")],
        ids=lambda case: case.key,
    )
    def test_caught_by_the_named_step(self, case) -> None:
        """The step that claims the case is the one that fails."""
        result = case.apply()
        report = verify_credential(
            result.credential,
            store=result.world.store,
            now=result.verify_at,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert report.outcome == "rejected"
        assert case.expected_step in [step.id for step in report.failures]

    @pytest.mark.parametrize(
        "case",
        [case for case in TAMPER_CASES if case.key.startswith("dcc-")],
        ids=lambda case: case.key,
    )
    def test_the_cryptography_is_untouched(self, case) -> None:
        """Signature, digests and standing all fine; only the contents disagree.

        Which is the argument for the checks existing at all. Nothing about signing a
        document keeps two copies of a fact inside it consistent.
        """
        result = case.apply()
        report = verify_credential(
            result.credential,
            store=result.world.store,
            now=result.verify_at,
            trusted_issuers=TRUST_ANCHORS,
        )
        generic = {step.id: step.status for step in report.steps}
        assert generic["proof"] == "pass"
        assert generic["validity"] == "pass"
        assert generic["recognition"] == "pass"

        representations = _find(report, "uncertainty.representations")
        digest_children = [
            child
            for child in representations.children
            if child.id.startswith("uncertainty.representations.")
        ]
        assert all(child.status == "pass" for child in digest_children)
