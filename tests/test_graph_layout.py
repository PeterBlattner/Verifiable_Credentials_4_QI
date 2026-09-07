"""The trust graph is drawn from a hand-written layout, so the layout needs checking.

`graph.js` fixes every box position by hand, deliberately: "the hierarchy is the message,
and a force layout would rearrange it every time the page loads." The cost of that choice
is that the layout can be wrong, and every way it goes wrong is silent. A node with no
coordinates is skipped. An edge touching it is dropped. A box outside the canvas rescales
the whole diagram. An edge routed through an unrelated box just looks like a mistake.

None of those raise, and no Python test would notice, because the layout is data in a
JavaScript file. So this module reads that data and checks it, replicating the two
geometry functions the browser uses. The duplication is the point: if `anchorPoint` or
`edgePath` changes shape, this stops describing what is drawn and should be updated to
match rather than deleted.
"""

from __future__ import annotations

import math
import pathlib
import re
from typing import Final

import pytest

from vcqi.web.app import BRANCHES, _graph

#: Box geometry, from `BOX` in graph.js.
BOX_WIDTH: Final = 170.0
BOX_HEIGHT: Final = 48.0

#: How far inside a box an edge has to pass before it counts as crossing it. A line that
#: clips a corner by a pixel is not a defect; one that runs through the middle is.
MARGIN: Final = 3.0

GRAPH_JS: Final = (
    pathlib.Path(__file__).resolve().parents[1]
    / "src"
    / "vcqi"
    / "web"
    / "static"
    / "js"
    / "graph.js"
).read_text(encoding="utf-8")


def _positions() -> dict[str, tuple[float, float]]:
    """Read the literal position map out of graph.js."""
    found = re.findall(
        r"'(did:web:[a-z0-9.-]+)':\s*\{\s*x:\s*(-?\d+),\s*y:\s*(-?\d+)\s*\}", GRAPH_JS
    )
    assert found, "could not find the position map in graph.js"
    return {did: (float(x), float(y)) for did, x, y in found}


def _canvas() -> tuple[float, float]:
    """Read the graph's own viewBox, not one of the arrow markers'."""
    match = re.search(r"class: 'graph', viewBox: '0 0 (\d+) (\d+)'", GRAPH_JS)
    assert match, "could not find the graph viewBox in graph.js"
    return float(match.group(1)), float(match.group(2))


POSITIONS: Final = _positions()
CANVAS_WIDTH, CANVAS_HEIGHT = _canvas()


def _centre(did: str) -> tuple[float, float]:
    x, y = POSITIONS[did]
    return x + BOX_WIDTH / 2, y + BOX_HEIGHT / 2


def _anchor(start_did: str, end_did: str) -> tuple[float, float]:
    """Where an edge leaves one box heading for another. Mirrors `anchorPoint`."""
    start_x, start_y = _centre(start_did)
    end_x, end_y = _centre(end_did)
    half_width, half_height = BOX_WIDTH / 2, BOX_HEIGHT / 2
    dx, dy = end_x - start_x, end_y - start_y
    if abs(dy) * half_width > abs(dx) * half_height:
        return (
            start_x + (dx * half_height) / abs(dy or 1),
            start_y + math.copysign(half_height, dy),
        )
    return (
        start_x + math.copysign(half_width, dx),
        start_y + (dy * half_width) / abs(dx or 1),
    )


def _curve(start_did: str, end_did: str) -> list[tuple[float, float]]:
    """Sample the cubic `edgePath` draws between two boxes."""
    start = _anchor(start_did, end_did)
    end = _anchor(end_did, start_did)
    mid_y = (start[1] + end[1]) / 2
    first, second = (start[0], mid_y), (end[0], mid_y)
    points = []
    for step in range(101):
        t = step / 100
        rest = 1 - t
        points.append(
            (
                rest**3 * start[0]
                + 3 * rest * rest * t * first[0]
                + 3 * rest * t * t * second[0]
                + t**3 * end[0],
                rest**3 * start[1]
                + 3 * rest * rest * t * first[1]
                + 3 * rest * t * t * second[1]
                + t**3 * end[1],
            )
        )
    return points


