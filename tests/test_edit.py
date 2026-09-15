"""Tests for the document a reader breaks by hand.

Chapter 8 offers a catalogue of fields and, under each one, a sentence saying which check
is supposed to notice when it moves. That sentence is a claim about the pipeline, and a
claim in prose beside a pipeline that changes is the thing this repository keeps writing
tests against. So the substantial test here is parametrised over the whole catalogue: it
runs every field through a real verification and asserts that the check named is among the
ones that actually failed -- and, for the three fields that are on offer precisely because
nothing catches them, that nothing does.

The shape is taken from ``tests/test_pipeline.py``, which does the same for the tamper
cases. The difference is that a tamper case builds its own world and this does not: the
edit routes verify a copy against the shared world, so a test that leaked a change into it
would break every test after it. One of the cases below checks that it does not.
"""

from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from vcqi.actors.edit import (
    EDITABLE_DOCUMENTS,
    EDITABLE_FIELDS,
    apply_edits,
    coerce,
    fields_for,
    read_path,
    write_path,
)
from vcqi.actors.registry import TRUST_ANCHORS, actor_key
from vcqi.actors.scenarios import DEMO_NOW, build_world
from vcqi.crypto.dataintegrity import sign_document
from vcqi.vc.checks import issuer_id
from vcqi.vc.verify import verify_credential
from vcqi.web.app import app

#: A value that ought to break each field, one per entry of the catalogue.
#:
#: Written out rather than generated, because "a plausible thing a reader would type" is a
#: judgement and generating it would only move the judgement into a helper. A field that
#: gains an entry in the catalogue and not here fails the completeness test below.
PROBES: dict[tuple[str, str], object] = {
    ("metas-calibration", "value"): 1.0e6,
    ("metas-calibration", "expanded-uncertainty"): 5.0e-4,
    ("metas-calibration", "coverage-factor"): 1.0,
    ("metas-calibration", "valid-until"): "2026-03-01",
    ("metas-calibration", "mra-logo"): False,
    ("metas-calibration", "issuer"): "did:web:testlab.example",
    ("callab-calibration", "value"): 10500.0,
    ("callab-calibration", "expanded-uncertainty"): 0.03,
    ("callab-calibration", "mra-logo"): True,
    ("callab-calibration", "frequency"): 10.0,
    ("callab-calibration", "traced-object"): (
        "urn:instrument:callab:standard-resistor:SR10K-0091"
    ),
    ("callab-calibration", "traced-digest"): "uEiDyOxhXZS2-SW5cYMEPruSsLdNLSzUQ9uebFLnSTcDLtQ",
    ("callab-calibration", "valid-until"): "2026-04-01",
    ("callab-calibration", "issuer"): "did:web:testlab.example",
    ("testlab-report", "standard"): "IEC 62368-1",
    ("testlab-report", "performed-on"): "2020-01-15",
    ("testlab-report", "scope-digest"): "uEiCE2CKRbizjkPpPmHi5m6dDTPHr9CPhkVlaN96SzrM_1A",
    ("testlab-report", "equipment-digest"): "uEiCogT1BJJ2ar4pJ3sg5vCwWyIkLJIWR8TPJOi6pATkfPQ",
    ("testlab-report", "equipment-object"): "urn:instrument:testlab:multimeter:DMM-9999",
    ("testlab-report", "issuer"): "did:web:callab.example",
    ("cab-conformity", "standard"): "IEC 62368-1",
    ("cab-conformity", "report-digest"): "uEiCogT1BJJ2ar4pJ3sg5vCwWyIkLJIWR8TPJOi6pATkfPQ",
    ("cab-conformity", "statement"): "The product is wonderful.",
    ("cab-conformity", "valid-until"): "2026-07-01",
    ("cab-conformity", "issuer"): "did:web:testlab.example",
    ("oiml-certificate", "legal-effect"): "national",
    ("oiml-certificate", "standard"): "OIML R 49:2013",
    ("oiml-certificate", "report-digest"): "uEiCogT1BJJ2ar4pJ3sg5vCwWyIkLJIWR8TPJOi6pATkfPQ",
    ("oiml-certificate", "range-maximum"): 9.0,
    ("oiml-certificate", "valid-until"): "2026-07-01",
    ("oiml-certificate", "issuer"): "did:web:testlab.example",
}


