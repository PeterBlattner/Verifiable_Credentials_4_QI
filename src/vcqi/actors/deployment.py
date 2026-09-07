"""What each role would actually have to run, and what it already runs.

The question this module answers is the one everybody asks after seeing the rest of the
demonstration: what IT infrastructure does any of this need? The answer is smaller than
people expect and very unevenly distributed, and both halves of that are worth showing
rather than asserting.

Two things make the burden small. Verification is a computation, not a conversation:
a verifier needs no account, no registration and no channel back to the issuer, so an
issuer operates no service on a verifier's behalf. And a credential travels with its
holder, so the documents an issuer must keep online are only the ones that say something
about the issuer itself -- its key, and which of its credentials it has since withdrawn.
The certificates themselves need not be hosted at all. :func:`hosting_burden` computes
that split from what the demonstration actually published rather than restating it here.

What is left is genuinely hard, and it is not capacity. It is key custody, which is a
governance problem with a technical surface, and long-term validation, because a
calibration certificate outlives the algorithm that signed it. Both are called out per
role below.

The profiles are editorial: they are an argument about deployment, not a measurement of
one. The counts they are shown beside are computed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "DeploymentProfile",
    "DEPLOYMENT_PROFILES",
    "ONLINE_KINDS",
    "host_of",
    "hosting_burden",
]

#: Kinds of document that say something about the issuer rather than about one
#: transaction, and which therefore have to be reachable for a verifier to finish. These
#: are the whole of what an issuer must keep online. The whois presentation is in the
#: list because recognition discovery falls back to it when a credential carries no
#: pointer of its own; everything per-certificate is not, because it reaches the verifier
#: in the holder's hands.
ONLINE_KINDS: frozenset[str] = frozenset(
    {"did-document", "status-list", "registry-entry", "schema", "presentation"}
)


@dataclass(frozen=True)
class DeploymentProfile:
    """The operational profile of one role in a deployment.

    Attributes:
        did: The organisation this profile describes.
        posture: One sentence on the overall size of the undertaking.
        custody: How the signing key would have to be held.
        custody_grade: ``root``, ``service`` or ``delegated``, ordering the three
            levels of key protection by how much ceremony they demand.
        availability: What breaks, and for whom, when this organisation is unreachable.
        already_runs: Infrastructure the organisation of this kind almost certainly
            operates today, and which the deployment reuses rather than replaces.
        must_add: Infrastructure that genuinely would not exist yet.
        hardest_part: The part that would actually consume the effort, which in every
            case here is not the part that looks hardest.
        scale: The volume this role handles, stated so it can be compared against what
            the hardware would do without noticing.
    """

    did: str
    posture: str
    custody: str
    custody_grade: str
    availability: str
    already_runs: tuple[str, ...]
    must_add: tuple[str, ...]
    hardest_part: str
    scale: str

    def to_json(self) -> dict[str, Any]:
        """Return the profile as the interface displays it.

        Returns:
            A JSON-compatible dictionary.
        """
        return {
            "id": self.did,
            "posture": self.posture,
            "custody": self.custody,
            "custodyGrade": self.custody_grade,
            "availability": self.availability,
            "alreadyRuns": list(self.already_runs),
            "mustAdd": list(self.must_add),
            "hardestPart": self.hardest_part,
            "scale": self.scale,
        }


#: The roles that span the range of the burden, from the trust anchor down to the
#: verifier that operates nothing at all.
#:
#: The accreditation body is deliberately left out: operationally it is the trust
#: anchor's profile at a smaller scale, and a column that says so adds length without
#: adding an argument. That reasoning would exclude an OIML Issuing Authority too, and
#: it is here anyway, for one reason the others do not have to answer for. An OIML
#: certificate is valid for about a decade where a calibration certificate is valid for
#: a year, so long-term validation -- which the institute's profile already calls the
#: hardest part -- stops being a caveat and becomes the design constraint. An Issuing
#: Authority also reviews rather than measures, which puts the hardest part of its
#: profile upstream, on the laboratory whose evidence it has to be able to re-check.
DEPLOYMENT_PROFILES: tuple[DeploymentProfile, ...] = (
    DeploymentProfile(
        did="did:web:bipm.example",
        posture=(
            "One static file and a signing ceremony. The infrastructure is trivial and "
            "the governance around it is not, which is the shape of the whole problem."
        ),
        custody=(
            "Root grade. A hardware security module, split custody, a witnessed key "
            "ceremony and a published rotation and compromise procedure. Everything "
            "downstream rests on this one key, so it is the one place where the "
            "ceremony is proportionate."
        ),
        custody_grade="root",
        availability=(
            "If the DID document is unreachable, nothing recognised under the CIPM MRA "
            "verifies anywhere in the world until it returns. It is a static file, so a "
            "CDN and a long cache lifetime answer this -- but it is a new single point "
            "of failure that the paper arrangement does not have."
        ),
        already_runs=(
            "A web presence at a stable domain, which is all did:web resolution needs.",
            "The KCDB: the CMC data, already curated and already peer reviewed.",
            "An editorial and review process governing what enters that database.",
        ),
        must_add=(
            "An HSM and the ceremony around it.",
            "A signing step in the KCDB publication pipeline, so each entry leaves with "
            "a signature and a stable content digest.",
            "A status list, republished whenever a participation is suspended.",
            "A registration authority function: deciding which identifier really "
            "belongs to which institute, and recording why.",
        ),
        hardest_part=(
            "Deciding who controls the key, and what happens the day it is compromised. "
            "That question has no technical answer, and every technical answer to it is "
            "a governance decision in disguise."
        ),
        scale=(
            "Roughly a hundred recognition credentials and a few thousand CMC entries, "
            "reissued on a review cycle measured in months. This is a batch job, not a "
            "service."
        ),
    ),
    DeploymentProfile(
        did="did:web:metas.example",
        posture=(
            "An institute that already signs certificates electronically is most of the "
            "way there. The work lands in the certificate production workflow, not in "
            "the cryptography."
        ),
        custody=(
            "Service grade. Realistically the same HSM already used for the qualified "
            "electronic signatures on PDF certificates, with a separate key and a "
            "separate purpose."
        ),
        custody_grade="service",
        availability=(
            "If the institute is unreachable, its own certificates stop verifying, but "
            "nobody else's do. A verifier that has cached the DID document keeps working "
            "-- with the caveat that caching a key is also how a verifier fails to "
            "notice a rotation."
        ),
        already_runs=(
            "A LIMS or equivalent that produces calibration certificates today.",
            "A signing capability, in most national institutes, for electronic "
            "signatures on the PDF certificates they already issue.",
            "A document archive with a retention period measured in decades.",
            "A stable domain and the ability to publish a file at a fixed path.",
        ),
        must_add=(
            "Emission of the credential from the existing workflow, so it is a "
            "by-product of issuing the certificate rather than a second process that "
            "can disagree with the first.",
            "A status list for withdrawn certificates.",
            "Structured capture of the uncertainty budget, including the dependency "
            "structure, which most systems today discard once U has been computed.",
            "Trusted timestamping at issuance, and an archival format that keeps the "
            "signature checkable after the algorithm has aged out.",
        ),
        hardest_part=(
            "Long-term validation. A certificate is kept for thirty years and a "
            "signature is comfortable for perhaps fifteen. This has to be designed in "
            "at the start, because a signature that was never timestamped cannot be "
            "given a timestamp afterwards."
        ),
        scale=(
            "Thousands of certificates a year. A P-256 signature takes well under a "
            "millisecond, so an institute's entire annual output signs in about a "
            "second. Throughput is not a consideration anywhere in this design."
        ),
    ),
    DeploymentProfile(
        did="did:web:callab.example",
        posture=(
            "The case that decides whether the design works in practice. A laboratory "
            "of fifteen people should operate almost none of this itself."
        ),
        custody=(
            "Delegated. A private key on a laboratory manager's laptop is worse than no "
            "cryptography at all, because it carries an assurance it cannot support. "
            "The realistic arrangement is custody by the accreditation body or a "
            "commercial trust service provider, with the laboratory authenticating to "
            "a signing service it does not run."
        ),
        custody_grade="delegated",
        availability=(
            "The DID document is a static file that can sit on the laboratory's "
            "existing website, or be hosted for it. Note that did:web keeps the "
            "laboratory's own name in the identifier even when somebody else holds the "
            "key -- which is exactly the right split, and is why did:key would not do."
        ),
        already_runs=(
            "A website at a domain it controls.",
            "Calibration software that already produces certificates as PDFs.",
        ),
        must_add=(
            "A did.json at a well-known path, which is a file upload.",
            "An arrangement with whoever will hold the key.",
            "A route from its calibration software to a signing service. For most such "
            "laboratories this arrives as a supplier update, not a project.",
        ),
        hardest_part=(
            "Making sure the laboratory is never asked to understand any of it. If "
            "adopting this requires a fifteen-person laboratory to reason about key "
            "management, it will not be adopted, and the certificates that most need "
            "the verifiability are exactly the ones that will not have it."
        ),
        scale=(
            "Hundreds of certificates a year, issued by people whose expertise is "
            "measurement and should not have to be anything else."
        ),
    ),
    # OIML and the Issuing Authority. The accreditation body was left out above because
    # "operationally it is the trust anchor's profile at a smaller scale", and the same
    # argument would exclude an Issuing Authority -- except for one thing no other
    # profile has to deal with. An OIML certificate is valid for about a decade, where a
    # calibration certificate is valid for a year or two. Long-term validation, which the
    # institute's profile calls the hardest part, is an order of magnitude harder when
    # the document has to still verify in 2034.
    DeploymentProfile(
        did="did:web:oiml.example",
        posture=(
            "A third anchor, with a third arrangement's worth of governance behind it. "
            "Operationally it looks like the BIPM's profile: two lists to publish, a key "
            "to protect, and nothing to compute. What is different is the "
            "<strong>lifetime of what it underwrites</strong> -- the recognitions it "
            "signs bound certificates that stay valid for a decade, so a key rotation "
            "here has to be survivable by documents issued long before it."
        ),
        custody=(
            "Root grade. The same problem as the other two anchors and no easier for "
            "being third: whoever holds this key can add an Issuing Authority to the "
            "scheme, and every certificate in the world beneath it rests on that not "
            "having happened quietly."
        ),
        custody_grade="root",
        availability=(
            "If the OIML is unreachable, a verifier that has not cached its recognition "
            "lists cannot establish that an Issuing Authority is approved, and every "
            "OIML certificate stops verifying rather than failing -- which is the right "
            "outcome and an unwelcome one. Certificates valid for ten years make the "
            "caching question sharper than it is anywhere else here: a verifier holding "
            "a copy from 2024 is holding something the scheme may have changed twice."
        ),
        already_runs=(
            "A public register of Issuing Authorities and Test Laboratories, searchable, "
            "which is the same information these credentials carry.",
            "A register of the certificates themselves, and their associated type "
            "evaluation reports.",
            "A publication process for Recommendations, with numbered editions.",
            "A stable domain, and decades of institutional continuity behind it.",
        ),
        must_add=(
            "A signing key, and the governance to say who may use it.",
            "The two recognition lists as signed credentials rather than as web pages, "
            "with a status list for a recognition that has been suspended.",
            "A decision about what the scheme means by suspension, which is not the same "
            "question as how to encode it.",
            "A published answer on Scheme A and Scheme B: whether they differ in what a "
            "verifier should check, and if so how a certificate says which it was issued "
            "under. This demonstration does not model the distinction at all.",
        ),
        hardest_part=(
            "Not the cryptography, and not even the key. It is that a Recommendation is "
            "not law, so this anchor underwrites a technical claim and no permission "
            "whatsoever -- and the value of the whole scheme depends on national "
            "authorities relying on it anyway. Making a credential say that clearly "
            "enough that a verifier acts on it, rather than reading a certificate as an "
            "approval, is the part with no technical answer."
        ),
        scale=(
            "A few hundred Issuing Authorities and laboratories, and a few thousand "
            "certificates, changing slowly. The lists are small enough to sign whole and "
            "republish; the interesting number is not throughput but retention."
        ),
    ),
    DeploymentProfile(
        did="did:web:legal-ia.example",
        posture=(
            "A certification body that already issues these certificates on paper. The "
            "work is in the certificate production workflow, as it is for an institute -- "
            "with one difference that runs through everything below. It "
            "<strong>reviews rather than measures</strong>, so what it has to be able to "
            "check is somebody else's document, and what it has to be able to prove later "
            "is that it checked."
        ),
        custody=(
            "Service grade. A signing key in whatever the body already uses for the "
            "electronic signatures on the certificates it issues today, with a separate "
            "key and a separate purpose."
        ),
        custody_grade="service",
        availability=(
            "If the Issuing Authority is unreachable, its own certificates stop "
            "verifying and nobody else's do. The uncomfortable case is the one where the "
            "body no longer exists: a certificate valid until 2034 outlives corporate "
            "arrangements, and somebody has to keep answering for its key and its status "
            "list after the organisation that made it has gone."
        ),
        already_runs=(
            "A certification workflow that reviews type evaluation reports and issues "
            "certificates against OIML Recommendations.",
            "A file of the reports it reviewed, kept for as long as the certificates "
            "are valid.",
            "An accreditation, in most cases, and the quality system that comes with it.",
        ),
        must_add=(
            "Verification of the type evaluation report as a document rather than as a "
            "PDF somebody read: that the laboratory was recognised for those tests on "
            "the day, and that the calibrations the tests rested on were live.",
            "Emission of the certificate as a credential from the existing workflow, so "
            "it is a by-product of issuing rather than a second process that can "
            "disagree with the first.",
            "A status list for withdrawn certificates, with a retention period measured "
            "against a ten-year validity rather than a one-year one.",
            "Trusted timestamping at issuance. A signature is comfortable for perhaps "
            "fifteen years and these certificates are valid for ten, so the margin is "
            "thinner here than anywhere else in this demonstration.",
        ),
        hardest_part=(
            "Checking the report it rests on, rather than filing it. Reviewing the test "
            "results is this body's defined job under the scheme, and today that review "
            "is a person reading a document and forming a judgement. Turning it into "
            "something a recipient can re-run means the evidence has to be structured, "
            "which means the laboratory upstream has to emit it that way -- so the "
            "hardest part of this profile is really a requirement on somebody else."
        ),
        scale=(
            "Tens to hundreds of certificates a year, each one the outcome of months of "
            "testing. Nothing about the volume is difficult; everything about the "
            "lifetime is."
        ),
    ),
    DeploymentProfile(
        did="did:web:surveillance.example",
        posture=(
            "Operates nothing. This is the half of the system that is genuinely free, "
            "and it is also the half on which all the value depends."
        ),
        custody=(
            "None. A verifier holds no key and signs nothing. It needs only a list of "
            "identifiers it has decided to trust, which is a policy artefact rather "
            "than a secret."
        ),
        custody_grade="delegated",
        availability=(
            "Verification is a local computation over documents the verifier already "
            "holds, plus a handful of cached fetches. It works on a laptop at a border "
            "post, and it keeps working with an intermittent connection."
        ),
        already_runs=("Whatever it inspects goods with today.",),
        must_add=(
            "A verifier library, embedded in an existing tool.",
            "A trust list: the identifiers of the anchors it accepts, and a decision "
            "about who maintains it.",
            "A policy for what a failed check means, which is the part that is not "
            "software.",
        ),
        hardest_part=(
            "Getting anyone to run it. Every benefit in this demonstration is "
            "conditional on the checking actually happening somewhere it does not "
            "happen today. If no verifier runs, the issuers have taken on cost and "
            "bought nothing."
        ),
        scale=(
            "One verification per document inspected, in milliseconds, against nothing "
            "that has to be online at the moment of checking except a key and a status "
            "list."
        ),
    ),
)

def host_of(url: str) -> str:
    """Return the host an https URL addresses.

    Args:
        url: The address.

    Returns:
        The host, or an empty string for anything that is not an https URL. Identifiers
        in ``did:`` form are deliberately not hosts: a DID document is counted once, at
        the web address it is actually served from.
    """
    if not url.startswith("https://"):
        return ""
    return url[len("https://") :].split("/", 1)[0]


def hosting_burden(kinds: Mapping[str, str], domain: str) -> dict[str, Any]:
    """Split what one organisation publishes into what must be online and what travels.

    This is the measurement behind the claim that the hosting requirement is small. A
    credential is presented by the party that holds it, so an issuer never serves one;
    what an issuer must serve is the small, slowly changing set of documents that
    describe the issuer itself. The ratio between the two is computed here rather than
    asserted, so it stays true as the demonstration world changes.

    Args:
        kinds: Mapping from published address to the kind of document published there,
            covering the whole world rather than one organisation.
        domain: The host whose burden to compute, for example ``metas.example``.

    Returns:
        The addresses that must be reachable, grouped by kind, together with the count
        of documents this organisation issued that need no hosting at all.
    """
    online: dict[str, list[str]] = {}
    travelling = 0
    for url, kind in kinds.items():
        if host_of(url) != domain:
            continue
        if kind in ONLINE_KINDS:
            online.setdefault(kind, []).append(url)
        else:
            travelling += 1

    return {
        "domain": domain,
        "online": [
            {"kind": kind, "urls": sorted(urls)}
            for kind, urls in sorted(online.items())
        ],
        "onlineCount": sum(len(urls) for urls in online.values()),
        "travellingCount": travelling,
    }
