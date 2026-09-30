"""Parsing XML that a caller may have written, with any DTD refused.

Every XML parser in this package can be handed a caller's document. ``POST /api/verify``
takes a credential whose representations may carry XML inline, and that content reaches
the DCC reader, the UncLib and linprop readers, the verifier's reconstruction, and the
``ds:Signature`` check. A DTD is where XML's classic attacks live: entity expansion
(the billion laughs), external entities that read files or fetch URLs, and the
quadratic blowup.

Python's parsers are already hardened against most of that. The Expat they use, 2.6
here, limits entity amplification and large tokens, and neither ``minidom`` nor
``ElementTree`` resolves external entities. The request body is also capped at 256 KB.
This module is the belt with those braces (issue #71), and it costs nothing, because no
document this demonstration makes or reads has a DTD. A PTB/DKD DCC is defined by an XML
Schema, and the UncLib and linprop documents declare none either. So a document that
declares one is refused before it is parsed. That is the strictest of ``defusedxml``'s
settings (``forbid_dtd``), where its default forbids only entity declarations and
external references, and it needs no dependency.

The refusal is a first pass with Expat itself, not a search for the string
``<!DOCTYPE``. The pass decodes the document exactly as the real parse will, so a
declaration cannot hide in an encoding a text search would miss, such as UTF-16.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from xml.dom.minidom import Document, parseString
from xml.parsers import expat

__all__ = ["DTD_REFUSED", "fromstring", "parse_dom"]

#: Why a document with a DTD is refused, as its parser's error message says it.
DTD_REFUSED = (
    "the document declares a DTD, which no document here needs and which is where "
    "entity expansion and external entities live, so it is refused unparsed"
)


class _Refused(Exception):
    """Raised inside the first pass to stop it at the declaration."""


def _declares_dtd(source: str | bytes) -> bool:
    """Say whether a document declares a DTD, reading no further than the declaration.

    Args:
        source: The document, as text or bytes, exactly as it will be parsed.

    Returns:
        True when Expat meets a document type declaration. A document that is not
        well-formed returns False, so the real parse reports it in its own words.
    """

    def refuse(*_: object) -> None:
        raise _Refused

    parser = expat.ParserCreate()
    parser.StartDoctypeDeclHandler = refuse
    try:
        parser.Parse(source, True)
    except _Refused:
        return True
    except expat.ExpatError:
        return False
    return False


def parse_dom(source: str | bytes) -> Document:
    """Parse a document into a DOM, as ``xml.dom.minidom.parseString`` does.

    Args:
        source: The document, as text or bytes.

    Returns:
        The parsed document.

    Raises:
        xml.parsers.expat.ExpatError: If it declares a DTD, or is not well-formed. The
            same error type ``parseString`` raises, so callers need no new handling.
    """
    if _declares_dtd(source):
        raise expat.ExpatError(DTD_REFUSED)
    return parseString(source)


def fromstring(source: str | bytes) -> ElementTree.Element:
    """Parse a document into an element tree, as ``ElementTree.fromstring`` does.

    Args:
        source: The document, as text or bytes.

    Returns:
        The root element.

    Raises:
        xml.etree.ElementTree.ParseError: If it declares a DTD, or is not well-formed.
            The same error type ``ElementTree.fromstring`` raises, so every caller's
            existing handling applies unchanged.
    """
    if _declares_dtd(source):
        raise ElementTree.ParseError(DTD_REFUSED)
    return ElementTree.fromstring(source)
