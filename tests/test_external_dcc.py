"""Tests for the certificate that exists only as a document outside its credential.

Two things are being pinned. The first is ordinary: the adapted DKD example is a
well-formed PTB/DKD DCC, it is signed, and the credential's digests match the bytes that
were published.

The second is the point of the whole change set, and it is a test of what the pipeline
*cannot* do. A pointer credential duplicates almost nothing, so almost nothing can be
cross-checked, and the verdicts have to say so. If a later change quietly turns those
warnings into passes -- by parsing the document, say -- these tests should fail and be
rewritten deliberately, because the chapter's argument would have changed.
"""

from __future__ import annotations

import copy

import pytest

from vcqi.actors.registry import TRUST_ANCHORS
from vcqi.actors.scenarios import DEMO_NOW, build_world
from vcqi.crypto.keys import derive_key
from vcqi.crypto.multibase import digest_multibase, digest_sri
from vcqi.crypto.xmlc14n import parse
from vcqi.crypto.xmldsig import verify_enveloped
from vcqi.domain.external_dcc import (
    EXTERNAL_DCC_INDEX,
    external_dcc_bytes,
    external_dcc_source,
)
from vcqi.domain.dcc import DCC_SCHEMA_VERSION
from vcqi.domain.kcdb import cmc_by_id
from vcqi.vc.schema import calibration_certificate_schema
from vcqi.vc.verify import verify_credential

NAME = "metas-external-dcc"
ADDRESS = "https://metas.example/certificates/METAS-2026-0420/certificate.dcc.xml"


@pytest.fixture(scope="module")
def world():
    """Build the demonstration world once for the whole module."""
    return build_world()


@pytest.fixture(scope="module")
def credential(world):
    """The external document credential.

    Args:
        world: The demonstration world.

    Returns:
        The signed credential.
    """
    return world.credential(NAME)


def _verify(world, credential):
    """Run the real pipeline over a credential.

    Args:
        world: The demonstration world.
        credential: The credential to verify.

    Returns:
        The verification report.
    """
    return verify_credential(
        credential,
        store=world.store,
        now=DEMO_NOW,
        trusted_issuers=frozenset(TRUST_ANCHORS),
    )


def _step(report, step_id):
    """Find one step of a report by id.

    Args:
        report: The verification report.
        step_id: The step id to look for.

    Returns:
        The step, or None.
    """

    def walk(steps):
        for step in steps:
            if step.id == step_id:
                return step
            found = walk(step.children)
            if found:
                return found
        return None

    return walk(report.steps)


class TestTheDocument:
    """The adapted DKD example, as committed."""

    def test_it_is_a_well_formed_dcc_at_the_version_it_claims(self) -> None:
        """Structure and namespaces are the DKD's and were not touched."""
        root = parse(external_dcc_source()).documentElement
        assert root.tagName == "dcc:digitalCalibrationCertificate"
        assert root.getAttribute("schemaVersion") == EXTERNAL_DCC_INDEX.schema_version
        assert root.getAttribute("xmlns:dcc") == "https://ptb.de/dcc"
        assert root.getAttribute("xmlns:si") == "https://ptb.de/si"

    def test_it_is_a_version_this_repository_does_not_generate(self) -> None:
        """Which is the reason the pointer model is attractive at all.

        ``domain/dcc.py`` emits 3.3.0. This document is 3.4.0-rc.2, produced by somebody
        else's tooling, and nothing here has to reconcile the two because nothing here
        reads it.
        """
        assert EXTERNAL_DCC_INDEX.schema_version == "3.4.0-rc.2"
        assert EXTERNAL_DCC_INDEX.schema_version != DCC_SCHEMA_VERSION
        assert (
            f'schemaVersion="{EXTERNAL_DCC_INDEX.schema_version}"'
            in external_dcc_source()
        )

    def test_the_pipeline_could_not_parse_its_uncertainty_if_it_tried(self) -> None:
        """The concrete reason the index goes unchecked, asserted rather than asserted at.

        ``parse_dcc_result`` reads ``si:uncertainty``; this document states
        ``si:valueExpandedMU``. That is a real incompatibility between two versions of
        one format, not a shortcut taken to make a point.
        """
        source = external_dcc_source()
        assert "si:valueExpandedMU" in source
        assert "<si:uncertainty>" not in source

    def test_the_attribution_survived_the_adaptation(self) -> None:
        """It is somebody else's document and the file has to keep saying so."""
        source = external_dcc_source()
        assert "DKD-E 1-1" in source
        assert "10.7795/550.20260724" in source
        assert "This is NOT a real calibration certificate!" in source
        assert "ADAPTED COPY" in source

    @pytest.mark.parametrize(
        "leftover", ["DAkkS", "dakks.de", "Musterhausen", "Musterzertifikat", "D-K-xxxxxx"]
    )
    def test_no_real_or_placeholder_body_is_left_named(self, leftover: str) -> None:
        """Every organisation in this world is fictional, including in the XML."""
        assert leftover not in external_dcc_source()

    def test_the_reported_uncertainty_is_one_the_cmc_supports(self) -> None:
        """The published example states a placeholder; a placeholder here would be wrong.

        CMC CH-EM-0042 declares a floor that works out at 2.1e-4 ohm at 100 ohm, and the
        document states 2.5e-4. Nothing in the pipeline checks this -- that is the whole
        finding -- so it is checked here instead, once, rather than shipping a world with
        a certificate better than its own published capability.
        """
        cmc = cmc_by_id("CH-EM-0042")
        assert cmc is not None
        floor = cmc.uncertainty_floor.evaluate(100.001502)
        assert "<si:valueExpandedMU>0.00025</si:valueExpandedMU>" in external_dcc_source()
        assert 0.00025 >= floor


