"""Canonical XML 1.1, for the signature slot a PTB/DKD DCC carries.

A signature is made over bytes, and an XML document does not have a single set of bytes
any more than a JSON one does: the same document can be written with different attribute
order, different namespace prefixes, different whitespace, and empty elements written
either way. So before anything is hashed it is put into a canonical form, and that is
what gets signed. This is the XML counterpart of ``crypto/jcs.py``, and it is here for
the same reason: the signing path is the thing being explained, and a reader should be
able to follow it without leaving the repository.

The rules that do the work:

* elements are written with a start and an end tag, never as ``<x/>``;
* namespace declarations come first, ordered by prefix, and one is emitted only when it
  differs from what an ancestor already put in the output;
* attributes follow, ordered by namespace URI and then by local name;
* text and attribute values are escaped to a fixed set of character references;
* comments are dropped.

**Why 1.1 rather than 1.0.** They differ in exactly two places, both of which only show
up when canonicalizing a *subset* of a document whose apex is not the root -- which is
precisely what happens to ``ds:SignedInfo``. Version 1.1 composes ``xml:base`` from the
ancestors rather than inheriting the nearest one, and it stops inheriting ``xml:id``,
which is unique to an element and was never sensible to copy downward. On a document
carrying neither attribute the two versions produce identical bytes, and there is a test
that says so.

**Inclusive, not exclusive.** A subset apex renders every namespace declaration in scope,
including ones nothing in the subset uses. That is what "inclusive" means, and it is the
reason exclusive canonicalization was later invented. It is correct here and it is
visible: canonicalizing ``ds:SignedInfo`` inside a PTB/DKD DCC pulls ``xmlns:dcc`` and
``xmlns:si`` along with it.
"""

from __future__ import annotations

from urllib.parse import urljoin
from xml.dom import Node
from xml.dom.minidom import Document, Element, parseString

__all__ = ["ALGORITHM", "canonicalize", "parse"]

#: The algorithm identifier this module implements, as it appears in a ds:Signature.
ALGORITHM = "http://www.w3.org/2006/12/xml-c14n11"

_XMLNS_NAMESPACE = "http://www.w3.org/2000/xmlns/"
_XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"

#: Attributes in the xml namespace that a subset apex inherits from its ancestors.
#: ``xml:base`` is composed rather than inherited and is handled separately; ``xml:id``
#: is deliberately absent, which is one of the two differences between 1.1 and 1.0.
_INHERITED = ("xml:lang", "xml:space")

_CARRIAGE_RETURN = chr(13)


def parse(source: str | bytes) -> Document:
    """Parse a document with namespace processing, ready to canonicalize.

    Args:
        source: The XML document, as text or as UTF-8 bytes.

    Returns:
        The parsed document.
    """
    if isinstance(source, str):
        source = source.encode("utf-8")
    return parseString(source)


def _escape_text(value: str) -> str:
    """Escape a text node for the canonical form.

    A carriage return survives only as a character reference, because the parser has
    already turned every literal one into a line feed. Escaping it here is what stops a
    document changing meaning when it crosses a system that rewrites line endings.

    Args:
        value: The text to escape.

    Returns:
        The escaped text.
    """
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace(_CARRIAGE_RETURN, "&#xD;")
    )


def _escape_attribute(value: str) -> str:
    """Escape an attribute value for the canonical form.

    Args:
        value: The attribute value to escape.

    Returns:
        The escaped value.
    """
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace('"', "&quot;")
        .replace("\t", "&#x9;")
        .replace("\n", "&#xA;")
        .replace(_CARRIAGE_RETURN, "&#xD;")
    )


def _own_namespaces(element: Element) -> dict[str, str]:
    """Return the namespace declarations made on this element itself.

    Args:
        element: The element to inspect.

    Returns:
        A mapping of prefix to namespace URI, the default namespace keyed by ``""``.
    """
    declarations: dict[str, str] = {}
    for index in range(element.attributes.length):
        attribute = element.attributes.item(index)
        if attribute.namespaceURI != _XMLNS_NAMESPACE:
            continue
        prefix = "" if attribute.prefix is None else attribute.localName
        declarations[prefix] = attribute.value
    return declarations


