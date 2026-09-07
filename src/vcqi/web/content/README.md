# Editing the text

The words in this demonstration live in `chapters/*.md`. You can change them without
touching any code, and you do not need to install anything or run anything.

## How to change a sentence

1. Open the file for the chapter you want on GitHub — the list is in
   [`../../../../CONTENT.md`](../../../../CONTENT.md), which links straight to each one.
2. Click the pencil icon.
3. Edit the words.
4. At the bottom, choose **Create a new branch for this commit** and open a pull request.

The tests run automatically on the pull request. If something is wrong they will say
what, in plain terms, and nothing reaches the site until it is fixed.

## What a file looks like

A line beginning with `##` starts a **block**. Everything under it, until the next `##`,
is that block's text. The page asks for blocks by name.

```markdown
## lede

Written for someone who has not met verifiable credentials before.

## what-it-is

A **verifiable credential** is a document with a digital signature over it.

Blank lines separate paragraphs. This is a second one.
```

**Do not rename or delete a block.** The page asks for it by that name, so renaming it
means changing the code as well; a rename on its own will make the page show a red
`[missing content: …]` marker where the text used to be, and the tests will fail. Ask a
developer if a block genuinely needs renaming.

Adding a *new* block also needs a developer, because something has to tell the page
where to put it.

Changing the words inside a block is always safe.

## What you can write

| To get | Write |
| --- | --- |
| **bold** | `**bold**` |
| *italic* | `*italic*` |
| `code` or an identifier | `` `dc.resistance` `` |
| a link | `[the text](https://example.org)` |
| a new paragraph | leave a blank line |
| a bullet list | lines beginning `- ` |
| a numbered list | lines beginning `1. ` |
| a small heading | `### Like this` |
| a quotation | lines beginning `> ` |

Tables are written with pipes. The second line, with the dashes, is required:

```markdown
| Recognized Entities | Quality infrastructure |
| --- | --- |
| Root of trust | BIPM under the CIPM MRA |
```

Two things to know. `##` is reserved for starting a block, so a heading inside your text
must be `###` or smaller. And HTML is ignored rather than rendered — if you write
`<strong>x</strong>` the reader will see those angle brackets, so use `**x**`.

## Previewing

GitHub renders these files, so the preview on the file's page is a fair preview of the
words. It shows the block names as small headings, which the real page does not, but the
paragraphs, emphasis, lists and tables will look right.

Some blocks are used as short headings rather than as paragraphs — anything ending
`.title` or `.hint`, and `title`, `eyebrow` and `lede`. Those are shown as plain text, so
**bold** or a link in one of them would appear as literal asterisks or brackets. A test
checks for that and will tell you.

## What is *not* here

Some text in the demonstration is not in these files, and it is worth knowing which so
you are not left hunting:

- **Labels on buttons, sliders and options.** They are short and tied to the code that
  reads them.
- **The names and descriptions of the organisations, certificates and failure cases.**
  Those are data rather than prose; they live in `src/vcqi/actors/`.
- **The deployment and harmonisation tables** in the last two chapters, for the same
  reason — they are records with many fields, which a markdown file expresses badly.
- **The repository's own documents**, `README.md` and `ARCHITECTURE.md`, which are edited
  where they are.
- **The caution banner at the top of every page.** That one is in
  `../static/index.html`. It has to appear even when the server is unreachable and none of
  this has loaded, so it cannot come from here. The full statement behind it is
  `chapters/00-cautions.md`, which you *can* edit — but the same words are also in the
  repository's `README.md`, so a correction to one needs the same correction to the other
  or the site and the repository end up saying different things about how much to trust
  the work.

If you find yourself wanting to change something in that list, say so — the boundary is
a judgement rather than a law, and it can move.
