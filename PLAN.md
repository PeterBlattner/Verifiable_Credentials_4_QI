# Change set 1 - the demonstrator (complete)

# Verifiable Credentials for the Quality Infrastructure — interactive demonstrator

## Context

W3C published *Recognized Entities v1.0* (`https://www.w3.org/TR/vc-recognized-entities-1.0/`).
Its §2.4 *Product Conformity* describes an accreditation body issuing a
`RecognizedEntityCredential` to a conformity assessment body, so a market surveillance
authority can verify a certificate of conformity **and** the issuer's accreditation
without any prior relationship.

The same shape fits metrology exactly, and the parallel is worth making concrete:

| Recognized Entities concept | Quality-infrastructure equivalent |
| --- | --- |
| Root of trust | BIPM (CIPM MRA) and ILAC (ILAC MRA) |
| `RecognizedEntityCredential` | CIPM MRA signatory status; ISO/IEC 17025 accreditation |
| `RecognizedAction.outputValidation` | The declared CMC scope in the KCDB / the accreditation scope |
| Leaf credential | Calibration certificate, test report, certificate of conformity |
| Chain traversal via `recognizedIn` | The recognition path a customer today has to check by hand |

The goal is a **runnable, presentation-grade demonstrator** that teaches verifiable
credentials from zero *and* argues the domain case: what actually becomes smarter if
calibration certificates, accreditation and CMC scope were machine-verifiable.
Two things the demo must show that go beyond the W3C use case:

1. **CMC scope enforcement** — an NMI may only apply the CIPM MRA logo when the
   calibration falls inside its declared CMCs. Today that is a human judgement.
   Here a verifier decides it automatically from the signed KCDB entry.
2. **Traceability and uncertainty** — the credential chain mirrors the metrological
   traceability chain, and the expanded uncertainty `U (k=2)` grows measurably at each
   hop. Recomputed with `metas_unclib`, so the verifier can also check that a claimed
   uncertainty is *consistent with its own budget*.

Decisions already taken with the user: Python + browser UI; all four aspects
(recognition chains, CMC enforcement, traceability/uncertainty, failure demos);
presentation-grade polish for colleagues and the QI community; simplified readable
certificate payload (DCC alignment documented as an extension point, not built).

## Constraints

- All entities are fictional `.example` domains. No real METAS/BIPM/SAS branding claim,
  no customer data, no real certificate numbers. Demo keys are generated from a fixed
  seed and labelled as such in the UI and README.
- Metrology per GUM: `k=2` for reporting, no rounding of intermediates, terms used
  exactly (Standard Uncertainty `u`, Expanded Uncertainty `U`, Residual),
  `value ± U (k=2)` with units. `u_variable` prefix reserved for `metas_unclib` numbers.
- Python 3.10+, strict type hints, Google-style docstrings with units.

## Architecture

One FastAPI process simulating every actor, plus a no-build browser SPA
(plain ES modules, hand-written CSS — no npm, no bundler).

Already installed: `fastapi`, `uvicorn`, `cryptography`, `pydantic`, `jsonschema`,
`metas_unclib`. `rfc8785` and `base58` are **not** installed — implement both in-repo
(~120 lines total, fully unit-tested) rather than adding dependencies. New dev
dependency: `pytest`.

Proof format: **`DataIntegrityProof` / `ecdsa-jcs-2019`** (ECDSA P-256, RFC 8785 JSON
canonicalization). Same JSON shape as the spec examples, deterministic, no JSON-LD
processor and no network context fetching. `ARCHITECTURE.md` records this as a
deliberate simplification of `ecdsa-rdfc-2019`.

```
vc-qi-demo/
  pyproject.toml            README.md            ARCHITECTURE.md
  src/vcqi/
    config.py               # actor registry, DIDs, fixed demo seed, base URL
    crypto/  jcs.py  multibase.py  keys.py  dataintegrity.py
    vc/      model.py  issue.py  verify.py  recognition.py  status.py  schema.py
    domain/  kcdb.py  accreditation.py  uncertainty.py  instruments.py
    actors/  registry.py  scenarios.py  tamper.py
    web/     app.py  contexts/  static/{index.html,css/app.css,js/*}
  tests/
```

### Actors and DIDs (`did:web`, resolved against the local server)

| DID | Role |
| --- | --- |
| `did:web:bipm.example` | CIPM MRA root; publishes KCDB CMC entries and recognizes NMIs |
| `did:web:ilac.example` | ILAC MRA root; recognizes accreditation bodies |
| `did:web:metas.example` | NMI (Switzerland) — issues calibration certificates |
| `did:web:ptb.example` | Peer NMI — makes mutual recognition concrete |
| `did:web:sas.example` | Accreditation body — accredits labs and the CAB |
| `did:web:callab.example` | Accredited calibration laboratory (holder *and* issuer) |
| `did:web:testlab.example` | Testing laboratory — issues test reports |
| `did:web:cab.example` | Product certification body (ISO/IEC 17065) — the §2.4 CAB |
| `did:web:surveillance.example` | Market surveillance authority — the verifier persona |

Each actor serves a DID document and a `WhoisService`+`PathService` endpoint returning a
verifiable presentation of its own recognition credential, so **both** discovery
mechanisms in the spec are demonstrable.

### Credential types

- `RecognizedEntityCredential` — exactly the spec's shape. BIPM→METAS carries one
  `RecognizedAction` per CMC service category with `action: "issue"`, an
  `outputValidation` JSON Schema (with `digestMultibase`), and a domain extension
  `cmcReference` pointing at the KCDB entry. ILAC→SAS (`action: "accredit"`),
  SAS→CalLab / SAS→TestLab / SAS→CAB (`action: "issue"`, accreditation scope).
- `CalibrationCertificateCredential` — instrument, owner, measurand, calibration points
  (nominal, measured value, `U`, `k`, unit, conditions), `traceableTo` (parent credential
  id + digest), `cmcReference`, and `mraLogoAsserted` — the claim the verifier adjudicates.
- `TestReportCredential` — references the calibration certificate of the equipment used.
- `ProductConformityCredential` — the §2.4 leaf, references test reports.
- `BitstringStatusListCredential` — revocation and suspension for the failure demos.

### Verification engine (`vc/verify.py`)

One pipeline returning a `VerificationReport` — a tree of steps, each
`{id, title, status: pass|fail|warn|skip, detail, evidence}` that the UI renders directly.
Verification time, trust anchors, stapled documents and `maxDepth` are all caller-supplied
so the UI can vary them.

1. Shape / required VC 2.0 properties
2. Proof — JCS canonicalize, SHA-256, ECDSA P-256 verify, key resolved from the DID document
3. Validity period against the (adjustable) verification time
4. Status — fetch and verify the status list, read the bit
5. **Recognition discovery** — the spec's credential-based algorithm implemented step for
   step (`recognizedIn` → fetch → verify → confirm membership → repeat, with `maxDepth`
   and cycle detection), reporting every hop; identifier-based discovery via the whois
   endpoint as the fallback path
6. Action authorisation — the `RecognizedAction` really authorises `issue` for this
   credential type, and the action's own `validFrom`/`validUntil` cover the **issuance**
   date, not merely the verification date
7. `outputValidation` — check the schema's `digestMultibase`, then validate against it
8. **CMC adjudication** — fetch the KCDB entry; check measurand, range and conditions, and
   that `U_reported ≥ U_CMC(value)`. Verdict gates `mraLogoAsserted`. A pure JSON Schema
   cannot express the uncertainty floor formula — that limit is shown deliberately, as the
   reason a signed registry entry is needed alongside `outputValidation`.
9. Traceability — follow `traceableTo` to an NMI-issued certificate, verifying each link's
   digest and recursing through steps 1–8
10. **Uncertainty consistency** — recompute the claimed `U` from the declared budget with
    `metas_unclib` (parent certificate's `u` plus the lab's own contributions) and flag a
    claimed `U` smaller than its own budget allows

### Uncertainty (`domain/uncertainty.py`)

Worked chain on a 10 kΩ resistance standard: METAS (`U_rel ≈ 0.1 µΩ/Ω`) → CalLab transfer
standard → customer instrument (`U_rel ≈ 5 µΩ/Ω`) → test result. Propagated with
`metas_unclib` so the shared reference standard's correlation is handled correctly —
which is itself a good argument for carrying the budget, not just the number, in the
credential.

```python
u_variable_r_ref = ufloat(10000.0012, 0.0005)     # Ω, standard uncertainty u = U / k
u_variable_ratio = ufloat(1.0000031, 2.5e-6)      # dimensionless bridge ratio
u_variable_r_dut = u_variable_r_ref * u_variable_ratio
expanded_uncertainty = 2 * get_stdunc(u_variable_r_dut)   # Ω, k = 2
```

### Web UI — chapters

Left rail of chapters, main stage with an interactive trust-graph SVG plus a JSON inspector.

0. **What is a verifiable credential?** Issuer / Holder / Verifier triangle, with a live
   toy credential the visitor signs and verifies. Written for someone new to VCs.
1. **The quality infrastructure as a trust graph.** Click a node for its DID document and
   credentials; click an edge for the `RecognizedEntityCredential` behind it.
2. **Issuing a calibration certificate.** METAS → CalLab, step by step: payload →
   JCS canonical form → hash → signature → final VC. Every intermediate shown.
3. **Verification and recognition discovery.** The surveillance authority trusts only BIPM
   and ILAC, and walks up the chain; each hop and each step's verdict animated.
4. **CMC scope and the MRA logo.** Sliders for measured value and claimed `U`; live
   `within / outside declared CMC` verdict beside the KCDB entry; the MRA logo lights up
   or is struck through.
5. **Traceability and uncertainty.** SI → METAS → CalLab → TestLab, with the budget at each
   level and `U` visibly growing down the chain.
6. **Break it.** Tamper with a value, expire the accreditation, suspend a scope, claim an
   out-of-CMC measurand, forge an issuer DID, exceed `maxDepth`. Each shows precisely which
   step catches it.
