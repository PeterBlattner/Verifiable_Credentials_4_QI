# Architecture, and what it deliberately simplifies

This is a demonstrator built to make an argument concrete, not a library and not a
prototype of a deployment. Several things are simplified, and the value of the exercise
depends on being clear about which.

## Layers

```
crypto/   canonicalization, keys, signatures        no domain knowledge
vc/       credential shapes, checks, recognition,   no metrology knowledge
          verification pipeline
domain/   CMCs, accreditation scopes, uncertainty,  no credential knowledge
          legal limits and conformity decisions
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

### Simplified certificate payloads

`credentialSubject` is a readable custom shape, not the PTB/DKD
[Digital Calibration Certificate][dcc]. This was a deliberate choice for legibility on
screen: a DCC carries far more structure than a demonstration needs, and the JSON would
stop fitting in a panel.

The obvious next step is not to keep this shape but to carry a DCC as the credential
subject, so the credential layer contributes recognition, scope enforcement and
revocation to a payload the community has already standardised. Nothing in `vc/`
depends on the payload shape; `domain/` reads results through a handful of accessors in
`verify.py` (`_payload`, `_first_result`) which are the only places that would change.

### Transmitting the dependency on input quantities

A calibration certificate states a value and an Expanded Uncertainty. Two certificates
reported that way are, to any recipient, unrelated — even when both rest on the same
reference standard in the same laboratory. The information needed to know better exists
at the issuer and is simply not sent.

METAS UncLib can send it. `metas_unclib.ustorage` serialises an uncertain number with
its full dependency structure: every input quantity, the distribution assumed for it,
the sensitivity of the result to it, and an identifier for the quantity itself. That
identifier is the load-bearing part. Two results that share an influence share its
identifier, so a later calculation involving both treats it as one influence rather than
two, and the correlation comes out right without anyone having to notice it was there.

`domain/uncertainty.py` offers both routes, and the contrast between them is the point:

- `from_expanded_uncertainty` is the classical path. It takes the two printed numbers
  and declares a **new** input quantity. Correct for this measurement, and everything
  about provenance is gone.
- `from_certificate` deserialises what the issuing laboratory actually computed, so the
  input quantities arrive **with their original identifiers**.

Both produce an identical Expanded Uncertainty. Nothing on the face of the certificate
reveals which was used. What differs is only what a recipient can do next, which is why
`traceability.shared-inputs` checks for the inherited identifiers rather than taking the
declared traceability at its word.

**Seeded identifiers are a demonstration device.** UncLib generates a random GUID per
input quantity, which is right — two laboratories using the same wording are not
describing the same influence. That would also make every run of this demonstration
produce different documents. So `seeded_input_id(label, context)` derives them from the
published seed, scoped by the certificate they belong to. The scoping is not cosmetic: an
early version seeded on the label alone, and every budget saying "temperature correction"
became one shared influence, which made unrelated results perfectly correlated. In
production this function should not exist.

**Transport.** Representations under `INLINE_LIMIT` characters are carried inside the
credential; larger ones are published separately and referenced. The binary form is
always referenced, both because that is what it is for and so the referenced path is
exercised on every run. In each case `digestMultibase` is over the **raw** payload rather
than over the JSON envelope it is published in, so the signature on the credential covers
the dependency data wherever it lives.

**GTC** is supported as an optional extra rather than a dependency, because it pulls in
scipy. It matters to the argument regardless: GTC reached the same design independently,
giving elementary uncertain numbers UUID-based identifiers and serialising archives
against published schemas. Two implementations agreeing is why the credential names a
format rather than assuming a library. `domain/gtc_archive.py` rebuilds the budget in
GTC rather than converting the UncLib object, because no bridge between the two libraries
exists and inventing one would misrepresent what is being shown.

**The cost, stated plainly.** A dependency representation exposes the internal structure
of an uncertainty budget, which many laboratories treat as commercially confidential.
That is a real objection and not an oversight. Selective disclosure is where it would be
addressed, and it is not implemented here.

### Legal metrology, and why it needed its own module

Legal metrology is the third pillar and it does not work like the other two, so
`domain/legal.py` sits beside `domain/scope.py` rather than inside it.

`domain/scope.py` decides whether a *measurement* falls inside a declared capability.
`domain/legal.py` decides whether a *decision* follows from the measurements offered for
it. A calibration certificate reports an error and an uncertainty and leaves the reader
to judge; a verification certificate has already judged, and the judgement has legal
effect. The only useful thing a recipient can do with the second kind is confirm it.

Two conditions decide a verification, and keeping them apart matters:

* **the error against the limit.** Outside the maximum permissible error, the instrument
  does not comply and a certificate saying otherwise is wrong.
* **the uncertainty against a third of the limit.** Above `MPE/3` the verification cannot
  distinguish a compliant instrument from a non-compliant one, so the certificate is not
  wrong but unsupported. `ConformityVerdict` exposes `decision_follows` and
  `adequately_measured` separately because an inspector should treat those differently.

The limits come from OIML R 76: three bands rising in half-interval steps, at different
loads for each accuracy class, doubled for an instrument already in service. The
in-service doubling is not laxity — an instrument is expected to drift within its
verification interval and is not required to stay as good as new.

**Four anchors, one thing each.** The most consequential design decision here was almost
made wrongly. OIML was initially left out of `TRUST_ANCHORS` on the reasoning that it
confers no legal force, which conflates two questions. Reaching OIML establishes
technical type evaluation perfectly well, and a national authority relying on OIML
evidence is exactly what the certification system exists for. What reaching OIML does not
establish is legal force. So OIML is an anchor, `NOT_A_LEGAL_ANCHOR` records what it does
not confer, and the distinction is enforced in `conformity.legal-basis`, which looks at
what the cited document *is* rather than at who vouches for its issuer. The result is a
failure mode with no counterpart elsewhere in the demonstration: a document that is
genuine, current, correctly signed, issued by a genuinely recognised body, reaching a
genuine trust anchor, and still unable to do the job being asked of it.

**One organisation, two roles.** METAS is both the national metrology institute and the
legal metrology authority, which is the Swiss arrangement and one of several the field
uses. It appears once in the graph, and two edges of different kinds arrive at it from
opposite ends of the row above: recognition from the BIPM, legal authority from the
ordinance. Its weight calibration chains to the BIPM and its type approval chains to the
legislator, and the two chains share nothing. Modelling it as two nodes would have been
easier to draw and would have hidden the point.

**Where the two systems join.** A verification is only as good as the standards it was
made with, so the reference weight the verification body weighs with is calibrated by the
institute under a published CMC, and the verification certificate references that
calibration certificate by content digest. The legal branch rests on the calibration
chain rather than running beside it, and `traceability` follows the reference straight
into it.

**What needed no new mechanism.** A designation is a `RecognizedEntityCredential` with
`action: "verify"`, on a status list the authority controls. Delegating verification
while keeping regulation public is exactly what that shape already expresses, and the
demonstration is better for having reused it than it would have been with a bespoke
credential type. `REQUIRED_ACTIONS` did have to grow into a set per credential type: an
accreditation body accredits and a legal metrology authority designates, and the two
produce the same kind of document from quite different standing.

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
| `conformity` | whether a legal conformity decision follows from its test points, was measured well enough to support, and rests on an approval with force in the stated jurisdiction |
| `traceability` | whether the chain of certificates below it holds, by content digest, and whether the influences of the parent are genuinely present in this result |

Every step returns a structured result rather than a boolean, and a step that cannot be
evaluated reports `skip` rather than passing quietly. `tests/test_pipeline.py` and `tests/test_legal.py` assert
that each of the seventeen failure cases is caught by the step that claims it, and that the
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

## Reproducibility

`build_world()` is deterministic: fixed seed, fixed timestamps, deterministic
signatures, and a status list compressed with a pinned modification time. Two builds
produce byte-identical documents, which `tests/test_pipeline.py` asserts and
`--dump` makes diffable.

[dcc]: https://www.ptb.de/dcc/
