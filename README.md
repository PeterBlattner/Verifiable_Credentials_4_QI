# Verifiable credentials for the quality infrastructure

An interactive demonstration of what W3C [Verifiable Credentials][vc] and
[Recognized Entities][re] would look like applied to metrology, accreditation and
conformity assessment — calibration certificates, CMCs and the CIPM MRA, accreditation
scopes and the ILAC MRA, test reports and certificates of conformity.

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
uv run pytest                                  # 134 tests
uv run python -m vcqi.actors.scenarios         # list every signed credential
uv run python -m vcqi.actors.scenarios --dump out/   # write all 52 documents as JSON
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
| Root of trust | BIPM under the CIPM MRA; ILAC under the ILAC MRA |
| `RecognizedEntityCredential` | CIPM MRA participation; ISO/IEC 17025 accreditation |
| `RecognizedAction` + `outputValidation` | The declared CMC or the granted accreditation scope |
| Leaf credential | Calibration certificate, test report, certificate of conformity |
| `recognizedIn`, followed upward | The recognition path a recipient checks by hand today |

Two things go beyond the specification, because metrology needs them:

**The CMC decides the logo.** An institute may apply the CIPM MRA logo only to work
covered by a capability it has published in the KCDB. Here that is an explicit
machine-checkable claim rather than an image, adjudicated by the recipient against the
signed registry entry. The bound runs in the direction people new to it get backwards:
a capability states the *smallest* achievable uncertainty, so a certificate claiming a
*smaller* one is out of scope.

**Uncertainty travels with its budget.** Each certificate carries the full GUM budget,
including what it inherited from the certificate above it. A recipient can then check
both that `U = k·u` and that the inherited line matches what the parent certificate
actually reports. Propagation uses `metas_unclib`, which tracks provenance so
correlated contributions are not double counted.

## The scenario

```
BIPM ──recognises──▶ METAS ──calibrates──▶ Alpine Calibration's 10 kΩ standard
                                                    │
ILAC ──recognises──▶ SAS ──accredits──▶ Alpine Calibration
                          ├─accredits──▶ Helvetia Testing
                          └─accredits──▶ Confoederatio Certification
                                                    │
Alpine ──calibrates──▶ Helvetia's multimeter ──measures──▶ a kettle
                                                    │
Helvetia ──test report──▶ Confoederatio ──certificate of conformity──▶ Acme
                                                    │
                                      Market surveillance authority, at a border,
                                      trusting only did:web:bipm.example and
                                      did:web:ilac.example
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
5. **Traceability and uncertainty** — budgets at each level, and U growing down the chain
6. **Break it** — eleven failure cases, each naming the one check that catches it
7. **What this would mean in practice** — the argument, and the open questions

## The eleven failure cases

Grouped by what it takes to notice them.

| Group | Cases | Caught by |
| --- | --- | --- |
| **Forgery** | edited value, invented issuer, loosened schema, reissued parent | proof, recognition, output-validation, traceability |
| **Standing** | expired, suspended accreditation, issuing outside the accredited activity | validity, recognition, action |
| **Metrology** | uncertainty below the CMC, level outside the range, unjustified MRA logo, understated inheritance | scope, mra-logo, traceability.inherited |

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

`ARCHITECTURE.md` records the design decisions, the simplifications, and what a real
deployment would need that this does not have.

[vc]: https://www.w3.org/TR/vc-data-model-2.0/
[re]: https://www.w3.org/TR/vc-recognized-entities-1.0/
