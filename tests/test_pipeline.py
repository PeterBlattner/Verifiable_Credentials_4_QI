"""Tests for recognition traversal and the full verification pipeline."""

from __future__ import annotations

import copy
from datetime import datetime, timezone

import pytest

from vcqi.actors.registry import TRUST_ANCHORS
from vcqi.actors.scenarios import BIPM_RECOGNITION, DEMO_NOW, build_world
from vcqi.actors.tamper import TAMPER_CASES
from vcqi.vc.recognition import discover_recognition
from vcqi.vc.resolver import Resolver
from vcqi.vc.verify import verify_credential


@pytest.fixture(scope="module")
def world():
    """Build the demonstration world once for the whole module."""
    return build_world()


def _verify(world, name, **kwargs):
    """Verify one named credential from the world.

    Args:
        world: The demonstration world.
        name: Short name of the credential.
        **kwargs: Overrides passed through to the pipeline.

    Returns:
        The verification report.
    """
    options = {
        "store": world.store,
        "now": DEMO_NOW,
        "trusted_issuers": TRUST_ANCHORS,
    }
    options.update(kwargs)
    return verify_credential(world.credential(name), **options)


class TestWorld:
    """The scenario itself holds together."""

    def test_build_is_deterministic(self) -> None:
        """Two builds produce byte-identical credentials."""
        first, second = build_world(), build_world()
        assert first.credentials == second.credentials

    def test_every_credential_verifies(self, world) -> None:
        """Nothing in the base world is broken."""
        for name in (
            "bipm-recognition",
            "ilac-recognition",
            "sas-recognition",
            "metas-calibration",
            "callab-calibration",
            "testlab-report",
            "cab-conformity",
        ):
            report = _verify(world, name)
            assert report.outcome == "verified", (name, [s.detail for s in report.failures])


class TestRecognition:
    """Traversal reaches an anchor, and stops safely when it cannot."""

    def test_institute_reaches_the_metrology_anchor_in_one_hop(self, world) -> None:
        """A national institute is recognised directly by the BIPM."""
        chain = discover_recognition(
            world.credential("metas-calibration"),
            resolver=Resolver(world.store),
            trusted_issuers=TRUST_ANCHORS,
            now=DEMO_NOW,
        )
        assert chain.succeeded
        assert chain.anchor == "did:web:bipm.example"
        assert len(chain.hops) == 1

    def test_laboratory_reaches_the_accreditation_anchor_in_two_hops(self, world) -> None:
        """A laboratory reaches ILAC through its accreditation body."""
        chain = discover_recognition(
            world.credential("callab-calibration"),
            resolver=Resolver(world.store),
            trusted_issuers=TRUST_ANCHORS,
            now=DEMO_NOW,
        )
        assert chain.succeeded
        assert chain.anchor == "did:web:ilac.example"
        assert [hop.issuer for hop in chain.hops] == [
            "did:web:callab.example",
            "did:web:sas.example",
        ]

    def test_anchor_needs_no_hops(self, world) -> None:
        """A credential issued by a trust anchor is recognised immediately."""
        chain = discover_recognition(
            world.credential("bipm-recognition"),
            resolver=Resolver(world.store),
            trusted_issuers=TRUST_ANCHORS,
            now=DEMO_NOW,
        )
        assert chain.succeeded and not chain.hops

    def test_depth_limit_stops_traversal(self, world) -> None:
        """A verifier unwilling to follow any hop refuses rather than looping."""
        chain = discover_recognition(
            world.credential("callab-calibration"),
            resolver=Resolver(world.store),
            trusted_issuers=TRUST_ANCHORS,
            now=DEMO_NOW,
            max_depth=1,
        )
        assert not chain.succeeded
        assert "gave up" in (chain.error or "")

    def test_pointer_to_a_credential_that_does_not_list_the_issuer_fails(self, world) -> None:
        """Pointing at a recognition credential is not the same as appearing in it."""
        credential = copy.deepcopy(world.credential("callab-calibration"))
        credential["issuer"]["recognizedIn"]["id"] = BIPM_RECOGNITION
        chain = discover_recognition(
            credential,
            resolver=Resolver(world.store),
            trusted_issuers=TRUST_ANCHORS,
            now=DEMO_NOW,
        )
        assert not chain.succeeded
        assert "does not appear" in (chain.error or "")

    def test_identifier_based_discovery_is_used_when_no_pointer_exists(self, world) -> None:
        """An issuer with no pointer can still be placed through its whois service."""
        credential = copy.deepcopy(world.credential("metas-calibration"))
        credential["issuer"].pop("recognizedIn")
        chain = discover_recognition(
            credential,
            resolver=Resolver(world.store),
            trusted_issuers=TRUST_ANCHORS,
            now=DEMO_NOW,
        )
        assert chain.succeeded
        assert chain.hops[0].discovery == "identifier"

    def test_unreachable_issuer_fails_cleanly(self, world) -> None:
        """An issuer that resolves to nothing produces an error, not an exception."""
        credential = copy.deepcopy(world.credential("metas-calibration"))
        credential["issuer"] = {"id": "did:web:nowhere.example", "type": "RecognizedIssuer"}
        chain = discover_recognition(
            credential,
            resolver=Resolver(world.store),
            trusted_issuers=TRUST_ANCHORS,
            now=DEMO_NOW,
        )
        assert not chain.succeeded and chain.error


