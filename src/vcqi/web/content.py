"""Chapter prose, read from markdown files rather than compiled into JavaScript.

The chapters used to carry their text as string literals inside `chapters.js`,
1799 lines of interactive code with about a hundred and twenty paragraphs threaded
through it. Correcting a sentence meant editing JavaScript, which put it out of reach of
everyone except whoever maintains the file.

So the prose lives in `content/chapters/*.md`, and this module reads it. The format is
one rule: a line matching ``<!-- block: some-key -->`` starts a block, and everything
until the next such line is that block's markdown. There is no front matter and no
second syntax -- ``title``, ``eyebrow`` and ``lede`` are blocks like any other.

A comment was chosen over YAML front matter, and over the ``## some-key`` heading this
used to use, for one reason: **GitHub's own preview of the file stays a usable preview of
the prose**. A comment is invisible there, so the paragraphs render as they will read,
and nobody has to think about quoting a colon in a title.

Against the heading it also removes a trap. ``## some-name`` written in the middle of a
paragraph used to be swallowed as a marker, silently splitting the block; it is now
simply text. What the change does *not* do is make ``##`` a heading:
:mod:`vcqi.web.markdown` emits ``h3`` to ``h6``, so a sub-heading inside a block is still
``###`` or smaller and ``##`` renders with its hashes showing. Emitting ``h2`` would want
a style for it in `app.css`, which there is none of, and would sit oddly beside the
page's own ``h1``.

Rendering happens here rather than in the browser. That keeps the page loading zero
external resources, which is what makes its Content-Security-Policy reach
``default-src 'none'``, and it keeps the README's claim of no build step literally true:
nothing is generated into the tree, and the markdown ships in the wheel by the same
mechanism that already ships `app.css`. The cache is keyed on file modification times,
so editing a file and pressing reload is enough -- no `--reload`, no restart.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

from vcqi.web.markdown import render, to_text

__all__ = [
    "CONTENT_ROOT",
    "CHAPTERS_ROOT",
    "CHAPTER_ORDER",
    "MISSING_PREFIX",
    "UNNUMBERED",
    "UNKNOWN_CHAPTER",
    "chapter_ids",
    "chapter_number",
    "content_payload",
    "blocks_for",
    "number_chapter_references",
    "with_chapter_numbers",
]

CONTENT_ROOT: Final[Path] = Path(__file__).parent / "content"
CHAPTERS_ROOT: Final[Path] = CONTENT_ROOT / "chapters"

#: A block key that no content file defines renders as this, so a typo costs one
#: paragraph and shows up as an obvious marker rather than as silence. See content.js
#: for the browser half.
MISSING_PREFIX: Final[str] = "[missing content: "

#: ``<!-- block: key -->`` on a line of its own. Keys are lowercase and dotted for
#: grouping, so that ``mapping.title``, ``mapping.hint`` and ``mapping.rows`` read as
#: belonging together. The pattern is deliberately narrower than "any comment", so that
#: the note a file opens with cannot be mistaken for a block.
_BLOCK: Final = re.compile(
    r"^<!--\s*block:\s*([a-z0-9][a-z0-9.-]*)\s*-->\s*$", re.MULTILINE
)

#: The chapters in the order the rail shows them, each in ``chapters/<id>.md``. The
#: CHAPTERS array in chapters.js lists the same ids in the same order, because it holds
#: the render functions, and a test holds the two together. This is where a chapter's
#: number comes from, so moving a chapter is moving one line here and one there.
#:
#: The files used to carry their position as a prefix, ``08-break.md``, which was one
#: more than the number a reader sees because the cautions come first. Every reference
#: to a chapter was written by number, in twenty-odd places, so nothing could move
#: (issue #73).
CHAPTER_ORDER: Final[tuple[str, ...]] = (
    "cautions",
    "orientation",
    "keys",
    "graph",
    "issuing",
    "verification",
    "scope",
    "traceability",
    "break",
    "tamper",
    "implications",
    "infrastructure",
    "harmonisation",
    "exchange",
)

#: Shown first and outside the numbering. The cautions are read before anything else,
#: and they are not a chapter anything refers a reader to.
UNNUMBERED: Final[frozenset[str]] = frozenset({"cautions"})

#: ``[chapter](#scope)`` or ``[Chapter](#scope)``: a reference to another chapter by id.
#: On GitHub's preview of a file it reads as a link saying "chapter"; on the page it
#: becomes "chapter 5", still a link, with the number the rail shows.
_CHAPTER_REFERENCE: Final = re.compile(r"\[([Cc]hapter)\]\(#([a-z][a-z-]*)\)")

#: What a reference to a chapter that does not exist renders as, visibly, in the way a
#: missing block does. A test also fails on one.
UNKNOWN_CHAPTER: Final[str] = "[unknown chapter: "


def _kind(html: str) -> str:
    """Classify a rendered block, so a consumer knows what shape it is.

    Args:
        html: The rendered HTML.

    Returns:
        ``table``, ``list``, ``heading``, ``code`` or ``prose``. Used by the tests to
        assert that a key rendered as a panel title carries no markup and that a key
        rendered as a table really is one.
    """
    if html.startswith("<table"):
        return "table"
    if html.startswith(("<ul", "<ol")):
        return "list"
    if html.startswith("<h"):
        return "heading"
    if html.startswith("<pre"):
        return "code"
    return "prose"


def _parse(text: str) -> dict[str, str]:
    """Split a content file into its blocks.

    Args:
        text: The whole file.

    Returns:
        Each block's markdown by key, in the order they appear, which is the order the
        page renders them. Anything before the first marker is ignored, which is what
        lets a file open with a note addressed to whoever is editing it.
    """
    blocks: dict[str, str] = {}
    matches = list(_BLOCK.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks[match.group(1)] = text[match.end() : end].strip()
    return blocks


def _chapter_files() -> list[tuple[int, str, Path]]:
    """Find the chapter content files.

    Returns:
        One ``(position, chapter id, path)`` per chapter in :data:`CHAPTER_ORDER` that
        has a file. A file for a chapter not in the order is not served; a test asserts
        the files and the order match.
    """
    return [
        (position, chapter_id, CHAPTERS_ROOT / f"{chapter_id}.md")
        for position, chapter_id in enumerate(CHAPTER_ORDER)
        if (CHAPTERS_ROOT / f"{chapter_id}.md").is_file()
    ]


def chapter_ids() -> list[str]:
    """Return the chapter ids that have content, in the order the rail shows them.

    Returns:
        The ids.
    """
    return [chapter_id for _, chapter_id, _ in _chapter_files()]


def chapter_number(chapter_id: str) -> int:
    """Return the number the rail shows for a chapter.

    Args:
        chapter_id: The chapter.

    Returns:
        Its position among the numbered chapters, counting from 0.

    Raises:
        ValueError: If there is no such chapter, or it is one the rail does not number.
    """
    numbered = [item for item in CHAPTER_ORDER if item not in UNNUMBERED]
    if chapter_id not in numbered:
        raise ValueError(f"no numbered chapter {chapter_id!r}")
    return numbered.index(chapter_id)


def _numbered(match: re.Match[str], *, link: bool) -> str:
    """Render one chapter reference.

    Args:
        match: A match of :data:`_CHAPTER_REFERENCE`.
        link: Whether to keep the reference a markdown link.

    Returns:
        ``[chapter 5](#scope)`` with a link, ``chapter 5`` without, or a visible marker
        when the chapter does not exist.
    """
    word, chapter_id = match.groups()
    try:
        number = chapter_number(chapter_id)
    except ValueError:
        return f"{word} {UNKNOWN_CHAPTER}{chapter_id}]"
    return f"[{word} {number}](#{chapter_id})" if link else f"{word} {number}"


def number_chapter_references(markdown: str) -> str:
    """Give every ``[chapter](#id)`` in a block the number the rail shows.

    Args:
        markdown: One block's markdown, before it is rendered.

    Returns:
        The markdown with ``[chapter](#scope)`` written as ``[chapter 5](#scope)``, so
        it renders as a link saying "chapter 5".
    """
    return _CHAPTER_REFERENCE.sub(lambda match: _numbered(match, link=True), markdown)


def with_chapter_numbers(value: Any) -> Any:
    """Number the chapter references in plain text, wherever they sit in a payload.

    For the editorial fields in ``actors/harmonisation.py``, ``actors/deployment.py``
    and the UNTP probe's findings, which the page sets as text rather than HTML and
    which therefore cannot carry a link.

    Args:
        value: A string, or lists and dictionaries of them, as a route returns.

    Returns:
        The same shape, with each ``[chapter](#scope)`` written as ``chapter 5``.
    """
    if isinstance(value, str):
        return _CHAPTER_REFERENCE.sub(lambda match: _numbered(match, link=False), value)
    if isinstance(value, list):
        return [with_chapter_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: with_chapter_numbers(item) for key, item in value.items()}
    return value


_cache: dict[str, Any] | None = None
_cache_stamp: tuple[tuple[str, int], ...] | None = None


def _stamp() -> tuple[tuple[str, int], ...]:
    """Return a fingerprint of the content files as they are on disk now.

    Returns:
        One ``(name, modification time)`` per file -- one ``stat`` per migrated
        chapter, per request to ``/api/content``, which is once per page load. That is
        the price of an edit being visible on reload without restarting anything.
    """
    return tuple(
        (path.name, path.stat().st_mtime_ns) for _, _, path in _chapter_files()
    )


def content_payload() -> dict[str, Any]:
    """Return every chapter's blocks, rendered, for the interface to consume.

    Returns:
        ``{"chapters": {chapter id: {key: {"html", "text", "kind"}}}}``. Each block
        carries both forms because `ui.js` needs plain strings for panel titles, which
        it sets with ``text:``, and HTML for prose, which it sets with ``html:``.
    """
    global _cache, _cache_stamp
    stamp = _stamp()
    if _cache is not None and _cache_stamp == stamp:
        return _cache

    chapters: dict[str, dict[str, dict[str, str]]] = {}
    for _, chapter_id, path in _chapter_files():
        rendered: dict[str, dict[str, str]] = {}
        for key, markdown in _parse(path.read_text(encoding="utf-8")).items():
            html = render(number_chapter_references(markdown))
            # The text form is rendered from the plain-text references rather than
            # stripped from the links, because stripping a tag leaves a space where it
            # was: a title would read "Chapter 10 's claim".
            text = to_text(render(with_chapter_numbers(markdown)))
            rendered[key] = {"html": html, "text": text, "kind": _kind(html)}
        chapters[chapter_id] = rendered

    _cache = {"chapters": chapters}
    _cache_stamp = stamp
    return _cache


def blocks_for(chapter_id: str) -> dict[str, dict[str, str]]:
    """Return one chapter's rendered blocks.

    Args:
        chapter_id: The chapter, as it appears in the CHAPTERS array.

    Returns:
        The blocks, or an empty mapping for a chapter with no content file yet. Empty
        rather than raising, because the migration is chapter by chapter and a chapter
        still carrying its own literals is a normal intermediate state.
    """
    return content_payload()["chapters"].get(chapter_id, {})
