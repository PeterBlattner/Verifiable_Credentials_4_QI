<!-- 05-verification.md -- chapter 4 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterVerification() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before. -->

<!-- block: title -->

Verification and recognition discovery

<!-- block: eyebrow -->

What a recipient checks

<!-- block: lede -->

A market surveillance authority that trusts two identifiers, meeting a certificate from an organisation it has never heard of.

<!-- block: the-scenario -->

This is the demonstration proper. A market surveillance authority in an importing country receives a certificate of conformity. It has no relationship with the certification body, the testing laboratory, the calibration laboratory or the institute. It trusts two identifiers in the world: the BIPM and Global ACI.

It runs eleven checks on this document. Four are generic, one walks the recognition chain, and six are about whether the metrology holds up — and a credential that only points at its certificate, rather than carrying one, picks up a twelfth. Expand any step to see what it decided.

<!-- block: stapled -->

The holder bundled the recognition credentials with the presentation, so the verifier read them from the presentation instead of going out for them. In a real deployment that is the difference between a border check that needs connectivity and one that does not.

<!-- block: unstapled -->

The verifier fetched everything itself. Toggle stapling above to see the same chain served from the presentation.

<!-- block: steps.title -->

What the verifier checked

<!-- block: steps.hint -->

Steps that passed are collapsed; open one to see inside

<!-- block: fetches.title -->

What the verifier had to fetch

<!-- block: fetches.hint -->

In the order it asked for them
