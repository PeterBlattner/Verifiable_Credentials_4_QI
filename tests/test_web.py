"""Tests for the HTTP surface the browser and a verifier both use."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from vcqi.actors.tamper import TAMPER_CASES
from vcqi.web.app import STATIC_ROOT, app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Return a client bound to the application."""
    return TestClient(app)


def test_page_is_served(client: TestClient) -> None:
    """The single page and its entry script are reachable."""
    assert client.get("/").status_code == 200
    script = client.get("/static/js/app.js")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]


def test_world_describes_the_demonstration(client: TestClient) -> None:
    """The world endpoint carries everything the interface needs to start."""
    data = client.get("/api/world").json()
    assert len(data["graph"]["nodes"]) == 10
    assert data["graph"]["trustAnchors"] == ["did:web:bipm.example", "did:web:global-aci.example"]
    assert len(data["tamperCases"]) == len(TAMPER_CASES)
    assert any(entry["identifier"] == "CH-EM-0042" for entry in data["cmcEntries"])


def test_graph_edges_are_derived_from_the_credentials(client: TestClient) -> None:
    """Every edge names a credential that really exists.

    The picture is read out of the documents rather than written down separately, so
    this is what stops the diagram drifting away from what was actually issued.
    """
    data = client.get("/api/world").json()
    names = {item["name"] for item in data["credentials"]}
    for edge in data["graph"]["edges"]:
        assert edge["credential"] in names
        assert edge["source"] and edge["target"]


def test_credential_carries_its_signing_trace(client: TestClient) -> None:
    """A credential comes back with every intermediate value of its signature."""
    data = client.get("/api/credential/metas-calibration").json()
    trace = data["trace"]
    assert trace["signingInput"] == trace["proofConfigHash"] + trace["documentHash"]
    assert trace["proofValue"] == data["credential"]["proof"]["proofValue"]
    assert trace["canonicalDocument"].startswith('{"@context":')
    assert data["measurement"]["reported"].endswith("(k = 2)")


def test_documents_are_served_at_their_own_addresses(client: TestClient) -> None:
    """Anything a credential references can be fetched, as the verifier does."""
    response = client.get(
        "/api/document", params={"url": "https://bipm.example/kcdb/cmc/CH-EM-0042"}
    )
    assert response.status_code == 200
    assert response.json()["document"]["identifier"] == "CH-EM-0042"


def test_missing_document_is_not_found(client: TestClient) -> None:
    """An address with nothing at it is a 404, never an empty success."""
    assert client.get("/api/document", params={"url": "https://nowhere.example/x"}).status_code == 404


def test_verify_accepts_the_conformity_chain(client: TestClient) -> None:
    """The Product Conformity case verifies through the API."""
    report = client.post("/api/verify", json={"name": "cab-conformity"}).json()
    assert report["outcome"] == "verified"
    assert {step["id"] for step in report["steps"]} >= {"recognition", "traceability"}


def test_verify_respects_the_verification_date(client: TestClient) -> None:
    """Moving the clock past expiry rejects an otherwise good certificate."""
    report = client.post(
        "/api/verify", json={"name": "callab-calibration", "when": "2028-01-15T12:00:00Z"}
    ).json()
    assert report["outcome"] == "rejected"


def test_verify_rejects_an_unknown_name(client: TestClient) -> None:
    """A request naming nothing verifiable is a bad request."""
    assert client.post("/api/verify", json={"name": "nope"}).status_code == 400


def test_scope_endpoint_flips_on_the_uncertainty_floor(client: TestClient) -> None:
    """The verdict changes exactly where the published capability says it should."""
    generous = client.post(
        "/api/scope", json={"value": 10000.0, "expanded_uncertainty": 1.2e-3}
    ).json()
    optimistic = client.post(
        "/api/scope", json={"value": 10000.0, "expanded_uncertainty": 5.0e-4}
    ).json()
    assert generous["withinScope"] and generous["mraLogoJustified"]
    assert not optimistic["withinScope"] and not optimistic["mraLogoJustified"]
    assert generous["uncertaintyFloor"] == pytest.approx(1.0198039e-3, rel=1e-6)


