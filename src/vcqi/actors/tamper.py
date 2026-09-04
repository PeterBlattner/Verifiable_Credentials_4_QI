"""Ways the chain can be attacked or can quietly go wrong, and what catches each.

A demonstration in which everything always passes teaches very little. What makes the
pipeline worth having is that each check is the only thing standing between a specific
failure and a recipient who would otherwise believe the document.

The cases below fall into three groups, and the difference between them is the whole
argument.

*Forgery* is the easy group. Change a number, sign with the wrong key, point at a
different schema: the cryptography catches all of it, and any Verifiable Credentials
library would.

*Standing* is the second group. The document is genuine and correctly signed, but the
organisation that issued it was not entitled to, or no longer is: an accreditation that
lapsed, one that was suspended last week, a laboratory issuing outside the scope it was
accredited for. Signatures say nothing about any of this. Recognition chains and status
lists are what catch it.

*Metrological* is the third group, and it is the one no general-purpose credential
system addresses at all. Every signature verifies, every organisation is in good
standing, and the certificate still claims something it should not: an uncertainty
smaller than the institute has ever demonstrated, a level outside the published range,
or a budget that quietly understates what it inherited from the certificate above it.
These are caught only because the capability and the budget are machine-readable and
are actually checked.

Each case names the step that must catch it, and the test suite asserts that exactly
that step fails and that the failure is not reached by accident through some earlier
step breaking first.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from vcqi.actors.registry import actor_key
from vcqi.actors.scenarios import (
    CALLAB_CERTIFICATE,
    DEMO_NOW,
    METAS_CERTIFICATE,
    SAS_STATUS,
    STATUS_INDEX,
    World,
    build_world,
)
from vcqi.crypto.dataintegrity import sign_document
from vcqi.crypto.keys import build_did_document, derive_key
from vcqi.domain.uncertainty import evaluate, from_expanded_uncertainty, normal, rectangular
from vcqi.vc.model import budget_to_json, credential_reference, measurement_result_to_json
from vcqi.vc.status import BitstringStatusList, status_list_credential

__all__ = ["TamperCase", "TAMPER_CASES", "tamper_by_key", "apply_tamper", "TamperResult"]

ROGUE_DID = "did:web:rogue.example"


@dataclass(frozen=True)
class TamperResult:
    """A tampered world and the credential to present from it.

    Attributes:
        world: The world after the change.
        credential: The credential a verifier should be asked to check.
        verify_at: The instant to verify at, which some cases move.
    """

    world: World
    credential: dict[str, Any]
    verify_at: datetime


@dataclass(frozen=True)
class TamperCase:
    """One thing that can go wrong, and the check that is supposed to notice.

    Attributes:
        key: Stable identifier for the case.
        title: Short label for the interface.
        group: ``forgery``, ``standing`` or ``metrological``.
        description: What is being attempted, in plain terms.
        expected_step: Identifier of the step that must fail.
        catches: One sentence on why that step is what catches it.
        apply: Builds the tampered world.
    """

    key: str
    title: str
    group: str
    description: str
    expected_step: str
    catches: str
    apply: Callable[[], TamperResult]

    def to_json(self) -> dict[str, Any]:
        """Return the case as a JSON-compatible dictionary.

        Returns:
            Everything the interface needs to describe the case before running it.
        """
        return {
            "key": self.key,
            "title": self.title,
            "group": self.group,
            "description": self.description,
            "expectedStep": self.expected_step,
            "catches": self.catches,
        }


def _resign(credential: dict[str, Any], did: str, created: datetime) -> dict[str, Any]:
    """Sign a modified credential again, as its own issuer.

    Used for the cases where the issuer itself is the problem. Re-signing means the
    proof is genuinely valid, so the failure has to be caught by something other than
    the cryptography, which is exactly the point of those cases.

    Args:
        credential: The modified credential.
        did: Identifier of the issuer to sign as.
        created: Timestamp for the new proof.

    Returns:
        The re-signed credential.
    """
    signed, _ = sign_document(credential, actor_key(did), created=created)
    return signed


def _republish(world: World, name: str, credential: dict[str, Any]) -> None:
    """Replace a credential in the world, keeping the store consistent.

    Args:
        world: The world to update.
        name: Short name of the credential.
        credential: The replacement.
    """
    world.credentials[name] = credential
    world.store.publish(credential["id"], credential, "credential")


def _altered_value() -> TamperResult:
    """Change a measured value on a signed certificate without re-signing it."""
    world = build_world()
    credential = copy.deepcopy(world.credential("metas-calibration"))
    credential["credentialSubject"]["calibration"]["results"][0]["value"] = 10000.0042
    _republish(world, "metas-calibration", credential)
    return TamperResult(world, credential, DEMO_NOW)


def _forged_issuer() -> TamperResult:
    """Reissue the certificate under an identifier nobody recognises."""
    world = build_world()
    rogue_key = derive_key(ROGUE_DID)
    world.store.publish(ROGUE_DID, build_did_document(rogue_key), "did-document")

    credential = copy.deepcopy(world.credential("metas-calibration"))
    credential["id"] = "https://rogue.example/certificates/ROGUE-2026-0001"
    credential["issuer"] = {
        "id": ROGUE_DID,
        "type": "RecognizedIssuer",
        "name": "Definitely A Metrology Institute (demonstration)",
    }
    credential.pop("credentialStatus", None)
    signed, _ = sign_document(credential, rogue_key, created=DEMO_NOW)
    world.store.publish(signed["id"], signed, "credential")
    return TamperResult(world, signed, DEMO_NOW)


def _substituted_schema() -> TamperResult:
    """Loosen the published schema after recognition was granted."""
    world = build_world()
    url = "https://bipm.example/schemas/calibration-certificate-CH-EM-0042.json"
    schema = copy.deepcopy(world.schemas[url])
    properties = schema["properties"]["credentialSubject"]["properties"]["calibration"]
    properties["properties"]["results"]["items"]["properties"]["value"]["maximum"] = 1.0e12
    world.store.publish(url, schema, "schema")
    return TamperResult(world, world.credential("metas-calibration"), DEMO_NOW)


def _expired_accreditation() -> TamperResult:
    """Present a genuine certificate long after its validity has run out."""
    world = build_world()
    return TamperResult(
        world, world.credential("callab-calibration"), datetime.fromisoformat("2028-01-15T12:00:00+00:00")
    )


def _suspended_accreditation() -> TamperResult:
    """Suspend the accreditation body's recognition of the laboratory."""
    world = build_world()
    status = BitstringStatusList(purpose="suspension")
    status.set(STATUS_INDEX["https://sas.example/recognition/accredited-bodies-2026"])

    credential = status_list_credential(
        credential_id=SAS_STATUS,
        issuer={
            "id": "did:web:sas.example",
            "type": "RecognizedIssuer",
            "name": "Swiss Accreditation Service (demonstration)",
        },
        valid_from="2025-01-01T00:00:00Z",
        status_list=status,
        description="Accreditations granted by the accreditation body",
    )
    signed = _resign(credential, "did:web:sas.example", DEMO_NOW)
    world.store.publish(SAS_STATUS, signed, "status-list")
    return TamperResult(world, world.credential("callab-calibration"), DEMO_NOW)


