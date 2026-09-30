"""Enveloped XML signatures, for the ``ds:Signature`` slot a PTB/DKD DCC leaves open.

The DCC schema imports the W3C ``ds:Signature`` element and stops there. It does not say
which canonicalization to use, which signature algorithm, or how a verifier is supposed
to find the key -- those are left to whoever fills the slot, which is why a document
carrying both a ``ds:Signature`` and a credential ``proof`` can verify under one and fail
under the other with no rule for which wins.

What this module fills the slot with:

===========================  ===================================================
canonicalization             Canonical XML 1.1, from ``crypto/xmlc14n.py``
signature                    ECDSA P-256 with SHA-256, deterministic per RFC 6979
reference                    the whole document, minus the signature itself
key discovery                the key itself, inline, in ``ds:KeyValue``
===========================  ===================================================

**The key is inline on purpose, and it is the interesting part.** A real DCC would carry
an X.509 certificate here and a verifier would walk a chain to a certification authority.
This demonstration has no such authority, so putting a self-signed certificate in that
slot would suggest a chain that does not exist. A bare key says what is true: the
signature verifies arithmetically and tells you nothing whatever about who made it. That
is chapter 2's lesson arriving in XML, and it is the honest reason the credential around
the document is what carries the identity.

A second reason used to be given here: certificate signing in ``cryptography`` was
randomised, and this world has to build byte-for-byte identically on every run. That
stopped being true in 45.0, whose ``CertificateBuilder.sign`` takes
``ecdsa_deterministic``, so the choice rests on the first reason, which is enough.

**This is an XMLDSig-shaped subset, not a verifier for signed DCCs in the wild.** It
implements the one profile in the table above and nothing else. A DCC signed by other
tooling will usually differ: exclusive canonicalization, RSA, another digest, a
reference to an ID, a key in an X.509 certificate. :func:`verify_enveloped` reads what a
signature declares, and when that is outside the profile it reports the signature as
*unsupported* and checks nothing. Reporting a digest mismatch instead would read as
tampering, and it would be a statement about this module rather than the document.

Unsupported is not a loophole. Anyone able to alter the document can equally delete the
signature, which is reported as absent. And a credential that points at the document
carries its own digest of the bytes, which is where tampering is caught.

The profile is also why signature wrapping does not apply. The one reference is to the
whole document, ``URI=""``, so nothing is selected by an identifier an attacker could
move.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from xml.dom.minidom import Document, Element

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from vcqi.crypto.ecdsa_p256 import P256, sign_deterministic
from vcqi.crypto.keys import DemoKey
from vcqi.crypto.xmlc14n import ALGORITHM as C14N_ALGORITHM
from vcqi.crypto.xmlc14n import canonicalize, parse

__all__ = [
    "C14N_ALGORITHM",
    "DIGEST_ALGORITHM",
    "ENVELOPED_TRANSFORM",
    "SIGNATURE_ALGORITHM",
    "SignatureReport",
    "sign_enveloped",
    "verify_enveloped",
]

#: The W3C XML Signature namespace, which is where ds:Signature comes from.
DS_NAMESPACE = "http://www.w3.org/2000/09/xmldsig#"

#: XML Signature 1.1, which is where an elliptic-curve key value comes from.
DS11_NAMESPACE = "http://www.w3.org/2009/xmldsig11#"

_XMLNS_NAMESPACE = "http://www.w3.org/2000/xmlns/"

#: ECDSA with SHA-256, from RFC 4051.
SIGNATURE_ALGORITHM = "http://www.w3.org/2001/04/xmldsig-more#ecdsa-sha256"

#: SHA-256, from XML Encryption.
DIGEST_ALGORITHM = "http://www.w3.org/2001/04/xmlenc#sha256"

#: The transform that takes the signature back out of what it is signing.
ENVELOPED_TRANSFORM = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"

#: NIST P-256, named by the object identifier XML Signature 1.1 uses for it.
NAMED_CURVE = "urn:oid:1.2.840.10045.3.1.7"


@dataclass(frozen=True)
class SignatureReport:
    """What a verifier found when it checked a ``ds:Signature``.

    Attributes:
        present: Whether the document carried a signature at all.
        digest_matches: Whether the document still hashes to the recorded DigestValue.
        signature_matches: Whether SignedInfo verifies under the key the signature
            carries.
        key_discovery: How the key was found, as something a report can print.
        detail: One sentence describing the outcome.
        supported: Whether the signature declares the profile this module implements.
            When it does not, nothing was checked, and both matches are False because
            nothing was compared, not because anything failed to match.
    """

    present: bool
    digest_matches: bool
    signature_matches: bool
    key_discovery: str
    detail: str
    supported: bool = True

    @property
    def verified(self) -> bool:
        """Whether both halves held.

        Returns:
            True only when a signature was present, the document still matches its
            digest, and that digest's SignedInfo verifies.
        """
        return self.present and self.digest_matches and self.signature_matches


def _text(document: Document, parent: Element, name: str, value: str) -> Element:
    """Append a ds element carrying text.

    Args:
        document: The owning document.
        parent: The element to append to.
        name: The qualified name, for example ``ds:DigestValue``.
        value: The text content.

    Returns:
        The element created.
    """
    element = document.createElementNS(DS_NAMESPACE, name)
    element.appendChild(document.createTextNode(value))
    parent.appendChild(element)
    return element


def _element(document: Document, parent: Element, name: str) -> Element:
    """Append an empty ds element.

    Args:
        document: The owning document.
        parent: The element to append to.
        name: The qualified name.

    Returns:
        The element created.
    """
    element = document.createElementNS(DS_NAMESPACE, name)
    parent.appendChild(element)
    return element


def _signature_element(document: Document) -> Element | None:
    """Find the enveloped signature, if the document has one.

    Args:
        document: The parsed document.

    Returns:
        The first ``ds:Signature`` child of the document element, or None. Only a direct
        child counts: a signature further down would be signing something else.
    """
    for child in document.documentElement.childNodes:
        if (
            child.nodeType == child.ELEMENT_NODE
            and child.namespaceURI == DS_NAMESPACE
            and child.localName == "Signature"
        ):
            return child
    return None


def _child(parent: Element, local_name: str) -> Element | None:
    """Return the first ds child with a given local name.

    Args:
        parent: The element to search.
        local_name: The local name to look for.

    Returns:
        The element, or None.
    """
    for child in parent.childNodes:
        if (
            child.nodeType == child.ELEMENT_NODE
            and child.namespaceURI == DS_NAMESPACE
            and child.localName == local_name
        ):
            return child
    return None


def _children(parent: Element | None, local_name: str) -> list[Element]:
    """Return every ds child with a given local name.

    Args:
        parent: The element to search, or None.
        local_name: The local name to look for.

    Returns:
        The elements in document order, empty when there is no parent.
    """
    if parent is None:
        return []
    return [
        child
        for child in parent.childNodes
        if child.nodeType == child.ELEMENT_NODE
        and child.namespaceURI == DS_NAMESPACE
        and child.localName == local_name
    ]


def _algorithm(element: Element | None) -> str:
    """Return the Algorithm an element declares.

    Args:
        element: The element, or None.

    Returns:
        The attribute's value, empty when there is no element or no attribute.
    """
    return element.getAttribute("Algorithm") if element is not None else ""


def _unsupported(signature: Element, signed_info: Element) -> str | None:
    """Say what a signature declares that this module does not implement.

    Checked in the order a verifier would process them, so the first difference named is
    the one that would have stopped it. The transform list has to match exactly:
    ``enveloped-signature`` alone would leave the default canonicalization, which is
    Canonical XML 1.0 rather than 1.1.

    Args:
        signature: The ``ds:Signature`` element.
        signed_info: Its ``ds:SignedInfo``.

    Returns:
        A phrase naming the first unsupported choice, to follow "the ds:Signature uses",
        or None when the signature declares exactly the profile implemented here.
    """
    canonicalization = _algorithm(_child(signed_info, "CanonicalizationMethod"))
    if canonicalization != C14N_ALGORITHM:
        return f"the canonicalization {canonicalization or '(none declared)'}"

    method = _algorithm(_child(signed_info, "SignatureMethod"))
    if method != SIGNATURE_ALGORITHM:
        return f"the signature method {method or '(none declared)'}"

    references = _children(signed_info, "Reference")
    if len(references) != 1:
        return f"{len(references)} references, where one is implemented"
    reference = references[0]
    uri = reference.getAttribute("URI") if reference.hasAttribute("URI") else None
    if uri != "":
        where = "no URI" if uri is None else f"the URI {uri!r}"
        return (
            f"a reference with {where}, where only the whole document, "
            'URI="", is implemented'
        )

    transforms = [
        _algorithm(transform)
        for transform in _children(_child(reference, "Transforms"), "Transform")
    ]
    if transforms != [ENVELOPED_TRANSFORM, C14N_ALGORITHM]:
        return f"the transforms {', '.join(transforms) or '(none declared)'}"

    digest = _algorithm(_child(reference, "DigestMethod"))
    if digest != DIGEST_ALGORITHM:
        return f"the digest {digest or '(none declared)'}"

    key_info = _child(signature, "KeyInfo")
    if key_info is None:
        return "no ds:KeyInfo, where only an inline dsig11:ECKeyValue is implemented"
    ec_key_value = _descendant(key_info, DS11_NAMESPACE, "ECKeyValue")
    if ec_key_value is None:
        # Named by what is inside a ds:KeyValue, since "KeyValue" alone would not say
        # whether it is RSA or DSA.
        given: list[str] = []
        for child in key_info.childNodes:
            if child.nodeType != child.ELEMENT_NODE:
                continue
            inner = [
                node.localName
                for node in child.childNodes
                if node.nodeType == node.ELEMENT_NODE
            ]
            if child.localName == "KeyValue" and inner:
                given.extend(inner)
            else:
                given.append(child.localName)
        return (
            f"a key given as {', '.join(given) or 'nothing'}, where only an inline "
            "dsig11:ECKeyValue is implemented"
        )
    curve = _descendant(ec_key_value, DS11_NAMESPACE, "NamedCurve")
    named = curve.getAttribute("URI") if curve is not None else ""
    if named != NAMED_CURVE:
        return f"the curve {named or '(none named)'}"
    return None


def _descendant(parent: Element, namespace: str, local_name: str) -> Element | None:
    """Return the first descendant with a given namespace and local name.

    Args:
        parent: The element to search.
        namespace: The namespace URI to match.
        local_name: The local name to match.

    Returns:
        The element, or None.
    """
    for element in parent.getElementsByTagNameNS(namespace, local_name):
        return element
    return None


def _content(element: Element | None) -> str:
    """Return an element's text content with surrounding whitespace removed.

    Args:
        element: The element, or None.

    Returns:
        The text, empty when there is no element.
    """
    if element is None:
        return ""
    return "".join(
        node.data for node in element.childNodes if node.nodeType == node.TEXT_NODE
    ).strip()


def _public_key_bytes(key: DemoKey) -> bytes:
    """Return the uncompressed EC point for a key, as ECKeyValue carries it.

    Args:
        key: The signing key.

    Returns:
        The point as ``0x04 || X || Y``.
    """
    return key.private_key.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )


def sign_enveloped(xml: str, key: DemoKey) -> str:
    """Add an enveloped ``ds:Signature`` to a document.

    The signature is appended as the last child of the document element and covers the
    whole document with itself taken back out, which is what the enveloped transform
    means and why the reference URI is empty.

    Args:
        xml: The document to sign.
        key: The signing key. Only its private scalar and public point are used; the
            identifier it belongs to is deliberately not recorded in the signature,
            because ``ds:KeyValue`` has nowhere to put one.

    Returns:
        The signed document as text.
    """
    document = parse(xml)
    root = document.documentElement

    signature = document.createElementNS(DS_NAMESPACE, "ds:Signature")
    signature.setAttributeNS(_XMLNS_NAMESPACE, "xmlns:ds", DS_NAMESPACE)
    root.appendChild(signature)

    signed_info = _element(document, signature, "ds:SignedInfo")
    _element(document, signed_info, "ds:CanonicalizationMethod").setAttribute(
        "Algorithm", C14N_ALGORITHM
    )
    _element(document, signed_info, "ds:SignatureMethod").setAttribute(
        "Algorithm", SIGNATURE_ALGORITHM
    )

    reference = _element(document, signed_info, "ds:Reference")
    reference.setAttribute("URI", "")
    transforms = _element(document, reference, "ds:Transforms")
    _element(document, transforms, "ds:Transform").setAttribute(
        "Algorithm", ENVELOPED_TRANSFORM
    )
    _element(document, transforms, "ds:Transform").setAttribute(
        "Algorithm", C14N_ALGORITHM
    )
    _element(document, reference, "ds:DigestMethod").setAttribute(
        "Algorithm", DIGEST_ALGORITHM
    )

    # The reference digest is over the document with the signature removed -- which is
    # the whole of what "enveloped" means, and the reason the signature can sit inside
    # what it signs without chasing its own tail.
    digest = hashlib.sha256(canonicalize(document, omit=(signature,))).digest()
    _text(document, reference, "ds:DigestValue", base64.b64encode(digest).decode("ascii"))

    raw = sign_deterministic(
        key.private_key.private_numbers().private_value, canonicalize(signed_info)
    )
    _text(
        document, signature, "ds:SignatureValue", base64.b64encode(raw).decode("ascii")
    )

    key_info = _element(document, signature, "ds:KeyInfo")
    key_value = _element(document, key_info, "ds:KeyValue")
    ec_key_value = document.createElementNS(DS11_NAMESPACE, "dsig11:ECKeyValue")
    ec_key_value.setAttributeNS(_XMLNS_NAMESPACE, "xmlns:dsig11", DS11_NAMESPACE)
    key_value.appendChild(ec_key_value)
    named_curve = document.createElementNS(DS11_NAMESPACE, "dsig11:NamedCurve")
    named_curve.setAttribute("URI", NAMED_CURVE)
    ec_key_value.appendChild(named_curve)
    public_key = document.createElementNS(DS11_NAMESPACE, "dsig11:PublicKey")
    public_key.appendChild(
        document.createTextNode(base64.b64encode(_public_key_bytes(key)).decode("ascii"))
    )
    ec_key_value.appendChild(public_key)

    return document.toxml(encoding="utf-8").decode("utf-8")


def verify_enveloped(xml: str) -> SignatureReport:
    """Check the enveloped signature on a document.

    Args:
        xml: The document to check.

    Returns:
        What was found. A missing or malformed signature comes back as a report rather
        than an exception, because a verifier meets these documents as untrusted input
        and the pipeline wants to say what was wrong rather than stop.
    """
    try:
        document = parse(xml)
    except Exception:  # noqa: BLE001 - any parse failure is one outcome to the caller
        return SignatureReport(
            present=False,
            digest_matches=False,
            signature_matches=False,
            key_discovery="none",
            detail="the document could not be parsed",
        )

    signature = _signature_element(document)
    if signature is None:
        return SignatureReport(
            present=False,
            digest_matches=False,
            signature_matches=False,
            key_discovery="none",
            detail="the document carries no ds:Signature",
        )

    signed_info = _child(signature, "SignedInfo")
    # Before anything is hashed: a signature made to another profile would otherwise be
    # reported as a mismatch, which reads as tampering and is not.
    unsupported = None if signed_info is None else _unsupported(signature, signed_info)
    if unsupported is not None:
        return SignatureReport(
            present=True,
            digest_matches=False,
            signature_matches=False,
            key_discovery="not attempted",
            detail=(
                f"the ds:Signature uses {unsupported}, which this demonstration "
                "does not implement, so it was not checked, and that says nothing "
                "either way about the document"
            ),
            supported=False,
        )

    reference = _child(signed_info, "Reference") if signed_info is not None else None
    recorded = _content(_child(reference, "DigestValue")) if reference is not None else ""
    if signed_info is None or not recorded:
        return SignatureReport(
            present=True,
            digest_matches=False,
            signature_matches=False,
            key_discovery="none",
            detail="the ds:Signature is missing its SignedInfo or its DigestValue",
        )

    digest = hashlib.sha256(canonicalize(document, omit=(signature,))).digest()
    digest_matches = base64.b64encode(digest).decode("ascii") == recorded

    encoded = _content(_descendant(signature, DS11_NAMESPACE, "PublicKey"))
    if not encoded:
        return SignatureReport(
            present=True,
            digest_matches=digest_matches,
            signature_matches=False,
            key_discovery="none",
            detail="the ds:Signature carries no key to check it with",
        )

    try:
        point = base64.b64decode(encoded, validate=True)
        public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
        raw = base64.b64decode(_content(_child(signature, "SignatureValue")), validate=True)
        if len(raw) != 2 * P256.size:
            raise ValueError("signature is not 64 bytes")
        public_key.verify(
            encode_dss_signature(
                int.from_bytes(raw[: P256.size], "big"),
                int.from_bytes(raw[P256.size :], "big"),
            ),
            canonicalize(signed_info),
            ec.ECDSA(hashes.SHA256()),
        )
        signature_matches = True
    except (InvalidSignature, ValueError, TypeError):
        signature_matches = False

    if digest_matches and signature_matches:
        detail = (
            "the ds:Signature verifies, with the key it carries inline -- which says "
            "nothing about whose key it is"
        )
    elif not digest_matches:
        detail = "the document no longer matches the digest recorded in its ds:Signature"
    else:
        detail = "the ds:SignedInfo does not verify under the key the signature carries"

    return SignatureReport(
        present=True,
        digest_matches=digest_matches,
        signature_matches=signature_matches,
        key_discovery="ds:KeyValue, inline, with no certificate chain",
        detail=detail,
    )
