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

# Change set 8 - sharpen the cautions

## Context

The demonstration is convincing enough to be mistaken for something it is not. It renders
real-looking credentials, names real institutions and reads like an implementation of a
specification, and it is none of those things: a weekend sketch, AI-assisted, unvalidated,
built to understand Verifiable Credentials rather than to propose anything.

The cautions in place said one narrower thing -- that the identifiers and keys are
fictional -- in two places easy to miss: a faint `rail__note` below twelve chapter links,
and a blockquote near the top of `README.md`. Neither said the work is unreviewed, that no
institution has endorsed it, that Recognized Entities is a Working Draft not fit for
production, or that nothing here should inform a decision about accreditation or
traceability. The nearest thing to a full statement was the closing paragraph of chapter
11 -- the last thing in the last chapter, which is the wrong position for it.

## Decisions taken

- A short banner at the top of every page, always visible, not dismissible.
- The full statement as the first entry in the rail, which makes it the landing page.
- `README.md` carries the same statement in full, replacing the blockquote.
- The banner is literal markup in `index.html`; the statement behind it is a content file.
- The cautions carry a marker in the rail rather than the number 0.

The last one changed during implementation. Seating the cautions at 0 was the original
choice, and a review found that it shifts every chapter number and falsifies about two
dozen by-number references -- several of them editorial fields in `actors/harmonisation.py`
served to the reader -- against a rule `ARCHITECTURE.md` already records for exactly that
reason. `CHAPTERS` grew an `unnumbered` flag instead, `buildRail` numbers from the numbered
entries, and every existing reference stayed true.

## Build order

- [x] `feature/caution-statement` -- banner, `00-cautions.md`, layout, docs, guard tests

## Progress log

367 tests pass, 46 skipped. `chapter-snapshot.mjs --text` diffs to exactly one added
section against the pre-change baseline: no word of the twelve existing chapters moved.
`ui-clicks.mjs` reports every control responding, with the cautions chapter at 0 controls.

- The banner is static markup because the stage shows only "Could not reach the
  demonstration server" when the world fetch fails, and that is precisely when a reader
  most needs telling what these pages are. A caution that ships with the JavaScript is
  missing whenever the page is confusing.
- Keeping it visible without measuring its height turned the page into a fixed-height
  column with two scrolling panes. The sticky-bar alternative needs the banner's height as
  a number and the banner wraps to two or three lines depending on the width, so that
  number is wrong nearly everywhere. Below 860px the rail already stacks, so there the
  document keeps its own scroll and the banner is merely sticky.
- Four consequences of that were found by review rather than by running it, and each would
  have looked fine in one browser: `.shell` had no declared grid row, so an `auto` row
  sized from a long chapter's max-content would have grown past the shell and left neither
  pane scrolling; `max-width` left on `.stage` would have floated the scrollbar 1180px from
  the left edge, so it moved to `.stage > *`; `100vh` became `100dvh` because the revert
  threshold is 860px and a tablet in landscape is above it; and a scroll container with no
  focusable content cannot be scrolled from the keyboard at all, which on a prose-only
  landing page meant the caution statement was unreachable without a mouse -- `#stage`
  gained `tabindex="0"`.
- `stage.scrollTop = 0` rather than `stage.scrollTo(...)`: jsdom implements the property
  and not the method, and the throw would have escaped the `try`/`catch` in `show()` into
  an unhandled rejection that takes both harnesses down. Verified against the installed
  jsdom before writing it rather than after.
- Nothing had ever asserted any caution wording -- `fictional`, `rail__note` and `footnote`
  appeared in no test. Six checks now cover the banner being in the page and served, the
  cautions being `CHAPTERS[0]`, the `unnumbered` flag being honoured, every panel of the
  statement being served, and `README.md` making the same five cautions. Each was
  confirmed to fail by mutating the thing it guards; structure and phrases are asserted,
  never whole sentences, so the words stay editable by whoever spots a mistake.
- `ui-clicks.mjs` now fails on a `.content-missing` marker. A prose-only chapter makes
  "0 controls, all responded" a legitimate result rather than the vacuous one that harness
  was written to catch, and `content.js` reports a missing key through `console.warn`,
  which it was not intercepting. Proved by renaming a key: `MISSING CONTENT`, exit 1.
- The `Dockerfile` packaging assertion covered the four static files and nothing about the
  markdown. Without the prose the migrated descriptors carry no title, so the landing page
  would have deployed as a blank heading over a column of red markers. It now asserts
  `"cautions" in content.chapter_ids()`.
- Two corrections to the supplied text: the banner sentence ended mid-clause, and "Global
  AIC" became "Global ACI", which is the name the reader sees everywhere else.
- Unverified and deliberately left so: "Recognized Entities v1.0 is a W3C Working Draft,
  described by the Working Group as experimental and not fit for production deployment."
  The version string and status wording should be checked against the published document.
- Follow-up on the same theme: chapter 2 asserted that the IAF and ILAC consolidated into
  Global Accreditation Cooperation Incorporated on 1 January 2026, and drew a lesson from
  it about a trust anchor changing its identifier. A dated claim about two real bodies is
  the kind of unnecessary complication the caution statement was written to avoid, and it
  was in three reader-facing places: the chapter prose, `README.md`, and the `description`
  field in `actors/registry.py` served through `/api/actor`. All three now describe
  Global ACI as a stand-in for whichever body holds the accreditation role, with the point
  that nothing in the demonstration rests on the name. The identifier-churn argument is
  worth making somewhere -- most naturally in chapter 10, next to the other things a
  deployment would have to survive -- and is not made anywhere at the moment.

# Change set 9 - legal metrology, scoped to OIML-CS

## Context

The demonstration covered two of the three pillars of the quality infrastructure.
Metrology ran from BIPM through the CIPM MRA; accreditation ran from Global ACI through
an accreditation body. The third pillar, legal metrology, was absent, and
`LEGAL-METROLOGY.md` recorded how it would be added and was then left unbuilt.

That document took a broad view: national type approval, national verification,
designation of private verification bodies, market surveillance. This change set does not
follow it. The scope is OIML-CS only, and within OIML-CS only three things -- an Issuing
Authority, a Test Laboratory, and the certificate that a type meets an OIML
Recommendation. Utilizers and Associates are out.

The reason to pick this pillar and this slice of it is not completeness. It is that
OIML-CS is the first thing in the project that makes a document rest on two arrangements
at once, which chapter 11 has described as "the entire reason for doing any of this"
since it was written and which nothing had actually built.

## Decisions taken

- Helvetia Testing plays the Test Laboratory rather than a new actor being invented. It
  was already an accredited testing laboratory at the bottom of a live calibration chain,
  and it is the join.
- R 46, active electrical energy meters, because a type evaluation of a meter needs
  calibrated electrical standards and this world already has them. R 60 is in the table
  unevaluated: it is the OIML's own pilot for machine-readable Recommendations, and it is
  what the Issuing Authority is *not* recognised for.
- A new dedicated Issuing Authority, and a new meter manufacturer, so the kettle story is
  untouched.
- Branch tags and a filter on the graph, dimming rather than hiding.
- Threaded through the existing chapters. No thirteenth chapter.
- `LEGAL-METROLOGY.md` deleted rather than narrowed. Most of it was about the national
  layer. It is at `ba1c144` with the reference implementation at `bf4b24d` / `bea1372`.

## Build order

- [x] `feature/oiml-cs` -- actors and R 46; the four credentials; the graph; chapters and
      documentation

## Progress log

395 tests pass, 46 skipped. Two `--dump` runs are byte-identical at 76 documents.
`ui-clicks.mjs` reports every control responding. The snapshot diff is confined to the
chapters that should have moved.

- The two-anchor claim is real and asserted, not described. Verifying one OIML
  certificate fetches from eight hosts and reaches `oiml.example` upward through
  recognition and `bipm.example` downward through evidence -- the type evaluation, then
  the multimeter's accredited calibration, then the national standard behind it. The only
  thing the two paths share is the laboratory in the middle.
- Three latent defects in the pipeline surfaced, each of which would have failed silently
  rather than loudly. `REQUIRED_ACTIONS` held one action string per credential type, and
  Global ACI *accredits* while OIML *recognises*, so one of them was always going to be
  wrong -- in the direction that rejects a genuine document. `_payload()` matched three
  subject members by name and a type absent from that list reads as an empty payload,
  which makes every downstream step *skip*: a new credential type that forgot to appear
  there would have verified with most of its checks quietly not running. And
  `_traceability_references()` never followed a single `testReport`, so the evidence path
  would have stopped at its first hop while reporting a pass.
