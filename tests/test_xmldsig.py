"""Tests for the enveloped XML signature.

What these can and cannot establish is worth being plain about. They establish that this
implementation is self-consistent, deterministic, and that each of the four ways a
signature can be wrong is actually caught. They do **not** establish interoperability:
no independent XML Signature implementation is installed here to check a document
against, so a systematic error shared between the signer and the verifier would pass
everything below. ``ARCHITECTURE.md`` records that, and the cheapest way to close it is
to hand one of these documents to someone with ``xmlsec1``.
"""

from __future__ import annotations

import base64
import hashlib
import re

import pytest

from vcqi.crypto.keys import derive_key
from vcqi.crypto.xmlc14n import canonicalize, parse
from vcqi.crypto.xmldsig import (
    C14N_ALGORITHM,
    DIGEST_ALGORITHM,
    ENVELOPED_TRANSFORM,
    SIGNATURE_ALGORITHM,
    sign_enveloped,
    verify_enveloped,
)

DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<dcc:digitalCalibrationCertificate xmlns:dcc="https://ptb.de/dcc" '
    'xmlns:si="https://ptb.de/si" schemaVersion="3.4.0-rc.2">'
    "<dcc:administrativeData><dcc:coreData>"
    "<dcc:uniqueIdentifier>METAS-2026-0420</dcc:uniqueIdentifier>"
    "</dcc:coreData></dcc:administrativeData>"
    "<dcc:measurementResults><dcc:measurementResult>"
    "<si:real><si:value>100.001502</si:value><si:unit>\\ohm</si:unit></si:real>"
    "</dcc:measurementResult></dcc:measurementResults>"
    "</dcc:digitalCalibrationCertificate>"
)


@pytest.fixture(scope="module")
def key():
    """The institute's demonstration key.

    Returns:
        A deterministic P-256 key pair.
    """
    return derive_key("did:web:metas.example")


@pytest.fixture(scope="module")
def signed(key) -> str:
    """The document, signed once for every test that only reads it.

    Args:
        key: The signing key.

    Returns:
        The signed document.
    """
    return sign_enveloped(DOCUMENT, key)


class TestTheSignatureItProduces:
    """Shape, and the algorithm identifiers a reader would check first."""

    def test_the_signature_verifies(self, signed: str) -> None:
        """The round trip, which everything else is a variation on."""
        report = verify_enveloped(signed)
        assert report.verified
        assert report.present and report.digest_matches and report.signature_matches

    def test_it_names_the_algorithms_it_actually_used(self, signed: str) -> None:
        """A wrong identifier here is a silent lie to any other implementation."""
        assert f'Algorithm="{C14N_ALGORITHM}"' in signed
        assert f'Algorithm="{SIGNATURE_ALGORITHM}"' in signed
        assert f'Algorithm="{DIGEST_ALGORITHM}"' in signed
        assert f'Algorithm="{ENVELOPED_TRANSFORM}"' in signed

    def test_the_reference_is_to_the_whole_document(self, signed: str) -> None:
        """An empty URI is what says "everything around me"."""
        assert 'URI=""' in signed

    def test_the_signature_sits_inside_what_it_signs(self, signed: str) -> None:
        """Enveloped, not enveloping and not detached."""
        document = parse(signed)
        children = [
            child.localName
            for child in document.documentElement.childNodes
            if child.nodeType == child.ELEMENT_NODE
        ]
        assert children[-1] == "Signature"

    def test_the_digest_is_over_the_document_without_the_signature(
        self, signed: str
    ) -> None:
        """Recomputed here from first principles rather than trusting the verifier.

        If this and ``verify_enveloped`` were both wrong in the same way, the test above
        would still pass and this one would not.
        """
        document = parse(signed)
        signature = [
            child
            for child in document.documentElement.childNodes
            if child.nodeType == child.ELEMENT_NODE and child.localName == "Signature"
        ][0]
        expected = base64.b64encode(
            hashlib.sha256(canonicalize(document, omit=(signature,))).digest()
        ).decode("ascii")
        assert f"<ds:DigestValue>{expected}</ds:DigestValue>" in signed

    def test_signing_the_same_document_twice_gives_the_same_bytes(self, key) -> None:
        """RFC 6979 again, and the reason the world can be built reproducibly."""
        assert sign_enveloped(DOCUMENT, key) == sign_enveloped(DOCUMENT, key)

    def test_two_keys_give_two_signatures(self, key) -> None:
        """Determinism is not sameness."""
        other = derive_key("did:web:callab.example")
        assert sign_enveloped(DOCUMENT, key) != sign_enveloped(DOCUMENT, other)