def _in_scope_namespaces(element: Element) -> dict[str, str]:
    """Return every namespace declaration in scope at an element.

    Walks outwards, so a declaration on the element itself wins over one further up.

    Args:
        element: The element to inspect.

    Returns:
        A mapping of prefix to namespace URI, with undeclarations removed.
    """
    scope: dict[str, str] = {}
    node: Node | None = element
    while node is not None and node.nodeType == Node.ELEMENT_NODE:
        for prefix, uri in _own_namespaces(node).items():
            scope.setdefault(prefix, uri)
        node = node.parentNode
    return {prefix: uri for prefix, uri in scope.items() if uri}


def _compose_base(values: list[str]) -> str:
    """Compose a chain of ``xml:base`` values into one.

    Args:
        values: The values in document order, outermost first.

    Returns:
        The composed base URI.
    """
    composed = values[0]
    for value in values[1:]:
        composed = urljoin(composed, value)
    return composed


def _inherited_xml_attributes(element: Element) -> dict[str, str]:
    """Return the xml-namespace attributes a subset apex inherits.

    ``xml:lang`` and ``xml:space`` are inherited from the nearest ancestor that states
    them. ``xml:base`` is composed from every ancestor that states one, which is the
    substantive change 1.1 made to 1.0. ``xml:id`` is not inherited at all, which is the
    other one.

    Args:
        element: The apex of the subset being canonicalized.

    Returns:
        A mapping of qualified name to value, covering only attributes the apex does not
        state for itself.
    """
    inherited: dict[str, str] = {}
    bases: list[str] = []

    node: Node | None = element.parentNode
    while node is not None and node.nodeType == Node.ELEMENT_NODE:
        for name in _INHERITED:
            if node.hasAttribute(name) and name not in inherited:
                inherited[name] = node.getAttribute(name)
        if node.hasAttribute("xml:base"):
            bases.append(node.getAttribute("xml:base"))
        node = node.parentNode

    for name in list(inherited):
        if element.hasAttribute(name):
            del inherited[name]

    if bases:
        # Outermost first, with the apex's own value applied last, which is the order a
        # reader resolving the base URI would go in.
        composed = bases[::-1]
        if element.hasAttribute("xml:base"):
            composed.append(element.getAttribute("xml:base"))
        inherited["xml:base"] = _compose_base(composed)
    return inherited


def _attribute_sort_key(name: str, namespace: str, local: str) -> tuple[str, str]:
    """Return the canonical ordering key for an attribute.

    Args:
        name: The qualified name, used only when the parser gave no local name.
        namespace: The attribute's namespace URI, empty when it is in none.
        local: The attribute's local name.

    Returns:
        The pair the canonical order sorts on, so that an attribute in no namespace
        comes before any that is in one.
    """
    return (namespace, local or name)


def _sorted_attributes(element: Element) -> list[tuple[str, str]]:
    """Return an element's non-namespace attributes in canonical order.

    Args:
        element: The element to inspect.

    Returns:
        ``(qualified name, value)`` pairs in canonical order.
    """
    attributes: list[tuple[tuple[str, str], str, str]] = []
    for index in range(element.attributes.length):
        attribute = element.attributes.item(index)
        if attribute.namespaceURI == _XMLNS_NAMESPACE:
            continue
        key = _attribute_sort_key(
            attribute.name, attribute.namespaceURI or "", attribute.localName or ""
        )
        attributes.append((key, attribute.name, attribute.value))
    attributes.sort(key=lambda item: item[0])
    return [(name, value) for _, name, value in attributes]


def _merge_apex_attributes(
    attributes: list[tuple[str, str]], inherited: dict[str, str]
) -> list[tuple[str, str]]:
    """Fold a subset apex's inherited xml attributes in with its own.

    Args:
        attributes: The apex's own attributes, already in canonical order.
        inherited: The xml-namespace attributes it inherits.

    Returns:
        The combined attributes in canonical order. An inherited attribute is in the xml
        namespace by construction, so it sorts after everything in no namespace.
    """
    merged = dict(attributes)
    for name, value in inherited.items():
        merged.setdefault(name, value)
    return sorted(
        merged.items(),
        key=lambda item: _attribute_sort_key(
            item[0],
            _XML_NAMESPACE if item[0].startswith("xml:") else "",
            item[0].split(":", 1)[-1],
        ),
    )


