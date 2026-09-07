"""Chapter prose, read from markdown files rather than compiled into JavaScript.

The twelve chapters used to carry their text as string literals inside `chapters.js`,
1799 lines of interactive code with about a hundred and twenty paragraphs threaded
through it. Correcting a sentence meant editing JavaScript, which put it out of reach of
everyone except whoever maintains the file.

So the prose lives in `content/chapters/*.md`, and this module reads it. The format is
one rule: a line matching ``## some-key`` starts a block, and everything until the next
such line is that block's markdown. There is no front matter and no second syntax --
``title``, ``eyebrow`` and ``lede`` are blocks like any other.

That rule was chosen over YAML front matter for a reason that decides it: **GitHub's own
preview of the file is a usable preview of the prose**. An editor working in the web UI
sees their paragraphs rendered, with the keys as small headings, and never has to think
about quoting a colon in a title. The cost is that ``##`` is reserved, so a heading
inside a block must be ``###`` -- and no chapter's prose contains a heading, so nothing
is given up.

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
    "MISSING_PREFIX",
    "chapter_ids",
    "content_payload",
    "blocks_for",
]

CONTENT_ROOT: Final[Path] = Path(__file__).parent / "content"
CHAPTERS_ROOT: Final[Path] = CONTENT_ROOT / "chapters"

#: A block key that no content file defines renders as this, so a typo costs one
#: paragraph and shows up as an obvious marker rather than as silence. See content.js
#: for the browser half.
MISSING_PREFIX: Final[str] = "[missing content: "

#: ``## key`` on a line of its own. Keys are lowercase and dotted for grouping, so that
#: ``mapping.title``, ``mapping.hint`` and ``mapping.rows`` read as belonging together.
_BLOCK: Final = re.compile(r"^## +([a-z0-9][a-z0-9.-]*)\s*$", re.MULTILINE)

#: ``01-orientation.md`` -> ``orientation``. The number is there so a directory listing
#: reads in chapter order; the authoritative order is the CHAPTERS array in chapters.js,
#: and a test asserts the two agree so the listing cannot lie.
_FILENAME: Final = re.compile(r"^(\d+)-([a-z][a-z-]*)$")


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
        page renders them. Anything before the first ``##`` is ignored, which is what
        lets a file open with an HTML comment addressed to whoever is editing it.
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
        One ``(order, chapter id, path)`` per file, sorted by the numeric prefix.
        Files whose names do not match the convention are skipped rather than guessed
        at; a test asserts the set matches the chapters the interface declares.
    """
    found: list[tuple[int, str, Path]] = []
    if not CHAPTERS_ROOT.is_dir():
        return found
    for path in sorted(CHAPTERS_ROOT.glob("*.md")):
        match = _FILENAME.match(path.stem)
        if match:
            found.append((int(match.group(1)), match.group(2), path))
    return sorted(found)


def chapter_ids() -> list[str]:
    """Return the chapter ids that have content, in file order.

    Returns:
        The ids, taken from the filenames.
    """
    return [chapter_id for _, chapter_id, _ in _chapter_files()]


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
            html = render(markdown)
            rendered[key] = {"html": html, "text": to_text(html), "kind": _kind(html)}
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
