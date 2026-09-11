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

from vcqi.actors.registry import actor_by_did, actor_key
from vcqi.actors.scenarios import (
    CALLAB_CERTIFICATE,
    METAS_CALIBRATED_ON,
    METAS_ISSUED,
    OIML_CERTIFICATE_ISSUED,
    OIML_EVALUATION_ISSUED,
    _dcc_for,
    _callab_result,
    DEMO_NOW,
    METAS_CERTIFICATE,
    SAS_STATUS,
    STATUS_INDEX,
    World,
    build_world,
)
from vcqi.crypto.dataintegrity import sign_document
from vcqi.crypto.keys import build_did_document, derive_key
from vcqi.domain.instruments import instrument_by_id
from vcqi.domain.oiml import recommendation_by_id
from vcqi.domain.uncertainty import evaluate, from_expanded_uncertainty, normal, rectangular
from vcqi.vc.model import (
    budget_to_json,
    credential_reference,
    measurement_result_to_json,
    uncertainty_representations,
)
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
    # The schema offers one branch per carrier of the measurement; the certificate
    # tampered with here carries its result, so that is the branch to loosen. Found by
    # what it requires rather than by position, because a second branch was added once
    # already and a third would move it again.
    branch = next(
        option
        for option in schema["anyOf"]
        if "calibration" in option["properties"]["credentialSubject"]["required"]
    )
    properties = branch["properties"]["credentialSubject"]["properties"]["calibration"]
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


def _dependency_disagrees() -> TamperResult:
    """Print one uncertainty and transmit a different one.

    The certificate reads exactly as before. Its dependency representation is replaced
    with one computed from a budget a third the size, and the digest is recomputed so
    nothing is broken cryptographically. A recipient reading the printed line and a
    recipient loading the XML get different answers from the same document.
    """
    world = build_world()
    credential = copy.deepcopy(world.credential("metas-calibration"))

    flattering = evaluate(
        lambda q: q["national_standard"] + q["repeatability"],
        [
            normal(
                "national_standard",
                "National standard, scaled from the quantum Hall resistance",
                10000.0012,
                1.0e-4,
                unit="ohm",
            ),
            normal("repeatability", "Repeatability of the comparison", 0.0, 1.5e-4, unit="ohm"),
        ],
        unit="ohm",
        context="METAS-2026-0417-flattering",
    )

    representations, artefacts = uncertainty_representations(
        flattering, credential_id=METAS_CERTIFICATE
    )
    world.publish_artefacts(artefacts)

    # Keep the classical statement the certificate already printed, and swap only the
    # dependency representations underneath it.
    result = credential["credentialSubject"]["calibration"]["results"][0]
    result["uncertaintyRepresentations"] = [
        result["uncertaintyRepresentations"][0]
    ] + [item for item in representations if item["type"] != "ClassicalStatement"]

    signed = _resign(credential, "did:web:metas.example", DEMO_NOW)
    _republish(world, "metas-calibration", signed)
    return TamperResult(world, signed, DEMO_NOW)


def _unshared_inputs() -> TamperResult:
    """Claim traceability while transmitting dependencies that contain none of it.

    The laboratory names the certificate of the institute, references it by content
    digest, and enters the right number in its budget. What it does not do is build on
    the dependency representation, so none of the input quantities of the institute
    appear in what it transmits. Every other check passes; the chain is asserted rather
    than realised.
    """
    world = build_world()
    credential = copy.deepcopy(world.credential("callab-calibration"))
    parent = world.credential("metas-calibration")
    parent_result = world.results["metas-calibration"]

    # Classical mode: the parent enters as two numbers, so it brings no identifiers.
    detached = _callab_result(parent_result, classical=True, context="AC-2026-1182")

    representations, artefacts = uncertainty_representations(
        detached, credential_id=CALLAB_CERTIFICATE
    )
    world.publish_artefacts(artefacts)

    calibration = credential["credentialSubject"]["calibration"]
    calibration["results"] = [
        measurement_result_to_json(
            detached, nominal_value=1.0e4, representations=representations
        )
    ]
    calibration["uncertaintyBudget"] = budget_to_json(detached)
    calibration["traceableTo"] = {
        **credential_reference(parent, relation="CalibrationCertificateCredential"),
        "instrument": "urn:instrument:callab:standard-resistor:SR10K-0042",
    }

    signed = _resign(credential, "did:web:callab.example", DEMO_NOW)
    _republish(world, "callab-calibration", signed)
    return TamperResult(world, signed, DEMO_NOW)