class TestTheFourWaysItCanBeWrong:
    """Each failure, and that it is caught for the reason claimed."""

    def test_an_edited_value_breaks_the_digest(self, signed: str) -> None:
        """The case the signature exists for."""
        report = verify_enveloped(signed.replace("100.001502", "100.001503"))
        assert not report.verified
        assert not report.digest_matches
        assert "no longer matches the digest" in report.detail

    def test_an_edited_administrative_field_breaks_it_too(self, signed: str) -> None:
        """The reference covers the whole document, not only the result."""
        report = verify_enveloped(signed.replace("METAS-2026-0420", "METAS-2026-0421"))
        assert not report.digest_matches

    def test_an_edited_signature_value_fails_the_signature_not_the_digest(
        self, signed: str
    ) -> None:
        """The two halves fail separately, and the report says which.

        Editing SignatureValue leaves the document matching its DigestValue perfectly
        well; what stops verifying is SignedInfo under the key.
        """
        document = parse(signed)
        value = document.getElementsByTagName("ds:SignatureValue")[0]
        original = value.firstChild.data
        flipped = ("B" if original[0] != "B" else "C") + original[1:]
        report = verify_enveloped(signed.replace(original, flipped))
        assert report.digest_matches
        assert not report.signature_matches
        assert not report.verified

    def test_a_substituted_key_fails(self, key) -> None:
        """Anyone can sign anything; the arithmetic is not the question.

        The signature is remade with a different key and the public key put back, which
        is exactly what an attacker who could not steal the key would try.
        """
        theirs = sign_enveloped(DOCUMENT, derive_key("did:web:callab.example"))
        mine = sign_enveloped(DOCUMENT, key)
        my_key = mine.split("<dsig11:PublicKey>")[1].split("</dsig11:PublicKey>")[0]
        their_key = theirs.split("<dsig11:PublicKey>")[1].split("</dsig11:PublicKey>")[0]
        assert not verify_enveloped(theirs.replace(their_key, my_key)).signature_matches

    def test_an_unsigned_document_is_reported_not_raised(self) -> None:
        """A verifier meets these as untrusted input and has to keep going."""
        report = verify_enveloped(DOCUMENT)
        assert not report.present
        assert not report.verified
        assert "no ds:Signature" in report.detail

    def test_an_unparseable_document_is_reported_not_raised(self) -> None:
        """Same reason."""
        report = verify_enveloped("<not-xml")
        assert not report.present
        assert "could not be parsed" in report.detail


def test_the_key_arrives_with_no_chain_and_the_report_says_so(signed: str) -> None:
    """The point of the whole exercise, asserted rather than left to the prose.

    A ``ds:Signature`` verifying is not a document being trustworthy. What this one
    carries is a bare public key: no certificate, no issuer, no revocation path. The
    credential wrapped around the document is what supplies all three, and that is the
    argument for signing once rather than twice.
    """
    report = verify_enveloped(signed)
    assert report.verified
    assert "no certificate chain" in report.key_discovery
    assert "X509" not in signed


#: A signature made to another profile, as other tooling would make it, and the words
#: the report has to use for it. Each pattern changes one declared choice of the
#: signature this module makes, and nothing else.
OTHER_PROFILES = {
    "exclusive canonicalization": (
        r'(<ds:CanonicalizationMethod Algorithm=")[^"]*',
        r"\1http://www.w3.org/2001/10/xml-exc-c14n#",
        "xml-exc-c14n",
    ),
    "RSA": (
        r'(<ds:SignatureMethod Algorithm=")[^"]*',
        r"\1http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
        "rsa-sha256",
    ),
    "a second reference": (
        r"(</ds:Reference>)",
        r'\1<ds:Reference URI="#annex"><ds:DigestValue>AA==</ds:DigestValue></ds:Reference>',
        "2 references",
    ),
    "a reference to an ID": (r'<ds:Reference URI=""', '<ds:Reference URI="#cert"', "#cert"),
    "a reference with no URI": (r'<ds:Reference URI=""', "<ds:Reference", "no URI"),
    "the enveloped transform alone, which means C14N 1.0": (
        r'<ds:Transform Algorithm="http://www.w3.org/2006/12/xml-c14n11"/>',
        "",
        "the transforms http://www.w3.org/2000/09/xmldsig#enveloped-signature",
    ),
    "another digest": (
        r'(<ds:DigestMethod Algorithm=")[^"]*',
        r"\1http://www.w3.org/2001/04/xmlenc#sha512",
        "sha512",
    ),
    "a key in an X.509 certificate": (
        r"<ds:KeyValue>.*</ds:KeyValue>",
        "<ds:X509Data><ds:X509Certificate>MIIB</ds:X509Certificate></ds:X509Data>",
        "X509Data",
    ),
    "an RSA key": (
        r"<dsig11:ECKeyValue.*</dsig11:ECKeyValue>",
        "<ds:RSAKeyValue><ds:Modulus>AQAB</ds:Modulus>"
        "<ds:Exponent>AQAB</ds:Exponent></ds:RSAKeyValue>",
        "RSAKeyValue",
    ),
    "another curve": (
        r'(<dsig11:NamedCurve URI=")[^"]*',
        r"\1urn:oid:1.3.132.0.34",
        "urn:oid:1.3.132.0.34",
    ),
}


class TestWhatItDoesNotImplement:
    """A signature made to another profile is unsupported, not a mismatch (#71).

    Before, each of these came back as a digest or signature mismatch, which a reader
    could take for tampering, when all it said was that this module does not implement
    what the signer chose.
    """

    @pytest.mark.parametrize(
        ("pattern", "replacement", "named"),
        OTHER_PROFILES.values(),
        ids=OTHER_PROFILES.keys(),
    )
    def test_it_is_reported_as_unsupported(
        self, signed: str, pattern: str, replacement: str, named: str
    ) -> None:
        """Present, unchecked, and the report names what the signature declared."""
        other = re.sub(pattern, replacement, signed, count=1, flags=re.DOTALL)
        assert other != signed
        report = verify_enveloped(other)
        assert report.present
        assert not report.supported
        assert not report.verified
        assert "does not implement" in report.detail
        assert named in report.detail
        assert report.key_discovery == "not attempted"

    def test_the_profile_it_implements_is_supported(self, signed: str) -> None:
        """The control: the signature it makes is one it can check."""
        report = verify_enveloped(signed)
        assert report.supported
        assert report.verified

    def test_tampering_within_the_profile_is_still_a_mismatch(self, signed: str) -> None:
        """Unsupported is about the declaration, not a softer word for a failure."""
        report = verify_enveloped(signed.replace("100.001502", "100.001503"))
        assert report.supported
        assert not report.digest_matches
