"""Tests for the content layer, and for the edits an editor is going to make.

The point of moving the prose into markdown is that someone who does not write
JavaScript can change a sentence. That is only safe if a bad edit is caught before it
reaches the site, so most of what is here is about the ways a content file can be wrong:
a renamed key, a block nobody renders, markup in a slot that shows plain text, a broken
table.

The pattern is not new to this repository. ``tests/test_web.py`` already regex-scans
``chapters.js`` to assert that the chapter list and the functions behind it cannot drift
apart; this does the same across two kinds of file. One convention makes it sound:
**content keys are always literal strings at the call site, never computed**, and the
first test enforces exactly that, because a computed key would make every other check
here unable to see it.
"""

from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

import pytest

from vcqi.web.app import STATIC_ROOT
from vcqi.web.content import (
    CHAPTER_ORDER,
    CHAPTERS_ROOT,
    CONTENT_ROOT,
    MISSING_PREFIX,
    UNKNOWN_CHAPTER,
    UNNUMBERED,
    _BLOCK,
    _CHAPTER_REFERENCE,
    blocks_for,
    chapter_ids,
    chapter_number,
    content_payload,
    number_chapter_references,
    with_chapter_numbers,
)
from vcqi.web.markdown import render, render_inline, to_text

CHAPTERS_JS = (STATIC_ROOT / "js" / "chapters.js").read_text(encoding="utf-8")
APP_JS = (STATIC_ROOT / "js" / "app.js").read_text(encoding="utf-8")

#: ``t.prose('what-it-is')`` and friends.
CALL = re.compile(r"\bt\.(text|html|prose|callout|block|fill|proseFill)\(\s*'([a-z0-9][a-z0-9.-]*)'")

#: The same call with something that is not a literal string.
LOOSE = re.compile(r"\bt\.(text|html|prose|callout|block|fill|proseFill)\(\s*(?!')")

#: ``const t = context.text('orientation');`` -- which chapter the calls below belong to.
BIND = re.compile(r"context\.text\('([a-z][a-z-]*)'\)")

#: Keys whose value is shown as plain text rather than rendered, so markup in them would
#: appear to a reader as literal asterisks.
PLAIN_TEXT_KEYS = ("title", "eyebrow", "lede")
PLAIN_TEXT_SUFFIXES = (".title", ".hint")


def referenced_keys() -> list[tuple[str, str, int]]:
    """Find every content key `chapters.js` asks for, and which chapter asked.

    Attribution is by nearest preceding ``context.text('id')`` binding, which is the
    convention every migrated chapter follows.

    Returns:
        One ``(chapter id, key, line number)`` per reference.
    """
    bindings: list[tuple[int, str]] = []
    for match in BIND.finditer(CHAPTERS_JS):
        bindings.append((CHAPTERS_JS.count("\n", 0, match.start()) + 1, match.group(1)))

    found: list[tuple[str, str, int]] = []
    for match in CALL.finditer(CHAPTERS_JS):
        line = CHAPTERS_JS.count("\n", 0, match.start()) + 1
        owner = None
        for binding_line, chapter_id in bindings:
            if binding_line <= line:
                owner = chapter_id
            else:
                break
        assert owner is not None, f"a content call at line {line} has no chapter binding"
        found.append((owner, match.group(2), line))
    return found


class TestTheConventionHolds:
    """Everything else depends on keys being visible to a regex."""

    def test_every_key_is_a_literal_string(self) -> None:
        """A computed key would make the whole static check unsound.

        If this ever needs to change, the checks below have to be replaced by something
        that runs the interface, not weakened.
        """
        offenders = [
            CHAPTERS_JS.count("\n", 0, match.start()) + 1 for match in LOOSE.finditer(CHAPTERS_JS)
        ]
        assert not offenders, (
            f"content keys must be string literals; chapters.js lines {offenders} compute one"
        )

    def test_at_least_one_chapter_is_migrated(self) -> None:
        """Otherwise every test here would pass by having nothing to check."""
        assert referenced_keys(), "no chapter reads its prose from a content file"


