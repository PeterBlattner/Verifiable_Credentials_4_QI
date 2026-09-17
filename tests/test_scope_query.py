"""Tests for a scope that answers questions instead of publishing its table.

Three groups.

The first is the rule itself: what a register replies, and why. A flexible row answers
for designations it does not list, which is the reason the endpoint has to exist at all,
and an answer that could not say how it was derived would be worth nothing.

The second is the question. Putting the date inside it is what separates *was this
laboratory accredited when it tested* from *is it accredited now*, and the counterfactual
here is the evidence: the same question asked about today is answered honestly, and
answered about the wrong day.

The third is the security of asking. An endpoint moves a check from reading a document to
trusting a reply, and three things make up the difference: the register that answers is
the one the scope names, the answer is signed by the body that granted the scope, and the
question echoed in the answer is the question that was asked. The last is the one that is
easy to leave out and is exactly the substituted-document forgery in a new costume.
"""

from __future__ import annotations

import copy

from vcqi.actors.registry import TRUST_ANCHORS, actor_key
from vcqi.actors.scenarios import DEMO_NOW, build_world
from vcqi.actors.tamper import tamper_by_key
from vcqi.domain.accreditation import QUERY_PROTOCOL, scope_by_id
from vcqi.crypto.dataintegrity import sign_document
from vcqi.domain.scope_query import CoverageQuestion, answer_coverage
from vcqi.vc.verify import verify_credential

TESTED_ON = "2026-05-06"
ENDPOINT = "https://sas.example/accreditation/STS-0456/covers"


def _rows():
    """Return the published rows of the testing scope.

    Returns:
        The rows, in register order.
    """
    scope = scope_by_id("STS 0456")
    assert scope is not None
    return scope.test_rows


class TestWhatTheRegisterAnswers:
    """The rule a register applies, and the grounds it gives."""

    def test_a_listed_designation_is_covered(self) -> None:
        """The ordinary case, and the only one a document could have handled."""
        answer = answer_coverage(_rows(), CoverageQuestion("EN 60598-1:2015", TESTED_ON))
        assert answer.covered
        assert "is listed in" in answer.reason

    def test_an_equivalent_designation_is_covered(self) -> None:
        """A register writes ``EN 60335-1, IEC 60335-1`` because they are one test.

        A report naming either is inside the row, and a verifier comparing strings
        without the register's own list of equivalents would refuse half of them.
        """
        answer = answer_coverage(_rows(), CoverageQuestion("IEC 60335-1:2010", TESTED_ON))
        assert answer.covered

    def test_a_flexible_row_covers_what_it_does_not_list(self) -> None:
        """The reason the endpoint exists rather than a document.

        A Type B row covers editions its scope was granted before. No frozen list can
        say that, so the answer has to be derived -- and derived by the body that granted
        the scope, because nobody else is entitled to apply the rule.
        """
        answer = answer_coverage(_rows(), CoverageQuestion("IEC 60335-1", TESTED_ON))
        assert answer.covered
        assert answer.flexibility == "B"
        assert "flexible scope of application" in answer.reason

    def test_a_fixed_row_covers_only_what_it_lists(self) -> None:
        """Type A is fixed, and the refusal says which row refused and why."""
        answer = answer_coverage(_rows(), CoverageQuestion("IEC 60598-1", TESTED_ON))
        assert not answer.covered
        assert "fixed scope of application" in answer.reason

    def test_a_row_not_yet_added_does_not_answer(self) -> None:
        """A scope is a fact with a date on it."""
        assert not answer_coverage(
            _rows(), CoverageQuestion("IEC 62368-1", TESTED_ON)
        ).covered

    def test_a_withdrawn_row_stops_answering(self) -> None:
        """Superseded standards leave a scope, and leaving is dated too."""
        before = answer_coverage(
            _rows(), CoverageQuestion("IEC 60950-1:2005", "2025-06-01")
        )
        after = answer_coverage(
            _rows(), CoverageQuestion("IEC 60950-1:2005", "2026-06-01")
        )
        assert before.covered and not after.covered

    def test_every_answer_gives_grounds(self) -> None:
        """Covered or not, an answer that cannot say why is not evidence."""
        for standard in ("IEC 60335-1", "IEC 62368-1", "ISO 9001"):
            answer = answer_coverage(_rows(), CoverageQuestion(standard, TESTED_ON))
            assert answer.reason.strip()


