"""Tests for the two things that let a credential here be checked somewhere else.

The first group is the portable copy. Its whole job is to make the signature checkable
by an implementation that cannot resolve ``did:web:metas.example``, so the tests are
about the properties that matters rests on: same key, different identifier, claims
untouched, and a signature that still verifies -- and one that stops verifying the
moment anything is altered, because a re-issue that silently blessed a modified document
would be worse than no export at all.

The second group is the UNTP projection, and it is a measurement rather than a target.
The projection is deliberately allowed to fail UNTP schema validation, so the test
cannot simply assert that it passes. What it asserts instead is the property that makes
the failure mean something: **every error the schema reports is an omission the
projection chose and recorded a reason for.** A projection that starts failing for a
reason nobody wrote down is a bug in the mapping, and the build should say so rather
than let it be read as a finding about the format.

The specific blocking omissions are pinned too. They are the result this project reports
in the harmonisation chapter, and a result nobody notices changing is not a result.
"""

from __future__ import annotations

import copy

from vcqi.actors.interop import FORMS, PROBED, export_document, untp_audit
from vcqi.actors.registry import actor_key
from vcqi.actors.scenarios import DEMO_NOW, build_world
from vcqi.vc.checks import check_proof
from vcqi.vc.portable import as_did_key, portable_copy
from vcqi.vc.resolver import DID_KEY_PREFIX, Resolver
from vcqi.vc.untp import (
    UNTP_CONTEXT,
    UNTP_DCC_TYPE,
    UNTP_VERSION,
    project,
    schema_errors,
    untp_schema,
)


class TestPortableCopy:
    """The did:key re-issue that makes the signature checkable by a stranger."""

    def test_the_identifier_changes_and_the_key_does_not(self) -> None:
        key = actor_key("did:web:metas.example")
        portable = as_did_key(key)

        assert portable.did.startswith(DID_KEY_PREFIX)
        assert portable.public_key_multibase == key.public_key_multibase
        assert portable.private_key is key.private_key
        # The method identifier has to match what did_key_document builds, or the
        # resolver will find the document and then fail to find the method inside it.
        assert portable.verification_method_id == f"{portable.did}#{portable.did[8:]}"

    def test_the_claims_are_untouched(self) -> None:
        world = build_world()
        original = world.credential("metas-calibration")
        copied, _ = portable_copy(original, actor_key(original["issuer"]["id"]), created=DEMO_NOW)

        assert copied["credentialSubject"] == original["credentialSubject"]
        assert copied["id"] == original["id"]
        assert copied["type"] == original["type"]
        # Only the identifier moves. The name and everything else on the issuer stays,
        # including recognizedIn, which now points at a chain this copy has left.
        assert copied["issuer"]["name"] == original["issuer"]["name"]
        assert copied["issuer"]["recognizedIn"] == original["issuer"]["recognizedIn"]
        assert copied["issuer"]["id"] != original["issuer"]["id"]

    def test_the_signature_verifies_with_nothing_fetched(self) -> None:
        world = build_world()
        original = world.credential("metas-calibration")
        copied, _ = portable_copy(original, actor_key(original["issuer"]["id"]), created=DEMO_NOW)

        resolver = Resolver(world.store)
        outcome, trace = check_proof(copied, resolver)

        assert outcome.passed, outcome.detail
        assert trace is not None
        # The point of did:key: the DID document was not retrieved from anywhere, it was
        # derived from the identifier. Nothing in the log says otherwise.
        assert all(record.source == "self-describing" for record in resolver.log)

    def test_altering_the_copy_breaks_it(self) -> None:
        world = build_world()
        original = world.credential("metas-calibration")
        copied, _ = portable_copy(original, actor_key(original["issuer"]["id"]), created=DEMO_NOW)

        altered = copy.deepcopy(copied)
        altered["credentialSubject"]["calibration"]["results"][0]["value"] += 1e-6
        outcome, _ = check_proof(altered, Resolver(world.store))

        assert not outcome.passed

    def test_the_wrong_key_is_refused(self) -> None:
        world = build_world()
        original = world.credential("metas-calibration")

        try:
            portable_copy(original, actor_key("did:web:callab.example"), created=DEMO_NOW)
        except ValueError as error:
            assert "callab" in str(error)
        else:  # pragma: no cover - the assertion above is the test
            raise AssertionError("a key belonging to another organisation was accepted")

    def test_exporting_twice_produces_the_same_bytes(self) -> None:
        world = build_world()
        first = export_document(world, "metas-calibration", "portable")
        second = export_document(world, "metas-calibration", "portable")

        assert first == second


