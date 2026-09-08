# Verifiable credentials for the quality infrastructure

An interactive demonstration of what W3C [Verifiable Credentials][vc] and
[Recognized Entities][re] would look like applied to metrology, accreditation and
conformity assessment — calibration certificates, CMCs and the CIPM MRA, accreditation
scopes and the Global ACI MRA, test reports and certificates of conformity.

> **Curiosity project — not validated, not official.** An AI-assisted weekend experiment
> exploring what W3C Verifiable Credentials might mean for the Quality Infrastructure. No
> institution named here has reviewed or endorsed any of it.

## About these pages, and what they are not

This started as curiosity. A friend pointed me to the W3C Recognized Entities
specification, whose use case §2.4 (Product Conformity) looked potentially relevant to the
Quality Infrastructure. Over a few hours one weekend I used AI-assisted coding to sketch a
simple metrology and accreditation scenario, mainly to understand Verifiable Credentials
better myself. I was struck by how much came together in so little time — which is exactly
why the following warnings matter.

**Nothing here has been validated.** The concepts, data models, credential examples and
workflows are illustrative sketches, not reference implementations. Nothing here has been
tested in an interoperable deployment or checked line by line against the specifications.

One reviewer who works on these specifications has since spent about half an hour on it,
over the data structures and the harmonisation chapter. Their reading was that most of the
data structures hold up as a first draft, and that the harmonisation chapter overstated the
problem: several things it listed as unsolved already have answers, some of them published
while this was being written. Those corrections are in chapter 11, which now counts its
open questions rather than asserting them. That is one reader's opinion after thirty
minutes, and it is the only review this work has had. It is not validation, and it changes
nothing about the warnings here.

Every organisation, identifier, certificate, capability and signing key is invented: the
identifiers use the `.example` domain reserved by RFC 2606 and the keys are derived from a
seed published in this repository, so they protect nothing. Nothing produced by this
project is an authentic output of any real institute, accreditation body or certification
body, and none of it should ever be presented as one.

**No institution is speaking here.** BIPM, Global ACI, METAS and PTB appear only as
recognisable placeholders in a fictional scenario. Nothing here represents their views,
plans, positions or endorsement, and none of them were involved in or informed about this
work.

**The underlying specification is still moving.** Recognized Entities v1.0 is a W3C
Working Draft, described by the Working Group as experimental and not fit for production
deployment. Anything here may already be out of date.

**No warranty.** The content is provided as-is, for educational purposes only, with no
assurance of correctness or fitness for any purpose. Do not rely on it for any decision
about accreditation, conformity assessment or metrological traceability.

**No permanence.** These pages may change or disappear without notice.

The same statement is the first chapter of the demonstration itself, in
[`00-cautions.md`](src/vcqi/web/content/chapters/00-cautions.md). Correct one and correct
the other. The hope is simply that this sparks curiosity — and, ideally, correction. If
something here is wrong, I would genuinely like to hear it.

That has happened once already, unsolicited, and it made the work better rather than worse
— which is the argument for publishing something unfinished in the first place. The offer
stands.

## Run it

```
uv sync
uv run vc-demo
```

Then open <http://127.0.0.1:8000>. No npm, no build step — the interface is plain ES
modules and hand-written CSS served straight from `src/vcqi/web/static/`.

```
uv run pytest                                  # the whole suite
uv run python -m vcqi.actors.scenarios         # list every signed credential
uv run python -m vcqi.actors.scenarios --dump out/   # write all 76 documents as JSON
```

Two extras, both optional and neither needed to run the demonstration:

```
uv sync --extra unclib  # propagate with METAS UncLib itself
uv sync --extra gtc     # certificates gain a GTC archive as well
```

`unclib` is for **licensed machines only**. METAS UncLib is the reference implementation
of the uncertainty propagation here, and its licence covers one designated computer and
forbids redistribution, so it cannot ship in a container image. Without it the
demonstrator computes with its own linear-propagation engine, which covers the models
used here exactly and writes byte-identical dependency representations;
`tests/test_linprop_equivalence.py` checks both claims on a machine that has the
library. Set `VCQI_ENGINE=linprop` to force that engine even where UncLib is installed,
which is how a deployed build is reproduced locally. See `ARCHITECTURE.md`.