class TestTheRenderContextContract:
    """What a chapter expects from app.js, and what app.js actually passes.

    A chapter render function receives one object and reaches into it. Nothing checked
    that the two files agreed about what is in it, and when `context.text` was added
    for the content layer they briefly did not: a browser running a cached older
    `app.js` beside the new `chapters.js` showed "This chapter failed to render:
    context.text is not a function".

    Caching was the reason the mismatch reached a reader, and that is fixed separately.
    This is the check for the mismatch itself, which would otherwise only ever show up
    in a browser.
    """

    def test_every_context_property_a_chapter_uses_is_passed(self) -> None:
        """The contract, read off both sides rather than assumed."""
        used = set(re.findall(r"context\.([a-zA-Z][\w]*)", CHAPTERS_JS))
        assert used, "no chapter reads anything from its context; this test is not working"

        # The single object literal passed to chapter.render(...).
        call = re.search(r"chapter\.render\(\{(.*?)\}\)", APP_JS, re.DOTALL)
        assert call, "could not find the chapter.render call in app.js"
        provided = set(re.findall(r"^\s*([a-zA-Z][\w]*)\s*[,:]", call.group(1), re.MULTILINE))

        missing = used - provided
        assert not missing, (
            f"chapters.js reads context.{{{', '.join(sorted(missing))}}} but app.js does "
            "not pass it; a chapter would fail to render"
        )

    def test_nothing_is_passed_that_no_chapter_uses(self) -> None:
        """The other direction, which is only untidiness but is free to check."""
        used = set(re.findall(r"context\.([a-zA-Z][\w]*)", CHAPTERS_JS))
        call = re.search(r"chapter\.render\(\{(.*?)\}\)", APP_JS, re.DOTALL)
        provided = set(re.findall(r"^\s*([a-zA-Z][\w]*)\s*[,:]", call.group(1), re.MULTILINE))
        unused = provided - used
        assert not unused, f"app.js passes {sorted(unused)}, which no chapter reads"


class TestKeysAndBlocksAgree:
    """The two halves cannot drift apart without this failing."""

    def test_every_referenced_key_exists(self) -> None:
        """Catches a typo, and a rename made in the markdown but not the code."""
        missing = [
            f"{chapter_id}/{key} (chapters.js line {line})"
            for chapter_id, key, line in referenced_keys()
            if key not in blocks_for(chapter_id)
        ]
        assert not missing, "the page asks for content that does not exist: " + ", ".join(missing)

    def test_no_block_is_orphaned(self) -> None:
        """The other direction: prose nobody renders.

        Catches a rename made in the code but not the markdown, an editor adding a
        section the page does not show, and a developer deleting a call and leaving the
        words behind.
        """
        referenced = {(chapter_id, key) for chapter_id, key, _ in referenced_keys()}
        migrated = {chapter_id for chapter_id, _ in referenced}
        orphaned = [
            f"{chapter_id}/{key}"
            for chapter_id in migrated
            for key in blocks_for(chapter_id)
            # title, eyebrow and lede are read by app.js's heading(), not through the
            # t.* accessors this scans for, so they are referenced everywhere by
            # construction rather than per chapter.
            if key not in PLAIN_TEXT_KEYS and (chapter_id, key) not in referenced
        ]
        assert not orphaned, "content nothing renders: " + ", ".join(sorted(orphaned))

        # And that claim about app.js is worth checking rather than assuming, since it
        # is what makes the exclusion above sound.
        assert "heading(" in APP_JS
        for field in PLAIN_TEXT_KEYS:
            assert f"'{field}'" in APP_JS, f"app.js does not read '{field}' from the content"

    def test_every_block_renders_to_something(self) -> None:
        """A key with nothing under it is a heading followed by silence."""
        empty = [
            f"{chapter_id}/{key}"
            for chapter_id, blocks in content_payload()["chapters"].items()
            for key, block in blocks.items()
            if not block["html"].strip()
        ]
        assert not empty, "blocks with no text: " + ", ".join(empty)


