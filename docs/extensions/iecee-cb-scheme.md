# The IECEE CB Scheme as a fourth arrangement - a proposal

**Status: proposed, not built.** Nothing in `src/` or `tests/` refers to anything in this
document. It records how the demonstration could be extended to the IECEE so that a later
change set can start from a design rather than from a blank page. The graph chapter
mentions the possibility in one paragraph and points here.

The design below was worked out against the code on `develop` at `b54845c` (October 2026).
Line numbers and counts are from that commit and will drift.

## 1. Why the IECEE

The world has three arrangements: the CIPM MRA under the BIPM, the accreditation
arrangement under Global ACI, and OIML-CS. Recognized Entities carries all three with the
same two constructs, a `RecognizedEntityCredential` and an `issuer.recognizedIn` pointer,
and nothing in it is specific to metrology or accreditation. The IECEE would be the test of
that claim on a system that works differently from the other three in three ways:

- **Recognition rests on peer assessment, not accreditation.** NCBs and CBTLs are assessed
  by experts from other participating bodies, initially and then every three years.
  National accreditation under ILAC/IAF is used as evidence, not as the basis. In this
  world, Confoederatio Certification and Helvetia Testing are already accredited by SAS, so
  the same two bodies would be recognised twice, on two different bases.
- **Acceptance without retesting.** The point of the CB Scheme is that an NCB in one
  country accepts a CB Test Certificate issued in another. Nothing here yet issues a
  document in the importing country on the strength of a document from abroad. The CB
  Scheme would make that decision machine-checkable, including the one condition that
  varies by country: whether that country's national differences were tested.
- **A named certification scheme.** The UNTP projection of the certificate of conformity
  records today that the certificate names no scheme, so `referenceScheme` stays empty
  (`src/vcqi/vc/untp.py`, around line 616). A CB Test Certificate would be the first
  document here with a scheme to name.

## 2. The IECEE in brief

From secondary sources only (see section 10). iecee.org refused automated retrieval while
this was written, so every statement here is on the list in section 8 to confirm.

- The IECEE is one of the IEC Conformity Assessment Systems, beside IECEx, IECQ and IECRE.
  The CB Scheme runs under IEC CA 01 (Basic Rules), IECEE 02 (Rules of Procedure) and a
  set of Operational Documents (ODs).
- **Member Bodies** represent a country and vote. They nominate the certification bodies
  that take part.
