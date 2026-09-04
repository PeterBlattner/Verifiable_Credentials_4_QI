# Verifiable credentials for the quality infrastructure

An interactive demonstration of what W3C [Verifiable Credentials][vc] and
[Recognized Entities][re] would look like applied to metrology, accreditation and
conformity assessment — calibration certificates, CMCs and the CIPM MRA, accreditation
scopes and the Global ACI MRA, test reports and certificates of conformity, and the type
approvals and verification certificates of legal metrology.

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
uv run pytest                                  # 225 tests
uv run python -m vcqi.actors.scenarios         # list every signed credential
uv run python -m vcqi.actors.scenarios --dump out/   # write all 84 documents as JSON
```

GTC support is optional because it pulls in scipy. Without it everything works and the
certificates carry the UncLib representation only:

```
uv sync --extra gtc     # certificates gain a GTC archive as well
```

There is also an optional interaction check. The Python suite verifies what the server
computes, and a separate harness verifies that the interface actually responds when you
click it, which is a different question and once had a different answer:

```
cd tools && npm install jsdom && cd ..
uv run vc-demo &
node tools/ui-clicks.mjs     # clicks every control on every chapter
```

The build is deterministic: signing uses RFC 6979, so two runs produce byte-identical
credentials and `--dump` output can be diffed between runs.

## What it demonstrates

The starting point was §2.4 *Product Conformity* of the Recognized Entities
specification: an accreditation body issues a `RecognizedEntityCredential` to a
conformity assessment body, so a market surveillance authority can verify a certificate
of conformity **and** the standing of whoever issued it, with no prior relationship.
The quality infrastructure already works this way on paper.

| Recognized Entities | Quality infrastructure |
| --- | --- |
| Root of trust | BIPM under the CIPM MRA; Global ACI under the Global ACI MRA; the national legislator for legal force |
| `RecognizedEntityCredential` | CIPM MRA participation; ISO/IEC 17025 accreditation |
| `RecognizedAction` + `outputValidation` | The declared CMC or the granted accreditation scope |
| Leaf credential | Calibration certificate, test report, certificate of conformity |
| `recognizedIn`, followed upward | The recognition path a recipient checks by hand today |

Note that one anchor is new: on 1 January 2026 the IAF and ILAC consolidated into
**Global Accreditation Cooperation Incorporated (Global ACI)**, whose arrangement is the
Global ACI *Multilateral* Recognition Arrangement. The CIPM MRA remains a *Mutual*
Recognition Arrangement; the demo keeps the distinction exact.

Three things go beyond the specification, because metrology needs them:

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

The classical statement is always present and always first. It is what remains legally
recognisable and the only thing an issuer without such a tool can offer. The others are
additional, never a replacement.

Chapter 6 makes the difference concrete. Two check standards, both calibrated against the
same national standard, are correlated at r = 0.69. A customer forming their difference
gets `U = 0.00086 Ω` from the dependency representations and `U = 0.0016 Ω` from the
printed numbers alone — **1.8× too large**, and the customer did nothing wrong. For a
*mean* the same omission runs the other way and produces an answer that is too
optimistic, so discarding correlation is not the conservative choice it is often taken
for.

**Verification is not calibration.** Legal metrology asks a different question and gets
a different kind of answer. A calibration reports *what is the error, and with what
uncertainty*; a verification reports *does this comply, yes or no*, and that decision has
legal effect. So a verification certificate carries the decision, the loads tested, and
the maximum permissible errors those loads were judged against — and the pipeline
confirms that the decision follows from the numbers, that the uncertainty was at most
MPE/3 at every load, and that it rests on an approval with force in the stated
jurisdiction.

There are **four** trust anchors and each establishes exactly one thing:

| Anchor | Establishes |
| --- | --- |
| `did:web:bipm.example` | metrological standing under the CIPM MRA |
| `did:web:global-aci.example` | competence to assess, under the Global ACI MRA |
| `did:web:oiml.example` | technical type evaluation — **and no legal force whatever** |
| `did:web:legislator.example` | legal force, and nothing else |

That last distinction is the point of the legal branch. An OIML Recommendation is not
law and an OIML certificate is not a national approval: it is genuine evidence that an
authority may rely on, and relying on it is exactly what the certification system is
for, but only the competent authority can make an instrument lawful. A verification
citing an OIML certificate as its legal basis passes every cryptographic check, reaches
a trust anchor, and is still rejected.

METAS holds two roles, which is the Swiss arrangement and lets the demonstration make
its sharpest point: one issuer, one identifier, two credentials, two unrelated chains
upward. Its weight calibration reaches the BIPM; its type approval reaches the
legislator; neither route can stand in for the other.

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
1. **The quality infrastructure as a trust graph** — click any organisation or edge
2. **Issuing a calibration certificate** — canonical form, hashes, signature, step by step
3. **Verification and recognition discovery** — the full pipeline, with the clock and the trust anchors under your control
4. **The CMC decides the logo** — sliders; the verdict changes where the published capability says it should
5. **Traceability and uncertainty** — budgets at each level, U growing down the chain, and the same measurement shown classically, as UncLib, and as GTC
6. **Why the dependencies matter** — two certificates, one shared standard, and what each way of reporting lets the customer do
7. **Legal metrology** — verification against calibration, where legal force comes from, and the conformity decision
8. **Break it** — seventeen failure cases, each naming the one check that catches it
9. **What this would mean in practice** — the argument, and the open questions

## The seventeen failure cases

Grouped by what it takes to notice them.

| Group | Cases | Caught by |
| --- | --- | --- |
| **Forgery** | edited value, invented issuer, loosened schema, reissued parent | proof, recognition, output-validation, traceability |
| **Standing** | expired, suspended accreditation, issuing outside the accredited activity | validity, recognition, action |
| **Metrology** | uncertainty below the CMC, level outside the range, unjustified MRA logo, understated inheritance, dependency data disagreeing with the printed line, traceability claimed but not inherited | scope, mra-logo, traceability.inherited, uncertainty.agreement, traceability.shared-inputs |
| **Legal force** | OIML certificate cited as a national approval, PASS recorded over the MPE, reference standards too coarse to support the decision, verification outside the designation | conformity.legal-basis, conformity.decision, conformity.uncertainty, output-validation |

The last two groups are the interesting ones: in every case the signature is valid, the
issuer is genuinely recognised, and the document is inside its validity period. A system
that checked only the cryptography would accept all of them. The legal group adds a
category of its own — a document that is entirely genuine and simply has no authority to
do what is being asked of it.

## Layout

```
src/vcqi/
  crypto/    jcs.py  multibase.py  keys.py  ecdsa_p256.py  dataintegrity.py
  vc/        model.py  checks.py  recognition.py  verify.py  schema.py  status.py  resolver.py
  domain/    scope.py  kcdb.py  accreditation.py  legal.py  uncertainty.py  instruments.py
             gtc_archive.py
  actors/    registry.py  scenarios.py  tamper.py
  web/       app.py  static/
tests/       test_jcs.py  test_ecdsa_p256.py  test_dataintegrity.py  test_domain.py
             test_dependencies.py  test_legal.py  test_pipeline.py  test_web.py
```

`ARCHITECTURE.md` records the design decisions, the simplifications, and what a real
deployment would need that this does not have.

[oiml]: https://www.oiml.org/
[unclib]: https://www.metas.admin.ch/en/metas-unclib
[gtc]: https://gtc.readthedocs.io/
[vc]: https://www.w3.org/TR/vc-data-model-2.0/
[re]: https://www.w3.org/TR/vc-recognized-entities-1.0/
