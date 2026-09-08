"""Tests for what can travel with a credential, and for the rule that decides it.

Two groups, and the first is a security regression test rather than a measurement.

Before ``RESOLVE_ONLY_KINDS`` existed, ``Resolver.fetch`` honoured anything the holder
supplied, and ``resolve_did_document`` went through it. So a holder could staple a DID
document claiming a trust anchor's identifier, sign a credential in that anchor's name
with its own key, and the whole pipeline reported ``verified``. Every check passed,
because from the verifier's point of view the anchor's published key really was the
attacker's -- the attacker had supplied the document that said so.

``test_a_stapled_did_document_cannot_impersonate_an_anchor`` is that exploit, kept.

The second group checks the audit is a measurement and not a story: every document the
verification reads is classified, the classification is exhaustive in both directions,
and the two retrieval counts come from the resolver's own log rather than from prose.
"""

from __future__ import annotations

import copy
import dataclasses

from starlette.testclient import TestClient

from vcqi.actors.portability import (
    AUDIT_CREDENTIAL,
    PORTABILITY_CLASSES,
    class_of_kind,
    portability_audit,
)
from vcqi.actors.registry import TRUST_ANCHORS, actor_key
from vcqi.actors.scenarios import DEMO_NOW, build_world
from vcqi.crypto.dataintegrity import sign_document
from vcqi.crypto.keys import build_did_document
from vcqi.vc.resolver import RESOLVE_ONLY_KINDS, Resolver
from vcqi.vc.verify import verify_credential
from vcqi.web.app import app


def _impostor_did_document(anchor: str, attacker_did: str) -> dict:
    """Build a DID document publishing an attacker's key under somebody else's name.

    Args:
        anchor: The identifier to impersonate.
        attacker_did: The identifier whose real key material is reused.

    Returns:
        A DID document that resolves ``anchor`` to the attacker's key.
    """
    attacker = actor_key(attacker_did)
    return build_did_document(dataclasses.replace(attacker, did=anchor))


class TestAHolderCannotSupplyTheKeyItIsCheckedAgainst:
    """The forgery the portability rule exists to stop."""

    def test_a_stapled_did_document_cannot_impersonate_an_anchor(self) -> None:
        """The exploit, kept as a test because it worked.

        The attacker signs a recognition credential in the OIML's name using its own
        key, and staples a DID document that resolves the OIML's identifier to that key.
        Nothing about the credential is malformed: the signature genuinely verifies
        against the key the stapled document publishes, and the issuer genuinely is a
        trust anchor. The only lie is which document said so.
        """
        world = build_world()
        anchor = "did:web:oiml.example"
        assert anchor in TRUST_ANCHORS

        forged_did = _impostor_did_document(anchor, "did:web:manufacturer.example")
        impostor = dataclasses.replace(
            actor_key("did:web:manufacturer.example"), did=anchor
        )

        genuine = copy.deepcopy(world.credentials["oiml-tl-recognition"])
        unsigned = {name: value for name, value in genuine.items() if name != "proof"}
        unsigned["id"] = "https://oiml.example/recognition/forged"
        # Dropped so the status check cannot be what catches it. It did catch it, once,
        # and only because the real host serves a list the attacker's key cannot sign --
        # which is luck rather than a defence, and would not survive a credential that
        # published no status list.
        unsigned.pop("credentialStatus", None)
        forged, _ = sign_document(unsigned, impostor, created=DEMO_NOW)

        report = verify_credential(
            forged,
            store=world.store,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
            presented=[forged_did],
        )

        assert report.outcome == "rejected"
        proof = next(step for step in report.steps if step.id == "proof")
        assert proof.status == "fail", "the stapled DID document was used as a key source"

    def test_the_rule_names_every_kind_that_must_not_travel(self) -> None:
        """The resolver's rule and the chapter's classification have to agree.

        Two places state the same thing -- ``RESOLVE_ONLY_KINDS`` enforces it and
        ``PORTABILITY_CLASSES`` explains it -- and a page that explained one rule while
        the code applied another would be worse than no page.
        """
        explained = {
            kind
            for item in PORTABILITY_CLASSES
            if not item.travels
            for kind in item.kinds
        }
        assert explained == set(RESOLVE_ONLY_KINDS)

    def test_a_status_list_is_never_allowed_to_travel(self) -> None:
        """A stapled status list is a stale status list.

        Called out separately from the set comparison above because this is the one that
        silently defeats revocation rather than failing loudly, and a future edit that
        moved it for convenience would look harmless.
        """
        found = class_of_kind("status-list")
        assert found is not None
        assert not found.travels

    def test_a_did_document_is_never_allowed_to_travel(self) -> None:
        """For the same reason, and with the exploit above as the evidence."""
        found = class_of_kind("did-document")
        assert found is not None
        assert not found.travels

    def test_retrieve_ignores_what_the_holder_supplied(self) -> None:
        """The mechanism underneath both, tested directly.

        ``fetch`` may prefer a supplied document; ``retrieve`` may not. Asserted at this
        level too, so the guarantee does not rest on every call site having chosen the
        right method.
        """
        world = build_world()
        url = world.store.urls_of_kind("did-document")[0]
        forgery = {"id": url, "verificationMethod": [], "note": "not the real thing"}
        resolver = Resolver(store=world.store, presented={url: forgery})

        assert resolver.retrieve(url) == world.store.get(url)
        # And `fetch` refuses it too, because the kind is resolve-only.
        assert resolver.fetch(url) == world.store.get(url)


