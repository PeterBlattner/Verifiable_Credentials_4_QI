"""The network, as far as a verifier in this demonstration can tell.

Verification is a retrieval problem as much as a cryptographic one. To check a
certificate a verifier has to resolve the identifier of its issuer to a key, fetch the
recognition credential the issuer points at, fetch the schema that recognition names,
and fetch the registry entry that bounds it. Each of those is a network round trip in a
real deployment, and each is a place where something can be missing, stale or
substituted.

Rather than hide that behind direct dictionary lookups, everything published in the
demonstration goes into a :class:`DocumentStore` addressed by URL, and every retrieval
goes through a :class:`Resolver` that records what was asked for and where the answer
came from. The interface can then show the reader the verifier's own retrieval log,
which makes the cost of a chain visible and shows what stapling upstream credentials to
a presentation actually saves.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ec

from vcqi.crypto.keys import public_key_from_multikey

__all__ = ["DocumentStore", "Resolver", "FetchRecord", "did_key_document", "DID_KEY_PREFIX"]


@dataclass(frozen=True)
class FetchRecord:
    """One retrieval attempted during verification.

    Attributes:
        url: What was asked for.
        kind: What sort of document it turned out to be, or ``unknown`` when nothing
            was found.
        found: Whether anything was returned.
        source: ``presented`` when the holder supplied the document alongside the
            credential, ``retrieved`` when the verifier had to go and get it.
    """

    url: str
    kind: str
    found: bool
    source: str

    def to_json(self) -> dict[str, Any]:
        """Return the record as a JSON-compatible dictionary.

        Returns:
            The url, kind, outcome and source of the retrieval.
        """
        return {"url": self.url, "kind": self.kind, "found": self.found, "source": self.source}


DID_KEY_PREFIX = "did:key:"


def did_key_document(did: str) -> dict[str, Any] | None:
    """Build the DID document a did:key identifier stands for.

    A did:key needs no lookup at all, because the identifier *is* the public key: strip
    the prefix and what remains is the Multikey. Nothing is fetched, nothing can be
    stale, and nothing can be substituted on the way.

    The cost is everything the demonstration otherwise relies on. The key can never be
    rotated, because changing it changes the identifier and therefore the party. It
    cannot carry a name, a website, or a service endpoint. And a recognition credential
    naming it is naming a key rather than an organisation, which is not what an
    accreditation body wants to say. So the organisations here use did:web and the
    reader making a key on the keys page gets a did:key, and the difference between
    those two lines is worth more than either on its own.

    Args:
        did: The identifier to expand.

    Returns:
        The equivalent DID document, or None when this is not a did:key.
    """
    if not did.startswith(DID_KEY_PREFIX):
        return None
    multikey = did[len(DID_KEY_PREFIX) :]
    if not multikey:
        return None
    method_id = f"{did}#{multikey}"
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/multikey/v1",
        ],
        "id": did,
        "verificationMethod": [
            {
                "id": method_id,
                "type": "Multikey",
                "controller": did,
                "publicKeyMultibase": multikey,
            }
        ],
        "assertionMethod": [method_id],
        "authentication": [method_id],
    }


class DocumentStore:
    """Everything published in the demonstration world, addressed by URL or DID."""

    def __init__(self) -> None:
        """Create an empty store."""
        self._documents: dict[str, dict[str, Any]] = {}
        self._kinds: dict[str, str] = {}

    def publish(self, url: str, document: dict[str, Any], kind: str) -> None:
        """Publish a document at an address.

        Args:
            url: The address, which may be an https URL or a DID.
            document: The document to publish.
            kind: What sort of document it is, for example ``credential``,
                ``did-document``, ``schema`` or ``registry-entry``.
        """
        self._documents[url] = document
        self._kinds[url] = kind

    def get(self, url: str) -> dict[str, Any] | None:
        """Retrieve a document.

        Args:
            url: The address to retrieve.

        Returns:
            The document, or None when nothing is published there.
        """
        return self._documents.get(url)

    def kind_of(self, url: str) -> str:
        """Return what sort of document is published at an address.

        Args:
            url: The address.

        Returns:
            The kind, or ``unknown`` when nothing is published there.
        """
        return self._kinds.get(url, "unknown")

    def urls_of_kind(self, kind: str) -> list[str]:
        """List every address holding a given sort of document.

        Args:
            kind: The kind to filter by.

        Returns:
            The matching addresses, in publication order.
        """
        return [url for url, value in self._kinds.items() if value == kind]

    def contents(self) -> dict[str, dict[str, Any]]:
        """Return every published document.

        Returns:
            A copy of the mapping from address to document.
        """
        return dict(self._documents)


@dataclass
class Resolver:
    """Retrieves documents on behalf of a verifier, recording every attempt.

    Attributes:
        store: What is published in the world.
        presented: Documents the holder supplied alongside the credential, indexed by
            identifier. Recognized Entities allows a holder to bundle the recognition
            credentials its own credential depends on, which spares the verifier the
            round trips at the cost of the verifier having to accept their freshness.
        log: Every retrieval attempted, in order.
    """

    store: DocumentStore
    presented: dict[str, dict[str, Any]] = field(default_factory=dict)
    log: list[FetchRecord] = field(default_factory=list)

    @classmethod
    def with_presented(
        cls, store: DocumentStore, documents: Sequence[dict[str, Any]]
    ) -> Resolver:
        """Build a resolver that prefers documents supplied by the holder.

        Args:
            store: What is published in the world.
            documents: Documents bundled with the presentation. Any document without an
                identifier is ignored, since it could not be matched to a reference.

        Returns:
            The resolver.
        """
        indexed = {
            document["id"]: document
            for document in documents
            if isinstance(document, dict) and isinstance(document.get("id"), str)
        }
        return cls(store=store, presented=indexed)

    def fetch(self, url: str) -> dict[str, Any] | None:
        """Retrieve a document, preferring one the holder supplied.

        Args:
            url: The address to retrieve.

        Returns:
            The document, or None when it cannot be found. A missing document is never
            treated as permission to skip a check.
        """
        document = self.presented.get(url)
        if document is not None:
            self.log.append(
                FetchRecord(url=url, kind=self.store.kind_of(url), found=True, source="presented")
            )
            return document

        document = self.store.get(url)
        self.log.append(
            FetchRecord(
                url=url,
                kind=self.store.kind_of(url),
                found=document is not None,
                source="retrieved",
            )
        )
        return document

    def resolve_did_document(self, did: str) -> dict[str, Any] | None:
        """Resolve an identifier to the document that describes it.

        Args:
            did: The identifier to resolve.

        Returns:
            The DID document, or None when the identifier does not resolve.
        """
        # A did:key carries its own key, so there is nothing to go and get. Resolving it
        # locally is not a shortcut; it is what the method means.
        local = did_key_document(did)
        if local is not None:
            self.log.append(
                FetchRecord(url=did, kind="did-document", found=True, source="self-describing")
            )
            return local
        return self.fetch(did)

    def resolve_public_key(
        self, verification_method_id: str
    ) -> ec.EllipticCurvePublicKey | None:
        """Resolve a verification method to the key it publishes.

        The method identifier is a DID URL: the part before the fragment names the
        controller, and the fragment names one of its keys. A verifier must take the
        key from the controller named by the credential, never from the credential
        itself, or the signature proves nothing.

        Args:
            verification_method_id: The DID URL from a proof.

        Returns:
            The public key, or None when the controller does not resolve or does not
            publish that method.
        """
        controller, _, _ = verification_method_id.partition("#")
        document = self.resolve_did_document(controller)
        if document is None:
            return None

        for method in document.get("verificationMethod", []):
            if not isinstance(method, dict) or method.get("id") != verification_method_id:
                continue
            multibase = method.get("publicKeyMultibase")
            if not isinstance(multibase, str):
                return None
            try:
                return public_key_from_multikey(multibase)
            except ValueError:
                return None
        return None

    def assertion_methods(self, did: str) -> list[str]:
        """List the verification methods an identifier allows for asserting claims.

        A key published for authentication is not thereby authorised to sign
        credentials, so the purpose recorded in the DID document has to be checked
        against the purpose recorded in the proof.

        Args:
            did: The identifier of the controller.

        Returns:
            The identifiers of its assertion methods, empty when it resolves to
            nothing or authorises none.
        """
        document = self.resolve_did_document(did)
        if document is None:
            return []
        methods = document.get("assertionMethod", [])
        return [method for method in methods if isinstance(method, str)]

    def authentication_methods(self, did: str) -> list[str]:
        """List the verification methods an identifier allows for authenticating.

        The mirror of :meth:`assertion_methods`, and needed for the same reason in the
        other direction: a key published only for signing credentials is not thereby
        authorised to prove who is holding them. A presentation is an authentication,
        so its proof has to name a key the controller published for that purpose.

        Args:
            did: The identifier of the controller.

        Returns:
            The identifiers of its authentication methods, empty when it resolves to
            nothing or authorises none.
        """
        document = self.resolve_did_document(did)
        if document is None:
            return []
        methods = document.get("authentication", [])
        return [method for method in methods if isinstance(method, str)]

    def reset_log(self) -> None:
        """Discard the retrieval log, so a fresh verification starts from empty."""
        self.log.clear()
