"""What would have to be agreed between organisations, and by whom.

Chapter 10 asks what one organisation would have to run. This asks the harder question:
what would they all have to agree with each other, for a certificate written in one
country to mean the same thing in another. The two are different problems, and the second
is the one the quality infrastructure exists to solve.

Every item here passes one test, and items that fail it were left out: **two conforming
implementations that differ here cannot interoperate.** That test is what separates a
harmonisation need from a deployment gap. Deployment gaps — key custody, long-term
validation, selective disclosure, the signed KCDB — are named in chapter 9 already, with a
direction for each. Repeating them here would be padding. What is not written down
anywhere else is who would have to agree each item, in which forum, and what happens when
two bodies answer differently.

The tiers are read in order rather than filtered. The ordering is itself the argument: the
first tier is what makes the system work at all, the second is what cannot be decided later
however much anyone would prefer to, and the third is what a deployment can do without.

One thing this module gets wrong less than an earlier draft did. It is tempting to assume
the metrology vocabularies are missing and must be invented. They are not. The BIPM
publishes permanent digital identifiers for every SI unit through the SI Digital Framework,
resolvable CMC identifiers already exist, and work on measurand identifiers is under way at
ISO and IEC. The honest finding is not that no vocabulary exists — it is that one exists
and this demonstration did not use it. The URLs below are the only references in this
project that point at something real; every other identifier in it is fictional by design.

The items are editorial: an argument about what would have to happen, not a measurement of
anything. Where a sentence states what this demonstration chose, it interpolates the real
constant rather than repeating it, so the text cannot drift away from the code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vcqi.config import CRYPTOSUITE
from vcqi.domain.dcc import DCC_SCHEMA_VERSION, SI_VERSION

__all__ = [
    "HarmonisationItem",
    "NextStep",
    "Tier",
    "HARMONISATION_ITEMS",
    "NEXT_STEPS",
    "STATUSES",
    "TIERS",
    "items_in_tier",
]

#: What exists today for a given item, which decides what the work actually is.
STATUSES: frozenset[str] = frozenset({"available", "emerging", "open"})


@dataclass(frozen=True)
class Tier:
    """One tier of harmonisation need.

    Attributes:
        key: Short identifier.
        label: Heading as the chapter shows it.
        test: The question that puts an item in this tier rather than another.
    """

    key: str
    label: str
    test: str

    def to_json(self) -> dict[str, Any]:
        """Return the tier as the interface displays it.

        Returns:
            A JSON-compatible dictionary.
        """
        return {"key": self.key, "label": self.label, "test": self.test}


#: The three tiers, in the order they are meant to be read.
TIERS: tuple[Tier, ...] = (
    Tier(
        key="floor",
        label="The minimum, without which nothing works",
        test=(
            "Two organisations that answer these differently cannot exchange a "
            "certificate at all. Nothing else on this page matters until they are settled."
        ),
    ),
    Tier(
        key="irreversible",
        label="Not needed yet, and still has to be decided now",
        test=(
            "Nothing breaks today if these are left open. They are here because the "
            "decision cannot be taken later: by the time the need is felt, the "
            "certificates that needed it have already been issued and archived."
        ),
    ),
    Tier(
        key="optional",
        label="Worth having, and the system runs without it",
        test=(
            "Real value, and a deployment that never agrees any of them still verifies "
            "every signature and every recognition chain. This is the tier where a "
            "programme of work should be honest that it is buying quality, not function."
        ),
    ),
)


@dataclass(frozen=True)
class HarmonisationItem:
    """One thing that would have to be agreed across organisations.

    Attributes:
        key: Short identifier, referenced by :class:`NextStep`.
        tier: Which tier this belongs to.
        title: Heading as the chapter shows it.
        status: ``available``, ``emerging`` or ``open`` — what exists today.
        requirement: What would have to be agreed.
        demonstrated: What this demonstration chose, stated concretely.
        exists: The register or standard already covering it, or an empty string.
        consequence: What happens when two parties answer differently.
        forum: Who would have to agree it, and whether such a body exists.
    """

    key: str
    tier: str
    title: str
    status: str
    requirement: str
    demonstrated: str
    exists: str
    consequence: str
    forum: str

    def to_json(self) -> dict[str, Any]:
        """Return the item as the interface displays it.

        Returns:
            A JSON-compatible dictionary.
        """
        return {
            "key": self.key,
            "tier": self.tier,
            "title": self.title,
            "status": self.status,
            "requirement": self.requirement,
            "demonstrated": self.demonstrated,
            "exists": self.exists,
            "consequence": self.consequence,
            "forum": self.forum,
        }


HARMONISATION_ITEMS: tuple[HarmonisationItem, ...] = (
    # ---------------------------------------------------------------- tier 1
    HarmonisationItem(
        key="cryptosuite",
        tier="floor",
        title="One cryptosuite, and one canonical form",
        status="available",
        requirement=(
            "Every issuer signs, and every verifier checks, the same way. A verifier "
            "cannot be expected to implement each institute's preference, and a "
            "certificate that has to say which dialect it used has already lost."
        ),
        demonstrated=(
            f"This demonstration signs with {CRYPTOSUITE}, which canonicalizes the JSON. "
            "ARCHITECTURE.md already records that this was chosen so a reader can watch "
            "the exact bytes being hashed, and that a production system should "
            "canonicalize the RDF graph instead. The demonstration is proposing "
            "something it does not itself recommend, which is worth knowing before "
            "anyone treats it as a template."
        ),
        exists=(
            "W3C Data Integrity, with a registry of cryptosuites. The standard exists; "
            "choosing one from it is the part nobody has done."
        ),
        consequence=(
            "Signatures made at one institute do not verify at another. This is the "
            "failure that stops everything, and it is the cheapest on this page to avoid."
        ),
        forum=(
            "Whoever governs the anchors, jointly. There is no obvious existing home for "
            "a decision this small and this load-bearing."
        ),
    ),
    HarmonisationItem(
        key="did-method",
        tier="floor",
        title="One identifier method, and an agreed meaning for resolving it",
        status="open",
        requirement=(
            "Agreeing the method is the easy half. The half nobody has written down is "
            "what a verifier must check when it resolves one: which certificate "
            "authority it trusts for the host, how a rotated key is recognised as the "
            "same organisation, and how a compromised one is withdrawn."
        ),
        demonstrated=(
            "Every organisation here is a did:web resolved from its own domain, and "
            "resolution is a local lookup that never touches the network. That is "
            "exactly the part a demonstration cannot exercise honestly."
        ),
        exists=(
            "did:web is a real method with a real well-known path. What a verifier owes "
            "the resolution step is specified nowhere."
        ),
        consequence=(
            "Verifiers each invent their own resolution policy, and an institute that "
            "rotates a key discovers which policies existed by finding out whose "
            "verification broke."
        ),
        forum="The arrangements, for their own members, with a common floor.",
    ),
    HarmonisationItem(
        key="chain-crossing",
        tier="floor",
        title="How a chain crosses from one arrangement into the other",
        status="open",
        requirement=(
            "A certificate of conformity can rest on an accreditation under the Global "
            "ACI arrangement and on a calibration traceable under the CIPM MRA. Somebody "
            "has to say how a verifier composes the two, and what it means when the two "
            "arrangements disagree about the same organisation."
        ),
        demonstrated=(
            "This demonstration trusts both anchors and lets a chain run through either "
            "without ceremony. It composes because one author decided both arrangements "
            "would use the same properties in the same way, which is the assumption a "
            "real deployment does not get to make."
        ),
        exists="",
        consequence=(
            "Every cross-border case is left to each verifier to invent — and the "
            "cross-border case is the entire reason for doing any of this."
        ),
        forum=(
            "The CIPM MRA and the Global ACI arrangement together. They have no standing "
            "joint technical body, which makes this the hardest item here by some margin."
        ),
    ),
    HarmonisationItem(
        key="status-meaning",
        tier="floor",
        title="What a status value means, not how it is encoded",
        status="open",
        requirement=(
            "The encoding is settled. What suspension means institutionally is not: who "
            "may set it, when it takes effect, whether it reaches back over certificates "
            "already issued, and what a laboratory is permitted to do while suspended."
        ),
        demonstrated=(
            "Every issuer here publishes a status list and nothing in the world is "
            "revoked or suspended. The lists exist so the failure cases have something "
            "real to flip rather than a deletion standing in for a revocation."
        ),
        exists=(
            "W3C Bitstring Status List defines revocation and suspension as values. It "
            "does not define, and could not define, what either means to an "
            "accreditation body."
        ),
        consequence=(
            "Two bodies reading the same bit differently is worse than having no status "
            "mechanism, because both of them believe they have checked."
        ),
        forum=(
            "Each arrangement for its own members — but the meanings have to line up "
            "where a chain crosses between them."
        ),
    ),
    HarmonisationItem(
        key="anchors",
        tier="floor",
        title="What the anchors' identifiers are, and how a verifier learns them",
        status="open",
        requirement=(
            "Every verifier needs the identifiers of the anchors before it can check "
            "anything at all. How it obtains them, how they rotate, and what happens on "
            "the day one is compromised is the whole trust model, and it is upstream of "
            "every other item here."
        ),
        demonstrated=(
            "Two anchors are hard-coded as trusted, and chapter 4 lets a reader remove "
            "one to watch what stops verifying. That is the decision a real deployment "
            "has to make explicitly, publish, and defend."
        ),
        exists="",
        consequence=(
            "Without an agreed way to distribute the list, every verifier assembles its "
            "own, and an arrangement whose members cannot agree who is in it has stopped "
            "being an arrangement."
        ),
        forum=(
            "The arrangements. Chapter 9 calls the custody of these keys a governance "
            "problem in a technical costume; the harmonisation question is the narrower "
            "one of who publishes the list and how it is fetched."
        ),
    ),
    HarmonisationItem(
        key="units",
        tier="floor",
        title="Unit identifiers, which already exist",
        status="available",
        requirement=(
            "A unit has to mean the same thing to the issuer and to the verifier. That "
            "means a resolvable identifier, not a symbol in a free text field."
        ),
        demonstrated=(
            "Units travel here as free text — ohm, V, kg — and acquire standard meaning "
            "only where a hand-maintained table translates them into D-SI. Nothing checks "
            "that table is right, and it raises rather than guessing when a unit is "
            "missing from it, which is the best a free string can do."
        ),
        exists=(
            "The BIPM's SI Digital Framework publishes permanent digital identifiers for "
            "every SI unit, prefix and defining constant, with RDF behind them. The ohm "
            "is at https://si-digital-framework.org/SI/units/ohm, carrying its symbol, "
            "its quantity and the CGPM resolution that defined it."
        ),
        consequence=(
            "Two laboratories writing the same unit differently produce certificates a "
            "machine cannot compare, in a system whose whole purpose is machine "
            "comparison."
        ),
        forum=(
            "None required. The register exists and it is the BIPM's. This item is "
            "adoption, not agreement, which makes it the one thing on this page that "
            "anybody could finish on their own."
        ),
    ),
    # ---------------------------------------------------------------- tier 2
    HarmonisationItem(
        key="timestamps",
        tier="irreversible",
        title="Whose timestamps everybody accepts",
        status="open",
        requirement=(
            "Long-term validation needs a timestamp from an authority the eventual "
            "verifier trusts — possibly thirty years later, and probably in a different "
            "country from the one that issued the certificate."
        ),
        demonstrated=(
            "Nothing here is timestamped. Chapter 10 says why that has a deadline; this "
            "is the half of it that needs agreeing between organisations rather than "
            "building inside one."
        ),
        exists=(
            "RFC 3161 and the ETSI archival profiles define the mechanism thoroughly. "
            "Neither says whose timestamps a national metrology institute should accept."
        ),
        consequence=(
            "A certificate timestamped by an authority the verifier does not recognise "
            "is worth no more than one never timestamped at all — and that is discovered "
            "decades after the mistake was made."
        ),
        forum=(
            "The arrangements, or an existing trust-list scheme borrowed wholesale. "
            "Inventing a metrology-specific one would be the wrong instinct."
        ),
    ),
    HarmonisationItem(
        key="governing-copy",
        tier="irreversible",
        title="Which copy governs",
        status="open",
        requirement=(
            "When a calibration exists as both a standardised document and a credential, "
            "one of them has to be the one that counts. Not stating which is a decision "
            "too, and the worst-behaved one."
        ),
        demonstrated=(
            f"Every calibration certificate here carries a PTB/DKD DCC "
            f"{DCC_SCHEMA_VERSION}, with quantities in D-SI {SI_VERSION}, alongside a "
            "readable credential subject, and the pipeline checks the two agree. "
            "ARCHITECTURE.md sets out the three available answers and favours making the "
            "document the subject."
        ),
        exists="",
        consequence=(
            "Two implementations answering differently disagree about what a certificate "
            "says while both verify it perfectly. Changing the answer afterwards is a "
            "migration across decades of archives that nobody will fund."
        ),
        forum=(
            "Wherever the certificate format is governed — which is itself unsettled, "
            "and is the next tier down."
        ),
    ),
    HarmonisationItem(
        key="persistence",
        tier="irreversible",
        title="How long an identifier goes on meaning what it means",
        status="open",
        requirement=(
            "did:web encodes an organisation as a domain name. Somebody has to commit "
            "that the domain still means that organisation in 2050, and say what becomes "
            "of the identifier when a body is renamed, merged or dissolved."
        ),
        demonstrated=(
            "The identifiers here are .example domains that will never move, never "
            "merge and never lapse. That is precisely the failure a demonstration cannot "
            "show you."
        ),
        exists="",
        consequence=(
            "A calibration certificate outlives the organisation that issued it. Without "
            "a persistence commitment, verification degrades quietly as the web changes "
            "underneath it, and nothing announces that it has."
        ),
        forum="Each arrangement for its own members, against a common minimum.",
    ),
    # ---------------------------------------------------------------- tier 3
    HarmonisationItem(
        key="digital-si",
        tier="optional",
        title="One digital representation of the SI",
        status="emerging",
        requirement=(
            "Quantities have to travel in a form both ends parse identically, including "
            "the awkward parts: prefixes, powers, and units that are ratios."
        ),
        demonstrated=(
            f"Quantities here are written in D-SI {SI_VERSION}, inside the carried "
            "PTB/DKD DCC."
        ),
        exists=(
            "Two candidates exist, and that is the difficulty. D-SI comes from the PTB; "
            "the SI Digital Framework comes from the BIPM. They are two digital "
            "representations of the same SI, and the asymmetry between a national "
            "construction and an international one is the substance of the choice rather "
            "than a footnote to it."
        ),
        consequence=(
            "Certificates parse at some recipients and not others, and the split follows "
            "institutional lines rather than technical merit."
        ),
        forum=(
            "The BIPM, with the PTB. A reconciliation between two existing things, not a "
            "decision taken on a blank page."
        ),
    ),
    HarmonisationItem(
        key="certificate-format",
        tier="optional",
        title="A certificate format with international standing",
        status="emerging",
        requirement=(
            "One machine-readable calibration certificate that a body in another region "
            "will accept without a bilateral arrangement behind it."
        ),
        demonstrated=(
            f"The PTB/DKD DCC {DCC_SCHEMA_VERSION} is carried by every calibration "
            "certificate here, as a subset rather than a conformant document, and with "
            "its signature slot unused."
        ),
        exists=(
            "The DCC is much the most mature candidate, and it is a national "
            "construction of the PTB and the DKD. Its technical merit is not in "
            "question. Its route to worldwide adoption is a governance question and "
            "deserves to be argued as one rather than assumed away."
        ),
        consequence=(
            "Regions standardise separately, and the cross-border case is the one that "
            "fails — again."
        ),
        forum=(
            "An international body, or the DCC brought through one. Which of those, and "
            "by what route, is the open part."
        ),
    ),
    HarmonisationItem(
        key="measurands",
        tier="optional",
        title="Measurand and quantity identifiers",
        status="emerging",
        requirement=(
            "A resolvable identifier for the measured quantity, so that a CMC and an "
            "accreditation scope can be compared by a machine rather than by a person "
            "who knows both documents."
        ),
        demonstrated=(
            "This demonstration invents dc.resistance and compares it with string "
            "equality. The CMC and the accreditation scope agree only because one author "
            "wrote both files. Chapter 5 decides whether a calibration may carry the "
            "CIPM MRA logo on exactly that comparison, and it would not survive contact "
            "with two organisations that had never spoken."
        ),
        exists=(
            "Work is under way at ISO and IEC. The correct move is to wait and adopt, "
            "not to invent a third scheme in the meantime."
        ),
        consequence=(
            "Scope enforcement between bodies is impossible. A laboratory well inside "
            "its accreditation is refused because nobody agreed on a name for resistance."
        ),
        forum="ISO and IEC, where it is already happening.",
    ),
    HarmonisationItem(
        key="uncertainty-transport",
        tier="optional",
        title="How uncertainty travels, dependencies included",
        status="open",
        requirement=(
            "A registered identifier for each uncertainty representation, and at least "
            "one representation that carries dependency structure rather than a single "
            "number."
        ),
        demonstrated=(
            "Certificates here offer the classical value with U, two METAS UncLib "
            "serialisations and a GTC archive, under format labels this project invented "
            "because no registry has any."
        ),
        exists=(
            "Nothing, and this is the one item on the page where the demonstration's "
            "invented labels reflect a real absence rather than an oversight. Neither "
            "D-SI nor the SI Digital Framework models dependency structure."
        ),
        consequence=(
            "Recipients fall back to the classical statement and the correlation "
            "information is lost. Chapter 7 measures what that costs, and the answer is "
            "not small."
        ),
        forum="The JCGM would be the natural home, alongside the GUM itself.",
    ),
)


@dataclass(frozen=True)
class NextStep:
    """One rung of the ladder, and what it would unblock.

    Attributes:
        order: Position in the ladder, from what needs nobody's permission upward.
        scope: Who is in a position to act at this rung.
        title: Short description of the step.
        detail: What it involves, and why it sits where it sits.
        unblocks: Keys of the :class:`HarmonisationItem` entries it advances.
    """

    order: int
    scope: str
    title: str
    detail: str
    unblocks: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        """Return the step as the interface displays it.

        Returns:
            A JSON-compatible dictionary.
        """
        return {
            "order": self.order,
            "scope": self.scope,
            "title": self.title,
            "detail": self.detail,
            "unblocks": list(self.unblocks),
        }


#: The ladder is dependency structure rather than advice. Whoever turns out to act, this
#: is the order the blocking relationships force: each rung is possible without the ones
#: above it, and none of the upper rungs deliver anything without the lower ones.
NEXT_STEPS: tuple[NextStep, ...] = (
    NextStep(
        order=1,
        scope="This demonstration",
        title="Use the identifiers that already exist",
        detail=(
            "Replace the free-text measurands and units with SI Digital Framework "
            "identifiers, and point the CMC entries at resolvable KCDB CMC identifiers. "
            "It is a small change, it removes the manufactured agreement that chapter 5 "
            "quietly depends on, and it is the smallest honest proof of this entire "
            "argument. Anything that cannot manage this step should be treated with "
            "suspicion when it proposes the later ones."
        ),
        unblocks=("units", "measurands"),
    ),
    NextStep(
        order=2,
        scope="One institute, alone",
        title="Publish a key, and start timestamping",
        detail=(
            "A did.json at a well-known path, one class of certificate signed alongside "
            "the PDF it already issues, and trusted timestamps from the first day rather "
            "than the first audit. And keep the dependency structure of every uncertainty "
            "budget: it costs nothing to retain and it is the one thing on this page that "
            "cannot be recovered once discarded."
        ),
        unblocks=("did-method", "timestamps", "uncertainty-transport"),
    ),
    NextStep(
        order=3,
        scope="Two institutes, bilaterally",
        title="Verify each other, and write down every disagreement",
        detail=(
            "Each institute verifies the other's certificates and records every point "
            "where they differ. This surfaces most of the first tier for the cost of two "
            "engineers and a fortnight, it produces evidence rather than opinion, and it "
            "requires nobody's permission."
        ),
        unblocks=("cryptosuite", "did-method", "status-meaning"),
    ),
    NextStep(
        order=4,
        scope="A regional metrology organisation",
        title="Write the profile down",
        detail=(
            "Fix the first-tier choices for a region's members. Regional scope is where "
            "this has historically been tractable, and a profile that demonstrably works "
            "regionally is the evidence an international one would otherwise spend years "
            "arguing about."
        ),
        unblocks=("cryptosuite", "did-method", "status-meaning", "anchors"),
    ),
    NextStep(
        order=5,
        scope="The BIPM",
        title="Sign the KCDB",
        detail=(
            "The CMC data already exists, is already peer reviewed, and now resolves. "
            "What is missing is a signature and a stable content digest over each entry. "
            "This is the highest-value single item on the list, because every scope check "
            "downstream of it is currently trusting a fetch."
        ),
        unblocks=("anchors", "measurands"),
    ),
    NextStep(
        order=6,
        scope="The CIPM MRA and the Global ACI arrangement, jointly",
        title="Agree that the chains compose",
        detail=(
            "Everything above can happen without this, and none of it delivers the "
            "cross-border case without it. It is also the only item on the page with no "
            "existing forum: the two arrangements have no standing joint technical body, "
            "so creating somewhere for the conversation to happen is the actual first "
            "step, and it is an institutional one rather than a technical one."
        ),
        unblocks=("chain-crossing", "anchors"),
    ),
)


def items_in_tier(tier: str) -> tuple[HarmonisationItem, ...]:
    """Return every item belonging to one tier, in declaration order.

    Args:
        tier: The tier key, for example ``floor``.

    Returns:
        The matching items.
    """
    return tuple(item for item in HARMONISATION_ITEMS if item.tier == tier)