7. **What this would mean in practice.** The written argument: what gets automated, what a
   real deployment needs (DID governance at BIPM/ILAC, KCDB as a signed registry, key
   management and long-term validation, DCC alignment, eIDAS 2.0 / EUDI wallet), and the
   honest open questions.

### API

`GET /` · `GET /api/world` · `GET /api/actor/{id}` · `GET /did/{domain}/did.json` ·
`GET /whois/{domain}` · `GET /api/credential/{id}` · `GET /kcdb/cmc/{id}` ·
`GET /schemas/{name}.json` · `GET /status/{id}` · `GET /contexts/vcqi/v1` ·
`POST /api/verify` · `POST /api/issue` · `POST /api/tamper` · `POST /api/uncertainty`

## Build order

This plan is copied to `D:\dev\verifiableCredentials\PLAN.md` as the first action, and the
checklist below is ticked off there as work lands — so the build can be interrupted and
resumed without losing the thread. Each phase ends in something runnable.

- [x] **P0 — Scaffold.** `PLAN.md`, `pyproject.toml`, package skeleton, `pytest` available.
- [x] **P1 — Crypto and VC core.** `jcs.py`, `multibase.py`, `keys.py`,
      `dataintegrity.py`, `vc/model.py`, `vc/issue.py`. RFC 8785 vectors pass;
      sign/verify round-trip passes.
- [x] **P2 — The world.** Actors, DID documents, KCDB CMC entries, accreditation scopes,
      status lists, `scenarios.py` building every credential from the fixed seed.
- [x] **P3 — Verification engine.** The ten steps, including recognition discovery and
      CMC adjudication.
- [x] **P4 — Web app.** FastAPI routes, SPA shell, trust graph, JSON inspector.
- [x] **P5 — Chapters 0–7.** Content, explanatory copy, styling, light/dark.
- [x] **P6 — Attack panel and docs.** `tamper.py`, `README.md`, `ARCHITECTURE.md`.

## Verification

- `uv run pytest` — RFC 8785 vectors; sign/verify round-trip; chain traversal including
  depth limit and cycles; CMC in-scope and out-of-scope cases; uncertainty propagation
  against hand-computed values; and a table-driven test asserting **every** tamper case is
  caught by the expected step id.
- `uv run vc-demo` → `http://localhost:8000`, then walk the chapters and confirm:
  chain reaches BIPM in 2 hops; an out-of-CMC value flips the MRA verdict; each break-it
  button fails exactly one step and only that step.
- `python -m vcqi.actors.scenarios --dump` writes every credential as JSON for inspection
  and diffing between runs (the fixed seed makes output stable).

## Git

The directory is not yet a repository. Proposed: `git init`, then work on
`feature/vc-qi-demo` from the start — nothing is ever committed to `main` or `develop`.
I will confirm with you before running `git init` or any commit.

## Not in scope

DCC (PTB/DKD) payload mapping, selective disclosure / SD-JWT, real DID registration,
production key management. Each is noted in `ARCHITECTURE.md` as an extension point.

## Progress log

All phases complete. 134 tests pass; the server runs; every chapter renders.

- **P0** uv project, package skeleton, PLAN.md copied into the repo.
- **P1** RFC 8785 canonicalizer, multibase/multikey, deterministic P-256 keys,
  RFC 6979 deterministic ECDSA, ecdsa-jcs-2019 Data Integrity proofs.
  Published RFC 8785 and RFC 6979 vectors both pass.
- **P2** 10 actors, 14 signed credentials, 52 published documents, KCDB CMC entries,
  accreditation scopes, generated outputValidation schemas, status lists.
  Build is byte-for-byte reproducible.
- **P3** The eleven-step verification pipeline, including the credential-based and
  identifier-based recognition discovery of the specification, CMC adjudication,
  traceability by content digest, and uncertainty consistency.
- **P4** FastAPI application, 10 routes, no-build browser front end.
- **P5** Eight chapters, trust-graph SVG, clickable JSON inspector, light and dark.
- **P6** Eleven failure cases, each caught by exactly the step it names.
  README.md and ARCHITECTURE.md written.

### Verified

- `uv run pytest` - 134 passed.
- `uv run vc-demo` - serves the page, assets and API on 127.0.0.1:8000.
- Every chapter rendered headlessly against the live server in a jsdom document with
  no console errors and no undefined or NaN in the output.
- `python -m vcqi.actors.scenarios --dump` run twice gives byte-identical output.
- The Product Conformity chain verifies end to end: a market surveillance authority
  trusting only BIPM and ILAC reaches a national measurement standard in 73 retrievals.

### Deviations from the plan

- Front-end source files were written with the editor tool rather than shell heredocs;
  heredocs were collapsing backslash escapes in prose-heavy source.
- `httpx2` added as a dev dependency so the API can be tested with Starlette's
  TestClient. `jsdom` was used for the headless UI check but installed outside the
  repository, so the project still has no npm dependency.
- Git was not initialised; see the Git section above. Nothing has been committed.

### Not done, and deliberately so

Selective disclosure, DCC payload mapping, long-term validation, key rotation, real DID
methods, wallet and presentation protocols. Each is recorded in ARCHITECTURE.md.

---

# Change set 2 - Global ACI, and transmitting metrological traceability

Phase 1 is built, tested and committed on `feature/vc-qi-demo` (48 files, 134 tests).
This plan covers two changes requested on top of it.

## Context

**A. ILAC no longer exists.** On 1 January 2026 the IAF and ILAC consolidated into a
single body, **Global Accreditation Cooperation Incorporated (Global ACI)**, whose
arrangement is the *Global ACI Multilateral Recognition Arrangement*. The demonstration
world is set in September 2026, so it should reflect that. This is a rename plus a
re-dating, not a structural change: Global ACI still accredits against ISO/IEC 17025 and
17065, so the accreditation scopes are untouched.

**B. The traceability chapter understates what is possible.** Right now a certificate
carries a value, an Expanded Uncertainty, and a budget rendered as a flat table. That is
the classical statement, and a receiving laboratory can only re-enter it as a single
lumped input.

METAS UncLib can transmit far more: the full dependency of the result on its input
quantities, with a sensitivity per input and — crucially — a **GUID per input quantity**.
When two certificates share an input quantity, the GUIDs match and correlations are
handled automatically. Verified against the installed library:

```
u(a − a₂) = 0.0            two independent loads of one certificate stay identical
r(R1, R2) = 0.667          two certificates sharing a transfer standard, correctly correlated
U(R1−R2) tracked = 0.00113 Ω
U(R1−R2) as RSS  = 0.00196 Ω    classical reporting overestimates by 1.7×
```

That last line is the argument. A customer who receives two certificates and forms a
difference gets a 1.7× too large uncertainty if all they were given was value ± U. The
information needed to do better exists at the laboratory and is simply not transmitted.

`metas_unclib.ustorage` already provides the transport: `to_xml_string` /
`from_xml_string` and `to_byte_array` / `from_byte_array`, the binary form being for
large data sets. A four-input budget is 972 characters of XML or 346 bytes binary. The
XML is exactly the structure being described:

```xml
<UncNumber>
  <Value>10000.0007</Value>
  <Dependencies>
    <DependsOn>
      <Input>
        <Id>BE-52-F0-9E-9F-A6-4F-BD-BF-67-5D-8C-C9-3D-B2-87</Id>
        <Description>National standard</Description>
        <Distribution xsi:type="Normal"><mu>10000.0007</mu><sigma>0.0003</sigma></Distribution>
      </Input>
      <Jacobi>1</Jacobi>
    </DependsOn>
```

**GTC** (GUM Tree Calculator, MSL New Zealand) solves the same problem independently:
elementary uncertain numbers carry UUID-based `eUID`s, archives serialise to JSON or XML
against published schemas. Two implementations of one idea is a better argument than one,
so the credential must be format-agnostic rather than UncLib-specific.

And **classical reporting stays**. It is what certificates say today, it is what remains
legally recognisable, and it is the only thing available when the issuer has no such tool.
It is always present; the dependency representations are additional.

Decisions taken with the user: GTC as an optional extra; dependency data inline when
small and referenced by digest when large; the correlation demonstration gets its own
chapter.

## A. Global ACI

Mechanical, 50 occurrences across 13 files.

- `did:web:ilac.example` → `did:web:global-aci.example`, in `actors/registry.py`
  (actor entry and `TRUST_ANCHORS`), `graph.js` (`POSITIONS`), and the tests.
- Name `ILAC` → `Global ACI`; legal name → *Global Accreditation Cooperation
  Incorporated (demonstration)*; role stays *Accreditation trust anchor*.
- URLs in `actors/scenarios.py`: `ILAC_RECOGNITION` →
  `https://global-aci.example/recognition/global-aci-mra-signatories-2026`,
  `ILAC_STATUS` → `https://global-aci.example/status/recognition`.
- Wording: *ILAC MRA* → *Global ACI MRA*, expanded as **Multilateral** Recognition
  Arrangement. The CIPM MRA stays **Mutual** — the distinction is real, keep it exact.
- **Re-date the recognition credentials.** Global ACI did not exist before 2026-01-01,
  so a recognition credential dated 2025 would be wrong, and the `action` step checks
  that a recognised action covers the *issuance* date of what it authorises. Move
  `RECOGNITION_FROM` to 2026-01-01 and `RECOGNITION_UNTIL` to 2031-01-01 for all three
  recognition credentials and the status lists. The underlying accreditations keep their
  own 2024 dates in `domain/accreditation.py`; only the recognition documents move.
- Add a short historical note in chapter 1 and in `README.md`: the consolidation is
  itself an argument, because a trust anchor changing its name and identifier is exactly
  the governance event a real deployment has to survive.

## B. Transmitting metrological traceability

### Credential shape

