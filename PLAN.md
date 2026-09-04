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

# Change set 3 - legal metrology

Change sets 1 and 2 are built, tested and pushed (`main` and `develop` at `97f6b25`,
176 tests). This plan adds the third pillar of the quality infrastructure.

## Context

The demonstration so far covers two of the three pillars: metrology (BIPM, CMCs,
traceability) and accreditation (Global ACI, ISO/IEC 17025 scopes). **Legal metrology**
is the third, and it does not work like either of them.

`temp/legal_metrology_overview.md` §8 gives the architecture. Three points from it drive
the whole design:

**OIML is not a trust anchor.** An OIML Recommendation is not law, and §1 is explicit
that *"an OIML certificate does not automatically constitute national legal approval"*.
Legal force comes from national or regional legislation. So OIML sits at the
international layer beside the BIPM and Global ACI while being categorically different
from them, and the demo has to be able to *show* that rather than assert it.

**Verification is not calibration** (§6). A calibration answers "what is the error, and
with what uncertainty" and produces metrological information. A verification answers
"does this comply, yes or no" and produces a **legal conformity decision**. This is the
single most important conceptual point, and it means a new credential type whose subject
is a decision rather than a measurement.

**Delegating verification does not privatise regulation** (§7). A private body may
verify; authorisation, supervision and enforcement stay public. That maps exactly onto a
`RecognizedEntityCredential` with `action: "verify"` — no new mechanism needed, which is
itself worth showing.

The two systems join where §6 says they do: *"verification normally relies on calibrated
and traceable reference standards"*. The verification body's reference weights are
calibrated by the institute, so its verification certificate references a calibration
certificate and the legal branch hangs off the existing traceability chain.

Decisions taken with the user: METAS holds both roles; the legislator becomes a third
trust anchor; all four failure cases; one filterable graph.

## What gets added

### Actors (four new, fourteen total)

| DID | Role | Branch |
| --- | --- | --- |
| `did:web:oiml.example` | International legal metrology organisation. Publishes Recommendations, runs the OIML-CS. **Deliberately not a trust anchor.** | legal |
| `did:web:legislator.example` | The metrology ordinance that confers legal force. **Third trust anchor.** | legal |
| `did:web:verifybody.example` | Gotthard Verification Services AG, an authorised private verification body | legal |
| `did:web:retailer.example` | Bergblick Delikatessen GmbH, which operates the scale | legal |

**METAS gains its second role.** Its `role` becomes *National metrology institute and
legal metrology authority*, which is the Swiss reality and §3's "same organization"
model. The demonstration this unlocks: one issuer, two kinds of credential, two entirely
unrelated chains upward — its calibration certificates reach the BIPM, its type approvals
reach the legislator, and neither route substitutes for the other.

**PTB gains a second hat too**, as an OIML-CS Issuing Authority recognised by OIML. Same
point at the international layer, and it reuses an actor rather than adding one.

`did:web:surveillance.example` is broadened to cover in-service metrological supervision
as well as border product-conformity checks. §8 is explicit that the boxes in its diagram
"do not necessarily correspond to different organizations", so one supervisory actor with
two functions is faithful rather than a shortcut.

### Credentials (seven new)

Four reuse existing machinery unchanged; three are new types.

| Name | Type | Says |
| --- | --- | --- |
| `oiml-recognition` | `RecognizedEntityCredential` | OIML recognises PTB as an OIML-CS Issuing Authority for R 76 |
| `legislator-recognition` | `RecognizedEntityCredential` | the ordinance makes METAS competent, with actions `approve` and `designate` |
| `metas-designation` | `RecognizedEntityCredential` | METAS designates the verification body, `action: "verify"`, scoped to class III up to 30 kg |
| `metas-weight-calibration` | `CalibrationCertificateCredential` | METAS calibrates the 5 kg reference weight, under a new mass CMC |
| `oiml-certificate` | `OimlCertificateCredential` | PTB type-evaluates the scale design. Carries `legalEffect: "none"` explicitly |
| `type-approval` | `TypeApprovalCredential` | METAS approves the type for use in Switzerland, citing the OIML certificate as evidence |
| `verification-certificate` | `VerificationCertificateCredential` | the conformity decision on one scale in one shop |

The verification certificate is the heart of it:

