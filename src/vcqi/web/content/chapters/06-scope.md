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

<!-- block: rows.title -->

What a published accreditation scope actually contains

<!-- block: rows.hint -->

Four rows, and the verifier has to choose one before it can decide anything

<!-- block: rows.body -->

### A scope is a table, not a row

A CMC entry really is one row: one quantity, one range, one floor. An accreditation scope is a table, and a real one runs to dozens of rows over several pages. The scope below is shaped like one — not in its numbers, which are invented, but in the things its rows do that a single range cannot hold.

Read down the coverage column. The first row does not state a range at all; it states a list of fixed values, because that is how an ohmmeter is calibrated and the uncertainty beside it is only claimed at those points. The second states an interval whose upper bound is strict, and a model that could only hold inclusive bounds would quietly grant the laboratory the one level its accreditation body wrote the `<` to exclude. The third and fourth are identical except for the frequency band, and they carry different capabilities — so the conditions are something to match on, not prose to print underneath.

Then read the first two columns together. Calibrating an ohmmeter and calibrating a resistance are different rows with different capabilities, because they are different activities on different kinds of object: a *measuring instrument* and a *material measure*, VIM 3.1 and VIM 3.6. A certificate has to say which it is about, or no row can be chosen for it.

The remarks column is the honest failure. The remarks that narrow a row have been folded into the row — fixed values became a list, frequency bands became conditions — but "on-site calibration is also covered, with appropriate measurement uncertainty" extends a scope by an amount nobody wrote down, and no model here is going to invent one. So the verifier reports that the row which decided the verdict carried words it did not read, and leaves the verdict standing: an extension cannot turn a pass into a failure. Chapter 4 shows that warning on the accredited certificate, every time.

<!-- block: carried-or-linked -->

### What a credential carries, and what it points at

This page is one instance of a question that runs through the whole design. The certificate states its measured value and its uncertainty budget in full, and states its accreditation as a link. When should a credential carry something, and when should it name a document that carries it?

The answer is not about size, and four things decide it.

**Who is entitled to say it.** A laboratory may state what it measured. It may not state what it is accredited for. So the measurement is carried and the accreditation is named — and named in a way that sends the verifier to the accreditation body rather than to the laboratory's word for it. That is a trust boundary, not a saving.

**Whether the fact is about *then* or about *now*.** A signature freezes what it covers, and a measured value should be frozen: it was true on the day, and a result the issuer can change after signing is not a result. An accreditation should not be. It is suspended, reduced and renewed between certificates, and only the body that granted it can say whether it still stands — which is why the scope here travels signed and pinned while its status is still fetched from the body every time.

**What the verifier loses.** Every link is a check that might not complete. Chapter 6 has the measured version of this: a certificate that points at its measurement instead of carrying it still comes out verified, and four of the checks on this page quietly stop happening. A verdict means whatever the checks behind it were able to reach.

**Whether it grows.** A dependency representation with thousands of input quantities cannot travel inside a credential, and a scope with forty-five rows should not be copied into every certificate issued under it. Past a threshold the content goes out by digest — integrity survives the move, availability does not.

And one rule that trims whatever the four leave: add no link a check does not read. Every document a verification fetches is a way for it to stop working in thirty years without anyone having tampered with anything, and chapter 12 counts them.

<!-- block: signed-registry -->

### A link that can still be checked

There is a fifth thing, and it is the one this demonstration changed its mind about. Being a link does not have to mean being unverifiable.

The CMC entry above is served unsigned, so a copy of it proves nothing and the verifier must go to the BIPM itself — which is why a holder may not carry it, and why one entry on chapter 12's list of what cannot travel is there for a reason that could be engineered away rather than a reason that is inherent. The accreditation scope used to sit beside it. It does not any more: the accreditation body signs its scopes, and every credential that cites one pins it by content digest. The link is still a link, and the laboratory still cannot state its own scope. But a verifier handed a copy can now check that it is the right scope, signed by the right body, still in force — without reaching the register at all.

Try *Serve a different accreditation scope at the same address* in chapter 8. The document that comes back is signed by the accreditation body, in force and not suspended, and it is refused anyway, because it is not the scope the certificate was issued under. An unsigned register entry could never have been refused for that reason: a verifier could only ask what the register says today.

<!-- block: schema-vs-registry -->

The schema attached to the recognition can express the measurand, the unit and a span, because those are constants. It cannot express the uncertainty floor, which varies with the measured level — and it cannot express the table at all. Fixed values, strict bounds and frequency bands all collapse into the widest level any row touches and the smallest uncertainty any row permits, because that is the only constant true of every row. Every one of those collapses loses in the permissive direction, which is the safe one: the schema admits claims the register will refuse, and never the other way round.

So the schema catches gross errors offline and the signed scope decides the rest — and the richer the scope, the more of the decision belongs to the scope alone. Both checks appear in the pipeline, and watching the schema pass while the row check fails is the clearest way to see why one does not replace the other.
