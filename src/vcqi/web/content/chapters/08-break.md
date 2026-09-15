<!-- 08-break.md -- chapter 7 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterBreakIt() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The twenty-three cases themselves -- their titles, what each one does and the check it
     is meant to trip -- are in src/vcqi/actors/tamper.py. They are records rather than
     prose, and the verifier reads the same records, so moving them here would split one
     fact across two files. Only the three group headings and their notes are here.

     The chapter after this one is the same argument with the reader's hand on the
     document. What earns this one its own chapter, and its place first, is that most of
     these cases change the world around the certificate rather than the certificate, which
     editing one document cannot do. -->

<!-- block: title -->

Break it

<!-- block: eyebrow -->

Failure modes

<!-- block: lede -->

Twenty-three ways this can go wrong, and the check that catches each. The interesting ones pass every cryptographic test.

<!-- block: why-break-it -->

A demonstration where everything always passes teaches very little. Each case below is a specific thing that can go wrong, and each names in advance the single check that is supposed to notice it.

Several of them go further than any edit to one document could: an accreditation suspended after the certificate was issued, a schema loosened after recognition was granted, a parent certificate reissued after it had been referenced. None of those is a change to the certificate being presented, which is why they are applied for you here. The next chapter hands you a document and lets you find one yourself.

The third group is the one worth dwelling on. In every case there, the signature is valid, the issuer is genuinely recognised, and the document is inside its validity period.

<!-- block: forgery.title -->

Forgery — the cryptography catches these

<!-- block: forgery.hint -->

Any Verifiable Credentials library would reject all of these. They are the easy half.

<!-- block: standing.title -->

Standing — the organisation was not entitled to issue it

<!-- block: standing.hint -->

Signatures say nothing about whether an accreditation has lapsed, been suspended, or never covered this activity. Recognition chains and status lists do.

<!-- block: metrological.title -->

Metrology — everything verifies and the claim is still wrong

<!-- block: metrological.hint -->

Every signature verifies, every organisation is in good standing, and the document is still wrong. A system that checked only the cryptography would accept every one of these.