NEW_CASES: tuple[TamperCase, ...] = (
    TamperCase(
        key="dependency-disagrees",
        title="Transmit a different uncertainty from the one printed",
        group="metrological",
        description=(
            "The certificate prints U = 0.0011 ohm as before, but the dependency "
            "representation attached to it was computed from a much smaller budget. "
            "Signature valid, digests correct, issuer in good standing."
        ),
        expected_step="uncertainty.agreement",
        catches=(
            "Offering two representations of one measurement means they can be checked "
            "against each other. A recipient reading the printed line and one loading "
            "the dependency data would otherwise reach different conclusions from the "
            "same certificate, and neither would know."
        ),
        apply=_dependency_disagrees,
    ),
    TamperCase(
        key="unshared-inputs",
        title="Claim traceability without inheriting anything",
        group="metrological",
        description=(
            "The laboratory names the certificate of the institute, references it by "
            "content digest, and puts the right number in its budget, but builds its "
            "result from a freshly declared quantity instead of the transmitted one."
        ),
        expected_step="traceability.shared-inputs",
        catches=(
            "Every other traceability check compares paperwork with paperwork. This one "
            "looks at the arithmetic: if the result were really built on that "
            "certificate, its input quantities would be present, carrying the "
            "identifiers they were given. They are not."
        ),
        apply=_unshared_inputs,
    ),
)

TAMPER_CASES = TAMPER_CASES + NEW_CASES
_BY_KEY.update({case.key: case for case in NEW_CASES})


def _rebuild_metas_with_dcc(mutate) -> TamperResult:
    """Reissue the institute certificate with an altered PTB/DKD DCC.

    The document is changed, the digest recomputed and the credential signed again, so
    every cryptographic check passes and the only thing wrong is that the certificate now
    contradicts itself.

    Args:
        mutate: Takes the generated PTB/DKD DCC and returns the altered one.

    Returns:
        The tampered world and the reissued certificate.
    """
    world = build_world()
    credential = copy.deepcopy(world.credential("metas-calibration"))
    result = world.results["metas-calibration"]

    representations, artefacts = uncertainty_representations(
        result,
        credential_id=METAS_CERTIFICATE,
        dcc_xml=mutate(
            _dcc_for(
                result,
                certificate_number="METAS-2026-0417",
                performed_on=METAS_CALIBRATED_ON,
                issued=METAS_ISSUED,
                measurand="dc.resistance",
                conditions="(23.0 +/- 1.0) degC, DC, four-terminal connection",
                instrument=instrument_by_id(
                    "urn:instrument:callab:standard-resistor:SR10K-0042"
                ),
                laboratory=actor_by_did("did:web:metas.example"),
                customer=actor_by_did("did:web:callab.example"),
            )
        ),
    )
    world.publish_artefacts(artefacts)

    calibration = credential["credentialSubject"]["calibration"]
    calibration["results"][0]["uncertaintyRepresentations"] = representations

    signed = _resign(credential, "did:web:metas.example", DEMO_NOW)
    _republish(world, "metas-calibration", signed)
    return TamperResult(world, signed, DEMO_NOW)


def _dcc_disagrees() -> TamperResult:
    """State one value on the certificate and a different one inside the document."""
    return _rebuild_metas_with_dcc(
        lambda xml: xml.replace(
            "<si:value>10000.001200000035</si:value>",
            "<si:value>10000.004200000035</si:value>",
        )
    )


def _dcc_names_another_laboratory() -> TamperResult:
    """Let the document credit a different laboratory from the credential."""
    return _rebuild_metas_with_dcc(
        lambda xml: xml.replace(
            "<dcc:eMail>did:web:metas.example</dcc:eMail>",
            "<dcc:eMail>did:web:ptb.example</dcc:eMail>",
            1,
        )
    )


DCC_CASES: tuple[TamperCase, ...] = (
    TamperCase(
        key="dcc-disagrees",
        title="The PTB/DKD DCC states a different value from the printed line",
        group="metrological",
        description=(
            "The certificate prints 10000.0012 ohm and the PTB/DKD DCC inside it says "
            "10000.0042. The credential is signed correctly and every digest matches; "
            "the document simply disagrees with itself."
        ),
        expected_step="uncertainty.agreement",
        catches=(
            "Carrying a measurement several ways means the ways can be compared. A "
            "recipient reading the printed line and one parsing the PTB/DKD DCC would "
            "otherwise walk away with different numbers from the same certificate, and "
            "neither would have any reason to suspect it."
        ),
        apply=_dcc_disagrees,
    ),
    TamperCase(
        key="dcc-names-another-laboratory",
        title="The PTB/DKD DCC credits a different laboratory",
        group="metrological",
        description=(
            "The credential is issued by METAS and the PTB/DKD DCC inside it names PTB "
            "as the calibrating laboratory. Signature valid, digest correct, and the "
            "certificate contradicts itself about who did the work."
        ),
        expected_step="uncertainty.duplication",
        catches=(
            "Wrapping a standardised document in a credential says almost everything "
            "twice: who calibrated, for whom, when, under which number. The signature "
            "covers both copies and is perfectly content for them to disagree. Only a "
            "check that reads both notices, which is the argument for either comparing "
            "them or not duplicating them at all."
        ),
        apply=_dcc_names_another_laboratory,
    ),
)

