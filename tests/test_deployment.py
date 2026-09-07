"""Tests for what each role would have to operate to run this.

The profiles themselves are editorial and cannot be tested. What can be tested is the
split they are shown beside: that an issuer's hosting requirement is computed from what
was published, covers only the documents describing the issuer, and does not grow with
the number of credentials it has issued.
"""

from __future__ import annotations

from vcqi.actors.harmonisation import HARMONISATION_ITEMS
from vcqi.actors.deployment import DEPLOYMENT_PROFILES, hosting_burden
from vcqi.actors.registry import actor_by_did

class TestHostingBurden:
    """The split between what an issuer must serve and what its holders carry."""

    KINDS = {
        "did:web:lab.example": "did-document",
        "https://lab.example/.well-known/did.json": "did-document",
        "https://lab.example/status/certificates": "status-list",
        "https://lab.example/certificates/A-1": "credential",
        "https://lab.example/certificates/A-2": "credential",
        "https://lab.example/certificates/A-2/uncertainty.unc": "uncertainty-data",
        "https://other.example/certificates/B-1": "credential",
    }

    def test_certificates_are_not_hosted(self) -> None:
        """Only the documents describing the issuer count against it."""
        burden = hosting_burden(self.KINDS, "lab.example")
        assert burden["onlineCount"] == 2
        assert burden["travellingCount"] == 3
        assert {group["kind"] for group in burden["online"]} == {"did-document", "status-list"}

    def test_the_did_form_is_not_counted_a_second_time(self) -> None:
        """A DID document is one file, however many names resolve to it.

        did:web:lab.example and the well-known URL are the same document at two
        addresses, and counting both would overstate the burden by a factor of two.
        """
        burden = hosting_burden(self.KINDS, "lab.example")
        urls = [url for group in burden["online"] for url in group["urls"]]
        assert urls == sorted(urls)
        assert all(url.startswith("https://") for url in urls)

    def test_other_domains_are_left_alone(self) -> None:
        """One organisation's burden never includes another's documents."""
        assert hosting_burden(self.KINDS, "other.example")["onlineCount"] == 0
        assert hosting_burden(self.KINDS, "nobody.example") == {
            "domain": "nobody.example",
            "online": [],
            "onlineCount": 0,
            "travellingCount": 0,
        }

    def test_every_profile_names_a_real_actor(self) -> None:
        """A profile for an organisation that does not exist would render as nothing."""
        for profile in DEPLOYMENT_PROFILES:
            assert actor_by_did(profile.did) is not None
            assert profile.custody_grade in {"root", "service", "delegated"}
            assert profile.must_add and profile.hardest_part

class TestTheEditorialFieldsSuitTheSlotsTheyFill:
    """Half of these records reach `innerHTML` and half reach `textContent`.

    `posture`, `custody` and `hardest_part` go through `callout`/`prose`, which set
    `html:`, so inline markup in them works. `availability`, `scale`, `already_runs` and
    `must_add` go through `keyValues`/`checklist`, which set `text:` -- and so does every
    field of a harmonisation item, because the chapter renders all five through
    `keyValues`. Markup in any of those is shown to the reader as literal angle
    brackets.

    Nothing raises. The page just looks wrong, on the two chapters nobody clicks through
    because they have no controls to click.
    """

    #: Fields the interface renders as plain text, per record type.
    PLAIN_TEXT = {
        "deployment": ("availability", "scale"),
        "deployment_lists": ("already_runs", "must_add"),
        "harmonisation": (
            "requirement",
            "demonstrated",
            "exists",
            "consequence",
            "forum",
        ),
    }

    def test_deployment_plain_text_fields_carry_no_markup(self) -> None:
        """`keyValues` and `checklist` set textContent, so a tag would show literally."""
        offenders = []
        for profile in DEPLOYMENT_PROFILES:
            for field in self.PLAIN_TEXT["deployment"]:
                if "<" in getattr(profile, field):
                    offenders.append(f"{profile.did}/{field}")
            for field in self.PLAIN_TEXT["deployment_lists"]:
                for index, line in enumerate(getattr(profile, field)):
                    if "<" in line:
                        offenders.append(f"{profile.did}/{field}[{index}]")
        assert not offenders, "markup in a plain-text slot: " + ", ".join(offenders)

    def test_harmonisation_fields_carry_no_markup(self) -> None:
        """Every item field is rendered through `keyValues`, so none may hold markup.

        This is why the `units` item spells its URL out in prose rather than linking it.
        """
        offenders = []
        for item in HARMONISATION_ITEMS:
            for field in self.PLAIN_TEXT["harmonisation"]:
                if "<" in getattr(item, field):
                    offenders.append(f"{item.key}/{field}")
        assert not offenders, "markup in a plain-text slot: " + ", ".join(offenders)

    def test_every_profile_names_an_actor_that_exists(self) -> None:
        """A profile whose DID resolves to nothing renders a blank panel heading."""
        for profile in DEPLOYMENT_PROFILES:
            assert actor_by_did(profile.did) is not None, profile.did
