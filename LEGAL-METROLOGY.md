# Extending the demonstration to legal metrology

The demonstration covers two of the three pillars of the quality infrastructure:
**metrology** (BIPM, CMCs, traceability to the SI) and **accreditation** (Global ACI,
ISO/IEC 17025 scopes). The third is **legal metrology**, and it is deliberately left out.

This note records how it would be added and what is worth knowing before starting. It is
written after building the extension once, so the design is not speculative: the numbers,
the credential shapes and the failure cases below were all made to work. That work lives
on the branch `feature/legal-metrology` and is described at the end.

The demonstration as it stands is enough to show what verifiable credentials offer the
quality infrastructure. Legal metrology makes the argument broader, not clearer, and it
roughly doubles the size of the world. Add it when the audience is a legal-metrology
audience.

---

## Why it is a separate problem

Three things make legal metrology different from everything the demonstration currently
models. Each of them changes the design.

### 1. OIML is not a source of legal force

The OIML publishes Recommendations for regulated instruments and runs a certification
system (OIML-CS) that produces internationally usable type-evaluation evidence. An
OIML certificate is genuine, valuable and reusable across borders — and it approves
nothing:

> An OIML Recommendation is not law, and an OIML certificate does not constitute national
> legal approval. Legal effect comes only from the competent national or regional
> authority.

This is the single most important thing to get right, and it is easy to get wrong in a
trust-chain model. The temptation is to leave OIML out of the trust anchors on the
grounds that it confers no legal force. That conflates two questions. Reaching OIML
establishes **technical type evaluation** perfectly well, and a national authority
relying on OIML evidence is exactly what the certification system exists for. What
reaching OIML does not establish is **legal force**.

So OIML *is* an anchor, and the legal distinction belongs in a check that looks at what a
cited document **is**, not at who vouches for its issuer.

The result is a failure mode with no counterpart elsewhere in the demonstration: a
document that is genuine, current, correctly signed, issued by a genuinely recognised
body, reaching a genuine trust anchor, and still unable to do the job being asked of it.

### 2. Verification is not calibration

| | asks | answers with | who decides |
| --- | --- | --- | --- |
| **Calibration** | what is the error, and with what uncertainty | metrological information | the reader, later |
| **Verification** | does this comply with the law, yes or no | a legal conformity decision | the verifier, now |

An instrument can be beautifully calibrated and not lawfully usable in a shop; it can be
lawfully verified and less accurate than a calibration laboratory would like. Neither
statement substitutes for the other.

For the credential model this means a new subject shape. A calibration certificate
carries a measurement and leaves interpretation open. A verification certificate carries
a **decision**, and the only useful thing a recipient can do with it is confirm that the
decision follows from the evidence offered for it. So the certificate has to carry the
evidence: the loads tested, the error found at each, and the limit each was judged
against.

### 3. Delegation is not privatisation

A private company may perform legal verification. Authorisation, supervision and the
power to withdraw stay public.

> Delegating verification does not mean privatising regulation.

This needs **no new mechanism**. A designation is a `RecognizedEntityCredential` with
`action: "verify"`, scoped to instrument categories, on a status list the authority
controls. Suspending a designation invalidates every verification the body has issued, at
the next check, without any of them being reissued. Reusing the existing shape is worth
more than a bespoke credential type would be, because it shows the Recognized Entities
model already expresses the arrangement.

---

## Architecture

```
INTERNATIONAL          OIML ──────────── Recommendations, OIML-CS
                        │                (technical, no legal effect)
                        ▼
REGIONAL / NATIONAL    LEGISLATOR ─────── metrology law
                        │                (the only source of legal force)
              ┌─────────┴─────────┐
              ▼                   ▼
     legal metrology         national metrology
        authority               institute
              │                     │
       ┌──────┼──────┐        national standards
       ▼      ▼      ▼         SI traceability
    type   designation  supervision    │
  approval      │                      ▼
                ▼             calibration infrastructure
        verification body ──────────────┘
                │              (uses calibrated reference standards)
                ▼
      the instrument in service
```

**The boxes are functions, not organisations.** One body commonly performs several. In
Switzerland METAS is both the national metrology institute and the legal metrology
authority; elsewhere they are separate. Model METAS as holding both roles — it is the
truth, and it produces the sharpest demonstration in the whole project:

> One issuer, one identifier, two credentials, two entirely unrelated chains upward. The
> weight calibration reaches the BIPM; the type approval reaches the legislator. Neither
> route can stand in for the other.

Modelling it as two nodes is easier to draw and hides the point.

---

## Four trust anchors, one thing each

| Anchor | Establishes | Does **not** establish |
| --- | --- | --- |
| `did:web:bipm.example` | metrological standing under the CIPM MRA | anything legal |
| `did:web:global-aci.example` | competence to assess | anything legal |
| `did:web:oiml.example` | technical type evaluation | **any legal force whatever** |
| `did:web:legislator.example` | legal force | anything metrological |