class TestItsSignature:
    """The ds:Signature the published example did not have."""

    def test_the_published_document_is_signed_and_verifies(self, world) -> None:
        """End to end, through the world's own publishing path."""
        _, published = world.artefacts[ADDRESS]
        assert verify_enveloped(published.decode("utf-8")).verified

    def test_the_committed_file_is_not_signed(self) -> None:
        """Signing happens at build time, so the file under review stays reviewable."""
        assert "ds:Signature" not in external_dcc_source()

    def test_signing_is_deterministic(self) -> None:
        """Otherwise the digest in the credential would move on every run."""
        key = derive_key("did:web:metas.example")
        assert external_dcc_bytes(key) == external_dcc_bytes(key)


class TestTheCredential:
    """What it states, and more importantly what it does not."""

    def test_it_is_its_own_credential_type(self, credential) -> None:
        """PascalCase, and specific enough for the pipeline to dispatch on."""
        assert credential["type"] == ["VerifiableCredential", "ExternalDocumentCredential"]

    def test_it_carries_no_measurement_whatsoever(self, credential) -> None:
        """The defining property. Everything else follows from it."""
        subject = credential["credentialSubject"]
        assert "calibration" not in subject
        external = subject["externalDocument"]
        for absent in ("value", "expandedUncertainty", "coverageFactor", "uncertaintyBudget"):
            assert absent not in external

    def test_the_index_is_exactly_four_facts(self, credential) -> None:
        """Enough to find and to route. Not enough to judge."""
        external = credential["credentialSubject"]["externalDocument"]
        assert external["certificateNumber"] == EXTERNAL_DCC_INDEX.certificate_number
        assert external["performedOn"] == EXTERNAL_DCC_INDEX.performed_on
        assert external["measurand"] == EXTERNAL_DCC_INDEX.measurand
        assert external["unit"] == EXTERNAL_DCC_INDEX.unit

    def test_the_integrity_goes_in_related_resource(self, credential, world) -> None:
        """The data model's own place for it, in both spellings it allows."""
        _, published = world.artefacts[ADDRESS]
        resource = credential["relatedResource"][0]
        assert resource["id"] == ADDRESS
        assert resource["digestMultibase"] == digest_multibase(published)
        assert resource["digestSRI"] == digest_sri(published)
        assert resource["digestSRI"].startswith("sha256-")

    def test_it_records_what_the_documents_own_signature_uses(self, credential) -> None:
        """So a reader sees two integrity mechanisms without opening the document."""
        signature = credential["credentialSubject"]["externalDocument"]["xmlSignature"]
        assert signature["canonicalization"] == "http://www.w3.org/2006/12/xml-c14n11"
        assert "ecdsa-sha256" in signature["algorithm"]
        assert "no certificate chain" in signature["keyDiscovery"]


class TestWhatTheVerifierCanSettle:
    """The four checks that work."""

    def test_the_credential_verifies(self, world, credential) -> None:
        """Nothing fails, which is exactly the finding the next class is about."""
        assert _verify(world, credential).outcome == "verified"

    def test_the_document_is_retrieved_and_matches_both_digests(
        self, world, credential
    ) -> None:
        """A reference that cannot be checked is a reference to nothing in particular."""
        digest = _step(_verify(world, credential), "external-document.digest")
        assert digest.status == "pass"
        assert "digestMultibase matches" in digest.detail
        assert "digestSRI matches" in digest.detail

    def test_the_documents_own_signature_is_checked_too(self, world, credential) -> None:
        """And reported as what it is: a second path that names nobody."""
        step = _step(_verify(world, credential), "external-document.xml-signature")
        assert step.status == "pass"
        assert "no certificate chain" in step.detail

    def test_measurand_and_unit_are_still_adjudicated(self, world, credential) -> None:
        """The index is not useless. It is just not sufficient."""
        assert _step(_verify(world, credential), "scope.measurand").status == "pass"
        assert _step(_verify(world, credential), "scope.unit").status == "pass"

    def test_recognition_and_action_still_work(self, world, credential) -> None:
        """A new credential type has to be authorised like any other.

        This is what ``REQUIRED_ACTIONS`` is for, and a type missing from it would skip
        the action check silently rather than failing it.
        """
        report = _verify(world, credential)
        assert _step(report, "recognition").status == "pass"
        assert _step(report, "action").status == "pass"


