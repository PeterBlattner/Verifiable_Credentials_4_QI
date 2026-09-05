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

import math
import copy
import hashlib
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from vcqi.actors.registry import ACTORS, TRUST_ANCHORS, actor_by_did, did_document
from vcqi.actors.scenarios import DEMO_NOW, World, build_world
from vcqi.actors.tamper import TAMPER_CASES, tamper_by_key
from vcqi.config import DEFAULT_HOST, DEFAULT_PORT
from vcqi.crypto.dataintegrity import ProofTrace, sign_document
from vcqi.crypto.ecdsa_p256 import P256, public_point, sign_deterministic
from vcqi.crypto.keys import DemoKey, derive_key, public_key_from_multikey
from vcqi.crypto.multibase import (
    encode_p256_multikey,
    multibase_decode,
    multibase_encode_base58btc,
)
from vcqi.domain.accreditation import ACCREDITATION_SCOPES
from vcqi.domain.gtc_archive import GTC_UNAVAILABLE_NOTE, gtc_available
from vcqi.domain.kcdb import CMC_ENTRIES, cmc_by_id
from vcqi.domain.scope import MeasurementClaim, evaluate_scope
from vcqi.domain.uncertainty import (
    evaluate,
    format_measurement,
    from_expanded_uncertainty,
    normal,
    rectangular,
)
from vcqi.vc.checks import credential_types, issuer_id
from vcqi.vc.resolver import DID_KEY_PREFIX, did_key_document
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


@app.get("/api/uncertainty-data")
def get_uncertainty_data(url: str = Query(..., description="Address of the data")) -> Response:
    """Serve a dependency representation as the bytes it actually is.

    A customer fetching this gets XML or a binary blob, not JSON wrapping one. It is the
    same payload the credential records a digest for, so anything retrieved here can be
    checked against the certificate that pointed at it.

    Args:
        url: The address the credential references.

    Returns:
        The raw payload with its own media type.

    Raises:
        HTTPException: If nothing is published there.
    """
    artefact = world().artefacts.get(url)
    if artefact is None:
        raise HTTPException(status_code=404, detail=f"no uncertainty data at {url}")
    media_type, payload = artefact
    return Response(content=payload, media_type=media_type)


class CombineRequest(BaseModel):
    """A request to combine two certified results.

    Attributes:
        first: Short name of the first certificate.
        second: Short name of the second certificate.
        operation: What to compute, one of difference, ratio or mean.
    """

    first: str = "metas-SR10K-0091"
    second: str = "metas-SR10K-0092"
    operation: str = "difference"