`gtc` is optional because it pulls in scipy. Without it everything works and the
certificates carry one fewer representation.

The build is deterministic: signing uses RFC 6979, so two runs produce byte-identical
credentials and `--dump` output can be diffed between runs.

There is also an optional interaction check. The Python suite verifies what the server
computes; a separate harness verifies that the interface responds when you click it,
which is a different question and has twice had a different answer:

```
cd tools && npm install jsdom && cd ..
uv run vc-demo &
node tools/ui-clicks.mjs     # clicks every control on every chapter
```

## Run it on the web

The demonstration argues that a verifier operates nothing. It should ask no more of its
own reader than a URL, which means not asking them to install Python first — and on a
managed machine, running an unsigned executable is often prohibited outright.

`Dockerfile` and `render.yaml` are all that is needed. There is nothing to install
locally: Render builds the image on its own builders and everything below is done in a
browser.

0. **Merge `develop` into `main` first.** `render.yaml` sets `branch: main`, and a
   blueprint has nothing to build until `main` carries the `Dockerfile`. Because `main`
   is the deployment branch, that pull request is also what publishes each new version;
   `ci.yml` runs on it, so the tests have passed on exactly that content first.
1. **Render → New → Blueprint**, and pick this repository. `render.yaml` defines the
   service, so there is no dashboard configuration to remember or reproduce. Render
   reads it, shows what it will create, and asks for confirmation.
2. **Watch the first build.** It should end with the two assertions from the Dockerfile
   in the log — that the interface reached the wheel, and that `metas_unclib` is *not*
   in the image — and then `/healthz` going green. First build is a few minutes; later
   ones reuse cached layers.
3. **Check the health endpoint** at `https://<service>.onrender.com/healthz`. It reports
   `"engine": "linprop"`, which is the confirmation that the deployment is computing
   with the engine it is licensed to ship, and the commit it is running.
4. **Settings → Custom Domains**, add the hostname, then create the DNS records below.
   Certificates are issued and renewed automatically, and HTTP is redirected to HTTPS.

| Type | Name | Value | Notes |
| --- | --- | --- | --- |
| `CNAME` | `vc` (or `www`) | `<service>.onrender.com.` | What Render wants for any non-apex name. |
| `ALIAS` / `ANAME` | `@` | `<service>.onrender.com.` | For the bare domain, if the registrar supports it. Preferred: no address is hard-coded. |
| `A` | `@` | Render's load-balancer address | Fallback where `ALIAS` is unavailable. Take the address from the dashboard rather than from here. |
| `AAAA` | any | — | **Delete them.** Render is IPv4-only, and a stale `AAAA` is the usual reason a certificate never issues. |

Pick one canonical hostname and redirect the other, so the demonstration has one address.

Two things worth knowing before the link circulates. The free instance spins down after
about fifteen minutes idle and takes the better part of a minute to wake, which is the
wrong behaviour for a link opened live in a meeting — `plan: starter` in `render.yaml`
removes it. And crawlers are asked off by default (`VCQI_ALLOW_INDEXING=0`), because this
names METAS, BIPM and PTB/DKD while inventing their documents; allowing indexing is a
deliberate decision rather than a default.

Environment variables, all optional and all defaulting to local behaviour:

| Variable | Default | Effect |
| --- | --- | --- |
| `VCQI_HOST` | `127.0.0.1` | Bind address. The container sets `0.0.0.0`. |
| `PORT` | `8000` | Managed hosts assign this. |
| `VCQI_PUBLIC` | `0` | Turns on the request limits, drops the API docs, and refuses to start if the interface is missing from the package. |
| `VCQI_RATE_LIMIT_BURST` | `0` (off) | Token bucket size, per client address. |
| `VCQI_RATE_LIMIT_PER_SECOND` | `1.0` | Refill rate. |
| `VCQI_MAX_BODY_BYTES` | `262144` | Largest request body parsed. |
| `VCQI_ALLOW_INDEXING` | `0` | Whether `robots.txt` and `X-Robots-Tag` invite crawlers. |
| `VCQI_ENGINE` | unset | Set to `linprop` to force the deployed uncertainty engine locally. |

