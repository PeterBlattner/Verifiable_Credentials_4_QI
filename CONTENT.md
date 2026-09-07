# Where the text is

The words in the demonstration live in markdown files, one per chapter. You can change
them from the GitHub web interface — no tools, no checkout, nothing to install. Click a
pencil icon, edit, and open a pull request; the tests run on it and say plainly if
something is wrong.

**Read [the editing guide](src/vcqi/web/content/README.md) first.** It is short, and it
covers the one rule that matters: `## some-name` starts a block, and the page asks for
blocks by that name, so the words inside a block are yours to change but the names are
not.

## The chapters

| # | Chapter | File |
| --- | --- | --- |
| — | About these pages, and what they are not | [`00-cautions.md`](src/vcqi/web/content/chapters/00-cautions.md) |
| 0 | What a verifiable credential is | [`01-orientation.md`](src/vcqi/web/content/chapters/01-orientation.md) |

The cautions come first in the rail but carry no chapter number, because the prose refers
to chapters by number in a good many places and seating them at 0 would make every one of
those references wrong.

Chapters not listed above still carry their text inside
`src/vcqi/web/static/js/chapters.js` and are being moved a chapter at a time. If you want
to change something in one of those, say so and it can be moved next — the order is not
important, and doing one because someone actually wants to edit it is a better reason
than doing them in sequence.

## What is not here

The short caution banner at the top of every page. It is in
`src/vcqi/web/static/index.html`, as plain markup rather than in a content file, because
it has to be on the page even when the server cannot be reached and nothing has loaded —
which is exactly when a reader most needs it. The full statement behind it *is* editable
here, in `00-cautions.md`, and is mirrored in `README.md`; change one and change the other.

Button and slider labels, the names of the organisations and certificates, the failure
cases, and the tables in the last two chapters. Those are data rather than prose and live
in `src/vcqi/actors/`. The editing guide explains why, and the boundary can move if it
turns out to be in the wrong place.

`README.md`, `ARCHITECTURE.md` and `LEGAL-METROLOGY.md` are edited where they are.
