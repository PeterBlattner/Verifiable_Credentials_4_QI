<!-- 10-implications.md -- chapter 9 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterImplications() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     This chapter is all prose and no interaction, so nearly every word a reader sees is
     in this file. The three panels take no subheading, which is why there is a
     ".title" for each but no ".hint". -->

<!-- block: title -->

What this would mean in practice

<!-- block: eyebrow -->

The argument

<!-- block: lede -->

What genuinely changes, what a real deployment would need, and what remains an open question.

<!-- block: prototype -->

The demonstration is a prototype and proves nothing about deployability. But it does make some things concrete enough to argue about, which is what it was for.

<!-- block: different.title -->

What actually becomes different

<!-- block: different -->

**The recipient checks, not the issuer.** Today a laboratory receiving a certificate that carries the CIPM MRA logo either takes the logo on trust or opens the KCDB and compares by eye. Here the comparison is made by whoever received the document, at the moment they received it, from the signed registry entry.

**Scope becomes enforceable rather than declaratory.** An accreditation scope and a CMC both already state exactly what is covered. Making them machine-readable turns them from something published into something checked.

**Suspension takes effect immediately, everywhere.** When an accreditation is suspended, every certificate already issued under it becomes unverifiable at the next check, without any of them being recalled or reissued.

**Traceability stops being an assertion.** A test report that says its equipment was calibrated can be made to prove it, by content digest, all the way down to a national standard.

**Border clearance without correspondence.** This is the case the Recognized Entities specification puts in section 2.4, and it works here: an authority holding two trusted identifiers reaches a verdict on a document from an organisation it has never dealt with.

<!-- block: needed.title -->

What a real deployment would need, and does not have yet

<!-- block: needed -->

**Governance of the identifiers.** Someone has to decide what the BIPM’s identifier is, who controls it, how it is rotated, and what happens when a key is compromised. This is a governance problem wearing a technical costume, and it is the hard part.

**The KCDB as a signed registry.** The CMC data already exists and is already peer reviewed. What is missing is publication in a form that carries a signature and a stable content digest.

**Long-term validation.** Calibration certificates are kept for decades and signatures do not age well. Anything real needs timestamping and an archival strategy from the start, not added later.

**Alignment with the PTB/DKD DCC.** Every calibration certificate here now carries one, in the real namespaces with the quantity in D-SI, so the same calibration appears both as a readable subject and as a standardised document. One certificate does it the other way round and carries nothing but a reference to a document published separately — the DKD's own example, at a schema version this repository does not generate, with a real `ds:Signature` over it. What is still missing is the part that matters most for a deployment: the generated document is a subset rather than a conformant one, neither document is validated against the published XSD, and the credential subject is still either the readable shape or a pointer, never the PTB/DKD DCC itself. D-SI also does not model dependency structure, so an UncLib or GTC block still has to ride alongside it.

**And what pointing at a document rather than carrying it costs.** It is exact, and it is measured rather than argued: the scope check falls back to the measurand and the unit, the uncertainty and traceability checks do not run at all, and the four facts the credential states about the document go unconfirmed because nothing parses it. The credential still verifies. A deployment choosing this model is choosing a verifier that checks provenance and integrity and leaves metrology to a human — which may well be the right trade, as long as it is made knowingly.

**And what the redundancy taught, which generalises.** Wrapping an existing standardised document inside a credential duplicates most of it, including its integrity mechanism. Who calibrated, for whom, when, under which number — all said twice, in two vocabularies, with nothing keeping them together. A real deployment has to choose deliberately between duplicating and checking, not duplicating at all, or declaring which copy governs. This demonstration duplicates and checks, because that is the cheapest thing to show and it turns every repeated fact into somewhere a mistake gets caught. The version worth building is probably the second: make the document the subject, and derive the rest from it.

**Selective disclosure.** A calibration certificate names a customer and an instrument. A testing laboratory may need to prove its equipment is traceable and in scope without disclosing the certificate. That is what SD-JWT or BBS signatures are for, and none of it is implemented here.

**Relationship to eIDAS 2.0 and the EU Digital Identity Wallet.** Organisational credentials are arriving in European regulation on their own schedule. Whatever the quality infrastructure does should meet that rather than run beside it.

<!-- block: questions.title -->

Honest open questions

<!-- block: questions -->

Is a decentralised recognition chain actually better than each MRA simply publishing one signed list? For a hierarchy this shallow, possibly not, and the answer should be argued rather than assumed.

Who verifies, in practice? The value depends entirely on the checking happening somewhere it does not happen today. If nobody runs the verifier, nothing has been gained.

What does a failed check mean institutionally? The pipeline can say a certificate is outside a published CMC. It cannot say whether that is an error, a typo, or a capability that was updated last week and not yet published.

How do these credentials relate to the certificates that remain legally authoritative? For a long time both will exist, and which one governs is a legal question, not a technical one.
