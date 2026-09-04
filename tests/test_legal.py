"""Tests for legal metrology: conformity decisions, and where legal force comes from.

Two claims are made good here. The first is arithmetic: the limits are the ones OIML
R 76 gives, and a decision either follows from the measurements or it does not. The
second is institutional and matters more: reaching a trust anchor establishes exactly one
thing, and a document can be impeccably recognised and still have no authority to do what
is being asked of it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vcqi.actors.registry import NOT_A_LEGAL_ANCHOR, TRUST_ANCHORS
from vcqi.actors.scenarios import DEMO_NOW, build_world
from vcqi.actors.tamper import TAMPER_CASES
from vcqi.domain.legal import (
    UNCERTAINTY_RATIO,
    TestPoint,
    designation_by_id,
    evaluate_conformity,
    maximum_permissible_error,
)
from vcqi.vc.recognition import discover_recognition
from vcqi.vc.resolver import Resolver
from vcqi.vc.verify import verify_credential
from vcqi.web.app import app

# The scale the demonstration verifies: class III, Max 15 kg, e = 5 g, so n = 3000.
E = 0.005


@pytest.fixture(scope="module")
def world():
    """Build the demonstration world once."""
    return build_world()


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Return a client bound to the application."""
    return TestClient(app)


def _report(world, name):
    """Verify one named credential as the inspector would."""
    return verify_credential(
        world.credential(name),
        store=world.store,
        now=DEMO_NOW,
        trusted_issuers=TRUST_ANCHORS,
    )


def _find(report, step_id):
    """Find a step anywhere in a report, however deeply nested."""

    def walk(steps):
        for step in steps:
            if step.id == step_id:
                return step
            found = walk(step.children)
            if found is not None:
                return found
        return None

    return walk(report.steps)


class TestMaximumPermissibleError:
    """The limits are the ones OIML R 76 gives, at every breakpoint."""

    @pytest.mark.parametrize(
        ("load", "expected_initial_grams"),
        [
            (0.5, 2.5),      # 100 e, first band
            (2.5, 2.5),      # 500 e, on the first boundary
            (2.505, 5.0),    # just past it, second band
            (10.0, 5.0),     # 2000 e, on the second boundary
            (10.005, 7.5),   # just past it, third band
            (15.0, 7.5),     # 3000 e, at capacity
        ],
    )
    def test_class_three_bands(self, load: float, expected_initial_grams: float) -> None:
        """The limit rises in half-interval steps at 500 e and 2000 e."""
        limit = maximum_permissible_error(
            load, scale_interval=E, accuracy_class="III", in_service=False
        )
        assert limit == pytest.approx(expected_initial_grams / 1000.0)

    def test_in_service_is_twice_initial(self) -> None:
        """An instrument in use is allowed twice the limit of initial verification.

        It is expected to drift within its verification interval and is not required to
        stay as good as the day it was made.
        """
        for load in (2.5, 5.0, 10.0, 15.0):
            initial = maximum_permissible_error(
                load, scale_interval=E, accuracy_class="III", in_service=False
            )
            in_service = maximum_permissible_error(
                load, scale_interval=E, accuracy_class="III", in_service=True
            )
            assert in_service == pytest.approx(2.0 * initial)

    def test_classes_differ_only_in_where_the_bands_fall(self) -> None:
        """A finer class holds the tighter limit out to a much higher load."""
        at_5kg = {
            name: maximum_permissible_error(
                5.0, scale_interval=E, accuracy_class=name, in_service=False
            )
            for name in ("I", "II", "III", "IIII")
        }
        assert at_5kg["II"] < at_5kg["III"] < at_5kg["IIII"]

    def test_unknown_class_is_rejected(self) -> None:
        """A class that does not exist is an error, not a default."""
        with pytest.raises(ValueError, match="unknown accuracy class"):
            maximum_permissible_error(5.0, scale_interval=E, accuracy_class="IX")

    def test_zero_scale_interval_is_rejected(self) -> None:
        """Every limit is a multiple of e, so e has to be a positive number."""
        with pytest.raises(ValueError, match="positive"):
            maximum_permissible_error(5.0, scale_interval=0.0)


