"""Tests for what each role would have to operate to run this.

The profiles themselves are editorial and cannot be tested. What can be tested is the
split they are shown beside: that an issuer's hosting requirement is computed from what
was published, covers only the documents describing the issuer, and does not grow with
the number of credentials it has issued.
"""

from __future__ import annotations

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
