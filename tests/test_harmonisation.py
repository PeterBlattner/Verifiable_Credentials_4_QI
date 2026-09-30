"""Tests for what would have to be agreed, and for the claim underneath it.

The harmonisation items are editorial and cannot be tested: they are an argument about
what would have to happen. Two things about them can be, and both matter.

The first is internal: the step ladder and the item set reference each other by key, and
a ladder that advances an item nobody wrote, or a first-tier item no step ever reaches,
is a broken argument rather than a broken sentence.

The second is the chapter's central claim, and it is the reason this file exists at all.
"""

from __future__ import annotations

import dataclasses
import re

from starlette.testclient import TestClient

from vcqi.actors.harmonisation import (
    HARMONISATION_ITEMS,
    NEXT_STEPS,
    STATUSES,
    TIERS,
    TOPICS,
    items_in_tier,
)
from vcqi.domain.accreditation import scope_by_id
from vcqi.domain.kcdb import cmc_by_id
from vcqi.web.app import app


class TestTheLadderAndTheItemsAgree:
    """Referential integrity between the two halves of the chapter."""

    def test_every_item_sits_in_a_declared_tier(self) -> None:
        """A tier key with no tier renders as nothing at all."""
        tiers = {tier.key for tier in TIERS}
        for item in HARMONISATION_ITEMS:
            assert item.tier in tiers
            assert item.status in STATUSES

    def test_keys_are_unique(self) -> None:
        """Two items sharing a key would make `unblocks` ambiguous."""
        keys = [item.key for item in HARMONISATION_ITEMS]
        assert len(keys) == len(set(keys))

    def test_every_step_advances_something_real(self) -> None:
        """A step naming an item that does not exist is a dangling claim."""
        keys = {item.key for item in HARMONISATION_ITEMS}
        for step in NEXT_STEPS:
            assert step.unblocks, f"step {step.order} advances nothing"
            for key in step.unblocks:
                assert key in keys, f"step {step.order} names unknown item {key!r}"

    def test_every_minimum_item_is_reached_by_some_step(self) -> None:
        """The first tier is the one the ladder exists to deliver.

        An item in the minimum tier that no step advances means the ladder does not
        reach the thing it was drawn for, which is a hole in the argument rather than
        in the code.
        """
        advanced = {key for step in NEXT_STEPS for key in step.unblocks}
        for item in items_in_tier("floor"):
            assert item.key in advanced, f"nothing advances {item.key!r}"

    def test_the_ladder_is_ordered_and_contiguous(self) -> None:
        """The order is the argument, so it has to be an order."""
        assert [step.order for step in NEXT_STEPS] == list(range(1, len(NEXT_STEPS) + 1))

    def test_every_item_names_a_consequence_and_a_forum(self) -> None:
        """Both are load-bearing: what breaks, and who would have to prevent it."""
        for item in HARMONISATION_ITEMS:
            assert item.consequence.strip()
            assert item.forum.strip()

    def test_a_source_is_a_bare_url_or_nothing(self) -> None:
        """The chapter renders it with `el('a', ...)`, so it has to be a URL alone.

        A sentence in this field reaches the reader as a link whose text is the sentence
        and whose href is the sentence, which fails silently and looks deliberate.
        """
        for item in HARMONISATION_ITEMS:
            if not item.source:
                continue
            assert item.source.startswith("https://"), item.key
            assert " " not in item.source, item.key
            assert "<" not in item.source, item.key

    def test_an_item_claiming_an_answer_says_where_to_read_it(self) -> None:
        """`available` and `partial` are claims about the world, and they need a citation.

        This is the check the first draft of the chapter needed and did not have. It
        filed five items under `open` that had published answers, and nothing in the
        suite could tell the difference between a researched claim and an assumed one.
        """
        for item in HARMONISATION_ITEMS:
            if item.status in {"available", "partial"}:
                assert item.exists.strip(), f"{item.key} claims an answer without naming it"
                assert item.source, f"{item.key} claims an answer with nowhere to read it"

    def test_the_open_items_are_a_minority(self) -> None:
        """The chapter counts these and tells the reader the proportion.

        The count is computed in the interface rather than written into the prose, so it
        cannot go stale -- but it can still be embarrassing. A page asserting that most
        of the quality infrastructure's interoperability problem is an unwritten page is
        the specific overstatement the review corrected.
        """
        open_items = [item for item in HARMONISATION_ITEMS if item.status == "open"]
        assert len(open_items) * 2 < len(HARMONISATION_ITEMS)

    def test_no_item_points_at_another_by_position(self) -> None:
        """An item names the item it means, because its neighbours are not fixed.

        The page groups items by tier, not in the order they are written here, so "the
        item below" in the source was already a different item on the page: the
        timestamps item pointed at the event-log item that way and reached the one
        about which copy governs. A filter would move them again.
        """
        positional = re.compile(
            r"\b(?:item|items|panel|identifiers)\s+(?:above|below)\b"
            r"|\babove this (?:one|list)\b|\bthe next item\b|\bthe previous item\b",
            re.IGNORECASE,
        )
        found = [
            f"{item.key}.{field.name}: {match.group(0)!r}"
            for item in HARMONISATION_ITEMS
            for field in dataclasses.fields(item)
            if isinstance(getattr(item, field.name), str)
            for match in positional.finditer(getattr(item, field.name))
        ]
        assert found == []

    def test_the_two_gaps_the_review_named_are_on_the_page(self) -> None:
        """Cryptographic event logs and long-term retrieval, both in the second tier.

        They are second-tier and not third because neither can be started late: a log
        not kept from the first day cannot be reconstructed, and a document nobody
        archived in 2026 is not archivable in 2056.
        """
        by_key = {item.key: item for item in HARMONISATION_ITEMS}
        for key in ("event-logs", "retrieval"):
            assert key in by_key, f"{key} is missing from the page"
            assert by_key[key].tier == "irreversible", key

    def test_the_retrieval_item_quotes_what_was_actually_measured(self) -> None:
        """It rests on a real count, and the count is produced by another chapter.

        The infrastructure chapter verifies the conformity certificate for real and
        reports how many distinct documents across how many hosts that took. This item
        writes those two numbers into a sentence, and a sentence is not recomputed when
        the world grows. Comparing against the live figures is the difference between a
        measurement and a number that was true once.

        The remaining count -- everything except the credential the holder presents --
        is checked too, because it is the whole point of the item: the credential is
        safe and the documents behind it are not.
        """
        retrieval = next(item for item in HARMONISATION_ITEMS if item.key == "retrieval")

        with TestClient(app) as client:
            trace = client.get("/api/infrastructure").json()["verifierTrace"]

        assert f"{trace['distinct']} distinct documents" in retrieval.demonstrated
        assert f"{trace['hostCount']} hosts" in retrieval.demonstrated
        assert f"other {trace['distinct'] - 1}" in retrieval.demonstrated