- The Recommendation is the scope, and that is the argument for the whole change set. A
  CMC and an accreditation scope are declarations an organisation writes about itself, so
  `scope.py` had to invent a machine-checkable form for them. `Recommendation.to_json()`
  emits the member names a verifier already looks for, so the existing capability check
  reads it without being taught a third shape -- and the thing it points at is numbered,
  edition-controlled and published by somebody else. What is still invented is the
  schema, which is the new chapter 11 item.
- The quantity a type evaluation reports is the instrument's *error*, not the quantity it
  measures. That took a second pass to get right: the first version had the capability in
  kWh and the claim in per cent, and the scope check could not compare them.
- The legal layer needed its own timeline, exactly as the archived branch had recorded.
  Recognitions run from 2021 where the rest of the world runs from 2026, so the 2024
  certificate is issued under a recognition that already existed. A test asserts the two
  stay apart.
- No new published binary uncertainty form, and no new top-level verification step. The
  first would have required regenerating `unclib_blobs.json` on a licensed machine for a
  representation nobody would have used; the second would have falsified the "eleven
  checks" sentence in chapter 4 and the exact step-id list two tests pin.
- Four silent-failure classes now have tests, three of them found by writing the tests
  rather than by the change: a node with no position in `graph.js` (skipped, with its
  edges dropped, without a word), an edge routed through an unrelated box, a credential
  missing from `CREDENTIAL_LABELS` (unreachable in two chapters, nothing logged), and
  markup in an editorial field the interface renders as plain text. Every one was
  confirmed to fail by mutating what it guards.
- `tools/ui-clicks.mjs` earned its keep again. It reported the three new filter chips as
  inert and it was right: dimming changes no text, so the control was indistinguishable
  from a broken one to a reader as much as to the harness. The chips now say what was
  selected and which organisations appear in more than one arrangement, which is the
  sentence a reader wants there anyway.
- Two incidental findings. The shared check-standard pair had been in the world since
  change set 4 and no test had ever run the pipeline over either credential. And the
  written-out failure-case count had been wrong twice -- the break-it lede said eleven,
  the README said fifteen -- so both are now compared against `len(TAMPER_CASES)` by a
  test.
- One case is caught twice, and it is left that way on purpose: certifying against the
  wrong Recommendation fails both `output-validation` and `scope`, because the recognition
  names the Recommendation *and* a schema built from it. That doubling is what a
  machine-readable Recommendation would buy, and saying so is more useful than tidying it
  into a single failure.
- Not modelled, and recorded as decisions rather than gaps: legal force and the national
  authority that confers it, the Utilizer and Associate roles, what distinguishes Scheme A
  from Scheme B, and what SMART stands for. The last two because no primary source to hand
  settled them, which given what the caution statement now says matters more here than
  anywhere else in the project.

# Change set 10 - what a reviewer corrected

## Context

The demonstration was reviewed, unsolicited, by someone who works on the verifiable
credentials specifications. About thirty minutes, over the data structures and the
harmonisation chapter. Three findings, and they are not equally comfortable.

The data structures held up: better than 90% of them sound for a first draft, with
changes to suggest but the general shape workable. That is the pleasant one and it needs
no work.

**The harmonisation chapter overstated the problem.** Seven of its sixteen items carried
*nothing exists yet*, and the reviewer's estimate was that only about a fifth of the list
needed a long argument. Checked item by item against the published specifications rather
than against the first draft's assumptions, five of those seven had answers - some
published while this was being written, some still moving through as pull requests.

**Two things it never considered**, both bearing directly on a document that has to
verify in thirty years: cryptographic event logs, and long-term retrieval of the
documents a verification reads.

**And there is no exchange anywhere in it.** Every credential here is handed around as
JSON. The reviewer pointed at VCALM's figure of a holder and an issuer/verifier, which is
the shape the cross-border case actually has. That is change set 11, on its own branch.

This is the second time this project has made one class of mistake. Change set 6 assumed
the metrology vocabularies were missing and had to be told the BIPM already publishes
them. This time it assumed the credential mechanisms were missing. Both run the same way -
concluding a gap exists because the author had not read far enough - and that is worth
recording as a pattern rather than as two incidents.

## Decisions taken with the user

- The re-audit, the two missing items and the caution update on one branch; the exchange
  on its own, because it is a chapter and endpoints rather than editorial data.
- did:webvh is **described, not built**. It answers three questions this chapter said were
  unanswered, and citing it costs nothing; migrating the world to it would move every
  digest and signature for a claim the page can make honestly in prose.
- The reviewer is not named. Their reading is described, their affiliation is not given,
  and nothing needed clearing with them before publishing.

## What changed

**A fourth status, `partial`.** The vocabulary was `available`, `emerging`, `open`, and it
had no way to say *a specification answers the mechanical half and something institutional
is left over*. Five items needed exactly that, and without it they were all filed as
`open`, which reads as *nothing exists*.

**A `source` field.** A bare URL per item, rendered as a link. A field of its own rather
than a sentence inside `exists`, because every other field reaches `textContent`, where an
anchor tag shows the reader its angle brackets - a trap `tests/test_deployment.py` already
guards, and which the `units` item had worked around by spelling a URL out in prose. Two
new tests make it load-bearing: a source must be a bare `https://` URL, and any item
claiming `available` or `partial` must have one. A researched claim and an assumed one
were previously indistinguishable to the suite.

**Five items re-audited.**

| Item | Was | Now | What answers it |
| --- | --- | --- | --- |
| `did-method` | open | partial | did:webvh. Rotation identity through the SCID, withdrawal through pre-rotation, and the resolver's obligation written down. Mechanical migration from did:web. |
| `status-meaning` | open | partial | Bitstring Status List, a Recommendation since May 2025: `statusPurpose: message`, `statusMessage` per value, `statusReference` at the governing document. |
| `anchors` | open | partial | ETSI TS 119 612 and the EU list of trusted lists. A signed, rotatable anchor list is deployed at scale, not unbuilt. |
| `persistence` | open | partial | SCID portability across domains, and watchers caching indefinitely. The thirty-year undertaking stays open and cannot be settled by evidence yet. |
| `timestamps` | open | partial | RFC 3161 was already named; what changed is that an issuer's own witnessed log answers *was this key valid then* without a third party being asked. |

`legal-effect` stays open and gained the near miss worth naming: `termsOfUse` sounds like
the answer and is not. It constrains what a recipient may do with a credential, not what
the credential permits in the world, and pressing it into service would produce a document
that reads plausibly to a person and means something else to a machine.

Still open, and these are the ones needing a long argument: `chain-crossing`,
`legal-effect`, `type-identity`, `governing-copy`, `uncertainty-transport`.

**Two new items, both second tier.** `event-logs` and `retrieval`. Second tier and not
third for the same reason in both cases: neither can be started late. A log not kept from
the first day cannot be reconstructed, and a document nobody archived in 2026 is not
archivable in 2056.

`retrieval` is the sharper of the two, because chapter 10 had already measured it without
naming it. Verifying one certificate of conformity reads 31 distinct documents from 7
hosts. The credential travels with its holder and is safe; the other 30 are fetched from
wherever they live. A test compares both numbers against what `/api/infrastructure`
actually reports, so the sentence stays a measurement rather than a number that was true
once.

**The chapter counts instead of asserting.** A panel above the tiers reports how many
items are available, partial, emerging and open, computed from the items themselves.

**The cautions.** *"have not been reviewed, tested or checked against the specification by
anyone"* was no longer true. All three copies now say what the review was and what it was
not - one reader, thirty minutes, not validation - and the closing offer records that
correction arrived once and improved the work. The banner is untouched and still correct:
no institution named here has reviewed or endorsed any of it.

## One defect found while doing it

`prose([step.detail])` put a whole ladder step into a single paragraph, so the blank lines
step 7 has carried since change set 9 rendered as spaces. Splitting on the blank line
fixes step 7 as well as the rewritten step 2.

## Files

