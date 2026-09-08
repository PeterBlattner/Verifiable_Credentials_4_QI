"""How a credential actually moves, which nothing here had ever modelled.

Every chapter before this one hands credentials around as JSON. A certificate exists, a
verifier reads it, and the step where one party asked another for it is skipped
completely. That is not a small omission. The quality infrastructure's hard case is a
document crossing a border between two organisations with no prior relationship, and the
crossing is precisely the part that had never been built.

W3C's VCALM -- *A Verifiable Credential API for Lifecycle Management* -- describes the
exchange this module implements. Its shape is worth stating before the code, because two
properties of it do all the work:

**One endpoint, used twice.** A holder POSTs to an exchange and gets back a request for a
presentation. It POSTs the presentation to the same URL and gets back a result. Not two
services with two protocols: one conversation with two turns.

**The holder starts it.** There is no way for an issuer or a verifier to reach into a
wallet. Every flow begins with the party that holds the credentials, which is why the
whole thing survives a laboratory sitting behind a firewall with no inbound port.

The third property is the one this world was already shaped for and could not show.
A single party can be **both issuer and verifier in one exchange**: it verifies what was
presented and issues something new in the same round trip, conditional on the first
having passed. That is exactly what an OIML Issuing Authority does. It is what a customs
authority granting a clearance does. It is the case the quality infrastructure is made
of, and modelling it costs one endpoint.

What building it cost, and it is worth being blunt because it contradicts this project
elsewhere:

``actors/deployment.py`` argues that verification is *a computation, not a conversation*,
and concludes that a verifier operates nothing. The first half is true and the conclusion
does not follow from it once anybody has to *ask* for a credential. An exchange has state
-- which exchange, which turn, which challenge -- and state means a service, a store, an
expiry policy and something to attack. The hosting burden chapter is right that verifying
a credential you already hold is free. It is wrong that participating in the system is.

**The challenge is the reason this cannot be faked.** Each exchange issues a fresh
challenge and the holder signs it into the presentation, so a presentation is good for one
exchange and replaying it fails. A consequence a demonstration feels immediately: these
presentations cannot be built with the rest of the world at start-up, because none of them
exists until somebody opens an exchange.

Two things this deliberately does not implement, recorded so they are not mistaken for
oversights. There is no authorization on the endpoints, so anyone may open any exchange
and the world's fictional holders will present for them -- real deployments put OAuth or a
capability in front, which VCALM discusses and which would teach nothing here. And the
credentials returned on success are the ones already in the world rather than freshly
minted, which keeps the build deterministic and makes the honest point that an exchange is
transport: the same document arrives, and what changed is how it got there.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Final

from datetime import datetime

from vcqi.actors.registry import actor_by_did, actor_key
from vcqi.actors.scenarios import World
from vcqi.crypto.dataintegrity import (
    ProofError,
    proof_verification_method,
    sign_document,
    verify_proof,
)
from vcqi.vc.model import CREDENTIAL_CONTEXT
from vcqi.vc.resolver import Resolver
from vcqi.vc.verify import verify_credential

__all__ = [
    "Exchange",
    "ExchangeStore",
    "Workflow",
    "WORKFLOWS",
    "exchange_url",
    "holder_presentation",
    "presentation_request",
    "respond",
    "workflow_by_id",
]

#: How many exchanges to keep. An exchange is small, but it is caller-created state on a
#: public host, so it needs a ceiling that does not depend on callers behaving.
MAX_EXCHANGES: Final[int] = 256

#: How long an unfinished exchange stays open, in seconds. VCALM leaves the value to the
#: implementation; what matters is that there is one, because a challenge that never
#: expires is not much of a challenge.
EXCHANGE_TTL_SECONDS: Final[int] = 900


@dataclass(frozen=True)
class Workflow:
    """One kind of exchange this world can conduct.

    Attributes:
        id: Short identifier, used in the URL.
        title: Heading as the chapter shows it.
        coordinator: DID of the organisation operating the exchange endpoint.
        holder: DID of the party expected to drive it.
        role: ``issuer``, ``verifier`` or ``issuer-verifier`` -- what the coordinator is
            doing in this particular exchange, which is a property of the exchange and
            not of the organisation.
        reason: What the coordinator tells the holder it wants the credentials for. VCALM
            puts this in the query so a wallet can show a person why they are being asked.
        asks_for: Credential types the presentation request queries for. Empty means the
            coordinator wants only proof that the holder controls its identifier.
        presents: Names of the credentials the holder would answer with, in this world.
        issues: Name of the credential returned when everything presented verifies, or
            ``None`` when the coordinator is only checking.
        lesson: The one sentence this exchange exists to make.
    """

    id: str
    title: str
    coordinator: str
    holder: str
    role: str
    reason: str
    asks_for: tuple[str, ...]
    presents: tuple[str, ...]
    issues: str | None
    lesson: str

    def to_json(self) -> dict[str, Any]:
        """Return the workflow as the interface displays it.

        Returns:
            A JSON-compatible dictionary, with the two organisations named rather than
            left as identifiers the reader would have to resolve by hand.
        """
        coordinator = actor_by_did(self.coordinator)
        holder = actor_by_did(self.holder)
        return {
            "id": self.id,
            "title": self.title,
            "coordinator": self.coordinator,
            "coordinatorName": coordinator.name if coordinator else self.coordinator,
            "holder": self.holder,
            "holderName": holder.name if holder else self.holder,
            "role": self.role,
            "reason": self.reason,
            "asksFor": list(self.asks_for),
            "presents": list(self.presents),
            "issues": self.issues,
            "lesson": self.lesson,
        }


#: The three exchanges, in the order the chapter reads them: the simplest first, the one
#: that makes the point last.
WORKFLOWS: tuple[Workflow, ...] = (
    Workflow(
        id="accreditation",
        title="A laboratory collects its accreditation",
        coordinator="did:web:sas.example",
        holder="did:web:callab.example",
        role="issuer",
        reason=(
            "Prove you control the identifier the accreditation will name, so it cannot "
            "be collected by somebody else."
        ),
        asks_for=(),
        presents=(),
        issues="sas-recognition",
        lesson=(
            "The simplest exchange there is, and it still needs two turns. The "
            "accreditation body has something to give and no way to push it, so nothing "
            "happens until the laboratory asks. What it checks before handing it over is "
            "not a credential but control of an identifier: the holder signs the "
            "challenge, which proves it holds the private key behind the DID the "
            "accreditation is about."
        ),
    ),
    Workflow(
        id="border",
        title="An authority asks for a certificate of conformity",
        coordinator="did:web:surveillance.example",
        holder="did:web:cab.example",
        role="verifier",
        reason=(
            "Show the certificate of conformity for the product presented at the border, "
            "so the recognition behind it can be checked without contacting anybody."
        ),
        asks_for=("ProductConformityCredential",),
        presents=("cab-conformity",),
        issues=None,
        lesson=(
            "Pure verification, and the chapter on hosting has to be corrected for it. "
            "That chapter says a verifier operates nothing, which is true of checking a "
            "credential already in hand and false the moment the verifier has to ask for "
            "one. Asking is a conversation, a conversation has state, and state is a "
            "service. What stays true is the expensive half: the authority still "
            "contacts none of the organisations in the chain."
        ),
    ),
    Workflow(
        id="oiml-type",
        title="A laboratory presents evidence and receives a certificate",
        coordinator="did:web:legal-ia.example",
        holder="did:web:testlab.example",
        role="issuer-verifier",
        reason=(
            "Show that the OIML recognises you as a Test Laboratory, and show the type "
            "evaluation report you are asking to have certified."
        ),
        asks_for=("RecognizedEntityCredential", "TypeEvaluationReportCredential"),
        presents=("oiml-tl-recognition", "oiml-evaluation"),
        issues="oiml-certificate",
        lesson=(
            "One party, both roles, one round trip. The Issuing Authority verifies what "
            "the laboratory presented and issues the type certificate in the same "
            "response, and it issues nothing if either credential fails. Every earlier "
            "chapter had this certificate simply existing. Here it is produced by the "
            "check that justifies it, which is the difference between a document and a "
            "decision."
        ),
    ),
)


@dataclass
class Exchange:
    """One conversation in progress.

    Attributes:
        id: Identifier, and the last path segment of the endpoint.
        workflow_id: Which workflow this is an instance of.
        challenge: Fresh per exchange, and signed into the presentation by the holder.
        opened: Monotonic time the exchange was created, for expiry.
        turn: How many times the holder has posted to it.
        state: ``open`` once a request has been served, then ``complete`` or ``refused``.
    """

    id: str
    workflow_id: str
    challenge: str
    opened: float
    turn: int = 0
    state: str = "created"
    history: list[dict[str, Any]] = field(default_factory=list)


class ExchangeStore:
    """The exchanges currently open, with a ceiling and an expiry.

    An in-process dictionary, which is the same honest choice ``web/limits.py`` makes for
    the token buckets: one container, no store to add, and nothing behind it worth
    protecting. It does mean exchanges vanish on restart and do not survive more than one
    worker, and both are recorded in ARCHITECTURE.md rather than discovered.

    It exists at all because an exchange is the first thing in this project that the
    server has to remember between requests.
    """

    def __init__(self) -> None:
        self._exchanges: dict[str, Exchange] = {}

    def open(self, workflow_id: str, *, now: float | None = None) -> Exchange:
        """Create an exchange and return it.

        Args:
            workflow_id: Which workflow to instantiate.
            now: Monotonic time to record, for tests that control the clock.

        Returns:
            The new exchange, already stored.
        """
        moment = time.monotonic() if now is None else now
        self._prune(moment)
        exchange = Exchange(
            id=secrets.token_urlsafe(9),
            workflow_id=workflow_id,
            challenge=secrets.token_urlsafe(16),
            opened=moment,
        )
        self._exchanges[exchange.id] = exchange
        return exchange

    def get(self, exchange_id: str, *, now: float | None = None) -> Exchange | None:
        """Return an exchange if it exists and has not expired.

        Args:
            exchange_id: The identifier from the URL.
            now: Monotonic time to compare against.

        Returns:
            The exchange, or ``None`` when it is unknown or too old.
        """
        moment = time.monotonic() if now is None else now
        exchange = self._exchanges.get(exchange_id)
        if exchange is None:
            return None
        if moment - exchange.opened > EXCHANGE_TTL_SECONDS:
            del self._exchanges[exchange_id]
            return None
        return exchange

    def _prune(self, now: float) -> None:
        """Drop expired exchanges, then oldest-first if still over the ceiling.

        Args:
            now: Monotonic time to compare against.
        """
        for key, exchange in list(self._exchanges.items()):
            if now - exchange.opened > EXCHANGE_TTL_SECONDS:
                del self._exchanges[key]
        while len(self._exchanges) >= MAX_EXCHANGES:
            oldest = min(self._exchanges.values(), key=lambda item: item.opened)
            del self._exchanges[oldest.id]

    def __len__(self) -> int:
        """Return how many exchanges are held.

        Returns:
            The count, which the chapter shows so the state is visible rather than
            merely described.
        """
        return len(self._exchanges)


def workflow_by_id(workflow_id: str) -> Workflow | None:
    """Return the workflow with this identifier.

    Args:
        workflow_id: The identifier from the URL.

    Returns:
        The workflow, or ``None`` if there is no such one.
    """
    for workflow in WORKFLOWS:
        if workflow.id == workflow_id:
            return workflow
    return None


def exchange_url(base_url: str, workflow: Workflow, exchange: Exchange) -> str:
    """Return the endpoint a holder posts to.

    Args:
        base_url: Origin of the running server, with no trailing slash.
        workflow: The workflow being run.
        exchange: The exchange in progress.

    Returns:
        The absolute URL, which is what goes into the request's ``interact`` service so
        the holder is told where to continue rather than having to construct it.
    """
    return f"{base_url}/workflows/{workflow.id}/exchanges/{exchange.id}"


def presentation_request(
    workflow: Workflow, exchange: Exchange, *, base_url: str
) -> dict[str, Any]:
    """Build what the coordinator sends back on the first turn.

    The shape is VCALM's: a list of queries, a challenge and domain that bind the answer
    to this exchange, and an ``interact`` service saying where to send it. A workflow
    that asks for no credential types still sends a query -- ``DIDAuthentication``, which
    asks the holder to prove control of its identifier and nothing more.

    Args:
        workflow: The workflow being run.
        exchange: The exchange in progress.
        base_url: Origin of the running server, with no trailing slash.

    Returns:
        The request, wrapped in the member name VCALM gives it.
    """
    if workflow.asks_for:
        query: dict[str, Any] = {
            "type": "QueryByExample",
            "credentialQuery": [
                {
                    "reason": workflow.reason,
                    "example": {"@context": CREDENTIAL_CONTEXT, "type": credential_type},
                }
                for credential_type in workflow.asks_for
            ],
        }
    else:
        query = {"type": "DIDAuthentication", "reason": workflow.reason}

    return {
        "verifiablePresentationRequest": {
            "query": [query],
            "challenge": exchange.challenge,
            "domain": workflow.coordinator,
            "interact": {
                "service": [
                    {
                        "type": "UnmediatedHttpPresentationService2021",
                        "serviceEndpoint": exchange_url(base_url, workflow, exchange),
                    }
                ]
            },
        }
    }


def holder_presentation(
    world: World,
    workflow: Workflow,
    exchange: Exchange,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Build and sign what the holder sends back on the second turn.

    The presentation is signed with the holder's own key, for the ``authentication``
    purpose rather than ``assertionMethod``: the holder is not asserting the contents,
    which the issuers already signed, but proving it is the party that was asked.

    The challenge and the coordinator's identifier are signed in. That is what makes this
    presentation answer *this* exchange and no other, and it is why one cannot be built in
    advance -- the challenge does not exist until the exchange is opened.

    Args:
        world: The built world, for the credentials the holder is presenting.
        workflow: The workflow being run.
        exchange: The exchange in progress, for its challenge.
        now: The instant to record as the proof's creation time.

    Returns:
        The signed presentation.
    """
    presentation: dict[str, Any] = {
        "@context": CREDENTIAL_CONTEXT,
        "type": ["VerifiablePresentation"],
        "holder": workflow.holder,
    }
    if workflow.presents:
        presentation["verifiableCredential"] = [
            world.credential(name) for name in workflow.presents
        ]

    signed, _ = sign_document(
        presentation,
        actor_key(workflow.holder),
        created=now,
        proof_purpose="authentication",
        challenge=exchange.challenge,
        domain=workflow.coordinator,
    )
    return signed