class TestTheQuestionCarriesItsDate:
    """Asking about now answers a different question from asking about then."""

    def test_the_same_question_about_today_is_answered_differently(self) -> None:
        """The counterfactual behind the break-it case, asserted rather than described.

        This is the whole argument for the ``at`` parameter. The register is honest in
        both directions; what differs is which day was asked about, and a verifier that
        omits the date gets a true answer to a question nobody needed.
        """
        rows = _rows()
        when_tested = answer_coverage(rows, CoverageQuestion("IEC 62368-1", TESTED_ON))
        today = answer_coverage(
            rows, CoverageQuestion("IEC 62368-1", DEMO_NOW.strftime("%Y-%m-%d"))
        )
        assert not when_tested.covered
        assert today.covered, "the counterfactual has stopped being a counterfactual"

    def test_one_question_has_exactly_one_address(self) -> None:
        """What makes an answer addressable, and therefore portable.

        Parameters are sorted and percent-encoded, so two verifiers asking the same
        thing compose the same address and a stapled answer is found by the verifier
        that wants it.
        """
        question = CoverageQuestion("IEC 60335-1", TESTED_ON)
        assert question.to_query() == "at=2026-05-06&standard=IEC%2060335-1"
        assert question.address(ENDPOINT) == f"{ENDPOINT}?{question.to_query()}"

    def test_the_address_distinguishes_the_dates(self) -> None:
        """Two dates are two questions, and so two documents."""
        first = CoverageQuestion("IEC 60335-1", "2026-05-06").address(ENDPOINT)
        second = CoverageQuestion("IEC 60335-1", "2026-09-04").address(ENDPOINT)
        assert first != second


