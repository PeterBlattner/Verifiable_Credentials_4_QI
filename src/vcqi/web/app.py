"""The FastAPI application that serves the demonstrator.

One process plays every part. The same routes that the browser calls are the routes a
verifier would call in a real deployment: a DID document is served where did:web says
it should be, a CMC entry is served from the registry that publishes it, and a status
list is served from the issuer that maintains it. Nothing is faked at the transport
level, which means the retrieval log the interface shows is a real account of what the
verifier had to go and get.

The world is built once at import and cached. Building it is deterministic, so a
reload produces identical documents and the interface can be refreshed without the
signatures changing underneath it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from vcqi.actors.registry import ACTORS, TRUST_ANCHORS, actor_by_did, did_document
from vcqi.actors.scenarios import DEMO_NOW, World, build_world
from vcqi.actors.tamper import TAMPER_CASES, tamper_by_key
from vcqi.config import DEFAULT_HOST, DEFAULT_PORT
from vcqi.crypto.dataintegrity import ProofTrace
from vcqi.domain.accreditation import ACCREDITATION_SCOPES
from vcqi.domain.kcdb import CMC_ENTRIES, cmc_by_id
from vcqi.domain.scope import MeasurementClaim, evaluate_scope
from vcqi.domain.uncertainty import evaluate, from_expanded_uncertainty, normal, rectangular
from vcqi.vc.checks import credential_types, issuer_id
from vcqi.vc.verify import verify_credential

STATIC_ROOT = Path(__file__).parent / "static"

app = FastAPI(
    title="Verifiable Credentials for the quality infrastructure",
    description=(
        "An interactive demonstration of W3C Verifiable Credentials and Recognized "
        "Entities applied to metrology, accreditation and conformity assessment. "
        "Every organisation, certificate and key in it is fictional."
    ),
    version="0.1.0",
)


@lru_cache(maxsize=1)
def world() -> World:
    """Return the demonstration world, building it on first use.

    Returns:
        The populated world.
    """
    return build_world()


def _parse_when(value: str | None) -> datetime:
    """Read the instant to verify against from a request.

    Args:
        value: An ISO 8601 timestamp, or None for the demonstration default.

    Returns:
        The instant, in UTC.

    Raises:
        HTTPException: If the value cannot be parsed.
    """
    if not value:
        return DEMO_NOW
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=f"cannot read {value!r} as a date") from error
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def _trace_to_json(trace: ProofTrace) -> dict[str, Any]:
    """Render a signing trace for the interface.

    Args:
        trace: The trace to render.

    Returns:
        Every intermediate value, so the reader can follow the signature being formed.
    """
    return {
        "proofConfig": trace.proof_config,
        "canonicalProofConfig": trace.canonical_proof_config,
        "proofConfigHash": trace.proof_config_hash,
        "canonicalDocument": trace.canonical_document,
        "documentHash": trace.document_hash,
        "signingInput": trace.signing_input,
        "proofValue": trace.proof_value,
    }


def _graph() -> dict[str, Any]:
    """Derive the trust graph from the credentials that were actually issued.

    The edges are read out of the documents rather than written down separately, so the
    picture cannot drift away from what the credentials say.

    Returns:
        Nodes and edges for the interface to draw.
    """
    current = world()
    edges: list[dict[str, Any]] = []

    for name in ("bipm-recognition", "global-aci-recognition", "sas-recognition"):
        credential = current.credential(name)
        source = issuer_id(credential)
        subjects = credential.get("credentialSubject", [])
        subjects = [subjects] if isinstance(subjects, dict) else subjects
        for entry in subjects:
            actions = entry.get("recognizedTo", [])
            actions = [actions] if isinstance(actions, dict) else actions
            edges.append(
                {
                    "source": source,
                    "target": entry.get("id"),
                    "kind": "recognition",
                    "label": ", ".join(sorted({str(a.get("action")) for a in actions})),
                    "credential": name,
                    "credentialId": credential["id"],
                }
            )

    issuance = [
        ("metas-calibration", "owner", "calibration certificate"),
        ("callab-calibration", "owner", "calibration certificate"),
        ("testlab-report", "client", "test report"),
        ("cab-conformity", "holder", "certificate of conformity"),
    ]
    for name, member, label in issuance:
        credential = current.credential(name)
        subject = credential.get("credentialSubject", {})
        recipient = subject.get(member, {}) if isinstance(subject, dict) else {}
        edges.append(
            {
                "source": issuer_id(credential),
                "target": recipient.get("id"),
                "kind": "issuance",
                "label": label,
                "credential": name,
                "credentialId": credential["id"],
            }
        )

    edges.append(
        {
            "source": "did:web:manufacturer.example",
            "target": "did:web:surveillance.example",
            "kind": "presentation",
            "label": "presents at the border",
            "credential": "cab-conformity",
            "credentialId": current.credential("cab-conformity")["id"],
        }
    )

    return {
        "nodes": [actor.to_json() for actor in ACTORS],
        "edges": edges,
        "trustAnchors": sorted(TRUST_ANCHORS),
    }


@app.get("/api/world")
def get_world() -> dict[str, Any]:
    """Return everything the interface needs to render the demonstration.

    Returns:
        The trust graph, the credential index, the registries and the failure cases.
    """
    current = world()
    credentials = []
    for name, credential in current.credentials.items():
        types = [t for t in credential_types(credential) if t != "VerifiableCredential"]
        credentials.append(
            {
                "name": name,
                "id": credential["id"],
                "type": types[0] if types else "VerifiableCredential",
                "title": credential.get("name") or credential.get("description", name),
                "issuer": issuer_id(credential),
                "validFrom": credential.get("validFrom"),
                "validUntil": credential.get("validUntil"),
            }
        )

    return {
        "graph": _graph(),
        "credentials": credentials,
        "cmcEntries": [entry.to_json() for entry in CMC_ENTRIES],
        "accreditations": [scope.to_json() for scope in ACCREDITATION_SCOPES],
        "tamperCases": [case.to_json() for case in TAMPER_CASES],
        "demoNow": DEMO_NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "documentCount": len(current.store.contents()),
    }


@app.get("/api/actor/{did:path}")
def get_actor(did: str) -> dict[str, Any]:
    """Return one organisation with its DID document and the credentials it touches.

    Args:
        did: The actor identifier.

    Returns:
        The organisation, its DID document, and what it issued and holds.

    Raises:
        HTTPException: If the identifier is not one of the demonstration actors.
    """
    actor = actor_by_did(did)
    if actor is None:
        raise HTTPException(status_code=404, detail=f"no actor {did}")

    current = world()
    issued = [
        {"name": name, "id": credential["id"], "title": credential.get("name", name)}
        for name, credential in current.credentials.items()
        if issuer_id(credential) == did
    ]
    return {
        "actor": actor.to_json(),
        "didDocument": did_document(did),
        "issued": issued,
    }


@app.get("/api/credential/{name}")
def get_credential(name: str) -> dict[str, Any]:
    """Return one signed credential together with the trace of how it was signed.

    Args:
        name: Short name of the credential.

    Returns:
        The credential and its signing trace.

    Raises:
        HTTPException: If no credential is registered under that name.
    """
    current = world()
    if name not in current.credentials:
        raise HTTPException(status_code=404, detail=f"no credential {name}")
    result = current.results.get(name)
    return {
        "name": name,
        "credential": current.credentials[name],
        "trace": _trace_to_json(current.traces[name]),
        "measurement": (
            {
                "value": result.value,
                "standardUncertainty": result.standard_uncertainty,
                "expandedUncertainty": result.expanded_uncertainty,
                "coverageFactor": result.coverage_factor,
                "relativeExpandedUncertainty": result.relative_expanded_uncertainty,
                "unit": result.unit,
                "reported": result.format(),
                "budget": [
                    {
                        "label": line.label,
                        "value": line.value,
                        "unit": line.unit,
                        "standardUncertainty": line.standard_uncertainty,
                        "distribution": line.distribution,
                        "sensitivityCoefficient": line.sensitivity_coefficient,
                        "uncertaintyContribution": line.uncertainty_contribution,
                        "index": line.index,
                        "source": line.note,
                    }
                    for line in result.budget
                ],
            }
            if result is not None
            else None
        ),
    }


@app.get("/api/document")
def get_document(url: str = Query(..., description="Address of the document")) -> Any:
    """Return whatever is published at an address.

    This is the route the interface uses to let a reader follow any reference in any
    credential, exactly as the verifier does.

    Args:
        url: The address to retrieve.

    Returns:
        The published document.

    Raises:
        HTTPException: If nothing is published there.
    """
    document = world().store.get(url)
    if document is None:
        raise HTTPException(status_code=404, detail=f"nothing published at {url}")
    return JSONResponse(
        {"url": url, "kind": world().store.kind_of(url), "document": document}
    )


class VerifyRequest(BaseModel):
    """A request to verify one credential under stated conditions.

    Attributes:
        name: Short name of a credential from the world, when verifying one of those.
        credential: A credential supplied directly, which takes precedence over name.
        when: The instant to verify against, as an ISO 8601 timestamp.
        trusted: Identifiers the verifier trusts directly.
        staple: Whether the holder bundles the recognition credentials it depends on.
        max_depth: How many recognition credentials the verifier will follow.
    """

    name: str | None = None
    credential: dict[str, Any] | None = None
    when: str | None = None
    trusted: list[str] | None = None
    staple: bool = False
    max_depth: int = Field(default=5, ge=0, le=10)


@app.post("/api/verify")
def post_verify(request: VerifyRequest) -> dict[str, Any]:
    """Verify a credential and return the full step-by-step report.

    Args:
        request: What to verify and under what conditions.

    Returns:
        The verification report.

    Raises:
        HTTPException: If neither a known name nor a credential was supplied.
    """
    current = world()
    if request.credential is not None:
        credential = request.credential
    elif request.name and request.name in current.credentials:
        credential = current.credentials[request.name]
    else:
        raise HTTPException(status_code=400, detail="supply a known name or a credential")

    trusted = frozenset(request.trusted) if request.trusted is not None else TRUST_ANCHORS
    presented = (
        [
            current.credential(name)
            for name in ("bipm-recognition", "global-aci-recognition", "sas-recognition")
        ]
        if request.staple
        else []
    )

    report = verify_credential(
        credential,
        store=current.store,
        now=_parse_when(request.when),
        trusted_issuers=trusted,
        presented=presented,
        max_depth=request.max_depth,
    )
    return report.to_json()


@app.post("/api/tamper/{key}")
def post_tamper(key: str) -> dict[str, Any]:
    """Apply one failure case and verify the result.

    Args:
        key: Identifier of the case.

    Returns:
        The case, the resulting credential, the report, and whether the step that was
        supposed to catch it did.

    Raises:
        HTTPException: If the case is unknown.
    """
    case = tamper_by_key(key)
    if case is None:
        raise HTTPException(status_code=404, detail=f"no failure case {key}")

    result = case.apply()
    report = verify_credential(
        result.credential,
        store=result.world.store,
        now=result.verify_at,
        trusted_issuers=TRUST_ANCHORS,
    )
    failures = [step.id for step in report.failures]
    return {
        "case": case.to_json(),
        "credential": result.credential,
        "report": report.to_json(),
        "caughtByExpectedStep": case.expected_step in failures,
        "failedSteps": failures,
    }


class ScopeRequest(BaseModel):
    """A request to check a hypothetical result against a published capability.

    Attributes:
        cmc: Identifier of the CMC entry to check against.
        value: The measured value, in the unit of the entry.
        expanded_uncertainty: The Expanded Uncertainty U claimed.
        coverage_factor: The coverage factor k the claim is stated at.
        measurand: The measurand claimed.
    """

    cmc: str = "CH-EM-0042"
    value: float
    expanded_uncertainty: float
    coverage_factor: float = 2.0
    measurand: str = "dc.resistance"


@app.post("/api/scope")
def post_scope(request: ScopeRequest) -> dict[str, Any]:
    """Adjudicate a hypothetical claim against a published capability.

    This is what drives the sliders: move the level or the claimed uncertainty and the
    verdict, and with it the legitimacy of the CIPM MRA logo, changes live.

    Args:
        request: The claim to check.

    Returns:
        The verdict with every condition evaluated, and the uncertainty floor at that
        level for plotting.

    Raises:
        HTTPException: If the CMC entry is unknown.
    """
    entry = cmc_by_id(request.cmc)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"no CMC entry {request.cmc}")

    capability = entry.as_capability()
    claim = MeasurementClaim(
        measurand=request.measurand,
        unit=entry.unit,
        value=request.value,
        expanded_uncertainty=request.expanded_uncertainty,
        coverage_factor=request.coverage_factor,
    )
    verdict = evaluate_scope(capability, claim)
    return {
        "verdict": verdict.to_json(),
        "withinScope": verdict.within_scope,
        "mraLogoJustified": verdict.within_scope,
        "uncertaintyFloor": entry.uncertainty_floor.evaluate(request.value),
        "floorDescription": entry.uncertainty_floor.describe(entry.unit),
        "entry": entry.to_json(),
    }


class BudgetRequest(BaseModel):
    """A request to recompute the laboratory budget with adjusted contributions.

    Attributes:
        parent_expanded_uncertainty: U from the certificate of the institute, in ohm.
        ratio_uncertainty: Standard Uncertainty of the bridge ratio, dimensionless.
        drift_half_width: Half-width of the drift interval, in ohm.
        temperature_half_width: Half-width of the temperature interval, in ohm.
    """

    parent_expanded_uncertainty: float = 0.0011313708498984759
    ratio_uncertainty: float = 2.6e-6
    drift_half_width: float = 5.0e-4
    temperature_half_width: float = 2.0e-4


@app.post("/api/uncertainty")
def post_uncertainty(request: BudgetRequest) -> dict[str, Any]:
    """Recompute the budget of the accredited laboratory with adjusted inputs.

    Args:
        request: The contributions to use.

    Returns:
        The recomputed result with its budget, and whether it stays inside the
        accreditation of the laboratory.
    """
    result = evaluate(
        lambda q: q["transfer_standard"] * q["ratio"] + q["drift"] + q["temperature"],
        [
            from_expanded_uncertainty(
                "transfer_standard",
                "Transfer standard, from the certificate of the institute",
                10000.0012,
                request.parent_expanded_uncertainty,
                unit="ohm",
            ),
            normal("ratio", "Resistance bridge ratio", 1.0000031, request.ratio_uncertainty),
            rectangular("drift", "Drift since calibration", 0.0, request.drift_half_width, unit="ohm"),
            rectangular(
                "temperature", "Temperature correction", 0.0, request.temperature_half_width, unit="ohm"
            ),
        ],
        unit="ohm",
    )

    scope = next(s for s in ACCREDITATION_SCOPES if s.identifier == "SCS 0123")
    capability = scope.as_capability()
    assert capability is not None
    verdict = evaluate_scope(
        capability,
        MeasurementClaim("dc.resistance", "ohm", result.value, result.expanded_uncertainty, 2.0),
    )

    return {
        "value": result.value,
        "standardUncertainty": result.standard_uncertainty,
        "expandedUncertainty": result.expanded_uncertainty,
        "relativeExpandedUncertainty": result.relative_expanded_uncertainty,
        "coverageFactor": result.coverage_factor,
        "unit": result.unit,
        "reported": result.format(),
        "budget": [
            {
                "label": line.label,
                "standardUncertainty": line.standard_uncertainty,
                "unit": line.unit,
                "distribution": line.distribution,
                "sensitivityCoefficient": line.sensitivity_coefficient,
                "uncertaintyContribution": line.uncertainty_contribution,
                "index": line.index,
            }
            for line in result.budget
        ],
        "withinAccreditation": verdict.within_scope,
        "bestMeasurementCapability": capability.uncertainty_floor.evaluate(result.value),
    }


@app.get("/")
def index() -> FileResponse:
    """Serve the single page that hosts the demonstration.

    Returns:
        The page.
    """
    return FileResponse(STATIC_ROOT / "index.html")


if STATIC_ROOT.exists():
    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


def main() -> None:
    """Run the development server.

    This is the ``vc-demo`` entry point.
    """
    import uvicorn

    print(f"Demonstration server on http://{DEFAULT_HOST}:{DEFAULT_PORT}")
    print("Every organisation, key and certificate in it is fictional.")
    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT, log_level="info")