- **National Certification Bodies (NCBs)** are accepted for listed product categories and
  standards. An NCB is either *Issuing and Recognizing* (it may issue CB Test Certificates
  and accept others') or *Recognizing* only.
- **CB Testing Laboratories (CBTLs)** are associated with an NCB and accepted for listed
  standards. They test, and issue the CB Test Report on the IECEE Test Report Form (TRF)
  for the standard.
- **Peer assessment.** NCBs and CBTLs are assessed against ISO/IEC 17065 and ISO/IEC 17025
  plus the IECEE rules, by teams appointed by the IECEE, initially and every three years.
- **CB Test Certificate.** Issued by an Issuing NCB on the strength of a CB Test Report
  from one of its CBTLs. It can state which national differences were tested.
- **Recognition by another NCB.** A Recognizing NCB in another country accepts the CB Test
  Certificate and issues its national certification, possibly after testing national
  differences it does not cover.
- **Online Deliverables Database.** Every certificate is recorded. The public sees an
  extract; the full content is restricted to NCBs.
- **CB-FCS** adds factory surveillance to the CB Scheme. It is out of scope here.

## 3. Mapping onto the demonstration

| IECEE | In the demonstration |
|---|---|
| The IECEE, deciding acceptance after peer assessment | A fourth trust anchor, `did:web:iecee.example`, added to `TRUST_ANCHORS` in `actors/registry.py` |
| An NCB's acceptance (role, product category, standards) | An unsigned register entry of a new type, `IeceeAcceptance`, published by the IECEE as a `registry-entry`, as the KCDB entries and OIML Recommendations are. The standards travel as `methods`. |
| A CBTL's acceptance, under its NCB | An `IeceeAcceptance` entry with `role: "Cbtl"` and `associatedNcb`, plus a recognition signed by the NCB (see the two-hop shape below) |
| The three-year assessment cycle | Recognitions valid from 2024-03-01 to 2027-03-01, a timeline of its own, as OIML's 2021 one is |
| The basis of acceptance | `assessment: {basis: "IECEE peer assessment", against: [...], cycleYears: 3, evidence: [the SAS scopes]}` on the entry |
| CB Test Report on a TRF | `TestReportCredential`, reused, with `testReportForm` and `accredited: false` |
| CB Test Certificate | A new `CbTestCertificateCredential`, subject member `cbTestCertificate` |
| National certification based on a CB Test Certificate | `ProductConformityCredential`, reused, with `country` and `cbTestCertificate` |
| The public extract of the Online Deliverables Database | An optional IECEE profile in `actors/deployment.py`, the only anchor whose register is deliberately restricted |

## 4. Proposed design

### 4.1 Actors

- **IECEE**, `did:web:iecee.example`, role "CB Scheme trust anchor", inserted after OIML.
  Configuration gains `IECEE_ORIGIN`.
- **Confoederatio Certification** (`cab.example`), reused as the Swiss Issuing and
  Recognizing NCB. It already holds ISO/IEC 17065 accreditation SCESp 0789 from SAS, which
  becomes evidence in its IECEE acceptance.
- **Helvetia Testing** (`testlab.example`), reused as Confoederatio's CBTL. It is already
  the join between accreditation and OIML-CS, and would sit under four branches.
- **Certa**, `did:web:ncb-xx.example`, a new fictional Recognizing NCB in country XX, the
  same country as the market surveillance authority. It is inserted before surveillance.

The kettle (`urn:product:acme:kettle:KT-2200-revC`) gets a CB Test Certificate against
IEC 60335-1. A real kettle certificate would also cite IEC 60335-2-15, and the document
should say why that is left out.

### 4.2 Two hops: IECEE -> NCB -> CBTL

The IECEE recognises the NCBs. Each NCB issues its own `RecognizedEntityCredential` for
its CBTLs, which the IECEE recognises it to do. This was chosen over a flat shape in which
the IECEE recognises both directly. Two reasons:

- It makes the association between a laboratory and its NCB structural. The CBTL's chain
  of trust runs through the NCB.
- It puts the existing per-hop `recognition.arrangement-scope` check
  (`vc/recognition.py`, lines 508-547) to work. That check is the only constraint on what
  an intermediate may grant.

For the second point to hold, `domain/iecee.py` defines the IECEE's own main scopes, as
`MainScope` pairs from `domain/arrangement.py`. Each is an activity under IECEE 02:

- "CB certification"
- "CB testing"
- "CB acceptance"

The IECEE grants Confoederatio `certify` (CB certification) and `recognise` (CB testing),
and grants Certa `accept` (CB acceptance). Confoederatio grants Helvetia `test` (CB
testing). When Certa tries to recognise a laboratory, the arrangement-scope check fails on
its own: Certa is recognised for CB acceptance only.

The two-hop shape needs that care for a reason. `discover_recognition` never checks an
intermediate's own action when it issues a recognition. Only `arrangement-scope`
constrains it, and only when main scopes are present. Without the IECEE pairs, any NCB
could recognise any laboratory and the chain would still pass.

### 4.3 `domain/iecee.py`

It mirrors `domain/oiml.py` and has no `vc` imports.

- `CbScheme`: identifier, name, and the rules (IEC CA 01, IECEE 02). `to_json()` is
  published as a register entry; `reference()` is what a certificate carries.
- `Acceptance`: slug, organisation, role (`IssuingAndRecognizingNcb`, `RecognizingNcb`,
  `Cbtl`), country, product category, `methods` (the standards), `associated_ncb` (CBTLs
  only), validity window and `evidence`. `to_json()` emits the `IeceeAcceptance` shape.
- `NationalDifference`: country, standard, document and `tested`.
- `ACCEPTANCES`, the IECEE main scopes, and `acceptance_by_id`.

There is no `as_capability()`. An acceptance states no measurand or range, so the scope
check falls through to `_step_scope_by_method`, which compares the document's `standard`
with the entry's `methods`. That works without teaching `verify.py` a new capability shape.

### 4.4 Credentials

| Name | Type | Issuer, `recognizedIn` | Actions | Capability | Status list |
|---|---|---|---|---|---|
| `iecee-ncb-recognition` | RecognizedEntity | iecee, none | grants cab `certify` and `recognise`; ncb-xx `accept` | the NCB acceptance entries | new IECEE list, suspension |
| `cab-cbtl-recognition` | RecognizedEntity | cab, `iecee-ncb-recognition` | grants testlab `test` | the CBTL acceptance entry | cab's list (see 4.9) |
| `iecee-cb-report` | TestReport, reused | testlab, `cab-cbtl-recognition` | requires `issue` or `test` | the CBTL acceptance entry | testlab's list |
| `iecee-cb-certificate` | CbTestCertificate, new | cab, `iecee-ncb-recognition` | requires `certify` | the Swiss NCB entry | cab's list |
| `iecee-national-certificate` | ProductConformity, reused | ncb-xx, `iecee-ncb-recognition` | requires `issue` or `accept` | the XX NCB entry | new ncb-xx list, revocation |

The `cbTestCertificate` subject member holds:
- certificateNumber
- the scheme reference
- standard and productCategory
- ratings
- `testReport`, as a reference with a digest
- `nationalDifferences[]`, as `{country, standard, tested}`

The new builders write their new members only when they are passed. Existing credentials
keep exactly the members they have now.

Timeline, all inside the IECEE window and before `DEMO_NOW` (2026-09-04):

| Event | Date |
|---|---|
| CB testing | 2026-05-12, after the multimeter's calibration |
| CB Test Report | 2026-05-19 |
| CB Test Certificate | 2026-06-10 |
| National certificate | 2026-07-06 |

The IECEE `outputValidation` schemas:

| Document | The schema requires |
|---|---|
| CB Test Report | `testReportForm` |
| CB Test Certificate | the scheme identifier, `testReport` with a digest, and `nationalDifferences` |
| National certificate | `country` and `cbTestCertificate` |

### 4.5 The verifier

No new top-level step, so "eleven checks" and the pinned step ids stay as they are.

1. `_payload()` gains `cbTestCertificate`. If this is missed, every later step skips and
   the document still verifies.
2. `REQUIRED_ACTIONS`:
   - TestReport becomes `{issue, test}`;
   - ProductConformity becomes `{issue, accept}`;
   - `CbTestCertificateCredential: {certify}` is added.
3. `_traceability_references()` follows `cbTestCertificate`.
4. Two checks nest under `traceability`, beside `traceability.inherited`:
   - **`traceability.association`**, when the outer document is a CB Test Certificate. The
     referenced report must have been issued under an `IeceeAcceptance`, not an
     accreditation scope. Its `recognizedIn` recognition must have been issued by the
     certificate's issuer. And the IECEE's CBTL entry must list that same NCB as
     `associatedNcb`.
   - **`traceability.national-differences`**, when the referenced document is a CB Test
     Certificate. The national certificate's `country` must appear among the
     `nationalDifferences`, with `tested: true`.

   Both are computed before the `if target in visited` shortcut. Otherwise the order of
   the references would decide whether they run.
5. `recognition.py`, `_step_scope` and `_capability_document` are unchanged.

### 4.6 Failure cases

Five cases join `actors/tamper.py`, all in the Standing group:

| Key | What changes | Step that must fail |
|---|---|---|
| `cb-report-outside-the-scheme` | The certificate references the accredited test report HTS-2026-3391 instead of the CB Test Report | `traceability.association` |
| `cbtl-listed-under-another-ncb` | The IECEE's CBTL entry is republished with `associatedNcb` set to Certa | `traceability.association` |
| `recognizing-ncb-names-a-cbtl` | Certa recognises Helvetia, and the report points at that recognition | `recognition`, on `arrangement-scope` |
| `cb-standard-outside-acceptance` | The certificate's standard becomes IEC 62368-1 | `scope` |
| `national-differences-not-tested` | XX is marked `tested: false`, and the national certificate is re-issued over the new digest | `traceability.national-differences` |

### 4.7 UNTP

- `_attestation()` takes an optional scheme and fills `referenceScheme`. Existing outputs
  stay byte-identical.
- A new `project_cb_test_certificate` is added. Its assessment level is `authority-peer`.
- National differences are dropped and the drop is recorded as a finding: UNTP has no
  member for the fact a Recognizing NCB decides on.
- `project_product_conformity` chooses its level from the capability type. A national
  certificate resting on an IECEE acceptance must not claim the level the accreditation
  arrangement earns.

### 4.8 Harmonisation and the chapters

**New harmonisation items:**

| Item | Tier and status | What it records |
|---|---|---|
| `national-differences` | floor, partial | National differences need publishing as data per country and standard |
| `scheme-identifier` | irreversible, partial | The first `referenceScheme` filled here, with an invented identifier |
| `assessment-basis` | irreversible, open | Peer assessment vs accreditation: the entry records `assessment.evidence`, and nothing reads it |

**Ladder:** a new rung, "The IECEE publishes national differences and scheme identifiers
as data".

**Existing items to update:**
- `chain-crossing`: four arrangements instead of three;
- `anchors`;
- `status-meaning`: an acceptance lapsing for want of re-assessment;
- `type-identity`;
- `reliance-policy`: the national-differences check is the importing country's policy,
  built into every verifier.

**Interface:**
- The graph gains an `iecee` branch, positions for the two new organisations, and an "All"
  filter chip in place of "All three".
- `CREDENTIAL_LABELS` and `NOTES` gain five entries.
- The issuing chapter gains five `doc.*` blocks.
- There is no new chapter.

### 4.9 Risks found in the code

- **Silent skips.** A credential type missing from `_payload` or `REQUIRED_ACTIONS` makes
  later steps skip rather than fail. Guard tests:
  - every non-recognition type has a non-empty payload;
  - every type in `DATA_MODEL_URLS`, apart from the scope type, is in `REQUIRED_ACTIONS`.
- **One status list per issuer domain.** `scenarios.py` registers lists as
  `status-{domain}` (line 749). Confoederatio's list is a revocation list, so its
  recognition of Helvetia goes on it as revocation, with the reason recorded: an NCB
  withdrawing a laboratory is final. A second list for the same domain would silently
  replace the first.
- **The IECEE main scopes are load-bearing.** See 4.2: without them, `arrangement-scope`
  is never added and the intermediate is not constrained. The `recognizing-ncb-names-a-cbtl`
  case is the regression test.
- **Substring matching in `_step_scope_by_method`.** "IEC 60335-2-1" matches
  "IEC 60335-2-15". Either the standards are chosen so they do not overlap, or the match
  is tightened to a designation boundary in a separate `fix(verify)`.
- **The timeline.** `_step_action` rejects a document issued before its recognition
  began, so every IECEE document must fall inside the 2024-2027 window.
- **The graph.** Confoederatio and Helvetia already share an edge. `test_graph_layout` has
  to accept the new routing, and its pin on Helvetia's branches gains `iecee`.
- **Whois.** `_whois_presentations` maps each DID to one credential. Confoederatio and
  Helvetia would each sit in more than one arrangement, so the identifier-based fallback
  needs checking.
- **Depth.** The national certificate's evidence chain would be five documents deep
  (national certificate, CB Test Certificate, CB Test Report, the laboratory's
  calibration, the institute's certificate). That is exactly `MAX_TRACEABILITY_DEPTH`.

## 5. Files a build would touch

| Area | Files |
|---|---|
| Actors and configuration | `config.py`, `actors/registry.py` |
| Domain | new `domain/iecee.py` |
| World | `actors/scenarios.py`: URLs, `STATUS_INDEX`, timestamps, `_build_schemas`, `_publish_registries`, `_status_lists`, a new `_iecee_cb_scheme()` after `_oiml_certification`, `_whois_presentations` |
| Credentials | `vc/model.py`, `vc/datamodel.py` (`DATA_MODEL_URLS`, `_TYPES`, the `_capability_reference` enum) |
| Verifier | `vc/verify.py` (`recognition.py` unchanged) |
| Failure cases | `actors/tamper.py` |
| UNTP | `vc/untp.py`, `actors/interop.py` |
| Harmonisation, hosting | `actors/harmonisation.py`, optionally `actors/deployment.py` |
| Web | `web/app.py` (`BRANCHES`, `BRANCH_OF_CREDENTIAL`, `_graph()`, the `/api/verify` staple list), `static/js/graph.js`, `static/js/chapters.js` |
| Prose | the graph, issuing, verification, break-it, harmonisation and infrastructure chapters |
| Documentation | `README.md`, `ARCHITECTURE.md`, `PLAN.md` |
| Tests | `test_pipeline`, `test_datamodel`, `test_web`, `test_graph_layout`, `test_readme`, `test_untp`, `test_harmonisation`, `test_domain` |

## 6. Figures that would move

Take each new value from the run, not from this table.

| Figure | Now | After |
|---|---|---|
| Organisations / arrangements | 13 / 3 | 15 / 4 |
| Credential types | 8 | 9 |
| Failure cases | 25 | 30 |
| Documents written by `--dump` | 86 | about 106 |
| Status lists | 9 | 11 |
| Reserved status positions | 1,179,648 | 1,441,792 |

These must **not** move, because the `cab-conformity` path is untouched, and a test should
say so:
- "eleven checks";
- "98 retrievals across 35 distinct";
- the portability figures "35" and "20".

The number words in `test_readme.WORDS` and `test_web.WORD_FOR_NUMBER` need "four",
"fifteen" and "thirty".

## 7. Suggested build order

On a `feature/iecee-cb-scheme` branch from `develop`, with tests green at every commit:

1. `docs(plan): open change set, the IECEE CB Scheme`
2. `feat(actors): add IECEE and a Recognizing NCB`
3. `feat(domain): add CB Scheme acceptances and differences`
4. `feat(scenarios): add the CB Scheme branch to the world`
5. `feat(verify): check CBTL association, national differences`
6. `feat(tamper): add five CB Scheme failure cases`
7. `feat(untp): name the scheme on the CB Test Certificate`
8. `feat(harmonisation): add what a fourth arrangement needs`
9. `docs: describe the fourth arrangement`
10. `docs(plan): close the change set and archive it`

When the change set is built, this document should be deleted rather than left to
contradict the code, as `LEGAL-METROLOGY.md` was.

**Verification:**
- `python -m pytest`, `python -m mypy .` and `python -m ruff check .` all pass.
- Two `--dump` runs are byte-identical.
- A diff against a `develop` dump, with `credentialSchema` and `proof` masked, shows no
  other change to existing documents.
- `tools/ui-clicks.mjs` shows every control responding, with raised floors.
- Deliberate breaks, each confirmed to fail exactly the expected test and then reverted:
  - remove `cbTestCertificate` from `_payload` and from `_traceability_references`;
  - move the relation checks after the visited shortcut;
  - drop `test` from `REQUIRED_ACTIONS`;
  - remove the IECEE main scope from Confoederatio's `recognise` action;
  - start the IECEE window after the certificate.

## 8. Facts to confirm before building

Each needs a primary source: IEC CA 01, IECEE 02, the ODs, or the IECEE secretariat.

1. The roles "Issuing and Recognizing" and "Recognizing" NCB. Acceptance per product
   category and per standard. The category code for household appliances.
2. A CBTL is associated with exactly one NCB, and an Issuing NCB issues only on reports
   from its own CBTLs. The association check and three of the five failure cases rest on
   this.
3. Peer assessment initially and every three years, with ILAC/IAF accreditation used as
   evidence only.
4. The TRF is mandatory for a CB Test Report, and the format of its identifier.
5. Whether a CB Test Certificate lists the national differences tested, and whether it has
   an expiry date.
6. What a Recognizing NCB is obliged to do, whether it may still require samples or tests,
   and what it issues: a certificate, a mark licence, or neither.
7. How national differences are published (the CB Bulletin), and how group differences
   such as CENELEC's are handled.
8. Whether UNTP's `authority-peer` level, and the "certification" attestation type, fit a
   CB Test Certificate that covers a tested sample with no surveillance.

## 9. Out of scope, by decision

- CB-FCS and factory surveillance.
- Member Body governance.
- Customer Testing Facility arrangements.
- The restricted content of the Online Deliverables Database.
- IEC 60335-2-15.
- A VCALM workflow for the CB documents.
- An editable CB document in the tamper chapter.
- A signed IECEE register.

## 10. Sources

Secondary sources, consulted October 2026:

- Nemko, "The extensive IECEE peer assessment regime":
  https://www.nemko.com/blog/the-extensive-iecee-per-assessment-regime
- NEMA, "IECEE CB Scheme":
  https://nema.org/standards/technical/the-abcs-of-conformity-assessment/iecee-cb-scheme
- IECEx, peer assessment comparison:
  https://www.iecex.com/archive/committee_docs/1379e_Peer_Assessmnt_Comparison.pdf
- IECEE, online certificates (refused automated retrieval):
  https://www.iecee.org/certification/certificates/
- IECEE, members (refused automated retrieval): https://www.iecee.org/members
