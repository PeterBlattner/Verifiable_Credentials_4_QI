"""Tests for Canonical XML 1.1.

The evidence here is weaker than what ``tests/test_jcs.py`` has for RFC 8785, and it is
better to say so than to let the file imply otherwise. There is no independent XML
Signature implementation on this machine to cross-check against -- ``xmlsec`` and
``lxml`` both need native builds -- so conformance rests on the test cases the
specification publishes, transcribed below, plus round-tripping against our own verifier.

The cases are from *Canonical XML Version 1.0*, section 3, which 1.1 inherits unchanged
except where a document carries ``xml:base`` or ``xml:id``. Sections 3.4 and 3.5 turn on
DTD entity expansion and 3.7 and 3.8 select their subsets with XPath, neither of which
this module offers; what replaces them is the subset behaviour that is actually used,
which is an apex element rather than an arbitrary node-set.
"""

from __future__ import annotations

from xml.etree import ElementTree

from vcqi.crypto.xmlc14n import ALGORITHM, canonicalize, parse


def c14n(source: str, **kwargs: object) -> str:
    """Canonicalize and decode, so the assertions read as text.

    Args:
        source: The document to canonicalize.
        **kwargs: Passed through to ``canonicalize``.

    Returns:
        The canonical form as text.
    """
    return canonicalize(parse(source), **kwargs).decode("utf-8")  # type: ignore[arg-type]


class TestTheSpecificationsOwnCases:
    """Section 3 of Canonical XML, transcribed."""

    def test_3_1_processing_instructions_and_comments_outside_the_element(self) -> None:
        """A comment goes; a processing instruction stays, with its line feed.

        The placement of that line feed is the whole point of the case: after a node
        that precedes the document element, before one that follows it.
        """
        source = (
            '<?xml version="1.0"?>\n'
            "\n"
            '<?xml-stylesheet   href="doc.xsl"\n'
            '   type="text/xsl"   ?>\n'
            "\n"
            "<doc>Hello, world!<!-- Comment 1 --></doc>\n"
            "\n"
            "<?pi-without-data     ?>\n"
            "\n"
            "<!-- Comment 2 -->\n"
            "\n"
            "<!-- Comment 3 -->\n"
        )
        expected = (
            '<?xml-stylesheet href="doc.xsl"\n'
            '   type="text/xsl"   ?>\n'
            "<doc>Hello, world!</doc>\n"
            "<?pi-without-data?>"
        )
        assert c14n(source) == expected

    def test_3_1_with_comments_keeps_them(self) -> None:
        """The other algorithm identifier, checked because the flag is easy to invert."""
        result = c14n(
            "<?xml version=\"1.0\"?>\n<doc>Hello<!-- c --></doc>\n", with_comments=True
        )
        assert result == "<doc>Hello<!-- c --></doc>"

    def test_3_2_whitespace_in_document_content_survives(self) -> None:
        """Canonicalization normalises markup, never the text between it."""
        source = (
            "<doc>\n"
            "   <clean>   </clean>\n"
            "   <dirty>   A   B   </dirty>\n"
            "   <mixed>\n"
            "      A\n"
            "      <clean>   </clean>\n"
            "      B\n"
            "   </mixed>\n"
            "</doc>\n"
        )
        assert c14n(source) == source.rstrip("\n")

    def test_3_3_start_and_end_tags(self) -> None:
        """Tag form, attribute order, and which namespace declarations are emitted.

        This is the densest of the cases and the one worth reading if only one is. It
        pins four separate rules at once, and the last two are where an implementation
        usually goes wrong: a redundant declaration is dropped, and an undeclaration is
        written only when there is something to undo.
        """
        source = (
            "<doc>\n"
            "   <e1   />\n"
            "   <e2   ></e2>\n"
            '   <e3   name = "elem3"   id="elem3"   />\n'
            '   <e4   name="elem4"   id="elem4"   ></e4>\n'
            "   <e5 a:attr=\"out\" b:attr=\"sorted\" attr2=\"all\" attr=\"I'm\"\n"
            '      xmlns:b="http://www.ietf.org"\n'
            '      xmlns:a="http://www.w3.org"\n'
            '      xmlns="http://example.org"/>\n'
            '   <e6 xmlns="" xmlns:a="http://www.w3.org">\n'
            '      <e7 xmlns="http://www.ietf.org">\n'
            '         <e8 xmlns="" xmlns:a="http://www.w3.org">\n'
            '            <e9 xmlns="" xmlns:a="http://www.ietf.org"/>\n'
            "         </e8>\n"
            "      </e7>\n"
            "   </e6>\n"
            "</doc>\n"
        )
        expected = (
            "<doc>\n"
            "   <e1></e1>\n"
            "   <e2></e2>\n"
            '   <e3 id="elem3" name="elem3"></e3>\n'
            '   <e4 id="elem4" name="elem4"></e4>\n'
            '   <e5 xmlns="http://example.org" xmlns:a="http://www.w3.org" '
            'xmlns:b="http://www.ietf.org" attr="I\'m" attr2="all" b:attr="sorted" '
            'a:attr="out"></e5>\n'
            '   <e6 xmlns:a="http://www.w3.org">\n'
            '      <e7 xmlns="http://www.ietf.org">\n'
            '         <e8 xmlns="">\n'
            '            <e9 xmlns:a="http://www.ietf.org"></e9>\n'
            "         </e8>\n"
            "      </e7>\n"
            "   </e6>\n"
            "</doc>"
        )
        assert c14n(source) == expected

    def test_3_6_utf8_is_the_output_encoding(self) -> None:
        """Whatever went in, bytes come out, and they come out as UTF-8."""
        source = '<?xml version="1.0" encoding="ISO-8859-1"?>\n<doc>H\xe4llo</doc>'
        assert canonicalize(parse(source.encode("iso-8859-1"))) == (
            "<doc>H\xe4llo</doc>".encode("utf-8")
        )