class TestChapterFiles:
    """The files, their names, and their relation to the interface."""

    def test_each_file_is_a_chapter_and_each_chapter_has_a_file(self) -> None:
        """Files are named by id, so a file outside the order would never be read."""
        files = {path.stem for path in CHAPTERS_ROOT.glob("*.md")}
        assert files == set(CHAPTER_ORDER)
        assert chapter_ids() == list(CHAPTER_ORDER)

    def test_the_interface_declares_the_same_chapters_in_the_same_order(self) -> None:
        """CHAPTER_ORDER numbers the chapters, and CHAPTERS renders them.

        The two lists are the price of the order living in Python, where the server
        needs it to write a number into a reference, while the render functions live
        in JavaScript. This is what keeps them one list in effect.
        """
        declared = re.findall(
            r"^    id: '([a-z-]+)',\n(    unnumbered: true,\n)?", CHAPTERS_JS, re.MULTILINE
        )
        assert [chapter_id for chapter_id, _ in declared] == list(CHAPTER_ORDER)
        assert {chapter_id for chapter_id, flag in declared if flag} == UNNUMBERED

    def test_a_migrated_chapter_defines_its_own_heading(self) -> None:
        """title, eyebrow and lede move together with the rest of a chapter.

        app.js falls back to the CHAPTERS descriptor for a chapter that has not been
        migrated, so a chapter with content but no title would silently take the old
        one and the two could then disagree.
        """
        for chapter_id in chapter_ids():
            blocks = blocks_for(chapter_id)
            for field in PLAIN_TEXT_KEYS:
                assert field in blocks, f"{chapter_id} has a content file but no '{field}'"
                assert blocks[field]["text"].strip(), f"{chapter_id}/{field} is empty"
            # And the descriptor must no longer carry them, or there would be two
            # sources for one string.
            descriptor = re.search(
                r"\{[^{}]*id: '" + re.escape(chapter_id) + r"'[^{}]*\}", CHAPTERS_JS, re.DOTALL
            )
            assert descriptor, f"no CHAPTERS entry for {chapter_id}"
            for field in PLAIN_TEXT_KEYS:
                assert f"{field}:" not in descriptor.group(0), (
                    f"{chapter_id} defines '{field}' in both chapters.js and its content file"
                )

    def test_there_is_a_readme_for_whoever_edits_these(self) -> None:
        """The failure mode of a content layer is an editor who cannot tell what to do.

        The guide has to show the delimiter it describes, and this checks it against the
        parser rather than against a string written down twice: somewhere in the text
        there has to be a line the parser would accept as a block marker. It used to
        assert ``"##" in text``, which went on passing after the delimiter changed
        because the syntax table happens to contain ``### Like this``.
        """
        readme = CONTENT_ROOT / "README.md"
        assert readme.is_file()
        text = readme.read_text(encoding="utf-8")
        assert "pull request" in text
        assert _BLOCK.search(text), (
            "the editing guide does not show a line the parser would read as a block "
            "marker, so it is describing a format that no longer exists"
        )


ROOT = Path(__file__).resolve().parent.parent

#: Everything that would go wrong if a chapter moved: the package, the tests, the tools
#: and the documents a first-time reader opens. The history in docs/history/ and the
#: working plan record what was true when they were written, so they are left alone.
SCANNED = (
    [ROOT / name for name in ("README.md", "ARCHITECTURE.md", "CONTENT.md", "DEPLOYMENT.md")]
    + sorted((ROOT / "src" / "vcqi").rglob("*.py"))
    + sorted((ROOT / "src" / "vcqi").rglob("*.md"))
    + sorted((ROOT / "src" / "vcqi" / "web" / "static" / "js").glob("*.js"))
    + sorted((ROOT / "tests").glob("*.py"))
    + sorted((ROOT / "tools").glob("*.mjs"))
)

#: These two show the rendered form, "chapter 5", as the example of what a reference
#: becomes, so they are the only places a number is written on purpose.
SHOWS_THE_RENDERED_FORM = {"content.py", "test_content.py"}

#: "chapter 5", "Chapters 4", or the same split across a line break inside a comment.
BY_NUMBER = re.compile(r"\b[Cc]hapters?[ \t]*(?:\n[ \t]*(?://|#:?|\*)?[ \t]*)?\d+\b")


def _scanned() -> list[tuple[Path, str]]:
    """Return every scanned file that may not write a chapter's number by hand.

    Returns:
        Each path with its text.
    """
    return [
        (path, path.read_text(encoding="utf-8"))
        for path in SCANNED
        if path.name not in SHOWS_THE_RENDERED_FORM
    ]