def _uncertainty_below_cmc() -> TamperResult:
    """Claim an uncertainty smaller than the institute has ever demonstrated.

    The certificate is rebuilt with a genuinely consistent budget, so the arithmetic
    checks out and the signature is valid. What is wrong is that the result is better
    than the published capability, which only the registry can reveal.
    """
    world = build_world()
    credential = copy.deepcopy(world.credential("metas-calibration"))

    result = evaluate(
        lambda q: q["national_standard"] * q["ratio"] + q["repeatability"],
        [
            normal(
                "national_standard",
                "National standard, scaled from the quantum Hall resistance",
                10000.0007,
                1.0e-4,
                unit="ohm",
            ),
            normal("ratio", "Cryogenic current comparator ratio", 1.00000005, 2.0e-9),
            normal("repeatability", "Repeatability of the comparison", 0.0, 1.0e-4, unit="ohm"),
        ],
        unit="ohm",
    )
    calibration = credential["credentialSubject"]["calibration"]
    calibration["results"] = [measurement_result_to_json(result, nominal_value=1.0e4)]
    calibration["uncertaintyBudget"] = budget_to_json(result)

    signed = _resign(credential, "did:web:metas.example", DEMO_NOW)
    _republish(world, "metas-calibration", signed)
    return TamperResult(world, signed, DEMO_NOW)