def _check_presentation(
    presentation: Any,
    workflow: Workflow,
    exchange: Exchange,
    *,
    resolver: Resolver,
) -> str | None:
    """Return why a presentation is unacceptable, or ``None`` if it is fine.

    This is the coordinator's half of the challenge mechanism, and it is deliberately
    separate from credential verification: a presentation can carry perfectly valid
    credentials and still be the wrong answer, because it was made for somebody else or
    for an earlier exchange.

    The order below is the whole argument, and the last step is the one that makes the
    others mean anything. Reading the challenge out of the proof and comparing it is
    worth nothing on its own -- a forger with an intercepted presentation would simply
    edit that string. It counts because the proof is then verified against the holder's
    published key, and the challenge is inside the proof configuration that was hashed,
    so editing it breaks the signature. A first version of this module checked the three
    strings and never verified the presentation, and a test caught it: an intercepted
    presentation, re-pointed at a live exchange by editing one field, collected a
    certificate. That is the bug this ordering exists to prevent.

    Args:
        presentation: Whatever the holder posted.
        workflow: The workflow being run.
        exchange: The exchange in progress.
        resolver: Used to resolve the holder's key.

    Returns:
        A sentence naming the problem, or ``None``.
    """
    if not isinstance(presentation, dict):
        return "the body carried no verifiablePresentation object"

    proof = presentation.get("proof")
    if not isinstance(proof, dict):
        return "the presentation is unsigned, so it proves only that somebody sent it"
    if proof.get("proofPurpose") != "authentication":
        return (
            "the presentation's proof was made for "
            f"{proof.get('proofPurpose')!r} rather than authentication"
        )
    if proof.get("challenge") != exchange.challenge:
        return (
            "the presentation answers a different challenge, so it was made for another "
            "exchange and is being replayed into this one"
        )
    if proof.get("domain") != workflow.coordinator:
        return (
            "the presentation was made for "
            f"{proof.get('domain')!r}, not for this coordinator, so it is being forwarded"
        )

    holder = presentation.get("holder")
    if holder != workflow.holder:
        return (
            f"the presentation names {holder!r} as its holder, and this exchange was "
            f"opened for {workflow.holder}"
        )

    try:
        method_id = proof_verification_method(presentation)
    except ProofError as error:
        return f"the presentation's proof is malformed: {error}"

    controller, _, _ = method_id.partition("#")
    if controller != holder:
        return (
            f"the presentation was signed with a key controlled by {controller}, which "
            f"is not the holder it claims to be"
        )
    if method_id not in resolver.authentication_methods(holder):
        return (
            f"{method_id} is not published by {holder} for authentication, so it cannot "
            "prove who is presenting"
        )

    public_key = resolver.resolve_public_key(method_id)
    if public_key is None:
        return f"{method_id} does not resolve to a published key"

    try:
        verify_proof(presentation, public_key)
    except ProofError as error:
        return (
            "the presentation's own signature does not verify, so whatever it says "
            f"about the challenge is unsupported: {error}"
        )
    return None