`ARCHITECTURE.md` records why `/api/keys/*` is safe to expose and what changed when the
old answer — "the server binds to localhost" — stopped being true.

## What it demonstrates

The starting point was §2.4 *Product Conformity* of the Recognized Entities
specification: an accreditation body issues a `RecognizedEntityCredential` to a
conformity assessment body, so a market surveillance authority can verify a certificate
of conformity **and** the standing of whoever issued it, with no prior relationship.
The quality infrastructure already works this way on paper.

| Recognized Entities | Quality infrastructure |
| --- | --- |
| Root of trust | BIPM under the CIPM MRA; Global ACI under the Global ACI MRA |
| `RecognizedEntityCredential` | CIPM MRA participation; ISO/IEC 17025 accreditation |
| `RecognizedAction` + `outputValidation` | The declared CMC or the granted accreditation scope |
| Leaf credential | Calibration certificate, test report, certificate of conformity |
| `recognizedIn`, followed upward | The recognition path a recipient checks by hand today |

The accreditation anchor is a placeholder: **Global ACI** stands in for whichever body
holds that role, and nothing in the demonstration rests on the name. Its arrangement is
written as a *Multilateral* Recognition Arrangement and the CIPM MRA as a *Mutual* one,
because the demonstration keeps that distinction rather than treating the two as
interchangeable. A verifier follows identifiers upward and never needs to know which
organisation occupies a position.

Chapter 1 answers the question the rest of the demonstration assumes: what a public and
a private key actually are. It derives a keypair in front of you, computes the public key
from the private one as `Q = d·G` on the P-256 curve, peels the four encodings between
that point and the `publicKeyMultibase` in a DID document, and then lets you sign a real
calibration certificate with your own key. All three ways of trying that fail, for three
different reasons — including one that **passes** the recognition check while failing the
proof, which is why the pipeline runs both.

Two things go beyond the specification, because metrology needs them:

**The CMC decides the logo.** An institute may apply the CIPM MRA logo only to work
covered by a capability it has published in the KCDB. Here that is an explicit
machine-checkable claim rather than an image, adjudicated by the recipient against the
signed registry entry. The bound runs in the direction people new to it get backwards:
a capability states the *smallest* achievable uncertainty, so a certificate claiming a
*smaller* one is out of scope.

**Uncertainty travels with its dependencies.** A calibration certificate has always
stated a value and an Expanded Uncertainty. That is enough to judge a result and not
enough to use it: a customer combining two certificates cannot tell that both rest on the
same reference standard, so the shared part gets counted twice.

So every certificate here offers its uncertainty three ways at once:

| Representation | What it carries | What a recipient can do with it |
| --- | --- | --- |
| **Classical** | `value ± U (k = 2)` | judge the result; combine only as if independent |
| **METAS UncLib** | every input quantity, its own identifier, its distribution, and the sensitivity to it — as [XML or binary][unclib] | recombine correctly, because shared influences are recognisable |
| **GTC** | the same idea from [MSL New Zealand][gtc], UUID-identified elementary quantities in a JSON archive | the same, from an independent implementation |
| **PTB/DKD DCC** | the whole certificate in the [PTB/DKD][dcc] schema 3.3.0, quantities in D-SI | read it as a standardised calibration certificate |

The classical statement is always present and always first. It is what remains legally
recognisable and the only thing an issuer without such a tool can offer. The others are
additional, never a replacement.

The UncLib XML has since acquired a second implementation, which is a small piece of
evidence for the argument rather than an incidental fact: this repository writes and
reads that format itself, byte for byte, without the library. A representation only
transmits dependencies usefully if a recipient can consume it with their own tools, and
that is now demonstrated instead of assumed.

The last one sits at a different level, and that is the useful part. The first three
describe a **result**; a PTB/DKD DCC describes a **document** — who calibrated what, for
whom, when, under which conditions. Inside it the quantity is D-SI, and D-SI's
`si:expandedUnc` carries a value, an uncertainty and a coverage factor, which is the
classical statement and not the dependency structure. So they compose rather than
compete, and a certificate wanting both carries both.

