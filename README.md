# Verifiable credentials for the quality infrastructure

An interactive demonstration of what W3C [Verifiable Credentials][vc] and
[Recognized Entities][re] would look like applied to metrology, accreditation and
conformity assessment — calibration certificates, CMCs and the CIPM MRA, accreditation
scopes and the Global ACI MRA, test reports and certificates of conformity.

> **Everything here is fictional.** Every organisation, identifier, certificate,
> capability and signing key is invented. The identifiers use the `.example` domain
> reserved by RFC 2606 and the keys are derived from a seed published in this repository.
> Nothing produced by this project is an authentic output of any real institute,
> accreditation body or certification body, and none of it should ever be presented as one.

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
uv run python -m vcqi.actors.scenarios --dump out/   # write all 59 documents as JSON
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

Note that one anchor is new: on 1 January 2026 the IAF and ILAC consolidated into
**Global Accreditation Cooperation Incorporated (Global ACI)**, whose arrangement is the
Global ACI *Multilateral* Recognition Arrangement. The CIPM MRA remains a *Mutual*
Recognition Arrangement; the demo keeps the distinction exact.

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
a national measurement standard, having fetched 73 documents and known none of the
parties in advance.

## Chapters

0. **What a verifiable credential is** — for someone who has not met one before
1. **Keys: what a signature actually proves** — make a keypair, sign something, break it four ways, then try to forge a certificate with it
2. **The quality infrastructure as a trust graph** — click any organisation or edge
3. **Issuing a calibration certificate** — canonical form, hashes, signature, step by step
4. **Verification and recognition discovery** — the full pipeline, with the clock and the trust anchors under your control
5. **The CMC decides the logo** — sliders; the verdict changes where the published capability says it should
6. **Traceability and uncertainty** — budgets at each level, U growing down the chain, the same measurement shown four ways including as a PTB/DKD DCC, and what gets said twice as a result
7. **Why the dependencies matter** — two certificates, one shared standard, and what each way of reporting lets the customer do
8. **Break it** — fifteen failure cases, each naming the one check that catches it
9. **What this would mean in practice** — the argument, and the open questions
10. **What it would take to run** — the hosting burden computed per role, from the trust anchor down to a fifteen-person laboratory, and what a verifier actually fetches
11. **What would have to be agreed** — global harmonisation in three tiers, what cannot be decided later, and a ladder of next steps ordered by who is able to act

## The fifteen failure cases

Grouped by what it takes to notice them.

| Group | Cases | Caught by |
| --- | --- | --- |
| **Forgery** | edited value, invented issuer, loosened schema, reissued parent | proof, recognition, output-validation, traceability |
| **Standing** | expired, suspended accreditation, issuing outside the accredited activity | validity, recognition, action |
| **Metrology** | uncertainty below the CMC, level outside the range, unjustified MRA logo, understated inheritance, dependency data disagreeing with the printed line, traceability claimed but not inherited, the PTB/DKD DCC contradicting the printed value, the PTB/DKD DCC crediting a different laboratory | scope, mra-logo, traceability.inherited, uncertainty.agreement, traceability.shared-inputs, uncertainty.duplication |

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

`LEGAL-METROLOGY.md` describes the third pillar of the quality infrastructure — type
approval, verification and market surveillance — and how the demonstration would be
extended to cover it. It is deliberately not covered here: legal metrology makes the
argument broader rather than clearer, and the two pillars modelled are enough to show
what verifiable credentials offer.

[dcc]: https://www.ptb.de/dcc/
[unclib]: https://www.metas.admin.ch/en/metas-unclib
[gtc]: https://gtc.readthedocs.io/
[vc]: https://www.w3.org/TR/vc-data-model-2.0/
[re]: https://www.w3.org/TR/vc-recognized-entities-1.0/