class TestTheAuditIsAMeasurement:
    """Not an argument about portability but a count of one real verification."""

    def test_every_document_read_is_classified(self) -> None:
        """An unclassified kind is how a measurement quietly starts under-counting.

        The audit reports them rather than dropping them, so this asserts the report is
        empty rather than asserting the classifier is complete in the abstract.
        """
        audit = portability_audit(
            build_world(), now=DEMO_NOW, trusted_issuers=TRUST_ANCHORS
        )
        assert audit["unclassified"] == []

    def test_the_split_accounts_for_every_distinct_document(self) -> None:
        """The four classes partition what was read -- no gaps, no double counting."""
        audit = portability_audit(
            build_world(), now=DEMO_NOW, trusted_issuers=TRUST_ANCHORS
        )
        counted = sum(row["count"] for row in audit["split"])
        assert counted == audit["baseline"]["distinct"]

        urls = [url for row in audit["split"] for url in row["urls"]]
        assert len(urls) == len(set(urls)), "a document was put in two classes"

    def test_stapling_what_may_travel_still_verifies(self) -> None:
        """The point of the exercise: portability must not cost correctness.

        If handing the verifier everything it is allowed to accept from the holder made
        the verification fail, the whole portable-credential argument would be unavailable
        to this demonstration.
        """
        audit = portability_audit(
            build_world(), now=DEMO_NOW, trusted_issuers=TRUST_ANCHORS
        )
        assert audit["baseline"]["outcome"] == "verified"
        assert audit["stapled"]["outcome"] == "verified"

    def test_stapling_actually_reduces_what_must_be_fetched(self) -> None:
        """Compared against the live figures rather than against literals.

        The numbers move when the world grows, and a test pinning today's would either
        break for no reason or, worse, be updated without anybody rechecking the claim.
        """
        audit = portability_audit(
            build_world(), now=DEMO_NOW, trusted_issuers=TRUST_ANCHORS
        )
        assert audit["stapled"]["supplied"] > 0
        assert audit["stapled"]["stillFetched"] < audit["baseline"]["distinct"]
        assert (
            audit["baseline"]["distinct"] - audit["stapled"]["stillFetched"]
            == audit["stapled"]["supplied"]
        )

    def test_signing_the_registries_leaves_only_keys_and_revocation(self) -> None:
        """The finding this whole module was built to produce.

        Once everything that can travel has travelled and the registries are signed,
        what a verifier still has to fetch is each organisation's key and its revocation
        list, and nothing else -- which is exactly the hosting burden chapter 10 computes
        from the other direction. If this ever reports a third kind, the two chapters have
        stopped describing the same quantity and one of them is wrong.
        """
        audit = portability_audit(
            build_world(), now=DEMO_NOW, trusted_issuers=TRUST_ANCHORS
        )
        projection = audit["ifRegistriesWereSigned"]
        assert projection["kinds"] == ["did-document", "status-list"]
        assert projection["stillFetched"] < audit["stapled"]["stillFetched"]

    def test_exactly_one_class_is_removable(self) -> None:
        """Saying which reason could be engineered away is most of the value.

        Three of the four are inherent. If a second ever became removable the chapter's
        argument changes shape, and that should be a deliberate edit rather than a drift.
        """
        removable = [item.key for item in PORTABILITY_CLASSES if item.removable]
        assert removable == ["not-yet"]

    def test_the_endpoint_serves_what_the_chapter_renders(self) -> None:
        """Every field the interface reads, present and populated."""
        with TestClient(app) as client:
            data = client.get("/api/portability").json()

        assert data["credential"] == AUDIT_CREDENTIAL
        assert data["title"].startswith("https://")
        assert [item["key"] for item in data["classes"]] == [
            item.key for item in PORTABILITY_CLASSES
        ]
        for item in data["classes"]:
            assert item["label"].strip() and item["why"].strip()
        for section in ("baseline", "stapled", "ifRegistriesWereSigned"):
            assert data[section]["hostCount"] >= 1