class TestTopics:
    """The topics the chapter filters by, which cut across the tiers without reordering."""

    def test_every_item_has_one_or_two_known_topics(self) -> None:
        """An item with no topic would vanish under every filter but "All topics"."""
        keys = {topic.key for topic in TOPICS}
        for item in HARMONISATION_ITEMS:
            assert 1 <= len(item.topics) <= 2, item.key
            assert set(item.topics) <= keys, item.key

    def test_every_topic_is_used_and_named_once(self) -> None:
        """A topic with no items would offer the reader an empty page."""
        keys = [topic.key for topic in TOPICS]
        assert len(keys) == len(set(keys))
        used = {key for item in HARMONISATION_ITEMS for key in item.topics}
        assert used == set(keys)

    def test_the_chapter_is_served_its_topics(self) -> None:
        """The page builds its filter from these, so they have to arrive."""
        with TestClient(app) as client:
            body = client.get("/api/harmonisation").json()
        assert [topic["key"] for topic in body["topics"]] == [topic.key for topic in TOPICS]
        served = {item["key"]: item["topics"] for tier in body["tiers"] for item in tier["items"]}
        assert served == {item.key: list(item.topics) for item in HARMONISATION_ITEMS}


class TestTheMeasurandCoincidence:
    """The claim the harmonisation chapter is built on, kept honest by a test.

    The scope chapter decides whether a calibration may carry the CIPM MRA logo by
    comparing the measurand on the certificate with the measurand on the published
    capability, and ``domain/scope.py`` makes that comparison with ``==`` on a free
    string.

    It passes here because the CMC and the accreditation scope were written by one author
    in one afternoon. In a real deployment the CMC comes from the BIPM's KCDB and the
    scope from a national accreditation body, and there is no reason whatever for the two
    strings to coincide -- which is why the BIPM's SI Digital Framework identifiers, and
    the measurand identifiers under way at ISO and IEC, are the thing to adopt.

    If this test ever fails because somebody changed one of the two files, that is the
    real-world behaviour arriving early, and the fix is identifiers rather than a matching
    pair of edits.
    """

    def test_the_cmc_and_the_scope_agree_only_because_we_wrote_both(self) -> None:
        """Two organisations, one free string, and nothing enforcing the match."""
        cmc = cmc_by_id("CH-EM-0042")
        scope = scope_by_id("SCS 0123")
        assert cmc is not None and scope is not None

        # Different organisations publish these two documents.
        assert cmc.institute != scope.body

        # And yet the strings match exactly, which is what the scope chapter depends on.
        # The scope says it a row at a time now, which changes nothing about the
        # coincidence: there are simply more free strings that have to agree by luck.
        row = next(row for row in scope.as_rows() if row.measurand == "dc.resistance")
        assert cmc.measurand == row.measurand == "dc.resistance"
        assert cmc.unit == row.unit == "ohm"

    def test_the_measurand_is_not_a_resolvable_identifier(self) -> None:
        """The point of the chapter: this is a free string, not something you can look up."""
        cmc = cmc_by_id("CH-EM-0042")
        assert cmc is not None
        assert not cmc.measurand.startswith("http")
