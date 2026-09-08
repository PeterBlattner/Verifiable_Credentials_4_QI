"""Tests for the exchange, which is the first stateful thing in this project.

Three groups, and the middle one is the reason this file is long.

The first checks that each of the three workflows completes and returns what it says it
will. The second checks that it refuses everything it should, because an exchange that
cannot refuse is a download with extra steps -- and the refusals are where the challenge
mechanism either works or is decoration. The third checks the store, since it is caller
created state on a public host and its ceiling is the only thing standing between a loop
and unbounded memory.

One property is asserted rather than assumed throughout: the challenge is *signed*, not
merely carried. A presentation that quotes the right challenge in a proof the holder did
not make over it would be a forgery this whole design rests on catching.
"""

from __future__ import annotations

import copy

from starlette.testclient import TestClient

from vcqi.actors.exchange import (
    EXCHANGE_TTL_SECONDS,
    MAX_EXCHANGES,
    WORKFLOWS,
    ExchangeStore,
    holder_presentation,
    presentation_request,
    respond,
    workflow_by_id,
)
from vcqi.actors.registry import TRUST_ANCHORS, actor_by_did
from vcqi.actors.scenarios import DEMO_NOW, build_world
from vcqi.crypto.dataintegrity import sign_document
from vcqi.actors.registry import actor_key
from vcqi.web.app import app
from vcqi.web.limits import route_cost

BASE = "https://example.test"


def _run(workflow_id: str, *, world, store, into: str | None = None):
    """Drive one exchange to completion and return the final response.

    Args:
        workflow_id: Which workflow to run.
        world: The built world.
        store: The exchange store to open exchanges in.
        into: Post the presentation into this other exchange instead, which is how a
            replay is staged.

    Returns:
        A tuple of the workflow, the exchange, the presentation and the final response.
    """
    workflow = workflow_by_id(workflow_id)
    assert workflow is not None
    exchange = store.open(workflow.id)
    respond({}, workflow, exchange, world=world, base_url=BASE, now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS)
    presentation = holder_presentation(world, workflow, exchange, now=DEMO_NOW)

    target = exchange
    if into is not None:
        target = store.open(workflow.id)
        respond({}, workflow, target, world=world, base_url=BASE, now=DEMO_NOW,
                trusted_issuers=TRUST_ANCHORS)

    response = respond(
        {"verifiablePresentation": presentation},
        workflow,
        target,
        world=world,
        base_url=BASE,
        now=DEMO_NOW,
        trusted_issuers=TRUST_ANCHORS,
    )
    return workflow, exchange, presentation, response


class TestTheThreeExchangesWork:
    """Each workflow completes, and returns the kind of thing it promised."""

    def test_every_workflow_names_organisations_that_exist(self) -> None:
        """A workflow naming an actor nobody built renders a blank panel heading."""
        for workflow in WORKFLOWS:
            assert actor_by_did(workflow.coordinator) is not None, workflow.id
            assert actor_by_did(workflow.holder) is not None, workflow.id
            assert workflow.role in {"issuer", "verifier", "issuer-verifier"}

    def test_every_workflow_presents_credentials_that_exist(self) -> None:
        """And issues one that exists, when it issues at all."""
        world = build_world()
        for workflow in WORKFLOWS:
            for name in workflow.presents:
                assert name in world.credentials, f"{workflow.id} presents unknown {name}"
            if workflow.issues is not None:
                assert workflow.issues in world.credentials, workflow.id

    def test_the_first_turn_asks_and_proves_nothing(self) -> None:
        """Turn one carries the challenge and settles no question at all."""
        world = build_world()
        store = ExchangeStore()
        workflow = workflow_by_id("oiml-type")
        assert workflow is not None
        exchange = store.open(workflow.id)

        response = respond({}, workflow, exchange, world=world, base_url=BASE,
                           now=DEMO_NOW, trusted_issuers=TRUST_ANCHORS)
        request = response["verifiablePresentationRequest"]

        assert request["challenge"] == exchange.challenge
        assert request["domain"] == workflow.coordinator
        # The holder is told where to continue rather than having to construct it.
        endpoint = request["interact"]["service"][0]["serviceEndpoint"]
        assert endpoint == f"{BASE}/workflows/{workflow.id}/exchanges/{exchange.id}"
        assert "verifiablePresentation" not in response

    def test_a_workflow_asking_for_no_credential_asks_for_authentication(self) -> None:
        """Collecting an accreditation proves control of an identifier, nothing more."""
        store = ExchangeStore()
        workflow = workflow_by_id("accreditation")
        assert workflow is not None
        exchange = store.open(workflow.id)
        request = presentation_request(workflow, exchange, base_url=BASE)
        query = request["verifiablePresentationRequest"]["query"][0]
        assert query["type"] == "DIDAuthentication"

    def test_issuing_returns_the_credential(self) -> None:
        """The accreditation arrives in the exchange the laboratory opened."""
        world = build_world()
        workflow, _, _, response = _run("accreditation", world=world, store=ExchangeStore())
        assert response["vcqi"]["state"] == "complete"
        assert response["vcqi"]["issued"] == workflow.issues
        issued = response["verifiablePresentation"]["verifiableCredential"][0]
        assert issued == world.credential(workflow.issues)

    def test_verifying_returns_nothing_and_that_is_success(self) -> None:
        """VCALM's empty response: finished, with nothing further to send."""
        world = build_world()
        _, _, _, response = _run("border", world=world, store=ExchangeStore())
        assert response["vcqi"]["state"] == "complete"
        assert response["vcqi"]["issued"] is None
        assert "verifiablePresentation" not in response
        assert [r["outcome"] for r in response["vcqi"]["reports"]] == ["verified"]

    def test_one_party_verifies_and_issues_in_the_same_turn(self) -> None:
        """The exchange the reviewer pointed at, and the reason for the chapter.

        Two credentials verified and a third issued, in one response. This is the shape
        the quality infrastructure is made of and the one thing the demonstration could
        not previously show at all.
        """
        world = build_world()
        workflow, _, presentation, response = _run(
            "oiml-type", world=world, store=ExchangeStore()
        )
        assert workflow.role == "issuer-verifier"

        # Two presented, both checked.
        assert len(presentation["verifiableCredential"]) == 2
        assert [r["outcome"] for r in response["vcqi"]["reports"]] == ["verified", "verified"]

        # And one issued, in the same response.
        assert response["vcqi"]["issued"] == "oiml-certificate"
        issued = response["verifiablePresentation"]["verifiableCredential"][0]
        assert "OimlCertificateCredential" in issued["type"]