```
src/vcqi/actors/harmonisation.py              partial, source, five re-audits, two new items
src/vcqi/web/static/js/chapters.js            status map, source link, count panel, step split
src/vcqi/web/content/chapters/00-cautions.md  what the review was, and was not
README.md                                     the same statement, kept in step by test
tests/test_harmonisation.py                   source shape, citation, the count, the new items
tests/test_web.py                             the fourth status, and the served source field
```

## Verification

- `uv run pytest`
- `node tools/ui-clicks.mjs` against a running server
- `python -m vcqi.actors.scenarios --dump` twice. No credential content changed here, so
  this must be untouched, and it is the check that proves it.

## Git

Branch `feature/harmonisation-review`, from `develop`. Nothing pushed without asking.

## Change set 10 - build order

- [x] **R1 - Vocabulary.** The `partial` status and the `source` field, with the two tests
      that make a citation compulsory for any item claiming an answer.
- [x] **R2 - Re-audit.** Five items restated against the specifications; `legal-effect`
      gains the near miss.
- [x] **R3 - The two gaps.** `event-logs` and `retrieval`, both second tier, with the
      retrieval count checked against what chapter 10 measures.
- [x] **R4 - Ladder.** Step 2 becomes publish a key as a log, and keep what you fetched.
- [x] **R5 - The count panel.** Computed in the interface, not written into the prose.
- [x] **R6 - Cautions.** All three copies, plus the closing offer.

## Change set 10 - progress log

401 tests pass, 46 skipped. All thirteen chapters render and every control responds.

- Eighteen items now, from sixteen. Five open, which the chapter reports as about 28% -
  higher than the reviewer's estimate of a fifth, and reported as counted rather than
  adjusted to match it.
- The five re-audited items each open by saying what the first draft got wrong. That is
  deliberate and should stay: a page about unsolved problems goes stale by overstating
  them, and one visible correction is the cheapest available warning that there are
  probably others.
- `test_an_item_claiming_an_answer_says_where_to_read_it` is the check this chapter needed
  from the beginning. Nothing previously could tell a researched claim from an assumed
  one, which is exactly how seven items came to say *nothing exists yet*.
- The retrieval item was the only place where the two new gaps could be made concrete
  rather than argued, because chapter 10 already produced the measurement. 31 distinct
  documents, 7 hosts, and only one of the 31 travels with the holder.

# Change set 11 - the exchange, which was never there

## Context

The reviewer's third finding, and the one with the most in it. Twelve chapters modelled
what a certificate says and none of them modelled anybody asking for it. Credentials
were handed around as JSON: a document existed, a verifier read it, and the step where
one organisation requested it from another was skipped entirely.

That is not a small omission, because the skipped step is the hard case. The quality
infrastructure exists for a document crossing a border between two organisations with no
prior relationship, and the crossing was the part that had never been built. The
harmonisation chapter's own inclusion test - *two conforming implementations that differ
here cannot interoperate* - catches it plainly, and it went unlisted for eleven chapters.

The reviewer pointed at VCALM's figure of an exchange between a holder and an
issuer/verifier. That figure is the shape this world was already built for and could not
show: the OIML Issuing Authority verifies what a test laboratory presents and issues a
type certificate on the strength of it. Every earlier chapter had that certificate simply
existing.

## Decisions taken

- VCALM's paths, not this project's. `/workflows/{id}/exchanges/{id}` are the only routes
  in the application not under `/api/`, and using the specification's shape rather than a
  local convention is most of what the chapter has to show.
- Chapter 12, last, after harmonisation. Seating it where it belongs thematically - next
  to the deployment chapters - would renumber everything from chapter 9 up, and roughly
  two dozen references to a chapter by number would silently become wrong, several of
  them editorial fields served to the reader from `actors/harmonisation.py`.
- Three workflows, in increasing order of interest, all using credentials the world
  already has.
- The credentials returned on success are the world's own rather than freshly minted.
  That keeps the build deterministic and makes the honest point about an exchange: it is
  transport, the same document arrives, and what changed is that somebody had to ask.

## What was built

**`src/vcqi/actors/exchange.py`.** Three workflows, an exchange store, the presentation
request, the holder's presentation, and the turn logic.

| Workflow | Coordinator | Role | What it shows |
| --- | --- | --- | --- |
| `accreditation` | SAS | issuer | The simplest exchange there is, and it still needs two turns. What is checked is not a credential but control of an identifier. |
| `border` | Market surveillance | verifier | Pure verification - and the reason chapter 10 had to be corrected. |
| `oiml-type` | Verifica | issuer-verifier | Two credentials verified and a third issued in one response, and nothing issued if either fails. The reviewer's figure. |

**Four routes.** `POST /workflows/{id}/exchanges` opens one;
`POST /workflows/{id}/exchanges/{id}` takes either turn - the body distinguishes them,
not the address; `GET /api/exchange/workflows` lists them for the chapter;
`POST /api/exchange/{wf}/{ex}/present` signs on the holder's behalf, which is ours and
not VCALM's and would not exist in a deployment.

**`challenge` and `domain` on `sign_document`.** Optional, and they go into the proof
configuration that is canonicalized and hashed, so they are covered by the signature
rather than travelling beside it. Verification needed no change at all:
`verify_document` rebuilds the configuration from every proof member except
`proofValue`, so an added member is included automatically.

**`Resolver.authentication_methods`.** The mirror of `assertion_methods`, and needed for
the same reason in the other direction: a key published only for signing credentials is
not thereby authorised to prove who is holding them.

## The bug the tests caught, which is the most useful thing here

The first version of `_check_presentation` read the challenge, the purpose and the domain
out of the proof, compared all three, and **never verified the presentation's signature**.

`test_the_challenge_is_signed_and_not_merely_carried` caught it. An intercepted
presentation, re-pointed at a live exchange by editing one string in the proof, collected
a type certificate. Nothing else in the suite would have noticed, because every
credential inside the presentation was genuine and verified perfectly.

The lesson generalises and is now in ARCHITECTURE.md: credentials are public documents,
anyone can obtain a copy, and the authentication proof on the presentation is the only
thing between a public certificate and anyone claiming to hold it. Every string
comparison in that function is worthless without the signature check that follows it -
the comparisons count only because the challenge sits inside the hashed proof
configuration, so editing it breaks the signature.

Related, and recorded rather than left to be found: identifier-based recognition
discovery in `vc/recognition.py` reads credentials out of a whois presentation without
verifying that presentation's proof. That is defensible there and deliberate - each
credential inside is verified independently, so the presentation is a container with no
claim of its own. It is not defensible in an exchange, where the presentation *is* the
authentication.

## What it cost, and the claim it falsifies

`actors/deployment.py` argued that verification is a computation rather than a
conversation, and concluded that a verifier operates nothing. The premise is true. The
conclusion does not survive anybody having to *ask*.

An exchange has state - which exchange, which turn, which challenge - and state means a
service, a store, an expiry policy and something to attack. `ExchangeStore` is the first
thing in this project the server has to remember between requests: 256 exchanges, fifteen
minutes each, oldest evicted first.

So the corrected split, which chapter 12 states and chapter 10 now bridges into:
checking a credential you already hold is free and works offline on a laptop at a border
post. Obtaining one needs both parties reachable at once and needs the asking party to
run something. The verifier profile and the module docstring both say so now, where it
applies, rather than the chapter quietly overstating its case.

The exchange turn is charged at the same rate as `/api/verify`, because it is
`/api/verify` with the number of credentials also in the caller's hands. Opening an
exchange is charged lightly, and for a different reason: what it consumes is a store slot
with a ceiling, not CPU.

## The nineteenth harmonisation item

`exchange`, first tier, `partial`. Not open, because the difficulty is that there is more
than one answer rather than none: VCALM is a Working Draft describing exactly this, and
OpenID for Verifiable Presentations answers the same question differently and is what the
European digital identity wallets are deploying. Choosing is a profile decision. The
consequential part is not which protocol but whether the choice is made once for the
quality infrastructure or once per country, and the second is the default that happens
when nobody decides.

Ladder step 3 - two institutes verifying each other bilaterally - now says to hand the
certificates over through an exchange rather than by email, because the disagreements
worth finding are in the protocol as much as in the documents.

## Files

