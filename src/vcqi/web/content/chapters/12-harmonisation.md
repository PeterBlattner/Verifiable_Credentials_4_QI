<!-- 12-harmonisation.md -- chapter 11 in the rail; the NN- prefix is the position in
     the CHAPTERS array, which counts the cautions. Rendered by chapterHarmonisation()
     in ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The items themselves -- every "What would have to be agreed", what this
     demonstration does, what already exists, the consequence and the forum -- are in
     src/vcqi/actors/harmonisation.py, as are the tier headings and the ladder of next
     steps. They are records of many correlated fields, and several of them are served
     to the reader as editorial text the verifier never sees.

     The placeholders in the open block -- {total}, {open} and {share} -- are counted
     from those items rather than written down, so that this page cannot overstate how
     much is unsolved. Leave the braces alone.

     The closing footnote stays in the code. It is one paragraph rendered straight into
     a p.footnote, and every accessor that returns markup wraps a block in a paragraph
     of its own, which would nest one inside the other. -->

<!-- block: title -->

What would have to be agreed

<!-- block: eyebrow -->

Harmonisation

<!-- block: lede -->

The minimum that has to be common for any of this to cross a border, what cannot be decided later however convenient that would be, and what a deployment can do without.

<!-- block: the-harder-question -->

The previous chapter asked what one organisation would have to run. This asks the harder question: what would they all have to agree with each other, so that a certificate written in one country means the same thing in another. That is the problem the quality infrastructure exists to solve, and signatures do not touch it.

Start with something this demonstration gets wrong, because it is the clearest case on the page.

<!-- block: one-string.title -->

Two organisations, one string

<!-- block: one-string.hint -->

fetch both — the BIPM publishes one, the accreditation body the other

<!-- block: one-string.body -->

Both say `dc.resistance`, and chapter 5 decides whether a calibration may carry the CIPM MRA logo by comparing those two strings for equality. They match because one author wrote both files. Two organisations that had never spoken would not have produced the same string, and the comparison would fail — not because the laboratory was outside its scope, but because nobody had agreed a name for resistance.

The instinct is to conclude that the metrology vocabularies are missing and would have to be invented. That is wrong, and worth correcting carefully: the BIPM already publishes permanent digital identifiers for every SI unit through the [SI Digital Framework](https://si-digital-framework.org/SI?lang=en), resolvable CMC identifiers already exist through the [KCDB-CMC service](https://si-digital-framework.org/kcdb-cmc/), and identifiers for measurands are being worked on at ISO and IEC. The finding is not that no vocabulary exists. It is that one exists and this demonstration did not use it.

<!-- block: one-test -->

What follows is sorted by one test, and anything failing it was left out: **two conforming implementations that differ here cannot interoperate.** That is what separates a harmonisation need from a deployment gap, and chapter 9 has the deployment gaps already. The tiers are meant to be read in order, because the order is the argument.

<!-- block: open.title -->

How much of this is actually open

<!-- block: open.hint -->

counted from the items below, not asserted

<!-- block: open.body -->

Of {total} items, **{open}** — about {share}% — have nothing to read yet. The rest have a specification, a register or a deployed mechanism behind them, and the work is adoption or a choice rather than invention.

That balance is a correction. The first version of this page filed seven items under *nothing exists yet*, and a reviewer who works on these specifications pointed out that five of them had answers — some published while this was being written, some still moving through as pull requests. The items below now open by saying what the earlier draft got wrong, which is left visible on purpose: a page about unsolved problems goes stale by overstating them, and one shown correction is a cheap warning that there are probably others.

What is left, once the answered items are set aside, is a short list and it is not a technical one: what a document authorises as distinct from what it attests, how three arrangements compose when no two of them share a technical body, which copy of a certificate governs, and whether anyone can undertake that an identifier still means the same organisation in thirty years. The last of those cannot be settled by evidence until something has been running for thirty years. Theories are available. Data is not.

<!-- block: the-ladder -->

The steps below are dependency structure rather than advice. Each rung is possible without the ones above it, and none of the upper rungs delivers anything without the lower ones — so whoever turns out to act, this is the order the blocking relationships force.

<!-- block: where-it-stops -->

Notice where the ladder stops. Every rung up to the fourth needs nobody’s permission, and the fifth needs one organisation to decide something about data it already owns. The sixth requires two arrangements to agree — and it is the one item here with no existing forum to agree it in, because the CIPM MRA and the Global ACI arrangement have no standing joint technical body. Creating somewhere for the conversation to happen is the real first step, and it is institutional rather than technical, which is usually the finding nobody wants.

The seventh rung is the newest and the odd one out. Legal metrology raised two questions the other two pillars never had to ask — what a document authorises as distinct from what it attests, and what identifies a design rather than one instrument — and both sit in the first tier, because getting either wrong is not a missing feature but a wrong answer. It is also the only rung whose forum plainly exists: the OIML has a standing structure for this conversation, which is more than the sixth rung can say.
