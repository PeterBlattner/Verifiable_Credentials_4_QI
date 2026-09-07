"""A small markdown renderer, for prose this repository controls.

The chapter text lives in markdown files so that correcting a sentence does not mean
editing JavaScript. Turning that markdown into HTML needs a renderer, and this is it:
about two hundred lines covering the subset an editor of this material actually writes.

Taking a dependency was the obvious alternative and `markdown-it-py` would have been the
choice. Two things argued the other way. The repository already does this deliberately
elsewhere -- `crypto/jcs.py` and `crypto/multibase.py` are implemented in-repo rather
than imported, and ARCHITECTURE.md has a section on why -- so a reader who wants to
understand the demonstration end to end can, without reading a third-party parser. And
the README's claim that there is no build step and nothing to install stays literally
true, which matters more for a demonstrator than for a library.

The narrower reason is safety, and it is the one that would decide it alone. A general
parser has to be told not to pass HTML through; this one has no such path. Every piece
of text is escaped on the way out, and the only tags in the result are ones this module
emitted. That makes handing the output to `innerHTML` defensible -- and it is a stricter
position than the code being replaced, where `chapters.js` hand-wrote `<strong>` into
string literals that went through `innerHTML` unexamined.

What is supported, which is what the prose being moved uses:

- paragraphs, separated by blank lines
- ``**bold**``, ``*italic*``, ``` `code` ```
- ``[text](url)``
- ``-`` and ``1.`` lists, one level
- ``>`` blockquotes
- ``###`` and deeper headings (``##`` is reserved: it delimits blocks, see content.py)
- ``---`` horizontal rules
- GFM pipe tables, which get the class the interface already styles
- fenced code blocks

What is not, deliberately: raw HTML, reference-style links, nested lists, images,
footnotes, and anything resembling a template. If a block needs logic it belongs in
JavaScript, and that boundary is what stops a content layer becoming a CMS.

Note for later: the repository's own documents (README, ARCHITECTURE) use
reference-style links and nested lists, so publishing those needs this extended or a real
CommonMark parser. That decision belongs with that change, not this one.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["render", "render_inline", "to_text"]

_ESCAPES: Final[tuple[tuple[str, str], ...]] = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
)

#: Inline spans, applied in this order. Code first, so that a backtick span protects
#: whatever is inside it from being read as emphasis.
_CODE: Final = re.compile(r"`([^`]+)`")
_LINK: Final = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_STRONG: Final = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.DOTALL)
_EMPHASIS: Final = re.compile(r"(?<![\w*])\*(?=\S)([^*]+?)(?<=\S)\*(?![\w*])")

_HEADING: Final = re.compile(r"^(#{3,6})\s+(.*)$")
_BULLET: Final = re.compile(r"^[-*]\s+(.*)$")
_NUMBERED: Final = re.compile(r"^\d+[.)]\s+(.*)$")
_QUOTE: Final = re.compile(r"^>\s?(.*)$")
_RULE: Final = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
_FENCE: Final = re.compile(r"^```+\s*([\w-]*)\s*$")
_TABLE_DIVIDER: Final = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_TAG: Final = re.compile(r"<[^>]+>")


def _escape(text: str) -> str:
    """Escape the characters that would otherwise be read as markup.

    Args:
        text: Plain text.

    Returns:
        The text, safe to place in an element body or a quoted attribute.
    """
    for character, entity in _ESCAPES:
        text = text.replace(character, entity)
    return text


def _safe_url(url: str) -> str:
    """Return a link target, or "#" for one that should not be followed.

    Only the schemes this material has any business using are allowed. A ``javascript:``
    or ``data:`` target would be a way to smuggle behaviour into a content file, and
    while the content files are reviewed like code, a renderer should not depend on
    that being true forever.

    Args:
        url: The target as written.

    Returns:
        The escaped target, or "#" when the scheme is not permitted.
    """
    stripped = url.strip()
    lowered = stripped.lower()
    if lowered.startswith(("http://", "https://", "mailto:", "#", "/")):
        return _escape(stripped).replace('"', "&quot;")
    return "#"


def render_inline(text: str) -> str:
    """Render the inline part of markdown: emphasis, code and links.

    Args:
        text: One logical line or paragraph of markdown, unescaped.

    Returns:
        HTML. Text is escaped first, so nothing in the input can introduce a tag; the
        substitutions below are the only source of markup in the result.
    """
    # Code spans are extracted before escaping so their contents are escaped exactly
    # once and never scanned for emphasis, which is what makes `**` inside code work.
    spans: list[str] = []

    def keep(match: re.Match[str]) -> str:
        spans.append(_escape(match.group(1)))
        return f"\x00{len(spans) - 1}\x00"

    text = _CODE.sub(keep, text)
    text = _escape(text)
    text = _LINK.sub(
        lambda m: f'<a href="{_safe_url(m.group(2))}" rel="noopener">{m.group(1)}</a>',
        text,
    )
    text = _STRONG.sub(lambda m: f"<strong>{m.group(1)}</strong>", text)
    text = _EMPHASIS.sub(lambda m: f"<em>{m.group(1)}</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{spans[int(m.group(1))]}</code>", text)


def _render_table(rows: list[str]) -> str:
    """Render a GFM pipe table.

    Args:
        rows: The table's lines, header first, divider second.

    Returns:
        HTML for the table, carrying the class the interface already styles so that a
        markdown table looks like the ones `ui.js` builds. That is why `table()` did not
        have to change.
    """

    def cells(line: str) -> list[str]:
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        return [cell.strip() for cell in line.split("|")]

    header, *body = [row for index, row in enumerate(rows) if index != 1]
    parts = ['<table class="data">', "<thead><tr>"]
    parts += [f"<th>{render_inline(cell)}</th>" for cell in cells(header)]
    parts.append("</tr></thead>")
    if body:
        parts.append("<tbody>")
        for row in body:
            parts.append("<tr>")
            parts += [f"<td>{render_inline(cell)}</td>" for cell in cells(row)]
            parts.append("</tr>")
        parts.append("</tbody>")
    parts.append("</table>")
    return "".join(parts)


def render(markdown: str) -> str:
    """Render a block of markdown to HTML.

    Args:
        markdown: The block, as written in a content file.

    Returns:
        HTML, safe to assign to ``innerHTML``: every character of the input is escaped
        and every tag in the output was emitted here.
    """
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    paragraph: list[str] = []
    index = 0

    def flush() -> None:
        """Emit the paragraph collected so far, if any."""
        if paragraph:
            out.append(f"<p>{render_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            flush()
            index += 1
            continue

        fence = _FENCE.match(stripped)
        if fence:
            flush()
            language = fence.group(1)
            index += 1
            body: list[str] = []
            while index < len(lines) and not _FENCE.match(lines[index].strip()):
                body.append(lines[index])
                index += 1
            index += 1  # the closing fence
            attribute = f' data-language="{_escape(language)}"' if language else ""
            out.append(f'<pre class="code"{attribute}>{_escape(chr(10).join(body))}</pre>')
            continue

        if _RULE.match(stripped):
            flush()
            out.append("<hr>")
            index += 1
            continue

        heading = _HEADING.match(stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            out.append(f"<h{level}>{render_inline(heading.group(2))}</h{level}>")
            index += 1
            continue

        # A table is only a table if the second line is a divider; otherwise a line
        # containing a pipe is just a line containing a pipe.
        if "|" in stripped and index + 1 < len(lines) and _TABLE_DIVIDER.match(lines[index + 1]):
            flush()
            rows = []
            while index < len(lines) and "|" in lines[index]:
                rows.append(lines[index])
                index += 1
            out.append(_render_table(rows))
            continue

        if _QUOTE.match(stripped):
            flush()
            quoted: list[str] = []
            while index < len(lines) and _QUOTE.match(lines[index].strip()):
                quoted.append(_QUOTE.match(lines[index].strip()).group(1))
                index += 1
            out.append(f"<blockquote>{render(chr(10).join(quoted))}</blockquote>")
            continue

        bullet = _BULLET.match(stripped)
        numbered = _NUMBERED.match(stripped)
        if bullet or numbered:
            flush()
            tag = "ul" if bullet else "ol"
            pattern = _BULLET if bullet else _NUMBERED
            items: list[str] = []
            while index < len(lines):
                candidate = lines[index].strip()
                match = pattern.match(candidate)
                if match:
                    items.append(match.group(1))
                    index += 1
                elif candidate and not _BULLET.match(candidate) and not _NUMBERED.match(candidate):
                    # A continuation line, indented under its item.
                    if lines[index].startswith((" ", "\t")) and items:
                        items[-1] += " " + candidate
                        index += 1
                    else:
                        break
                else:
                    break
            out.append(
                f"<{tag}>" + "".join(f"<li>{render_inline(item)}</li>" for item in items) + f"</{tag}>"
            )
            continue

        paragraph.append(stripped)
        index += 1

    flush()
    return "".join(out)


def to_text(html: str) -> str:
    """Reduce rendered HTML to the words in it.

    Panel titles and hints go through `ui.js`'s ``text:`` rather than ``html:``, so a
    plain form of every block is served alongside the HTML one. Safe to do by stripping
    tags precisely because the only tags present are ones :func:`render` emitted.

    Args:
        html: HTML from :func:`render`.

    Returns:
        The text, with entities resolved and whitespace collapsed.
    """
    text = _TAG.sub(" ", html)
    for character, entity in reversed(_ESCAPES):
        text = text.replace(entity, character)
    text = text.replace("&quot;", '"')
    return re.sub(r"\s+", " ", text).strip()
