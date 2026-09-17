"""Tests for the one way to name an organisation.

Two groups. The first is the vocabulary itself: what a party reference is, and what
:func:`party_id` refuses. The second is the sweep over every document the world
produces, which is the part that keeps an eighth spelling from arriving later -- it is
in this file rather than in ``test_web.py`` because it is about the documents, not about
what the server does with them.
"""

from __future__ import annotations

import pytest

from vcqi.party import (
    PARTY_TYPE,
    RECIPIENT_ROLES,
    party_id,
    party_in,
    party_name,
    party_reference,
)


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