class TestUntpProjection:
    """The mapping probe: what UNTP's vocabulary can carry, and what it cannot."""

    def test_the_playground_can_recognise_what_it_is(self) -> None:
        # Both halves of what the Playground keys on: the type it matches to pick a
        # schema, and a versioned test.uncefact.org context, without which its version
        # detection reports "unknown" and the schema step never runs.
        world = build_world()
        projected = project(world.credential("metas-calibration")).credential

        assert projected["type"] == UNTP_DCC_TYPE
        assert projected["@context"] == UNTP_CONTEXT
        assert any(
            "test.uncefact.org" in context and UNTP_VERSION in context
            for context in projected["@context"]
        )

    def test_the_envelope_reaches_calibration(self) -> None:
        # The part of the finding that corrected the chapter: UNTP already enumerates
        # calibration as an attestation type and already separates an international
        # arrangement from a national accreditation.
        world = build_world()
        attestation = project(world.credential("metas-calibration")).credential[
            "credentialSubject"
        ]

        assert attestation["attestationType"] == "calibration"
        assert attestation["assessmentLevel"] == "GlobalMRA"
        assert attestation["authorisation"], "the accreditation behind the body is carried"

        schema = untp_schema()["$defs"]["ConformityAttestation"]["properties"]
        assert "calibration" in schema["attestationType"]["enum"]
        assert "GlobalMRA" in schema["assessmentLevel"]["enum"]

    def test_the_measurement_does_not_arrive(self) -> None:
        world = build_world()
        source = world.credential("metas-calibration")
        projection = project(source)
        metric = projection.credential["credentialSubject"]["assessment"][0]["declaredValue"][0]

        # The value travels; nothing that qualifies it does.
        assert metric["metricValue"]["value"] == (
            source["credentialSubject"]["calibration"]["results"][0]["value"]
        )
        assert "accuracy" not in metric
        left_behind = {omission.source for omission in projection.omissions}
        assert "calibration.uncertaintyBudget" in left_behind

        # The traceability chain goes the same way, and it has to be read off a
        # certificate that has one: METAS realises the unit itself, so its certificate
        # is the top of the chain and states no link upwards to lose.
        downstream = project(world.credential("callab-calibration"))
        assert "calibration.traceableTo" in {
            omission.source for omission in downstream.omissions
        }

        # And there is nowhere any of it could have been put, which is why it was not.
        schema = untp_schema()["$defs"]
        assert schema["Metric"]["additionalProperties"] is False
        assert schema["Measure"]["additionalProperties"] is False

    def test_every_schema_error_is_a_recorded_omission(self) -> None:
        # The load-bearing assertion. The projection is allowed to fail UNTP validation,
        # but only in ways it chose and can explain.
        world = build_world()
        for name in PROBED:
            projection = project(world.credential(name))
            errors = schema_errors(projection.credential)
            assert len(errors) == len(projection.blocking), (
                f"{name}: {len(errors)} schema errors against "
                f"{len(projection.blocking)} omissions marked required -- "
                f"{[error['message'] for error in errors]}"
            )
            for omission in projection.omissions:
                assert omission.reason.strip(), f"{name}: {omission.source} has no reason"

    def test_the_result_reported_in_the_chapter_is_pinned(self) -> None:
        world = build_world()

        calibration = project(world.credential("metas-calibration"))
        assert {omission.path for omission in calibration.blocking} == {
            "assessment[0].conformance",
            "assessment[0].conformityTopic",
        }

        conformity = project(world.credential("cab-conformity"))
        assert {omission.path for omission in conformity.blocking} == {
            "assessment[0].conformityTopic",
            "assessment[0].referenceStandard.issuingParty.id",
        }
        # The case UNTP was built for still carries its conformance statement, which is
        # what makes the calibration case's missing one a finding rather than a bug.
        assert conformity.credential["credentialSubject"]["assessment"][0]["conformance"] is True

    def test_conformity_topic_is_a_sustainability_list(self) -> None:
        # Quoted in the chapter as the reason neither certificate has an honest value,
        # so it is worth failing the build if UNTP ever widens it.
        topics = untp_schema()["$defs"]["Criterion"]["properties"]["conformityTopic"]["enum"]

        assert len(topics) == 15
        assert all(
            topic.split(".")[0] in {"environment", "circularity", "social", "governance"}
            for topic in topics
        )

    def test_the_audit_agrees_with_itself(self) -> None:
        audit = untp_audit(build_world())

        assert audit["version"] == UNTP_VERSION
        assert audit["accountedFor"]
        assert [entry["name"] for entry in audit["credentials"]] == list(PROBED)
        for entry in audit["credentials"]:
            assert entry["omissions"], "a projection that cost nothing would be suspicious"


class TestExport:
    """The three forms a credential leaves the page in."""

    def test_every_form_produces_a_signed_document(self) -> None:
        world = build_world()
        for form in FORMS:
            document = export_document(world, "metas-calibration", form)
            assert "proof" in document, form
            assert document["proof"]["cryptosuite"] == "ecdsa-jcs-2019"

    def test_only_the_native_form_keeps_the_did_web_issuer(self) -> None:
        world = build_world()

        assert export_document(world, "metas-calibration", "native")["issuer"]["id"].startswith(
            "did:web:"
        )
        for form in ("portable", "untp"):
            issuer = export_document(world, "metas-calibration", form)["issuer"]["id"]
            assert issuer.startswith(DID_KEY_PREFIX), form

    def test_an_unknown_form_is_refused(self) -> None:
        world = build_world()
        try:
            export_document(world, "metas-calibration", "pdf")
        except ValueError as error:
            assert "pdf" in str(error)
        else:  # pragma: no cover - the assertion above is the test
            raise AssertionError("an unknown export form was accepted")
