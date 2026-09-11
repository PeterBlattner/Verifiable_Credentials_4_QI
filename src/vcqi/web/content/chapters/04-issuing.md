<!-- 04-issuing.md -- chapter 3 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterIssuing() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The four panels are numbered "1." to "4." by the code, not here: markdown reads a
     line beginning "1. " as a list item and would swallow the number. The words after
     it are yours. -->

<!-- block: title -->

Issuing a certificate

<!-- block: eyebrow -->

How signing works

<!-- block: lede -->

From the claims an institute wants to make, through canonicalization and hashing, to the signature itself. Every intermediate value shown.

<!-- block: canonicalization -->

A signature is made over bytes, and a JSON document does not have a single set of bytes: the same certificate can be written with different spacing, different member order, or different ways of writing the same number. So before anything is hashed, the document is put into a **canonical form**, and that is what gets signed. This is why a certificate can be reformatted on its way to a verifier without breaking.

Two things are hashed separately and signed together: the document without its proof, and the proof configuration without its signature. Hashing the configuration too is what stops anyone editing the stated purpose, the key or the time after the fact.

<!-- block: claims.title -->

The claims, before anything cryptographic happens

<!-- block: claims.hint -->

The document as its issuer assembled it

<!-- block: canonical.title -->

The canonical form

<!-- block: canonical.hint -->

RFC 8785: members sorted, no whitespace, numbers written one way only

<!-- block: hashing.title -->

What is hashed and signed

<!-- block: hashing.hint -->

Two SHA-256 digests, concatenated, then signed with ECDSA over P-256

<!-- block: deterministic -->

Signing here is deterministic, per RFC 6979. Identical input always produces an identical signature, so any change in the signature is caused by a change in the document rather than by a fresh random number.

<!-- block: finished.title -->

The finished credential

<!-- block: finished.hint -->

The proof configuration, plus the signature it covers

<!-- block: what-is-signed -->

One of the documents above is not like the others. Certificate METAS-2026-0420 carries no measurement at all — no value, no Expanded Uncertainty, no budget. Its claims are a URL, two digests of a PTB/DKD DCC published elsewhere, and four facts of index about it. Pick it and watch the canonical form: there is very little of it, because there is very little being said. Everything the certificate actually reports is in a document this credential vouches for and does not contain. Chapter 6 is where that trade is worked through.