```json
"verification": {
  "kind": "subsequent",
  "performedOn": "2026-07-14",
  "accuracyClass": "III",
  "maximumCapacity": 15.0, "unit": "kg",
  "verificationScaleInterval": 0.005,
  "legalBasis": { type approval, by id and digest },
  "testPoints": [
    { "load": 2.5, "indicationError": 0.002, "maximumPermissibleError": 0.005,
      "expandedUncertainty": 0.0010, "coverageFactor": 2, "verdict": "pass" }, ...
  ],
  "decision": "pass",
  "decisionRule": "OIML R 76: |error| <= MPE, and U <= MPE/3",
  "verificationMark": { seal identifier, applied date },
  "validUntil": "2028-07-31",
  "referenceStandards": [ { calibration certificate, by id and digest } ]
}
```

### The instrument, and real numbers

A retail scale, OIML R 76 accuracy class III, Max 15 kg, e = 5 g, so n = 3000 (class III
allows 500 to 10000). In-service MPE is twice the initial-verification MPE, which in
terms of `e` is ±0.5 e up to 500 e, ±1.0 e to 2000 e, ±1.5 e to 10000 e. Test points at
2.5, 5, 10 and 15 kg therefore carry in-service MPEs of 5, 10, 10 and 15 g, and the
observed errors of 2, 3, −4 and 6 g all pass with margin.

`U = 1.0 g` at every point, dominated by the resolution and repeatability of the scale
rather than by the reference weights — which is the honest picture and quietly makes a
point: the traceability chain matters even where the reference contributes almost
nothing. A new CMC entry `CH-M-0015` covers METAS for mass, 1 mg to 20 kg, giving about
0.13 mg at 5 kg.

### A new pipeline step: `conformity`

Twelve top-level steps rather than eleven, skipped for everything that is not a
verification certificate. Three children:

| Check | Decides |
| --- | --- |
| `conformity.decision` | every test point verdict follows from &#124;error&#124; ≤ MPE, and the overall decision follows from the points |
| `conformity.uncertainty` | `U ≤ MPE/3` at every point, the rule that makes a verification defensible |
| `conformity.type-approval` | the cited legal basis is a type approval valid in the stated jurisdiction, and not merely type-evaluation evidence |

The second is where the uncertainty work from change set 2 does real duty rather than
being decorative, and the third is what catches an OIML certificate doing a job it cannot
do.

### Four failure cases, in a new `legal` group

| Case | Caught by | Why it is new |
| --- | --- | --- |
| `oiml-is-not-approval` | `conformity.type-approval` | every signature is valid and the OIML certificate is genuine; it simply has no legal effect. Valid credential, wrong legal force — a category the existing twelve do not cover |
| `mpe-exceeded-but-passed` | `conformity.decision` | the legal counterpart of the CMC check: the decision must follow from the numbers |
| `verification-uncertainty-too-large` | `conformity.uncertainty` | worn reference weights give `U > MPE/3`; the decision may be right and is not defensible |
| `outside-designation` | `action` | genuinely designated, correctly signed, wrong accuracy class |

### Chapter 7, and the graph

A new chapter, *Legal metrology: a different kind of decision*, between dependencies and
Break it; Break it and the argument become 8 and 9.

It opens with §6 side by side — the same instrument, a calibration reporting
`error +0.7 g, U = 0.2 g` and a verification reporting `MPE ±1.0 g, observed +0.7 g →
PASS` — then walks the layered architecture, then the conformity decision with its test
points, then §7 on delegation without privatisation.

The graph gains a third edge kind, `authority`, and three filter chips for the metrology,
accreditation and legal branches, all lit by default. Every actor and edge carries a
`branch`. The canvas widens to roughly 1280 × 560.

## Files

```
src/vcqi/domain/legal.py          new: DesignationScope, the R 76 MPE table, evaluate_conformity
src/vcqi/domain/kcdb.py           the mass CMC CH-M-0015
src/vcqi/domain/instruments.py    the scale and the 5 kg reference weight
src/vcqi/actors/registry.py       four actors, the third anchor, branch tags, METAS dual role
src/vcqi/actors/scenarios.py      seven credentials, three status lists
src/vcqi/actors/tamper.py         four cases in a new legal group
src/vcqi/vc/model.py              oiml_certificate_credential, type_approval_credential,
                                  verification_certificate_credential
src/vcqi/vc/verify.py             the conformity step; _payload and _traceability_references
                                  learn about verification, typeApproval and referenceStandards;
                                  REQUIRED_ACTIONS gains verify, approve
src/vcqi/web/app.py               branch tags on graph edges, /api/conformity for the chapter
src/vcqi/web/static/js/graph.js   layout, the authority edge kind, branch filtering
src/vcqi/web/static/js/chapters.js  chapter 7
tests/test_legal.py               new
README.md, ARCHITECTURE.md
```