class TestConformityDecision:
    """A recorded decision either follows from the measurements or it does not."""

    def _points(self, overrides=None):
        """Render the demonstration test points, optionally changing one."""
        points = [
            (2.5, 0.002, 0.0010),
            (5.0, 0.003, 0.0010),
            (10.0, -0.004, 0.0010),
            (15.0, 0.006, 0.0010),
        ]
        if overrides:
            points[overrides[0]] = overrides[1]
        return [
            TestPoint(load, error, uncertainty, 2.0, "kg").to_json(
                scale_interval=E, accuracy_class="III", in_service=True
            )
            for load, error, uncertainty in points
        ]

    def test_a_sound_verification_passes(self) -> None:
        """Every load inside its limit, measured well enough to say so."""
        verdict = evaluate_conformity(self._points(), decision="pass", scale_interval=E)
        assert verdict.decision_follows
        assert verdict.adequately_measured
        assert not verdict.failures

    def test_a_load_over_the_limit_makes_the_decision_wrong(self) -> None:
        """18 g at 15 kg against a limit of 15 g is a fail, whatever was written down."""
        verdict = evaluate_conformity(
            self._points((3, (15.0, 0.018, 0.0010))), decision="pass", scale_interval=E
        )
        assert not verdict.decision_follows
        assert verdict.implied_decision == "fail"
        assert [check.key for check in verdict.failures] == ["error"]

    def test_a_coarse_measurement_leaves_the_decision_unsupported(self) -> None:
        """The right verdict, and no way to stand behind it.

        This is the distinction the two properties exist to keep apart. The instrument
        does comply. The verification cannot demonstrate it, because at the lowest load
        the uncertainty is more than a third of the limit being judged against.
        """
        verdict = evaluate_conformity(
            self._points((0, (2.5, 0.002, 0.0020))), decision="pass", scale_interval=E
        )
        assert verdict.decision_follows
        assert not verdict.adequately_measured
        assert [check.key for check in verdict.failures] == ["uncertainty"]

    def test_the_limit_binds_hardest_at_the_bottom_of_the_range(self) -> None:
        """A uniform uncertainty fails at low load first, which is counter-intuitive.

        The limit grows with the load and the uncertainty of weighing often does not, so
        the demanding point is the light one. It is why a verification tests several
        loads instead of the heaviest.
        """
        at_lowest = maximum_permissible_error(2.5, scale_interval=E) / UNCERTAINTY_RATIO
        at_highest = maximum_permissible_error(15.0, scale_interval=E) / UNCERTAINTY_RATIO
        assert at_lowest < at_highest

        uncertainty = 0.0020
        assert uncertainty > at_lowest
        assert uncertainty < at_highest

    def test_a_misstated_limit_is_caught(self) -> None:
        """A certificate cannot quietly widen the limit it judges itself against."""
        points = self._points()
        points[3]["maximumPermissibleError"] = 0.030
        verdict = evaluate_conformity(points, decision="pass", scale_interval=E)
        assert "limit" in [check.key for check in verdict.failures]

    def test_an_unreadable_point_fails_rather_than_being_skipped(self) -> None:
        """A point that cannot be read is not a point that passed."""
        verdict = evaluate_conformity(
            [{"load": "heavy"}], decision="pass", scale_interval=E
        )
        assert not verdict.decision_follows


class TestDesignation:
    """Being designated is not the same as being designated for this."""

    def test_the_designation_covers_the_instrument(self) -> None:
        """Class III at 15 kg is inside a designation for class III up to 30 kg."""
        scope = designation_by_id("EV 042")
        assert scope is not None
        assert scope.covers("III", 15.0)

    def test_another_class_is_outside_it(self) -> None:
        """A finer class is a different competence, not a lesser case of the same one."""
        scope = designation_by_id("EV 042")
        assert scope is not None
        assert not scope.covers("II", 15.0)
        assert not scope.covers("III", 60.0)

    def test_it_is_expressed_as_methods_so_the_scope_check_can_read_it(self) -> None:
        """A designation reuses the shape an accreditation scope already has."""
        scope = designation_by_id("EV 042")
        assert scope is not None
        assert scope.to_json()["methods"]


