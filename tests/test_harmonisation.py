"""Tests for what would have to be agreed, and for the claim underneath it.

The harmonisation items are editorial and cannot be tested: they are an argument about
what would have to happen. Two things about them can be, and both matter.

The first is internal: the step ladder and the item set reference each other by key, and
a ladder that advances an item nobody wrote, or a first-tier item no step ever reaches,
is a broken argument rather than a broken sentence.

The second is the chapter's central claim, and it is the reason this file exists at all.
"""

from __future__ import annotations

from vcqi.actors.harmonisation import (
    HARMONISATION_ITEMS,
    NEXT_STEPS,
    STATUSES,
    TIERS,
    items_in_tier,
)
from vcqi.domain.accreditation import scope_by_id
from vcqi.domain.kcdb import cmc_by_id


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


class TestTheMeasurandCoincidence:
    """The claim chapter 11 is built on, kept honest by a test.

    Chapter 5 decides whether a calibration may carry the CIPM MRA logo by comparing the
    measurand on the certificate with the measurand on the published capability, and
    ``domain/scope.py`` makes that comparison with ``==`` on a free string.

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

        # And yet the strings match exactly, which is what chapter 5 depends on.
        assert cmc.measurand == scope.measurand == "dc.resistance"
        assert cmc.unit == scope.unit == "ohm"

    def test_the_measurand_is_not_a_resolvable_identifier(self) -> None:
        """The point of the chapter: this is a free string, not something you can look up."""
        cmc = cmc_by_id("CH-EM-0042")
        assert cmc is not None
        assert not cmc.measurand.startswith("http")
