# Where the text is

The words in the demonstration live in markdown files, one per chapter. You can change
them from the GitHub web interface — no tools, no checkout, nothing to install. Click a
pencil icon, edit, and open a pull request; the tests run on it and say plainly if
something is wrong.

**Read [the editing guide](src/vcqi/web/content/README.md) first.** It is short, and it
covers the one rule that matters: `<!-- block: some-name -->` starts a block, and the
page asks for blocks by that name, so the words inside a block are yours to change but
the names are not.

## The chapters

Every chapter is here.

| # | Chapter | File |
| --- | --- | --- |
| — | About these pages, and what they are not | [`00-cautions.md`](src/vcqi/web/content/chapters/00-cautions.md) |
| 0 | What a verifiable credential is | [`01-orientation.md`](src/vcqi/web/content/chapters/01-orientation.md) |
| 1 | Keys: what a signature actually proves | [`02-keys.md`](src/vcqi/web/content/chapters/02-keys.md) |
| 2 | The quality infrastructure as a trust graph | [`03-graph.md`](src/vcqi/web/content/chapters/03-graph.md) |
| 3 | Issuing a certificate | [`04-issuing.md`](src/vcqi/web/content/chapters/04-issuing.md) |
| 4 | Verification and recognition discovery | [`05-verification.md`](src/vcqi/web/content/chapters/05-verification.md) |
| 5 | The CMC decides the logo | [`06-scope.md`](src/vcqi/web/content/chapters/06-scope.md) |
| 6 | Traceability and uncertainty | [`07-traceability.md`](src/vcqi/web/content/chapters/07-traceability.md) |
| 7 | Why the dependencies matter | [`08-dependencies.md`](src/vcqi/web/content/chapters/08-dependencies.md) |
| 8 | Break it | [`09-break.md`](src/vcqi/web/content/chapters/09-break.md) |
| 9 | What this would mean in practice | [`10-implications.md`](src/vcqi/web/content/chapters/10-implications.md) |
| 10 | What it would take to run | [`11-infrastructure.md`](src/vcqi/web/content/chapters/11-infrastructure.md) |
| 11 | What would have to be agreed | [`12-harmonisation.md`](src/vcqi/web/content/chapters/12-harmonisation.md) |
| 12 | How a credential moves | [`13-exchange.md`](src/vcqi/web/content/chapters/13-exchange.md) |

The cautions come first in the rail but carry no chapter number, because the prose refers
to chapters by number in a good many places and seating them at 0 would make every one of
those references wrong.

**The number on a file is not the chapter number.** It is the position in the `CHAPTERS`
array at the end of `src/vcqi/web/static/js/chapters.js`, which counts the cautions — so
`01-orientation.md` is chapter 0, and every file after it is one ahead of its chapter. The
prefix exists so that a directory listing reads in chapter order, and a test asserts the
two agree so the listing cannot lie. The authoritative order is that array, not this
table and not the file names.

## What is not here

The short caution banner at the top of every page. It is in
`src/vcqi/web/static/index.html`, as plain markup rather than in a content file, because
it has to be on the page even when the server cannot be reached and nothing has loaded —
which is exactly when a reader most needs it. The full statement behind it *is* editable
here, in `00-cautions.md`, and is mirrored in `README.md`; change one and change the other.

Button and slider labels, the names of the organisations and certificates, the failure
cases, and the tables behind chapters 10, 11 and 12. Those are data rather than prose and
live in `src/vcqi/actors/`. The editing guide explains why, and lists the few other things
that stayed in the code: a sentence built around a number the page has just worked out,
and three comparison tables that are assembled as tables rather than written as words.
The boundary can move if it turns out to be in the wrong place.

`README.md` and `ARCHITECTURE.md` are edited where they are.
