"""What can travel with a credential, and what a verifier must go and get.

UN/CEFACT's portable-credential architecture argues that hub-and-pipe networks never
reach everyone who needs a document -- fifty years of EDI reaching about a tenth of
cross-border trade -- so a signed document should travel by whatever means is to hand:
email, file transfer, a USB drive, a QR code. Anyone given it can verify it. Zero
infrastructure, no counter-party dependency.

This project was already built that way and had not noticed. ``actors/deployment.py``
says verification is *a computation, not a conversation*; chapter 10 computes that the
institute keeps three documents online while six of its credentials travel unhosted. And
metrology has the oldest instance of the idea in existence: a calibration certificate
already travels with the instrument. The paper in the box is a portable credential.

So the interesting question is not whether the model works. It is **where it stops**, and
that is measurable rather than arguable. Verifying one certificate of conformity reads 31
distinct documents from 7 hosts. This module sorts every one of them into four classes
and then proves the sort by running the verification twice -- once with nothing supplied,
once with everything supplied that is allowed to travel -- and comparing what the resolver
actually had to fetch.

The four classes are not a taxonomy invented for the chapter. Three of them are inherent
and one is an accident:

1. **It travels.** Signed in its own right, or covered by a ``digestMultibase`` inside
   something signed. A copy from any source is checkable, so the source does not matter.
2. **It must be resolved.** A DID document establishes a key. Accepting the holder's copy
   means accepting the holder's opinion about who somebody else is.
3. **It must be fresh.** A status list is a claim about *now*, and a stapled one is stale
   by construction.
4. **It cannot travel yet.** A CMC or an accreditation scope carries neither a signature
   nor a digest, so a copy cannot be checked at all. This is the accident: the reason is
   removable rather than inherent, and removing it is
   ``harmonisation.NEXT_STEPS`` step 5, *sign the KCDB*.

The audit therefore prices that step. It reports what remains after everything that can
travel has travelled, and then what would remain if the registries were signed too -- and
the second number is each organisation's key and its revocation list, and nothing else.
Which is precisely the hosting burden chapter 10 computed from the other end, without
either chapter knowing it was describing the same quantity.

``vc/resolver.py`` enforces the split with ``RESOLVE_ONLY_KINDS`` and its ``retrieve``
method. That enforcement is not decoration: before it existed, a holder could staple a DID
document claiming a trust anchor's identifier and have a credential it had signed itself
verify completely. ``tests/test_portability.py`` keeps that from coming back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vcqi.actors.deployment import host_of
from vcqi.actors.scenarios import World
from vcqi.vc.resolver import RESOLVE_ONLY_KINDS, Resolver
from vcqi.vc.verify import verify_credential

__all__ = [
    "PORTABILITY_CLASSES",
    "PortabilityClass",
    "class_of_kind",
    "portability_audit",
]

#: The credential the audit measures. The deepest chain in the world, and the same one
#: chapter 10 uses for its retrieval figures, so the two chapters can be compared.
AUDIT_CREDENTIAL: str = "cab-conformity"


@dataclass(frozen=True)
class PortabilityClass:
    """One answer to "may the holder bring this, or must the verifier fetch it?".

    Attributes:
        key: Short identifier.
        label: Heading as the chapter shows it.
        kinds: Document kinds that fall in this class.
        travels: Whether a holder may supply documents of these kinds.
        why: What makes the answer what it is.
        removable: Whether the reason could be engineered away. True for exactly one
            class, and saying which is most of the value of the whole exercise.
    """

    key: str
    label: str
    kinds: tuple[str, ...]
    travels: bool
    why: str
    removable: bool

    def to_json(self) -> dict[str, Any]:
        """Return the class as the interface displays it.

        Returns:
            A JSON-compatible dictionary.
        """
        return {
            "key": self.key,
            "label": self.label,
            "kinds": list(self.kinds),
            "travels": self.travels,
            "why": self.why,
            "removable": self.removable,
        }


PORTABILITY_CLASSES: tuple[PortabilityClass, ...] = (
    PortabilityClass(
        key="travels",
        label="It travels with the holder",
        kinds=("credential", "schema", "uncertainty-data"),
        travels=True,
        why=(
            "Either signed in its own right, or covered by a digestMultibase inside "
            "something that is. A copy is checkable whatever hand it arrived in, so "
            "where it came from stops mattering -- which is the whole portable-credential "
            "argument, and the reason a calibration certificate has always been able to "
            "travel in the box with the instrument."
        ),
        removable=False,
    ),
    PortabilityClass(
        key="must-resolve",
        label="It must be resolved from its publisher",
        kinds=("did-document", "presentation"),
        travels=False,
        why=(
            "A DID document establishes a key, so accepting the holder's copy means "
            "accepting the holder's opinion about who somebody else is. That is not a "
            "weakened check but a defeated one: staple a document claiming a trust "
            "anchor's identifier, sign a credential in that anchor's name, and every "
            "check passes. This demonstration did exactly that until it was tested for. "
            "A whois presentation is here for the milder version of the same reason -- it "
            "is what an issuer says about itself, so the issuer has to be the one saying "
            "it."
        ),
        removable=False,
    ),
    PortabilityClass(
        key="must-be-fresh",
        label="It must be fetched now",
        kinds=("status-list",),
        travels=False,
        why=(
            "A status list is a claim about the present tense. A stapled one is stale by "
            "construction, and a holder who kept a copy from the week before its "
            "accreditation was suspended would go on presenting it indefinitely. This is "
            "the class that makes zero infrastructure impossible rather than merely "
            "inconvenient: revocation is the one thing that cannot be pre-shipped."
        ),
        removable=False,
    ),
    PortabilityClass(
        key="not-yet",
        label="It could travel, and does not",
        kinds=("registry-entry",),
        travels=False,
        why=(
            "A CMC and an accreditation scope carry neither a signature nor a digest, so "
            "a copy cannot be checked at all and accepting one would let a laboratory "
            "declare its own measurement capability. Nothing about that is inherent. "
            "Sign the entries, or digest them from the credential that cites them, and "
            "every one of these moves into the first class -- which is why the "
            "harmonisation ladder puts signing the KCDB where it does."
        ),
        removable=True,
    ),
)


def class_of_kind(kind: str) -> PortabilityClass | None:
    """Return the class a document kind belongs to.

    Args:
        kind: The kind recorded by the document store, for example ``status-list``.

    Returns:
        The class, or ``None`` for a kind nobody has classified -- which the audit
        reports rather than silently dropping, because an unclassified kind is how a
        measurement like this quietly starts under-counting.
    """
    for candidate in PORTABILITY_CLASSES:
        if kind in candidate.kinds:
            return candidate
    return None


def _distinct(log: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Reduce a retrieval log to one record per address.

    Args:
        log: The resolver's log, as JSON records.

    Returns:
        Mapping from address to its first record.
    """
    distinct: dict[str, dict[str, Any]] = {}
    for record in log:
        distinct.setdefault(record["url"], record)
    return distinct