def test_uncertainty_endpoint_recomputes_the_budget(client: TestClient) -> None:
    """The laboratory budget recomputes and reports whether it stays in scope."""
    data = client.post("/api/uncertainty", json={}).json()
    assert data["withinAccreditation"]
    assert data["expandedUncertainty"] == pytest.approx(2.0 * data["standardUncertainty"])
    assert sum(line["index"] for line in data["budget"]) == pytest.approx(1.0)


def test_understating_the_inherited_uncertainty_leaves_scope(client: TestClient) -> None:
    """Claiming a tenth of what the parent certificate reports breaks the accreditation."""
    data = client.post(
        "/api/uncertainty", json={"parent_expanded_uncertainty": 1.1e-4, "ratio_uncertainty": 1.0e-7}
    ).json()
    assert not data["withinAccreditation"]


@pytest.mark.parametrize("case", TAMPER_CASES, ids=lambda case: case.key)
def test_tamper_endpoint_reports_the_expected_step(client: TestClient, case) -> None:
    """Each failure case is caught by the step it names, through the API."""
    data = client.post(f"/api/tamper/{case.key}").json()
    assert data["caughtByExpectedStep"]
    assert data["report"]["outcome"] == "rejected"


def test_unknown_tamper_case_is_not_found(client: TestClient) -> None:
    """An unknown case identifier is a 404."""
    assert client.post("/api/tamper/nonexistent").status_code == 404


def test_combine_reports_both_answers(client: TestClient) -> None:
    """Combining two certificates gives the correlated answer and the naive one."""
    data = client.post("/api/combine", json={"operation": "difference"}).json()
    assert data["correlation"] == pytest.approx(0.69, abs=0.02)
    assert data["factor"] == pytest.approx(1.81, abs=0.03)
    assert data["direction"] == "overstates"
    assert data["tracked"]["standardUncertainty"] < data["naive"]["standardUncertainty"]
    assert len(data["sharedInfluences"]) == 1


def test_combine_reports_the_direction_for_a_mean(client: TestClient) -> None:
    """For a mean the classical answer is optimistic, not conservative.

    Worth asserting rather than assuming: discarding correlation is often described as
    the safe simplification, and for this operation it is the opposite.
    """
    data = client.post("/api/combine", json={"operation": "mean"}).json()
    assert data["direction"] == "understates"
    assert data["naive"]["standardUncertainty"] < data["tracked"]["standardUncertainty"]


def test_combine_ratio_is_dimensionless(client: TestClient) -> None:
    """A ratio of two resistances carries no unit."""
    assert client.post("/api/combine", json={"operation": "ratio"}).json()["unit"] == ""


def test_combine_rejects_an_unknown_operation(client: TestClient) -> None:
    """An operation the server does not implement is a bad request."""
    assert client.post("/api/combine", json={"operation": "product"}).status_code == 400


def test_uncertainty_data_is_served_as_itself(client: TestClient) -> None:
    """Dependency data comes back as bytes with its own media type, not as JSON."""
    url = "https://metas.example/certificates/METAS-2026-0417/uncertainty.unc"
    response = client.get("/api/uncertainty-data", params={"url": url})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/octet-stream")
    assert len(response.content) > 100


def test_missing_uncertainty_data_is_not_found(client: TestClient) -> None:
    """An address with no dependency data at it is a 404."""
    assert client.get(
        "/api/uncertainty-data", params={"url": "https://nowhere.example/x.unc"}
    ).status_code == 404


def test_gtc_status_is_reported(client: TestClient) -> None:
    """The interface can say plainly whether the optional extra is installed."""
    data = client.get("/api/gtc").json()
    assert isinstance(data["available"], bool)
    assert data["note"]


def test_certificates_carry_a_classical_statement_and_dependencies(client: TestClient) -> None:
    """Every calibration certificate reports classically and offers more besides."""
    data = client.get("/api/credential/metas-calibration").json()
    result = data["credential"]["credentialSubject"]["calibration"]["results"][0]
    formats = [item["format"] for item in result["uncertaintyRepresentations"]]
    assert formats[0] == "value-and-expanded-uncertainty"
    assert "METAS-UncLib-XML" in formats
    assert "METAS-UncLib-binary" in formats


