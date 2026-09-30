<!-- harmonisation.md -- rendered by chapterHarmonisation() in ../../static/js/chapters.js.
     To send a reader to another chapter, write [chapter](#scope), or [Chapter](#scope)
     to start a sentence: the page shows the number the rail gives it.

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

Both say `dc.resistance`, and [chapter](#scope) decides whether a calibration may carry the CIPM MRA logo by comparing those two strings for equality. They match because one author wrote both files. Two organisations that had never spoken would not have produced the same string, and the comparison would fail — not because the laboratory was outside its scope, but because nobody had agreed a name for resistance.

The instinct is to conclude that the metrology vocabularies are missing and would have to be invented. That is wrong, and worth correcting carefully: the BIPM already publishes permanent digital identifiers for every SI unit through the [SI Digital Framework](https://si-digital-framework.org/SI?lang=en), resolvable CMC identifiers already exist through the [KCDB-CMC service](https://si-digital-framework.org/kcdb-cmc/), and identifiers for measurands are being worked on at ISO and IEC. The finding is not that no vocabulary exists. It is that one exists and this demonstration did not use it.

<!-- block: one-test -->

What follows is sorted by one test, and anything failing it was left out: **two conforming implementations that differ here cannot interoperate.** That is what separates a harmonisation need from a deployment gap, and [chapter](#implications) has the deployment gaps already. The tiers are meant to be read in order, because the order is the argument.

How a list like this gets made is worth one paragraph, because the obvious method would have missed the newest items on it. The obvious method is to tabulate the recognition relationships across the whole quality infrastructure — who recognises whom, for what, under which arrangement — and read the common vocabulary off the table. That is a good exercise and it should be done. It would also have produced a scope with a quantity, a range and an uncertainty in it, which is exactly the model this demonstration started with and had to throw away. The grammars a real scope uses, and the rows that cannot be written down at all, became visible only when something had to decide a case and could not. A table of relationships and one chain built end to end find different problems, and neither finds the other's.

<!-- block: open.title -->

How much of this is actually open

<!-- block: open.hint -->

counted from the items, not asserted — press a count to list only those

<!-- block: open.body -->

Of {total} items, **{open}** — about {share}% — have nothing to read yet. The rest have a specification, a register or a deployed mechanism behind them, and the work is adoption or a choice rather than invention.

An earlier version of this page filed seven items under *nothing exists yet*, and a reviewer who works on these specifications showed that five of them had answers. Those items still open by saying what the first draft got wrong, on purpose: a page about unsolved problems goes stale by overstating them.

The open items that will take longest are not technical. What a document authorises as distinct from what it attests, how three arrangements compose when no two of them share a technical body, which copy of a certificate governs, and what a verdict is good enough for are questions about who decides, and no specification can answer them on anyone's behalf.

<!-- block: map.title -->

All of it at a glance

<!-- block: map.hint -->

pick a topic, or press an item to open it in the list below

<!-- block: filter.none -->

Nothing matches both filters. Pick another topic, or show every status.

<!-- block: filter.empty-tier -->

Nothing in this tier matches.

<!-- block: probe.title -->

One of them tried rather than argued

<!-- block: probe.hint -->

two certificates and two recognitions really projected, validated and expanded, against pinned UNTP

<!-- block: probe.summary -->

Two of this demonstration's certificates and the two recognitions behind them, expressed in UN/CEFACT's formats, validated against the published UNTP schemas and run through the UNTP Playground. The envelope now reaches calibration. What stops at the border is the uncertainty and the identifiers: the parts that make a measurement comparable rather than merely reported.

<!-- block: probe.body -->

The certificate-format item weighs one mature format without international standing against one with standing. That is a claim, and a claim on a page like this is worth more once somebody has run it. So two of this demonstration's certificates are expressed in UN/CEFACT's Digital Conformity Credential, validated against the published UNTP schema and expanded against the published contexts — a calibration certificate, which the format was not built for, and a certificate of conformity, which it was.

The rule the projection follows is the only thing that makes the result mean anything: **where UNTP requires something the certificate does not state, it is left out and the reason recorded, never filled in with a plausible value.** Where the certificate states something UNTP refuses, it is carried anyway and the refusal recorded. Where the projection supplies a value the certificate does not literally state — a code from one of UNTP's lists — that is recorded too, as a judgement. The schema complaining is the finding rather than a fault to be tidied away.

More arrives than the first run of this probe, against UNTP 0.6.0, suggested. A calibration is no longer forced into a verdict: `conformance` is optional. `conformityTopic` is an open list, and UNTP's own topic vocabulary has `metrology-and-measurement` — the accuracy and traceability of measurements and calibrations to national and international measurement standards — and `product-safety-standards` for the kettle. The conditions of measurement travel as text in `specifiedCondition`. The authority behind each certificate travels as an endorsement naming whoever issued the recognition or the accreditation, with a link to it.

What still does not arrive is the uncertainty. `Measure` holds a value, a unit and two tolerances, and a tolerance is a limit — UNTP's own example reads 10 kg + 0.1 kg — where an Expanded Uncertainty at k=2 is a coverage interval. Writing one into the other would restate a 95 % statement as a certainty, so the value travels rounded as the certificate reports it, and without its uncertainty. Three identifiers UNTP requires do not exist on this side: one for the measurand, which ISO and IEC are still defining; one for the scheme, since nothing here gives the CIPM MRA an identifier; and one for IEC 60335-1, which the certificate names by its designation. The unit arrives as a UNECE Recommendation 20 code, `OHM`, expanded against UN/CEFACT's code list — a second register beside the BIPM's.

One layer up, the recognitions go the same way. UN/CEFACT's counterpart of a W3C recognition is the Digital Identity Anchor, in which a registrar says that a DID belongs to an entity in its register. So the BIPM's recognition of METAS and the Swiss Accreditation Service's recognition of the certification body are each expressed as an anchor too — one per entity, since an anchor names one where a recognition lists several. The entity arrives, with its registrar, its entry on the registrar's site and the capabilities it is recognised for, as a list of links. What does not arrive is the part a verifier acts on: what the entity is recognised to *do*, the `outputValidation` schemas a document issued under the recognition must satisfy — the check [chapter](#verification) runs — and the validity of each recognised action. UNTP also wants a registration number and a first-registration date that no recognition here states, and its register types stop at accreditation, so the CIPM MRA has none.

One thing is carried and refused. The W3C Bitstring Status List Recommendation says a status index is an integer written as a string, and so does UNTP's own description of the member, but UNTP's schema types it as a number. The projection writes it the way W3C does, and the schema says so.

Two things this panel said before are withdrawn. It read UNTP 0.6.0's `GlobalMRA` as the CIPM MRA and said UNTP already distinguished it from accreditation. UNTP 0.7.0 defines `authority-globalmra` as accreditation under the Global Accreditation Cooperation MRA and has no code for the CIPM MRA at all, so the calibration here carries `authority-peer`, recorded as a judgement rather than presented as a fit. And the 0.6.0 projection filled two required parties with the scope document itself, so the scheme appeared to have issued itself — exactly the plausible value the rule forbids, and invisible to a check that only counted errors. Each authority is now whoever issued the document it rests on, and a test says so.

So the reading is sharper again. UNTP's envelope now reaches calibration, and what stops at the border is the uncertainty and the identifiers: the parts that make a measurement comparable rather than merely reported.

<!-- block: probe.unavailable -->

The probe could not be run. The rest of this chapter is unaffected — it is an argument and a list, and neither depends on this panel. The most likely reason is a server started before this check existed, which a reader who left the demonstrator running while pulling would hit; restarting it is the fix.

<!-- block: probe.errors.title -->

What the UNTP schema says about the result

<!-- block: probe.errors.hint -->

the validator's own words, not a summary of them

<!-- block: probe.accounted -->

Every error above is a finding this projection recorded at the same member and can explain, and the test suite asserts that member by member. A projection that starts failing for a reason nobody wrote down fails the build instead of being read as a finding, and so does one that quietly fills a member it had recorded as missing.

<!-- block: probe.terms.title -->

Terms that do not expand

<!-- block: probe.terms.hint -->

against the pinned W3C and UNTP contexts, checked offline

<!-- block: probe.expands -->

Every type and property in all four documents expands against the pinned contexts. That is this project's own check, written by the same hand as the projection, so the documents were also run through the UNTP Playground: its JSON-LD step expanded all four, and its schema step reported exactly the errors above and nothing else. The runs are recorded in `docs/history/PLAN-2026.md`.

<!-- block: probe.unaccounted -->

The schema is reporting errors this projection did not choose and cannot explain. That is a bug in the mapping rather than a finding about the format, and it should be treated as one.

<!-- block: the-ladder -->

The steps below are dependency structure rather than advice. Each rung is possible without the ones above it, and none of the upper rungs delivers anything without the lower ones — so whoever turns out to act, this is the order the blocking relationships force.

<!-- block: where-it-stops -->

Notice where the ladder stops. Every rung up to the fourth needs nobody’s permission, and the fifth needs one organisation to decide something about data it already owns. The sixth requires two arrangements to agree — and it is the one item here with no existing forum to agree it in, because the CIPM MRA and the Global ACI arrangement have no standing joint technical body. Creating somewhere for the conversation to happen is the real first step, and it is institutional rather than technical, which is usually the finding nobody wants.

The seventh rung is the newest and the odd one out. Legal metrology raised two questions the other two pillars never had to ask — what a document authorises as distinct from what it attests, and what identifies a design rather than one instrument — and both sit in the first tier, because getting either wrong is not a missing feature but a wrong answer. It is also the only rung whose forum plainly exists: the OIML has a standing structure for this conversation, which is more than the sixth rung can say.