Keep a `NOT_A_LEGAL_ANCHOR` set alongside `TRUST_ANCHORS` so the interface can say *why*
OIML is different, rather than leaving its role to be inferred.

## Actors to add

| DID | Role | Notes |
| --- | --- | --- |
| `oiml.example` | International harmonisation | anchor, but not a legal one |
| `legislator.example` | The metrology ordinance | the third anchor |
| `verifybody.example` | Authorised verification body | private, designated, suspendable |
| `retailer.example` | Instrument user | holds the verification certificate |

Give **METAS** its second role, and **PTB** a second hat as an OIML-CS Issuing Authority
— both reuse existing actors and both illustrate that one organisation performs several
functions. Broaden the existing market surveillance actor to cover in-service
metrological supervision as well as border checks; supervision is a function, not an
organisation.

That takes the world from 10 actors to 14, which is where a single static trust graph
starts to strain. Add branch tags (`metrology` / `accreditation` / `legal`) to every actor
and edge, a fourth edge kind for legal authority, and filter chips.

---

## Credentials

Four of the seven reuse existing builders unchanged.

| Credential | Type | Says |
| --- | --- | --- |
| OIML recognition | `RecognizedEntityCredential` | OIML recognises PTB as an Issuing Authority for R 76 |
| Ordinance | `RecognizedEntityCredential` | the legislator makes METAS competent: `approve`, `designate` |
| Designation | `RecognizedEntityCredential` | METAS designates the verification body: `verify`, class III up to 30 kg |
| Weight calibration | `CalibrationCertificateCredential` | METAS calibrates the 5 kg reference weight under a new mass CMC |
| OIML certificate | **new** `OimlCertificateCredential` | PTB type-evaluates the design. `legalEffect: "none"`, stated explicitly |
| Type approval | **new** `TypeApprovalCredential` | METAS approves the type for CH, citing the OIML certificate as evidence |
| Verification certificate | **new** `VerificationCertificateCredential` | the decision on one scale in one shop |

The verification certificate is the heart of it:

```json
"verification": {
  "kind": "subsequent",
  "performedOn": "2026-07-14",
  "jurisdiction": "CH",
  "accuracyClass": "III",
  "maximumCapacity": 15.0,
  "verificationScaleInterval": 0.005,
  "unit": "kg",
  "legalBasis":  { "id": "…/approvals/CH-TA-2024-0271", "digestMultibase": "u…" },
  "testPoints": [
    { "load": 2.5, "indicationError": 0.002, "maximumPermissibleError": 0.005,
      "expandedUncertainty": 0.0010, "coverageFactor": 2, "verdict": "pass" }
  ],
  "decision": "pass",
  "decisionRule": "|error| <= MPE at every load, and U <= MPE/3",
  "verificationMark": { "identifier": "CH-EV042-2026-04417", "appliedOn": "2026-07-14" },
  "validUntil": "2028-07-31",
  "referenceStandards": [
    { "id": "…/certificates/METAS-2026-0512", "digestMultibase": "u…" }
  ]
}
```

`validUntil` is when the next periodic verification falls due. A lapsed verification stops
being lawful without anything about the instrument having changed, which the existing
validity check already handles.

### Where the two systems join

`referenceStandards` is the join. A verification is only as good as the standards it was
made with, so the reference weight is calibrated by the institute under a published CMC
and referenced by content digest. The legal branch then rests on the calibration chain
rather than running beside it, and the existing `traceability` step follows the reference
straight into it.

Add one CMC entry for mass — 1 mg to 20 kg, `U = sqrt((1e-7 kg)² + (1.5e-8 · m)²)`, about
0.13 mg at 5 kg. The schema generator produces its JSON Schema and registry entry with no
code change.

---

## The conformity check

A new top-level step, skipped for anything that is not a verification certificate.

| Check | Decides | Failure means |
| --- | --- | --- |
| `conformity.decision` | every load is inside its maximum permissible error, and the recorded decision follows | the certificate is **wrong** |
| `conformity.uncertainty` | `U ≤ MPE/3` at every load | the certificate is **unsupported** |
| `conformity.legal-basis` | the cited basis is a type approval with force in the stated jurisdiction | the decision **rests on nothing** |

Keeping the first two apart matters. A load over the limit means the instrument does not
comply, so a recorded pass is false. An uncertainty above `MPE/3` means the verification
cannot distinguish a compliant instrument from a non-compliant one, whatever verdict was
written down — the certificate is not wrong so much as unsupportable, and an inspector
should treat those differently. Expose them as separate properties on the verdict.

This is also where the uncertainty work from the dependency-representation change set
does real duty rather than being decorative.

### OIML R 76 numbers that work

A retail counter scale, accuracy class III, `Max = 15 kg`, `e = 5 g`, so `n = 3000`
(class III allows 500 to 10000).

The maximum permissible error of **initial** verification, in verification scale
intervals: `±0.5 e` to 500 e, `±1.0 e` to 2000 e, `±1.5 e` to 10000 e. **Subsequent**
verification of an instrument in service is allowed **twice** that — an instrument is
expected to drift within its interval and is not required to stay as good as new.