`credentialSubject.calibration.results[0]` gains `uncertaintyRepresentations`, an ordered
list. The classical statement is always first and always present.

```json
"uncertaintyRepresentations": [
  { "type": "ClassicalStatement", "format": "value-and-expanded-uncertainty",
    "value": 10000.0012, "standardUncertainty": 0.000566, "expandedUncertainty": 0.001131,
    "coverageFactor": 2, "unit": "ohm", "reported": "10000.0012 +/- 0.0011 ohm (k = 2)" },
  { "type": "DependencyRepresentation", "format": "METAS-UncLib-XML",
    "mediaType": "application/xml", "specification": "https://www.metas.ch/unclib",
    "inputQuantityCount": 4,
    "inputQuantities": [ { "id": "BE-52-...", "description": "National standard" }, ... ],
    "content": "<?xml version=...",
    "digestMultibase": "u..." },
  { "type": "DependencyRepresentation", "format": "METAS-UncLib-binary",
    "mediaType": "application/octet-stream",
    "id": "https://metas.example/certificates/METAS-2026-0417/uncertainty.unc",
    "byteCount": 346, "digestMultibase": "u..." },
  { "type": "DependencyRepresentation", "format": "GTC-archive-JSON", ... }   // when GTC installed
]
```

`digestMultibase` is over the **raw** dependency bytes (UTF-8 XML, or the binary blob),
not over a JSON wrapper, so the signature covers the actual data whether it is inline or
fetched. Inline below a `INLINE_LIMIT = 4096` character threshold, referenced above it;
the binary form is always referenced so both paths are exercised. `inputQuantities` lists
the GUIDs and descriptions so the identity mechanism is visible without parsing XML.

### Code changes

**`domain/uncertainty.py`** — the substantive one.

- `Contribution` gains an optional `uncertain_number` field. When set, `evaluate()` uses
  that object directly instead of building a fresh `ufloat`. This is what makes the GUIDs
  shared: the laboratory does not re-enter a number, it *continues* the parent's one.
- New constructor `from_certificate(key, label, unclib_xml, note)`, which deserialises
  with `mu.ustorage.from_xml_string` and hands the result to `Contribution`. Contrast it
  in the docstring with the existing `from_expanded_uncertainty`, which is the classical
  path and deliberately creates a *new* input quantity with a *new* GUID.
- `MeasurementResult` gains `uncertain_number: Any = None`, excluded from every JSON
  rendering, so the result can be serialised later.
- Budget rendering: in dependency mode the parent's input quantities appear as individual
  lines rather than one lumped row. Keep `get_unc_component(result, parent_object)` to
  also report the parent's total contribution, so both views are available.

**`vc/model.py`** — `uncertainty_representations(result, *, base_url, gtc_archive)`
building the list above; reuse `digest_multibase` from `crypto/multibase.py`.

**`vc/verify.py`** — three new child steps, all under the existing `uncertainty` and
`traceability` steps so the top-level step list stays at eleven:

| Step | Checks |
| --- | --- |
| `uncertainty.representations` | each representation's `digestMultibase` matches its inline content or the fetched document |
| `uncertainty.agreement` | where both a classical statement and a dependency representation exist, the value and u agree within tolerance — catches a certificate whose XML disagrees with its printed number |
| `traceability.shared-inputs` | the child's dependency representation contains the parent's input quantity GUIDs — a traceability proof independent of names and digests |

`traceability.inherited` stays, for the classical path where no dependency data exists.

**`actors/scenarios.py`** — the METAS certificate is issued with a dependency
representation; the CalLab certificate is built in *dependency mode*, loading the METAS
XML rather than re-entering U/k. Add the shared-reference pair: two 10 kΩ standards owned
by the testing laboratory, certificates `AC-2026-1190` and `AC-2026-1191`, both calibrated
against the same transfer standard, so chapter 6 has real documents to work with.

**`domain/gtc_archive.py`** (new, optional) — builds a GTC archive mirroring the same
budget, importing GTC lazily and returning `None` when it is absent. `pyproject.toml`
gains `[project.optional-dependencies] gtc = ["GTC>=1.5"]`; `uv sync --extra gtc` enables
it. Every GTC test is skipped when the import fails.

**`web/app.py`** — `GET /api/uncertainty-data?url=` serving referenced representations
with their real media type, and `POST /api/combine` for chapter 6, which takes two
certificate names and an operation and returns both the correlation-aware and the naive
RSS result.

### Chapters

Chapter 5 is reworked and a new chapter 6 inserted; Break it and the argument shift to 7
and 8.

**5. Traceability and uncertainty.** As now, plus a three-way tab on the certificate:
*classical* (value ± U, what a paper certificate says), *UncLib* (the XML, its input
quantities and GUIDs, the sensitivity per input), *GTC* (the archive, or a note that it
is not installed). The point made explicitly: all three describe the same measurement,
and only the last two let the recipient do anything further with it.

**6. Why the dependencies matter.** Two certificates, one shared transfer standard. The
reader picks an operation — difference, ratio, mean — and sees both answers side by side:
correlation-aware from the shared GUIDs, and naive RSS from value ± U alone. The 1.7×
overestimate is the headline. A second panel shows what happens if the laboratory had
reported classically: the customer *cannot* recover the correlation, at any effort, from
the numbers they were given.

Also worth stating plainly in this chapter: transmitting the dependency structure exposes
the internals of a laboratory's uncertainty budget, which some laboratories treat as
confidential. That is a genuine trade-off, not an oversight, and selective disclosure is
where it would be addressed.

## Files

```
src/vcqi/domain/uncertainty.py     Contribution.uncertain_number, from_certificate, budget expansion
src/vcqi/domain/gtc_archive.py     new, optional, lazily imported
src/vcqi/vc/model.py               uncertainty_representations()
src/vcqi/vc/verify.py              three new child steps
src/vcqi/actors/scenarios.py       Global ACI, re-dating, dependency mode, the resistor pair
src/vcqi/actors/registry.py        Global ACI actor and trust anchor
src/vcqi/actors/tamper.py          two new cases (below)
src/vcqi/web/app.py                /api/uncertainty-data, /api/combine
src/vcqi/web/static/js/chapters.js chapters 5 and 6
src/vcqi/web/static/js/graph.js    POSITIONS key rename
pyproject.toml                     [project.optional-dependencies] gtc
tests/, README.md, ARCHITECTURE.md
```

Two failure cases to add in `tamper.py`, both in the metrological group:

- **`dependency-disagrees`** — the UncLib XML is replaced with one stating a smaller
  uncertainty than the printed classical statement. Caught by `uncertainty.agreement`.
- **`unshared-inputs`** — the laboratory claims traceability to the institute but its
  dependency representation contains none of the institute's input quantity GUIDs, so the
  chain is asserted rather than real. Caught by `traceability.shared-inputs`.

## Verification

- `uv run pytest` — existing 134 plus roughly 20 new. Specifically: XML round-trip keeps
  GUID identity (`u(a − a₂) == 0`); a certificate built in dependency mode correlates with
  its parent while one built classically does not; the 1.7× figure is asserted against a
  hand-computed value; all 13 tamper cases caught by their named step.
- `uv sync --extra gtc && uv run pytest` — the GTC path exercised; without the extra those
  tests skip rather than fail.
- `uv run vc-demo`, then walk chapters 5 and 6 and confirm the three representations
  render and the two combination results differ by the stated factor.
- Headless render of every chapter against the live server, as before.
- `python -m vcqi.actors.scenarios --dump` twice, byte-identical. This needed resolving
  before the plan could stand, because UncLib assigns a fresh GUID to every input quantity
  by default and two runs would then differ. `ufloat` accepts an explicit `id`, and
  passing four little-endian uint32 words yields a clean 16 byte GUID:

  ```python
  raw = hashlib.sha256(DEMO_SEED + b"|" + label).digest()[:16]
  identifier = [int.from_bytes(raw[i : i + 4], "little") for i in range(0, 16, 4)]
  u_variable_x = mu.ufloat(value, stdunc, id=identifier, desc=label)
  # -> 10-FE-D3-10-7E-B3-4C-4D-67-C0-84-56-D3-81-39-61, stable across runs,
  #    and equal to uuid.UUID(bytes=raw) = 10fed310-7eb3-4c4d-67c0-8456d3813961
  ```

  Verified: two inputs built this way from the same label are treated as the *same* input
  quantity, `u(a − b) == 0`. A helper `seeded_input_id(label)` goes in
  `domain/uncertainty.py`, and `ARCHITECTURE.md` records that real deployments must let
  UncLib generate genuinely random GUIDs — seeding them is a reproducibility device for a
  demonstration, and would be a correctness bug in production, since two unrelated
  laboratories using the same label must not collide.

## Git

Continue on `feature/vc-qi-demo`. Two commits, so the rename stays separable from the
substantive work:

```
refactor(actors): replace ILAC with Global ACI
feat(uncertainty): transmit input dependencies to customers
```

Nothing pushed; no remote is configured yet.

---

## Change set 2 - build order

- [x] **A - Global ACI.** Rename ILAC to Global ACI across 13 files, re-date the
      recognition credentials to 2026-01-01, update graph positions and tests.
- [x] **B1 - Dependency-aware uncertainty.** `Contribution.uncertain_number`,
      `from_certificate()`, `seeded_input_id()`, `MeasurementResult.uncertain_number`.
- [x] **B2 - Credential transport.** `uncertainty_representations()` in `vc/model.py`,
      inline below 4096 characters and referenced by digest above it.
- [x] **B3 - Verification.** `uncertainty.representations`, `uncertainty.agreement`,
      `traceability.shared-inputs`.
- [x] **B4 - The world.** METAS certificate carries its dependencies; CalLab builds in
      dependency mode; add the shared-reference resistor pair.