def _verify_once(
    world: World,
    *,
    now: datetime,
    trusted_issuers: frozenset[str] | set[str],
    supplied: dict[str, dict[str, Any]] | None = None,
) -> tuple[str, int, dict[str, dict[str, Any]]]:
    """Verify the audited credential once and reduce its retrieval log.

    Args:
        world: The built world.
        now: The instant to verify against.
        trusted_issuers: The anchors the verifier trusts.
        supplied: Documents the holder hands over, keyed by the address they are cited
            by. Built directly rather than through :meth:`Resolver.with_presented`,
            which indexes on a document's own ``id`` -- schemas carry ``$id`` and
            uncertainty data carries no identifier at all, so neither could be matched
            that way.

    Returns:
        The outcome, how many retrievals were attempted in total, and one record per
        distinct address. The two counts differ because this resolver refetches a DID
        document at every hop, which chapter 10 quotes rather than hides.
    """
    resolver = Resolver(store=world.store, presented=dict(supplied or {}))
    report = verify_credential(
        world.credential(AUDIT_CREDENTIAL),
        store=world.store,
        now=now,
        trusted_issuers=trusted_issuers,
        resolver=resolver,
    )
    rendered = report.to_json()
    return rendered["outcome"], len(rendered["fetches"]), _distinct(rendered["fetches"])