Carrying it is not free. Wrapping a standardised document inside a credential says most
of the certificate twice — who calibrated, for whom, when, under which number, and the
integrity mechanism itself. Duplication permits disagreement, and a signature does
nothing about copies that were written inconsistent. So the verifier reads both and
compares them, and the demonstration signs once: the credential proof covers the
credential, the credential carries a digest of the DCC bytes, and the `ds:Signature`
slot stays empty. Chapter 6 lays out the alternatives.

Chapter 6 makes the difference concrete. Two check standards, both calibrated against the
same national standard, are correlated at r = 0.69. A customer forming their difference
gets `U = 0.00086 Ω` from the dependency representations and `U = 0.0016 Ω` from the
printed numbers alone — **1.8× too large**, and the customer did nothing wrong. For a
*mean* the same omission runs the other way and produces an answer that is too
optimistic, so discarding correlation is not the conservative choice it is often taken
for.

## The scenario

```
BIPM ──recognises──▶ METAS ──calibrates──▶ Alpine Calibration's 10 kΩ standard
                                                    │
Global ACI ──recognises──▶ SAS ──accredits──▶ Alpine Calibration
                          ├─accredits──▶ Helvetia Testing
                          └─accredits──▶ Confoederatio Certification
                                                    │
Alpine ──calibrates──▶ Helvetia's multimeter ──measures──▶ a kettle
                                                    │
Helvetia ──test report──▶ Confoederatio ──certificate of conformity──▶ Acme
                                                    │
                                      Market surveillance authority, at a border,
                                      trusting only did:web:bipm.example and
                                      did:web:global-aci.example
```

That authority runs eleven checks, and reaches a verified path from the kettle down to
a national measurement standard, having fetched 76 documents and known none of the
parties in advance.

## Three arrangements, and where they join

The demonstration models three roots of trust, one per arrangement:

| Anchor | Arrangement | What reaching it establishes |
| --- | --- | --- |
| BIPM | CIPM MRA | The institute's calibrations are covered by a published CMC |
| Global ACI | Global ACI MRA | The body is accredited for the activity it is performing |
| OIML | OIML-CS | The type was evaluated against an international Recommendation |

The interesting case is a document that needs two of them. An OIML certificate says a
type of electricity meter meets OIML R 46. It rests on a type evaluation performed by a
laboratory the OIML-CS recognises — and that evaluation is a *measurement*, made with a
multimeter whose accredited calibration is traceable to a national standard. So verifying
one certificate walks upward to OIML through recognition and downward to the BIPM through
evidence, and the two paths have nothing in common except the laboratory in the middle.

That laboratory, Helvetia Testing, is recognised twice for different things: accredited by
SAS under ISO/IEC 17025, and recognised by OIML to perform type evaluation. One
organisation, one identifier, two arrangements above it, neither aware the other exists.
Chapter 11 has called composing arrangements "the entire reason for doing any of this"
since it was written; this is the first document in the demonstration that actually does
it, and chapter 2's filter is there to make the join visible.

Two things the OIML-CS branch adds that the other pillars did not need:

- **The Recommendation is the scope.** A CMC and an accreditation scope are declarations
  an organisation writes about itself, so this project had to invent a machine-checkable
  form for them. An OIML Recommendation is a numbered, edition-controlled document
  published by somebody else, which is a much stronger thing for a recognition to point
  at. What is still invented is the schema: R 46 is not machine-readable, so the schema
  here is this project's reading of it. The OIML has a sub-group working towards
  machine-readable Recommendations, and that gap is the last item in chapter 11.
- **A certificate that attests without authorising.** An OIML certificate is evidence, not
  permission — a Recommendation is not law. It carries `legalEffect: "none"` and a sentence
  saying so, and the schema makes that a validation requirement, so a certificate that
  quietly drops the disclaimer fails rather than reading as an approval. The authority that
  would turn evidence into permission is not modelled at all.

Two things it deliberately does **not** say, because no primary source to hand settles
them: what distinguishes OIML-CS Scheme A from Scheme B, and what SMART stands for.

## Chapters