- [x] **B5 - GTC.** Optional `domain/gtc_archive.py` and the `gtc` extra.
- [x] **B6 - Web.** `/api/uncertainty-data`, `/api/combine`, chapters 5 and 6.
- [x] **B7 - Failure cases and docs.** `dependency-disagrees`, `unshared-inputs`,
      README and ARCHITECTURE.

## Change set 2 - progress log

Complete. 176 tests pass, 1 skipped (GTC not installed). All nine chapters render.

- **A** ILAC replaced by Global ACI across 13 files; recognition credentials re-dated to
  2026-01-01 because Global ACI did not exist before that and the action step checks the
  issuance date. Committed separately as 244ee10.
- **B** Certificates now carry their uncertainty three ways: the classical statement
  (always), the METAS UncLib dependency structure as XML inline and binary by reference,
  and a GTC archive when the optional extra is installed.

### Two things the work itself corrected

- **Seeded identifiers collided.** Deriving them from the label alone made every budget
  saying "temperature correction" one shared influence, and unrelated results came out
  perfectly correlated (r = 1.0). Fixed by scoping identifiers to the certificate.
- **The first shared-reference pair was physically implausible.** Having the accredited
  laboratory calibrate both check standards produced certificates 36 times better than
  its accreditation allows, and the pipeline rejected them - correctly. Moved the pair to
  the institute, where two comparisons against one national standard give a real
  correlation of r = 0.69 and both certificates sit inside the published CMC.

### Verified

- `uv run pytest` - 176 passed, 1 skipped.
- Determinism survives: `--dump` twice gives byte-identical output across all 58
  documents, input quantity identifiers included.
- All 13 failure cases caught by the step each names.
- Every chapter renders headlessly against the live server with no console errors.
- The headline figures are asserted in tests: r = 0.69 between the paired certificates,
  classical reporting overstating their difference by 1.81x and understating their mean.

---

# Change set 4 - a chapter on public and private keys

## Context

The demonstration asserts the thing it never explains. Chapter 0 says a credential is
"a document with a digital signature over it, made with a key that its issuer
publishes", and chapter 2 shows what gets hashed and signed — but nothing says what a
key *is*, why one half signs and the other verifies, or how a verifier ends up holding
the right public key. A reader who is unsure about that is unsure about everything
downstream, because every later chapter rests on it.

The request is explicit that the concept itself is not fully clear, so this is a
teaching chapter first and a tour of the implementation second. It should confront the
confusions people actually have rather than restate the mechanism.

Four in particular:

- **Which half is secret.** For signatures the *private* key signs and the *public* key
  verifies. Many people arrive with the encryption intuition, where the public key
  encrypts and the private key decrypts, and quietly map it the wrong way round.
- **A credential is not secret.** Signing is not encryption. Anyone can read a
  calibration certificate; the signature says who made it and that it has not changed.
- **A valid signature proves almost nothing on its own.** Anyone can generate a keypair
  and sign anything at all. The signature only becomes meaningful once you know whose
  key it was, which is what identifiers and recognition are for.
- **A key is not an identity.** It is something an identifier publishes, for a stated
  purpose, and it can be replaced without the identifier changing.

The demonstration already enforces all of this in `vc/checks.py`; the chapter makes it
visible.

Decisions taken with the user: the chapter goes immediately after chapter 0; all four
interactive groups; show the one-way step mathematically; and wire the reader's own key
into the real pipeline.

## What the chapter contains

### 1. A private key is a number. The public key is computed from it.

A passphrase box, and a "give me a random one instead" button. Either way the result is
a private scalar `d`, and the public key is then computed **in front of the reader** as
`Q = d·G` by repeated point addition on the P-256 curve, using the code already in
`crypto/ecdsa_p256.py`.

```
private key   d = 0x7f3a9c2e…            just a number, 32 bytes
                    │  point multiplication
                    ▼
public key    Q = (x, y)                 a point on the curve
```

Then the encodings are peeled, which is what makes `publicKeyMultibase` stop looking
arbitrary: point → SEC1 compressed (33 bytes, `02`/`03` prefix) → multicodec prefix
`0x1200` for p256-pub → base58btc → `zDnae…`.

The passphrase path is deliberately reproducible, and the chapter says plainly why that
makes it a terrible way to make a real key: **type the same word, get the same key, and
so can anyone else.** The random button exists to show the contrast — press it twice,
get two different keys.

Two honest warnings belong here, not in a footnote: every key in this demonstration is
derived from a seed published in the repository and protects nothing, and the reader's
"private" key is handed back to the browser in plain sight, which is exactly what you
must never do with a real one.

### 2. Which half does what

A table that confronts the encryption confusion head on rather than hoping the reader
does not have it.

| | Signing — what credentials use | Encryption — a different job |
| --- | --- | --- |
| private key | **signs** | decrypts |
| public key | **verifies** | encrypts |
| kept secret by | the issuer | the recipient |
| what you get | authenticity and integrity | confidentiality |
| who can read the document | **anyone** | only the holder of the private key |

### 3. Sign something, then break it four ways

The reader types a message, signs it, and then four buttons each break it differently:
verify with the right key (passes), with a different key (fails), after changing one
character of the message (fails), after changing one character of the signature (fails).

The signature is 64 bytes whatever the message length, because what is signed is a
32-byte digest — which is also why chapter 3 has to canonicalize before hashing.

### 4. Anyone can sign. That is the point, and the problem.

Three certificates, all signed with the reader's own key, run through the demonstration's
**real** verification pipeline. The outcomes were checked while planning and are all
different, which is what makes the section worth building:

| What the reader does | `proof` | `recognition` | Why |
| --- | --- | --- | --- |
| Signs as themselves, `did:key:zDnae…` | **pass** | **fail** | the mathematics is perfect and nobody has heard of them |
| Claims to be METAS, names their own key | **fail** | pass | the key's controller is not the issuer the credential claims |
| Claims to be METAS *and* claims METAS's key identifier | **fail** | pass | the verifier resolves that identifier and gets METAS's real key |

The second row is the most instructive and was not obvious in advance: recognition
**passes**, because it checks the issuer the credential *claims* and METAS really is
recognised. Only `proof` binds that claim to a key. Two checks, two different questions,
and a forgery that would sail through either one alone.

This is where the chapter earns its place: it turns "a valid signature proves nothing on
its own" from a sentence into something the reader watched happen.

### 5. Where the public key actually lives, and what it is allowed to do

Follow `proof.verificationMethod` outward: `did:web:metas.example#issuance-key-1` →
controller `did:web:metas.example` → resolve → DID document → `verificationMethod` →
`publicKeyMultibase` → decode → the same 33 bytes from section 1.

Contrast the reader's `did:key:zDnae…`, where the identifier **is** the key and nothing
needs fetching — then say why the demonstration uses `did:web` for organisations anyway:
a `did:key` cannot rotate its key, and cannot be an organisation that a recognition
credential names.

Then purpose: a DID document lists keys under `assertionMethod` and `authentication`
separately, and `check_proof` already refuses a key that is published only for logging
in. Show the refusal.

Close on compromise: the day a private key leaks, everything it ever signed becomes
suspect and anyone can issue in that name. That is what key rotation and status lists
are for, and it is why the ARCHITECTURE note calls key management an unsolved part of
any real deployment.

## Code

### New endpoints in `web/app.py`

Every call carries the private scalar explicitly rather than the server holding state.
That is a deliberate teaching device: the private key really is just a number the caller
has, and seeing it travel makes the custody problem concrete.

| Route | Does |
| --- | --- |
| `POST /api/keys/derive` | passphrase or random → scalar, point, encodings, `did:key`, DID document |
| `POST /api/keys/sign` | scalar + message → digest, `r`, `s`, multibase signature |
| `POST /api/keys/verify` | message + signature + multikey → verdict and reason |
| `POST /api/keys/issue` | scalar + one of the three modes → the credential and its full report |

`/api/keys/sign` signs caller-supplied bytes with a caller-supplied key, so it is an
oracle for nothing but the caller's own key. Worth one line in ARCHITECTURE.md all the
same, next to the existing note that the server binds to localhost.

### Reused rather than rebuilt

- `crypto/ecdsa_p256.py` — `_scalar_multiply` and `P256`, promoted to a public
  `public_point(scalar)` so the chapter can show `Q = d·G` happening. Verified during
  planning to agree with `cryptography` for a known scalar.
- `crypto/keys.py` — `DemoKey` can be constructed directly from a raw scalar, so a
  reader-supplied key works everywhere an actor key does. `build_did_document`,
  `public_key_from_multikey`.
- `crypto/multibase.py` — `encode_p256_multikey`, `base58btc_decode` for peeling.
- `crypto/dataintegrity.py` — `sign_document` for the three certificates.
- `vc/verify.py` — `verify_credential` unchanged; the three modes are ordinary
  credentials through the ordinary pipeline.

### One small addition: `did:key` resolution

`vc/resolver.py` gains a branch in `resolve_public_key` and `assertion_methods`: when a
controller starts with `did:key:`, build the verification method from the identifier
itself instead of fetching. Around ten lines, it removes the need to publish a
throwaway DID document for the reader, and it is the honest implementation of what
`did:key` means — which the chapter then uses to contrast the two methods.

### Chapter registration

`chapters.js` gains `chapterKeys` registered at index 1, id `keys`, title *Keys: what a
signature actually proves*. Everything after it shifts down one; the ids are stable
strings so no links break. `ui.js` may need one small helper for the peeling panel;
otherwise `panel`, `table`, `keyValues`, `stepTree` and `verdictBanner` already cover it.

## Files

```
src/vcqi/crypto/ecdsa_p256.py       public_point()
src/vcqi/vc/resolver.py             did:key resolution
src/vcqi/web/app.py                 four /api/keys routes
src/vcqi/web/static/js/api.js       the four calls
src/vcqi/web/static/js/chapters.js  chapterKeys, registered at index 1
src/vcqi/web/static/css/app.css     only if the peeling panel needs it
tests/test_keys.py                  new
tests/test_web.py                   the four routes
README.md, ARCHITECTURE.md
```