class TestPipeline:
    """The steps a recipient runs, and what each of them decides."""

    def test_report_records_every_step(self, world) -> None:
        """A calibration certificate exercises the whole pipeline."""
        report = _verify(world, "metas-calibration")
        assert [step.id for step in report.steps] == [
            "shape",
            "proof",
            "validity",
            "status",
            "recognition",
            "action",
            "output-validation",
            "scope",
            "mra-logo",
            "uncertainty",
            "traceability",
        ]

    def test_mra_logo_is_justified_for_the_institute(self, world) -> None:
        """The institute's certificate is inside its CMC, so the logo is legitimate."""
        report = _verify(world, "metas-calibration")
        step = next(step for step in report.steps if step.id == "mra-logo")
        assert step.status == "pass"

    def test_laboratory_makes_no_mra_claim(self, world) -> None:
        """An accredited laboratory carries its accreditation symbol, not the logo."""
        report = _verify(world, "callab-calibration")
        step = next(step for step in report.steps if step.id == "mra-logo")
        assert step.status == "pass"
        assert "does not claim" in step.detail

    def test_conformity_certificate_reaches_the_institute(self, world) -> None:
        """The Product Conformity case resolves all the way down to the SI.

        This is the whole demonstration in one assertion: an authority that trusts only
        two international bodies, meeting a certificate from an organisation it has
        never dealt with, ends up with a verified path to a national measurement
        standard.
        """
        report = _verify(world, "cab-conformity")
        assert report.outcome == "verified"
        chased = {fetch["url"] for fetch in report.fetches}
        assert "https://metas.example/certificates/METAS-2026-0417" in chased
        assert "https://bipm.example/kcdb/cmc/CH-EM-0042" in chased

    def test_presented_documents_avoid_retrieval(self, world) -> None:
        """Bundling upstream credentials with the presentation saves round trips."""
        without = _verify(world, "callab-calibration")
        with_staple = _verify(
            world,
            "callab-calibration",
            presented=[
                world.credential("sas-recognition"),
                world.credential("ilac-recognition"),
                world.credential("bipm-recognition"),
            ],
        )
        assert with_staple.outcome == "verified"
        presented = [f for f in with_staple.fetches if f["source"] == "presented"]
        assert presented
        assert len(with_staple.fetches) == len(without.fetches)

    def test_verification_time_is_respected(self, world) -> None:
        """Verifying before a credential exists rejects it."""
        report = _verify(world, "metas-calibration", now=datetime(2025, 1, 1, tzinfo=timezone.utc))
        assert report.outcome == "rejected"
        assert [step.id for step in report.failures][0] == "validity"

    def test_trusting_nobody_rejects_everything(self, world) -> None:
        """Recognition is what carries the trust, not the signature."""
        report = _verify(world, "metas-calibration", trusted_issuers=frozenset())
        assert report.outcome == "rejected"
        assert "recognition" in [step.id for step in report.failures]

    def test_key_of_one_actor_cannot_sign_for_another(self, world) -> None:
        """A proof made with someone else's key is refused before the arithmetic."""
        credential = copy.deepcopy(world.credential("metas-calibration"))
        credential["proof"]["verificationMethod"] = "did:web:callab.example#issuance-key-1"
        report = verify_credential(
            credential, store=world.store, now=DEMO_NOW, trusted_issuers=TRUST_ANCHORS
        )
        step = next(step for step in report.steps if step.id == "proof")
        assert step.status == "fail"
        assert "controlled by" in step.detail


class TestTamperCases:
    """Every failure the demonstration can produce is caught by the intended step."""

    @pytest.mark.parametrize("case", TAMPER_CASES, ids=lambda case: case.key)
    def test_case_is_caught_by_its_expected_step(self, case) -> None:
        """The named step fails, and the credential is rejected overall."""
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
        [case for case in TAMPER_CASES if case.group == "metrological"],
        ids=lambda case: case.key,
    )
    def test_metrological_cases_survive_the_generic_checks(self, case) -> None:
        """The signature, validity and status of a metrological failure all pass.

        This is what makes these cases worth demonstrating: a system that checked only
        the cryptography would accept every one of them.
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

    def test_every_case_has_a_distinct_key(self) -> None:
        """Keys address cases from the interface, so they have to be unique."""
        keys = [case.key for case in TAMPER_CASES]
        assert len(set(keys)) == len(keys)
