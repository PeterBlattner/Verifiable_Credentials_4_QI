"""One way to name an organisation inside a document.

Before this module there were seven of them. A party could be a flat pair of members
(``organisation`` beside ``organisationName``), a ``{id, name}`` object, a
``{id, type, name}`` object, a richer subject node, or a bare identifier string, and
which one you got depended on which file had written the document.

The rule is a distinction rather than a preference:

* A document that **points at** an organisation carries a party reference -- exactly
  ``id``, ``type`` and ``name``, and nothing else. :func:`party_reference` builds it.
* A document that **is about** an organisation carries a subject node with the class
  that credential type requires, and may say more. ``RecognizedEntity`` in a recognition
  credential is the example, and it keeps its ``legalName``, ``url`` and ``description``
  because a roster has to be readable.

So ``type`` always names the role the organisation plays *in this document*, and
``Organization`` is what is left when the role is "this party and nothing more". That is
also why ``issuer_reference`` keeps ``RecognizedIssuer``: it is a role the specification
being demonstrated defines, not one this project invented.

**Why an object rather than a flat pair**, given that under ``ecdsa-jcs-2019`` nothing is
dereferenced and the choice is invisible today. The two forms fail differently if the
contexts are ever made resolvable, which ARCHITECTURE.md says a real deployment must do.
``{"id": "did:web:testlab.example"}`` needs one term definition to denote the laboratory
as a node. ``"did:web:testlab.example"`` needs a term definition *and* an
``"@type": "@id"`` coercion, and with only the first it quietly becomes a string literal
-- a document asserting that the laboratory's name is the characters
``did:web:testlab.example``. The node form survives a half-written context; the flat form
is silently wrong under one.

The flat pair has a second cost. Two members that can disagree, with nothing comparing
them, is the redundancy this project argues against everywhere else. Folding the name
into the node removes the disagreement rather than checking for it.

Two members are deliberately *not* party references, and both are recorded here so they
read as decisions rather than omissions:

* ``recognizedBy`` in a ``RecognizedAction`` stays a bare identifier. It is a
  specification member whose whole purpose is the case where it differs from the issuer,
  and a member kept for fidelity to a specification keeps that specification's spelling.
* ``Instrument.manufacturer`` stays a free string. Tinsley and Fluke are not parties in
  this world -- no identifier, no key, nothing to point at -- and making them nodes would
  mean minting identifiers for organisations that are not actors.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

__all__ = [
    "PARTY_TYPE",
    "RECIPIENT_ROLES",
    "party_reference",
    "party_id",
    "party_name",
    "party_in",
]

#: The class a party reference carries. ``Organization`` is schema.org's, which makes it
#: one of the few terms in this demonstration that was not invented for it.
PARTY_TYPE = "Organization"

#: The members under which a document names the organisation it was issued to. They are
#: four different words because they mean four different things -- the *applicant* is a
#: defined position in the OIML-CS, the *holder* of a certificate of conformity is a
#: legal one -- and collapsing them to one word would delete the distinction the legal
#: metrology branch exists to show. What is collapsed is the shape, not the role.
#:
#: This tuple exists so the list is written down once. It used to be repeated in
#: ``web/app.py``, which is the kind of second copy that goes stale quietly.
RECIPIENT_ROLES: tuple[str, ...] = ("owner", "client", "holder", "applicant")


def party_reference(identifier: str, name: str) -> dict[str, Any]:
    """Name an organisation a document points at.

    Args:
        identifier: The organisation's identifier, as a single URL. Every party in this
            demonstration is a ``did:web:`` identifier, but the data model requires only
            a URL, so nothing here depends on it being a DID.
        name: The organisation's name as it would appear on a document, which in this
            project is the legal name rather than the short one.

    Returns:
        The reference: ``id``, ``type`` and ``name``, and nothing else.
    """
    return {"id": identifier, "type": PARTY_TYPE, "name": name}


def party_id(value: Any) -> str | None:
    """Return the identifier of a party reference.

    A bare string is **not** a party and returns None. This is the one place the module
    differs deliberately from ``issuer_id`` in :mod:`vcqi.vc.checks`, which accepts both
    forms because the Verifiable Credentials data model genuinely allows ``issuer`` to
    be either. Nothing says that about ``owner`` or ``accreditationBody``: those are this
    project's own terms, and one term gets one spelling. Tolerating the old form here
    would leave two spellings legal forever, which is the state being removed.

    Args:
        value: The member to read, whatever it turned out to be.

    Returns:
        The identifier, or None when the value is not a party reference.
    """
    if isinstance(value, Mapping):
        identifier = value.get("id")
        if isinstance(identifier, str):
            return identifier
    return None


def party_name(value: Any) -> str | None:
    """Return the name of a party reference.

    Args:
        value: The member to read.

    Returns:
        The name, or None when the value is not a party reference or carries none.
    """
    if isinstance(value, Mapping):
        name = value.get("name")
        if isinstance(name, str):
            return name
    return None


def party_in(
    node: Mapping[str, Any], roles: Sequence[str] = RECIPIENT_ROLES
) -> dict[str, Any] | None:
    """Return the organisation a document was issued to.

    Args:
        node: The credential subject, or any node that might name a recipient.
        roles: Members to look under, in order. Defaults to :data:`RECIPIENT_ROLES`.

    Returns:
        The first party reference found, or None when the node names no recipient.
    """
    for role in roles:
        candidate = node.get(role)
        if party_id(candidate) is not None:
            return dict(candidate)
    return None
