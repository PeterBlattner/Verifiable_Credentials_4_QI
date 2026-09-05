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