TAMPER_CASES = TAMPER_CASES + DCC_CASES
_BY_KEY.update({case.key: case for case in DCC_CASES})
# ---------------------------------------------------------------- legal metrology
#
# None of these are new mechanisms. Each one is a document that signs correctly, reaches
# a genuine trust anchor, and is still wrong -- which is the only kind of failure worth
# adding, because the cryptographic half was never the hard part.


def _certified_against_the_wrong_recommendation() -> TamperResult:
    """Certify a type against a Recommendation the Issuing Authority is not approved for.

    The OIML analogue of applying the CIPM MRA logo outside a published CMC. Verifica is
    recognised for R 46 and only R 46; this certificate cites R 60, which is a real
    Recommendation covering something else entirely.
    """
    world = build_world()
    other = recommendation_by_id("R 60")
    assert other is not None

    credential = copy.deepcopy(world.credential("oiml-certificate"))
    payload = credential["credentialSubject"]["oimlCertificate"]
    payload["recommendation"] = other.to_json()
    payload["standard"] = other.identifier
    signed = _resign(credential, "did:web:legal-ia.example", OIML_CERTIFICATE_ISSUED)
    _republish(world, "oiml-certificate", signed)
    return TamperResult(world, signed, DEMO_NOW)


def _evaluation_rested_on_expired_calibration() -> TamperResult:
    """Evaluate a type with a multimeter whose calibration had already lapsed.

    Everything about the report is in order except the one thing that makes a type
    evaluation a measurement rather than an opinion. The laboratory is genuinely
    recognised, the signature is genuine, and the equipment it measured with was out of
    calibration on the day.

    The lapse is arranged by moving the evaluation later rather than by editing the
    calibration certificate, so nothing is forged anywhere: the calibration really did
    expire, and the evaluation really was performed after it.
    """
    world = build_world()
    credential = copy.deepcopy(world.credential("oiml-evaluation"))
    late = datetime.fromisoformat("2027-06-01T09:00:00+00:00")
    credential["validFrom"] = "2027-06-01T09:00:00Z"
    credential["credentialSubject"]["typeEvaluation"]["performedOn"] = "2027-05-28"
    signed = _resign(credential, "did:web:testlab.example", late)
    _republish(world, "oiml-evaluation", signed)
    return TamperResult(world, signed, late)


def _evaluation_by_an_unrecognised_laboratory() -> TamperResult:
    """Rest the certificate on a report from a laboratory OIML never recognised.

    The certificate is sound on its own terms -- signed by a recognised Issuing
    Authority, inside its Recommendation, digest of the report intact. What is wrong is
    one level down: the report the Issuing Authority reviewed was written by somebody
    the scheme does not recognise, and only a verifier that follows the reference finds
    out.
    """
    world = build_world()
    rogue_key = derive_key(ROGUE_DID)
    world.store.publish(ROGUE_DID, build_did_document(rogue_key), "did-document")

    report = copy.deepcopy(world.credential("oiml-evaluation"))
    report["id"] = "https://rogue.example/oiml/evaluations/RG-TE-2024-0001"
    report["issuer"] = {
        "id": ROGUE_DID,
        "type": "RecognizedIssuer",
        "name": "Definitely A Test Laboratory (demonstration)",
    }
    report.pop("credentialStatus", None)
    signed_report, _ = sign_document(report, rogue_key, created=OIML_EVALUATION_ISSUED)
    world.store.publish(signed_report["id"], signed_report, "credential")

    certificate = copy.deepcopy(world.credential("oiml-certificate"))
    payload = certificate["credentialSubject"]["oimlCertificate"]
    payload["testReport"] = {
        **credential_reference(signed_report, relation="TypeEvaluationReportCredential"),
        "issuer": ROGUE_DID,
    }
    signed = _resign(certificate, "did:web:legal-ia.example", OIML_CERTIFICATE_ISSUED)
    _republish(world, "oiml-certificate", signed)
    return TamperResult(world, signed, DEMO_NOW)