def _level_outside_cmc() -> TamperResult:
    """Certify at a level above the published range, with everything else in order."""
    world = build_world()
    credential = copy.deepcopy(world.credential("metas-calibration"))

    result = evaluate(
        lambda q: q["national_standard"] * q["ratio"] + q["repeatability"],
        [
            normal(
                "national_standard",
                "National standard, scaled from the quantum Hall resistance",
                1.0e7,
                2.0,
                unit="ohm",
            ),
            normal("ratio", "Comparison bridge ratio", 1.0000001, 5.0e-8),
            normal("repeatability", "Repeatability of the comparison", 0.0, 1.0, unit="ohm"),
        ],
        unit="ohm",
    )
    calibration = credential["credentialSubject"]["calibration"]
    calibration["results"] = [measurement_result_to_json(result, nominal_value=1.0e7)]
    calibration["uncertaintyBudget"] = budget_to_json(result)

    signed = _resign(credential, "did:web:metas.example", DEMO_NOW)
    _republish(world, "metas-calibration", signed)
    return TamperResult(world, signed, DEMO_NOW)


def _understated_inheritance() -> TamperResult:
    """Enter a smaller inherited uncertainty than the parent certificate reports.

    The budget still adds up and the signature is valid, so nothing but a comparison
    against the referenced certificate can reveal it. This is the case that argues for
    carrying the budget inside the credential rather than only the final figure.
    """
    world = build_world()
    credential = copy.deepcopy(world.credential("callab-calibration"))
    parent = world.credential("metas-calibration")

    result = evaluate(
        lambda q: q["transfer_standard"] * q["ratio"] + q["drift"] + q["temperature"],
        [
            from_expanded_uncertainty(
                "transfer_standard",
                "Transfer standard, from certificate METAS-2026-0417",
                10000.0012,
                # A tenth of what the parent certificate actually reports.
                1.131370849898476e-4,
                unit="ohm",
                note=METAS_CERTIFICATE,
            ),
            normal("ratio", "Resistance bridge ratio", 1.0000031, 2.6e-6),
            rectangular(
                "drift",
                "Drift of the transfer standard since its calibration",
                0.0,
                5.0e-4,
                unit="ohm",
            ),
            rectangular(
                "temperature", "Temperature correction to 23 degC", 0.0, 2.0e-4, unit="ohm"
            ),
        ],
        unit="ohm",
    )
    calibration = credential["credentialSubject"]["calibration"]
    calibration["results"] = [measurement_result_to_json(result, nominal_value=1.0e4)]
    calibration["uncertaintyBudget"] = budget_to_json(result)
    calibration["traceableTo"] = {
        **credential_reference(parent, relation="CalibrationCertificateCredential"),
        "instrument": "urn:instrument:callab:standard-resistor:SR10K-0042",
    }

    signed = _resign(credential, "did:web:callab.example", DEMO_NOW)
    _republish(world, "callab-calibration", signed)
    return TamperResult(world, signed, DEMO_NOW)