@app.post("/api/combine")
def post_combine(request: CombineRequest) -> dict[str, Any]:
    """Combine two certified results, with and without their shared influences.

    This is the demonstration chapter 6 is built around. Both certificates come from the
    same laboratory and rest on the same transfer standard, so part of their uncertainty
    is common to both. Whether a customer can take advantage of that depends entirely on
    what was transmitted:

    * given the dependency representations, the shared influence is recognised by its
      identifier and the common part cancels where the arithmetic says it should;
    * given only a value and an Expanded Uncertainty, the customer has no way to know
      the influence was shared, and the honest thing to do is add in quadrature, which
      overstates the result.

    The second answer is not a mistake by the customer. It is the best that can be done
    with what they were given.

    Args:
        request: Which certificates to combine and how.

    Returns:
        Both answers, the correlation between the inputs, the factor between them, and
        which way the classical answer errs.

    Raises:
        HTTPException: If a certificate is unknown or the operation is not supported.
    """
    import metas_unclib as unclib

    current = world()
    try:
        first = current.results[request.first]
        second = current.results[request.second]
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"no result {error}") from error

    u_variable_a, u_variable_b = first.uncertain_number, second.uncertain_number
    if u_variable_a is None or u_variable_b is None:
        raise HTTPException(status_code=400, detail="those results carry no dependencies")

    operations = {
        "difference": (lambda a, b: a - b, "R1 - R2", first.unit),
        "ratio": (lambda a, b: a / b, "R1 / R2", ""),
        "mean": (lambda a, b: (a + b) / 2.0, "(R1 + R2) / 2", first.unit),
    }
    if request.operation not in operations:
        raise HTTPException(status_code=400, detail=f"unknown operation {request.operation}")
    apply, label, unit = operations[request.operation]

    tracked = apply(u_variable_a, u_variable_b)
    tracked_value = float(unclib.get_value(tracked))
    tracked_standard = float(unclib.get_stdunc(tracked))

    # What the same customer would get from the printed numbers alone. The sensitivities
    # are those of the operation at the measured values; only the correlation is missing.
    if request.operation == "difference":
        naive_standard = math.sqrt(first.standard_uncertainty**2 + second.standard_uncertainty**2)
    elif request.operation == "mean":
        naive_standard = 0.5 * math.sqrt(
            first.standard_uncertainty**2 + second.standard_uncertainty**2
        )
    else:
        relative = math.sqrt(
            (first.standard_uncertainty / first.value) ** 2
            + (second.standard_uncertainty / second.value) ** 2
        )
        naive_standard = abs(tracked_value) * relative

    correlation = float(unclib.get_correlation([u_variable_a, u_variable_b])[0][1])
    factor = naive_standard / tracked_standard if tracked_standard else float("inf")

    # Which way the error runs depends on the operation, and it is worth being plain
    # about that. Positive correlation makes a difference more certain and a sum or a
    # mean less certain, so ignoring it does not simply err on the safe side. Sometimes
    # the classical answer is optimistic, which is the worse direction to be wrong in.
    if factor > 1.01:
        direction = "overstates"
    elif factor < 0.99:
        direction = "understates"
    else:
        direction = "agrees with"

    return {
        "operation": request.operation,
        "expression": label,
        "value": tracked_value,
        "unit": unit,
        "correlation": correlation,
        "tracked": {
            "standardUncertainty": tracked_standard,
            "expandedUncertainty": 2.0 * tracked_standard,
            "reported": format_measurement(tracked_value, 2.0 * tracked_standard, unit),
            "basis": "the dependency representations, in which the shared influence is recognisable",
        },
        "naive": {
            "standardUncertainty": naive_standard,
            "expandedUncertainty": 2.0 * naive_standard,
            "reported": format_measurement(tracked_value, 2.0 * naive_standard, unit),
            "basis": "the printed value and Expanded Uncertainty alone, combined in quadrature",
        },
        "factor": factor,
        "direction": direction,
        "inputs": [
            {
                "name": request.first,
                "reported": first.format(),
                "certificate": current.credential(request.first)["id"],
            },
            {
                "name": request.second,
                "reported": second.format(),
                "certificate": current.credential(request.second)["id"],
            },
        ],
        "sharedInfluences": _shared_influences(request.first, request.second),
    }


def _shared_influences(first: str, second: str) -> list[dict[str, Any]]:
    """List the influences two certificates have in common.

    Args:
        first: Short name of the first certificate.
        second: Short name of the second certificate.

    Returns:
        One entry per shared influence, with the identifier that made it recognisable.
    """
    current = world()

    def influences(name: str) -> dict[str, str]:
        credential = current.credentials.get(name, {})
        subject = credential.get("credentialSubject", {})
        results = subject.get("calibration", {}).get("results", [])
        found: dict[str, str] = {}
        for entry in results:
            for representation in entry.get("uncertaintyRepresentations", []):
                for item in representation.get("inputQuantities", []) or []:
                    if isinstance(item, dict) and isinstance(item.get("id"), str):
                        found[item["id"]] = str(item.get("description", ""))
        return found

    left, right = influences(first), influences(second)
    return [
        {"id": identifier, "description": description}
        for identifier, description in sorted(left.items())
        if identifier in right
    ]


