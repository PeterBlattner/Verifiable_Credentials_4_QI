# Working plan

The change set being worked on now, with its checklist and progress log. When one is
finished it moves to `docs/history/`, so this file stays short enough to read.

- `docs/history/PLAN-2026.md`: change sets 1 to 33, from the first demonstrator to the
  XML-signature profile check, each with its context, decisions and progress log.
- `docs/history/firstPrompt.md`: the question the project started from.

# Change set 34 - documentation that cannot drift from the code (#73)

## Context

Issue #73, found at 12be858. The README said 23 failure cases where `tamper.py` had 24;
the comment above `/api/keys/*` still leans on "the server binds to localhost"; and the
prose writes chapter numbers by hand, which is why the files' prefixes and the numbers a
reader sees differ by one (`08-break.md` is chapter 7) and why the cautions page could
not take a number. The root cause the issue names is volume: README, ARCHITECTURE.md,
PLAN.md and the chapters run to tens of thousands of words.

Already done before this change set: the count was corrected in #84 and has been tested
since #96.

## Decisions

Taken with Peter:
- **Chapters are referred to by id.** Prose writes `[chapter](#scope)`, and the number is
  rendered when the page is served, as a link to the chapter. Files are named by id. The
  order is declared once, and a test keeps `chapters.js` in step with it.
- **History is archived, not deleted.** Change sets 1 to 33 went to
  `docs/history/PLAN-2026.md` and `firstPrompt.md` to `docs/history/`. The root PLAN.md
  keeps the current change set, so the plan-in-the-root workflow is unchanged.
- **The README's figures are tested against the code**, as the failure-case count
  already is.

## Checklist

- [x] 1. Archive: change sets 1 to 33 and `firstPrompt.md` into `docs/history/`, and the
      references to them repointed
- [x] 2. The localhost comment above `/api/keys/*` in `web/app.py`
- [x] 3. Tests for the README's figures
- [x] 4. Chapter references by id, and files named by id
- [x] 5. Docs: CONTENT.md, `web/content/README.md`, README.md, ARCHITECTURE.md
- [x] 6. Verification: the full suite, the click harness, the chapter snapshot

## Progress log

- 2026-09-30: agreed in conversation. Peter chose references by id and a live PLAN.md
  with the history archived. Branch `fix/documentation-drift` from `develop`.
- 2026-09-30: items 1 to 3 done.
  - The archive went in two commits: the move alone, then the new PLAN.md, so git sees a
    rename and `git log --follow docs/history/PLAN-2026.md` keeps all 48 commits.
  - `tests/test_readme.py` checks the README's figures: 86 documents; thirteen
    organisations and three arrangements; eight types; five editable documents; eleven
    checks, 98 retrievals and 35 distinct documents; 20 of 35 that can travel; nine
    status lists and 1,179,648 positions; and the chapter list.
    - Not checked: the breakdown of the 20 by kind, which the audit does not report.
    - Deliberate break: 86 changed to 85 and eleven to nine failed exactly those two.
- 2026-09-30: items 4 to 6 done.
  - **The order.** `CHAPTER_ORDER` and `UNNUMBERED` in `web/content.py`, with
    `chapter_number`. The files are `chapters/<id>.md`, renamed with `git mv`.
  - **The syntax.** `[chapter](#scope)` or `[Chapter](#scope)`.
    - The prose gets `[chapter 5](#scope)`, rendered as a link; following one in a DOM
      lands on the chapter the rail numbers the same.
    - `with_chapter_numbers` gives plain text for `/api/harmonisation`,
      `/api/infrastructure` and `/api/untp`.
    - The text form of a block is rendered from the plain-text references. Stripping
      the link left a space, so a title read "Chapter 10 's claim", which the
      plain-text-slot test caught.
    - An unknown id renders a visible `[unknown chapter: …]` marker.
  - **Every reference, reviewed against its context.**
    - 55 reader-facing references became links by id; they already pointed where
      today's numbering says.
    - About 110 in code, tests, tools and documents became names ("the scope chapter").
    - Three were wrong when written, because the order had changed since: JCS "so
      chapter 2 can show the bytes" (issuing), and "chapter 2's lesson" in `xmldsig.py`
      and `test_exchange.py` (keys). One anecdote in `ui-clicks.mjs` now says "one
      chapter", since the numbering on 5 September cannot be trusted.
  - **Wrapping.** A script re-wrapped only the paragraphs the renaming pushed past 88
    columns. It mangled one `//:` comment in `ui-clicks.mjs`, which the syntax check
    caught and which was restored.
  - **Code unchanged.** Every changed Python file has the same syntax tree as on
    `develop` with strings blanked, except the three meant to change (`app.py`,
    `content.py`, `test_content.py`). Served editorial text is identical once rendered.
  - **Tests.** The number prefix test is replaced by: files equal the order; `CHAPTERS`
    in `chapters.js` equals the order and the unnumbered set; no number written by
    hand in the package, tests, tools or first-time documents; every id is a numbered
    chapter; the rendering; and CONTENT.md's table.
    - Deliberate breaks, each restored: "chapter 11" written by hand; `#harmonization`;
      `break` and `tamper` swapped in the order. Each failed exactly its tests.
  - Full suite: 874 pass, 46 skipped (859 before). `ui-clicks.mjs`: every control
    responds. `--dump` is byte-identical.

## Git

Branch `fix/documentation-drift` from `develop`, into `develop`.