def _broken_traceability() -> TamperResult:
    """Reissue the parent certificate after it was referenced by content digest."""
    world = build_world()
    parent = copy.deepcopy(world.credential("metas-calibration"))
    parent["credentialSubject"]["calibration"]["results"][0]["value"] = 10000.0031
    signed_parent = _resign(parent, "did:web:metas.example", DEMO_NOW)
    world.store.publish(METAS_CERTIFICATE, signed_parent, "credential")
    return TamperResult(world, world.credential("callab-calibration"), DEMO_NOW)


def _outside_accredited_scope() -> TamperResult:
    """Have the testing laboratory issue a calibration certificate.

    The laboratory is genuinely accredited, genuinely recognised, and its signature is
    genuinely valid. It is simply accredited for testing, not for calibration.
    """
    world = build_world()
    credential = copy.deepcopy(world.credential("callab-calibration"))
    credential["id"] = "https://testlab.example/certificates/HTS-CAL-2026-0001"
    credential["issuer"] = {
        "id": "did:web:testlab.example",
        "type": "RecognizedIssuer",
        "name": "Helvetia Testing Services GmbH (demonstration)",
        "recognizedIn": "https://sas.example/recognition/accredited-bodies-2026",
    }
    credential["issuer"]["recognizedIn"] = {
        "id": "https://sas.example/recognition/accredited-bodies-2026",
        "type": "RecognizedEntityCredential",
    }
    credential.pop("credentialStatus", None)
    signed = _resign(credential, "did:web:testlab.example", DEMO_NOW)
    world.store.publish(signed["id"], signed, "credential")
    return TamperResult(world, signed, DEMO_NOW)


def _unjustified_mra_logo() -> TamperResult:
    """Put the CIPM MRA logo on an accredited laboratory's own certificate."""
    world = build_world()
    credential = copy.deepcopy(world.credential("callab-calibration"))
    credential["credentialSubject"]["calibration"]["mraLogoAsserted"] = True
    signed = _resign(credential, "did:web:callab.example", DEMO_NOW)
    _republish(world, "callab-calibration", signed)
    return TamperResult(world, signed, DEMO_NOW)


