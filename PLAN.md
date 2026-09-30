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
- [ ] 2. The localhost comment above `/api/keys/*` in `web/app.py`
- [ ] 3. Tests for the README's figures
- [ ] 4. Chapter references by id, and files named by id
- [ ] 5. Docs: CONTENT.md, `web/content/README.md`, README.md, ARCHITECTURE.md
- [ ] 6. Verification: the full suite, the click harness, the chapter snapshot

## Progress log

- 2026-09-30: agreed in conversation. Peter chose references by id and a live PLAN.md
  with the history archived. Branch `fix/documentation-drift` from `develop`.

## Git

Branch `fix/documentation-drift` from `develop`, into `develop`.
