# Architecture, and what it deliberately simplifies

This is a demonstrator built to make an argument concrete, not a library and not a
prototype of a deployment. Several things are simplified, and the value of the exercise
depends on being clear about which.

## Layers

```
crypto/   canonicalization, keys, signatures        no domain knowledge
vc/       credential shapes, checks, recognition,   no metrology knowledge
          verification pipeline
domain/   CMCs, accreditation scopes, uncertainty   no credential knowledge
actors/   the world, and the ways to break it
web/      one FastAPI process playing every part
```

The middle two layers are kept apart on purpose. `vc/` knows how to verify a credential
and follow a recognition chain, and nothing about ohms. `domain/` knows what a CMC
bounds and how uncertainty propagates, and nothing about signatures. Only `verify.py`
sees both, and that is where the interesting checks live.

## Decisions

### `ecdsa-jcs-2019`, not `ecdsa-rdfc-2019`

Data Integrity proofs use ECDSA over P-256 with **RFC 8785 JSON canonicalization**. The
cryptosuite the specification examples use, `ecdsa-rdfc-2019`, canonicalizes the RDF
graph instead, which requires a full JSON-LD processor and dereferencing every context.

JCS was chosen because the whole point of chapter 2 is to show a reader the exact bytes
that get hashed. RDF canonicalization is correct and is what a production system should
use; it is also impossible to display in a way that teaches anything. The proof objects
have the same shape either way, so the difference is one string in `cryptosuite`.

**Consequence:** the `@context` values are not dereferenced, so the term definitions are
decorative here. A real deployment needs them resolvable and needs `ecdsa-rdfc-2019` or
an equivalent, or the JSON-LD layer is providing no semantics at all.

### Deterministic signatures (RFC 6979)

`crypto/ecdsa_p256.py` implements ECDSA signing with a nonce derived from the key and
the message rather than from a random source, so identical input always produces an
identical signature. This is what lets the demonstration be diffed: any change in a
`proofValue` was caused by a change in the document.

It exists because `cryptography` exposes no deterministic mode. Verification is still
delegated to `cryptography`, so the implementation is cross-checked against an
independent one on every signature, and against the published RFC 6979 vectors in
`tests/test_ecdsa_p256.py`.

**It is not constant-time.** That is acceptable only because every key in this project
is derived from a published seed and protects nothing. It must never be used with a real
key.

### JCS and multibase implemented in-repo

`rfc8785` and `base58` exist on PyPI. They are implemented here anyway, in about 300
lines with RFC 8785 conformance tests, because the signing path is the thing being
explained and a reader should be able to follow it without leaving the repository.

### Certificate payloads, and the PTB/DKD DCC alongside them

`credentialSubject` is a readable custom shape rather than a PTB/DKD Digital Calibration
Certificate. Note the name: several things are called a DCC, and this project always
means the one the PTB and the DKD define, schema 3.3.0 in `https://ptb.de/dcc`, with
quantities in D-SI 2.2.1 in `https://ptb.de/si`.

Every calibration certificate now *carries* a PTB/DKD DCC alongside its readable subject,
in `domain/dcc.py`. It uses the real namespaces, element names and nesting, and includes
only the elements this world has data for. Deliberately not done: validating against the
published XSD, filling the `ds:Signature` slot, and making the DCC the credential subject
rather than a passenger.

The levels are the point. The classical statement, the UncLib serialisation and the GTC
archive all describe a **result**. A PTB/DKD DCC describes a **document**. And D-SI's
`si:expandedUnc` carries a value, an uncertainty, a coverage factor and a probability,
which is exactly the classical statement and is not the dependency structure — so the two
compose rather than compete, and a certificate wanting both carries both.

**Units.** D-SI writes units siunitx-style: English names each preceded by a backslash,
prefixes and powers as separate tokens. Ohm is `\ohm`; kilogram is `\kilo\gram`, not
`\kilogram`. `dsi_unit()` raises on any unit it has no mapping for rather than guessing,
because a certificate quietly stating the wrong unit is worse than one that fails to be
produced.

### Redundancy, and signing once

Putting a standardised document inside a credential duplicates most of it: who
calibrated, for whom, when, under which number, the item, the result — and the integrity
mechanism. Duplication permits disagreement, and the signature does nothing about it: it
stops anyone editing a copy after issue and is perfectly content for the copies to have
been written inconsistent.

The two integrity mechanisms differ at every layer that matters. A credential proof
canonicalizes with RFC 8785, finds its key by resolving an identifier, and is revoked
through a status list. A `ds:Signature` canonicalizes with XML C14N, finds its key
through an X.509 chain, and is revoked through a CRL or OCSP. A document carrying both
can verify under one and fail under the other, with no natural rule for which wins.

So this demonstration **signs once**. The credential proof covers the credential, the
credential carries a digest of the DCC bytes, and the `ds:Signature` slot stays empty.
That is a choice, not an obligation.

For the rest of the redundancy there are three honest options, and only the first is
built: **duplicate and check**, which is why `uncertainty.duplication` compares the six
facts stated twice and turns the redundancy into somewhere mistakes get caught;
**do not duplicate**, by making the DCC the credential subject and deriving `issuer` and
`validFrom` from it, which is cleanest and probably right for a real deployment; or
**declare precedence**, which works, needs governance, and is never read when needed.