class TestWhatTheVerifierCannotSettle:
    """The point of the exercise. Each of these is a warning on every run, by design."""

    def test_the_index_is_never_confirmed_against_the_document(
        self, world, credential
    ) -> None:
        """Four facts stated twice, with nothing comparing them.

        The passenger form pays for its six duplicated facts by checking them. This
        form duplicates less and checks none of it, which is the trade in one sentence.
        """
        step = _step(_verify(world, credential), "external-document.index")
        assert step.status == "warn"
        assert "issuer's word" in step.detail

    def test_range_and_uncertainty_floor_go_unevaluated(self, world, credential) -> None:
        """The CMC's whole purpose, and the credential cannot reach it."""
        report = _verify(world, credential)
        assert _step(report, "scope").status == "warn"
        not_evaluated = _step(report, "scope.not-evaluated")
        assert not_evaluated.status == "warn"
        assert "does not parse" in not_evaluated.detail

    def test_uncertainty_and_traceability_do_not_run_at_all(
        self, world, credential
    ) -> None:
        """No budget to check and no chain to follow, because neither is here."""
        report = _verify(world, credential)
        assert _step(report, "uncertainty").status == "skip"
        assert _step(report, "traceability").status == "skip"

    def test_a_verified_verdict_here_carries_two_warnings(
        self, world, credential
    ) -> None:
        """Stated as a test because it is the sentence the chapter rests on.

        The pipeline reports ``verified`` -- nothing failed -- while two of its steps say
        the measurement was never examined. That is not a defect to fix by silencing
        them; it is what choosing the pointer model costs, and it should stay visible.
        """
        report = _verify(world, credential)
        warnings = [step.id for step in report.steps if step.status == "warn"]
        assert report.outcome == "verified"
        assert sorted(warnings) == ["external-document", "scope"]

    def test_every_other_certificate_still_decides_everything(self, world) -> None:
        """The contrast, so the claim above is about this credential and not the suite."""
        report = _verify(world, world.credential("metas-calibration"))
        assert [step.id for step in report.steps if step.status == "warn"] == []
        assert _step(report, "scope").status == "pass"
        assert _step(report, "uncertainty").status == "pass"


class TestSubstitutingTheDocument:
    """What the digest is actually for."""

    def test_swapping_the_published_document_is_caught(self, world, credential) -> None:
        """Every signature stays valid and the credential still points at the address.

        This is the attack the pointer model has to survive, because the document is the
        whole content: without the digest, an issuer or a host could replace the
        certificate after issue and nothing would notice.
        """
        altered = copy.deepcopy(world)
        _, published = world.artefacts[ADDRESS]
        swapped = published.replace(b"100.001502", b"100.001999")
        assert swapped != published
        altered.publish_artefacts({ADDRESS: ("application/xml", swapped)})

        report = _verify(altered, credential)
        assert report.outcome == "rejected"
        assert _step(report, "external-document.digest").status == "fail"
        # And the credential's own proof is untouched, which is what makes the failure
        # informative rather than confusing: the credential is fine, the document is not.
        assert _step(report, "proof").status == "pass"


class TestTheSchemaAcceptsEitherCarrier:
    """One authorisation, two shapes."""

    @pytest.fixture(scope="class")
    @classmethod
    def schema(cls):
        """The generated schema for the CMC both carriers are issued under.

        Returns:
            The JSON Schema document.
        """
        cmc = cmc_by_id("CH-EM-0042")
        assert cmc is not None
        return calibration_certificate_schema(
            cmc.as_capability(), schema_id="urn:test", title="test"
        )

    def test_it_offers_one_branch_per_carrier(self, schema) -> None:
        """Named by what they require, not by position."""
        assert len(schema["anyOf"]) == 2
        required = [sorted(branch["required"]) for branch in schema["anyOf"]]
        assert ["credentialSubject", "type"] in required
        assert ["credentialSubject", "relatedResource", "type"] in required

    def test_both_real_credentials_validate(self, world, schema) -> None:
        """Which is the reason the branch was added rather than the check relaxed."""
        from jsonschema import Draft202012Validator  # noqa: PLC0415 - test-only import

        validator = Draft202012Validator(schema)
        validator.validate(world.credential("metas-calibration"))
        validator.validate(world.credential(NAME))

    def test_a_pointer_without_a_digest_is_refused(self, world, schema) -> None:
        """A reference with no digest is a reference to whatever is there today."""
        from jsonschema import Draft202012Validator  # noqa: PLC0415 - test-only import

        broken = copy.deepcopy(world.credential(NAME))
        del broken["relatedResource"][0]["digestMultibase"]
        assert not Draft202012Validator(schema).is_valid(broken)

    def test_a_pointer_to_another_measurand_is_refused(self, world, schema) -> None:
        """The index is thin, and what there is of it is still checked."""
        from jsonschema import Draft202012Validator  # noqa: PLC0415 - test-only import

        broken = copy.deepcopy(world.credential(NAME))
        broken["credentialSubject"]["externalDocument"]["measurand"] = "dc.voltage"
        assert not Draft202012Validator(schema).is_valid(broken)