## Verification

- `uv run pytest` — 176 existing plus roughly 20 new. Specifically: `public_point` agrees
  with `cryptography` across several scalars including 1 and n−1; a passphrase gives the
  same key twice and different passphrases differ; two random keys differ; multikey and
  `did:key` round-trip to the same public numbers; each of the four break-it cases fails
  for the reason claimed; and the three issue modes produce the three step outcomes in
  the table above, asserted by step id rather than by wording.
- `uv run vc-demo`, then walk chapter 1: derive a key, sign, break it four ways, run all
  three impostor modes, and follow the encoding chain from `publicKeyMultibase` back to
  the point.
- `node tools/ui-clicks.mjs` — **this matters here.** The last chapter added had dead
  buttons that the Python suite could not see. That harness lives on the archived
  `feature/legal-metrology` branch; cherry-pick it onto this branch first, since a
  chapter this interactive is exactly what it exists to check.
- Chapter renumbering: confirm the rail reads 0 to 9 and that every chapter still renders.

## Git

Branch from `develop`:

```
git switch -c feature/keys-chapter develop
```

Two commits: the crypto and API surface, then the chapter itself. Nothing pushed without
asking.

## Change set 4 - build order

- [x] **K1 - Crypto surface.** `public_point()` in ecdsa_p256; `did:key` resolution in
      the resolver.
- [x] **K2 - API.** The four /api/keys routes.
- [x] **K3 - Chapter.** chapterKeys at index 1, five sections, renumbering.
- [x] **K4 - Tests and docs.** tests/test_keys.py, the routes in test_web.py, README and
      ARCHITECTURE.
- [x] **K5 - Interaction check.** `node tools/ui-clicks.mjs` against the live server.

## Change set 4 - progress log

Complete. 213 tests pass, 1 skipped (GTC). Ten chapters render, every control responds.

- `public_point()` exposes the point multiplication, checked against `cryptography` at
  d = 1, 2, 3, n-1 and an arbitrary scalar, and the result is confirmed to lie on the
  curve.
- The resolver understands `did:key`, which resolves with no retrieval at all and gives
  the chapter its contrast with `did:web`.
- Four `/api/keys/*` routes. The private key travels in the request on purpose;
  ARCHITECTURE.md records why that is safe here and would not be anywhere else.
- The chapter derives a key, computes the public one in front of the reader, peels four
  encodings down to `publicKeyMultibase`, signs and breaks a message four ways, and runs
  three forgery attempts through the real pipeline.

### The three forgery attempts, all confirmed by test

| Attempt | proof | recognition | first failure |
| --- | --- | --- | --- |
| Sign as yourself | pass | fail | no route to a trusted identifier |
| Claim to be METAS, own key named | fail | pass | key controller is not the issuer |
| Claim METAS and its key id | fail | pass | signature does not verify |

The middle row is the one worth having built the chapter for: recognition **passes**,
because it checks the issuer the credential names and METAS really is recognised. Only
proof binds the claim to a key. Either check alone would let the forgery through.

### Two things the click harness caught

- The **dependencies** chapter had dead certificate chips on `develop`. The inspector fix
  had been made on the archived legal-metrology branch and only `tools/ui-clicks.mjs` was
  cherry-picked, so the bug came straight back the moment a chapter was added. Fixed on
  the main line this time.
- Pressing **Derive** twice with the same passphrase changed nothing on screen, which
  looked broken and is in fact the lesson. It now says so explicitly instead.

---

# Change set 5 - the PTB/DKD DCC as a carrier

## Context

Chapter 6 shows one measurement carried three ways: the classical `value ± U (k = 2)`,
the METAS UncLib dependency structure, and a GTC archive. All three answer the same
question — how do you transmit an uncertainty so the recipient can use it.

The **PTB/DKD DCC** answers a different one, and that difference is the most useful thing
the addition brings. It is not a way of expressing an uncertainty; it is a standardised
way of expressing an entire calibration certificate — who calibrated what, when, for
whom, under which conditions, with which equipment, and what came out. The uncertainty
inside it is expressed in **D-SI**, and D-SI's `si:expandedUnc` carries a value, an
uncertainty, a coverage factor and a coverage probability. That is the classical
statement. It is not the dependency structure.

So the four carriers are not four alternatives. They stack:

| Carrier | Answers | Level |
| --- | --- | --- |
| Classical `value ± U` | how good is this number | a result |
| METAS UncLib | what does it depend on | a result |
| GTC archive | the same, independently | a result |
| **PTB/DKD DCC** | what is the whole certificate | **a document** |

A PTB/DKD DCC and an UncLib block are not competing; a certificate can carry both, the
DCC standardising the document and the dependency representation supplying what D-SI does
not model. Chapter 6 currently implies the three carriers are alternatives, and adding
the fourth is what makes the levels visible.

ARCHITECTURE.md already calls DCC alignment "the obvious next step". This does a
deliberately partial version of it and says exactly how partial.

**Naming.** Other DCCs exist. Every mention in code, prose and documentation says
**PTB/DKD DCC**, and existing bare "DCC" mentions get normalised.

Decisions taken with the user: a schema-shaped subset, carried alongside the readable
subject rather than replacing it, with the `ds:Signature` slot left empty and discussed,
and the agreement check extended to read it.

## The document

Real namespaces and real element names, in the real nesting, carrying only what this
demonstration has data for — and labelled a subset rather than a conformant document.

- DCC **3.3.0**, namespace `https://ptb.de/dcc`
- D-SI **2.2.1**, namespace `https://ptb.de/si`

```
dcc:digitalCalibrationCertificate
├── dcc:administrativeData
│   ├── dcc:coreData        countryCodeISO3166_1, usedLangCodeISO639_1,
│   │                       mandatoryLangCodeISO639_1, uniqueIdentifier,
│   │                       beginPerformanceDate, endPerformanceDate,
│   │                       performanceLocation, issueDate
│   ├── dcc:items           the instrument: name, manufacturer, model, identifications
│   ├── dcc:calibrationLaboratory   the issuer
│   └── dcc:customer        the owner
├── dcc:measurementResults
│   └── dcc:measurementResult
│       ├── dcc:usedMethods           the measurand and the method
│       ├── dcc:measuringEquipments   the reference standard, by certificate
│       ├── dcc:influenceConditions   the stated conditions
│       └── dcc:results/dcc:result/dcc:data/dcc:list/dcc:quantity
│           └── si:real   si:value, si:unit, si:expandedUnc
│                                  └── si:uncertainty, si:coverageFactor,
│                                      si:coverageProbability
└── (dcc:comment, dcc:document, ds:Signature — deliberately absent)
```

**Units are D-SI, not our symbols.** D-SI writes units siunitx-style with backslashed
English names, so `ohm` becomes `\ohm` and — the one that catches people — `kg` becomes
`\kilo\gram`, not `\kilogram`, because the prefix is its own token. A small explicit
mapping covers the units this world uses and **raises** on anything unmapped, so the
demonstration can never quietly emit a wrong unit.

## Redundancy: two copies of nearly everything

Wrapping a PTB/DKD DCC in a verifiable credential duplicates most of the certificate,
and this is the part of the exercise most worth being explicit about. It is not a flaw
in either format — each was designed to stand alone — but putting one inside the other
makes the overlap unavoidable.

| Fact | In the credential | In the PTB/DKD DCC |
| --- | --- | --- |
| who calibrated | `issuer.id`, `issuer.name` | `dcc:calibrationLaboratory` |
| for whom | `credentialSubject.owner` | `dcc:customer` |
| certificate number | `id`, `calibration.certificateNumber` | `dcc:coreData/dcc:uniqueIdentifier` |
| when | `validFrom`, `calibration.performedOn` | `dcc:beginPerformanceDate`, `dcc:endPerformanceDate`, `dcc:issueDate` |
| the instrument | `credentialSubject` | `dcc:items` |
| the result | `calibration.results[0]` | `si:real` |
| **integrity** | `proof` | `ds:Signature` |

**Duplication permits disagreement.** The signature stops anyone editing either copy
after issue; it does nothing about an issuer emitting them inconsistent in the first
place. Two copies of a fact inside one signed document are one copy too many unless
something reads both.

### The signatures in particular

The DCC's `ds:Signature` and the credential's `proof` are two integrity mechanisms over
overlapping content, and they do not merely repeat each other — they differ at every
layer that matters:

| | credential `proof` | `ds:Signature` in a DCC |
| --- | --- | --- |
| canonicalization | RFC 8785 over the credential | XML C14N over the document |
| key discovery | resolve the issuer identifier | an X.509 certificate chain |
| revocation | status list | CRL or OCSP |
| what it covers | the credential, including a digest of the DCC | the DCC only |

A document carrying both can verify under one and fail under the other, and there is no
natural rule for which wins. So this demonstration signs once: the credential proof
covers the credential, the credential carries a digest of the DCC bytes, the
`ds:Signature` slot stays empty, and there is exactly one trust path. That is a choice,
not an obligation, and the chapter says so.

### Three ways to live with the rest

Worth naming all three, because the demonstration only implements one and the other two
are not worse:

1. **Duplicate and check** — what this does. Every duplicated fact becomes a place the
   verifier can catch an inconsistency, which turns a liability into an asset. Cheap,
   and it is why the pipeline gains a duplication check rather than only a numeric one.
2. **Do not duplicate** — make the DCC the credential subject and let `issuer` and
   `validFrom` be derived views of it. Cleanest, and probably what a real deployment
   settles on. It changes every chapter here, which is why it is described rather than
   built.
3. **Duplicate and declare precedence** — state in the credential which copy governs.
   It works, it needs governance, and nobody reads the rule at the moment they need it.

## Code

### `src/vcqi/domain/dcc.py` (new)

- `DSI_UNITS` — the mapping, with the `\kilo\gram` subtlety commented where someone
  will actually read it.
