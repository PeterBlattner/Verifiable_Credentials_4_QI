# Where the text is

The words in the demonstration are moving into markdown files, one per chapter. For a
chapter that has one, you can change them from the GitHub web interface — no tools, no
checkout, nothing to install. Click a pencil icon, edit, and open a pull request; the tests
run on it and say plainly if something is wrong.

**Read [the editing guide](src/vcqi/web/content/README.md) first.** It is short, and it
covers the one rule that matters: `## some-name` starts a block, and the page asks for
blocks by that name, so the words inside a block are yours to change but the names are
not.

## The chapters

Fourteen pages. Two of them have a markdown file and can be edited as above. The other
twelve still carry their words as string literals inside
`src/vcqi/web/static/js/chapters.js`, so changing one of those means editing JavaScript —
or asking to have that chapter moved first, which is usually the better trade.

| # | Chapter | Where its words are |
| --- | --- | --- |
| — | About these pages, and what they are not | [`00-cautions.md`](src/vcqi/web/content/chapters/00-cautions.md) |
| 0 | What a verifiable credential is | [`01-orientation.md`](src/vcqi/web/content/chapters/01-orientation.md) |
| 1 | Keys: what a signature actually proves | `chapters.js`, `chapterKeys`, from line 139 |
| 2 | The quality infrastructure as a trust graph | `chapters.js`, `chapterGraph`, from line 437 |
| 3 | Issuing a certificate | `chapters.js`, `chapterIssuing`, from line 577 |
| 4 | Verification and recognition discovery | `chapters.js`, `chapterVerification`, from line 645 |
| 5 | The CMC decides the logo | `chapters.js`, `chapterScope`, from line 756 |
| 6 | Traceability and uncertainty | `chapters.js`, `chapterTraceability`, from line 1106 |
| 7 | Why the dependencies matter | `chapters.js`, `chapterDependencies`, from line 1263 |
| 8 | Break it | `chapters.js`, `chapterBreakIt`, from line 1379 |
| 9 | What this would mean in practice | `chapters.js`, `chapterImplications`, from line 1440 |
| 10 | What it would take to run | `chapters.js`, `chapterInfrastructure`, from line 1502 |
| 11 | What would have to be agreed | `chapters.js`, `chapterHarmonisation`, from line 1683 |
| 12 | How a credential moves | `chapters.js`, `chapterMoving`, from line 1849 |

Those line numbers drift as the file changes. The function name is the half of the pointer
worth trusting, and the authoritative order is the `CHAPTERS` array at the end of
`chapters.js` — not this table, and not the filenames.

The cautions come first in the rail but carry no chapter number, because the prose refers
to chapters by number in a good many places and seating them at 0 would make every one of
those references wrong.

**The number on a content file is not the chapter number.** It is the position in the
`CHAPTERS` array, which counts the cautions, so `01-orientation.md` is chapter 0 and the
files still to come will be `02-keys.md` through `13-exchange.md`. A test only asks that
the prefixes sort in the same order as the array, so the numbers themselves are free — but
running two conventions at once would make a directory listing lie about the order, which
is the one thing the prefix is there to prevent.

If you want to change something in a chapter that has no markdown file yet, say so and it
can be moved next — the order is not important, and doing one because someone actually
wants to edit it is a better reason than doing them in sequence.

## What is not here

The short caution banner at the top of every page. It is in
`src/vcqi/web/static/index.html`, as plain markup rather than in a content file, because
it has to be on the page even when the server cannot be reached and nothing has loaded —
which is exactly when a reader most needs it. The full statement behind it *is* editable
here, in `00-cautions.md`, and is mirrored in `README.md`; change one and change the other.

Button and slider labels, the names of the organisations and certificates, the failure
cases, and the tables in chapters 10, 11 and 12. Those are data rather than prose and live
in `src/vcqi/actors/`. The editing guide explains why, and the boundary can move if it
turns out to be in the wrong place.

`README.md` and `ARCHITECTURE.md` are edited where they are.