class TestWhereAuthorityComesFrom:
    """Each anchor establishes one thing, and none of them establishes the others."""

    def test_the_type_approval_reaches_the_legislator(self, world) -> None:
        """Legal force comes from legislation and from nowhere else."""
        chain = discover_recognition(
            world.credential("type-approval"),
            resolver=Resolver(world.store),
            trusted_issuers=TRUST_ANCHORS,
            now=DEMO_NOW,
        )
        assert chain.succeeded
        assert chain.anchor == "did:web:legislator.example"

    def test_the_weight_calibration_reaches_the_bipm(self, world) -> None:
        """The same institute, a different document, a different anchor.

        This is the sharpest thing the demonstration says. METAS issues both credentials
        under one identifier, and the two chains have nothing in common: nothing the BIPM
        says can make an instrument lawful, and nothing the legislator says can make a
        measurement accurate.
        """
        chain = discover_recognition(
            world.credential("metas-weight-calibration"),
            resolver=Resolver(world.store),
            trusted_issuers=TRUST_ANCHORS,
            now=DEMO_NOW,
        )
        assert chain.succeeded
        assert chain.anchor == "did:web:bipm.example"

    def test_the_oiml_certificate_reaches_oiml_and_that_is_not_legal_force(self, world) -> None:
        """An OIML certificate is genuine, recognised, and confers nothing legally."""
        chain = discover_recognition(
            world.credential("oiml-certificate"),
            resolver=Resolver(world.store),
            trusted_issuers=TRUST_ANCHORS,
            now=DEMO_NOW,
        )
        assert chain.succeeded
        assert chain.anchor in NOT_A_LEGAL_ANCHOR
        assert _report(world, "oiml-certificate").outcome == "verified"

    def test_the_verification_reaches_the_legislator_through_the_authority(self, world) -> None:
        """A private body verifies; its permission to do so is public and traceable."""
        chain = discover_recognition(
            world.credential("verification-certificate"),
            resolver=Resolver(world.store),
            trusted_issuers=TRUST_ANCHORS,
            now=DEMO_NOW,
        )
        assert chain.succeeded
        assert [hop.issuer for hop in chain.hops] == [
            "did:web:verifybody.example",
            "did:web:metas.example",
        ]
        assert chain.anchor == "did:web:legislator.example"


class TestPipeline:
    """The conformity step, as a recipient runs it."""

    def test_every_legal_credential_verifies(self, world) -> None:
        """Nothing in the legal branch of the base world is broken."""
        for name in (
            "oiml-recognition",
            "legislator-recognition",
            "metas-designation",
            "metas-weight-calibration",
            "oiml-certificate",
            "type-approval",
            "verification-certificate",
        ):
            report = _report(world, name)
            assert report.outcome == "verified", (name, [s.detail for s in report.failures])

    def test_the_conformity_step_runs_on_a_verification(self, world) -> None:
        """All three conditions are evaluated and all three hold."""
        report = _report(world, "verification-certificate")
        step = _find(report, "conformity")
        assert step is not None and step.status == "pass"
        assert [child.id for child in step.children] == [
            "conformity.decision",
            "conformity.uncertainty",
            "conformity.legal-basis",
        ]

    def test_the_conformity_step_is_skipped_for_a_calibration(self, world) -> None:
        """A calibration certificate records no decision, so there is none to check."""
        step = _find(_report(world, "metas-calibration"), "conformity")
        assert step is not None and step.status == "skip"

    def test_the_verification_rests_on_a_calibrated_reference(self, world) -> None:
        """Legal metrology sits on top of the calibration chain, and it is checkable."""
        report = _report(world, "verification-certificate")
        chased = {fetch["url"] for fetch in report.fetches}
        assert "https://metas.example/certificates/METAS-2026-0512" in chased
        assert "https://bipm.example/kcdb/cmc/CH-M-0015" in chased