```
src/vcqi/actors/exchange.py           new: workflows, store, request, presentation, turns
src/vcqi/actors/harmonisation.py      the exchange item, and ladder step 3
src/vcqi/actors/deployment.py         the verifier operates nothing, corrected
src/vcqi/crypto/dataintegrity.py      challenge and domain in the proof configuration
src/vcqi/vc/resolver.py               authentication_methods
src/vcqi/web/app.py                   four routes, and the only non-/api/ ones
src/vcqi/web/limits.py                what a turn costs, and why opening costs less
src/vcqi/web/static/js/api.js         four calls
src/vcqi/web/static/js/chapters.js    chapter 12, and chapter 10's bridge forward
tests/test_exchange.py                new: 23 tests, eight of them refusals
README.md, ARCHITECTURE.md
```

## Verification

- `uv run pytest`
- `node tools/ui-clicks.mjs` against a running server
- `python -m vcqi.actors.scenarios --dump` twice, byte-identical. Exchanges are runtime
  state and no credential content changed, so the world must be untouched.

## Git

Branch `feature/vcalm-exchange`, from `develop`, with `feature/harmonisation-review`
merged in so the two read as one piece of work. Nothing pushed without asking.

## Change set 11 - build order

- [x] **X1 - The module.** Workflows, `ExchangeStore`, `presentation_request`,
      `holder_presentation`, `respond`.
- [x] **X2 - Challenge binding.** `challenge` and `domain` on `sign_document`, inside the
      hashed proof configuration.
- [x] **X3 - Routes.** The two VCALM paths, the listing, and the holder-signing seam.
- [x] **X4 - Limits.** A turn costs what `/api/verify` costs; opening costs less.
- [x] **X5 - Verify the presentation.** `authentication_methods` on the resolver, and the
      proof check that the first version was missing.
- [x] **X6 - Chapter 12.** Three exchanges, the message trace, the replay button.
- [x] **X7 - Corrections.** The verifier profile, the module docstring, chapter 10's
      bridge, and the nineteenth harmonisation item.
- [x] **X8 - Tests and docs.** `tests/test_exchange.py`, ARCHITECTURE.md, README.md.

## Change set 11 - progress log

424 tests pass, 46 skipped. Thirteen chapters render and every control responds. Two
`--dump` runs are byte-identical at 76 documents, which is the check that the world was
not touched.

- The dual-role exchange works on the credentials the world already had, which is the
  strongest thing about it: nothing was invented for the chapter. Helvetia Testing
  presents the recognition the OIML gave it and the type evaluation it performed, and
  Verifica returns the certificate. Alter either presented credential and the certificate
  is not issued.
- Eight of the twenty-three tests are refusals, and they are the ones worth having.
  Replay, forwarding to a second verifier, an unsigned presentation, a proof made for
  `assertionMethod` instead of `authentication`, a tampered credential inside a validly
  signed presentation, someone else's credentials wrapped in a presentation signed with
  the wrong key, a challenge edited to match its target, and an exchange id used under
  the wrong workflow.
- **The missing proof check is the finding of this change set.** It is recorded in
  ARCHITECTURE.md and in the module because the class of error is worth more than the
  instance: three string comparisons that look like security and are not, until the
  signature is checked. It was written, reviewed by eye, and read as correct.
- One thing not done and deliberately so: no failure case was added to chapter 8. The
  break-it chapter is about documents that are wrong, and every refusal here is about a
  conversation that is wrong. Folding them together would have cost the eighteen-case
  count two tests pin and blurred a real distinction.

# Change set 12 - two ways a credential moves

## Context

Chapter 12 implemented one architecture and presented it as the answer. It was not the one
METAS intends, and -- the part that mattered more -- it was not the one the rest of the
demonstration is built on.

UN/CEFACT's portable-credential architecture, at
`https://unvtd.unece.org/architecture/portable-credentials/`, argues from failure rather
than from elegance: fifty years of EDI digitised about a tenth of cross-border trade,
because a network of hubs and pipes only reaches the parties who joined it. So stop
building the network. Sign the document and let it travel with the consignment, by email,
file transfer, a USB drive or a QR code.

**This project was already built that way and had not noticed.** `actors/deployment.py`
says verification is *a computation, not a conversation*; chapter 10 computes that the
institute keeps three documents online while six of its credentials travel unhosted. And
metrology has the oldest instance of the idea in existence, which is not digital at all: a
calibration certificate already travels with the instrument. The paper in the box is a
portable credential.

So change set 11 imported a second architecture and then rewrote chapter 10's claim as
though the exchange's cost were unavoidable. It is not. It is the price of choosing the API
model, and the chapter now says so.

## Decisions taken with the user

- **Both architectures, at full length.** The three VCALM workflows are untouched. The
  portable model goes in beside them, and the chapter is reordered so the reader meets the
  cheap answer first and the protocol as the narrow case that needs one.
- **The audit is computed, not asserted.** It is the novel result and the machinery for it
  already existed.
- **All three UNTP findings** go into chapter 11, plus a fourth in the exchange item.
- The chapter keeps its `exchange` id so no link breaks; `chapterExchange` becomes
  `chapterMoving` and the title becomes *How a credential moves*.

## The vulnerability this turned up, which is the most useful thing in it

The audit needed a rule about what a holder may hand over. Writing the rule down exposed
that the code did not have one.

`Resolver.fetch` preferred any document the holder supplied, and `resolve_did_document`
went through it. **So a holder could staple a DID document claiming a trust anchor's
identifier, sign a credential in that anchor's name with its own key, and the pipeline
reported `verified`.** Every check passed -- `proof` included -- because from the
verifier's point of view the anchor's published key really was the attacker's. The
attacker had supplied the document that said so.

It predates the exchange: `presented` and `resolve_did_document` are from change sets 1
and 6. What change set 11 did was make it reachable over HTTP, because `respond()` passes
the credentials a holder posted straight into `presented`.

It was caught once, by accident. The status check fetches the status list from the real
host, and that list's signature does not verify against the attacker's key -- so the first
attempt failed on `status` while `proof` passed. A credential publishing no status list
went through completely. Being saved by an unrelated check is not a defence.

The fix is `Resolver.retrieve`, which ignores `presented` entirely, plus
`RESOLVE_ONLY_KINDS` as a second guard inside `fetch` so a future call site using the
wrong method does not reopen it. Four call sites moved: DID documents, status lists, whois
presentations and registry entries.

## The measurement

`actors/portability.py` sorts every document one real verification reads into four classes
and then proves the sort by running the verification twice -- once with nothing supplied,
once with everything supplied that is allowed to travel.

| Class | Kinds | Count | Why |
| --- | --- | --- | --- |
| It travels | credential, schema, uncertainty-data | 13 | Signed in its own right, or covered by a `digestMultibase` inside something signed. Checkable whatever hand it arrived in. |
| Must be resolved | did-document, presentation | 7 | Establishes a key, or is what an issuer says about itself. Inherent. |
| Must be fetched now | status-list | 7 | A claim about the present tense. Inherent. |
| Could travel, and does not | registry-entry | 4 | No signature, no digest, so a copy cannot be checked. **Removable.** |

Both runs reach `verified`. Stapling removes 13 of the 31 retrievals and changes no
verdict, which is the portable-credential claim holding up under measurement.

**And the residue is the finding.** If the registries were signed -- the one removable
reason -- what a verifier would still have to fetch is 14 documents of exactly two kinds,
`did-document` and `status-list`: each organisation's key and its revocation list, and
nothing else. Which is, to the document, the hosting burden chapter 10 computed from the
opposite direction. Neither chapter knew it was describing the same quantity, and a test
pins the two kinds so they cannot drift apart.

The audit therefore prices *sign the KCDB*, which the harmonisation ladder already called
the highest-value single item on the page: four documents out of thirty-one, and the
difference between a registry a verifier must reach and one that can travel.

## Chapter 11

Four items gain facts, no statuses change, and the count panel recomputes itself so
nineteen items and five open stay correct with no edit.

- **`uncertainty-transport`** -- UNTP's Digital Conformity Credential carries a measured
  result as a value and a unit with **no uncertainty of any kind**. Three independent
  efforts have now modelled a measurement without modelling how good it is, which makes
  this an absence in the field rather than an oversight in any one of them.
- **`certificate-format`** -- there is now a second candidate with the international
  standing the PTB/DKD DCC lacks, and it is not a replacement: UNTP covers conformity
  assessment, not calibration, with no traceability chain and no uncertainty. One mature
  format without standing, one standing format that does not reach metrology, and nobody
  has joined them.