def portability_audit(
    world: World,
    *,
    now: datetime,
    trusted_issuers: frozenset[str] | set[str],
) -> dict[str, Any]:
    """Measure how much of a verification can arrive with the holder.

    Runs the same verification twice. The first time the verifier is given nothing and
    fetches all of it. The second time it is handed every document that is allowed to
    travel, and what it still fetches is the residue -- the part of the portable model
    that is not portable.

    Args:
        world: The built world.
        now: The instant to verify against.
        trusted_issuers: The anchors the verifier trusts.

    Returns:
        The classes, the per-class split of what the baseline read, the two retrieval
        counts, and the projection for signed registries.
    """
    # Baseline: nothing supplied, everything fetched.
    baseline_outcome, baseline_retrievals, seen = _verify_once(
        world, now=now, trusted_issuers=trusted_issuers
    )

    # Sort what it read, and collect the documents a holder would be allowed to bring.
    groups: dict[str, list[str]] = {item.key: [] for item in PORTABILITY_CLASSES}
    unclassified: list[str] = []
    stapled: dict[str, dict[str, Any]] = {}

    for url, record in sorted(seen.items()):
        found = class_of_kind(record["kind"])
        if found is None:
            unclassified.append(url)
            continue
        groups[found.key].append(url)
        if found.travels:
            document = world.store.get(url)
            if document is not None:
                stapled[url] = document

    # Second run: hand over everything that may travel.
    stapled_outcome, _, after = _verify_once(
        world, now=now, trusted_issuers=trusted_issuers, supplied=stapled
    )
    still_fetched = {
        url: record for url, record in after.items() if record["source"] == "retrieved"
    }

    def hosts(urls: Any) -> list[str]:
        """Return the distinct hosts a set of addresses points at.

        ``deployment.host_of`` understands ``https://`` only, and every DID document in
        this world is addressed as ``did:web:``. Those are the addresses that matter most
        to this count -- a key is served by a host like anything else -- so the method's
        own rule is applied here rather than reporting them as hostless.

        Args:
            urls: Addresses to inspect.

        Returns:
            Sorted host names, dropping addresses that name no host.
        """
        found = set()
        for url in urls:
            if url.startswith("did:web:"):
                # did:web percent-encodes a port as %3A and separates a path with ':'.
                found.add(url[len("did:web:") :].split(":", 1)[0].replace("%3A", ":"))
            else:
                found.add(host_of(url))
        return sorted(found - {""})

    # What would remain if the registries were signed -- the one removable class.
    removable_keys = {item.key for item in PORTABILITY_CLASSES if item.removable}
    irreducible = [
        url
        for key, urls in groups.items()
        if key not in removable_keys and key != "travels"
        for url in urls
    ]

    return {
        "credential": AUDIT_CREDENTIAL,
        "title": world.credential(AUDIT_CREDENTIAL)["id"],
        "classes": [item.to_json() for item in PORTABILITY_CLASSES],
        "split": [
            {
                "key": item.key,
                "count": len(groups[item.key]),
                "urls": groups[item.key],
                "hosts": hosts(groups[item.key]),
            }
            for item in PORTABILITY_CLASSES
        ],
        "unclassified": unclassified,
        "baseline": {
            "outcome": baseline_outcome,
            "distinct": len(seen),
            "retrievals": baseline_retrievals,
            "hosts": hosts(seen),
            "hostCount": len(hosts(seen)),
        },
        "stapled": {
            "outcome": stapled_outcome,
            "supplied": len(stapled),
            "stillFetched": len(still_fetched),
            "hosts": hosts(still_fetched),
            "hostCount": len(hosts(still_fetched)),
        },
        "ifRegistriesWereSigned": {
            "stillFetched": len(irreducible),
            "hosts": hosts(irreducible),
            "hostCount": len(hosts(irreducible)),
            "kinds": sorted(
                {
                    seen[url]["kind"]
                    for url in irreducible
                    if url in seen
                }
            ),
        },
        "resolveOnlyKinds": sorted(RESOLVE_ONLY_KINDS),
    }