| Load | m/e | MPE initial | MPE in service | MPE/3 |
| ---: | ---: | ---: | ---: | ---: |
| 2.5 kg | 500 | 2.5 g | 5.0 g | 1.67 g |
| 5.0 kg | 1000 | 5.0 g | 10.0 g | 3.33 g |
| 10.0 kg | 2000 | 5.0 g | 10.0 g | 3.33 g |
| 15.0 kg | 3000 | 7.5 g | 15.0 g | 5.00 g |

Errors of +2, +3, −4 and +6 g pass with margin. `U = 1.0 g` at every load clears `MPE/3`
everywhere, and is dominated by the resolution and repeatability of the scale rather than
by the reference weights — which is the honest picture and quietly makes a point: the
traceability chain matters even where the reference contributes almost nothing.

**Note the shape of the limit.** It binds hardest at the *bottom* of the range, because
the limit grows with load and the uncertainty of weighing often does not. That is the
opposite of most intuitions and the reason several loads are tested rather than the
heaviest.

---

## Failure cases

Four, forming a group of their own. In every one the signature is valid, the issuer is
genuinely recognised, the document is current, and the chain reaches a real anchor.

| Case | Caught by | Why it is new |
| --- | --- | --- |
| OIML certificate cited as the legal basis | `conformity.legal-basis` | valid credential, wrong legal force — a category the metrological cases do not cover |
| PASS recorded with a load over the MPE | `conformity.decision` | the legal counterpart of the CMC check |
| Reference standards too coarse, `U > MPE/3` | `conformity.uncertainty` | the decision may be right and is not supportable |
| Verification outside the designation | `output-validation` | genuinely designated, for something else |

---

## Pitfalls found while building it

All four were caught by the pipeline itself, which is a good sign for the design and a
warning for anyone reimplementing it.

**A designation is not an accreditation.** `REQUIRED_ACTIONS` mapped one required action
per credential type, but an accreditation body *accredits* and a legal metrology authority
*designates*, and both emit a `RecognizedEntityCredential`. It has to take a set per type.

**Status entries must match the purpose of the list they point into.** A designation is
*suspended* pending corrective action; a certificate is *revoked*. The two cannot share
one bitstring, so an issuer with both needs two lists.

**The legal layer predates Global ACI.** Dating the OIML and ordinance recognitions from
2026-01-01 alongside Global ACI made the action check reject a type approval issued in
2024 — correctly, since the recognition did not yet exist. OIML has run its certification
system for decades and the ordinance is older still; give the legal layer its own
timeline.

**Do not leave OIML out of the anchors.** Covered above, and worth repeating because it
is the mistake that looks most principled.

---

## Not covered, and worth knowing

**The European layer.** In the EU there is a further layer between OIML and national
implementation. The Measuring Instruments Directive and the Non-Automatic Weighing
Instruments Directive harmonise requirements for *placing instruments on the market and
putting them into use*, while **in-service control stays national**: verification
intervals, periodic verification, inspection regimes and enforcement differ by member
state. So the same instrument type can enter the market under harmonised rules and then
be subject to different legal-metrology arrangements in different countries. Modelling
that would mean a regional layer between the legislator and OIML, and notified bodies
with their four-digit numbers.

**Institutional variety.** The design above assumes one model. Real systems range from
fully centralised (one agency does everything) through decentralised public (regional
inspectors) to delegated (accredited private bodies), and most countries are mixed. The
demonstration can only show one; say which.

**Prepackage control, and supervision proper.** Market surveillance is more than checking
certificates: unannounced inspections, seals, complaints, prepackage control, enforcement
action. Only the credential-checking part fits this model.

---

## If you decide to build it

The reference implementation is on the branch **`feature/legal-metrology`**, three
commits ahead of `develop`:

```
bf4b24d  feat(legal): add the legal metrology branch
bea1372  feat(legal): add failure cases, chapter and graph branches
3ea7dec  fix(web): attach the inspector when a chapter asks for it
```

It works and is tested — 225 tests, 14 actors, 26 credentials, 84 documents, 17 failure
cases, reproducible byte for byte. It is **not merged** because the demonstration is
clearer without it, and because a UI defect in its chapter was not resolved to
satisfaction: the credential chips did not respond to clicks in a real browser. A cause
was found and fixed (the document inspector was attached only for a hardcoded list of
chapter ids, so a click fetched a document and rendered it into a node that was never in
the page) and verified headlessly, but not confirmed in a browser. `tools/ui-clicks.mjs`
on that branch drives the real application in a DOM and clicks every control, which is
the check that would have caught it originally.

Anyone resurrecting the branch should start there: serve it, hard-reload, and click the
seven credential chips in the legal chapter.

Estimated shape of the work if rebuilt from this note rather than the branch: a
`domain/legal.py` for the MPE table and conformity verdict, three credential builders,
one pipeline step with three children, four failure cases, one chapter, and a graph that
can hold fourteen nodes. The domain and pipeline parts are straightforward. The graph and
the chapter are where the time goes.