- **`units`** -- UNTP writes a unit as a bare string, so a UN construction published in
  2026 has the same gap this demonstration has. A register existing is not the same as
  anybody using it.
- **`exchange`** -- gains the third position, which is that the question is smaller than it
  looks: a portable credential needs no protocol, and UNVTD names OpenID4VP where it names
  one at all, and says it is compatible with business wallets without depending on them.

`ARCHITECTURE.md`'s naming section has earned its keep: change set 5 qualified every
mention as *PTB/DKD DCC* because "other DCCs exist", and one of them has now turned up.

## One defect fixed on the way

Editorial fields reach `textContent` by design, so the blank lines these four items now
contain rendered as spaces. `textParagraphs` builds real `<p>` elements and still sets
`text:` on each, which gives paragraphs without opening the fields to markup -- the
contract `tests/test_deployment.py` guards.

## Files

```
src/vcqi/actors/portability.py        new: four classes, and the audit that proves them
src/vcqi/vc/resolver.py               retrieve(), RESOLVE_ONLY_KINDS
src/vcqi/vc/checks.py                 the status list is retrieved, never presented
src/vcqi/vc/recognition.py            so is the whois presentation
src/vcqi/vc/verify.py                 so is the registry entry
src/vcqi/actors/harmonisation.py      four items gain UNTP and portable-credential facts
src/vcqi/web/app.py                   GET /api/portability
src/vcqi/web/static/js/api.js          one call
src/vcqi/web/static/js/chapters.js    chapter 12 reordered; textParagraphs; ch10 reworded
src/vcqi/web/static/css/app.css       one rule for stacked paragraphs in a kv field
tests/test_portability.py             new: the exploit, and the audit as a measurement
README.md, ARCHITECTURE.md
```

Nothing was deleted. `exchange.py`, its four routes, `challenge`/`domain` on
`sign_document` and `authentication_methods` all stay, all still tested.

## Verification

- `uv run pytest`
- `node tools/ui-clicks.mjs` against a running server
- `python -m vcqi.actors.scenarios --dump` twice, byte-identical

## Git

Branch `feature/portable-credentials`, from `develop`. Nothing pushed without asking.

## Change set 12 - build order

- [x] **P1 - The rule.** `retrieve()` and `RESOLVE_ONLY_KINDS`; four call sites moved off
      `fetch`.
- [x] **P2 - The exploit, kept.** The stapled-DID-document forgery as a regression test,
      confirmed to verify with the fix reverted.
- [x] **P3 - The audit.** `actors/portability.py`, four classes, two runs, the residue.
- [x] **P4 - Endpoint.** `GET /api/portability`, free in `route_cost`.
- [x] **P5 - Chapter 12 reordered.** Portable first, the audit second, the exchange third,
      the contrast and chapter 10's claim last.
- [x] **P6 - Chapter 11.** Four items, and `textParagraphs` so they render.
- [x] **P7 - Docs.** README, ARCHITECTURE, and this.

## Change set 12 - progress log

436 tests pass, 46 skipped. Thirteen chapters render and every control responds. Two
`--dump` runs are byte-identical at 76 documents, so no credential content moved.

- **The vulnerability was found by writing prose, not by writing code.** The audit needed
  a sentence saying what a holder may hand over; the sentence turned out to be false about
  this code; the exploit followed in twenty minutes. Worth recording as a method rather
  than as luck: the classification had to be defensible before it could be displayed, and
  making it defensible is what surfaced the hole.
- The residue coming out as exactly `did-document` and `status-list` was predicted before
  it was measured, and it is the strongest result in the project so far: two chapters
  built months apart, from opposite directions, computing the same minimum. A test asserts
  the two kinds rather than the count, so growing the world cannot quietly falsify it.
- `must-resolve` first reported zero hosts, because `deployment.host_of` understands
  `https://` only and every DID document here is addressed `did:web:`. The count that
  mattered most was the one silently reading zero.
- One thing not done and deliberately so: no attempt to make registry entries actually
  travel. Signing them is the BIPM's to do, the demonstration can say what it would buy
  without pretending to have done it, and inventing a signature over a KCDB entry would
  have been this project asserting a decision nobody has taken.

# Change set 13 - finish the content layer, and question the format first

## Context

Change set 7 built the content layer and moved two chapters into it. Twelve were left
carrying their prose as string literals in `chapters.js`, and `CONTENT.md` listed only the
two that were done -- so for the other twelve it answered "where do I edit this sentence?"
by omission, and an editor had to read 2218 lines of interactive JavaScript to find out
whether the words were reachable at all.

The half-finished state was supported by design and honestly so: `blocks_for` returns an
empty mapping for an unmigrated chapter deliberately. What was not defensible was the map
of it.

## The format, questioned before it was finished

The first thing asked was not "finish it" but "wouldn't HTML be better?" -- the page is
HTML in the end, so a markdown hop looks like indirection. That was the right question to
ask before migrating twelve more chapters into a format, and the answer is worth keeping
because it is not the one `ARCHITECTURE.md` gave.

`ARCHITECTURE.md` justified markdown by an editor working in the GitHub web UI. Asked
directly, the only people who edit this prose are the author and developers, so that
argument does not hold and could not be leaned on.

What holds instead, measured rather than asserted:

- `to_text()` tokenises with `<[^>]+>`, which is a valid tokeniser *only* because no
  attribute in the renderer's output can contain `>`. It feeds every panel title.
- `_kind()` classifies a block with a bare `startswith("<table")`. A leading newline or a
  comment -- which `_parse` explicitly permits at the top of a file -- would make a real
  table classify as prose.
- `_safe_url` rewrites `javascript:`, `data:` and `vbscript:` targets to `#`, and every
  link gets `rel="noopener"`. Nothing would do either for a hand-typed `<a>`.
- `content.js`'s `fill()` escapes three characters and substitutes into the HTML string.
  Today a `{placeholder}` can only land in prose; in author-written HTML it could land
  inside an attribute, where escaping three characters is not enough.
- `TestMarkdown` is 7 tests and 27 collected cases, 57% of the cases in that file, and
  deletes wholesale under HTML. Eight further tests change shape rather than pass.

And the one argument that would have favoured HTML did not survive measurement. The appeal
was that the twelve chapters already held HTML in their literals, so migration would be
cut-and-paste with byte-identical snapshots. `chapters.js` contained **102 inline tags in
total**: 48 `<strong>`, 25 `<em>`, 22 `<code>`, 4 `<a>`, 2 `<p>`, 1 `<sup>`. All but the
last are five mechanical substitutions. HTML would have saved almost nothing.

So markdown stayed, and the recorded reason was corrected to the one that is true.

## The delimiter, and a claim that had to be withdrawn

`## some-key` became `<!-- block: some-key -->`.

`ARCHITECTURE.md` presented `##` as settled: chosen over YAML front matter so that
GitHub's own preview of the file stays a usable preview of the prose. Sound, but it never
considered a delimiter invisible to the preview. A comment gets the same property and
better -- the keys stop appearing in the preview as headings the real page never renders --
and it removes a trap, since `## some-name` mid-paragraph used to be swallowed as a marker.

The claim first written into `content.py` was that this frees every `#` level for a
heading. That is false and was withdrawn in the same change set. `markdown.py` emits `h3`
to `h6`, so `## foo` renders with its hashes showing, and `app.css` has no `h2` rule.
`##` is free of the *delimiter*; it is still not a heading. All three documents now say
that instead of implying an `h2` an editor cannot have.

## Three defects this turned up

**Chapter 2's lede counted an older world.** It promised "Ten organisations, two
international anchors, and one supply chain". The world serves thirteen nodes and three
trust anchors, and the chapter's own first paragraph says two supply chains. Every number
had been left behind when the legal-metrology branch and its OIML anchor arrived.

The test that guards exactly this read `chapters.js` with a regex and matched whichever
count came first in the file -- the paragraph, which was right. The lede sat two lines
above it and was never read. This is the same shape as the `must-resolve` zero in change
set 12: the number that mattered was the one nothing was looking at.

**Chapter 12 showed an HTML entity to a reader.** The step-3 hint built the holder's name
with `&rsquo;` and reaches the page through `panel()`, which sets a hint with
`textContent`, so anyone pressing "Run the exchange" saw `Verifica&rsquo;s key` spelled
out. It renders only after a click, which is why the snapshot harness never saw it. Every
other entity in the file went to an `html:` slot and was fine.

