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

The third group is about the one class that cannot travel. It checks that the roster of
status lists is read back out of what the world published, that every credential is on
one of them, and that withdrawing a certificate changes no byte of the certificate --
which is the whole of why the list has to be fetched rather than carried.
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
    revocation_audit,
)
from vcqi.actors.registry import TRUST_ANCHORS, actor_key
from vcqi.actors.scenarios import DEMO_NOW, build_world
from vcqi.actors.tamper import tamper_by_key
from vcqi.crypto.dataintegrity import sign_document
from vcqi.crypto.jcs import canonicalize
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


class TestTheRegisterThatMoved:
    """The accreditation scopes left the fourth class, and the rule did not change.

    Nothing here relaxes ``RESOLVE_ONLY_KINDS``. What made a scope unportable was that
    an unsigned document cannot be checked, and the scopes stopped being unsigned: the
    body that granted them signs them, and the credentials citing them pin the digest.
    The kind stayed where it was and the documents moved, which is the only safe way
    round -- relaxing the kind would have taken the KCDB with it.
    """

    def test_a_signed_scope_is_published_as_a_credential(self) -> None:
        """Its store kind is what decides whether it may travel."""
        world = build_world()
        assert (
            world.store.kind_of("https://sas.example/accreditation/SCS-0123")
            == "credential"
        )

    def test_the_unportable_class_is_now_only_the_kcdb(self) -> None:
        """One register signed, one not, and the count is the price of the difference."""
        audit = portability_audit(
            build_world(), now=DEMO_NOW, trusted_issuers=TRUST_ANCHORS
        )
        not_yet = next(row for row in audit["split"] if row["key"] == "not-yet")
        assert not_yet["urls"] == ["https://bipm.example/kcdb/cmc/CH-EM-0042"]

    def test_the_rule_itself_is_untouched(self) -> None:
        """``registry-entry`` is still resolve-only, and must stay so.

        Moving the kind rather than the documents would have let an unsigned CMC entry
        arrive from the holder, which is the forgery the class exists to stop.
        """
        assert "registry-entry" in RESOLVE_ONLY_KINDS

    def test_a_scope_the_holder_supplies_is_used(self) -> None:
        """The point of signing it: the verifier no longer has to reach the register."""
        world = build_world()
        url = "https://sas.example/accreditation/SCS-0123"
        scope = world.store.get(url)
        assert scope is not None

        report = verify_credential(
            world.credentials["callab-calibration"],
            store=world.store,
            now=DEMO_NOW,
            trusted_issuers=TRUST_ANCHORS,
            presented=[scope],
        )
        assert report.outcome == "verified"
        record = next(entry for entry in report.fetches if entry["url"] == url)
        assert record["source"] == "presented"

    def test_a_substituted_scope_is_refused_even_from_the_publisher(self) -> None:
        """The digest pins the version, which is what an unsigned entry could not offer.

        Kept next to the stapled-DID-document exploit because it is the same shape of
        question -- which document said so -- answered by a different mechanism.
        """
        case = tamper_by_key("substituted-scope")
        assert case is not None
        result = case.apply()
        report = verify_credential(
            result.credential,
            store=result.world.store,
            now=result.verify_at,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert report.outcome == "rejected"
        assert [step.id for step in report.failures] == ["scope"]


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


class TestTheRevocationAudit:
    """The one document a holder may not carry, counted rather than described."""

    def test_every_published_list_is_in_the_roster(self) -> None:
        """Read back out of the store, so a tenth list cannot appear unreported."""
        world = build_world()
        audit = revocation_audit(world)
        assert {item["url"] for item in audit["lists"]} == set(
            world.store.urls_of_kind("status-list")
        )
        assert audit["listCount"] == len(audit["lists"])

    def test_every_credential_is_on_a_list_that_exists(self) -> None:
        """Nothing points at a status list nobody publishes.

        The audit attributes a credential to a list by the address the credential names,
        so a typo in one would show up here as a credential counted in the total and
        present on no list.
        """
        audit = revocation_audit(build_world())
        attributed = sum(item["covered"] for item in audit["lists"])
        assert attributed == audit["covered"]
        assert audit["covered"] > 0

    def test_no_credential_in_this_world_is_unrevocable(self) -> None:
        """A credential carrying no status entry passes the status step by definition.

        ``check_status`` has nothing to check when there is no ``credentialStatus``, so
        an issuer that omits one has issued something it can never withdraw. That is a
        legitimate reading of the data model and a poor property for a calibration
        certificate, and this asserts the world never does it.
        """
        assert revocation_audit(build_world())["unlisted"] == []

    def test_no_list_is_smaller_than_the_specification_requires(self) -> None:
        """The floor is what makes one list a crowd rather than a pointer.

        A verifier downloads the whole list and reads one bit out of it locally, so the
        retrieval says which issuer is being asked about and not which credential. That
        only holds while the list is large, which is why the minimum is normative and why
        it is measured here by decompressing what was actually published.
        """
        audit = revocation_audit(build_world())
        for item in audit["lists"]:
            assert item["positions"] >= audit["minimumListLength"], item["url"]

    def test_the_bytes_reported_are_the_bytes_that_travel(self) -> None:
        """Measured off the published document, not estimated from the bitstring."""
        world = build_world()
        audit = revocation_audit(world)
        for item in audit["lists"]:
            document = world.store.get(item["url"])
            assert document is not None
            assert item["documentBytes"] == len(canonicalize(document))
        assert audit["documentBytes"] == sum(
            item["documentBytes"] for item in audit["lists"]
        )

    def test_the_whole_revocation_state_weighs_less_than_one_certificate(self) -> None:
        """The figure the chapter leads with, compared live rather than pinned.

        Every status list this world publishes, covering every credential in it, comes to
        less than the one calibration certificate the laboratory issued. Both sides are
        computed, so the claim follows the world instead of dating.
        """
        world = build_world()
        audit = revocation_audit(world)
        certificate = len(canonicalize(world.credential("callab-calibration")))
        assert audit["documentBytes"] < certificate

    def test_the_endpoint_serves_what_the_chapter_renders(self) -> None:
        """Every field the interface reads, present and populated."""
        with TestClient(app) as client:
            data = client.get("/api/revocation").json()

        assert data["listCount"] == len(data["lists"])
        assert data["covered"] > 0
        assert data["positions"] > 0
        assert data["documentBytes"] > 0
        for item in data["lists"]:
            assert item["url"].startswith("https://")
            assert item["issuer"].startswith("did:web:")
            assert item["issuerName"].strip()
            assert item["purpose"] in {"revocation", "suspension"}
            assert item["description"].strip()
            assert item["positions"] >= data["minimumListLength"]


class TestWithdrawalChangesNothingAboutTheDocument:
    """Why the list is fetched and not carried, stated as an equality on bytes."""

    def test_withdrawing_a_certificate_changes_no_byte_of_it(self) -> None:
        """The demonstration chapter 12 runs, asserted on the canonical form.

        Both cases leave the credential exactly as the laboratory signed it. One flips a
        bit on the laboratory's own revocation list and the other on the accreditation
        body's suspension list, and the verdict changes in both. If a future edit made
        either case modify the credential, the section would be showing something else
        and still look right.
        """
        base = canonicalize(build_world().credential("callab-calibration"))

        for key in ("revoked-certificate", "suspended-accreditation"):
            case = tamper_by_key(key)
            assert case is not None
            result = case.apply()
            assert canonicalize(result.credential) == base, key

            report = verify_credential(
                result.credential,
                store=result.world.store,
                now=result.verify_at,
                trusted_issuers=TRUST_ANCHORS,
            )
            assert report.outcome == "rejected", key
            assert case.expected_step in [step.id for step in report.failures], key

    def test_the_two_withdrawals_are_caught_by_different_steps(self) -> None:
        """One is about this document; the other about the right to have issued it.

        Worth pinning, because the section says so in words: the laboratory's own list is
        read by the top-level status step, while a suspension one link up the chain is
        only reached while the chain is being walked.
        """
        assert tamper_by_key("revoked-certificate").expected_step == "status"
        assert tamper_by_key("suspended-accreditation").expected_step == "recognition"