OIML_CASES: tuple[TamperCase, ...] = (
    TamperCase(
        key="wrong-recommendation",
        title="Certify a type against a Recommendation nobody approved",
        group="standing",
        description=(
            "Verifica is recognised to issue OIML certificates against R 46, active "
            "electrical energy meters. This certificate cites R 60, load cells. The "
            "signature is genuine, the Issuing Authority is genuinely recognised, and "
            "the recognition does not reach this far."
        ),
        expected_step="scope",
        catches=(
            "A Recommendation is what bounds an Issuing Authority, exactly as a "
            "published CMC bounds an institute. Recognition is never recognition to do "
            "anything at all, and a verifier that stopped at reaching OIML would accept "
            "a certificate the scheme never authorised. Two checks reject this one, and "
            "that is worth noticing rather than tidying away: the recognition names the "
            "Recommendation, and it also names a schema built from it, so the document "
            "fails validation against the very thing that bounds it. That doubling is "
            "what a machine-readable Recommendation would buy -- and the schema here is "
            "still a reading of the Recommendation rather than the Recommendation "
            "itself, which is the open item in the last chapter."
        ),
        apply=_certified_against_the_wrong_recommendation,
    ),
    TamperCase(
        key="evaluation-out-of-calibration",
        title="Evaluate a type with equipment that was out of calibration",
        group="metrological",
        description=(
            "The type evaluation was performed in May 2027 with a multimeter whose "
            "accredited calibration expired in March 2027. Nothing is forged: the "
            "laboratory is recognised, the report is signed, and the calibration it "
            "rests on really had run out on the day the measurements were made."
        ),
        expected_step="traceability",
        catches=(
            "This is what makes a type evaluation a measurement rather than an opinion. "
            "The report names the equipment it used and references that equipment's "
            "calibration by content digest, so a verifier can ask whether the "
            "traceability was live at the time -- a question no signature answers and "
            "nobody asks of a paper report."
        ),
        apply=_evaluation_rested_on_expired_calibration,
    ),
    TamperCase(
        key="unrecognised-test-laboratory",
        title="Rest the certificate on a report from an unrecognised laboratory",
        group="standing",
        description=(
            "The OIML certificate is correct in every respect: recognised issuer, right "
            "Recommendation, valid signature, intact digest of the report it reviewed. "
            "The report itself was written by a laboratory the OIML-CS does not "
            "recognise."
        ),
        expected_step="traceability",
        catches=(
            "Reviewing the test results is the Issuing Authority's defined job under the "
            "scheme, which means the certificate is only as good as the report beneath "
            "it. Referencing that report as a document rather than as a number is what "
            "lets a recipient check the level down -- and the level down is where this "
            "one is wrong."
        ),
        apply=_evaluation_by_an_unrecognised_laboratory,
    ),
)

TAMPER_CASES = TAMPER_CASES + OIML_CASES
_BY_KEY.update({case.key: case for case in OIML_CASES})


# ---------------------------------------------------------------- object identity
#
# The chain is followed by identifier and confirmed by content digest, which establishes
# which documents are in it and nothing about what they are about. This is the failure
# that hole leaves open.


def _traceability_names_another_object() -> TamperResult:
    """Claim traceability through a certificate about a different standard.

    The laboratory references the institute certificate it really was given, unaltered,
    and names as its transfer standard a different resistor -- one the institute really
    did calibrate, just not in the certificate being referenced.

    Nothing cryptographic is wrong anywhere. The reference resolves, the digest matches,
    the parent verifies on its own terms, the inherited uncertainty still reconciles and
    the input quantities still reappear, because all of those are properties of the
    documents rather than of the object. What has gone is the only thing that made the
    chain a chain: that each certificate is about the artefact the next one used.
    """
    world = build_world()
    credential = copy.deepcopy(world.credential("callab-calibration"))
    credential["credentialSubject"]["calibration"]["traceableTo"]["instrument"] = (
        "urn:instrument:callab:standard-resistor:SR10K-0091"
    )
    signed = _resign(credential, "did:web:callab.example", DEMO_NOW)
    _republish(world, "callab-calibration", signed)
    return TamperResult(world, signed, DEMO_NOW)


IDENTITY_CASES: tuple[TamperCase, ...] = (
    TamperCase(
        key="traceability-names-another-object",
        title="The chain is followed to a certificate about a different object",
        group="metrological",
        description=(
            "The laboratory claims its transfer standard was calibrated by the "
            "institute, references a genuine institute certificate, and names a "
            "different resistor as the one it used. Every signature verifies, every "
            "digest matches, and the uncertainty still reconciles line by line."
        ),
        expected_step="traceability.object-identity",
        catches=(
            "Following a chain by identifier and digest establishes which documents are "
            "in it and nothing whatever about what they concern. A certificate is a "
            "statement about an object, so a chain of certificates is only a chain of "
            "traceability if each one is about the artefact the next one used -- and "
            "that is a claim about the physical world which has to be written down "
            "before it can be checked."
        ),
        apply=_traceability_names_another_object,
    ),
)

TAMPER_CASES = TAMPER_CASES + IDENTITY_CASES
_BY_KEY.update({case.key: case for case in IDENTITY_CASES})
