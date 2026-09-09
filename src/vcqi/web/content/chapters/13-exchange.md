<!-- 13-exchange.md -- chapter 12 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterMoving() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The three exchanges, the portability classes and the lesson under each are in
     src/vcqi/actors/exchange.py and src/vcqi/actors/portability.py.

     The comparison table near the end stays in the code. It is assembled as a table
     element and dropping it in from here would wrap it in a div, which changes the
     markup for no gain in editability.

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

Two architectures answer the same question and disagree about almost everything: let the document travel, or make the parties talk. Both are built here, and the cost of each is measured rather than argued.

<!-- block: two-ways -->

Every verifier you have met so far already had the document in hand. That is a comfortable place to start a chapter and nobody arrives there by accident: somebody asked, somebody answered, and both steps happened before the page opened.

There are two ways to answer the question, and they disagree about almost everything. One says the document should travel — signed, self-contained, by whatever means is to hand — and that no protocol is needed for most of it. The other says the parties should talk, over an agreed protocol, so that each can ask for exactly what it needs. This world can do both, and the rest of the chapter is what each one costs.

<!-- block: one.title -->

One: the credential is a file

<!-- block: one -->

UN/CEFACT put the argument for this most sharply, and it is an argument from failure rather than from elegance. Fifty years of electronic data interchange digitised something like a tenth of cross-border trade, because a network of hubs and pipes only ever reaches the parties who joined it, and a commercial invoice is needed by the exporter, the importer, two customs authorities, banks, insurers, brokers and freight forwarders. The network never reaches all of them. So [stop building the network](https://unvtd.unece.org/architecture/portable-credentials/): sign the document, and let it travel with the consignment by email, file transfer, a USB drive or a QR code.

**This demonstration was already built that way and had not noticed.** Every credential here is a signed file that verifies wherever it is found; the world dumps to 76 documents on disk and they verify from there. Chapter 10 computes the same property from the other end — the institute keeps three documents online while six of its credentials travel unhosted — and calls it a hosting burden rather than an architecture.

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

<!-- block: the-forgery -->

The forgery in the second class is not hypothetical, and it is worth being plain that this demonstration had it. A holder could staple a DID document claiming a trust anchor’s identifier, sign a credential in that anchor’s name with its own key, and the pipeline reported *verified* — every check passing, because the verifier was reading the attacker’s own account of whose key was whose. `vc/resolver.py` now refuses to take any of these kinds second-hand, and the exploit is kept as a regression test.

<!-- block: three.title -->

Three: when somebody has to ask

<!-- block: three -->

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

The fourth row is where the two models genuinely need each other, and it is the honest limit of the portable one. A signed file proves who issued it and says nothing about who is holding it out, so **anyone with a copy can present it**. For a calibration certificate that is usually harmless — it is a public attestation about an instrument, and a copy is as true as the original. For a laboratory claiming its own accreditation in order to win work, a copy is enough to impersonate it. UNECE’s own business-wallet page does not discuss holder binding, a nonce or replay at all, and that gap is exactly what the challenge in the exchange above closes.

And the exchange charges for it. State means a service, a store, an expiry policy and something to attack: this is the only thing in the whole demonstration that the server has to remember between requests, and it holds at most {max} exchanges for {minutes} minutes each, evicting the oldest when it runs out of room.

<!-- block: claim.title -->

Chapter 10’s claim, stated properly

<!-- block: claim.hint -->

it was right, and for a reason it did not give

<!-- block: claim -->

Chapter 10 says a verifier operates nothing, and an earlier version of this chapter called that an overstatement. It is not one — it is a claim about the portable model, and under that model it is true. Checking a credential you already hold is free and works on a laptop at a border post with an intermittent connection.

What is true alongside it is that *asking* for a credential is not free. So the cost is a property of the architecture chosen, not of credentials: choose the portable model and a verifier really does operate nothing, at the price of never being able to ask; choose the exchange and it can ask, at the price of running something. The measurement above is what that choice actually costs in this world, and the residue — a key and a revocation list per organisation — is what neither model can avoid.
