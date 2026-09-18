"""Re-issue a credential in a form somebody else's verifier can actually check.

Every credential in this project has so far been checked only by the verifier in this
same repository. :func:`vcqi.vc.verify.verify_credential` was written alongside
:func:`vcqi.crypto.dataintegrity.sign_document`, which means a shared misreading of the
specification would pass unnoticed in both. The way to find out is to hand a credential
to an implementation that shares none of our assumptions.

Two things stop that today, and only one of them is fixable here. The first is the
network: every organisation in the demonstration is a ``did:web`` under a reserved
``.example`` domain, so an outside verifier asked to resolve ``did:web:metas.example``
gets nothing, and the signature check fails before it begins. The second is the
JSON-LD context, which is also fictional; that one needs a genuinely hosted document
and is not addressed here.

The first has a clean answer. A ``did:key`` needs no lookup at all, because the
identifier *is* the public key -- the same argument
:func:`vcqi.vc.resolver.did_key_document` already makes, and it applies as much to an
outside verifier as to this one. So a portable copy is the same credential, signed with
the same key, under the identifier that key stands for on its own.

What that costs is exactly what the resolver docstring lists, and it is worth being
blunt about it: the copy names a key rather than an organisation. Nobody accredited a
key. The recognition chain the original carries still points at ``did:web`` identifiers,
so on the portable copy it hangs from a hook that is no longer there. That is not a
defect in the copy; it is the whole reason the organisations here use ``did:web`` in the
first place. The portable copy answers one question -- does this signature verify
somewhere else -- and deliberately answers no other.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from vcqi.crypto.dataintegrity import ProofTrace, sign_document
from vcqi.crypto.keys import DemoKey
from vcqi.vc.resolver import DID_KEY_PREFIX


def as_did_key(key: DemoKey) -> DemoKey:
    """Return the same key pair under its ``did:key`` identifier.

    No new key material is derived. The private key is untouched and the public key is
    untouched; only the name changes, from one the world has to publish to one that
    needs no publishing.

    Args:
        key: The organisation's signing key.

    Returns:
        A key pair whose ``verification_method_id`` is the ``did:key`` DID URL, matching
        the method identifier :func:`vcqi.vc.resolver.did_key_document` builds.
    """
    multikey = key.public_key_multibase
    return replace(key, did=f"{DID_KEY_PREFIX}{multikey}", fragment=multikey)


def portable_copy(
    credential: dict[str, Any],
    key: DemoKey,
    *,
    created: datetime,
) -> tuple[dict[str, Any], ProofTrace]:
    """Re-issue a credential under the ``did:key`` form of its own signing key.

    The claims are copied unchanged. Only the issuer identifier moves, and because the
    issuer identifier is covered by the signature, the credential has to be signed
    again -- with the same key, so the arithmetic an outside verifier performs is the
    arithmetic this project performs.

    ``recognizedIn`` is left in place rather than stripped. It now points at a
    recognition credential that names the ``did:web`` identifier this copy no longer
    uses, so the chain does not close. Removing it would hide that; leaving it makes the
    price of ``did:key`` visible in the document itself.

    Args:
        credential: The signed credential to copy. Its existing proof is discarded.
        key: The key that signed the original, as returned by
            :func:`vcqi.actors.registry.actor_key`.
        created: When the new proof was created.

    Returns:
        A tuple of the portable credential and the trace of intermediate values.

    Raises:
        ValueError: If the credential names no issuer, or if the key does not belong to
            the issuer it names.
    """
    issuer = credential.get("issuer")
    issuer_did = issuer.get("id") if isinstance(issuer, dict) else issuer
    if not isinstance(issuer_did, str):
        raise ValueError("credential names no issuer to move")
    if issuer_did != key.did:
        raise ValueError(
            f"credential is issued by {issuer_did}, but the key belongs to {key.did}"
        )

    portable_key = as_did_key(key)
    copy = {name: value for name, value in credential.items() if name != "proof"}
    copy["issuer"] = (
        {**issuer, "id": portable_key.did} if isinstance(issuer, dict) else portable_key.did
    )
    return sign_document(copy, portable_key, created=created)
