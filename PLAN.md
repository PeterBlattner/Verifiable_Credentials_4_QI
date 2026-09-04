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
