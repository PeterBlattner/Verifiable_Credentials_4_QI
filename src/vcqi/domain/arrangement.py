"""The main scopes of the Global ACI multilateral recognition arrangement.

Global ACI recognises an accreditation body *for named scopes*, not as a member. A
scope is a pair: the arrangement calls the activity Level 2, the normative document it
is assessed against Level 3, and the combination of the two a **main scope**. Signatory
status is granted and extended one main scope at a time, each with its own date of
signature.

The pair matters, and a list of standards cannot replace it. Testing and Calibration are
two different main scopes assessed against the same ISO/IEC 17025, so a body may be a
signatory for one and not the other. A credential that recorded only the standards would
be unable to say which.

Sub-scopes exist below the main scope, at Levels 4 and 5. Only the main scope is modelled
here, which is enough to decide whether an accreditation body was a signatory for the kind
of accreditation it granted, and not enough to decide anything finer.

The arrangement is real and the signatories here are not: ILAC and IAF ceased to operate
separately on 1 January 2026 and were replaced by Global Accreditation Cooperation
Incorporated, which launched this arrangement the same day. Every organisation,
identifier and date below is fictional.

Nothing here is published as a retrievable document, unlike the CMC entries and the
accreditation scopes. There would be nothing for a verifier to do with it. A recognised
action carries its main scope inside the credential, where Global ACI's own signature
covers it; a registry entry carries no signature, and Global ACI is the authority on its
own arrangement, so fetching its unsigned statement to check its signed one would add a
retrieval and no evidence. Where a registry is worth retrieving -- a CMC, an accreditation
scope -- it is because the party being checked is *not* the party that published it.

The standard identifiers are ISO URNs as RFC 5141 defines them, which makes them the one
family of identifiers in this demonstration that is not invented here -- see chapter 11.
They do not resolve, so the human title travels beside each one. The edition numbers are
stated as best known and are exactly the sort of thing a real deployment has to pin
against the ISO catalogue rather than against anyone's memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "MainScope",
    "SignatoryScope",
    "MAIN_SCOPES",
    "SIGNATORY_SCOPES",
    "main_scope_by_activity",
    "scopes_for_signatory",
]


@dataclass(frozen=True)
class MainScope:
    """One main scope of the arrangement: an activity and the document it rests on.

    Attributes:
        activity: The Level 2 activity, for example ``Calibration``.
        standard: Title of the Level 3 normative document, with its year.
        standard_id: RFC 5141 ISO URN identifying that document.
    """

    activity: str
    standard: str
    standard_id: str

    def to_json(self) -> dict[str, Any]:
        """Return the pair as a credential records it.

        Returns:
            A JSON-compatible dictionary. The activity and the standard travel
            together, because neither alone identifies a main scope.
        """
        return {
            "activity": self.activity,
            "standard": {"id": self.standard_id, "name": self.standard},
        }


#: Every main scope of the arrangement, in the order its own scope list gives them.
MAIN_SCOPES: tuple[MainScope, ...] = (
    MainScope("Testing", "ISO/IEC 17025:2017", "urn:iso:std:iso-iec:17025:ed-3"),
    MainScope("Medical testing", "ISO 15189:2022", "urn:iso:std:iso:15189:ed-4"),
    MainScope("Calibration", "ISO/IEC 17025:2017", "urn:iso:std:iso-iec:17025:ed-3"),
    MainScope(
        "Management systems certification",
        "ISO/IEC 17021-1:2015",
        "urn:iso:std:iso-iec:17021:-1:ed-1",
    ),
    MainScope("Persons certification", "ISO/IEC 17024:2012", "urn:iso:std:iso-iec:17024:ed-2"),
    MainScope("Products certification", "ISO/IEC 17065:2012", "urn:iso:std:iso-iec:17065:ed-1"),
    MainScope("Inspection", "ISO/IEC 17020:2012", "urn:iso:std:iso-iec:17020:ed-2"),
    MainScope(
        "Validation and verification",
        "ISO/IEC 17029:2019",
        "urn:iso:std:iso-iec:17029:ed-1",
    ),
    MainScope(
        "Proficiency testing provision",
        "ISO/IEC 17043:2023",
        "urn:iso:std:iso-iec:17043:ed-2",
    ),
    MainScope(
        "Reference material production", "ISO 17034:2016", "urn:iso:std:iso:17034:ed-1"
    ),
    MainScope("Biobanking", "ISO 20387:2018", "urn:iso:std:iso:20387:ed-1"),
)


def main_scope_by_activity(activity: str) -> MainScope:
    """Look up a main scope by its Level 2 activity.

    Args:
        activity: The activity name, for example ``Calibration``.

    Returns:
        The main scope.

    Raises:
        KeyError: If the arrangement defines no such activity. Unlike a lookup of
            somebody else's identifier, this one names a scope of the arrangement
            itself, so a miss is a mistake in this file rather than a fact about the
            world.
    """
    for scope in MAIN_SCOPES:
        if scope.activity == activity:
            return scope
    raise KeyError(f"{activity!r} is not a main scope of the arrangement")


@dataclass(frozen=True)
class SignatoryScope:
    """One main scope one accreditation body is a signatory for.

    This is what a signatory search answers: not "this body is a member", but "this body
    is a signatory for this activity under this document, since this date".

    Attributes:
        organisation: DID of the accreditation body.
        main_scope: The activity and normative document pair.
        signed_on: Date signatory status for this scope began, as an ISO 8601 date.
            Real signatories hold their scopes from different dates, because each is
            granted separately; these three happen to share the day the arrangement
            began.
    """

    organisation: str
    main_scope: MainScope
    signed_on: str


#: The main scopes the accreditation body of this world is a signatory for. Three of
#: eleven, and exactly the three its accreditation scopes are granted under: two share a
#: standard and differ only in activity, which is the case a list of standards loses.
SIGNATORY_SCOPES: tuple[SignatoryScope, ...] = (
    SignatoryScope(
        organisation="did:web:sas.example",
        main_scope=main_scope_by_activity("Calibration"),
        signed_on="2026-01-01",
    ),
    SignatoryScope(
        organisation="did:web:sas.example",
        main_scope=main_scope_by_activity("Testing"),
        signed_on="2026-01-01",
    ),
    SignatoryScope(
        organisation="did:web:sas.example",
        main_scope=main_scope_by_activity("Products certification"),
        signed_on="2026-01-01",
    ),
)


def scopes_for_signatory(organisation: str) -> tuple[SignatoryScope, ...]:
    """Return every main scope one accreditation body is a signatory for.

    Args:
        organisation: DID of the accreditation body.

    Returns:
        Its signatory scopes, in the order the arrangement lists them.
    """
    return tuple(
        scope for scope in SIGNATORY_SCOPES if scope.organisation == organisation
    )