def respond(
    body: dict[str, Any],
    workflow: Workflow,
    exchange: Exchange,
    *,
    world: World,
    base_url: str,
    now: datetime,
    trusted_issuers: frozenset[str] | set[str],
) -> dict[str, Any]:
    """Take one turn of an exchange and return what the coordinator sends back.

    Both turns are the same POST to the same URL, which is the property worth seeing:
    what distinguishes them is what the holder put in the body, not where it was sent.

    Turn one has an empty body and is answered with a presentation request. Turn two
    carries a presentation, and is answered with the credential the workflow issues, or
    with an empty object when the workflow only verifies, or with a refusal naming the
    check that failed.

    Args:
        body: The parsed request body.
        workflow: The workflow being run.
        exchange: The exchange in progress.
        world: The built world, for the credentials involved.
        base_url: Origin of the running server, with no trailing slash.
        now: The instant to verify against.
        trusted_issuers: The identifiers the coordinator trusts as anchors.

    Returns:
        The response body, plus a ``vcqi`` member carrying what the chapter needs to
        narrate the turn. That member is not part of VCALM and is marked as ours.
    """
    presentation = body.get("verifiablePresentation")

    if presentation is None:
        exchange.turn = 1
        exchange.state = "open"
        response = presentation_request(workflow, exchange, base_url=base_url)
        exchange.history.append({"turn": 1, "direction": "down", "kind": "request"})
        return {
            **response,
            "vcqi": {
                "turn": 1,
                "state": exchange.state,
                "explains": (
                    "The holder asked, and was asked back. Nothing has been proved yet: "
                    "this response only says what would satisfy the coordinator, and "
                    "carries the challenge that ties the answer to this exchange."
                ),
            },
        }

    exchange.turn = 2
    resolver = Resolver(store=world.store)
    refusal = _check_presentation(presentation, workflow, exchange, resolver=resolver)
    reports: list[dict[str, Any]] = []

    if refusal is None:
        credentials = presentation.get("verifiableCredential") or []
        if not isinstance(credentials, list):
            credentials = [credentials]

        # Verify every credential presented, with the others stapled alongside so the
        # coordinator uses what the holder actually sent rather than fetching its own
        # copy. That is the point of a presentation: the holder supplies the evidence.
        for credential in credentials:
            report = verify_credential(
                credential,
                store=world.store,
                now=now,
                trusted_issuers=trusted_issuers,
                presented=list(credentials),
            )
            reports.append(report.to_json())

        failed = [report for report in reports if report["outcome"] != "verified"]
        if failed:
            refusal = (
                "a credential in the presentation did not verify, so nothing is issued"
            )

    if refusal is not None:
        exchange.state = "refused"
        exchange.history.append({"turn": 2, "direction": "down", "kind": "refusal"})
        return {
            "vcqi": {
                "turn": 2,
                "state": exchange.state,
                "refused": refusal,
                "reports": reports,
                "explains": (
                    "The coordinator refused, and the exchange is over. Refusing is the "
                    "whole reason the second turn exists: an exchange that always ended "
                    "in issuance would be a download."
                ),
            }
        }

    exchange.state = "complete"
    exchange.history.append({"turn": 2, "direction": "down", "kind": "result"})

    if workflow.issues is None:
        return {
            "vcqi": {
                "turn": 2,
                "state": exchange.state,
                "reports": reports,
                "issued": None,
                "explains": (
                    "An empty response, which VCALM says means the exchange is finished "
                    "and there is nothing further to send. The coordinator was verifying, "
                    "not issuing, so a successful outcome looks like silence."
                ),
            }
        }

    issued = world.credential(workflow.issues)
    return {
        "verifiablePresentation": {
            "@context": CREDENTIAL_CONTEXT,
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [issued],
        },
        "vcqi": {
            "turn": 2,
            "state": exchange.state,
            "reports": reports,
            "issued": workflow.issues,
            "explains": (
                "Verified and issued in one response. The coordinator was both verifier "
                "and issuer, and the second depended on the first: had either presented "
                "credential failed, this would have been the refusal above and no "
                "certificate would exist."
            )
            if workflow.role == "issuer-verifier"
            else (
                "Issued. The holder proved control of its identifier and the credential "
                "came back in the same exchange it asked in."
            ),
        },
    }
