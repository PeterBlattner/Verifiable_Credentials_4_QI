<!-- 07-traceability.md -- chapter 6 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterTraceability() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The budget panels are titled from the certificate they show, so their headings are
     built in the code rather than here. The slider labels and table headers stay there
     too: they are labels, not sentences. -->

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
