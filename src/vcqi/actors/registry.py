"""The organisations that populate the demonstration and the keys they sign with.

The set is chosen to show both halves of the quality infrastructure meeting in one
supply chain. On the metrology side the BIPM anchors the CIPM MRA and national
metrology institutes calibrate against it. On the conformity assessment side Global ACI
anchors its own arrangement and an accreditation body accredits the laboratories and
the certification body beneath it. A manufacturer holds the resulting credentials and a
market surveillance authority in an importing country is the party that has to decide
whether to believe them, having no prior relationship with anybody in the chain.

Every organisation is fictional and uses a domain under the reserved ``.example``
top-level domain. The keys are derived from a published seed and secure nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from vcqi.crypto.keys import DemoKey, build_did_document, derive_key

__all__ = [
    "Actor",
    "ACTORS",
    "TRUST_ANCHORS",
    "actor_by_did",
    "actor_key",
    "did_web_domain",
    "whois_url",
    "did_document",
]


@dataclass(frozen=True)
class Actor:
    """One organisation in the demonstration.

    Attributes:
        did: The decentralized identifier the organisation signs with.
        name: Short display name.
        legal_name: Full name as it would appear on a document.
        role: The part the organisation plays in the quality infrastructure.
        country: ISO 3166 alpha-2 code, or an empty string for an international body.
        description: One sentence on what the organisation does here.
        issues: Short description of what it issues, or an empty string if it issues
            nothing and only receives and verifies credentials.
    """

    did: str
    name: str
    legal_name: str
    role: str
    country: str
    description: str
    issues: str = ""

    @property
    def domain(self) -> str:
        """Return the domain encoded in the DID.

        Returns:
            The host part, for example ``metas.example``.
        """
        return did_web_domain(self.did)

    @property
    def url(self) -> str:
        """Return the website of the organisation.

        Returns:
            The origin corresponding to the DID.
        """
        return f"https://{self.domain}/"

    def to_json(self) -> dict[str, Any]:
        """Return the organisation as the interface displays it.

        Returns:
            A JSON-compatible dictionary, including the public key so a reader can see
            that a DID is nothing more than a name that resolves to a key.
        """
        return {
            "id": self.did,
            "name": self.name,
            "legalName": self.legal_name,
            "role": self.role,
            "country": self.country,
            "description": self.description,
            "issues": self.issues,
            "url": self.url,
            "domain": self.domain,
            "publicKeyMultibase": actor_key(self.did).public_key_multibase,
            "isTrustAnchor": self.did in TRUST_ANCHORS,
        }


#: Every organisation in the demonstration, in the order the trust graph reads.
ACTORS: tuple[Actor, ...] = (
    Actor(
        did="did:web:bipm.example",
        name="BIPM",
        legal_name="International Bureau of Weights and Measures (demonstration)",
        role="Metrology trust anchor",
        country="",
        description=(
            "Maintains the key comparison database and records which national "
            "metrology institutes participate in the CIPM MRA and for what."
        ),
        issues="Recognition of national metrology institutes, and CMC entries",
    ),
    Actor(
        did="did:web:global-aci.example",
        name="Global ACI",
        legal_name="Global Accreditation Cooperation Incorporated (demonstration)",
        role="Accreditation trust anchor",
        country="",
        description=(
            "Formed on 1 January 2026 when the IAF and ILAC consolidated into one body. "
            "Records which accreditation bodies are signatories to its multilateral "
            "recognition arrangement, and for which standards."
        ),
        issues="Recognition of accreditation bodies",
    ),
    Actor(
        did="did:web:metas.example",
        name="METAS",
        legal_name="Federal Institute of Metrology (demonstration)",
        role="National metrology institute",
        country="CH",
        description=(
            "Realises the national measurement standards and calibrates the reference "
            "standards of accredited laboratories against them."
        ),
        issues="Calibration certificates carrying the CIPM MRA logo",
    ),
    Actor(
        did="did:web:ptb.example",
        name="PTB",
        legal_name="National Metrology Institute of Germany (demonstration)",
        role="National metrology institute",
        country="DE",
        description=(
            "A second institute recognised under the same arrangement, which is what "
            "makes the recognition mutual rather than merely hierarchical."
        ),
        issues="Calibration certificates carrying the CIPM MRA logo",
    ),
    Actor(
        did="did:web:sas.example",
        name="SAS",
        legal_name="Swiss Accreditation Service (demonstration)",
        role="Accreditation body",
        country="CH",
        description=(
            "Assesses laboratories and certification bodies against ISO/IEC 17025 and "
            "ISO/IEC 17065 and grants them a defined scope."
        ),
        issues="Accreditation of laboratories and certification bodies",
    ),
    Actor(
        did="did:web:callab.example",
        name="Alpine Calibration",
        legal_name="Alpine Calibration Laboratory AG (demonstration)",
        role="Accredited calibration laboratory",
        country="CH",
        description=(
            "Holds a certificate from the national institute for its own transfer "
            "standard, and issues calibration certificates to its customers."
        ),
        issues="Accredited calibration certificates",
    ),
    Actor(
        did="did:web:testlab.example",
        name="Helvetia Testing",
        legal_name="Helvetia Testing Services GmbH (demonstration)",
        role="Accredited testing laboratory",
        country="CH",
        description=(
            "Tests products against product standards using equipment whose "
            "calibration it must be able to demonstrate."
        ),
        issues="Accredited test reports",
    ),
    Actor(
        did="did:web:cab.example",
        name="Confoederatio Certification",
        legal_name="Confoederatio Product Certification AG (demonstration)",
        role="Conformity assessment body",
        country="CH",
        description=(
            "The conformity assessment body of the Product Conformity use case: it "
            "certifies that a product meets a standard, on the strength of test reports."
        ),
        issues="Certificates of conformity",
    ),
    Actor(
        did="did:web:manufacturer.example",
        name="Acme Appliances",
        legal_name="Acme Appliances AG (demonstration)",
        role="Manufacturer",
        country="CH",
        description=(
            "Holds the certificate of conformity for its product and presents it when "
            "the product crosses a border."
        ),
    ),
    Actor(
        did="did:web:surveillance.example",
        name="Market surveillance",
        legal_name="Importing Market Surveillance Authority (demonstration)",
        role="Verifier",
        country="XX",
        description=(
            "Has no relationship with anyone upstream, trusts only the two "
            "international anchors, and has to decide whether to clear the goods."
        ),
    ),
)

#: The identifiers the verifier is configured to trust directly. Everything else has to
#: be reached from one of these by following recognition, which is the entire point.
TRUST_ANCHORS: frozenset[str] = frozenset(
    {"did:web:bipm.example", "did:web:global-aci.example"}
)

_BY_DID = {actor.did: actor for actor in ACTORS}


def did_web_domain(did: str) -> str:
    """Return the domain encoded in a did:web identifier.

    Args:
        did: A ``did:web`` identifier.

    Returns:
        The host part, with any path segments joined by slashes.

    Raises:
        ValueError: If the identifier is not a did:web identifier.
    """
    prefix = "did:web:"
    if not did.startswith(prefix):
        raise ValueError(f"{did!r} is not a did:web identifier")
    return did[len(prefix) :].replace(":", "/")


def whois_url(did: str) -> str:
    """Return the endpoint at which an actor publishes a description of itself.

    Recognized Entities calls this a WhoisService. It is what identifier-based
    discovery dereferences when a verifier has an issuer identifier but no recognition
    credential to go with it.

    Args:
        did: The actor identifier.

    Returns:
        The service endpoint URL.
    """
    return f"https://{did_web_domain(did)}/whois"


def actor_by_did(did: str) -> Actor | None:
    """Look up an organisation by identifier.

    Args:
        did: The actor identifier.

    Returns:
        The organisation, or None when the identifier is not one of the demonstration
        actors. A verifier meeting an unknown identifier must not invent a party for
        it, so the absent case is returned rather than raised.
    """
    return _BY_DID.get(did)


@lru_cache(maxsize=None)
def actor_key(did: str) -> DemoKey:
    """Return the signing key of an organisation.

    Args:
        did: The actor identifier.

    Returns:
        The deterministic demonstration key pair. Derivation is cached because the
        scenario signs many documents with the same handful of keys.
    """
    return derive_key(did)


def did_document(did: str) -> dict[str, Any]:
    """Build the DID document an actor publishes.

    Args:
        did: The actor identifier.

    Returns:
        The DID document, advertising a whois service so that both discovery
        mechanisms described in Recognized Entities can be demonstrated.
    """
    return build_did_document(actor_key(did), whois_endpoint=whois_url(did))