**A test was guarding nothing.** `test_there_is_a_readme_for_whoever_edits_these` asserted
`"##" in text` against the editing guide, and went on passing after the delimiter changed
because the guide's syntax table happens to contain `### Like this`. It now requires the
guide to contain a line the parser itself would accept, so the two cannot drift silently.

## And the cautions had drifted between the two copies

Change set 8's statement exists twice, on the site and in `README.md`, and three documents
say to change both. A paragraph about a reviewer was removed from `00-cautions.md` and left
standing in the README, so the repository claimed a review the site no longer mentioned.

Removed from the README too. What survives says the same thing in both places -- the site's
`correction` block and the README's closing paragraphs are now word for word identical, and
both record that a correction happened once without detailing it, which was the
load-bearing part.

A test for this was considered and rejected on evidence. Comparing each caution body,
whitespace collapsed and emphasis stripped: `spec-moving` and `no-warranty` are identical,
`no-institution` differs deliberately ("Nothing on these pages" against "Nothing here"),
`no-permanence` carries README-only navigation prose, and `nothing-validated` is 474
characters on the site against 1297 in the README. `test_the_repository_says_the_same_thing`
is right to compare headings and to say in its docstring that the words deliberately are
not. Neither subset direction catches what happened, because the README saying *more* is
normally correct. This one needed a person.

## What moved, and what did not

236 blocks across 14 files, 67 737 bytes of prose. `chapters.js` went from 2218 lines to
2024 -- a net 194, which is the honest figure: the interaction code all stays and gains
accessor calls, and what left was about a hundred and twenty paragraphs of literal prose.

Kept in code, by the rule already recorded -- move it if a reader reads it as a sentence or
a heading, leave it if it is a label, a unit, an option name or a value:

- Button, slider, field and badge labels.
- The records in `actors/` -- the eighteen failure cases, the deployment profiles, the
  harmonisation items, the portability classes. The verifier reads the same records.
- Sentences built around a value the server has just computed, where a plain-text slot
  cannot take a substitution. Where the slot accepts markup they did move, as interpolated
  blocks: `{curve}`, `{part}`, `{total}`, `{open}`, `{share}`, `{inputs}`, `{max}`,
  `{minutes}`, `{reason}`, `{outcome}`, `{travelling}`, `{baseline}`, `{residue}`,
  `{kinds}`.
- Three comparison tables -- signing-versus-encryption in chapter 1, the two signature
  comparisons in chapter 6 -- assembled as table elements. Dropping them in from a content
  file would wrap each in a div: a change in markup for no gain in editability.
- The two closing footnotes, which render straight into a `p.footnote`. Every accessor that
  returns markup wraps a block in a paragraph of its own, which would nest one inside the
  other.
- Chapter 8's group headings could not simply be read by key, because a content key has to
  be a literal at the call site and a test enforces it -- a computed key is invisible to
  the check that every key exists, and that check is what lets the others see anything. The
  two maps became a small array read by literal key.

## Two things a reader sees differently

Everything else is byte-identical. These are the whole cost:

1. `2<sup>256</sup>` became `2^256` in chapter 1. The subset has no superscript and no raw
   HTML; extending the renderer for one exponent was the alternative and was not worth it.
   One differing region in 9504 characters.
2. Four links gained `rel="noopener"` -- two in chapter 11, two in chapter 12 -- because
   the renderer adds it to every link. An improvement, and no words changed.

## Files

```
src/vcqi/web/content.py                     _BLOCK is a comment; docstring corrected
src/vcqi/web/content/chapters/*.md          12 new files; the 2 existing ones converted
src/vcqi/web/content/README.md              the editing guide, rewritten
src/vcqi/web/static/js/chapters.js          -194 lines; every chapter reads its prose
tests/test_web.py                           3 scraping tests repointed at the content layer
tests/test_content.py                       the guide test checks against the parser
CONTENT.md                                  all 14 chapters; the filename trap recorded
ARCHITECTURE.md                             the format rationale, corrected
README.md                                   the reviewer paragraph; the live URL
render.yaml                                 the hostname does not follow from `name:`
.dockerignore                               ARCHITECTURE.md excluded; stale note removed
```

`markdown.py` is untouched.

## Verification

- `uv run pytest` -- 440 passed, 46 skipped. Was 437 before; three tests were repointed and
  three added.
- `tools/chapter-snapshot.mjs` per chapter, before and after, compared with the
  100-character wrapping undone. A change of length re-aligns every following line, so a
  plain `diff` reports the whole tail and buries the one thing worth seeing; `temp/realdiff.py`
  unwraps both sides and reports only the differing regions.
- `node tools/ui-clicks.mjs` -- every control on all fourteen chapters responds. This is
  what covers the exchange log and the representation tabs, which render only after a click
  and which the snapshot harness therefore never sees.
- Against the deployed service: `/healthz` reporting the merged commit, CSP, `x-robots-tag`,
  `no-cache` on the modules and `no-store` on `/api/content`, `/docs` 404, and `/api/content`
  serving fourteen chapters with no entity in a text-only slot and no empty block.

## Git

Branches `refactor/content-block-delimiter`, `fix/readme-cautions-drift`,
`fix/record-the-live-url`, each from `develop`, each deleted after merge. PRs #32, #33, #35.

One conflict, worth recording. PR #31 landed on `develop` mid-change and added a
`CONTENT.md` table pointing at `chapters.js` line ranges for the twelve unmigrated
chapters -- accurate when written and wrong by the time it merged. Git auto-merged inside
the paragraphs and produced a hybrid opening "The words in the demonstration are moving
into markdown files. For a chapter that has one..." directly above the new delimiter: two
states of the world in one sentence. The file was taken from the branch wholesale after
checking that nothing unique was lost.

## Change set 13 - build order

- [x] **P1 - Question the format.** Audit what depends on markdown rather than HTML;
      measure the 102 inline tags; keep markdown for reasons that are true.
- [x] **P2 - The delimiter.** `<!-- block: name -->`, two files converted, byte-identical.
- [x] **P3 - Twelve chapters.** One per commit, each against a snapshot baseline.
- [x] **P4 - The helpers.** `representationPanel`, `dccTab`, `duplicationPanel` -- about
      twenty paragraphs the first chapter 6 commit had claimed and not moved.
- [x] **P5 - The three broken guards.** Repointed at the content layer; the graph one
      parametrized over both places the number appears.
- [x] **P6 - The lede.** Thirteen organisations, three anchors, two supply chains.
- [x] **P7 - Docs.** `CONTENT.md`, the editing guide, `ARCHITECTURE.md`, `content.py`.
- [x] **P8 - The cautions.** The README copy brought back into agreement.
- [x] **P9 - The live URL,** which nothing in the repository recorded.

## Change set 13 - progress log

440 tests pass, 46 skipped. Fourteen chapters render, every control responds, and the
deployed service reports the merged commit.

- **Three tests broke loudly and that is the whole reason this was caught.** All three
  scraped `chapters.js` for literals that had moved, and each asserted its own pattern
  still matched rather than passing on an empty match. A test that quietly finds nothing is
  worse than no test, and the one that did behave that way -- `"##" in text` -- is exactly
  the one that had been guarding nothing for a whole change set.
- **The over-claim is the most useful thing to have written down.** Freeing `##` from the
  delimiter felt like it should enable an `h2`, it was written into a docstring as though
  it did, and it does not. The renderer was never asked. Checking took one call to
  `render('## Like this')`.
- Migrating out of order was fine and the file names allow it, but nothing said the prefix
  is the array position rather than the chapter number -- so `01-orientation.md` being
  chapter 0 was a trap sitting in plain sight. `CONTENT.md` says it now.
- The half-finished state was defensible for one change set and stopped being so once
  `CONTENT.md` described only half of it. The lesson is not "finish migrations" but
  "a map that covers half the territory is worse than none, because it looks complete".
- One thing not done deliberately: `markdown.py` still emits `h3` and upward. Making `##`
  a heading needs an `h2` rule in `app.css` as well, and an `h2` inside a chapter body
  would sit oddly beside the page's own `h1`. The restriction on writing one stands even
  though the reason for it changed.