Reused rather than rebuilt: `recognized_entity_credential` and `recognized_action` for
both the designation and the OIML recognition; `calibration_certificate_schema` generates
the mass schema from the new CMC with no change; `_step_scope_by_method` already handles
a scope expressed as a list of methods, which is what a designation is;
`credential_reference` for every legal-basis and reference-standard link.

## Verification

- `uv run pytest` — 176 existing plus roughly 25 new. Specifically: the R 76 MPE table
  against values computed by hand at each class III breakpoint; a decision recorded as
  PASS with a point over the MPE is rejected; `U > MPE/3` is rejected; the OIML
  certificate verifies as a credential *and* fails as a legal basis; all sixteen tamper
  cases caught by the step each names.
- Chain assertions: the type approval reaches `did:web:legislator.example` and never the
  BIPM; the weight calibration reaches the BIPM and never the legislator; the OIML
  certificate reaches OIML, which is not an anchor, so it fails when trusted anchors are
  the inspector's three.
- `uv run vc-demo`, then chapter 7 and the graph filters.
- Headless render of all ten chapters against the live server.
- `python -m vcqi.actors.scenarios --dump` twice, byte-identical.

## Git

Branch from `develop`, per the standards:

```
git switch -c feature/legal-metrology develop
```

Two commits — the actors and graph, then the legal credentials and the conformity check.
`temp/` is already in `.gitignore`, so the source overview stays out of the repository;
that `.gitignore` change is currently uncommitted and will go in with the first commit.
Nothing pushed without asking.

## Change set 3 - build order

- [x] **L1 - Domain.** `domain/legal.py` with the R 76 MPE table, DesignationScope and
      evaluate_conformity; the mass CMC CH-M-0015; the scale and the reference weight.
- [x] **L2 - Actors and graph.** Four actors, third trust anchor, branch tags, METAS dual
      role, PTB as OIML Issuing Authority, graph layout and filters.
- [x] **L3 - Credentials.** Three new builders in `vc/model.py`; seven credentials and
      three status lists in `scenarios.py`.
- [x] **L4 - Verification.** The conformity step and its three children; `_payload` and
      `_traceability_references` learn the new members; REQUIRED_ACTIONS.
- [x] **L5 - Failure cases.** Four cases in a new legal group.
- [x] **L6 - Chapter 7 and the web.** `/api/conformity`, chapter 7, renumbering.
- [x] **L7 - Tests and docs.** `tests/test_legal.py`, README, ARCHITECTURE.

## Change set 3 - progress log

Complete. 225 tests pass, 1 skipped (GTC not installed). All ten chapters render.

- 14 actors, 4 trust anchors, 26 credentials, 84 documents, 17 failure cases.
- The legal branch rests on the calibration chain: the reference weight the verification
  body weighs with is calibrated by the institute under a new mass CMC, and the
  verification certificate references that certificate by content digest.

### Three things the pipeline caught while this was being written

- **A designation is not an accreditation.** REQUIRED_ACTIONS mapped one action per
  credential type, but an accreditation body accredits and a legal metrology authority
  designates, and both produce a RecognizedEntityCredential. It now takes a set per type.
- **Status entries must match the purpose of the list they point into.** A designation is
  suspended and a certificate is revoked, and the two cannot share one bitstring.
- **Dating the OIML and ordinance recognitions from 2026** alongside Global ACI made the
  action check reject a type approval issued in 2024, correctly. The legal layer predates
  Global ACI and now has its own timeline.

### One modelling error corrected

OIML was initially left out of the trust anchors on the reasoning that it confers no
legal force. That conflates two questions: reaching OIML establishes technical type
evaluation perfectly well, and a national authority relying on OIML evidence is what the
certification system is for. What it does not establish is legal force. OIML is now an
anchor, and the distinction is enforced in conformity.legal-basis, which looks at what
the cited document is rather than at who vouches for its issuer.

### Verified

- `uv run pytest` - 225 passed, 1 skipped.
- All 17 failure cases caught by the step each names; the four legal ones pass proof,
  validity, status and recognition first.
- Chain assertions: the type approval reaches the legislator, the weight calibration
  reaches the BIPM, the OIML certificate reaches OIML and cannot serve as a legal basis.
- All ten chapters rendered headlessly against the live server with no console errors.
- `--dump` twice gives byte-identical output across all 84 documents.
