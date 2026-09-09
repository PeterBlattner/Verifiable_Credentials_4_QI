<!-- 06-scope.md -- chapter 5 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterScope() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The slider labels and the rows of the verdict table stay in the code: the labels
     are labels, and each row is a check the server ran, with its own title and detail.
     The published floor is quoted from the registry entry. -->

<!-- block: title -->

The CMC decides the logo

<!-- block: eyebrow -->

Scope enforcement

<!-- block: lede -->

Whether a calibration may carry the CIPM MRA logo, adjudicated from the published capability rather than taken on trust.

<!-- block: the-floor -->

A national metrology institute may put the CIPM MRA logo on a calibration certificate only when the calibration falls inside a capability it has published in the key comparison database. The published entry gives a measurand, a range, the conditions, and the **smallest** Expanded Uncertainty the institute can achieve.

That last one is the part that catches people out. The capability is a floor, not a ceiling. A certificate claiming a *larger* uncertainty is comfortably inside scope. A certificate claiming a *smaller* one is claiming to have done better than the institute has ever demonstrated, and is outside it.

Move the sliders. The verdict, and with it the legitimacy of the logo, is decided from the published entry rather than from anybody’s judgement.

The same machinery bounds the legal-metrology branch, and there the bound is a better one. An OIML Issuing Authority may certify a type only against a Recommendation it has been approved for, and a Recommendation is a numbered, edition-controlled document published by somebody else — not a declaration the organisation wrote about itself. Try *Certify a type against a Recommendation nobody approved* in chapter 8: the certificate is signed by a genuinely recognised body and rejected anyway, twice over, because the recognition names both the Recommendation and a schema built from it.

What is still missing is that the schema is this project’s reading of R 46 rather than R 46 speaking for itself. The OIML is working towards machine-readable Recommendations; until then, the bound is only as good as whoever transcribed it. That is the last item in chapter 11.

<!-- block: inside.title -->

Inside CMC CH-EM-0042 — the CIPM MRA logo is justified

<!-- block: inside.body -->

The calibration is covered by a published, peer-reviewed capability, so its international recognition follows.

<!-- block: outside.title -->

Outside CMC CH-EM-0042 — the CIPM MRA logo may not be used

<!-- block: outside.body -->

The calibration may still be perfectly sound. What is not supported is the claim of international recognition that the logo makes.

<!-- block: adjust.title -->

Adjust the claim

<!-- block: adjust.hint -->

Both axes are logarithmic

<!-- block: entry.title -->

The published entry

<!-- block: entry.hint -->

Served from the registry, exactly as the verifier fetched it

<!-- block: schema-vs-registry -->

The schema attached to the recognition can express the measurand, the unit and the range, because those are constants. It cannot express this uncertainty floor, which varies with the measured level. So the schema catches gross errors offline and the signed registry entry decides the rest. Both checks appear in the pipeline, and watching the schema pass while the registry check fails is the clearest way to see why one does not replace the other.