class TestAskingIsCheckedLikeReading:
    """What makes a reply as good as a document, and what it costs to leave out."""

    def test_the_endpoint_answers_and_signs(self) -> None:
        """The reply is a credential, not a JSON blob authenticated by a connection."""
        world = build_world()
        address = CoverageQuestion("IEC 60335-1", TESTED_ON).address(ENDPOINT)
        answer = world.store.answer(address)

        assert answer is not None
        assert "proof" in answer
        assert answer["id"] == address
        assert world.store.kind_of(address) == "query-answer"
        assert answer["credentialSubject"]["protocol"] == QUERY_PROTOCOL

    def test_a_malformed_question_is_refused_rather_than_guessed(self) -> None:
        """A register that answers a question it did not understand is worse than none."""
        world = build_world()
        assert world.store.answer(f"{ENDPOINT}?standard=IEC%2060335-1") is None
        assert world.store.answer(ENDPOINT) is None

    def test_the_scope_check_passes_through_the_endpoint(self) -> None:
        """The whole path, end to end, on the real report."""
        world = build_world()
        report = verify_credential(
            world.credentials["testlab-report"],
            store=world.store,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert report.outcome == "verified"

        scope = next(step for step in report.steps if step.id == "scope")
        assert [child.id for child in scope.children] == [
            "scope.source",
            "scope.query",
            "scope.answer",
            "scope.covered",
        ]

    def test_a_stapled_answer_is_filed_under_its_own_question(self) -> None:
        """A holder cannot put an answer where it did not come from.

        This is why the question belongs in the address rather than only inside the
        document. A holder carrying the register's genuine, correctly signed answer
        about a *different* standard has something entirely true and entirely useless:
        it is indexed by the question it answers, the verifier asks for another, and the
        two never meet. No check had to fire for that, which is the good kind of
        defence.
        """
        world = build_world()
        asked = CoverageQuestion("IEC 60335-1", TESTED_ON).address(ENDPOINT)
        other = world.store.answer(
            CoverageQuestion("EN 60598-1:2015", TESTED_ON).address(ENDPOINT)
        )
        assert other is not None and other["credentialSubject"]["answer"]["covered"]

        report = verify_credential(
            world.credentials["testlab-report"],
            store=world.store,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
            presented=[other],
        )
        assert report.outcome == "verified"

        record = next(entry for entry in report.fetches if entry["url"] == asked)
        assert record["source"] == "retrieved", (
            "an answer to another question was accepted for this one"
        )

    def test_a_register_answering_something_else_is_caught(self) -> None:
        """The echoed question is checked, and not taken on trust.

        Addressing keeps a *holder* honest. It cannot keep the register honest: a
        misbehaving or simply buggy endpoint can sign an answer whose question does not
        match the address it was served at, and everything else about that document --
        signature, issuer, standing -- is impeccable. So the verifier compares the
        question it asked against the question the answer says it answered.
        """
        world = build_world()
        asked = CoverageQuestion("IEC 60335-1", TESTED_ON).address(ENDPOINT)
        other = world.store.answer(
            CoverageQuestion("EN 60598-1:2015", TESTED_ON).address(ENDPOINT)
        )
        assert other is not None

        mismatched = copy.deepcopy(other)
        mismatched["id"] = asked
        mismatched.pop("proof")
        mismatched, _ = sign_document(
            mismatched, actor_key("did:web:sas.example"), created=DEMO_NOW
        )
        world.store.publish_endpoint(ENDPOINT, lambda _query: mismatched, "query-answer")

        report = verify_credential(
            world.credentials["testlab-report"],
            store=world.store,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert report.outcome == "rejected"
        assert "scope.answer" in [step.id for step in report.failures]

    def test_an_answer_signed_by_anyone_else_is_refused(self) -> None:
        """The second of the three protections this module's docstring names.

        Controlling the address is not the only way to answer for yourself. A laboratory
        that reached the register's own endpoint -- by compromise, by a misdirected name,
        or because it operates the host -- could serve a reply that is a perfectly valid
        credential: signed with a real key, by an issuer whose DID document authorises
        that key, echoing exactly the question that was asked, at exactly the address it
        was asked at. Every other check in this group passes on it.

        What it cannot do is be the body that granted the scope, and the scope says which
        body that is. This check had no test until the guard around it was found to be
        satisfied by any value at all.
        """
        world = build_world()
        asked = CoverageQuestion("IEC 60335-1", TESTED_ON).address(ENDPOINT)
        genuine = world.store.answer(asked)
        assert genuine is not None

        forged = copy.deepcopy(genuine)
        forged["issuer"] = {
            "id": "did:web:testlab.example",
            "type": "RecognizedIssuer",
            "name": "Helvetia Testing Services GmbH (demonstration)",
        }
        forged.pop("proof")
        forged, _ = sign_document(
            forged, actor_key("did:web:testlab.example"), created=DEMO_NOW
        )
        world.store.publish_endpoint(ENDPOINT, lambda _query: forged, "query-answer")

        outcome = verify_credential(
            world.credentials["testlab-report"],
            store=world.store,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert outcome.outcome == "rejected"
        answer = next(step for step in outcome.failures if step.id == "scope.answer")
        assert "was granted by did:web:sas.example" in answer.detail
        assert "signed by did:web:testlab.example" in answer.detail

    def test_the_laboratory_cannot_choose_who_answers(self) -> None:
        """The endpoint comes from the scope document, not from the certificate.

        A laboratory that could name the endpoint could answer for itself, which is the
        same forgery as stating its own scope.
        """
        world = build_world()
        report = copy.deepcopy(world.credentials["testlab-report"])
        report["credentialSubject"]["testing"]["capabilityReference"]["queryEndpoint"] = (
            "https://testlab.example/our-own-scope/covers"
        )

        outcome = verify_credential(
            report,
            store=world.store,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert "scope.query" in [step.id for step in outcome.failures]

    def test_the_break_it_case_is_caught_where_it_says(self) -> None:
        """Kept beside the rule it exercises, as well as in the tamper suite."""
        case = tamper_by_key("tested-before-accredited")
        assert case is not None
        result = case.apply()
        outcome = verify_credential(
            result.credential,
            store=result.world.store,
            now=result.verify_at,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert outcome.outcome == "rejected"
        assert "scope.covered" in [step.id for step in outcome.failures]