**Two names outgrew their contents** when the DCC arrived, and it is better to record
that than to leave it as a puzzle. The credential member is still
`uncertaintyRepresentations` although it now also holds a whole certificate, and the
pipeline step is still `uncertainty` although its children compare administrative facts.
Renaming the member would change every signed credential and both generated schemas;
renaming the step would break ids that the tests and the interface refer to. The names
stayed and the `type` values carry the meaning.

### The network is a dictionary

`vc/resolver.py` stands in for retrieval. Every document is published at the address a
credential references it by, and every fetch is logged, so the retrieval counts the
interface shows are real. What is missing is everything that makes real retrieval hard:
latency, caching, availability, and an attacker who controls the network. `did:web`
resolution in particular is reduced to a lookup; a real one involves TLS, and the
security of the whole chain then rests on the web PKI.

### `credentialSubject` as an array

`RecognizedEntityCredential` uses an array of subjects, matching the specification's own
examples of a list of recognised entities. The BIPM credential lists two institutes and
the accreditation body lists three organisations, so the array shape is exercised rather
than assumed.

## What the pipeline checks, and why each step exists

| Step | Exists because |
| --- | --- |
| `shape` | a document that is not a credential should fail as that, not as a bad signature |
| `proof` | signature, *and* that the key's controller is the issuer, *and* that the controller authorised that key for assertions |
| `validity` | evaluated against the moment of verification, not of issue |
| `status` | a signature says what was true at issue; only the status list says what is true now |
| `recognition` | the Recognized Entities contribution: getting from an unknown issuer to a trusted identifier |
| `action` | being recognised is not being recognised *for this*, at *this time*, under *this capability* |
| `output-validation` | the schema the recognition names, pinned by content digest |
| `scope` | the numeric decision a schema cannot express |
| `mra-logo` | whether a claim of international recognition is justified |
| `uncertainty` | whether the stated U is supported by the budget offered for it, whether every representation matches its recorded digest, and whether the printed line agrees with the dependency data |
| `traceability` | whether the chain of certificates below it holds, by content digest, and whether the influences of the parent are genuinely present in this result |

Every step returns a structured result rather than a boolean, and a step that cannot be
evaluated reports `skip` rather than passing quietly. `tests/test_pipeline.py` asserts
that each of the thirteen failure cases is caught by the step that claims it, and that the
metrological cases pass `proof`, `validity` and `recognition` first — which is the whole
reason they are worth demonstrating.

## Not implemented

- **Selective disclosure.** A calibration certificate names a customer and an
  instrument, and a dependency representation exposes a whole uncertainty budget. A
  laboratory should be able to prove its equipment is traceable and in scope without
  disclosing either. That needs SD-JWT VC or BBS signatures, neither of which is here,
  and it is the most obvious thing missing.
- **Long-term validation.** Calibration certificates are kept for decades; signatures
  and keys are not built for that. Timestamping and an archival strategy would have to
  be designed in from the start.
- **Key management and rotation.** Each actor has exactly one key, forever.
- **Real DID methods.** `did:web` only, resolved locally.
- **Holder wallets and presentation protocols.** Credentials are handed around as JSON.
  OpenID4VP and a wallet are what a real flow would use.
- **Any authority whatsoever.** No part of this reflects the position of any real
  institute, accreditation body, RMO, Global ACI, or the BIPM.

## The keys chapter signs with keys the caller supplies

`/api/keys/*` takes the private key as a request parameter rather than holding it server
side, and hands it back to the browser in plain sight. That is deliberate teaching: a
private key really is just a number somebody possesses, and watching it travel makes the
custody problem concrete in a way prose does not.

It is also the last thing a real system would do, and why it is harmless here is worth
stating rather than assuming. The server binds to localhost. Every key in the
demonstration comes from a seed published in this repository. And `/api/keys/sign` signs
caller-supplied bytes with a caller-supplied key, so it is an oracle for nothing but the
caller's own key. None of that would survive exposure to a network.

`did:key` support in `vc/resolver.py` exists for the same chapter. A `did:key` carries
its own public key, so resolving it fetches nothing — which makes the contrast with
`did:web` visible: one identifier *is* a key, the other is a name that has to be resolved
to find one. The organisations here use `did:web` because a `did:key` cannot rotate its
key and cannot be the subject of a recognition credential; you would be recognising a key
rather than an organisation.

## Testing what the interface does, not only what it renders

`tests/` covers everything the server computes, and it structurally cannot cover whether
a button works. That gap has produced the same bug twice.

The document inspector was appended to the page only for a hardcoded list of chapter ids,
so a chapter not on that list could fetch a document, render it, and put the result into
a node that had never been in the page. Every request succeeded and every test passed
while the controls did nothing. It was found once, fixed on a branch that was later
archived rather than merged, and arrived back on the main line the moment a new chapter
was added.

Two things came out of it. The inspector now attaches itself the first time a chapter
asks for a document, so there is no list to fall off. And `tools/ui-clicks.mjs` drives
the real application in a jsdom document, navigating to each chapter and clicking every
control, failing if the page does not change. It skips controls that are already the
selected option, because re-choosing the tab you are on is meant to do nothing and a
check that cries wolf gets ignored.

It needs jsdom, which is not a project dependency and should not become one: nothing that
ships needs npm.

## Reproducibility

`build_world()` is deterministic: fixed seed, fixed timestamps, deterministic
signatures, and a status list compressed with a pinned modification time. Two builds
produce byte-identical documents, which `tests/test_pipeline.py` asserts and
`--dump` makes diffable.

[dcc]: https://www.ptb.de/dcc/