class TestItRefusesWhatItShould:
    """An exchange that cannot refuse is a download. These are the refusals."""

    def test_a_presentation_replayed_into_another_exchange_is_refused(self) -> None:
        """The challenge is per exchange, so an answer fits exactly one of them."""
        world = build_world()
        _, _, _, response = _run(
            "oiml-type", world=world, store=ExchangeStore(), into="second"
        )
        assert response["vcqi"]["state"] == "refused"
        assert "different challenge" in response["vcqi"]["refused"]
        assert "verifiablePresentation" not in response

    def test_a_tampered_credential_stops_the_issuance(self) -> None:
        """The point of verifying before issuing, and it has to be the whole reason.

        The presentation is re-signed after the credential is altered, so the holder's
        own proof is valid and only the credential inside it is broken. Nothing may be
        issued on the strength of it.
        """
        world = build_world()
        store = ExchangeStore()
        workflow = workflow_by_id("oiml-type")
        assert workflow is not None
        exchange = store.open(workflow.id)
        respond({}, workflow, exchange, world=world, base_url=BASE, now=DEMO_NOW,
                trusted_issuers=TRUST_ANCHORS)

        presentation = holder_presentation(world, workflow, exchange, now=DEMO_NOW)
        altered = copy.deepcopy(presentation)
        altered["verifiableCredential"][1]["credentialSubject"]["typeDesignation"] = "MW-E9"
        unsigned = {k: v for k, v in altered.items() if k != "proof"}
        resigned, _ = sign_document(
            unsigned,
            actor_key(workflow.holder),
            created=DEMO_NOW,
            proof_purpose="authentication",
            challenge=exchange.challenge,
            domain=workflow.coordinator,
        )

        response = respond(
            {"verifiablePresentation": resigned},
            workflow,
            exchange,
            world=world,
            base_url=BASE,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert response["vcqi"]["state"] == "refused"
        assert "did not verify" in response["vcqi"]["refused"]
        assert "verifiablePresentation" not in response
        assert [r["outcome"] for r in response["vcqi"]["reports"]] == ["verified", "rejected"]

    def test_the_challenge_is_signed_and_not_merely_carried(self) -> None:
        """Quoting the right challenge in someone else's proof must not work.

        This is the assumption the whole mechanism rests on. If the challenge travelled
        beside the signature rather than inside it, an intercepted presentation could be
        re-pointed at a live exchange by editing one string.
        """
        world = build_world()
        store = ExchangeStore()
        workflow = workflow_by_id("oiml-type")
        assert workflow is not None

        first = store.open(workflow.id)
        second = store.open(workflow.id)
        for exchange in (first, second):
            respond({}, workflow, exchange, world=world, base_url=BASE, now=DEMO_NOW,
                    trusted_issuers=TRUST_ANCHORS)

        presentation = holder_presentation(world, workflow, first, now=DEMO_NOW)
        # Edit the challenge to match the exchange it is being aimed at.
        forged = copy.deepcopy(presentation)
        forged["proof"]["challenge"] = second.challenge

        response = respond(
            {"verifiablePresentation": forged},
            workflow,
            second,
            world=world,
            base_url=BASE,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
        )
        # It passes the challenge comparison and fails the signature, which is the
        # order that matters: the proof covers the challenge.
        assert response["vcqi"]["state"] == "refused"
        assert "verifiablePresentation" not in response

    def test_an_unsigned_presentation_is_refused(self) -> None:
        """Anyone can post a JSON object; a proof is what makes it an answer."""
        world = build_world()
        store = ExchangeStore()
        workflow = workflow_by_id("border")
        assert workflow is not None
        exchange = store.open(workflow.id)
        respond({}, workflow, exchange, world=world, base_url=BASE, now=DEMO_NOW,
                trusted_issuers=TRUST_ANCHORS)

        presentation = holder_presentation(world, workflow, exchange, now=DEMO_NOW)
        del presentation["proof"]

        response = respond(
            {"verifiablePresentation": presentation},
            workflow,
            exchange,
            world=world,
            base_url=BASE,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert response["vcqi"]["state"] == "refused"
        assert "unsigned" in response["vcqi"]["refused"]

    def test_a_presentation_made_for_another_coordinator_is_refused(self) -> None:
        """The domain stops an answer being forwarded to a second verifier."""
        world = build_world()
        store = ExchangeStore()
        workflow = workflow_by_id("border")
        assert workflow is not None
        exchange = store.open(workflow.id)
        respond({}, workflow, exchange, world=world, base_url=BASE, now=DEMO_NOW,
                trusted_issuers=TRUST_ANCHORS)

        elsewhere = {
            "@context": world.credential("cab-conformity")["@context"],
            "type": ["VerifiablePresentation"],
            "holder": workflow.holder,
            "verifiableCredential": [world.credential("cab-conformity")],
        }
        signed, _ = sign_document(
            elsewhere,
            actor_key(workflow.holder),
            created=DEMO_NOW,
            proof_purpose="authentication",
            challenge=exchange.challenge,
            domain="did:web:somebody-else.example",
        )

        response = respond(
            {"verifiablePresentation": signed},
            workflow,
            exchange,
            world=world,
            base_url=BASE,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert response["vcqi"]["state"] == "refused"
        assert "forwarded" in response["vcqi"]["refused"]

    def test_a_credential_proof_is_not_an_authentication_proof(self) -> None:
        """A presentation signed for assertionMethod is refused.

        Not pedantry. The purpose is what separates *I made these claims* from *I am the
        party you asked*, and a verifier that accepts either has stopped distinguishing
        the holder from the issuer.
        """
        world = build_world()
        store = ExchangeStore()
        workflow = workflow_by_id("border")
        assert workflow is not None
        exchange = store.open(workflow.id)
        respond({}, workflow, exchange, world=world, base_url=BASE, now=DEMO_NOW,
                trusted_issuers=TRUST_ANCHORS)

        presentation = {
            "@context": world.credential("cab-conformity")["@context"],
            "type": ["VerifiablePresentation"],
            "holder": workflow.holder,
            "verifiableCredential": [world.credential("cab-conformity")],
        }
        signed, _ = sign_document(
            presentation,
            actor_key(workflow.holder),
            created=DEMO_NOW,
            proof_purpose="assertionMethod",
            challenge=exchange.challenge,
            domain=workflow.coordinator,
        )

        response = respond(
            {"verifiablePresentation": signed},
            workflow,
            exchange,
            world=world,
            base_url=BASE,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert response["vcqi"]["state"] == "refused"
        assert "authentication" in response["vcqi"]["refused"]


    def test_somebody_elses_credentials_cannot_be_presented(self) -> None:
        """The forgery the challenge check alone would have allowed.

        Every credential in this presentation is genuine and verifies perfectly, because
        credentials are public documents and anyone can obtain a copy. What the attacker
        cannot do is sign an authentication proof as the laboratory. Chapter 2 makes this
        point about credentials; it is the same point about presentations, and it is the
        only thing standing between a public certificate and anyone claiming it.
        """
        world = build_world()
        store = ExchangeStore()
        workflow = workflow_by_id("oiml-type")
        assert workflow is not None
        exchange = store.open(workflow.id)
        respond({}, workflow, exchange, world=world, base_url=BASE, now=DEMO_NOW,
                trusted_issuers=TRUST_ANCHORS)

        stolen = {
            "@context": world.credential("oiml-evaluation")["@context"],
            "type": ["VerifiablePresentation"],
            # Claiming to be the laboratory the exchange was opened for.
            "holder": workflow.holder,
            "verifiableCredential": [
                world.credential("oiml-tl-recognition"),
                world.credential("oiml-evaluation"),
            ],
        }
        # Signed with a different organisation's key, everything else correct.
        signed, _ = sign_document(
            stolen,
            actor_key("did:web:manufacturer.example"),
            created=DEMO_NOW,
            proof_purpose="authentication",
            challenge=exchange.challenge,
            domain=workflow.coordinator,
        )

        response = respond(
            {"verifiablePresentation": signed},
            workflow,
            exchange,
            world=world,
            base_url=BASE,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert response["vcqi"]["state"] == "refused"
        assert "not the holder it claims to be" in response["vcqi"]["refused"]
        assert "verifiablePresentation" not in response


class TestTheStoreHasALimit:
    """It is caller-created state on a public host, so the ceiling is load-bearing."""

    def test_an_expired_exchange_is_gone(self) -> None:
        """A challenge that never expires is not much of a challenge."""
        store = ExchangeStore()
        exchange = store.open("border", now=0.0)
        assert store.get(exchange.id, now=EXCHANGE_TTL_SECONDS - 1) is not None
        assert store.get(exchange.id, now=EXCHANGE_TTL_SECONDS + 1) is None

    def test_the_store_does_not_grow_without_bound(self) -> None:
        """Oldest first, so a loop pushes out its own exchanges rather than the host."""
        store = ExchangeStore()
        for index in range(MAX_EXCHANGES * 2):
            store.open("border", now=float(index))
        assert len(store) <= MAX_EXCHANGES

    def test_an_unknown_exchange_is_not_an_error_to_guess(self) -> None:
        """Returning None rather than raising is what lets the route answer 404."""
        assert ExchangeStore().get("not-an-exchange") is None


class TestTheRoutes:
    """Over HTTP, because the paths are VCALM's and the shape is the point."""

    def test_both_turns_are_the_same_post_to_the_same_url(self) -> None:
        """The property worth seeing: the body distinguishes them, not the address."""
        with TestClient(app) as client:
            opened = client.post("/workflows/oiml-type/exchanges").json()
            url = f"/workflows/oiml-type/exchanges/{opened['exchangeId']}"

            first = client.post(url, json={}).json()
            assert "verifiablePresentationRequest" in first

            presentation = client.post(
                f"/api/exchange/oiml-type/{opened['exchangeId']}/present"
            ).json()["verifiablePresentation"]

            second = client.post(url, json={"verifiablePresentation": presentation}).json()
            assert second["vcqi"]["state"] == "complete"
            assert "verifiableCredential" in second["verifiablePresentation"]

    def test_an_empty_body_is_a_valid_first_turn(self) -> None:
        """VCALM's first turn carries nothing, so no body at all must work."""
        with TestClient(app) as client:
            opened = client.post("/workflows/border/exchanges").json()
            response = client.post(
                f"/workflows/border/exchanges/{opened['exchangeId']}", content=b""
            )
            assert response.status_code == 200
            assert "verifiablePresentationRequest" in response.json()

    def test_an_unknown_workflow_or_exchange_is_a_404(self) -> None:
        """Rather than a 500, which is what guessing an identifier used to produce."""
        with TestClient(app) as client:
            assert client.post("/workflows/nonesuch/exchanges").status_code == 404
            assert client.post("/workflows/border/exchanges/nope", json={}).status_code == 404

    def test_an_exchange_belongs_to_its_own_workflow(self) -> None:
        """An exchange id from one workflow must not be usable under another.

        Otherwise a border exchange could be driven through the issuing workflow and
        collect a credential the authority never asked for.
        """
        with TestClient(app) as client:
            opened = client.post("/workflows/border/exchanges").json()
            crossed = client.post(
                f"/workflows/oiml-type/exchanges/{opened['exchangeId']}", json={}
            )
            assert crossed.status_code == 404

    def test_the_workflow_listing_shows_the_state_the_server_now_holds(self) -> None:
        """The chapter shows this, because the statefulness is the honest cost."""
        with TestClient(app) as client:
            data = client.get("/api/exchange/workflows").json()
            assert [w["id"] for w in data["workflows"]] == [w.id for w in WORKFLOWS]
            assert data["maxExchanges"] == MAX_EXCHANGES
            assert data["ttlSeconds"] == EXCHANGE_TTL_SECONDS
            before = data["open"]
            client.post("/workflows/border/exchanges")
            assert client.get("/api/exchange/workflows").json()["open"] == before + 1

    def test_the_expensive_turn_is_charged_and_the_cheap_one_is_not(self) -> None:
        """A turn runs the pipeline over a presentation the caller composed.

        That is `/api/verify` with the number of credentials also in the caller's hands,
        so it has to cost the same. Opening an exchange costs less because what it
        consumes is a store slot with a ceiling, not CPU.
        """
        assert route_cost("/workflows/border/exchanges/abc") == route_cost("/api/verify")
        assert 0 < route_cost("/workflows/border/exchanges") < route_cost("/api/verify")
        assert route_cost("/api/exchange/workflows") == 0
