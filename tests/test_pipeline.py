"""Tests for recognition traversal and the full verification pipeline."""

from __future__ import annotations

import copy
from datetime import datetime, timezone

import pytest

from vcqi.actors.registry import TRUST_ANCHORS
from vcqi.actors.scenarios import BIPM_RECOGNITION, DEMO_NOW, build_world
from vcqi.actors.tamper import TAMPER_CASES, tamper_by_key
from vcqi.vc.recognition import discover_recognition
from vcqi.vc.resolver import Resolver
from vcqi.vc.verify import verify_credential

#: Every credential the base world issues, which
#: :meth:`TestWorld.test_every_credential_verifies` checks end to end. Status lists are
#: excluded: they are not issued *about* anything and have no chain to walk.
#:
#: Written out rather than derived, so that adding a credential is a deliberate act --
#: and checked against the world by the test below, so it cannot fall behind.
VERIFIED_CREDENTIALS = (
    "bipm-recognition",
    "global-aci-recognition",
    "sas-recognition",
    "metas-calibration",
    "callab-calibration",
    "metas-SR10K-0091",
    "metas-SR10K-0092",
    "metas-external-dcc",
    "testlab-report",
    "cab-conformity",
    "oiml-ia-recognition",
    "oiml-tl-recognition",
    "oiml-evaluation",
    "oiml-certificate",
)


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
        for name in VERIFIED_CREDENTIALS:
            report = _verify(world, name)
            assert report.outcome == "verified", (name, [s.detail for s in report.failures])

    def test_every_credential_in_the_world_is_verified(self, world) -> None:
        """VERIFIED_CREDENTIALS is written out, so it can fall behind the world.

        A credential nobody verifies is a credential that can rot unnoticed. This
        caught two: the shared check-standard pair had been in the world since the
        dependencies chapter and no test had ever run the pipeline over either of them.
        """
        actual = {name for name in world.credentials if not name.startswith("status-")}
        listed = set(VERIFIED_CREDENTIALS)
        assert not actual - listed, f"in the world, verified by nothing: {sorted(actual - listed)}"
        assert not listed - actual, f"listed but not in the world: {sorted(listed - actual)}"


class TestTheLegalMetrologyBranch:
    """OIML-CS, and the one thing it does that nothing else here does."""

    def test_the_certificate_reaches_two_anchors(self, world) -> None:
        """The claim the whole branch exists to make.

        An OIML certificate's recognition path runs upward to OIML. Its *evidence* path
        runs downward into the type evaluation, from there into the calibration of the
        equipment the evaluation used, and from there up a completely different chain to
        the BIPM and the accreditation anchor. Two roots of trust, one document, and the
        only thing the two paths share is the laboratory in the middle.
        """
        report = _verify(world, "oiml-certificate")
        assert report.outcome == "verified"

        recognition = next(step for step in report.steps if step.id == "recognition")
        assert "did:web:oiml.example" in recognition.detail

        hosts = {
            fetch["url"].split("/")[2]
            for fetch in report.fetches
            if str(fetch.get("url", "")).startswith("http")
        }
        assert "oiml.example" in hosts
        assert "bipm.example" in hosts, "the evidence path never reached the metrology anchor"
        assert "sas.example" in hosts, "the evidence path never reached the accreditation body"

    def test_the_evaluation_carries_traceability_into_the_test(self, world) -> None:
        """A type evaluation that cannot say what it measured with is not traceable."""
        report = _verify(world, "oiml-evaluation")
        step = next(step for step in report.steps if step.id == "traceability")
        assert step.status == "pass"
        assert "1 referenced document" in step.detail

    def test_the_certificate_says_it_authorises_nothing(self, world) -> None:
        """`legalEffect` is carried explicitly so a verifier can act on it.

        The OIML-CS produces evidence. Converting evidence into permission is a national
        act, and this demonstration does not model the authority that would perform it --
        so the certificate has to say so itself rather than leave a reader to know it.
        """
        certificate = world.credential("oiml-certificate")
        payload = certificate["credentialSubject"]["oimlCertificate"]
        assert payload["legalEffect"] == "none"
        assert "confers no legal permission" in payload["legalEffectNote"]

    def test_the_schema_requires_the_disclaimer(self, world) -> None:
        """A certificate that quietly drops it fails validation rather than reading as
        an approval."""
        schema = world.store.get("https://oiml.example/schemas/certificate-R-46.json")
        assert schema is not None
        certificate = schema["properties"]["credentialSubject"]["properties"][
            "oimlCertificate"
        ]
        assert "legalEffect" in certificate["required"]
        assert certificate["properties"]["legalEffect"] == {"const": "none"}

    def test_the_laboratory_is_recognised_twice_for_different_things(self, world) -> None:
        """One laboratory, one identifier, two arrangements, neither aware of the other."""
        accreditation = world.credential("sas-recognition")
        oiml = world.credential("oiml-tl-recognition")

        def actions(credential: dict) -> set[str]:
            subjects = credential["credentialSubject"]
            entries = subjects if isinstance(subjects, list) else [subjects]
            found: set[str] = set()
            for entry in entries:
                if entry.get("id") != "did:web:testlab.example":
                    continue
                for action in entry.get("recognizedTo", []):
                    found.add(action["action"])
            return found

        assert actions(accreditation) == {"issue"}
        assert actions(oiml) == {"evaluate"}

    def test_the_recognition_predates_the_certificate(self, world) -> None:
        """The legal layer has its own timeline, and it has to.

        OIML has run its certification system for decades. Dating its recognitions from
        2026 alongside Global ACI made the action check reject a certificate issued in
        2024 -- correctly, since the recognition did not yet exist. This is the
        assertion that keeps the two timelines apart.
        """
        recognition = world.credential("oiml-ia-recognition")
        certificate = world.credential("oiml-certificate")
        assert recognition["validFrom"] < certificate["validFrom"]


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
        """A laboratory reaches Global ACI through its accreditation body."""
        chain = discover_recognition(
            world.credential("callab-calibration"),
            resolver=Resolver(world.store),
            trusted_issuers=TRUST_ANCHORS,
            now=DEMO_NOW,
        )
        assert chain.succeeded
        assert chain.anchor == "did:web:global-aci.example"
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
                world.credential("global-aci-recognition"),
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


