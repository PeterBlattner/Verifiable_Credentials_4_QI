<!-- 04-issuing.md -- chapter 3 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterIssuing() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The chapter opens with two rows of chips: the credential types, and then the
     documents of the type picked. The labels on the type chips are not here -- each is
     the title of that type's data model, in src/vcqi/vc/datamodel.py -- and the labels
     on the document chips are in chapters.js.

     The four panels are numbered "1." to "4." by the code, not here: markdown reads a
     line beginning "1. " as a list item and would swallow the number. The words after
     it are yours.

     The "doc." blocks are the note shown under the document chips, one for every
     document. Adding a document to the demonstration means adding a block here *and* a
     line in chapters.js; the tests fail if the two ever disagree. They are grouped by
     type, in the order the type chips are, and a note is only ever read beside the
     other documents of its own type. -->

<!-- block: title -->

Issuing a certificate

<!-- block: eyebrow -->

How signing works

<!-- block: lede -->

Pick a type of credential and see its data model, then one of its documents: from the claims its issuer wants to make, through canonicalization and hashing, to the signature itself. Every intermediate value shown.

<!-- block: types.title -->

Type of credential

<!-- block: schema.title -->

The data model of this type

<!-- block: schema.hint -->

A JSON Schema, draft 2020-12, which every credential of this type names in its credentialSchema

<!-- block: schema.unavailable -->

The data model could not be fetched, so it is not shown here. The documents below do not depend on it.

<!-- block: examples.title -->

Documents of this type in this world

<!-- block: data-model -->

Every credential here names its data model, in the member the data model reserves for it, `credentialSchema`. The reference carries two digests of the schema, so the model a credential was issued against cannot be loosened afterwards without the credential noticing. Chapter 4 checks it inside the first step, *Document is a Verifiable Credential*, because it is that question asked properly: not whether this is a credential at all, but whether it is a well-formed one of the type it says it is.

This is not the schema a recognition names in `outputValidation`, which chapter 4 checks as well. That one says what a particular issuer **may** issue — this measurand, this range — and differs from one issuer to the next. The data model says what a document of the type **is**, the same for everybody. It is open by design: it says what each member it lists must be, and forbids nothing it does not list, because a credential is meant to be extended.

<!-- block: canonicalization -->

A signature is made over bytes, and a JSON document does not have a single set of bytes: the same certificate can be written with different spacing, different member order, or different ways of writing the same number. So before anything is hashed, the document is put into a **canonical form**, and that is what gets signed. This is why a certificate can be reformatted on its way to a verifier without breaking.

Two things are hashed separately and signed together: the document without its proof, and the proof configuration without its signature. Hashing the configuration too is what stops anyone editing the stated purpose, the key or the time after the fact.

<!-- block: doc.bipm-recognition -->

Not a certificate. The BIPM naming the national metrology institutes that take part in the CIPM MRA, each one scoped to the calibration and measurement capabilities it has published in the key comparison database. This is the root everything on the metrology side hangs from.

<!-- block: doc.global-aci-recognition -->

The other root. The Global ACI naming the accreditation bodies that have signed its arrangement, with one entry per main scope — an activity paired with the document it is assessed against — because that is the unit signatory status is actually granted and withdrawn in.

<!-- block: doc.sas-recognition -->

One accreditation body naming the laboratories and certification bodies it has accredited, each scoped to its published accreditation. It is the last recognition on this side of the chain: every other type here is about somebody in particular.

<!-- block: doc.oiml-ia-recognition -->

A third arrangement, and it knows nothing of the other two. OIML naming the Issuing Authorities recognised to certify against a Recommendation — here R 46, and only R 46.

<!-- block: doc.oiml-tl-recognition -->

OIML naming the laboratories recognised to evaluate against R 46. The laboratory named here is the same one SAS accredited under STS 0456: one laboratory, one identifier, two arrangements above it, neither aware of the other.

<!-- block: doc.scope-scs-0123 -->

The signed scope behind SCS 0123: what Alpine Calibration may issue accredited calibration certificates for, row by row, with the conditions each row holds under. Chapter 5 is where a certificate is held against it.

<!-- block: doc.scope-sts-0456 -->

The testing scope, STS 0456, behind the test report — electrical safety of household appliances. Its method table is deliberately not published in the document: the body answers questions about it instead, which chapter 5 makes something of.

<!-- block: doc.scope-scesp-0789 -->

The certification scope, SCESp 0789, behind the certificate of conformity. ISO/IEC 17065 rather than 17025, because certifying a product is not the same activity as measuring one.

<!-- block: doc.metas-calibration -->

The reference calibration of this world. METAS calibrates Alpine Calibration's 10 kΩ transfer standard and carries the whole uncertainty budget inside the credential. It claims the CIPM MRA logo rather than an accreditation, and everything else here that measures resistance traces back to it.

<!-- block: doc.callab-calibration -->

The mirror image of METAS-2026-0417: the accredited laboratory's own certificate, resting on it by content digest. Accredited under SCS 0123, and no MRA logo.

<!-- block: doc.metas-check-a -->

Check standard A. METAS calibrating a 10 kΩ resistor, serial `SR10K-0091`, directly against the national standard with no transfer standard in between. One half of a pair — the note on B says what the pair is for.

<!-- block: doc.metas-check-b -->

Check standard B, serial `SR10K-0092`. Same institute, same national standard, same day, same budget; only the resistor and the ratio measured against it differ. That is the whole reason the pair exists. The national standard's contribution is one uncertainty being counted twice, so it cancels when a customer takes the difference of the two results — and whether the customer can see that from what was sent is the subject of chapter 6. Put the canonical forms of A and B side by side and very little separates them.

<!-- block: doc.metas-external-dcc -->

The only document of its type, and the odd one out: a calibration certificate with no measurement in it at all, only a pointer to one. Its data model has a place for an address and a digest and none for a result. The last paragraph of this chapter is about it.

<!-- block: doc.testlab-report -->

A test report rather than a calibration. A kettle against IEC 60335-1, two clauses, each with a value, an Expanded Uncertainty and a verdict. It names the multimeter it measured with, and that multimeter's calibration certificate by digest, which is how a test reaches a national standard.

<!-- block: doc.cab-conformity -->

A certificate of conformity: this product meets IEC 60335-1. It contains no measurement and no uncertainty of its own, resting entirely on test report HTS-2026-3391.

<!-- block: doc.oiml-evaluation -->

A type evaluation of an electricity meter design against R 46, three clauses with verdicts. This is the document that reaches two roots at once — up to OIML by recognition, and down to the BIPM by evidence, through the calibration certificate of the multimeter it measured with.

<!-- block: doc.oiml-certificate -->

The type approval certificate itself, issued by the Issuing Authority on the strength of evaluation report HTS-TE-2024-0114. The one document here with two roots of trust above it and nothing in common between them but the laboratory in the middle.

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

Not every type above is a certificate, and one of them is unlike everything else here. Certificate METAS-2026-0420, the one document under *Certificate by reference*, carries no measurement at all — no value, no Expanded Uncertainty, no budget. Its claims are a URL, two digests of a PTB/DKD DCC published elsewhere, and four facts of index about it. Put its data model beside the calibration certificate's: where one describes results with a value, an Expanded Uncertainty and a budget, the other describes an address and a digest. Then pick it and watch the canonical form: there is very little of it, because there is very little being said. Everything the certificate actually reports is in a document this credential vouches for and does not contain. Chapter 6 is where that trade is worked through.