@pytest.fixture(scope="module")
def world():
    """Return a world of this module's own, so nothing here can disturb another test."""
    return build_world()


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Return a client bound to the application."""
    return TestClient(app)


def _verify(world, document: str, edits: dict[str, object]) -> list[str]:
    """Apply edits, sign as the issuer named, verify, and report what failed.

    Args:
        world: The world to verify against.
        document: Short name of the credential to start from.
        edits: Submitted values, keyed by field identifier.

    Returns:
        The identifiers of every step that failed, in report order.
    """
    credential = copy.deepcopy(world.credential(document))
    apply_edits(credential, edits, document=document)
    signed, _ = sign_document(
        credential, actor_key(issuer_id(credential)), created=DEMO_NOW
    )
    report = verify_credential(
        signed, store=world.store, now=DEMO_NOW, trusted_issuers=TRUST_ANCHORS
    )
    return [step.id for step in report.failures]


class TestTheCatalogue:
    """The fields on offer, and whether they still do what they say."""

    def test_every_field_has_a_probe(self) -> None:
        """A field added to the catalogue is a field this module has to exercise."""
        catalogue = {(field.document, field.key) for field in EDITABLE_FIELDS}
        assert catalogue == set(PROBES), (
            f"no probe for {sorted(catalogue - set(PROBES))}, "
            f"probe for nothing: {sorted(set(PROBES) - catalogue)}"
        )

    def test_keys_are_unique_within_a_document(self) -> None:
        """Fields are addressed by key, so two of a name would make one unreachable."""
        for document in EDITABLE_DOCUMENTS:
            keys = [field.key for field in fields_for(document)]
            assert len(keys) == len(set(keys)), f"{document} has a repeated field key"

    def test_every_path_resolves_in_its_document(self, world) -> None:
        """The catalogue is a set of claims about documents it does not contain."""
        for field in EDITABLE_FIELDS:
            credential = world.credential(field.document)
            # Raises rather than returning a sentinel, which is what makes this a test of
            # the path and not of a default.
            read_path(credential, field.path)

    def test_a_choice_field_offers_the_value_the_document_carries(self, world) -> None:
        """A select whose pristine value is not among its options cannot be put back."""
        for field in EDITABLE_FIELDS:
            if field.kind != "choice":
                continue
            pristine = read_path(world.credential(field.document), field.path)
            assert pristine in field.choices, (
                f"{field.document}/{field.key} carries {pristine!r}, "
                f"which is not one of {field.choices}"
            )

    def test_every_document_verifies_before_it_is_touched(self, world) -> None:
        """The baseline the chapter opens on, and the one Put it back returns to."""
        for document in EDITABLE_DOCUMENTS:
            assert _verify(world, document, {}) == []

    @pytest.mark.parametrize(
        "field", EDITABLE_FIELDS, ids=lambda f: f"{f.document}/{f.key}"
    )
    def test_the_field_reaches_the_check_it_names(self, world, field) -> None:
        """Each field's note claims a check notices it. This is that claim, run.

        The three fields with no expected step are the interesting half: they are on offer
        because nothing catches them, and if something started to, the prose under them
        would be wrong in the direction that matters.
        """
        failures = _verify(world, field.document, {field.key: PROBES[(field.document, field.key)]})
        if field.expected_step is None:
            assert failures == [], (
                f"{field.document}/{field.key} is documented as reaching no check, "
                f"and it now fails {failures}"
            )
        else:
            assert field.expected_step in failures, (
                f"{field.document}/{field.key} claims {field.expected_step}, "
                f"and what failed was {failures}"
            )


class TestApplyingEdits:
    """Reading and writing by path, and what is refused."""

    def test_a_value_equal_to_the_pristine_one_is_not_a_change(self, world) -> None:
        """A reader who types the number back has not edited anything."""
        credential = copy.deepcopy(world.credential("metas-calibration"))
        pristine = read_path(credential, "credentialSubject.calibration.results.0.value")
        assert apply_edits(credential, {"value": pristine}, document="metas-calibration") == []

    def test_an_unknown_key_is_refused(self, world) -> None:
        """Fields are addressed by key, and only keys the catalogue publishes."""
        credential = copy.deepcopy(world.credential("metas-calibration"))
        with pytest.raises(KeyError):
            apply_edits(credential, {"nonesuch": 1.0}, document="metas-calibration")

    def test_writing_never_creates_a_member(self, world) -> None:
        """A path that does not already resolve is a mistake, not an instruction."""
        credential = copy.deepcopy(world.credential("metas-calibration"))
        with pytest.raises(KeyError):
            write_path(credential, "credentialSubject.calibration.invented", 1.0)
        with pytest.raises(KeyError):
            write_path(credential, "credentialSubject.calibration.results.7.value", 1.0)

    def test_a_number_has_to_be_finite(self) -> None:
        """JSON accepts NaN and the canonicalization the signature runs over does not."""
        field = next(f for f in EDITABLE_FIELDS if f.kind == "number")
        for refused in (float("nan"), float("inf")):
            with pytest.raises(ValueError):
                coerce(field, refused)

    def test_a_number_stays_inside_its_field(self) -> None:
        """The bounds are what keep a slip from becoming an unexplained failure."""
        field = next(f for f in EDITABLE_FIELDS if f.minimum is not None)
        with pytest.raises(ValueError):
            coerce(field, field.minimum - 1.0)

    def test_a_date_that_is_not_a_date_is_refused(self) -> None:
        """The validity check reads an unparseable date as no date at all, and passes.

        Which would teach a reader the opposite of the truth, so it is refused here
        instead of reaching the pipeline.
        """
        field = next(f for f in EDITABLE_FIELDS if f.kind == "date")
        with pytest.raises(ValueError):
            coerce(field, "next Tuesday")

    def test_an_issuer_outside_the_list_is_refused(self) -> None:
        """Keys are derived under a cache with no bound, so nothing reader-supplied."""
        field = next(f for f in EDITABLE_FIELDS if f.path == "issuer.id")
        with pytest.raises(ValueError):
            coerce(field, "did:web:whoever.example")


class TestTheRoute:
    """What /api/edit answers, and what it refuses."""

    def test_no_edits_verifies(self, client: TestClient) -> None:
        """The state the chapter opens on, and the one Put it back returns to."""
        data = client.post(
            "/api/edit", json={"document": "metas-calibration", "edits": {}}
        ).json()
        assert data["report"]["outcome"] == "verified"
        assert data["applied"] == []
        assert data["caughtByExpectedStep"] is None

    def test_an_unsigned_edit_fails_the_proof_and_nothing_stops(
        self, client: TestClient
    ) -> None:
        """Only `shape` short-circuits, so the rest of the report is still an account."""
        data = client.post(
            "/api/edit",
            json={
                "document": "metas-calibration",
                "edits": {"valid-until": "2026-03-01"},
                "resign": False,
            },
        ).json()
        steps = {step["id"]: step["status"] for step in data["report"]["steps"]}
        assert steps["proof"] == "fail"
        assert steps["recognition"] == "pass"
        assert steps["validity"] == "fail"

    def test_signing_it_again_moves_the_failure(self, client: TestClient) -> None:
        """The argument of the chapter, as one assertion.

        The same edit, signed again by the issuer, produces a document nothing
        cryptographic can object to -- and it is refused anyway.
        """
        body = {
            "document": "callab-calibration",
            "edits": {"mra-logo": True},
            "resign": True,
        }
        data = client.post("/api/edit", json=body).json()
        steps = {step["id"]: step["status"] for step in data["report"]["steps"]}
        assert steps["proof"] == "pass"
        assert steps["recognition"] == "pass"
        assert data["failedSteps"] == ["mra-logo"]
        assert data["caughtByExpectedStep"] is True

    def test_the_report_names_the_member_a_schema_refused(self, client: TestClient) -> None:
        """A top-level anyOf reports one error at the root, quoting the whole instance.

        Which arrived in the step tree as twelve kilobytes of Python repr where a sentence
        belonged, and named nothing. It is the branch that got furthest that gets reported.
        """
        data = client.post(
            "/api/edit",
            json={
                "document": "metas-calibration",
                "edits": {"coverage-factor": 1.0},
            },
        ).json()
        step = next(s for s in data["report"]["steps"] if s["id"] == "output-validation")
        assert step["status"] == "fail"
        assert "coverageFactor" in step["detail"]
        assert len(step["detail"]) < 300

    def test_an_unknown_document_is_refused(self, client: TestClient) -> None:
        """Only the five end documents, and not by a name the caller invents."""
        assert client.post("/api/edit", json={"document": "bipm-recognition"}).status_code == 404

    def test_an_unknown_field_is_refused(self, client: TestClient) -> None:
        """The catalogue is what keeps this from being "rewrite any member"."""
        response = client.post(
            "/api/edit",
            json={"document": "metas-calibration", "edits": {"credentialSubject": 1}},
        )
        assert response.status_code == 400

    def test_an_unreadable_value_is_refused(self, client: TestClient) -> None:
        """And says which field, because the reader is looking at eight of them."""
        response = client.post(
            "/api/edit",
            json={"document": "metas-calibration", "edits": {"valid-until": "soon"}},
        )
        assert response.status_code == 400
        assert "Valid until" in response.json()["detail"]

    def test_the_world_is_not_disturbed(self, client: TestClient) -> None:
        """Every request verifies a copy, so the next reader gets the document as issued.

        The route does not rebuild the world -- nothing in the pipeline writes to the
        store, so it does not have to -- and this is what that rests on.
        """
        before = client.get("/api/credential/metas-calibration").json()["credential"]
        client.post(
            "/api/edit",
            json={"document": "metas-calibration", "edits": {"value": 1.0e6}},
        )
        after = client.get("/api/credential/metas-calibration").json()["credential"]
        assert before == after

    def test_the_catalogue_travels_with_the_world(self, client: TestClient) -> None:
        """The chapter draws its form from the world payload it already has."""
        documents = client.get("/api/world").json()["editableDocuments"]
        assert [item["name"] for item in documents] == list(EDITABLE_DOCUMENTS)
        for item in documents:
            assert item["fields"], f"{item['name']} offers nothing to edit"
            assert set(item["pristine"]) == {field["key"] for field in item["fields"]}
