"""Tests for refusing DTDs wherever XML is parsed (issue #71).

Three things are pinned. A document declaring a DTD is refused, whatever the DTD holds
and however the document is encoded. A document without one parses exactly as it did.
And every parse site in the package goes through ``vcqi.xmlsafe``, so a new one cannot
quietly bypass it.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from xml.dom.minidom import parseString
from xml.parsers import expat

import pytest

from vcqi import xmlsafe
from vcqi.crypto.xmldsig import verify_enveloped
from vcqi.domain.dcc import parse_dcc_administrative, parse_dcc_result
from vcqi.domain.external_dcc import external_dcc_source
from vcqi.domain.linprop import ustorage
from vcqi.domain.uncertainty import parse_input_quantities
from vcqi.vc.verify import _reconstruct

PACKAGE = Path(__file__).resolve().parent.parent / "src" / "vcqi"

_LAUGHS = "".join(
    f'<!ENTITY lol{level} "{f"&lol{level - 1};" * 10}">' for level in range(1, 10)
)

#: What a DTD can be used for, and one that is used for nothing at all.
WITH_A_DTD = {
    "entity expansion": (
        f'<?xml version="1.0"?>\n<!DOCTYPE lolz [<!ENTITY lol0 "lol">{_LAUGHS}]>\n'
        "<lolz>&lol9;</lolz>"
    ),
    "an external entity": (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>\n<r>&x;</r>'
    ),
    "an external DTD": '<!DOCTYPE r SYSTEM "https://attacker.example/r.dtd">\n<r/>',
    "a bare declaration": "<!DOCTYPE r>\n<r/>",
}


@pytest.mark.parametrize("document", WITH_A_DTD.values(), ids=WITH_A_DTD.keys())
class TestADtdIsRefused:
    """Before anything in it is read, and as each parser's own error."""

    def test_by_the_dom_parser(self, document: str) -> None:
        """The error minidom raises, so ``xmlc14n.parse``'s callers need nothing new."""
        with pytest.raises(expat.ExpatError, match="declares a DTD"):
            xmlsafe.parse_dom(document)

    def test_by_the_element_tree_parser(self, document: str) -> None:
        """The error ElementTree raises, which every caller already turns into its own."""
        with pytest.raises(ElementTree.ParseError, match="declares a DTD"):
            xmlsafe.fromstring(document)

    def test_as_bytes_too(self, document: str) -> None:
        """Both parsers take bytes, and the refusal must not depend on which is given."""
        with pytest.raises(ElementTree.ParseError, match="declares a DTD"):
            xmlsafe.fromstring(document.encode("utf-8"))


def test_an_encoding_does_not_hide_the_declaration() -> None:
    """In UTF-16 the bytes of ``<!DOCTYPE`` never appear, and it is still refused.

    This is why the first pass is Expat rather than a search for the string.
    """
    document = '<?xml version="1.0" encoding="UTF-16"?>\n<!DOCTYPE r>\n<r/>'.encode(
        "utf-16"
    )
    assert b"<!DOCTYPE" not in document
    with pytest.raises(ElementTree.ParseError, match="declares a DTD"):
        xmlsafe.fromstring(document)
    with pytest.raises(expat.ExpatError, match="declares a DTD"):
        xmlsafe.parse_dom(document)


class TestADocumentWithoutOneIsUntouched:
    """The refusal costs no legitimate document anything."""

    def test_the_dkd_example_parses_as_it_did(self) -> None:
        """The one document here produced by someone else's tooling."""
        source = external_dcc_source()
        assert xmlsafe.parse_dom(source).toxml() == parseString(source).toxml()
        ours, theirs = xmlsafe.fromstring(source), ElementTree.fromstring(source)
        assert ElementTree.tostring(ours) == ElementTree.tostring(theirs)

    def test_a_malformed_document_is_reported_in_the_parser_s_own_words(self) -> None:
        """The first pass stays out of the way of an ordinary syntax error."""
        with pytest.raises(ElementTree.ParseError) as ours:
            xmlsafe.fromstring("<r>")
        with pytest.raises(ElementTree.ParseError) as theirs:
            ElementTree.fromstring("<r>")
        assert str(ours.value) == str(theirs.value)


@pytest.mark.parametrize(
    "reader",
    [
        parse_dcc_result,
        parse_dcc_administrative,
        parse_input_quantities,
        ustorage.from_xml_string,
        _reconstruct,
    ],
    ids=lambda reader: reader.__qualname__,
)
def test_every_reader_refuses_it(reader) -> None:
    """Each reader a caller's XML can reach, refusing it as its ordinary ValueError."""
    with pytest.raises(ValueError, match="declares a DTD"):
        reader(WITH_A_DTD["entity expansion"])


def test_the_signature_check_reports_it_rather_than_raising() -> None:
    """``verify_enveloped`` meets untrusted input and says what was wrong."""
    report = verify_enveloped(WITH_A_DTD["an external entity"])
    assert not report.present
    assert "could not be parsed" in report.detail


def test_nothing_in_the_package_parses_xml_any_other_way() -> None:
    """So a parse site added later cannot quietly bypass the refusal."""
    direct = re.compile(
        r"\b(?:ElementTree\.(?:fromstring|XML|parse|iterparse|XMLParser)"
        r"|parseString|minidom\.parse|expat\.ParserCreate)\("
    )
    offenders = [
        f"{path.relative_to(PACKAGE)}:{number}"
        for path in sorted(PACKAGE.rglob("*.py"))
        if path.name != "xmlsafe.py"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if direct.search(line)
    ]
    assert offenders == []
