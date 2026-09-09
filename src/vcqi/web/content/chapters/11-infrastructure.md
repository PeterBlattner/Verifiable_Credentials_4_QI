<!-- 11-infrastructure.md -- chapter 10 in the rail; the NN- prefix is the position in
     the CHAPTERS array, which counts the cautions. Rendered by chapterInfrastructure()
     in ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The per-role text -- the posture, the custody note, what already runs, what must be
     added, availability and the hardest part -- is in src/vcqi/actors/deployment.py. It
     is nine correlated fields per role, which a markdown file expresses badly, and the
     figures beside it are computed from what the demonstration published.

     The document-kind labels and the custody grades stay in the code as well: they are
     labels chosen by a key the server sends, not sentences.

     "{part}" in the hardest block is filled in from the role on show. Leave the braces
     alone. -->

<!-- block: title -->

What it would take to run

<!-- block: eyebrow -->

Deployment

<!-- block: lede -->

The hosting requirement, computed rather than asserted, and why it is so unevenly spread between a trust anchor, a national institute, a fifteen-person laboratory and a verifier.

<!-- block: two-properties -->

Two properties of the design settle most of this question, and neither of them is about capacity.

**Verification is a computation, not a conversation.** A recipient needs no account with the issuer, no registration, and no channel back to it. So an issuer operates no service on a verifier’s behalf, and nothing here grows with the number of people who check. That is a claim about *checking* a credential, and it is true because a credential here travels as a signed file. Chapter 12 measures how far that goes, what a verifier still cannot be handed second-hand, and what it costs to *ask* for a document instead of being given one.

**A credential travels with whoever holds it.** The certificate arrives from the customer, not from the laboratory that wrote it. What an issuer must keep online is therefore only what describes the issuer itself — its key, and which of its credentials it has since withdrawn. The certificates need not be hosted at all.

Everything below is computed from what this demonstration actually published, so the figures move if the world does.

<!-- block: fetches.title -->

What a verifier actually goes and fetches

<!-- block: unevenly-spread -->

The burden is then very unevenly spread. Pick a role to see what it would have to stand up, and — usually the larger half — what it already runs today.

<!-- block: whose.title -->

Whose infrastructure?

<!-- block: pure-verifier -->

A pure verifier publishes nothing. The single document counted here is a DID document that exists only because every organisation in this demonstration was given one; nothing in the system needs it.

<!-- block: does-not-grow -->

Note that the first figure does not grow with the second. An institute issuing ten times as many certificates keeps exactly the same documents online.

<!-- block: reachable.title -->

Everything it must keep reachable

<!-- block: reachable.hint -->

click any of them — all of it is public, and this is precisely what a verifier retrieves

<!-- block: key.title -->

The signing key

<!-- block: already.title -->

Already runs today

<!-- block: already.hint -->

reused, not replaced

<!-- block: must-add.title -->

Would genuinely have to be added

<!-- block: availability.title -->

Availability and scale

<!-- block: hardest -->

**The part that would actually take the effort.** {part}

<!-- block: new.title -->

What is genuinely new, across all of them

<!-- block: new -->

**Key custody is the whole problem.** Every role above reduces to a question about who holds a key and what happens when it is lost. None of that is answered by buying hardware, and the hardware is where the attention usually goes.

**Long-term validation is the second problem, and it is the one with a deadline.** Signatures have to be timestamped at the moment of issue. A certificate signed today and archived without a timestamp cannot be given one in 2040, when the question of whether P-256 still means anything will be a live one. Almost everything else here can be retrofitted. This cannot.

**And there is a new way to fail.** A paper certificate keeps working when a web server does not. These do not: an unreachable DID document means an unverifiable certificate, and for a trust anchor that is a global outage. Static files behind a long cache lifetime make that a manageable risk rather than an unlikely one — but it is a dependency the present arrangement simply does not have, and it belongs on the other side of the ledger from the benefits in the previous chapter.

<!-- block: next-chapter -->

All of that is what a single organisation would have to run. It says nothing about what they would have to agree with each other, which is the harder half and the next chapter.