def test_infrastructure_separates_hosting_from_issuance(client: TestClient) -> None:
    """What an issuer hosts is small, and does not grow with what it issues.

    This is the claim chapter 10 rests on, so it is measured rather than trusted: an
    institute that issued several certificates keeps fewer documents online than it
    issued, because a credential reaches a verifier in its holder's hands.
    """
    data = client.get("/api/infrastructure").json()
    roles = {role["actor"]["id"]: role for role in data["roles"]}
    assert "did:web:bipm.example" in roles

    metas = roles["did:web:metas.example"]
    assert metas["issuedCount"] >= 3
    assert metas["hosting"]["onlineCount"] < metas["issuedCount"]
    assert metas["hosting"]["travellingCount"] >= metas["issuedCount"]

    kinds = {group["kind"] for group in metas["hosting"]["online"]}
    assert "did-document" in kinds
    assert "status-list" in kinds
    assert "credential" not in kinds


def test_infrastructure_hosting_lists_reachable_addresses(client: TestClient) -> None:
    """Everything the burden counts can really be fetched, as the chapter lets a reader do."""
    data = client.get("/api/infrastructure").json()
    roles = {role["actor"]["id"]: role for role in data["roles"]}
    for group in roles["did:web:bipm.example"]["hosting"]["online"]:
        for url in group["urls"]:
            assert url.startswith("https://bipm.example/")
            assert client.get("/api/document", params={"url": url}).status_code == 200


def test_infrastructure_verifier_trace_is_a_real_verification(client: TestClient) -> None:
    """The retrieval figures come from verifying the deepest chain, not from a table."""
    trace = client.get("/api/infrastructure").json()["verifierTrace"]
    assert trace["outcome"] == "verified"
    assert trace["hostCount"] == len(trace["hosts"])
    # Every fetch is one of a handful of hosts, and the uncached count is the honest one:
    # this resolver has no cache, so it must be at least the number of distinct documents.
    assert 0 < trace["distinct"] <= trace["documents"]
    assert "bipm.example" in trace["hosts"]


def test_every_chapter_in_the_rail_has_a_render_function() -> None:
    """The chapter list and the functions behind it cannot drift apart unnoticed."""
    source = (STATIC_ROOT / "js" / "chapters.js").read_text(encoding="utf-8")
    ids = re.findall(r"^    id: '([a-z-]+)',$", source, flags=re.MULTILINE)
    assert "infrastructure" in ids
    assert "harmonisation" in ids
    assert len(ids) == len(set(ids))
    for name in re.findall(r"^    render: (\w+),$", source, flags=re.MULTILINE):
        assert f"async function {name}(" in source


def test_harmonisation_serves_three_tiers_and_a_ladder(client: TestClient) -> None:
    """The chapter reads the tiers in order, so the endpoint has to serve them in order."""
    data = client.get("/api/harmonisation").json()
    assert [tier["key"] for tier in data["tiers"]] == ["floor", "irreversible", "optional"]
    assert all(tier["items"] for tier in data["tiers"])
    assert [step["order"] for step in data["nextSteps"]] == [1, 2, 3, 4, 5, 6]


def test_harmonisation_items_carry_what_the_chapter_renders(client: TestClient) -> None:
    """Every field the chapter puts on the page is present and non-empty."""
    data = client.get("/api/harmonisation").json()
    items = [item for tier in data["tiers"] for item in tier["items"]]
    assert len(items) >= 10
    for item in items:
        assert item["status"] in {"available", "emerging", "open"}
        for field in ("title", "requirement", "demonstrated", "consequence", "forum"):
            assert item[field].strip(), f"{item['key']} has an empty {field}"


def test_harmonisation_quotes_the_cryptosuite_the_demonstration_actually_uses(
    client: TestClient,
) -> None:
    """The text interpolates the constant rather than repeating it, so it cannot drift.

    If the cryptosuite is ever changed, this catches a chapter that would otherwise go on
    describing the old one in a sentence that still reads perfectly well.
    """
    from vcqi.config import CRYPTOSUITE

    data = client.get("/api/harmonisation").json()
    items = {item["key"]: item for tier in data["tiers"] for item in tier["items"]}
    assert CRYPTOSUITE in items["cryptosuite"]["demonstrated"]