0. **What a verifiable credential is** — for someone who has not met one before
1. **Keys: what a signature actually proves** — make a keypair, sign something, break it four ways, then try to forge a certificate with it
2. **The quality infrastructure as a trust graph** — thirteen organisations, three arrangements, filterable; click any organisation or edge
3. **Issuing a certificate** — canonical form, hashes, signature, step by step
4. **Verification and recognition discovery** — the full pipeline, with the clock and the trust anchors under your control
5. **The CMC decides the logo** — sliders; the verdict changes where the published capability says it should
6. **Traceability and uncertainty** — budgets at each level, U growing down the chain, the same measurement shown four ways including as a PTB/DKD DCC, and what gets said twice as a result
7. **Why the dependencies matter** — two certificates, one shared standard, and what each way of reporting lets the customer do
8. **Break it** — 18 failure cases, each naming the check that catches it
9. **What this would mean in practice** — the argument, and the open questions
10. **What it would take to run** — the hosting burden computed per role, from the trust anchor down to a fifteen-person laboratory, and what a verifier actually fetches
11. **What would have to be agreed** — global harmonisation in three tiers, what cannot be decided later, and a ladder of next steps ordered by who is able to act

## The 18 failure cases

Grouped by what it takes to notice them.

| Group | Cases | Caught by |
| --- | --- | --- |
| **Forgery** | edited value, invented issuer, loosened schema, reissued parent | proof, recognition, output-validation, traceability |
| **Standing** | expired, suspended accreditation, issuing outside the accredited activity, certifying a type against a Recommendation nobody approved, resting a certificate on an unrecognised laboratory | validity, recognition, action, scope, traceability |
| **Metrology** | uncertainty below the CMC, level outside the range, unjustified MRA logo, understated inheritance, dependency data disagreeing with the printed line, traceability claimed but not inherited, the PTB/DKD DCC contradicting the printed value, the PTB/DKD DCC crediting a different laboratory, a type evaluation made with equipment out of calibration | scope, mra-logo, traceability, traceability.inherited, uncertainty.agreement, traceability.shared-inputs, uncertainty.duplication |

The third group is the interesting one: in every case the signature is valid, the issuer
is genuinely recognised, and the document is inside its validity period. A system that
checked only the cryptography would accept all of them.

## Layout

```
src/vcqi/
  crypto/    jcs.py  multibase.py  keys.py  ecdsa_p256.py  dataintegrity.py
  vc/        model.py  checks.py  recognition.py  verify.py  schema.py  status.py  resolver.py
  domain/    scope.py  kcdb.py  accreditation.py  uncertainty.py  instruments.py
  actors/    registry.py  scenarios.py  tamper.py
  web/       app.py  static/
tests/       test_jcs.py  test_ecdsa_p256.py  test_dataintegrity.py
             test_domain.py  test_pipeline.py  test_web.py
```

`CONTENT.md` says where the words are and how to change them without touching code. The
chapter prose lives in markdown files, edited in the GitHub web interface and merged by
pull request; the tests run on the pull request and say plainly if an edit is wrong.

`ARCHITECTURE.md` records the design decisions, the simplifications, and what a real
deployment would need that this does not have.

The third pillar, legal metrology, is covered **only as OIML-CS**: an Issuing Authority
recognised to certify a type against an OIML Recommendation, a Test Laboratory recognised
to perform the type evaluation, and the certificate that rests on it. Utilizers and
Associates are out of scope, and so is everything downstream of the certificate — national
type approval, national verification, market surveillance. Those are where legal *force*
comes from, and an OIML Recommendation is not law: the certificate here says in
`legalEffect` that it authorises nothing anywhere, and the authority that would convert it
into permission is not modelled.

There was a design document for the broader version, `LEGAL-METROLOGY.md`, written after
building it once and then reverting it. It has been deleted rather than left to contradict
the code: most of it was about the national layer, which is not being built. It is still in
git history if the argument is wanted — `git show ba1c144:LEGAL-METROLOGY.md`, with the
reference implementation at `bf4b24d` and `bea1372`.

[dcc]: https://www.ptb.de/dcc/
[unclib]: https://www.metas.admin.ch/en/metas-unclib
[gtc]: https://gtc.readthedocs.io/
[vc]: https://www.w3.org/TR/vc-data-model-2.0/
[re]: https://www.w3.org/TR/vc-recognized-entities-1.0/