@app.get("/api/gtc")
def get_gtc_status() -> dict[str, Any]:
    """Report whether the optional GTC support is installed.

    Returns:
        Whether GTC can be imported, and the note to display when it cannot.
    """
    return {"available": gtc_available(), "note": GTC_UNAVAILABLE_NOTE}


# ---------------------------------------------------------------- keys
#
# These four routes exist to teach one thing: what a keypair is and what a signature
# does and does not prove. Every one of them takes the private key as a parameter rather
# than holding it server side, which is deliberate. The private key really is just a
# number the caller possesses, and watching it travel in and out of an HTTP request makes
# the custody problem concrete in a way that any amount of prose does not.
#
# It is also, obviously, the last thing a real system would do. Nothing here protects
# anything: the demonstration keys come from a seed published in the repository, the
# server binds to localhost, and /api/keys/sign will sign whatever bytes it is handed
# with whatever key it is handed. That is safe only because the key is always the
# caller's own.


class DeriveKeyRequest(BaseModel):
    """A request to make a keypair.

    Attributes:
        passphrase: Words to derive the key from, reproducibly. The same passphrase
            always gives the same key, which is the point being taught and the reason
            nobody should ever do this for real.
        random: Generate from the operating system random source instead, so that two
            presses give two different keys.
    """

    passphrase: str = ""
    random: bool = False


def _key_material(scalar: int) -> dict[str, Any]:
    """Describe a private key and everything derived from it.

    Args:
        scalar: The private key as an integer.

    Returns:
        The scalar, the public point, each encoding layer between that point and the
        string a DID document actually carries, and the resulting did:key.

    Raises:
        HTTPException: If the scalar is outside the valid range for the curve.
    """
    try:
        x, y = public_point(scalar)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    private = ec.derive_private_key(scalar, ec.SECP256R1())
    compressed = private.public_key().public_bytes(
        Encoding.X962, PublicFormat.CompressedPoint
    )
    multikey = encode_p256_multikey(compressed)
    did = f"{DID_KEY_PREFIX}{multikey}"

    return {
        "privateScalarHex": f"{scalar:064x}",
        "privateScalarDecimalDigits": len(str(scalar)),
        "publicPoint": {"x": f"{x:064x}", "y": f"{y:064x}"},
        # The layers between the point and the string in a DID document. Each one is
        # reversible and none of them is cryptography; publicKeyMultibase looks opaque
        # only because four ordinary encodings are stacked on top of each other.
        "encodingLayers": [
            {
                "step": "the point on the curve",
                "value": f"x = {x:#0{66}x}",
                "note": "two coordinates, 32 bytes each",
            },
            {
                "step": "SEC1 compressed point",
                "value": compressed.hex(),
                "note": (
                    f"33 bytes: a {compressed[:1].hex()} prefix saying which of the two "
                    f"y values it is, then x. y is recomputed from the curve equation."
                ),
            },
            {
                "step": "multicodec prefix for p256-pub",
                "value": "8024" + compressed.hex(),
                "note": "0x1200 as a varint, so a reader knows what kind of key follows",
            },
            {
                "step": "base58btc, with a z to say so",
                "value": multikey,
                "note": "this is the publicKeyMultibase in every DID document here",
            },
        ],
        "publicKeyMultibase": multikey,
        "didKey": did,
        "verificationMethodId": f"{did}#{multikey}",
        "didDocument": did_key_document(did),
        "curve": {
            "name": "NIST P-256 (secp256r1)",
            "order": f"{P256.n:#x}",
            "generatorX": f"{P256.gx:#x}",
        },
    }


