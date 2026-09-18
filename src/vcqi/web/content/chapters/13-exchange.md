<!-- 13-exchange.md -- chapter 12 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterMoving() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The three exchanges, the portability classes and the lesson under each are in
     src/vcqi/actors/exchange.py and src/vcqi/actors/portability.py. The status lists
     the third section counts are measured by revocation_audit() in the same
     portability module.

     The comparison table near the end stays in the code. It is assembled as a table
     element and dropping it in from here would wrap it in a div, which changes the
     markup for no gain in editability. It has three columns, one per model, and a new
     row has to say something in all three.

     Several blocks carry placeholders in braces -- counts and outcomes measured from
     the world rather than written down. Leave the braces alone.

     Blocks from step1.title down to checked.hint appear only after a reader presses
     "Run the exchange", so the snapshot harness never renders them. The test suite
     still checks that every one of them exists. -->

<!-- block: title -->

How a credential moves

<!-- block: eyebrow -->

Distribution

<!-- block: lede -->

Three architectures answer the same question and disagree about almost everything: let the document travel, let the issuer publish a list, or make the parties talk. All three are built here, and the cost of each is measured rather than argued.

<!-- block: two-ways -->

Every verifier you have met so far already had the document in hand. That is a comfortable place to start a chapter and nobody arrives there by accident: somebody asked, somebody answered, and both steps happened before the page opened.

There are three ways to answer the question, and they disagree about almost everything. The first says the document should travel — signed, self-contained, by whatever means is to hand — and that no protocol is needed for most of it. The last says the parties should talk, over an agreed protocol, so that each can ask for exactly what it needs. In between sits the arrangement most real deployments actually run: the document travels, and the issuer publishes a list saying what it has since taken back. This world can do all three, and the rest of the chapter is what each one costs.

<!-- block: one.title -->

One: the credential is a file

<!-- block: one -->