#: Every failure the demonstration can produce on demand.
TAMPER_CASES: tuple[TamperCase, ...] = (
    TamperCase(
        key="altered-value",
        title="Edit a measured value",
        group="forgery",
        description=(
            "Someone changes the certified resistance from 10000.0012 to 10000.0042 ohm "
            "on an otherwise genuine certificate."
        ),
        expected_step="proof",
        catches=(
            "The signature covers a canonical form of the whole document, so changing "
            "any digit of it invalidates the proof."
        ),
        apply=_altered_value,
    ),
    TamperCase(
        key="forged-issuer",
        title="Issue under an invented identity",
        group="forgery",
        description=(
            "An organisation nobody has heard of issues a perfectly well-formed, "
            "correctly signed calibration certificate under its own key."
        ),
        expected_step="recognition",
        catches=(
            "The signature is valid, which is the point: a valid signature by an "
            "unknown party proves only that the party exists. There is no route from "
            "that identifier to the BIPM or Global ACI."
        ),
        apply=_forged_issuer,
    ),
    TamperCase(
        key="substituted-schema",
        title="Loosen the published schema",
        group="forgery",
        description=(
            "The schema referenced by the recognition is edited afterwards to permit a "
            "much wider range than the capability allows."
        ),
        expected_step="output-validation",
        catches=(
            "The recognition records the content digest of the schema it was granted "
            "against, so editing the published file makes it stop matching."
        ),
        apply=_substituted_schema,
    ),
    TamperCase(
        key="broken-traceability",
        title="Reissue a certificate that was already referenced",
        group="forgery",
        description=(
            "The national institute's certificate is reissued with a different value "
            "after the calibration laboratory referenced it."
        ),
        expected_step="traceability",
        catches=(
            "Traceability references carry a content digest, so a reference is only "
            "satisfied by the exact document that was referenced."
        ),
        apply=_broken_traceability,
    ),
    TamperCase(
        key="expired-accreditation",
        title="Present a certificate after it expired",
        group="standing",
        description=(
            "A genuine calibration certificate is presented in 2028, well after its "
            "stated validity ran out."
        ),
        expected_step="validity",
        catches=(
            "Validity is evaluated against the moment of verification, not the moment "
            "of issue."
        ),
        apply=_expired_accreditation,
    ),
    TamperCase(
        key="suspended-accreditation",
        title="Suspend the laboratory's accreditation",
        group="standing",
        description=(
            "The accreditation body suspends the laboratory. Every document it has "
            "already issued still carries a perfectly valid signature."
        ),
        expected_step="recognition",
        catches=(
            "Each link of the recognition chain is checked against the issuer's status "
            "list, so a suspension takes effect for every certificate at once without "
            "any of them being reissued."
        ),
        apply=_suspended_accreditation,
    ),
    TamperCase(
        key="outside-accredited-scope",
        title="Issue outside the accredited activity",
        group="standing",
        description=(
            "The testing laboratory issues a calibration certificate. It is genuinely "
            "accredited and correctly signed, but accredited for testing."
        ),
        expected_step="action",
        catches=(
            "Recognition is scoped to an activity and a capability, so being recognised "
            "is not the same as being recognised for this."
        ),
        apply=_outside_accredited_scope,
    ),
    TamperCase(
        key="uncertainty-below-cmc",
        title="Claim a better uncertainty than the CMC allows",
        group="metrological",
        description=(
            "The institute reports U = 0.00028 ohm where its published capability "
            "bottoms out near 0.0010 ohm. Signature valid, budget self-consistent, "
            "issuer in good standing."
        ),
        expected_step="scope",
        catches=(
            "The reported Expanded Uncertainty is compared against the uncertainty "
            "floor in the published CMC entry, which is the one thing a schema cannot "
            "express."
        ),
        apply=_uncertainty_below_cmc,
    ),
    TamperCase(
        key="level-outside-cmc",
        title="Certify outside the published range",
        group="metrological",
        description=(
            "The institute certifies a 10 Mohm standard, above the 100 kohm upper "
            "bound of its published capability."
        ),
        expected_step="scope",
        catches=(
            "The measured level is checked against the range in the CMC entry, and the "
            "schema generated from that entry catches it too."
        ),
        apply=_level_outside_cmc,
    ),
    TamperCase(
        key="unjustified-mra-logo",
        title="Use the CIPM MRA logo without standing",
        group="metrological",
        description=(
            "An accredited calibration laboratory puts the CIPM MRA logo on its own "
            "certificate. The logo belongs to the institutes that signed the "
            "arrangement, not to the laboratories they calibrate for."
        ),
        expected_step="mra-logo",
        catches=(
            "The claim to CIPM MRA coverage is an explicit machine-readable assertion, "
            "so it can be adjudicated instead of being taken on trust from an image."
        ),
        apply=_unjustified_mra_logo,
    ),
    TamperCase(
        key="understated-inheritance",
        title="Understate what was inherited from the parent certificate",
        group="metrological",
        description=(
            "The laboratory enters one tenth of the uncertainty its reference "
            "certificate actually reports. Its budget still adds up perfectly."
        ),
        expected_step="traceability.inherited",
        catches=(
            "The inherited contribution is compared against the certificate it names. "
            "Nothing else in the document is wrong, so nothing else could catch it."
        ),
        apply=_understated_inheritance,
    ),
)

_BY_KEY = {case.key: case for case in TAMPER_CASES}


def tamper_by_key(key: str) -> TamperCase | None:
    """Look up a case by identifier.

    Args:
        key: The case identifier.

    Returns:
        The case, or None when the identifier is unknown.
    """
    return _BY_KEY.get(key)


def apply_tamper(key: str) -> TamperResult:
    """Build the tampered world for one case.

    Args:
        key: The case identifier.

    Returns:
        The tampered world and the credential to present.

    Raises:
        KeyError: If the identifier is unknown.
    """
    case = _BY_KEY.get(key)
    if case is None:
        raise KeyError(f"no tamper case named {key!r}")
    return case.apply()