class TestChapterReferences:
    """A chapter is referred to by id, and the number is written in when it is served."""

    def test_no_chapter_is_referred_to_by_a_number_written_by_hand(self) -> None:
        """The drift #73 found: numbers written in some sixty places, some already wrong.

        Prose and the editorial fields write ``[chapter](#scope)``; code and documents
        name the chapter ("the scope chapter"). Either way nothing has to change when a
        chapter moves.
        """
        found = [
            f"{path.relative_to(ROOT)}:{text.count(chr(10), 0, match.start()) + 1}"
            for path, text in _scanned()
            for match in BY_NUMBER.finditer(text)
        ]
        assert found == [], f"chapters referred to by number: {found}"

    def test_every_reference_names_a_chapter_that_has_a_number(self) -> None:
        """An id that is not a chapter would show the unknown-chapter marker."""
        references = [
            (path.relative_to(ROOT), match.group(2))
            for path, text in _scanned()
            for match in _CHAPTER_REFERENCE.finditer(text)
        ]
        assert len(references) > 40, "the references by id have gone missing"
        numbered = set(CHAPTER_ORDER) - UNNUMBERED
        wrong = [
            f"{path}: #{chapter_id}"
            for path, chapter_id in references
            if chapter_id not in numbered
        ]
        assert wrong == []

    def test_a_reference_becomes_a_link_carrying_the_number(self) -> None:
        """What the reader sees, with the number the rail shows."""
        number = chapter_number("scope")
        assert number_chapter_references("see [chapter](#scope).") == (
            f"see [chapter {number}](#scope)."
        )
        assert number_chapter_references("[Chapter](#scope) says") == (
            f"[Chapter {number}](#scope) says"
        )
        html = render(number_chapter_references("see [chapter](#scope)."))
        assert f'<a href="#scope" rel="noopener">chapter {number}</a>' in html

    def test_the_served_prose_carries_numbers_and_no_raw_references(self) -> None:
        """Every block, as /api/content serves it."""
        served = json.dumps(content_payload())
        assert "[chapter](#" not in served and "[Chapter](#" not in served
        assert UNKNOWN_CHAPTER not in served
        assert f">chapter {chapter_number('break')}</a>" in served

    def test_an_editorial_field_gets_the_number_as_plain_text(self) -> None:
        """Fields the page sets as text cannot carry a link, so they get the number."""
        number = chapter_number("exchange")
        payload = {"items": [{"why": "[Chapter](#exchange) builds it."}], "count": 3}
        assert with_chapter_numbers(payload) == {
            "items": [{"why": f"Chapter {number} builds it."}],
            "count": 3,
        }

    def test_an_id_that_is_not_a_chapter_is_visible_rather_than_silent(self) -> None:
        """A typo costs one phrase, and shows as a marker the way a missing block does."""
        rendered = number_chapter_references("see [chapter](#scopes).")
        assert UNKNOWN_CHAPTER + "scopes]" in rendered
        with pytest.raises(ValueError):
            chapter_number("cautions")

    def test_the_content_index_lists_the_chapters_in_order(self) -> None:
        """CONTENT.md's table: number, title and file, for whoever is looking to edit."""
        rows = re.findall(
            r"^\| (—|\d+) \| (.+?) \| \[`([a-z-]+)\.md`\]"
            r"\(src/vcqi/web/content/chapters/([a-z-]+)\.md\) \|$",
            (ROOT / "CONTENT.md").read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        expected = [
            (
                "—" if chapter_id in UNNUMBERED else str(chapter_number(chapter_id)),
                blocks_for(chapter_id)["title"]["text"],
                chapter_id,
                chapter_id,
            )
            for chapter_id in CHAPTER_ORDER
        ]
        assert rows == expected


class TestBlocksSuitTheSlotsTheyFill:
    """A block used as a heading is not the same as a block used as prose."""

    def test_plain_text_slots_contain_no_markup(self) -> None:
        """`panel()` sets its title with textContent, so markup would show literally.

        This is the check that catches an editor bolding a word in a panel title, which
        would otherwise appear to a reader as asterisks.
        """
        # A reference to another chapter is the one link allowed: its text form is
        # "Chapter 10", which is what a title shows, with no link.
        reference = re.compile(r'<a href="#[a-z-]+" rel="noopener">([Cc]hapter \d+)</a>')
        offenders = []
        for chapter_id, blocks in content_payload()["chapters"].items():
            for key, block in blocks.items():
                if key in PLAIN_TEXT_KEYS or key.endswith(PLAIN_TEXT_SUFFIXES):
                    html = reference.sub(r"\1", block["html"])
                    if html != f"<p>{block['text']}</p>":
                        offenders.append(f"{chapter_id}/{key}")
        assert not offenders, (
            "these are shown as plain text, so markdown in them would appear literally: "
            + ", ".join(offenders)
        )

    def test_keys_used_as_a_block_render_as_a_table_or_a_list(self) -> None:
        """`t.block()` exists for structure; prose belongs in `t.prose()`."""
        for chapter_id, key, line in referenced_keys():
            if not re.search(rf"t\.block\(\s*'{re.escape(key)}'", CHAPTERS_JS):
                continue
            kind = blocks_for(chapter_id)[key]["kind"]
            assert kind in {"table", "list"}, (
                f"{chapter_id}/{key} is used as a block but rendered as {kind} "
                f"(chapters.js line {line})"
            )

    def test_every_table_row_has_the_headers_column_count(self) -> None:
        """A broken pipe table renders as a mangled table rather than an error."""
        for chapter_id, blocks in content_payload()["chapters"].items():
            for key, block in blocks.items():
                if block["kind"] != "table":
                    continue
                headers = block["html"].count("<th>")
                for row in re.findall(r"<tr>(?:(?!</tr>).)*</tr>", block["html"], re.DOTALL):
                    cells = row.count("<td>")
                    if cells:
                        assert cells == headers, (
                            f"{chapter_id}/{key}: a row has {cells} cells but the header "
                            f"has {headers} columns"
                        )

    def test_every_json_example_parses(self) -> None:
        """A ```json fence is shown coloured only if it parses.

        chapters.js falls back to the plain text when it does not, so a stray comma in an
        example would reach a reader looking unlike every other credential on the site,
        with nothing to say why. Caught here instead, naming the block.
        """
        fence = re.compile(r'<pre class="code" data-language="json">(.*?)</pre>', re.DOTALL)
        found = 0
        for chapter_id, blocks in content_payload()["chapters"].items():
            for key, block in blocks.items():
                for number, body in enumerate(fence.findall(block["html"]), start=1):
                    found += 1
                    try:
                        json.loads(unescape(body))
                    except json.JSONDecodeError as error:
                        pytest.fail(
                            f"{chapter_id}/{key}: JSON example {number} does not parse: {error}"
                        )
        assert found, "no JSON examples found in any content file; this test is not working"

    def test_placeholders_only_appear_in_interpolated_blocks(self) -> None:
        """A {name} in a block nothing fills would be shown to the reader as-is."""
        filled = set(re.findall(r"t\.(?:proseFill|fill)\(\s*'([a-z0-9][a-z0-9.-]*)'", CHAPTERS_JS))
        for chapter_id, blocks in content_payload()["chapters"].items():
            for key, block in blocks.items():
                if key in filled:
                    continue
                assert not re.search(r"\{[a-z][a-z0-9_]*\}", block["html"], re.IGNORECASE), (
                    f"{chapter_id}/{key} contains a placeholder but is never interpolated"
                )


class TestAMissingKeyIsVisibleNotSilent:
    """What a typo actually costs."""

    def test_the_marker_says_what_is_missing(self) -> None:
        """Both halves agree on the wording, so it can be searched for."""
        assert MISSING_PREFIX in (STATIC_ROOT / "js" / "content.js").read_text(encoding="utf-8")

    def test_the_browser_half_never_throws_and_never_returns_empty(self) -> None:
        """A miss must cost one paragraph, not a chapter.

        app.js catches a render error and replaces the whole chapter with a banner. That
        is right for a genuine bug and much too much for a mistyped key, so the
        accessors are written not to throw.
        """
        source = (STATIC_ROOT / "js" / "content.js").read_text(encoding="utf-8")
        assert "throw" not in source
        assert "content-missing" in source

    def test_the_stylesheet_makes_the_marker_impossible_to_miss(self) -> None:
        """An unstyled marker in the middle of a paragraph is easy to skim past."""
        css = (STATIC_ROOT / "css" / "app.css").read_text(encoding="utf-8")
        assert ".content-missing" in css


class TestMarkdown:
    """The renderer, against the constructs the prose actually uses."""

    @pytest.mark.parametrize(
        "markdown,expected",
        [
            ("plain words", "<p>plain words</p>"),
            ("two\n\nparagraphs", "<p>two</p><p>paragraphs</p>"),
            ("a line\nwrapped in source", "<p>a line wrapped in source</p>"),
            ("**strong**", "<p><strong>strong</strong></p>"),
            ("*emphasis*", "<p><em>emphasis</em></p>"),
            ("`dc.resistance`", "<p><code>dc.resistance</code></p>"),
            ("`**not bold**`", "<p><code>**not bold**</code></p>"),
            ("- one\n- two", "<ul><li>one</li><li>two</li></ul>"),
            ("1. one\n2. two", "<ol><li>one</li><li>two</li></ol>"),
            ("### heading", "<h3>heading</h3>"),
            ("---", "<hr>"),
            ("> quoted", "<blockquote><p>quoted</p></blockquote>"),
            ("2 * 3 * 4 is not emphasis", "<p>2 * 3 * 4 is not emphasis</p>"),
        ],
    )
    def test_known_renderings(self, markdown: str, expected: str) -> None:
        """Each construct the editor documentation promises."""
        assert render(markdown) == expected

    def test_a_link_carries_its_target(self) -> None:
        """Links are the one construct that can point somewhere."""
        assert render_inline("[x](https://example.org/a)") == (
            '<a href="https://example.org/a" rel="noopener">x</a>'
        )

    @pytest.mark.parametrize(
        "target",
        ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,x", "vbscript:x"],
    )
    def test_a_dangerous_link_target_is_dropped(self, target: str) -> None:
        """Content files are reviewed like code, and this should not depend on that."""
        assert f'href="{target}"' not in render_inline(f"[x]({target})")
        assert 'href="#"' in render_inline(f"[x]({target})")

    @pytest.mark.parametrize(
        "markdown",
        [
            "<img src=x onerror=alert(1)>",
            "<script>alert(1)</script>",
            "`</code><script>alert(1)</script>`",
            "| <script>x</script> | b |\n| --- | --- |\n| c | d |",
            "> <iframe src=evil>",
            "### <b>heading</b>",
        ],
    )
    def test_no_tag_survives_that_this_module_did_not_emit(self, markdown: str) -> None:
        """What makes handing the output to innerHTML defensible.

        There is no HTML passthrough to disable, because there is no such path: every
        character of input is escaped and every tag in the result was emitted here.
        """
        emitted = {
            "p", "strong", "em", "code", "a", "ul", "ol", "li",
            "h3", "h4", "h5", "h6", "hr", "blockquote",
            "table", "thead", "tbody", "tr", "th", "td", "pre",
        }
        present = set(re.findall(r"<\s*/?\s*([a-zA-Z][\w-]*)", render(markdown)))
        assert present <= emitted, f"unexpected tags: {sorted(present - emitted)}"

    def test_a_table_gets_the_class_the_interface_already_styles(self) -> None:
        """Which is why `table()` in ui.js did not have to change."""
        html = render("| a | b |\n| --- | --- |\n| c | d |")
        assert html.startswith('<table class="data">')
        assert "<th>a</th><th>b</th>" in html
        assert "<td>c</td><td>d</td>" in html

    def test_a_pipe_without_a_divider_is_not_a_table(self) -> None:
        """Prose is allowed to contain a pipe character."""
        assert render("a | b") == "<p>a | b</p>"

    def test_text_recovers_the_words(self) -> None:
        """The plain form is what fills a panel title."""
        assert to_text(render("A **bold** and `code` word")) == "A bold and code word"
        assert to_text(render("Angle < brackets > survive")) == "Angle < brackets > survive"


class TestPackaging:
    """The content has to reach a wheel, or a deployed copy has no words."""

    def test_the_content_lives_inside_the_package(self) -> None:
        """hatchling ships src/vcqi wholesale, so being inside it is the mechanism.

        A path outside the package would need force-include, which is easy to forget
        and fails only in the built image.
        """
        package_root = Path(__file__).resolve().parents[1] / "src" / "vcqi"
        assert CONTENT_ROOT.resolve().is_relative_to(package_root.resolve())

    def test_the_files_are_found_relative_to_the_module(self) -> None:
        """Not relative to the working directory, which a server does not control."""
        assert CHAPTERS_ROOT.is_dir()
        assert list(CHAPTERS_ROOT.glob("*.md"))