# Change set 14 - the PTB/DKD DCC as an external document

## Context

Two problems, both found by reading `content/chapters/07-traceability.md` against
`content/chapters/04-issuing.md`.

**1. Three sections of chapter 7 were out of scope where they sat.** *What is now said
twice*, *Including the signature* and the *A document carrying both...* paragraph are all
about wrapping a PTB/DKD DCC in a credential, but `duplicationPanel()` was appended
unconditionally outside the tab strip, so a reader on the Classical or the METAS UncLib
tab was told that "wrapping a PTB/DKD DCC in a credential duplicates most of the
certificate" while looking at something that was not one. `_step_duplication` already
returned SKIP without a DCC, so the data layer was honest and only the layout was not.

**2. Nothing said how a PTB/DKD DCC relates to the JSON claims.** It was a *passenger*:
one entry in `uncertaintyRepresentations` with `type: "CertificateRepresentation"`,
inline under `INLINE_LIMIT` and published by URL above it. Two consequences were
undocumented: the DCC is covered by `digestMultibase` but appears nowhere in the
generated JSON Schema, and the passenger model is only one of three ways to carry a
document.

So this change set scoped the three sections correctly and then built the second way - a
credential carrying a *reference* to an external DCC rather than the document - using a
real DKD example, so the trade-off is measured rather than asserted.

## Decisions taken with the user

- The three sections move **into the PTB/DKD DCC tab**.
- Build the pointer variant, from the DKD example downloaded to
  `temp/DKD-E_Widerstand_V4.xml`.
- Subject carries a **pointer plus a minimal index**, and both the chapter and the
  pipeline say what cannot be tested as a result.
- The document is a **new 100 ohm standard, pointer-only** - no readable subject anywhere.
- `ds:Signature` built for real: **Canonical XML 1.1 in-repo**, ECDSA P-256.
- The credential appears in chapter 4's document list.

## What the example turned out to be

28 123 bytes, 572 lines, and three facts shaped the work:

- **schemaVersion 3.4.0-rc.2**, not the 3.3.0 `domain/dcc.py` emits. The generator was
  left alone; the external document is carried at whatever version its issuer produced,
  which is the point of the pointer model rather than a defect in it.
- Its uncertainty is `si:valueExpandedMU`; `parse_dcc_result` reads `si:uncertainty`. So
  **the pipeline cannot parse this document** - a real incompatibility between two
  versions of one format, and the honest reason the index goes unchecked.
- It carries `dcc:statement refType="basic_isInCMC"` with `dcc:valid`/`refId`: the
  document asserts its own CMC coverage, and the credential cannot corroborate it.

**Adaptation.** Laboratory, responsible persons, customer, accreditation statement, dates
and reported uncertainty replaced with this world's fictional actors; the DKD-E 1-1
citation, both DOIs and "This is NOT a real calibration certificate!" kept, plus an
ADAPTED COPY note. The published example states U = 1e-7 ohm, which at 100 ohm is 1e-9
relative and is a placeholder rather than a measurement; it was brought to 2.5e-4 ohm,
which CMC CH-EM-0042 actually supports, rather than shipping a world containing a
certificate better than its own published capability. Nothing in the pipeline checks
that - which is the finding - so `tests/test_external_dcc.py` checks it once instead.

## What was built

### Scoping

`duplicationPanel()` is built in `representationPanel()` (already async) and passed into
`dccTab()`, which appends it below the `if (!dcc) return;` guard. `dccTab` stays
synchronous and `show()` is unchanged. The unused `api.credential` fetch in
`duplicationPanel` went at the same time, and the inline step walker became a shared
`findStep(report, id)`.

### The signature

- `crypto/xmlc14n.py` - Canonical XML 1.1. 1.1 rather than 1.0 because canonicalizing
  `ds:SignedInfo` is a document-subset operation, which is exactly where the two differ;
  on a document with no `xml:base` and no `xml:id` they agree, and a test says so.
- `crypto/xmldsig.py` - enveloped signature: the enveloped-signature transform, C14N 1.1,
  SHA-256, ECDSA P-256 through the existing RFC 6979 signer, so the bytes are identical
  on every run.

`ds:KeyInfo` carries a bare `ds:KeyValue/ECKeyValue`, not X.509: a self-signed
certificate would suggest a chain to an authority that does not exist here, and
certificate signing in `cryptography` is randomised and would break the reproducible
build. The contrast is the point - the signature verifies arithmetically and identifies
nobody.

### The credential

`external_document_credential()` in `vc/model.py`. Subject is `externalDocument` with the
format, schema version, namespace, byte count, the four index facts and a
`capabilityReference`; integrity goes in top-level `relatedResource` with both
`digestSRI` and `digestMultibase`, which is the data model's own spelling for what the
request called `checksum_external_type` / `checksum_external_value`. `digest_sri` and
`verify_digest_sri` were added to `crypto/multibase.py`.

### Verification

`REQUIRED_ACTIONS` and `_payload` gained the type and its subject member. A twelfth
top-level step, `external-document`, with four children: retrieved, digest (both
spellings), the document's own `ds:Signature`, and **index - WARN on every run**, because
the four facts are the issuer's word about a document nothing parses. `_step_scope` gained
a branch that checks measurand and unit and returns **WARN**, naming the range and the
uncertainty floor as unevaluated.

### One thing the work itself forced

The generated `outputValidation` schema rejected the new credential, and it was right to:
it required `credentialSubject.calibration` and a `CalibrationCertificateCredential`
type. The fix belonged in the schema rather than around it. What a recognition authorises
is a measurement, not a JSON shape, so `calibration_certificate_schema` grew an `anyOf`
with one branch per carrier - the carried form bounded as before, the pointer form pinned
on measurand and unit and required to carry a digest. A schema naming only the first would
have refused the second for the wrong reason: not because the institute may not do it, but
because the schema was written before it did.

## Files

```
src/vcqi/crypto/xmlc14n.py                           new - Canonical XML 1.1
src/vcqi/crypto/xmldsig.py                           new - enveloped signature
src/vcqi/crypto/multibase.py                         digest_sri, verify_digest_sri
src/vcqi/domain/dcc_examples/DKD-E-1-1-resistor.xml  new - adapted DKD example, unsigned
src/vcqi/domain/external_dcc.py                      new - load, sign, the index
src/vcqi/vc/model.py                                 external_document_credential()
src/vcqi/vc/schema.py                                anyOf, one branch per carrier
src/vcqi/vc/verify.py                                the step, the scope branch, the tables
src/vcqi/actors/scenarios.py                         issue it, publish the signed XML
src/vcqi/actors/tamper.py                            substituted-schema finds its branch
src/vcqi/web/static/js/chapters.js                   scoping, findStep, carriagePanel, the label
src/vcqi/web/content/chapters/04-issuing.md          what-is-signed
src/vcqi/web/content/chapters/07-traceability.md     carriage, verdicts, header comment
src/vcqi/web/content/chapters/10-implications.md     the DCC paragraph, and what it costs
tests/test_xmlc14n.py, test_xmldsig.py, test_external_dcc.py   new
tests/test_pipeline.py                               metas-external-dcc
README.md, ARCHITECTURE.md
```

## Change set 14 - build order

- [x] **X1 - Scope.** Duplication panel moved into `dccTab()`; header comment; dead fetch
      removed.
- [x] **X2 - Canonicalization.** `crypto/xmlc14n.py` and the specification's test cases.
- [x] **X3 - Signature.** `crypto/xmldsig.py`, deterministic, four failure modes tested.
- [x] **X4 - The document.** DKD example adapted and committed; `domain/external_dcc.py`.
- [x] **X5 - The credential.** `external_document_credential()`; issued in `scenarios.py`.
- [x] **X6 - Verification.** The `external-document` step, the `_step_scope` branch, the
      `REQUIRED_ACTIONS` and `_payload` entries, the schema `anyOf`.
- [x] **X7 - Chapters.** The label, chapter 4's block, chapter 7's carriage panel,
      chapter 10's paragraph.
- [x] **X8 - Tests and docs.** Three new test files, README, ARCHITECTURE, the step count.

## Change set 14 - progress log

Complete. 504 tests pass, 46 skipped. Every control on all fourteen chapters responds,
and the world still builds byte-identically across 78 documents.

