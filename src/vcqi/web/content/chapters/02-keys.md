<!-- 02-keys.md -- chapter 1 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterKeys() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     Three things stay in the code. Sentences built from a number the server has just
     computed -- how many decimal digits the private key has, and the note under a
     derived key -- because a plain-text slot cannot take a substitution. The
     signing-versus-encryption comparison table, because it is assembled as a table
     element rather than as words. And the button and field labels, which are labels.

     "{curve}" in the one-way block is filled in with the name of the curve. Leave the
     braces alone. -->

<!-- block: title -->

Keys: what a signature actually proves

<!-- block: eyebrow -->

The idea underneath

<!-- block: lede -->

A private key is a number, a public key is computed from it, and the computation goes one way only. Make a keypair, sign something, and watch what a signature does and does not settle.

<!-- block: what-a-key-is -->

The previous chapter said a credential is a document signed with a key that its issuer publishes. That sentence carries the whole idea, and it is worth slowing down on, because everything after it depends on what a key actually is.

A **private key** is a number. Not a file, not a password: a number, about 78 digits long. A **public key** is a second value computed from the first. The computation goes one way only, which is the entire trick and the reason the second one can be published.

<!-- block: keypair.title -->

Make a keypair

<!-- block: keypair.hint -->

nothing here is secret; see the warning below

<!-- block: same-key.title -->

Exactly the same key came back

<!-- block: same-key.body -->

Which is the whole problem with deriving a key from words. Nothing about this key is unpredictable: anyone who tries the same passphrase gets the same private key, and it is the private key that is supposed to be the secret. Change a character, or ask for a random one, and watch it move.

<!-- block: private-key.title -->

Your private key

<!-- block: public-key.title -->

The public key, computed from it

<!-- block: one-way -->

That multiplication is a few hundred point additions on the {curve} curve and takes well under a millisecond. Going the other way — recovering *d* from the point — is the elliptic curve discrete logarithm problem, and after forty years of trying, nobody knows how to do it. That asymmetry is the only reason the right-hand value can be published at all.

<!-- block: encoding.title -->

From a point to publicKeyMultibase

<!-- block: encoding.hint -->

four ordinary encodings stacked up, none of them cryptography

<!-- block: did-key -->

Notice what that identifier is. A `did:key` *contains* the public key, so a verifier needs to fetch nothing at all to check a signature made with it. Compare `did:web:metas.example`, which has to be resolved to a document before you learn anything. The trade is that a `did:key` can never rotate its key, cannot carry a name or a website, and cannot be the subject of a recognition credential — you would be recognising a key rather than an organisation.

<!-- block: randomness -->

Press **Derive** twice with the same words and you get the same key every time. Press **random** twice and you get two different keys. That contrast is the point: a real private key is chosen at random from about 2^256 possibilities, and one derived from words you can remember is one an attacker can guess.

And to be explicit about what you are looking at: this page shows you a private key and sends it back and forth over HTTP. Every key in this demonstration comes from a seed published in the source and protects nothing. A real private key is generated on the device that will use it and never leaves it.

<!-- block: halves.title -->

Which half does what

<!-- block: halves -->

This is where most of the confusion lives, and it comes from encryption. In encryption the *public* key encrypts and the *private* key decrypts, so people reasonably assume signing works the same way round. It does not.

<!-- block: not-secret -->

So a verifiable credential is **not secret**. A calibration certificate signed this way is as readable as one on paper. The signature does not hide anything; it says who wrote it and that nobody has changed it since. If you also need it kept confidential, that is a separate mechanism on top.

<!-- block: sign.title -->

Sign something, then break it four ways

<!-- block: sign.hint -->

a signature is never valid on its own, only for one message and one key

<!-- block: make-a-key-first -->

Make a keypair above first.

<!-- block: anyone.title -->

Anyone can sign. That is the point, and the problem.

<!-- block: anyone -->

Nothing stopped you making that key, and nothing stops you signing a calibration certificate with it right now. The mathematics does not know or care who you are. So try it: take the real METAS certificate from this demonstration, sign it with your own key, and put it through the same verification pipeline every other chapter uses.

Three ways to try, and all three fail — for three *different* reasons, which is what makes this worth doing rather than reading.

<!-- block: try.title -->

Sign a real calibration certificate with your key

<!-- block: checks.title -->

Every check the verifier ran

<!-- block: checks.hint -->

the same pipeline every other chapter uses

<!-- block: signed.title -->

The credential you just signed

<!-- block: second-attempt -->

The second attempt is the one to think about. Claiming to be METAS while naming your own key **passes** the recognition check, because recognition asks whether the issuer the credential *names* is recognised — and METAS genuinely is. Only the proof check binds that claim to a key, and only then does the forgery come apart.

Two checks, two different questions. A forgery would sail straight through either one on its own, which is why the pipeline runs both and why a valid signature, by itself, settles almost nothing.

<!-- block: how.title -->

How the verifier gets the right key

<!-- block: follow.title -->

Follow it from the proof back to the published key

<!-- block: controller -->

And crucially, the verifier takes the key from **the controller the credential names**, never from the credential itself. A document that carried its own public key would prove only that whoever wrote it owned a key — which is precisely the second attempt above.

The document also says what each key may be *used* for. A key listed under `authentication` is for proving you are present, logging in; one listed under `assertionMethod` is for making statements that outlive the conversation. The pipeline refuses a credential signed with a key its controller published only for authentication, and that is not pedantry: a key used to log in is exposed far more often than one kept for issuing.

<!-- block: leaks.title -->

And the day it leaks

<!-- block: leaks -->

If a private key gets out, everything it ever signed becomes questionable, because there is no longer any way to tell what the holder signed from what the thief signed. Anyone can issue in that name, backdated, indefinitely.

That is what revocation lists, key rotation and validity periods are really for, and why an identifier that can publish a *new* key without becoming a different party matters more than it first appears. It is also why `ARCHITECTURE.md` lists key management and long-term validation among the things a real deployment would have to solve that this demonstration does not.

<!-- block: footnote -->

Every key here is derived from a seed published in this repository, including the one you just made. They exist to be looked at, not to protect anything.