class TestObjectIdentity:
    """The chain is about physical objects, and following it does not establish that.

    Every other traceability check is a property of the documents: the reference resolves,
    the digest matches, the parent verifies, the uncertainty reconciles. None of them
    notices a laboratory referencing a genuine certificate about a standard it never had.
    """

    def _identity_steps(self, report):
        """Collect every object-identity step in a report.

        Args:
            report: The verification report.

        Returns:
            The steps, outermost first.
        """
        found = []

        def walk(steps):
            for step in steps:
                if step.id == "traceability.object-identity":
                    found.append(step)
                walk(step.children)

        walk(report.steps)
        return found

    def test_the_real_chain_names_the_object_it_used(self, world) -> None:
        """The laboratory's transfer standard is the standard the institute calibrated."""
        steps = self._identity_steps(_verify(world, "callab-calibration"))
        assert [step.status for step in steps] == ["pass"]
        assert "SR10K-0042" in steps[0].detail

    def test_a_reference_naming_no_object_skips(self, world) -> None:
        """Skipped, not passed.

        The test report's equipment reference carries no instrument, so nothing was
        established. Reporting that as a pass would claim a check ran when it did not,
        which is the distinction the whole report is built on.
        """
        steps = self._identity_steps(_verify(world, "testlab-report"))
        assert any(step.status == "skip" for step in steps)
        assert all(step.status in ("pass", "skip") for step in steps)

    def test_naming_a_different_object_is_caught(self, world) -> None:
        """And is caught by nothing else, which is why the check was added.

        The tampered certificate references the institute's real, unaltered certificate
        and names a different resistor. Proof, recognition, status, the digest of the
        reference and the inherited uncertainty all still pass.
        """
        result = tamper_by_key("traceability-names-another-object").apply()
        report = verify_credential(
            result.credential,
            store=result.world.store,
            now=result.verify_at,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert report.outcome == "rejected"

        failed = {step.id for step in report.failures}
        assert "traceability.object-identity" in failed

        intact = {step.id: step.status for step in report.steps}
        for step_id in ("proof", "validity", "status", "recognition", "scope", "uncertainty"):
            assert intact[step_id] == "pass", step_id

    def test_the_inherited_uncertainty_still_reconciles(self, world) -> None:
        """The sharpest part: the arithmetic is untouched.

        A reader could reasonably expect a wrong parent to show up in the numbers. It
        does not, because the numbers were copied from the certificate that really was
        referenced. Only the object is wrong, and only the object check sees it.
        """
        result = tamper_by_key("traceability-names-another-object").apply()
        report = verify_credential(
            result.credential,
            store=result.world.store,
            now=result.verify_at,
            trusted_issuers=TRUST_ANCHORS,
        )

        def find(steps, step_id):
            for step in steps:
                if step.id == step_id:
                    return step
                found = find(step.children, step_id)
                if found:
                    return found
            return None

        assert find(report.steps, "traceability.inherited").status == "pass"
        assert find(report.steps, "traceability.shared-inputs").status == "pass"