UN/CEFACT put the argument for this most sharply, and it is an argument from failure rather than from elegance. Fifty years of electronic data interchange digitised something like a tenth of cross-border trade, because a network of hubs and pipes only ever reaches the parties who joined it, and a commercial invoice is needed by the exporter, the importer, two customs authorities, banks, insurers, brokers and freight forwarders. The network never reaches all of them. So [stop building the network](https://unvtd.unece.org/architecture/portable-credentials/): sign the document, and let it travel with the consignment by email, file transfer, a USB drive or a QR code.

**This demonstration was already built that way and had not noticed.** Every credential here is a signed file that verifies wherever it is found; the world dumps to 78 documents on disk and they verify from there. Chapter 10 computes the same property from the other end — the institute keeps three documents online while eight of its credentials travel unhosted — and calls it a hosting burden rather than an architecture.

Metrology has the oldest instance of the idea in existence, and it is not digital. **A calibration certificate already travels with the instrument.** The paper in the box is a portable credential: self-contained, checkable by whoever opens the box, and dependent on no service being reachable. What the cryptography adds is not the idea. It is that the copy in the box can now be checked.

<!-- block: two.title -->

Two: what can travel, and what cannot

<!-- block: two -->

The interesting question is not whether the portable model works. It is where it stops, and that is measurable rather than arguable. Below, the same certificate of conformity is verified twice: once with the verifier given nothing, and once with the verifier handed every document a holder is allowed to bring. The difference is read out of the resolver’s own retrieval log.

<!-- block: twice.title -->

The same verification, twice

<!-- block: twice.body -->

Both runs reach **{outcome}**. Handing the verifier everything it is allowed to accept second-hand removes {travelling} of the {baseline} retrievals and changes no verdict, which is the portable-credential claim holding up under measurement rather than in principle.

What is left is the part that is not portable. And if the registries were signed — the one removable reason below — the residue would be {residue} documents of exactly two kinds: **{kinds}**. That is each organisation’s key and its revocation list, and nothing else. It is also, to the document, the hosting burden chapter 10 computed from the opposite direction. Neither chapter knew it was describing the same quantity.

Two kinds, and it is tempting to read that as one residue. It is not. A key must be **authentic**, and a copy of one from a year ago is still the key. A status list must be **fresh**, and a copy of one from a day ago is a day of undetected revocation. Only the second has a clock in it, and the next section is about what that clock costs.

<!-- block: the-forgery -->

The forgery in the second class is not hypothetical, and it is worth being plain that this demonstration had it. A holder could staple a DID document claiming a trust anchor’s identifier, sign a credential in that anchor’s name with its own key, and the pipeline reported *verified* — every check passing, because the verifier was reading the attacker’s own account of whose key was whose. `vc/resolver.py` now refuses to take any of these kinds second-hand, and the exploit is kept as a regression test.

<!-- block: three.title -->

Three: the document travels, and the issuer publishes a list

<!-- block: three -->

The portable argument has a hole in it that its own page does not mention. UN/CEFACT says a signed document can travel by email, file transfer, a USB drive or a QR code, and never once says what happens when it has to be withdrawn. UNTP, built on exactly that architecture, does say: a conformant implementation *MUST implement W3C VC Bitstring Status List for credential status management including revocation*, and every UNTP object is described as tamper-evident, issuer-identifiable and **revocable**. Two UN pages, one architecture, and only the second of them has a way to take something back.

So there is a third arrangement between the two, and it is the one nearly every real deployment runs. The document still travels. Nobody talks to anybody — no protocol, no state, no challenge, nothing for the holder to consent to and no channel back to the issuer. But one document cannot be carried, because it is a claim about the present tense, and the verifier has to go and get it.

Chapter 10’s rule survives this intact, and it is worth saying why rather than leaving it looking contradicted. **A status list is a file, not a question.** The issuer serves the same bytes to everyone who asks, is asked nothing, and answers nobody in particular. Verification is still a computation. A conversation is the section after this one.

<!-- block: lists.title -->

What this world’s revocation state weighs

<!-- block: lists.hint -->

every list, decompressed and counted rather than described

<!-- block: lists.body -->

{lists} lists, one per issuer, reserving {positions} positions between them and carrying {covered} credentials — which is every credential in this world. Nothing here was issued that could not afterwards be withdrawn.

All of it comes to {bytes} bytes of signed document. That is less than the single calibration certificate the laboratory issued, and it is the whole of what this architecture asks a verifier to fetch that it could not have been handed. Revocation is not expensive. It is simply not something a holder can give you.

<!-- block: herd -->

Reading one bit is not the same as asking about one credential, and the difference is the reason the lists are the size they are. The specification sets a floor of 131,072 positions and every list here sits on it, with between one and four of those positions in use. A verifier downloads the whole list and reads its bit locally, so what the issuer’s server sees is a request for a list — not a question about a certificate, a holder or a customer. The floor does a second job at the same time: a list scaled to the number of credentials an issuer had actually issued would publish that number to anyone who looked.

<!-- block: same-bytes.title -->

The same file, withdrawn

<!-- block: same-bytes.hint -->

nothing about the document changes, and it stops verifying

<!-- block: same-bytes -->

Each button changes one bit on a list, and nothing else. The credential is not touched, and the two copies are compared byte for byte below rather than asserted to be the same. Its signature is still valid and its contents are still what the laboratory measured; it is simply no longer in force, and there is nothing in the holder’s hands that could say so.

The two are caught in different places, which is worth watching. The certificate’s own list is read by the top-level **status** step. A suspension one link further up — the accreditation behind the laboratory — is only reached while the chain is being walked, and it reaches every certificate that laboratory ever issued at once, without any of them being reissued.

<!-- block: resolver-note -->

Revocation is not the only thing sitting in this gap. UNTP also defines an **Identity Resolver**, ISO/IEC 18975: you hold an identifier rather than a document, and resolving it hands back links to whatever has been published about the thing identified. That is another arrangement with a service in it and no conversation, and the holder is not party to it at all. It is not implemented here — every address in this world resolves to a document directly — and what a resolver would add is a level of indirection between an identifier and the documents about it.

<!-- block: four.title -->

Four: when somebody has to ask

<!-- block: four -->

Portable credentials answer distribution and say nothing about the case where the verifier does not have the document and wants it — an authority at a border, an issuing authority that needs to see evidence before it certifies anything. For that the parties do have to talk, and what follows is W3C’s [VCALM](https://www.w3.org/TR/vcalm-1.0/) exchange, implemented against this same world. Two properties of it do all the work.

**One endpoint, used twice.** The holder POSTs to an exchange and is answered with a request for a presentation. It POSTs the presentation to the same URL and is answered with a result. Not two services with two protocols — one conversation with two turns.

**The holder starts it.** There is no way for an issuer or a verifier to reach into a wallet. Every flow begins with the party holding the credentials, which is why even this arrangement survives a fifteen-person laboratory sitting behind a firewall with no inbound port.

<!-- block: exchanges.title -->

Three exchanges this world can hold

<!-- block: exchanges.hint -->

pick one, then run it

<!-- block: asks-nothing -->

Only proof that the holder controls its identifier

<!-- block: issues-nothing -->

Nothing — this coordinator is checking, not issuing

<!-- block: step1.title -->

The holder opens an exchange

<!-- block: step2.title -->

The coordinator asks for a presentation

<!-- block: step2.hint -->

the same URL, answered with a request

<!-- block: step3.title -->

The holder answers

<!-- block: authentication -->

Look at the proof. Its `proofPurpose` is `authentication` rather than `assertionMethod` — the holder is not asserting the contents, which the issuers already signed, but proving it is the party that was asked. And it carries the `challenge` from the request and the `domain` of the coordinator, both signed in. That is what makes this presentation an answer to *this* exchange and no other, and it is why it could not have been prepared in advance: the challenge did not exist until step 1.

<!-- block: replay -->

Now a second exchange has been opened, with its own challenge, and the presentation from the first one is about to be posted into it — which is precisely what an attacker who intercepted a presentation would try.

<!-- block: step4.ok -->

verified, and issued where there is something to issue

<!-- block: step4.no -->

and nothing is issued

<!-- block: refused -->

**Refused.** {reason}

<!-- block: empty-body -->

Empty body — the exchange is finished and there is nothing further to send.

<!-- block: checked.title -->

What the coordinator checked before answering

<!-- block: checked.hint -->

the same pipeline every other chapter uses, run over what the holder sent

<!-- block: buys.title -->

What each one buys

<!-- block: buys.hint -->

and what it charges for it

<!-- block: buys.body -->

The fourth row is where the first two models both stop, and it is the honest limit of the portable one. A signed file proves who issued it and says nothing about who is holding it out, so **anyone with a copy can present it** — and a status list does not help, because it says whether a document is in force and never who is showing it to you. For a calibration certificate that is usually harmless — it is a public attestation about an instrument, and a copy is as true as the original. For a laboratory claiming its own accreditation in order to win work, a copy is enough to impersonate it. UNECE’s own business-wallet page does not discuss holder binding, a nonce or replay at all, and that gap is exactly what the challenge in the exchange above closes.

And the exchange charges for it. State means a service, a store, an expiry policy and something to attack: this is the only thing in the whole demonstration that the server has to remember between requests, and it holds at most {max} exchanges for {minutes} minutes each, evicting the oldest when it runs out of room.

<!-- block: claim.title -->

Chapter 10’s claim, stated properly

<!-- block: claim.hint -->

it was right, and for a reason it did not give

<!-- block: claim -->

Chapter 10 says a verifier operates nothing, and an earlier version of this chapter called that an overstatement. It is not one — it is a claim about the portable model, and under that model it is true. Checking a credential you already hold is free and works on a laptop at a border post with an intermittent connection — as long as the connection comes back before the status list in the cache goes stale, which is the one thing the middle model puts a clock on.

What is true alongside it is that *asking* for a credential is not free. So the cost is a property of the architecture chosen, not of credentials: choose the portable model and a verifier really does operate nothing, at the price of never being able to ask and never being told that anything was withdrawn; add the list and it is told, at the price of one retrieval it cannot pre-ship; choose the exchange and it can ask, at the price of running something. The measurement above is what that choice actually costs in this world, and the residue — a key and a revocation list per organisation — is what none of the three can avoid.