- `to_dcc_xml(result, *, certificate, instrument, issuer, owner, conditions, measurand,
  reference)` — builds the document with `xml.etree.ElementTree`, which is already a
  dependency of `domain/uncertainty.py`.
- `parse_dcc_result(xml)` — reads `si:value`, `si:unit`, `si:uncertainty` and
  `si:coverageFactor` back out. Used by the verifier, and written with a plain XML parser
  so the check does not depend on the tool that wrote the document.

### `src/vcqi/vc/model.py`

`uncertainty_representations()` gains a `dcc_xml` parameter and emits a fifth entry with
`type: "CertificateRepresentation"` and `format: "PTB-DKD-DCC-XML"`. It goes inline like
the UncLib XML, since a one-result DCC is a couple of kilobytes, and carries a
`digestMultibase` over the raw bytes exactly like every other entry.

The member is still called `uncertaintyRepresentations`, which is now slightly narrow for
what it holds. Renaming it would change every signed credential and both generated
schemas for a cosmetic gain, so the name stays and `type` carries the distinction —
recorded in ARCHITECTURE.md rather than left as a puzzle.

### `src/vcqi/vc/verify.py`

`_step_representations` already digest-checks anything it does not recognise, so the DCC
is covered from the moment it exists. Two changes make it *read*:

- pick up `PTB-DKD-DCC-XML`, parse it, and keep the value and Expanded Uncertainty;
- `_step_agreement` compares **three** sources rather than two — the printed line, the
  dependency representation, and the DCC — and reports which one disagrees.

The DCC states an *Expanded* uncertainty with its coverage factor, so the comparison
divides by `si:coverageFactor` before comparing with the printed `u`. Getting that
backwards would be exactly the kind of error the check exists to catch, so the test
asserts it both ways.

A third child, **`uncertainty.duplication`**, reads the facts the two carriers state
twice — the certificate number, the calibrating laboratory, the customer and the
performance dates — and confirms they agree. This is what turns the redundancy above
from a liability into something useful: every duplicated field becomes a place an
inconsistent issuer gets caught.

Two naming compromises come out of this change, and they are better recorded than
rediscovered. The member is still `uncertaintyRepresentations` and the step is still
`uncertainty`, both of which are now narrower than what they hold. Renaming the member
would change every signed credential and both generated schemas; renaming the step would
break ids that the tests and the interface refer to. So the names stay, the `type` and
the step ids carry the meaning, and ARCHITECTURE.md says so in one place rather than
leaving two puzzles.

### `src/vcqi/actors/tamper.py`

Two new metrological cases, both signed correctly with matching digests:

- **`dcc-disagrees`** — the DCC states a different measured value from the printed line.
  Caught by `uncertainty.agreement`.
- **`dcc-names-another-laboratory`** — the DCC's `dcc:calibrationLaboratory` names a
  different body from the credential's `issuer`. Every signature and digest is intact,
  and the document contradicts itself about who performed the calibration. Caught by
  `uncertainty.duplication`, and it exists precisely because that failure is invisible
  without a check that reads both copies.

Fifteen cases total.

## Chapters

### Chapter 6 — a fourth tab

`representationPanel` gains **PTB/DKD DCC** beside Classical, METAS UncLib and GTC. It
shows the generated document, a table mapping our fields onto the DCC and D-SI elements
they become, and makes the level distinction explicit: the first three carry a *result*,
this one carries a *document*, and they compose rather than compete.

A second panel, **What is now said twice**, renders the redundancy table against the
actual documents: each duplicated fact with the credential's value beside the DCC's, and
a badge where the verifier compared them. It ends on the signature comparison — two
mechanisms, different canonicalization, different key discovery, different revocation —
and states plainly that the demonstration signs once and covers the DCC by digest, that
this is a choice rather than an obligation, and that using both needs a precedence rule
which is governance rather than engineering.

### Chapter 9 — rewrite the alignment paragraph

It currently says carrying a PTB/DKD DCC as the credential subject is the obvious next
step. Part of that is now demonstrated, so the text should say what is real and what is
not: the document is a subset, it is not validated against the published XSD, the
`ds:Signature` slot is unused, D-SI does not model dependency structure so UncLib or GTC
still has to ride alongside, and the credential subject is still the readable shape rather
than the DCC itself.

It should also gain what the redundancy actually taught, because it is the more
transferable lesson: wrapping an existing standardised document in a credential
duplicates most of it, including its integrity mechanism, and a real deployment has to
decide deliberately between duplicating and checking, not duplicating at all, or
declaring precedence. This demonstration duplicates and checks because that is the
cheapest thing to show; the version worth building is probably the second.

## Files

```
src/vcqi/domain/dcc.py              new
src/vcqi/vc/model.py                the fifth representation
src/vcqi/vc/verify.py               read the DCC, three-way agreement
src/vcqi/actors/scenarios.py        generate it for both calibration certificates
src/vcqi/actors/tamper.py           dcc-disagrees
src/vcqi/web/static/js/chapters.js  chapter 6 tab, chapter 9 paragraph
tests/test_dcc.py                   new
README.md, ARCHITECTURE.md          normalise naming, record the compromises
```

Reused unchanged: `uncertainty_representations` digest and inline handling,
`_step_representations`, `credential_reference`, the scenario wiring that already passes
`gtc_archive` through.

## Verification

- `uv run pytest` — 213 existing plus roughly 20 new. Specifically: `\ohm` and
  `\kilo\gram` are produced and an unmapped unit raises; the generated document parses,
  declares both namespaces and the right schema version, and has the full element path
  down to `si:real`; `parse_dcc_result` round-trips the value, unit, `U` and `k`; the
  agreement check passes for both real certificates and fails when the DCC is altered;
  and `si:coverageFactor` is applied in the right direction.
- The duplication check: every field the two carriers state twice agrees for the real
  certificates, and altering any one of them in the DCC alone is caught while every
  signature and digest stays valid.
- All 15 failure cases caught by the step each names.
- `uv run vc-demo`, then chapter 6, all four tabs and the duplication panel.
- `node tools/ui-clicks.mjs` — the tool is on `develop` now, so run it directly.
- `python -m vcqi.actors.scenarios --dump` twice, byte-identical.

## Git

Branch from `develop`:

```
git switch -c feature/ptb-dkd-dcc develop
```

One commit. Nothing pushed without asking.

**Note on line endings.** The repository has drifted into mixed CRLF and LF, which
inflates every diff. It is unrelated to this change and still outstanding; the offer to
normalise it with a `.gitattributes` stands, and is best done as its own commit rather
than folded into this one.

## Change set 5 - build order

- [x] **D1 - The document.** `domain/dcc.py`: D-SI units, to_dcc_xml, parse_dcc_result.
- [x] **D2 - Carried.** The fifth representation in `vc/model.py`, generated in
      `scenarios.py` for both calibration certificates.
- [x] **D3 - Read.** Three-way agreement and the duplication check in `vc/verify.py`.
- [x] **D4 - Broken.** `dcc-disagrees` and `dcc-names-another-laboratory`.
- [x] **D5 - Shown.** Chapter 6 fourth tab and the duplication panel; chapter 9 rewrite.
- [x] **D6 - Tests and docs.** `tests/test_dcc.py`, naming normalised to PTB/DKD DCC.

## Change set 5 - progress log

Complete. 253 tests pass, 1 skipped (GTC). Ten chapters render, every control responds,
the world still builds byte-identically.

- `domain/dcc.py` generates a PTB/DKD DCC 3.3.0 with quantities in D-SI 2.2.1, using the
  real namespaces, element names and nesting. Every calibration certificate carries one.
- Both transport paths fall out naturally: the institute's document is 3639 characters
  and travels inline, the laboratory's is 4292 and is published separately.
- `uncertainty.agreement` now compares three carriers instead of two, dividing the DCC's
  Expanded Uncertainty by its coverage factor first.
- `uncertainty.duplication` compares the six facts the credential and the DCC both state.

### What the redundancy is, concretely

Six facts said twice, plus the integrity mechanism. The check found them all agreeing on
the real certificates, and the two new failure cases show what happens when they do not:
`dcc-disagrees` and `dcc-names-another-laboratory` both keep every signature and digest
valid and are caught only because something reads both copies.

### D-SI units

Written siunitx-style with backslashed English names. Ohm is `\ohm`; kilogram is
`\kilo\gram` and not `\kilogram`, because the prefix is its own token. `dsi_unit()`
raises on an unmapped unit rather than guessing, and there is a test for the kilogram
specifically.

### One test was wrong, not the code

`test_the_duplication_check_is_skipped_without_a_dcc` searched the whole report tree and
found the duplication step belonging to the calibration certificate that the test report
follows its traceability into. Scoped to the top level.

# Change set 6 - what it takes to run, and what would have to be agreed

## Context

Two chapters, built on one branch, answering the two halves of "could this actually be
deployed". Chapter 10 answers what one organisation would have to **run**; chapter 11
answers what organisations would have to **agree with each other**.

Chapter 10 landed on this branch before the plan existed, in answer to a question about
what IT infrastructure BIPM, METAS or a small calibration laboratory would need. It is
recorded here so the branch has one account of itself.

Chapter 11 was planned. A structural review argued the harmonisation material did not
belong inside chapter 10 — chapter 10's lede is the hosting burden, and merging the two
would bury the second argument under the first — so it became its own chapter.

## What chapter 10 established

The hosting burden is computed from what the demonstration actually published, not
asserted. Two properties do the work: verification is a computation rather than a
conversation, so an issuer runs no service on a verifier's behalf; and a credential
travels with whoever holds it, so an issuer hosts only what describes the issuer itself.

METAS keeps three documents online while having issued four credentials and six that
travel unhosted. The first figure does not grow with the second. BIPM's burden is eight
and is dominated by the registry, not by signing. A pure verifier operates nothing.

