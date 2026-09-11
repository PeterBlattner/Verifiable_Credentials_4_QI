<!-- 07-traceability.md -- chapter 6 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterTraceability() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The budget panels are titled from the certificate they show, so their headings are
     built in the code rather than here. The slider labels and table headers stay there
     too: they are labels, not sentences.

     The blocks from representations.title downwards belong to the four representation
     tabs. Those are built by helpers shared with nothing else, so they read their words
     from this file. The field-mapping table and the two signature comparison tables stay
     in the code: they are assembled as table elements, and dropping them in from here
     would wrap each in a div.

     Everything from dcc down -- the mapping panel, the document, what is said twice, and
     the signature comparison -- appears only when a reader selects the PTB/DKD DCC tab,
     because all of it is about wrapping that document in a credential. A certificate
     carrying no PTB/DKD DCC shows the single line in no-dcc instead.

     "{inputs}" in the unclib block is the number of input quantities the certificate
     actually carries. Leave the braces alone. -->

<!-- block: title -->

Traceability and uncertainty

<!-- block: eyebrow -->

Where the numbers come from

<!-- block: lede -->

The credential chain and the traceability chain are the same chain. The uncertainty grows measurably along it.

<!-- block: the-chain -->

Metrological traceability is an unbroken chain of calibrations back to a realisation of the unit, each with a stated uncertainty. The credential chain has exactly the same shape, and each certificate inherits its parent’s result as the first line of its own budget.

Because the budget travels inside the credential, a recipient can check two things no signature could tell it: that the stated uncertainty really is the quadrature sum of the contributions offered for it, and that the inherited line matches what the parent certificate actually reports.

<!-- block: chain.title -->

Expanded uncertainty down the chain

<!-- block: chain.hint -->

Relative U at k = 2. Each step inherits everything above it and can only add

<!-- block: recompute.title -->

Recompute the laboratory budget

<!-- block: recompute.hint -->

Propagated with metas_unclib, which keeps track of where each uncertainty came from

<!-- block: try-dragging -->

Try dragging the inherited uncertainty far down. The budget still adds up, the certificate would still be validly signed, and the laboratory would still be genuinely accredited — but the result becomes better than its accreditation allows, and the inherited line stops matching the certificate it names. Those are the last two checks in the pipeline, and they are the only things that would notice.

<!-- block: representations.title -->

One measurement, four ways of handing it over

<!-- block: classical -->

This is the whole of what a calibration certificate has stated for as long as calibration certificates have existed, and for most purposes it is enough. It tells you how good the number is.

What it cannot tell you is anything about *where* the uncertainty came from. Two certificates reported this way are, as far as any recipient can determine, unrelated — even when both rest on the same reference standard in the same laboratory.

<!-- block: no-dependencies -->

This certificate carries no dependency representation.

<!-- block: unclib -->

The same result, transmitted with everything it depends on: {inputs} input quantities, each with its own identifier, its distribution, and the sensitivity of the result to it.

The identifiers are what matter. They travel with the number, so an influence stays recognisable wherever it turns up again, and a recipient combining two results can tell that part of their uncertainty is one and the same thing.

<!-- block: as-transmitted.title -->

As transmitted

<!-- block: binary.title -->

The same thing, in binary

<!-- block: binary.hint -->

Published separately and referenced by digest, which is what the binary form is for: a result depending on thousands of influences, as an ordinary scattering-parameter measurement does, is not something to write out as XML.

<!-- block: gtc -->

The **GUM Tree Calculator**, from the Measurement Standards Laboratory of New Zealand, arrives at the same design independently: elementary uncertain numbers carry UUID-based identifiers, and an archive of them serialises to JSON or XML against a published schema.

Two implementations reaching the same conclusion is a better argument for the idea than one, and it is why the credential names a *format* rather than assuming a library. A certificate can carry either, or both, and a recipient uses whichever it can read.

<!-- block: gtc-either-way -->

Everything else in this chapter works either way. The credential simply carries one dependency representation instead of two.

<!-- block: no-dcc -->

This certificate carries no PTB/DKD DCC.

<!-- block: dcc -->

The **PTB/DKD DCC** is doing something different from the other three, and the difference is worth pausing on. Note the name, too: several things are called a PTB/DKD DCC, and this is the one the PTB and the DKD define.

Classical, UncLib and GTC all describe a *result* — how good a number is, and what it rests on. A PTB/DKD DCC describes a *document*: who calibrated what, for whom, when, under which conditions, with which equipment, and what came out. It is a calibration certificate in a schema, not an uncertainty in a format.

Inside it the quantity is written in **D-SI**, which is where the two levels meet. And D-SI's `si:expandedUnc` carries a value, an uncertainty, a coverage factor and a probability — that is the classical statement exactly, and it is not the dependency structure. So the two do not compete: a certificate wanting a standardised document *and* transmissible dependencies carries a PTB/DKD DCC and an UncLib block together, which is what this one does.

<!-- block: mapping.title -->

How this certificate maps onto the schema

<!-- block: mapping.hint -->

our field on the left, the element it becomes on the right

<!-- block: siunitx -->

One detail worth having been careful about: D-SI writes units the way siunitx does, as English names each preceded by a backslash. Ohm is `\ohm`. Kilogram is `\kilo\gram` and *not* `\kilogram`, because the prefix is a token of its own. The generator here refuses to emit a unit it has no mapping for, rather than guessing — a certificate that quietly states the wrong unit is worse than one that fails to be produced.

<!-- block: document.title -->

The document

<!-- block: duplication.title -->

What is now said twice

<!-- block: duplication.hint -->

the cost of putting one standardised document inside another

<!-- block: duplication -->

Wrapping a PTB/DKD DCC in a credential duplicates most of the certificate. That is not a flaw in either format — each was built to stand alone — but putting one inside the other makes the overlap unavoidable, and **duplication permits disagreement**. The signature stops anyone editing either copy after issue. It does nothing at all about an issuer writing them inconsistent in the first place.

<!-- block: no-duplicates -->

No duplicated facts were compared.

<!-- block: signature.title -->

Including the signature

<!-- block: sign-once -->

A document carrying both can verify under one mechanism and fail under the other, and there is no natural rule for which wins. So this demonstration **signs once**: the credential proof covers the credential, the credential carries a digest of the PTB/DKD DCC bytes, and the `ds:Signature` slot stays empty. One trust path. That is a choice rather than an obligation.

There are three honest ways to live with the rest of the redundancy, and only the first is built here. **Duplicate and check**, so every repeated fact becomes somewhere a mistake gets caught. **Do not duplicate**, by making the PTB/DKD DCC the credential subject and letting `issuer` and `validFrom` be views of it — cleanest, and probably what a real deployment settles on. Or **declare precedence**, saying which copy governs, which works and needs governance and is never read at the moment it is needed.