class TestEscaping:
    """The character-by-character rules, which differ between the two positions."""

    def test_text_escapes_the_three_characters_and_the_carriage_return(self) -> None:
        """A quote in text is left alone; in an attribute value it is not."""
        assert c14n("<doc>&lt; &amp; &gt; \" '</doc>") == (
            "<doc>&lt; &amp; &gt; \" '</doc>"
        )

    def test_a_carriage_return_in_text_becomes_a_reference(self) -> None:
        """It can only have arrived as one, and it has to leave as one.

        Otherwise a document changes meaning the first time it crosses a system that
        rewrites line endings -- which, on this repository's own evidence, happens.
        """
        assert c14n("<doc>a&#xD;b</doc>") == "<doc>a&#xD;b</doc>"

    def test_attribute_values_escape_quote_tab_and_both_line_breaks(self) -> None:
        """Four more characters than text, because the delimiters differ."""
        result = c14n('<doc a="&quot; &#x9; &#xA; &#xD; &lt; &amp;"></doc>')
        assert result == '<doc a="&quot; &#x9; &#xA; &#xD; &lt; &amp;"></doc>'

    def test_a_greater_than_sign_is_not_escaped_in_an_attribute(self) -> None:
        """The rules are not symmetric, and it is easy to write them as if they were."""
        assert c14n('<doc a="&gt;"></doc>') == '<doc a=">"></doc>'


class TestSubsets:
    """An apex that is not the document element, which is what ds:SignedInfo is."""

    SOURCE = (
        '<root xmlns="urn:outer" xmlns:k="urn:kept" xml:lang="de">'
        "<mid><apex xmlns:o=\"urn:own\"><leaf/></apex></mid>"
        "</root>"
    )

    def test_every_namespace_in_scope_is_rendered_at_the_apex(self) -> None:
        """Inclusive canonicalization, including declarations the subset never uses.

        ``urn:kept`` appears in the output although nothing under the apex refers to it.
        That is the behaviour exclusive canonicalization exists to avoid, and knowing it
        is deliberate here matters: it is why a ds:Signature made this way breaks if the
        document is later moved under a different set of ancestor declarations.
        """
        document = parse(self.SOURCE)
        apex = document.getElementsByTagName("apex")[0]
        result = canonicalize(apex).decode("utf-8")
        assert 'xmlns="urn:outer"' in result
        assert 'xmlns:k="urn:kept"' in result
        assert 'xmlns:o="urn:own"' in result

    def test_xml_lang_is_inherited_by_the_apex(self) -> None:
        """A simple inheritable attribute, as in 1.0."""
        document = parse(self.SOURCE)
        apex = document.getElementsByTagName("apex")[0]
        assert 'xml:lang="de"' in canonicalize(apex).decode("utf-8")

    def test_an_apex_that_states_it_itself_is_not_overwritten(self) -> None:
        """The nearer value wins, and the nearest is the apex's own."""
        document = parse(
            '<root xml:lang="de"><apex xml:lang="en"><leaf/></apex></root>'
        )
        apex = document.getElementsByTagName("apex")[0]
        result = canonicalize(apex).decode("utf-8")
        assert 'xml:lang="en"' in result
        assert 'xml:lang="de"' not in result

    def test_omitting_a_subtree_removes_it(self) -> None:
        """The enveloped-signature transform, which is all it needs to be."""
        document = parse("<doc><keep>a</keep><drop>b</drop><keep>c</keep></doc>")
        drop = document.getElementsByTagName("drop")[0]
        assert canonicalize(document, omit=(drop,)).decode("utf-8") == (
            "<doc><keep>a</keep><keep>c</keep></doc>"
        )


class TestWhereElevenDiffersFromTen:
    """The two changes, and the fact that neither shows on these documents."""

    def test_xml_base_is_composed_rather_than_inherited(self) -> None:
        """1.0 would have copied the nearest value; 1.1 resolves the chain."""
        document = parse(
            '<root xml:base="http://example.org/a/">'
            '<mid xml:base="b/"><apex/></mid>'
            "</root>"
        )
        apex = document.getElementsByTagName("apex")[0]
        assert 'xml:base="http://example.org/a/b/"' in canonicalize(apex).decode("utf-8")

    def test_xml_id_is_not_inherited(self) -> None:
        """It identifies one element. Copying it downward would make it identify two."""
        document = parse('<root xml:id="r"><apex/></root>')
        apex = document.getElementsByTagName("apex")[0]
        assert "xml:id" not in canonicalize(apex).decode("utf-8")

    def test_the_two_versions_agree_on_a_document_carrying_neither(self) -> None:
        """Which is what makes choosing 1.1 here free.

        The PTB/DKD DCC this repository signs has no ``xml:base`` and no ``xml:id``
        anywhere, so the bytes a 1.0 implementation would produce are the same bytes.
        ``ElementTree.canonicalize`` is not a 1.0 implementation -- it is 2.0 -- but the
        three algorithms coincide on a document this plain, which is enough to catch a
        gross error in the walker even if it cannot certify conformance.
        """
        source = (
            '<doc xmlns="urn:x" xmlns:b="urn:b" z="1" a="2" b:y="3">'
            "<child>text &amp; more</child><empty/></doc>"
        )
        assert c14n(source) == ElementTree.canonicalize(source)


def test_the_algorithm_identifier_is_the_one_for_this_version() -> None:
    """It is written into every signature, so a wrong constant is a silent lie."""
    assert ALGORITHM == "http://www.w3.org/2006/12/xml-c14n11"
