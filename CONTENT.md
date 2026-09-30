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
| — | About these pages, and what they are not | [`cautions.md`](src/vcqi/web/content/chapters/cautions.md) |
| 0 | What a verifiable credential is | [`orientation.md`](src/vcqi/web/content/chapters/orientation.md) |
| 1 | Keys: what a signature actually proves | [`keys.md`](src/vcqi/web/content/chapters/keys.md) |
| 2 | The quality infrastructure as a trust graph | [`graph.md`](src/vcqi/web/content/chapters/graph.md) |
| 3 | Issuing a Verifiable Credential | [`issuing.md`](src/vcqi/web/content/chapters/issuing.md) |
| 4 | Verification and recognition discovery | [`verification.md`](src/vcqi/web/content/chapters/verification.md) |
| 5 | The CMC decides the logo | [`scope.md`](src/vcqi/web/content/chapters/scope.md) |
| 6 | Traceability and uncertainty | [`traceability.md`](src/vcqi/web/content/chapters/traceability.md) |
| 7 | Break it | [`break.md`](src/vcqi/web/content/chapters/break.md) |
| 8 | Break it yourself | [`tamper.md`](src/vcqi/web/content/chapters/tamper.md) |
| 9 | What this would mean in practice | [`implications.md`](src/vcqi/web/content/chapters/implications.md) |
| 10 | What it would take to run | [`infrastructure.md`](src/vcqi/web/content/chapters/infrastructure.md) |
| 11 | What would have to be agreed | [`harmonisation.md`](src/vcqi/web/content/chapters/harmonisation.md) |
| 12 | How a credential moves | [`exchange.md`](src/vcqi/web/content/chapters/exchange.md) |

The cautions come first in the rail and carry no number, because nothing refers a reader
to them.

**Each file is named by its chapter's id**, and the number is not written anywhere a
reader sees. To send a reader to another chapter, write `[chapter](#scope)`, or
`[Chapter](#scope)` at the start of a sentence: the page shows it as "chapter N", linked
to that chapter. So a chapter can move without any sentence having to change. The order
is `CHAPTER_ORDER` in `src/vcqi/web/content.py`; this table follows it, and a test
checks that it does.

## What is not here

The short caution banner at the top of every page. It is in
`src/vcqi/web/static/index.html`, as plain markup rather than in a content file, because
it has to be on the page even when the server cannot be reached and nothing has loaded —
which is exactly when a reader most needs it. The full statement behind it *is* editable
here, in `cautions.md`, and is mirrored in `README.md`; change one and change the other.

Button and slider labels, the names of the organisations and certificates, the failure
cases, and the tables behind the infrastructure, harmonisation and exchange chapters.
Those are data rather than prose and live in `src/vcqi/actors/`. The editing guide
explains why, and lists the few other things that stayed in the code: a sentence built
around a number the page has just worked out, and three comparison tables that are
assembled as tables rather than written as words. The boundary can move if it turns out
to be in the wrong place.

`README.md` and `ARCHITECTURE.md` are edited where they are.