@app.post("/api/keys/derive")
def post_derive_key(request: DeriveKeyRequest) -> dict[str, Any]:
    """Make a keypair and show every step from the private number to the published one.

    Args:
        request: A passphrase to derive from, or a request for a random key.

    Returns:
        The key material, and whether it is reproducible.

    Raises:
        HTTPException: If neither a passphrase nor the random flag was given.
    """
    if request.random:
        scalar = ec.generate_private_key(ec.SECP256R1()).private_numbers().private_value
        reproducible = False
        note = (
            "Generated from the random source of the operating system. Ask again and you "
            "will get a different key, because a real key is chosen from about 2^256 "
            "possibilities and never derived from anything guessable."
        )
    else:
        if not request.passphrase.strip():
            raise HTTPException(
                status_code=400, detail="give a passphrase, or ask for a random key"
            )
        derived = derive_key(f"passphrase:{request.passphrase}", "key-1")
        scalar = derived.private_key.private_numbers().private_value
        reproducible = True
        note = (
            "Derived from this passphrase and a seed published in this repository. The "
            "same passphrase always gives the same key, which is exactly why nobody "
            "should ever make a real key this way: anyone who guesses the words has your "
            "private key, and so does anyone reading the source."
        )

    return {**_key_material(scalar), "reproducible": reproducible, "note": note}


class SignRequest(BaseModel):
    """A request to sign a message with a supplied key.

    Attributes:
        private_scalar_hex: The private key, as 64 hex characters.
        message: The text to sign.
    """

    private_scalar_hex: str
    message: str = "The 10 kilohm standard reads 10000.0012 ohm."


def _scalar_of(private_scalar_hex: str) -> int:
    """Read a private key out of a request.

    Args:
        private_scalar_hex: The scalar as hexadecimal.

    Returns:
        The scalar as an integer.

    Raises:
        HTTPException: If it is not readable hexadecimal in the valid range.
    """
    try:
        scalar = int(private_scalar_hex, 16)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail="the private key is not hexadecimal") from error
    if not 1 <= scalar < P256.n:
        raise HTTPException(status_code=400, detail="the private key is outside the curve order")
    return scalar


@app.post("/api/keys/sign")
def post_sign(request: SignRequest) -> dict[str, Any]:
    """Sign a message and show what the signature is made of.

    Args:
        request: The key and the message.

    Returns:
        The digest that was actually signed, the two halves of the signature, and its
        encoded form.

    Raises:
        HTTPException: If the key is unusable.
    """
    scalar = _scalar_of(request.private_scalar_hex)
    payload = request.message.encode("utf-8")
    signature = sign_deterministic(scalar, payload)

    return {
        "message": request.message,
        "messageBytes": len(payload),
        "digest": hashlib.sha256(payload).hexdigest(),
        "signature": {
            "r": signature[: P256.size].hex(),
            "s": signature[P256.size :].hex(),
            "bytes": len(signature),
            "multibase": multibase_encode_base58btc(signature),
        },
        "publicKeyMultibase": _key_material(scalar)["publicKeyMultibase"],
        "note": (
            "The signature is 64 bytes whatever the message length, because what gets "
            "signed is the 32-byte digest rather than the message. That is also why the "
            "credentials in this demonstration are canonicalized before they are hashed: "
            "the signature commits to exactly one sequence of bytes."
        ),
    }


class VerifySignatureRequest(BaseModel):
    """A request to check a signature.

    Attributes:
        message: The text the signature is claimed to be over.
        signature_multibase: The signature as produced by the sign route.
        public_key_multibase: The public key to check it against.
    """

    message: str
    signature_multibase: str
    public_key_multibase: str


