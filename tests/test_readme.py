"""The figures README.md states, checked against the code that produces them (#73).

A figure written into prose is not recomputed when the world grows. The failure-case
count drifted that way, from 24 to 23 in the README while ``tamper.py`` moved on, and it
is checked in ``test_web.py``. These check the rest. Each is compared with the number
the page itself serves, so a change that moves one fails here instead of leaving the
README a number that was true once. And each test fails when its sentence can no longer
be found, so rewording the README cannot quietly retire the check.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from vcqi.web.app import app
from vcqi.web.content import blocks_for

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
SCRIPTS = ROOT / "src" / "vcqi" / "web" / "static" / "js"
CHAPTERS_JS = (SCRIPTS / "chapters.js").read_text(encoding="utf-8")

#: The number words the README uses, and only those, so a new one fails loudly.
WORDS = {"three": 3, "five": 5, "eight": 8, "nine": 9, "eleven": 11, "thirteen": 13}


def _number(text: str) -> int:
    """Read a figure the way the README writes it.

    Args:
        text: A number word, or digits with optional thousands separators.

    Returns:
        The value.
    """
    return WORDS[text] if text in WORDS else int(text.replace(",", ""))


def _stated(pattern: str) -> tuple[int, ...]:
    """Find the one sentence a figure sits in, and read its figures.

    Args:
        pattern: A regular expression whose groups are the figures.

    Returns:
        The figures, in the order of the groups.
    """
    found = re.findall(pattern, README)
    assert found, f"the README no longer says anything matching {pattern!r}"
    assert len(set(found)) == 1, f"the README says {pattern!r} in {len(found)} ways"
    groups = found[0] if isinstance(found[0], tuple) else (found[0],)
    return tuple(_number(group) for group in groups)


@pytest.fixture(scope="module")
def client() -> TestClient:
    """A client over the application, warmed up the way a deployment is."""
    with TestClient(app) as warmed:
        yield warmed


@pytest.fixture(scope="module")
def world(client: TestClient) -> dict[str, Any]:
    """What ``/api/world`` serves: the counts the first chapters are built on."""
    return client.get("/api/world").json()


def test_the_dump_writes_as_many_documents_as_the_world_publishes(world) -> None:
    """``--dump`` is how a reader sees every document, so its count is the world's."""
    assert _stated(r"write all (\d+) documents as JSON") == (world["documentCount"],)


def test_the_trust_graph_has_the_organisations_and_arrangements_it_names(world) -> None:
    """The graph chapter's line in the chapter list."""
    graph = world["graph"]
    assert _stated(r"(\w+) organisations, (\w+) arrangements") == (
        len(graph["nodes"]),
        len(graph["branches"]),
    )


def test_the_issuing_chapter_has_the_credential_types_it_names(world) -> None:
    """One data model per type, and the chapter opens on the list of them."""
    types = len(world["credentialTypes"])
    assert _stated(r"one of the (\w+) credential types") == (types,)


def test_the_editing_chapter_offers_the_documents_it_names(world) -> None:
    """The documents a reader may change a field of."""
    assert _stated(r"pick one of (\w+) documents") == (len(world["editableDocuments"]),)


def test_the_authority_s_verification_is_the_one_the_page_runs(client) -> None:
    """The market surveillance authority's run, as the README describes it.

    The checks are the pipeline's top-level steps. The retrievals and distinct documents
    are what the infrastructure chapter measures when it verifies the same certificate.
    """
    report = client.post("/api/verify", json={"name": "cab-conformity"}).json()
    trace = client.get("/api/infrastructure").json()["verifierTrace"]
    assert report["outcome"] == trace["outcome"] == "verified"
    assert _stated(r"That authority runs (\w+) checks") == (len(report["steps"]),)
    assert _stated(r"made (\d+) retrievals across (\d+) distinct") == (
        trace["documents"],
        trace["distinct"],
    )


def test_what_can_arrive_with_the_holder_is_what_the_portability_audit_found(
    client,
) -> None:
    """The exchange chapter's measurement, in the chapter list.

    The README also breaks the travelling documents down by kind: three accreditation
    scopes, three data models and one register answer. The audit does not report kinds
    per document, so that breakdown is not checked here.
    """
    audit = client.get("/api/portability").json()
    stated = _stated(r"of the (\d+) documents one verification reads, (\d+) can arrive")
    assert stated == (audit["baseline"]["distinct"], audit["stapled"]["supplied"])


def test_the_status_lists_are_the_ones_the_revocation_audit_counts(client) -> None:
    """How many lists, how many positions, and that no credential is left out."""
    audit = client.get("/api/revocation").json()
    stated = _stated(
        r"The (\w+) status lists that make the middle model work reserve (\S+) "
    )
    assert stated == (audit["listCount"], audit["positions"])
    assert "cover every credential in the world" in README
    assert audit["unlisted"] == []


def test_the_chapter_list_is_the_chapters_in_order() -> None:
    """Numbered as the rail numbers them, and titled as each chapter titles itself.

    The cautions page is unnumbered, so the list starts at the chapter shown as 0.
    """
    entries = re.findall(r"^(\d+)\. \*\*(.+?)\*\* — ", README, re.MULTILINE)
    assert entries, "the README no longer lists the chapters"
    declared = re.findall(
        r"^    id: '([a-z-]+)',\n(    unnumbered: true,\n)?", CHAPTERS_JS, re.MULTILINE
    )
    numbered = [chapter_id for chapter_id, unnumbered in declared if not unnumbered]
    expected = [
        (str(number), blocks_for(chapter_id)["title"]["text"])
        for number, chapter_id in enumerate(numbered)
    ]
    assert entries == expected