def _render(
    node: Node,
    rendered: dict[str, str],
    out: list[str],
    *,
    omit: frozenset[int],
    with_comments: bool,
    apex_namespaces: dict[str, str] | None = None,
    apex_attributes: dict[str, str] | None = None,
) -> None:
    """Write one node's canonical form into the output.

    Args:
        node: The node to render.
        rendered: Namespace declarations an ancestor has already put in the output,
            keyed by prefix.
        out: Accumulating output fragments.
        omit: Identities of nodes to drop along with their subtrees.
        with_comments: Whether comments are part of the canonical form.
        apex_namespaces: For a subset apex, every declaration in scope, which is
            rendered whether or not the subset uses it.
        apex_attributes: For a subset apex, the xml-namespace attributes it inherits.
    """
    if id(node) in omit:
        return

    if node.nodeType == Node.ELEMENT_NODE:
        declarations = dict(rendered)
        emitted: list[tuple[str, str]] = []
        candidates = (
            apex_namespaces if apex_namespaces is not None else _own_namespaces(node)
        )

        for prefix in sorted(candidates):
            uri = candidates[prefix]
            current = declarations.get(prefix)
            if not uri:
                # An undeclaration is written only when there is something to undo.
                if current:
                    emitted.append((prefix, ""))
                    declarations[prefix] = ""
                continue
            if current != uri:
                emitted.append((prefix, uri))
                declarations[prefix] = uri

        out.append("<" + node.tagName)
        for prefix, uri in emitted:
            name = "xmlns" if prefix == "" else "xmlns:" + prefix
            out.append(' %s="%s"' % (name, _escape_attribute(uri)))

        attributes = _sorted_attributes(node)
        if apex_attributes:
            attributes = _merge_apex_attributes(attributes, apex_attributes)
        for name, value in attributes:
            out.append(' %s="%s"' % (name, _escape_attribute(value)))
        out.append(">")

        for child in node.childNodes:
            _render(child, declarations, out, omit=omit, with_comments=with_comments)

        out.append("</" + node.tagName + ">")
        return

    if node.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE):
        out.append(_escape_text(node.data))
        return

    if node.nodeType == Node.PROCESSING_INSTRUCTION_NODE:
        data = node.data
        out.append("<?" + node.target + ((" " + data) if data else "") + "?>")
        return

    if node.nodeType == Node.COMMENT_NODE and with_comments:
        out.append("<!--" + node.data.replace(_CARRIAGE_RETURN, "&#xD;") + "-->")


def canonicalize(
    node: Document | Element,
    *,
    omit: tuple[Element, ...] = (),
    with_comments: bool = False,
) -> bytes:
    """Return the Canonical XML 1.1 form of a document, or of one subtree of it.

    Args:
        node: The document, or the element that is the apex of the subset. An apex that
            is not the document element is treated as a subset, which means it renders
            every namespace declaration in scope and inherits the xml-namespace
            attributes described in this module's docstring.
        omit: Elements to leave out along with their subtrees. This is how the
            enveloped-signature transform removes the ``ds:Signature`` element from the
            document it is signing.
        with_comments: Whether to keep comments. Off by default, which is what the plain
            algorithm identifier means.

    Returns:
        The canonical form, as UTF-8 bytes. Bytes rather than text because this is what
        gets hashed, and handing back a string would invite someone to encode it twice.
    """
    excluded = frozenset(id(element) for element in omit)
    out: list[str] = []

    if node.nodeType == Node.DOCUMENT_NODE:
        seen_root = False
        for child in node.childNodes:
            if child.nodeType == Node.ELEMENT_NODE:
                _render(child, {}, out, omit=excluded, with_comments=with_comments)
                seen_root = True
                continue
            before = len(out)
            _render(child, {}, out, omit=excluded, with_comments=with_comments)
            if len(out) == before:
                continue
            # Outside the document element, a processing instruction or comment is
            # separated from it by a line feed: after the node when it precedes the
            # element, before it when it follows.
            if seen_root:
                out.insert(before, "\n")
            else:
                out.append("\n")
    else:
        _render(
            node,
            {},
            out,
            omit=excluded,
            with_comments=with_comments,
            apex_namespaces=_in_scope_namespaces(node),
            apex_attributes=_inherited_xml_attributes(node),
        )

    return "".join(out).encode("utf-8")
