"""What would have to be agreed between organisations, and by whom.

Chapter 10 asks what one organisation would have to run. This asks the harder question:
what would they all have to agree with each other, for a certificate written in one
country to mean the same thing in another. The two are different problems, and the second
is the one the quality infrastructure exists to solve.

There are three arrangements in this demonstration now, not two, and the third made the
list longer in a way worth naming: the OIML-CS raised two questions neither of the others
had to ask. What a document authorises as distinct from what it attests, and what
identifies a design rather than one instrument. Both are in the first tier, because
getting either wrong is not a missing feature but a wrong answer.

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

That same mistake had been made a second time, across the page rather than in one item, and
it took a reader who works on these specifications to see it. Seven items carried *nothing
exists yet*. Five of them were answered, or half answered, in specifications that were
published while this was being written: did:webvh for rotation and withdrawal, Bitstring
Status List for what a status value means, ETSI trusted lists for distributing anchors, and
did:webvh again for what becomes of an identifier when an organisation moves. The reviewer's
own estimate was that only about a fifth of the list needed a long argument. Recounting from
the items themselves puts it near a quarter, and the chapter now counts rather than asserts.

So the ``exists`` field on those items opens by saying what the first draft got wrong. That
is deliberate and it should stay: a page about what nobody has agreed yet is exactly the
kind of page that goes stale by quietly overstating the gap, and showing one correction is
the cheapest way to warn a reader that there are probably others.

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
#:
#: ``partial`` was added after the review described in the cautions. It is the status the
#: first draft needed and did not have: a specification answers the mechanical half of the
#: question, and something institutional is left over. Without it every such item had to be
#: filed as ``open``, which read as *nothing exists* and was wrong five times.
STATUSES: frozenset[str] = frozenset({"available", "partial", "emerging", "open"})


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
        status: ``available``, ``partial``, ``emerging`` or ``open`` — what exists today.
        requirement: What would have to be agreed.
        demonstrated: What this demonstration chose, stated concretely.
        exists: The register or standard already covering it, or an empty string.
        source: Where to go and read it — a bare ``https://`` URL, or empty when there
            is nothing to read. The chapter renders it as a link, which is why it is a
            field of its own rather than a sentence inside ``exists``: every other field
            reaches ``textContent`` and markup in one shows as angle brackets.
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
    source: str
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
            "source": self.source,
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
        source="https://www.w3.org/TR/vc-data-integrity/",
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
        key="exchange",
        tier="floor",
        title="One protocol for asking, not just one format for answering",
        status="partial",
        requirement=(
            "Every item above this one is about what a certificate says. This is about "
            "how anybody comes to be holding it. Two organisations have to agree how a "
            "presentation is requested, what a request may ask for, how the answer is "
            "bound to the request so it cannot be replayed, and what a refusal looks "
            "like. Agreeing the document format and not the exchange leaves two parties "
            "able to read each other's certificates and unable to obtain one."
        ),
        demonstrated=(
            "Chapter 12 now shows both answers. It implements VCALM's exchange for "
            "three cases, including the one the quality infrastructure is actually made "
            "of: a party that verifies what was presented and issues in the same round "
            "trip. What it does not implement is authorization, which is the half a real "
            "deployment argues about - anyone may open an exchange here and the "
            "fictional holders will present for them.\n\n"
            "Beside it the chapter measures the other answer, which is to need no "
            "protocol at all. Every credential here already verifies from a file, and "
            "the audit reports exactly how much of a verification can arrive that way "
            "and what is left over."
        ),
        exists=(
            "More than one answer, which is the difficulty rather than the absence. "
            "VCALM is a W3C Working Draft describing exactly this exchange, and it is "
            "the one built here. OpenID for Verifiable Presentations answers the same "
            "question differently and is what the European digital identity wallets are "
            "deploying, so for a quality infrastructure that ever has to meet an EUDI "
            "wallet the choice is already half made by somebody else. Choosing between "
            "them is a profile decision, not a research problem.\n\n"
            "And there is a third position, which is that the question is smaller than "
            "it looks. UN/CEFACT's portable-credential architecture argues that no "
            "protocol is needed for most of it: a signed document travels by whatever "
            "means is to hand, and a network of hubs and pipes never reaches everyone "
            "who needs the document anyway. UNVTD names OpenID4VP where it names a "
            "protocol at all, and says it is compatible with business wallets without "
            "depending on them. On that reading a protocol is what you need for the "
            "narrow case where the verifier has to ask, and agreeing one is less urgent "
            "than agreeing what the document says."
        ),
        source="https://www.w3.org/TR/vcalm-1.0/",
        consequence=(
            "The cross-border case fails at the first step rather than the last. Two "
            "conforming implementations hold certificates each could verify perfectly "
            "and have no way to hand one over - which is the clearest possible instance "
            "of this page's own test, and it went unlisted until a reviewer pointed at "
            "the exchange this project had never built."
        ),
        forum=(
            "The arrangements, choosing from what exists rather than writing anything. "
            "The consequential part is not which protocol but whether the choice is made "
            "once for the quality infrastructure or once per country, and the second is "
            "the default that happens when nobody decides."
        ),
    ),
    HarmonisationItem(
        key="did-method",
        tier="floor",
        title="One identifier method, and an agreed meaning for resolving it",
        status="partial",
        requirement=(
            "What remains is the choice, and the trust placed in the very first fetch. "
            "Which method the arrangements adopt is unsettled, and whatever a verifier "
            "retrieves the first time it meets an organisation it has to believe on the "
            "strength of the web's own certificate authorities, because there is nothing "
            "yet to check it against."
        ),
        demonstrated=(
            "Every organisation here is a did:web resolved from its own domain, and "
            "resolution is a local lookup that never touches the network. A key is "
            "published once and never rotates. That is exactly the part a demonstration "
            "cannot exercise honestly, and this one does not try to."
        ),
        exists=(
            "This item said the resolution step was specified nowhere, and that was "
            "wrong. did:webvh is did:web with a verifiable history: the organisation "
            "publishes an append-only log instead of a single document, and each entry "
            "is signed by the keys the previous entry authorised. It answers all three "
            "questions the first draft asked. A rotated key is the same organisation "
            "because the identifier contains a hash of the log's first entry, which never "
            "changes. A compromised key is withdrawn by pre-rotation, where each entry "
            "commits to the hash of the key that may sign the next one. And what a "
            "verifier owes the resolution step is now written down: retrieve every entry "
            "and verify the chain. Moving a did:web to it is mechanical - the same URL, "
            "with did.jsonl in place of did.json - and the Swiss federal e-ID "
            "infrastructure already runs on it."
        ),
        source="https://identity.foundation/didwebvh/next/",
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
            "ACI arrangement and on a calibration traceable under the CIPM MRA. An OIML "
            "certificate rests on a type evaluation performed by a laboratory the OIML-CS "
            "recognises, using equipment calibrated under the other two. Somebody has to "
            "say how a verifier composes three arrangements, and what it means when two "
            "of them disagree about the same organisation."
        ),
        demonstrated=(
            "The OIML certificate here is the case in miniature: following it upward "
            "reaches OIML, and following its evidence downward reaches the BIPM through a "
            "chain that has nothing in common with the first except the laboratory in the "
            "middle. It composes because one author decided all three arrangements would "
            "use the same properties in the same way, which is the assumption a real "
            "deployment does not get to make."
        ),
        exists="",
        source="",
        consequence=(
            "Every cross-border case is left to each verifier to invent — and the "
            "cross-border case is the entire reason for doing any of this."
        ),
        forum=(
            "The CIPM MRA, the Global ACI arrangement and the OIML together. No two of "
            "them have a standing joint technical body, let alone all three, which makes "
            "this the hardest item here by some margin."
        ),
    ),
    HarmonisationItem(
        key="status-meaning",
        tier="floor",
        title="What a status value means, not how it is encoded",
        status="partial",
        requirement=(
            "What is left is the institutional answer itself, not a way to write it "
            "down: who may set a suspension, when it takes effect, whether it reaches "
            "back over certificates already issued, and what a laboratory is permitted "
            "to do while suspended. A carrier does not supply the policy it carries."
        ),
        demonstrated=(
            "Every issuer here publishes a status list and nothing in the world is "
            "revoked or suspended. The lists exist so the failure cases have something "
            "real to flip rather than a deletion standing in for a revocation. Each list "
            "carries revocation and suspension and nothing else, so none of them says "
            "what either would mean."
        ),
        exists=(
            "This item said the specification does not define, and could not define, "
            "what a status means to an accreditation body. The second half was wrong. "
            "Bitstring Status List became a W3C Recommendation in May 2025, and a list "
            "may declare a purpose of message, give every value its own statusMessage, "
            "and point a statusReference at the document that governs it. So an "
            "accreditation body can publish suspended pending review of scope 3.2, "
            "machine-readable, alongside the rule it is acting under. The mechanism is "
            "there and unused."
        ),
        source="https://www.w3.org/TR/vc-bitstring-status-list/",
        consequence=(
            "Two bodies reading the same bit differently is worse than having no status "
            "mechanism, because both of them believe they have checked."
        ),
        forum=(
            "Each arrangement for its own members — but the meanings have to line up "
            "where a chain crosses between them, and there are three of them now. A "
            "suspended OIML recognition and a suspended accreditation are the same bit "
            "and not obviously the same act."
        ),
    ),
    HarmonisationItem(
        key="anchors",
        tier="floor",
        title="What the anchors' identifiers are, and how a verifier learns them",
        status="partial",
        requirement=(
            "The mechanism is not the hard part and this item used to imply it was. What "
            "is left is who operates the list for the quality infrastructure, what it "
            "takes to be on it, and who is trusted to sign it — which is the same "
            "custody question one level up, and has no answer here."
        ),
        demonstrated=(
            "Three anchors are hard-coded as trusted — one per arrangement — and chapter "
            "4 lets a reader remove them to watch what stops verifying. That is the "
            "decision a real deployment has to make explicitly, publish, and defend, and "
            "each arrangement added makes the list longer without making it more agreed."
        ),
        exists=(
            "A signed list of trust anchors, fetched over the network and rotated "
            "without redeploying anything, is a solved and deployed problem. ETSI "
            "TS 119 612 specifies the format, and the European Commission runs it at "
            "scale under eIDAS: a signed list of lists points at each member state's "
            "own list, and each of those carries the certificates of the services it "
            "vouches for. Whether that particular format suits identifiers rather than "
            "X.509 certificates is a fair question. That it has to be invented is not."
        ),
        source="https://www.etsi.org/deliver/etsi_ts/119600_119699/119612/",
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
        key="legal-effect",
        tier="floor",
        title="What a document authorises, as distinct from what it attests",
        status="open",
        requirement=(
            "A verifier has to be able to tell evidence from permission. An OIML "
            "certificate says a type was evaluated against a Recommendation and met it. "
            "It does not say the instrument may be sold or used anywhere, because a "
            "Recommendation is not law and only a national or regional authority confers "
            "that. Somebody has to fix how a credential states which of the two it is, "
            "so a verifier can act on the difference instead of a reader having to know "
            "it."
        ),
        demonstrated=(
            "The OIML certificate carries legalEffect: none and a sentence saying what "
            "that means, and the schema behind the recognition makes it a validation "
            "requirement, so a certificate that quietly drops the disclaimer fails "
            "rather than reading as an approval. That is one project inventing one "
            "property name. The authority that would convert this evidence into "
            "permission is not modelled here at all."
        ),
        exists=(
            "Nothing, and the near miss is worth naming because it would be reached for "
            "first. The data model has termsOfUse, which sounds like the answer and is "
            "not: it constrains what a recipient may do with the credential, not what "
            "the credential permits in the world. Pressing it into this service would "
            "produce a document that reads plausibly to a person and means something "
            "else to a machine, which is worse than the blank page."
        ),
        source="https://www.w3.org/TR/vc-data-model-2.0/#terms-of-use",
        consequence=(
            "A verifier that reads an attestation as an authorisation is worse than one "
            "that reads nothing, because it clears goods nobody approved and reports "
            "that it checked. This is the one item on the page where getting it wrong "
            "does active harm rather than merely failing to help."
        ),
        forum=(
            "The OIML for its own certificates, and the W3C or its successor for the "
            "general property, since the distinction is not peculiar to metrology: any "
            "credential that attests without authorising has the same problem."
        ),
    ),
    HarmonisationItem(
        key="type-identity",
        tier="floor",
        title="What identifies a type, rather than an instrument",
        status="open",
        requirement=(
            "Everything else in this demonstration is about one physical object with a "
            "serial number. A type certificate covers a design, and the OIML-CS extends "
            "that to families of instruments, to modules, and to families of modules. "
            "Two parties have to be able to agree that the instrument in front of one of "
            "them is the type the other certified, which needs an identifier for a design "
            "and a rule for when a variant is still the same design."
        ),
        demonstrated=(
            "A type here is a urn with a manufacturer designation, an accuracy class and "
            "a list of module names, and nothing checks any of it. A meter presented at a "
            "border could differ from the evaluated type in any respect not written down, "
            "and the certificate would still verify."
        ),
        exists="",
        source="",
        consequence=(
            "Without it a type certificate is a document about nothing in particular. It "
            "verifies, it reaches an anchor, and it cannot be tied to the object being "
            "inspected — which is the only reason anyone wanted it."
        ),
        forum=(
            "The OIML, whose scheme already has the vocabulary of families and modules "
            "and would have to say how each is identified. Manufacturers would have to "
            "agree to use it, which is the harder half."
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
            "its quantity and the CGPM resolution that defined it." "\n\n"
            "Worth knowing how easily this gets skipped by people who are not "
            "metrologists: UN/CEFACT's Digital Conformity Credential writes a measured "
            "result with its unit as a bare string, so a UN construction published in "
            "2026 has the same gap this demonstration has. A register existing is not the "
            "same as anybody using it."
        ),
        source="https://si-digital-framework.org/SI?lang=en",
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
        status="partial",
        requirement=(
            "Long-term validation needs a timestamp from an authority the eventual "
            "verifier trusts — possibly thirty years later, and probably in a different "
            "country from the one that issued the certificate. Which authorities those "
            "are is the open half, and it is a list to be agreed rather than a mechanism "
            "to be built."
        ),
        demonstrated=(
            "Nothing here is timestamped. Chapter 10 says why that has a deadline; this "
            "is the half of it that needs agreeing between organisations rather than "
            "building inside one."
        ),
        exists=(
            "RFC 3161 and the ETSI archival profiles define the mechanism thoroughly. "
            "Neither says whose timestamps a national metrology institute should accept "
            "— and the item below changes how much of this a timestamp has to carry, "
            "because an issuer keeping a witnessed log of its own key history answers "
            "was this key valid then without any third party being asked."
        ),
        source="https://www.rfc-editor.org/rfc/rfc3161",
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
        source="",
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
        status="partial",
        requirement=(
            "Somebody has to commit that an identifier still means the same organisation "
            "in 2050, and say what becomes of it when a body is renamed, merged or "
            "dissolved. The technical half has an answer. The commitment does not, and "
            "this is the one item on the page where nobody can have the answer yet: it "
            "is a claim about thirty years that only thirty years of operation will "
            "settle. Theories exist. Evidence cannot."
        ),
        demonstrated=(
            "The identifiers here are .example domains that will never move, never "
            "merge and never lapse. That is precisely the failure a demonstration cannot "
            "show you."
        ),
        exists=(
            "Rather more than the first draft credited. Under did:webvh an identifier is "
            "anchored on a hash of its own first log entry rather than on where it is "
            "hosted, so an organisation that changes domain keeps the identifier and a "
            "verifier can confirm the move rather than trusting an announcement of it. "
            "Watchers - third parties that cache logs by that hash - are specified to go "
            "on serving one after the original location has gone. That covers renaming "
            "and moving. It does not cover dissolution, and no mechanism will: what "
            "happens when the body is simply gone is an institutional undertaking about "
            "who inherits the obligation."
        ),
        source="https://identity.foundation/didwebvh/next/",
        consequence=(
            "A calibration certificate outlives the organisation that issued it. Without "
            "a persistence commitment, verification degrades quietly as the web changes "
            "underneath it, and nothing announces that it has."
        ),
        forum="Each arrangement for its own members, against a common minimum.",
    ),
    HarmonisationItem(
        key="event-logs",
        tier="irreversible",
        title="A log of what was true, not a document saying what is true",
        status="partial",
        requirement=(
            "A verifier meeting a certificate in 2050 has to establish what was true in "
            "2026: which key the issuer held, whether the accreditation behind it was "
            "live on the day it was issued, whether a suspension came before or after. A "
            "document says what is true now. Answering the question needs an append-only "
            "log, each entry signed and naming the hash of the one before, so the order "
            "of events is evidence rather than testimony. What has to be agreed is who "
            "witnesses those logs, and how far back a verifier is required to walk."
        ),
        demonstrated=(
            "Nothing here keeps history at all. Every DID document, status list and "
            "registry entry is a single current document that is simply replaced, and a "
            "reader who wanted to know what any of them said last year would have no way "
            "to find out and no way to notice that they could not. The whole "
            "demonstration verifies against the present tense."
        ),
        exists=(
            "The pattern is established and one instance of it is in production. "
            "did:webvh's log is exactly this, with optional witnesses that co-sign "
            "entries before they are published, so a compromised key alone cannot "
            "rewrite a history. The W3C Credentials Community Group has a Cryptographic "
            "Event Log specification generalising it beyond identifier documents. Both "
            "are younger than the rest of the page and neither is a Recommendation."
        ),
        source="https://w3c-ccg.github.io/cel-spec/",
        consequence=(
            "Two verifiers reconstruct different pasts from the same evidence, and "
            "neither can show the other is wrong. It sits in this tier and not the third "
            "for a blunt reason: a log not kept from the first day cannot be "
            "reconstructed afterwards. Every year of not keeping one is a year that "
            "cannot later be verified."
        ),
        forum=(
            "Nobody, to start with. An institute can keep a log without asking anyone, "
            "and it is worth keeping before the question of whose witnesses count has an "
            "answer. The agreement is only needed at the point of mutual reliance."
        ),
    ),
    HarmonisationItem(
        key="retrieval",
        tier="irreversible",
        title="Who still serves the documents a verification reads",
        status="partial",
        requirement=(
            "Verifying a credential is not reading one file. Somebody has to undertake "
            "that the supporting documents are still retrievable decades later, and "
            "somebody has to say where a verifier looks when the original host does not "
            "answer."
        ),
        demonstrated=(
            "Chapter 10 measures this without naming it. Verifying one certificate of "
            "conformity reads 31 distinct documents from 7 hosts. The credential itself "
            "travels with its holder and is safe. The other 30 - DID documents, "
            "accreditation scopes, KCDB entries, validation schemas, status lists, and "
            "the uncertainty representations published by reference rather than inline - "
            "are fetched from wherever they live, and every one of them is a way for a "
            "verification to stop working without anything having been tampered with."
        ),
        exists=(
            "Partly, and unevenly. Watchers cache identifier logs. Content addressing "
            "makes a document self-verifying wherever it is found, and this "
            "demonstration already digests most of what it references, so a copy from "
            "anywhere is checkable - which means the problem is location, not integrity. "
            "General web archives cover the rest by accident rather than by undertaking. "
            "What is missing is an obligation: nobody has said who keeps a 2026 CMC "
            "entry reachable in 2056, or how a verifier finds it once the BIPM has "
            "reorganised its URLs."
        ),
        source="https://www.w3.org/TR/vc-data-integrity/",
        consequence=(
            "Verification decays instead of failing. A chain that once reached an anchor "
            "returns fewer documents each decade, and a verifier reports what it could "
            "not fetch rather than a verdict — assuming it was written to notice the "
            "difference, which this one is and most will not be."
        ),
        forum=(
            "Whoever publishes each register, for their own documents. The BIPM for the "
            "KCDB, each accreditation body for its scopes. It is a commitment rather "
            "than a standard, which is why it belongs on this page and not in a "
            "specification."
        ),
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
        source="",
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
        key="smart-recommendations",
        tier="optional",
        title="Machine-actionable requirements, in the Recommendation itself",
        status="emerging",
        requirement=(
            "A recognition bounds what an entity may issue by pointing at a schema. For "
            "an accreditation scope this project had to invent the schema, because the "
            "scope is prose. An OIML Recommendation is a numbered, edition-controlled "
            "published document, so the schema could be derived from it rather than "
            "written about it — if the Recommendation carried its requirements in a form "
            "a machine can read."
        ),
        demonstrated=(
            "The recognition of the Issuing Authority points at a JSON Schema built by "
            "hand from a reading of R 46. It pins the Recommendation identifier and "
            "requires the certificate to reference its type evaluation report and to "
            "state that it authorises nothing. Those are this project's judgements about "
            "what R 46 requires, not R 46 speaking for itself, and a reader should treat "
            "the numbers in it accordingly."
        ),
        exists=(
            "The OIML has a sub-group on machine-readable documents under its "
            "Digitalization Task Group, founded in November 2022, whose remit is "
            "guidance and exchange towards machine-readable OIML documents. Its stated "
            "prerequisites are a revision of OIML B 6 and clear requirements for the "
            "numbering and organisation of sections, together with harmonised use of "
            "vocabulary in headers and titles. R 60 is the pilot Recommendation, and the "
            "group exchanges with IEC Strategic Group 12. No completion dates are stated."
        ),
        source="",
        consequence=(
            "Two Issuing Authorities encoding the same Recommendation differently would "
            "bound themselves differently while both citing the same document, and a "
            "verifier comparing their certificates would have no way to notice."
        ),
        forum=(
            "The OIML, in a sub-group that already exists. Like the unit identifiers "
            "above, this is closer to adoption than to agreement — which is why it sits "
            "in this tier rather than the first: the certificate works today with an "
            "invented schema, it just cannot be checked against the real requirement."
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
            "The PTB/DKD DCC is much the most mature candidate for a calibration "
            "certificate, and it is a national construction of the PTB and the DKD. Its "
            "technical merit is not in question. Its route to worldwide adoption is a "
            "governance question and deserves to be argued as one rather than assumed "
            "away.\n\n"
            "There is now a second candidate carrying the international standing the "
            "first lacks, and it is not a replacement. UN/CEFACT's Digital Conformity "
            "Credential, under the UN Transparency Protocol, models third-party "
            "conformity assessment: an attestation, the criteria assessed against, a "
            "pass or fail, and a measured result. That is the testing and certification "
            "case rather than the calibration one — no traceability chain, and no "
            "uncertainty. So the honest reading is that the quality infrastructure has "
            "one mature format without standing and one standing format that does not "
            "reach metrology, and nobody has joined them.\n\n"
            "It is also called the DCC, which is the reason every mention in this "
            "project says PTB/DKD DCC."
        ),
        source="https://untp.unece.org/docs/specification/ConformityCredential/",
        consequence=(
            "Regions standardise separately, and the cross-border case is the one that "
            "fails — again. Or two formats each cover half of it and neither covers "
            "the join, which is the shape the problem actually has now."
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
        source="",
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
            "D-SI nor the SI Digital Framework models dependency structure, and a third "
            "source now confirms it from a different direction: UN/CEFACT's Digital "
            "Conformity Credential, at "
            "https://untp.unece.org/docs/specification/ConformityCredential/, is a UN "
            "construction for third-party conformity assessment, and it carries a "
            "measured result as a value and a unit with no uncertainty of any kind. "
            "Three independent efforts have now modelled a measurement without modelling "
            "how good it is, which makes this an absence in the field rather than an "
            "oversight in any one of them."
        ),
        source="",
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
        title="Publish a key as a log, and keep what you fetched",
        detail=(
            "One class of certificate signed alongside the PDF it already issues, and "
            "trusted timestamps from the first day rather than the first audit.\n\n"
            "Publish the key as a did:webvh log rather than a static did.json. It is the "
            "same file at the same path with one letter added, it costs nothing extra on "
            "the first day, and it is the difference between being able to rotate a key "
            "in ten years and not. Retain three things from the outset, because all three "
            "are cheap to keep and impossible to reconstruct: the log itself, the "
            "dependency structure of every uncertainty budget, and a copy of every "
            "document a verification of your own certificates had to fetch.\n\n"
            "Everything here is a retention decision disguised as an engineering one, "
            "which is why it sits this low on the ladder and needs nobody's agreement."
        ),
        unblocks=(
            "did-method",
            "timestamps",
            "uncertainty-transport",
            "event-logs",
            "retrieval",
        ),
    ),
    NextStep(
        order=3,
        scope="Two institutes, bilaterally",
        title="Verify each other, and write down every disagreement",
        detail=(
            "Each institute verifies the other's certificates and records every point "
            "where they differ. This surfaces most of the first tier for the cost of two "
            "engineers and a fortnight, it produces evidence rather than opinion, and it "
            "requires nobody's permission.\n\nHand the certificates over through an "
            "exchange rather than by email, even for a trial. The disagreements worth "
            "finding are in the protocol as much as in the documents, and emailing them "
            "hides exactly the half that a border crossing would depend on."
        ),
        unblocks=("cryptosuite", "did-method", "status-meaning", "exchange"),
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
    NextStep(
        order=7,
        scope="The OIML, alongside the other two arrangements",
        title="Say what a certificate authorises, and what identifies a type",
        detail=(
            "The legal-metrology branch adds two questions the other two never had to "
            "ask, and both are upstream of it being useful rather than merely working. "
            "One is the distinction between attesting and authorising, which this "
            "demonstration answers by inventing a property name and hoping. The other is "
            "what identifies a design, as against one instrument with a serial number — "
            "the OIML-CS already has the vocabulary of families and modules, and would "
            "have to say how each is identified before a certificate could be tied to the "
            "object an inspector is holding.\n\nThis rung is last because it depends on "
            "the ones above it and not the other way round. It is also the only one whose "
            "forum plainly exists: the OIML has a standing structure for exactly this "
            "conversation, which is more than can be said for the joint work in step 6."
        ),
        unblocks=("legal-effect", "type-identity", "smart-recommendations"),
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