@app.post("/api/keys/verify")
def post_verify_signature(request: VerifySignatureRequest) -> dict[str, Any]:
    """Check a signature against a message and a public key.

    All three inputs are checked together, which is the whole point: a signature is not
    valid or invalid on its own, only valid *for this message and this key*. Change any
    one of the three and it fails.

    Args:
        request: The message, the signature and the key.

    Returns:
        Whether it verified, and if not, a plain statement of why.
    """
    try:
        public_key = public_key_from_multikey(request.public_key_multibase)
    except ValueError as error:
        return {"valid": False, "reason": f"that is not a usable public key: {error}"}

    try:
        signature = multibase_decode(request.signature_multibase)
    except ValueError as error:
        return {"valid": False, "reason": f"that is not a usable signature: {error}"}
    if len(signature) != 2 * P256.size:
        return {
            "valid": False,
            "reason": (
                f"a P-256 signature is {2 * P256.size} bytes and this one is "
                f"{len(signature)}, so it has been altered"
            ),
        }

    r = int.from_bytes(signature[: P256.size], "big")
    s = int.from_bytes(signature[P256.size :], "big")
    try:
        public_key.verify(
            encode_dss_signature(r, s),
            request.message.encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )
    except InvalidSignature:
        return {
            "valid": False,
            "reason": (
                "the signature does not verify. Either it was made with a different key, "
                "or the message is not the one that was signed, or the signature itself "
                "has been altered. The arithmetic cannot tell you which."
            ),
        }
    return {
        "valid": True,
        "reason": "this key signed exactly this message, and neither has changed since",
    }


class IssueAsReaderRequest(BaseModel):
    """A request to sign a real credential with the reader's own key.

    Attributes:
        private_scalar_hex: The private key to sign with.
        mode: One of ``honest``, ``impersonate`` or ``steal-key-id``.
    """

    private_scalar_hex: str
    mode: str = "honest"


ISSUE_MODES = {
    "honest": "Sign as yourself, saying plainly that the credential is yours.",
    "impersonate": "Claim to be METAS, but name your own key in the proof.",
    "steal-key-id": "Claim to be METAS and claim METAS's key identifier as well.",
}


@app.post("/api/keys/issue")
def post_issue_as_reader(request: IssueAsReaderRequest) -> dict[str, Any]:
    """Sign a genuine calibration certificate with the reader's key and verify it.

    Three ways to try it, and none of them works, for three different reasons. Being
    able to see all three is the argument of the chapter: signing is easy, and a
    signature on its own settles almost nothing.

    Args:
        request: The key and which of the three attempts to make.

    Returns:
        The signed credential and its full verification report.

    Raises:
        HTTPException: If the key is unusable or the mode is unknown.
    """
    if request.mode not in ISSUE_MODES:
        raise HTTPException(status_code=400, detail=f"unknown mode {request.mode}")

    scalar = _scalar_of(request.private_scalar_hex)
    private = ec.derive_private_key(scalar, ec.SECP256R1())
    compressed = private.public_key().public_bytes(
        Encoding.X962, PublicFormat.CompressedPoint
    )
    multikey = encode_p256_multikey(compressed)
    did = f"{DID_KEY_PREFIX}{multikey}"
    reader = DemoKey(
        did=did, fragment=multikey, private_key=private, public_key_multibase=multikey
    )

    current = world()
    credential = copy.deepcopy(current.credential("metas-calibration"))
    credential.pop("credentialStatus", None)

    if request.mode == "honest":
        credential["id"] = "https://reader.example/certificates/MINE-0001"
        credential["issuer"] = {
            "id": did,
            "type": "RecognizedIssuer",
            "name": "A reader of this page",
        }
    # In the other two modes the issuer is left as METAS, which is the impersonation.

    signed, _ = sign_document(credential, reader, created=DEMO_NOW)
    if request.mode == "steal-key-id":
        # Claiming the identifier of a key you do not have. The verifier will resolve it
        # and get the real one.
        signed["proof"]["verificationMethod"] = "did:web:metas.example#issuance-key-1"

    report = verify_credential(
        signed, store=current.store, now=DEMO_NOW, trusted_issuers=TRUST_ANCHORS
    )
    steps = {step.id: step.status for step in report.steps}

    return {
        "mode": request.mode,
        "modeDescription": ISSUE_MODES[request.mode],
        "didKey": did,
        "credential": signed,
        "report": report.to_json(),
        "proof": steps.get("proof"),
        "recognition": steps.get("recognition"),
    }
