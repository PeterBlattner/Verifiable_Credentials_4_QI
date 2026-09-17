"""Tests for the one way to name an organisation.

Two groups. The first is the vocabulary itself: what a party reference is, and what
:func:`party_id` refuses. The second is the sweep over every document the world
produces, which is the part that keeps an eighth spelling from arriving later -- it is
in this file rather than in ``test_web.py`` because it is about the documents, not about
what the server does with them.
"""

from __future__ import annotations

import pytest

from vcqi.actors.scenarios import build_world
from vcqi.party import (
    PARTY_TYPE,
    RECIPIENT_ROLES,
    party_id,
    party_in,
    party_name,
    party_reference,
)


@pytest.fixture(scope="module")
def world():
    """Build the demonstration world once for the sweep.

    Returns:
        The world, whose store holds every document this project publishes.
    """
    return build_world()


class TestTheVocabulary:
    """What a party reference is, and what is not one."""

    def test_a_reference_carries_three_members_and_no_more(self) -> None:
        """Exactly id, type and name. A fourth member is a subject node, not a reference."""
        party = party_reference("did:web:testlab.example", "Helvetia Testing Services GmbH")
        assert party == {
            "id": "did:web:testlab.example",
            "type": PARTY_TYPE,
            "name": "Helvetia Testing Services GmbH",
        }

    def test_a_bare_identifier_is_not_a_party(self) -> None:
        """The deliberate difference from ``issuer_id``, and the reason it is deliberate.

        ``issuer`` may be a string or an object because the data model says so. Nothing
        says that about ``owner`` or ``accreditationBody``, so tolerating a bare string
        here would keep two spellings legal forever -- which is the state this module
        exists to remove. A check that reads a party has to be able to tell that it did
        not get one.
        """
        assert party_id("did:web:testlab.example") is None
        assert party_name("Helvetia Testing Services GmbH") is None

    @pytest.mark.parametrize("value", [None, {}, {"name": "No identifier"}, {"id": 42}, []])
    def test_nothing_else_is_a_party_either(self, value) -> None:
        """Anything that cannot yield an identifier yields None rather than raising."""
        assert party_id(value) is None

    def test_the_recipient_is_found_under_whichever_role_names_it(self) -> None:
        """Four words, one shape. The caller does not have to know which word."""
        for role in RECIPIENT_ROLES:
            subject = {"id": "urn:thing", role: party_reference("did:web:a.example", "A")}
            found = party_in(subject)
            assert found is not None and found["id"] == "did:web:a.example"

    def test_a_subject_naming_no_recipient_yields_none(self) -> None:
        """A scope names no recipient under these roles, and that is not an error."""
        assert party_in({"id": "urn:accreditation:sas:STS-0456"}) is None

    def test_a_role_holding_a_bare_identifier_is_not_found(self) -> None:
        """Half-migrated data reads as absent rather than as a party.

        This is what makes the sweep below sound: a member that kept the old spelling
        cannot satisfy a reader that went through this module.
        """
        assert party_in({"owner": "did:web:a.example"}) is None


#: Members under which a document names an organisation it points at. The four recipient
#: roles plus the three registers' own words for who a document belongs to.
PARTY_MEMBERS = RECIPIENT_ROLES + ("accreditationBody", "organisation", "institute")


def _nodes(value):
    """Walk every dictionary inside a document.

    Args:
        value: Any part of a document.

    Yields:
        Each dictionary, the document itself included.
    """
    if isinstance(value, dict):
        yield value
        for member in value.values():
            yield from _nodes(member)
    elif isinstance(value, list):
        for member in value:
            yield from _nodes(member)


class TestEveryDocumentInTheWorld:
    """The sweep. This is what stops an eighth spelling arriving later."""

    def test_every_party_is_the_one_shape(self, world) -> None:
        """One definition of a party, in every document the world publishes."""
        seen = 0
        for address in world.store.contents():
            document = world.store.get(address)
            for node in _nodes(document):
                for member in PARTY_MEMBERS:
                    party = node.get(member)
                    if not isinstance(party, dict):
                        continue
                    seen += 1
                    assert set(party) == {"id", "type", "name"}, (
                        f"{member} in {address} carries {sorted(party)}"
                    )
                    assert party["type"] == PARTY_TYPE, (
                        f"{member} in {address} is a {party['type']}"
                    )
        assert seen > 0, "the sweep found no parties at all, so it proves nothing"

    def test_no_document_carries_a_flat_pair(self, world) -> None:
        """A `fooName` beside a `foo` is the shape this module removed.

        Two members that can disagree, with nothing comparing them, is the redundancy
        the project argues against everywhere else. Catching the shape rather than the
        four names it happened to have means a new one is caught too.
        """
        for address in world.store.contents():
            for node in _nodes(world.store.get(address)):
                for member in node:
                    assert f"{member}Name" not in node, (
                        f"{address} carries both {member} and {member}Name"
                    )

    def test_the_recognised_entity_roster_keeps_its_own_class(self, world) -> None:
        """Subjects are not references, and the sweep must not have flattened them.

        `RecognizedEntity` is a role the specification being demonstrated defines, and a
        roster has to carry `legalName` and `url` to be readable. If this ever starts
        failing because the subjects became `Organization`, the sweep has been applied
        somewhere it does not belong.
        """
        roster = world.credential("sas-recognition")["credentialSubject"]
        assert isinstance(roster, list) and roster
        for entity in roster:
            assert entity["type"] == "RecognizedEntity"
            assert entity["id"].startswith("did:web:")