A real verification of the conformity certificate reports 31 distinct documents across 7
hosts and no accounts at any of them — alongside 76 uncached retrievals, quoted rather
than dropped, because this resolver refetches DID documents at every hop.

## What chapter 11 argues

Three tiers, read in order rather than filtered, because the ordering is the claim.

**Tier 1, minimum to interoperate:** one cryptosuite profile; one identifier method and
an agreed meaning for resolution; how a chain crosses between the two arrangements; what
a status value means institutionally rather than how it is encoded; trust anchor
identifiers and their distribution; unit identifiers.

**Tier 2, must be decided now though not yet needed:** whose timestamps are mutually
accepted; which copy governs, the certificate document or the credential; persistence
commitments on identifiers.

**Tier 3, nice to have:** a digital representation of SI quantities settled between the
existing candidates; a machine-readable certificate format with international standing;
measurand identifiers; registered uncertainty-transport identifiers including dependency
structure.

Every item has to pass one discriminator: *two conforming implementations that differ
here cannot interoperate*. Anything failing it is a deployment gap and belongs in chapter
9, which already covers identifier governance, the signed KCDB, long-term validation and
selective disclosure. Chapter 11 asks the different question of who would have to agree,
and in which forum.

### The correction that shaped it

A first draft assumed the metrology vocabularies were missing and treated the PTB/DKD DCC
and D-SI as the presumptive global formats. Both were wrong.

The DCC and D-SI are German constructions, from the PTB and the DKD. Their maturity does
not settle their global standing, and a national construction seeking worldwide adoption
is a governance question rather than a technical one.

BIPM already runs the SI Digital Framework, publishing permanent digital identifiers for
SI units, prefixes and defining constants, backed by RDF knowledge bases. The ohm
resolves at `https://si-digital-framework.org/SI/units/ohm` with its symbol, its quantity
and the CGPM resolution that defined it. Resolvable CMC identifiers already exist through
the KCDB-CMC service. Digital identifiers for measurands are in progress at ISO and IEC.

So the finding is not that no vocabulary exists. It is that one exists, BIPM publishes it,
and this demonstration did not use it.

### The evidence in the code

`domain/scope.py:229` decides whether a calibration may carry the CIPM MRA logo with
`claim.measurand == capability.measurand` — exact string equality on free text. The CMC in
`domain/kcdb.py` and the accreditation scope in `domain/accreditation.py` both say
`dc.resistance`, and they match only because one author wrote both files. Chapter 5 rests
on a vocabulary agreement the demonstration manufactured for itself.

There is a connection worth drawing: BIPM's identifiers are RDF, so adopting them makes
JSON-LD semantics load-bearing, and `ARCHITECTURE.md`'s note that a real deployment needs
`ecdsa-rdfc-2019` or an equivalent stops being academic. The cryptosuite choice and the
vocabulary choice are the same decision.

## Files

- `src/vcqi/actors/deployment.py` - deployment profiles and `hosting_burden`.
- `src/vcqi/actors/harmonisation.py` - harmonisation items and the next-step ladder.
- `src/vcqi/web/app.py` - `/api/infrastructure` and `/api/harmonisation`.
- `src/vcqi/web/static/js/chapters.js` - chapters 10 and 11.
- `src/vcqi/web/static/js/api.js`, `static/css/app.css` - one call, one `.checklist` rule.
- `tests/test_deployment.py`, `tests/test_harmonisation.py`, `tests/test_web.py`.

## Verification

`uv run pytest`, then `node tools/ui-clicks.mjs` against a running server. The click
harness is the one that matters: it exists because a chapter once rendered buttons that
did nothing.

Not verified visually. The Chrome extension was declined during the session, so the
layout of the new panels has not been seen in a browser.

## Git

Branch `feature/infrastructure-chapter`, from `develop`. Nothing pushed without asking.

**Line endings.** Still mixed across the repository, and `chore/normalise-line-endings` is
still unmerged. Files touched here were rewritten to match whatever `develop` holds for
each, so the diffs stay reviewable; new files are LF.

## Change set 6 - build order

- [x] **E1 - Roles.** `actors/deployment.py`: profiles and the computed hosting burden.
- [x] **E2 - Endpoint.** `/api/infrastructure`, with a real verification's retrieval log.
- [x] **E3 - Chapter 10.** The role picker and the six panels behind it.
- [x] **E4 - Tests for 10.** `tests/test_deployment.py` and four in `tests/test_web.py`.
- [x] **E5 - Items.** `actors/harmonisation.py`: the three tiers and the step ladder.
- [x] **E6 - Endpoint.** `/api/harmonisation`.
- [x] **E7 - Chapter 11.** Three stacked tier panels, the ladder, the disclaimer.
- [x] **E8 - Stitching.** Chapter 10's bridging sentence; move chapter 9's stranded
      closing footnote to the end of chapter 11, which is now last.
- [x] **E9 - Tests and docs.** `tests/test_harmonisation.py`, the measurand-coincidence
      regression test, `README.md`.

## Change set 6 - progress log

Chapter 10 complete before this plan existed: 261 tests pass, 1 skipped (GTC), every
control responds across eleven chapters.

- `actors/deployment.py` holds four editorial role profiles and `hosting_burden`, which
  splits what an organisation publishes into what must stay online and what travels with
  its holders. The profiles are an argument; the counts beside them are computed.
- `/api/infrastructure` joins the two and adds a real verification of the conformity
  certificate, reporting distinct documents, hosts and the uncached retrieval count.
- Chapter 10 renders a four-role picker over that data. Twelve controls, all responding.
- The module was first written under `domain/` and moved to `actors/`: `ARCHITECTURE.md`
  reserves `domain/` for code with no credential knowledge, and document kinds like
  `did-document` and `status-list` are credential concepts.
- Trimmed before landing: `profile_for` was never called, and four response fields were
  unused by both the chapter and the tests.

Chapter 11 complete. 272 tests pass, 1 skipped. Twelve chapters render and every control
responds; chapter 10 still reports twelve controls and chapter 11 two.

- `actors/harmonisation.py` holds thirteen items across three tiers and a six-rung ladder.
  Items are editorial; what is enforced is that the two halves agree — every step advances
  an item that exists, and every first-tier item is reached by some step.
- The one sentence that could rot quietly interpolates `CRYPTOSUITE` rather than repeating
  it, and a test asserts the served text still contains it. `MINIMUM_LIST_LENGTH` was
  deliberately left out of that treatment: it is a spec-mandated floor the constructor
  rejects below, so presenting it as a choice would have asserted a decision nobody made.
- `tests/test_harmonisation.py` turns the chapter's central claim into a regression test:
  the CMC and the accreditation scope are published by different organisations and agree
  on `dc.resistance` only because one author wrote both files, which is exactly what
  `domain/scope.py` compares with `==`.
- Two stitching fixes: chapter 10 now bridges into 11, and chapter 9's closing footnote —
  stranded mid-book when chapter 10 was added — moved to the end of chapter 11, extended
  to cover the real organisations chapter 11 names.
- Not verified visually. The Chrome extension was declined, so the layout of the new
  panels has not been seen in a browser. Structure was checked in jsdom instead: flat
  panels, no nesting, no stray nulls, and tier headings at 15px above 13.5px panel titles.

# Change set 7 - publish it on the web, and make its text editable

## Context

The demonstrator runs only as a local process. Showing it to a delegate, a colleague at
another NMI or an accreditation body means asking them to install Python and `uv` first,
and on many managed machines running an unsigned executable is prohibited outright. The
demonstration argues that a verifier "operates nothing"; the demonstrator itself should
ask no more of its reader than a URL.

Four things follow, in this order:

1. Get UncLib off the server.
2. Host it behind a registered domain, driveable from a browser and a `git push` — the
   METAS machine cannot install Docker, `gh` or a host CLI.
3. Make it safe to expose. `ARCHITECTURE.md` rested the safety argument for
   `/api/keys/*` on binding to localhost, which hosting makes false.
4. Move the chapter prose out of `chapters.js` into markdown an editor can change, and
   publish `README.md`, `ARCHITECTURE.md` and `LEGAL-METROLOGY.md` on the site.

Decisions taken up front: markdown edited in the GitHub web UI on a feature branch and
merged by PR, no live-site editing; the site unlisted, `noindex`, no password; and only
those three documents published, not `PLAN.md` or `firstPrompt.md`.

## Why item 1 turned out to be first

The plan assumed the problem was running `metas_unclib` on Linux under Mono, and it
probably would have worked — the shipped `Metas.IntelMKL.dll.config` carries Mono
`<dllmap>` entries pointing at `mkl_custom/linux/intel64/*.so`, which is the vendor
saying Mono is the supported Linux runtime.

The licence is what does not work. The METAS UncLib EULA grants a designated-computer
licence and §4c prohibits distribution to third parties "whether modified, incorporated
into a software package, incorporated into any kind of device or machine, reproduced or
left in its original form". A container image on a hosting provider is three of those at
once. METAS is the licensor and permission is obtainable internally, but the deployment
should not depend on that conversation, and it does not need to.

Asking the question first, rather than after building the Mono image, was luck: the
question was asked as "could this be simplified by faking UncLib?"

## Build order

- [x] `feature/linprop` — the engine, the blobs, the equivalence tests, CI
- [x] `feature/hosting` — config, hardening, Dockerfile, domain, doc updates
- [x] `feature/content-layer` — loader, `/api/content`, `content.js`, tests, editor README,
      plus the chapter 0 pilot and the snapshot tool (merged: a mechanism with no consumer
      cannot be reviewed, so the pilot landed with it)
- [ ] `feature/content-chapters-*` — the remaining eleven chapters, one commit each
- [ ] `feature/docs-viewer` — the three repository documents on the site

## Progress log

`feature/linprop` complete. 332 tests pass with UncLib installed (2 skipped), 288 pass
without it (46 skipped, all of them the ones that need both engines to compare).