@pytest.fixture(scope="module")
def graph() -> dict:
    """The graph as the server serves it."""
    return _graph()


def test_every_box_is_inside_the_canvas() -> None:
    """A box outside the viewBox rescales the whole diagram to fit it."""
    for did, (x, y) in sorted(POSITIONS.items()):
        assert 0 <= x and x + BOX_WIDTH <= CANVAS_WIDTH, f"{did} runs off the right"
        assert 0 <= y and y + BOX_HEIGHT <= CANVAS_HEIGHT, f"{did} runs off the bottom"


def test_no_two_boxes_overlap() -> None:
    """Two boxes in the same place read as one box with the wrong label."""
    items = sorted(POSITIONS.items())
    for index, (first_did, (ax, ay)) in enumerate(items):
        for second_did, (bx, by) in items[index + 1 :]:
            overlapping = abs(ax - bx) < BOX_WIDTH and abs(ay - by) < BOX_HEIGHT
            assert not overlapping, f"{first_did} and {second_did} overlap"


def test_no_edge_is_routed_through_an_unrelated_box(graph: dict) -> None:
    """An edge crossing a box it does not end at reads as connecting to it."""
    offenders = []
    for edge in graph["edges"]:
        source, target = edge["source"], edge["target"]
        if source not in POSITIONS or target not in POSITIONS:
            continue
        for x, y in _curve(source, target):
            for did, (box_x, box_y) in POSITIONS.items():
                if did in (source, target):
                    continue
                inside_x = box_x + MARGIN <= x <= box_x + BOX_WIDTH - MARGIN
                inside_y = box_y + MARGIN <= y <= box_y + BOX_HEIGHT - MARGIN
                if inside_x and inside_y:
                    offenders.append(f"{source} -> {target} crosses {did}")
    assert not offenders, "; ".join(sorted(set(offenders)))


def test_no_edge_leaves_the_canvas(graph: dict) -> None:
    """A curve that swings outside the viewBox is clipped without a word."""
    for edge in graph["edges"]:
        source, target = edge["source"], edge["target"]
        if source not in POSITIONS or target not in POSITIONS:
            continue
        for x, y in _curve(source, target):
            assert -1 <= x <= CANVAS_WIDTH + 1, f"{source} -> {target} leaves sideways"
            assert -1 <= y <= CANVAS_HEIGHT + 1, f"{source} -> {target} leaves vertically"


def test_every_edge_carries_a_known_branch(graph: dict) -> None:
    """The filter chips are built from `branches`, so an unknown key is invisible."""
    known = {branch["key"] for branch in BRANCHES}
    for edge in graph["edges"]:
        assert edge["branch"] in known, f"unknown branch {edge['branch']!r}"


def test_every_branch_has_an_anchor_and_some_edges(graph: dict) -> None:
    """A branch chip that filters to nothing is worse than no chip."""
    used = {edge["branch"] for edge in graph["edges"]}
    anchors = {node["id"] for node in graph["nodes"] if node["isTrustAnchor"]}
    for branch in BRANCHES:
        assert branch["key"] in used, f"no edge belongs to {branch['key']}"
        assert branch["anchor"] in anchors, f"{branch['key']} names a non-anchor"


def test_a_node_belongs_to_the_branches_of_its_edges(graph: dict) -> None:
    """Node branches are derived, so this checks the derivation rather than a table.

    The laboratory recognised under two arrangements is the case worth having a test
    for: it should come out in three branches -- metrology because it holds a
    calibration, accreditation because SAS recognised it, legal metrology because OIML
    did -- without any of that being written down twice.
    """
    expected: dict[str, set[str]] = {}
    for edge in graph["edges"]:
        for end in ("source", "target"):
            expected.setdefault(edge[end], set()).add(edge["branch"])

    by_id = {node["id"]: node for node in graph["nodes"]}
    for did, branches in expected.items():
        assert set(by_id[did]["branches"]) == branches, did

    laboratory = by_id["did:web:testlab.example"]["branches"]
    assert set(laboratory) == {"metrology", "accreditation", "legal-metrology"}