- Chapter 7's duplication and signature sections now appear only under the PTB/DKD DCC
  tab, which is where the `dcc` prose already was.
- The world carries a twelfth credential, `metas-external-dcc`, which points at a signed
  PTB/DKD DCC 3.4.0-rc.2 instead of carrying one.
- Canonical XML 1.1 and enveloped XML signatures are implemented in-repo, the same way
  RFC 8785 already was and for the same reason.

### What the pointer credential actually verifies as

| Step | Verdict | Why |
| --- | --- | --- |
| proof, recognition, action, status | pass | ordinary; a new type is authorised like any other |
| output-validation | pass | after the schema learned the second carrier |
| external-document.digest | pass | both digest spellings match the published bytes |
| external-document.xml-signature | pass | and the key it carries names nobody |
| **scope** | **warn** | measurand and unit only; range and uncertainty floor unreachable |
| **external-document.index** | **warn** | four facts the issuer asserts, checked against nothing |
| uncertainty, traceability | skip | no budget and no chain, because neither is in the credential |

**And the outcome is `verified`.** Nothing failed, so nothing rejected it. That pairing -
a verified verdict beside two warnings saying the measurement was never examined - is the
single most useful thing the comparison shows, and `test_a_verified_verdict_here_carries_two_warnings`
asserts it so it cannot quietly stop being true. Making `outcome` report a third value
when a step warns would be defensible and was not done: it would change every caller for
one credential, and the step tree already says it.

### What could not be verified, and is recorded rather than glossed

No independent XML Signature implementation is installed on this machine - `xmlsec` and
`lxml` both need native builds - so nothing here establishes interoperability.
Conformance rests on the specification's own published test cases, transcribed into
`tests/test_xmlc14n.py`, and on round-tripping against our own verifier; a systematic
error shared by signer and verifier would pass the whole suite. That is weaker evidence
than the RFC 8785 vectors give for JCS. The cheapest way to close it is to hand a signed
document to someone who has `xmlsec1` on the command line.

### Verified

- `uv run pytest` - 504 passed, 46 skipped.
- `python -m vcqi.actors.scenarios --dump` twice - byte-identical across 78 documents,
  the enveloped XML signature included, which is what RFC 6979 is doing there.
- `node tools/ui-clicks.mjs` - every control on every chapter responds; chapter 4 went
  from 13 controls to 14 with the new document in the picker.
- Not verified visually. The layout of the carriage panel has not been seen in a browser.

# Change set 15 - the object the chain is about

## Context

A colleague proposed a "special-purpose VC passport" per measurement standard. Reviewed
against the repository, most of the sketch is already the demonstrator: the recognition
chain, the traceability links by content digest, the accreditation half reaching Global
ACI, and - since change set 14 - the choice between carrying a PTB/DKD DCC and pointing
at one.

One part was genuinely new, and reviewing it exposed a hole worth closing on its own.

**The chain was held together by credential digests alone.** A laboratory certificate
carries `traceableTo: {id, digestMultibase, instrument}`. The verifier followed the id,
checked the digest, and re-ran the whole pipeline on the parent - but `vc/verify.py`
contained no occurrence of the word "instrument". So "the transfer standard I used is the
standard the institute calibrated" was asserted by the laboratory and checked by nobody. A
verifier could walk the chain end to end without establishing that it concerned one
physical object.

## Part A - the check that needs no passport (built)

`traceability.object-identity`, a child of each traceability hop. Where a reference names
an object, it is compared against the subject of the certificate it points at. A reference
that names none reports **skip**, not pass: most references in this world carry no
instrument, and a passing verdict would claim a check that never ran.

`traceability-names-another-object` is the failure case that exists only because of it:
the laboratory references the institute's real, unaltered certificate and names a
different resistor - one the institute really did calibrate, just not in the certificate
being referenced. Nineteen cases now.

### Why it is worth having, stated as the tests state it

Everything else about that certificate still passes. Proof, validity, status,
recognition, scope, the digest of the reference, **and the inherited uncertainty**, which
reconciles line by line because the numbers were copied from the certificate that really
was referenced. Only the object is wrong, and until now only the reader would have
noticed.

### The honest limit

The identifier compared is a URN minted in `domain/instruments.py`, agreed only because
one author wrote both ends - the same weakness `tests/test_harmonisation.py` already pins
for measurands. Two organisations would need a shared way to name a physical artefact
before the check means anything between them. That is governance, not engineering, and
`ARCHITECTURE.md` says so beside the check.

## Part B - the passport (designed, not built)

The design rule that keeps a passport from competing with a certificate: **it states
nothing a certificate states.** Identity only - what the object is, who keeps it, what it
is for - and no value, no Expanded Uncertainty, no coverage factor, no budget. The two
then have no overlapping claims and cannot disagree, which is the failure
`uncertainty.duplication` exists to catch elsewhere.

The move is the one chapter 6 already makes for the PTB/DKD DCC: Classical, UncLib and GTC
describe a *result*, a DCC describes a *document*, a passport would describe an *object*.
`ARCHITECTURE.md`'s "a calibration certificate is a statement about that object on that
day" stays true and is complemented rather than contradicted.

**Links would point upward.** A passport listing its calibrations must be reissued on
every one, which is where supersession, versioning and the append-only-log problem come
from. Each certificate naming its passport instead - the way `issuer.recognizedIn` points
up at the recognition that contextualises it - means issuing a certificate never touches
the passport. No subject index, no supersession relation, no reissue.

Not built pending a decision, because Part A banks most of the practical benefit without
introducing a credential type, a vocabulary, or any reframing of a chapter.

## Impact on the rest of the site, checked rather than assumed

- **The trust graph does not change, and should not.** `_graph()` builds edges from a
  hardcoded list of eleven credential names, not from everything issued. A passport has no
  natural edge anyway: nodes come from `ACTORS` and a passport's target is an object URN
  rather than a party. Chapter 3 keeps meaning "who recognises and issues to whom".
- **Chapter 3's introduction is unaffected** - it counts organisations, and none is added.
- **Chapter 5's introduction was already imprecise** and is corrected here: it said "It
  runs eleven checks", which is true of the conformity certificate but not of the external
  document credential added in change set 14, which gets twelve.
- **Chapters 11 and 13 self-update** - their figures are computed or interpolated, with no
  digits written into the prose.
- **`README.md` was stale**: "write all 76 documents" became 78 after change set 14. The
  other 76 turned out to be a retrieval count rather than a document count and was correct
  but loosely worded; it now says 76 retrievals across 31 distinct documents.
- **`ARCHITECTURE.md` said "thirteen failure cases"**, which had been wrong for two change
  sets. Rephrased without a number so it cannot rot again.

## Files

```
src/vcqi/vc/verify.py                              _step_object_identity, attached per hop
src/vcqi/actors/tamper.py                          traceability-names-another-object
src/vcqi/web/content/chapters/09-break.md          Eighteen -> Nineteen
src/vcqi/web/content/chapters/05-verification.md   the step count, corrected
tests/test_pipeline.py                             TestObjectIdentity
README.md, ARCHITECTURE.md
```

Reused rather than rebuilt: the already-fetched and digest-checked parent inside
`_step_traceability`, so the check adds a comparison rather than a retrieval; `_resign`
and `_republish` for the failure case.

## Change set 15 - build order

- [x] **P1 - The hole.** `traceability.object-identity` plus the failure case.
- [ ] **P2 - The credential.** `instrument_passport_credential()` and `subjectPassport`.
- [ ] **P3 - The world.** The national standard as an object; two passports issued.
- [ ] **P4 - The check.** `traceability.passport`, and the three-way identity.
- [ ] **P5 - The chapter.** The section, the panel, the labels.
- [ ] **P6 - Tests and docs.**

## Change set 15 - progress log

Part A complete. 511 tests pass, 46 skipped; the world still builds byte-identically
across 78 documents.

- The real chain passes: the laboratory's reference names
  `urn:instrument:callab:standard-resistor:SR10K-0042` and the institute's certificate is
  about that object.
- The test report's equipment reference names no object and reports skip, which is the
  honest answer and not a pass.
- The new failure case is caught by `traceability.object-identity` and by nothing else.
  `test_the_inherited_uncertainty_still_reconciles` is the one worth reading: the
  arithmetic is untouched, because the numbers were copied from the certificate that
  really was referenced.

Part B designed and deliberately not built; see above.