class TestLegalFailureCases:
    """The four things that can go wrong here, and nothing else catching them."""

    @pytest.mark.parametrize(
        "case",
        [case for case in TAMPER_CASES if case.group == "legal"],
        ids=lambda case: case.key,
    )
    def test_case_is_caught_by_its_expected_step(self, case) -> None:
        """The named step fails, and the certificate is rejected overall."""
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
        [case for case in TAMPER_CASES if case.group == "legal"],
        ids=lambda case: case.key,
    )
    def test_the_generic_checks_all_pass(self, case) -> None:
        """Every one of these survives the cryptography and the recognition chain.

        Which is the whole reason they are worth demonstrating: a system that verified
        signatures and stopped would accept all four.
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
        assert generic["status"] == "pass"
        assert generic["recognition"] == "pass"

    def test_an_oiml_certificate_cannot_be_a_legal_basis(self) -> None:
        """The document cited is real, current and recognised, and still will not do."""
        result = next(
            case for case in TAMPER_CASES if case.key == "oiml-is-not-approval"
        ).apply()
        report = verify_credential(
            result.credential,
            store=result.world.store,
            now=result.verify_at,
            trusted_issuers=TRUST_ANCHORS,
        )
        step = _find(report, "conformity.legal-basis")
        assert step is not None and step.status == "fail"
        assert "type-evaluation evidence" in step.detail


class TestApi:
    """The endpoint the chapter drives."""

    def test_conformity_endpoint_agrees_with_the_domain(self, client: TestClient) -> None:
        """The default verification passes and is supportable."""
        data = client.post("/api/conformity", json={}).json()
        assert data["decisionFollows"] and data["adequatelyMeasured"]
        assert data["uncertaintyRatio"] == UNCERTAINTY_RATIO
        assert [point["verdict"] for point in data["testPoints"]] == ["pass"] * 4

    def test_conformity_endpoint_separates_the_two_failures(self, client: TestClient) -> None:
        """Wrong and unsupported come back as different answers."""
        wrong = client.post(
            "/api/conformity", json={"test_points": [[15.0, 0.018, 0.001]]}
        ).json()
        assert not wrong["decisionFollows"] and wrong["adequatelyMeasured"]

        unsupported = client.post(
            "/api/conformity", json={"test_points": [[2.5, 0.002, 0.002]]}
        ).json()
        assert unsupported["decisionFollows"] and not unsupported["adequatelyMeasured"]

    def test_conformity_endpoint_rejects_an_unknown_class(self, client: TestClient) -> None:
        """An accuracy class that does not exist is a bad request."""
        assert client.post("/api/conformity", json={"accuracy_class": "IX"}).status_code == 400

    def test_the_graph_carries_branches_and_the_authority_edge(self, client: TestClient) -> None:
        """Legal authority is drawn as its own kind of edge, because it is one."""
        graph = client.get("/api/world").json()["graph"]
        assert graph["branches"] == ["metrology", "accreditation", "legal"]
        assert graph["notALegalAnchor"] == ["did:web:oiml.example"]

        authority = [edge for edge in graph["edges"] if edge["kind"] == "authority"]
        assert {edge["source"] for edge in authority} == {
            "did:web:legislator.example",
            "did:web:metas.example",
        }
        assert all("branch" in edge for edge in graph["edges"])

    def test_metas_appears_once_and_issues_across_two_branches(self, client: TestClient) -> None:
        """One organisation, one identifier, two roles, two chains."""
        graph = client.get("/api/world").json()["graph"]
        nodes = [node for node in graph["nodes"] if node["id"] == "did:web:metas.example"]
        assert len(nodes) == 1

        branches = {
            edge["branch"]
            for edge in graph["edges"]
            if edge["source"] == "did:web:metas.example"
        }
        assert {"metrology", "legal"} <= branches