- `domain/linprop.py` implements what the project uses and nothing more: real scalars,
  the four operations, sensitivity vectors keyed on input identity. The subset is the
  point — it is small enough that the equivalence claim is checkable rather than hoped
  for. Every measurement model here is a sum of products, so first-order propagation is
  exact, not approximate.
- `domain/engine.py` chooses. `VCQI_ENGINE=linprop` forces the deployed engine on a
  licensed machine, which is how the two are compared. Two import lines were the whole
  wiring change.
- The used API surface was six functions, and the plan's table said so. It was seven:
  `/api/combine` calls `get_correlation`, which the survey missed because `app.py:664`
  imported `metas_unclib` inside a function body rather than at module level. Found by
  running the suite, not by reading.
- **Byte-identical XML** was the requirement, since every credential digests it. Four
  details decide it and all four were read off real output: CRLF with no trailing
  newline; `encoding="utf-16"` on a string digested as UTF-8, which is UncLib's own
  inconsistency and is preserved rather than corrected; .NET's fifteen-then-seventeen
  significant digit formatting, which Python's `%g` matches once the exponent marker is
  uppercased — validated over 516 values including 240 random bit patterns; and
  `-(a/b)/b` for a quotient's second Jacobian, which differs in the last bit from
  `-a/(b*b)`. The last two were found by the equivalence test failing, which is the
  argument for having written it before trusting the engine.
- The binary form is **not** reimplemented. Its layout is undocumented and reverse
  engineering a licensed library's format would be the wrong move twice over. Four blobs
  are generated on a licensed machine and committed, keyed by a digest of each result's
  XML, so a content-derived key cannot attach a stale blob to a changed measurement: the
  lookup misses and the certificate reports the representation unavailable. That also
  means the committed keys double as reference XML digests, so CI proves byte-identity
  without UncLib present.
- **Four budget lines moved by one unit in the last place**, taking three digests and six
  signatures with them; 55 of 59 documents are byte-identical. UncLib computes a budget
  contribution by inverting the dependency matrix, so its rounding depends on the whole
  system and no closed form reproduces it. Chasing bit-exactness would have meant
  reimplementing `LinAlg.Inv` to reproduce an inconsistency, because where they differ
  this engine is the self-consistent one: UncLib reports a sensitivity coefficient of
  `10000.000699999999` in a budget while writing `10000.0007` as the Jacobian into the
  XML of the same certificate. A test pins that. Rounding would make them agree and is
  not available — these are intermediate values.
- Three tests in `test_dependencies.py` were about the binary carrier and would have
  simply skipped. Two were split instead, so the engine-independent half still runs and
  the deployed configuration's documented degradation is pinned: an unavailable
  representation says so rather than being absent or invented.
- `.github/workflows/ci.yml` is the project's first CI. It asserts `metas_unclib` is
  *absent* from the base install — if that ever passes, a deploy would be redistributing
  the library — and that two dumps of the world are identical.
- Not yet done on this branch: nothing. The chapter 6 prose still describes UncLib as
  the only implementation of the format; that sentence belongs to the content-layer work
  and is noted there rather than edited in JavaScript now.

`feature/hosting` complete. 305 tests pass in the deployed configuration (46 skipped:
the equivalence tests need UncLib, which by then had left the local venv — see below).

- `config.py` reads seven variables and every default is the local one, so `uv run
  vc-demo` behaves exactly as before. `VCQI_PUBLIC` gates the rest, because a reader on
  their own machine should not have to fight limits only a public host needs.
- `web/limits.py` holds a body-size cap and a token bucket. Plain ASGI, no dependency.
- **The cost table was wrong on the first attempt, and the harness caught it.** Charging
  every `/api/` POST looked prudent and was not: `sliderRow` fires `oninput` on every
  step with no debouncing, so one drag of the scope slider could post hundreds of times.
  The rule that replaced it is not "how much work does this route do" but "can the
  caller raise it" — only `/api/keys/*` and `/api/verify` can. The slider routes
  evaluate a four-input model however the sliders are set, so charging them would
  throttle a reader and do nothing about an attacker.
- That led to a second fix worth having on its own merits. `sliderRow` now serialises
  its handler: the readout still updates on every event, but the request runs one at a
  time against the slider's latest position, so intermediate positions are skipped.
  Besides the wasted requests, the old behaviour had a latent race — responses could
  land out of order and a slow early one could overwrite a newer verdict. The five call
  sites return their promise now.
- The Content-Security-Policy reaches `default-src 'none'`, which is unusual and worth
  keeping: no CDN, no web font, no analytics, and the only inline asset is the favicon's
  data URI. One obstacle, as anticipated: `el()` set inline styles with
  `setAttribute('style', ...)`, which a strict `style-src` blocks. Assigning through
  `node.style.cssText` instead is not covered by CSP and left all fourteen call sites
  untouched, including the one computed bar width.
- `docs_url=None` in public mode. Swagger UI loads from a CDN, so the API docs would
  have been a page broken by this project's own policy.
- ARCHITECTURE.md's "The server binds to localhost" was the load-bearing clause of the
  `/api/keys/*` safety argument. It is now false, and the paragraph says what replaced
  it: there is still no secret, because every key derives from a published seed and the
  route signs with the caller's own key; what changed is that unbounded CPU on
  attacker-chosen input is now reachable, and that is what the limits answer.
- The Dockerfile is ordinary — `python:3.11-slim`, no system packages, ~150 MB — which
  is the dividend from change set 7's first branch. It asserts two things at build time:
  that the interface and the committed blobs reached the wheel (the local checkout is an
  editable install, so packaging had never been exercised, and the failure mode was a
  process that starts happily and serves 404), and that `metas_unclib` is *not* in the
  image, because if that ever succeeds the build is redistributing a licensed library.
- `render.yaml` is a Blueprint so first-time setup is New → Blueprint → pick the repo,
  in a browser. That is the reason Render was chosen over Fly.io, whose app creation
  wants a CLI this machine cannot install.
- CI gained a second job that builds the image and drives it under `--cpus=0.5
  --memory=512m`, the smallest Render instance, so "does it fit" is measured rather than
  assumed. Every assertion in it was first checked against a local server, which is how
  the one wrong one was found: `server_header=False` lives in `main()`, so a check run
  against `python -m uvicorn` fails for a reason that has nothing to do with the code.
- Verified against a server started through `main()` with the production limits:
  `node tools/ui-clicks.mjs` reports every control on every chapter responding, and the
  keys and issuing chapters — the two that spend tokens — pass without a 429. An earlier
  run with a burst of 10 did hit one, which is what turned the burst from a guess into a
  measurement.
- Not verified here: the image itself. There is no Docker on this machine and no network
  from the session, so the container job is the first thing to read after pushing.
- Also not verified here, and worth being plain about: moving `metas-unclib` to an extra
  removed numpy as a transitive dependency, and the local venv was re-synced to the base
  configuration partway through. So the equivalence tests skipped for the rest of the
  branch. They passed on this machine earlier in change set 7 (332 passed, 2 skipped);
  restoring that needs `uv sync --extra unclib`.

`feature/content-layer` complete. 350 tests pass (46 skipped, still the UncLib
comparisons). Chapter 0 reads its prose from markdown; the other eleven are unchanged and
keep working, which is the property that makes the rest of the migration incremental.

- Merged with what the plan called PR 4. A mechanism with no consumer cannot be reviewed
  meaningfully, and chapter 0 exercises prose, callout, a static table and a panel
  title/hint in one go.
- **The renderer is in-repo rather than `markdown-it-py`, and the reason was forced
  before it was chosen.** The session had no network, and the package is not in the uv
  cache, so a dependency could not have been added or tested. Having to decide, the
  in-repo answer turned out to be the better one here: the repository already does this
  for JCS and multibase with a section in ARCHITECTURE.md explaining why, the README's
  claim of nothing to install stays true, and — the argument that would decide it alone —
  a general parser has to be *told* not to pass HTML through, whereas this one has no
  such path. Twelve adversarial inputs confirm no tag survives that the module did not
  emit. The repository's own documents use reference-style links and nested lists, which
  this does not support, so the docs viewer will need it extended or the library after
  all; that is recorded in the module and in ARCHITECTURE.md rather than left to be
  rediscovered.
- **No word changed.** `tools/chapter-snapshot.mjs` captured all twelve chapters before
  the migration and again after; stripping tags from both and comparing gives an empty
  diff across every chapter. The only HTML difference anywhere is the `content-block`
  wrapper `t.block()` puts around chapter 0's table, and no CSS selector depends on that
  table's depth, so it still looks the same.
- Fifty-five lines of `chapters.js` became nine, and `triangle()`, the stat row and every
  handler were untouched — which is the whole reason this was tractable rather than a
  rewrite: `prose()` already took HTML.
- Six ways an editor can break a file were each introduced deliberately and confirmed to
  fail the suite: a renamed key, markdown in a panel hint, a block nothing renders, a
  table row with too few cells, an empty heading block, and a placeholder in a block
  nothing interpolates.
- Two of the first four test failures were the tests catching my own prose: the word
  "throws" in a comment in `content.js`, and `lede:` inside the comment that replaced the
  descriptor fields. Both reworded rather than the checks loosened. A third was a real
  gap — the missing-content marker had no CSS, so it would have been easy to skim past.
- The mtime cache was verified live: renaming a key in a file and re-requesting
  `/api/content` reflected it with no restart, and the chapter then rendered with the red
  marker in place of that paragraph, no render failure, everything else intact.
- `heading()` in `app.js` reads title/eyebrow/lede from the content file where there is
  one and from the CHAPTERS descriptor otherwise, so migrated and unmigrated chapters
  coexist without either being a fallback for a failure. A test asserts a migrated chapter
  does not define its heading in both places.
- Left for the remaining chapters: about 110 string literals across eleven chapters, and
  the eight places a sentence interpolates a computed value, which need `t.fill`. The
  order should follow whichever chapter someone actually wants to edit rather than the
  numbering.
