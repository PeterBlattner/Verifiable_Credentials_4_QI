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
the failure mean something: **every error the schema reports is a finding the projection
recorded, at the same member, with a reason.** Matched member by member rather than
counted, so that filling a member recorded as missing is caught. The faults the 0.6.0
Playground run turned up -- a scope document named as its own authority, a status entry
dropped without a word, one identifier for three things, a value with seventeen digits
and no uncertainty -- each have a test of their own, so they cannot come back quietly.

The specific blocking findings are pinned too. They are the result this project reports
in the harmonisation chapter, and a result nobody notices changing is not a result.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from vcqi.actors.interop import FORMS, PROBED, export_document, untp_audit
from vcqi.actors.registry import actor_key
from vcqi.actors.scenarios import DEMO_NOW, World, build_world
from vcqi.vc.checks import check_proof
from vcqi.vc.jsonld_terms import term_problems
from vcqi.vc.portable import as_did_key, portable_copy
from vcqi.vc.resolver import DID_KEY_PREFIX, Resolver
from vcqi.vc.untp import (
    CONFLICT,
    CONTEXT_PATHS,
    DROPPED,
    JUDGEMENT,
    REQUIRED,
    SCHEMA_PATHS,
    UNTP_CONTEXT,
    UNTP_DCC_TYPE,
    UNTP_DIA_TYPE,
    UNTP_VERSION,
    VENDORED_CONTENT_SHA256,
    Finding,
    Projection,
    content_sha256,
    project,
    schema_errors,
    untp_schema,
    vendored_contexts,
)

#: Every projection checked, as the credential and, for a recognition, the entity it
#: anchors: the four the probe shows, the accredited laboratory's calibration, which is
#: the one with a traceability chain to lose, and PTB, the second entity of the BIPM's
#: recognition.
PROJECTED = (
    *PROBED,
    ("callab-calibration", None),
    ("bipm-recognition", "did:web:ptb.example"),
)

#: The certificates among them, whose projection is a Digital Conformity Credential.
CERTIFICATES = tuple(item for item in PROJECTED if item[1] is None)

#: Where the one assessment sits in a projected document, as a finding path.
ASSESSMENT = "credentialSubject/conformityAssessment/0"


def _projection(
    name: str, subject: str | None = None, *, lookup: bool = True
) -> tuple[World, dict[str, Any], Projection]:
    """Project one credential of a freshly built world.

    Args:
        name: Short name of the credential.
        subject: For a recognition, the DID of the entity to anchor.
        lookup: Whether the projection may read the documents the credential points at.

    Returns:
        The world, the source credential and the projection.
    """
    world = build_world()
    source = world.credential(name)
    return world, source, project(source, world.store.get if lookup else None, subject)


def _assessment(projection: Projection) -> dict[str, Any]:
    """Return the one ConformityAssessment of a projection.

    Args:
        projection: A projection.

    Returns:
        The assessment.
    """
    return projection.credential["credentialSubject"]["conformityAssessment"][0]


def _objects(value: Any) -> list[dict[str, Any]]:
    """List every JSON object in a document, depth first.

    Args:
        value: A document or part of one.

    Returns:
        Each object found.
    """
    if isinstance(value, dict):
        return [value, *(item for child in value.values() for item in _objects(child))]
    if isinstance(value, list):
        return [item for child in value for item in _objects(child)]
    return []


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
        # Both halves of what the Playground keys on: the type, without which it refuses
        # the upload outright and which it then matches to pick a schema, and a versioned
        # UNTP context, without which its version detection reports "unknown". The
        # schema fixes the context array exactly, so it is read from there.
        _, _, projection = _projection("metas-calibration")
        projected = projection.credential
        prefix = untp_schema()["properties"]["@context"]["prefixItems"]

        assert projected["type"] == UNTP_DCC_TYPE
        assert projected["@context"] == UNTP_CONTEXT == [item["const"] for item in prefix]
        assert any(
            "vocabulary.uncefact.org" in context and UNTP_VERSION in context
            for context in projected["@context"]
        )

    def test_the_vendored_artefacts_are_the_published_ones(self) -> None:
        # Hashed the way the Playground's artefact manifest hashes them, so a mismatch
        # means a different document rather than different line endings.
        for path in (*SCHEMA_PATHS.values(), *CONTEXT_PATHS.values()):
            document = json.loads(path.read_text(encoding="utf-8"))
            assert content_sha256(document) == VENDORED_CONTENT_SHA256[path.name], path.name

    def test_the_envelope_reaches_calibration(self) -> None:
        _, _, projection = _projection("metas-calibration")
        attestation = projection.credential["credentialSubject"]
        assessment = _assessment(projection)
        schema = untp_schema()["$defs"]
        types = schema["ConformityAttestation"]["properties"]["attestationType"]["enum"]

        assert attestation["attestationType"] == "calibration"
        assert "calibration" in types
        # No verdict is forced on a calibration: conformance is optional, and left out.
        assert "conformance" not in schema["ConformityAssessment"]["required"]
        assert "conformance" not in assessment
        assert assessment["conformityTopic"][0]["id"].endswith("/metrology-and-measurement")
        assert assessment["specifiedCondition"]

    def test_the_cipm_mra_has_no_code_and_the_choice_is_recorded(self) -> None:
        # What the chapter withdrew: UNTP does not distinguish the CIPM MRA from
        # accreditation. authority-peer is the nearest, and it is a judgement.
        _, _, projection = _projection("metas-calibration")
        levels = untp_schema()["$defs"]["ConformityAttestation"]["properties"][
            "assessmentLevel"
        ]["enum"]
        attestation = projection.credential["credentialSubject"]

        assert attestation["assessmentLevel"] == "authority-peer"
        assert "authority-peer" in levels and "authority-globalmra" in levels
        assert not any("cipm" in level.lower() for level in levels)
        assert any(
            finding.kind == JUDGEMENT and finding.path == "credentialSubject/assessmentLevel"
            for finding in projection.findings
        )

    def test_the_measurement_does_not_arrive(self) -> None:
        world, source, projection = _projection("metas-calibration")
        result = source["credentialSubject"]["calibration"]["results"][0]
        measure = _assessment(projection)["assessedPerformance"][0]["measure"]

        # The value travels, rounded as the certificate reports it; nothing that
        # qualifies it does.
        assert measure == {"value": 10000.0012, "unit": "OHM"}
        assert measure["value"] == float(result["reported"].split()[0])
        dropped = {finding.source for finding in projection.findings if finding.kind == DROPPED}
        assert "calibration.results[0].expandedUncertainty" in dropped
        assert "calibration.uncertaintyBudget" in dropped

        # The traceability chain goes the same way, and it has to be read off a
        # certificate that has one: METAS realises the unit itself, so its certificate
        # is the top of the chain and states no link upwards to lose.
        downstream = project(world.credential("callab-calibration"), world.store.get)
        assert "calibration.traceableTo" in {finding.source for finding in downstream.findings}

        # And there is nowhere any of it could have been put, which is why it was not.
        schema = untp_schema()["$defs"]["Measure"]
        assert schema["additionalProperties"] is False
        assert set(schema["properties"]) == {"value", "unit", "upperTolerance", "lowerTolerance"}

    def test_every_schema_error_is_a_recorded_blocking_finding(self) -> None:
        # The load-bearing assertion. The projection is allowed to fail UNTP validation,
        # but only in ways it chose and can explain, at the member it recorded.
        for name, subject in PROJECTED:
            _, _, projection = _projection(name, subject)
            errors = schema_errors(projection.credential)
            assert {error["member"] for error in errors} == {
                finding.path for finding in projection.blocking
            }, f"{name}: {[error['message'] for error in errors]}"
            for finding in projection.findings:
                assert finding.reason.strip(), f"{name}: {finding.source} has no reason"

    def test_a_plausible_fill_is_caught(self) -> None:
        # Fill a member recorded as missing and the error disappears while the finding
        # stays, so the two no longer match -- where a count of errors would not notice a
        # fill that happened to coincide with a new gap.
        _, _, projection = _projection("metas-calibration")
        filled = copy.deepcopy(projection.credential)
        filled["credentialSubject"]["referenceScheme"] = {
            "id": "https://bipm.example/cipm-mra",
            "name": "CIPM MRA",
        }

        assert {error["member"] for error in schema_errors(filled)} != {
            finding.path for finding in projection.blocking
        }

    def test_the_result_reported_in_the_chapter_is_pinned(self) -> None:
        _, _, calibration = _projection("metas-calibration")
        assert {(finding.kind, finding.path) for finding in calibration.blocking} == {
            (CONFLICT, "credentialStatus/statusListIndex"),
            (REQUIRED, "credentialSubject/referenceScheme"),
            (REQUIRED, f"{ASSESSMENT}/assessedPerformance/0/metric/id"),
        }

        _, _, conformity = _projection("cab-conformity")
        assert {(finding.kind, finding.path) for finding in conformity.blocking} == {
            (CONFLICT, "credentialStatus/statusListIndex"),
            (REQUIRED, "credentialSubject/referenceScheme"),
            (REQUIRED, f"{ASSESSMENT}/assessmentCriteria/0/id"),
            (REQUIRED, f"{ASSESSMENT}/assessedPerformance"),
        }
        # The case UNTP was built for still carries its verdict, which is what makes the
        # calibration's absent one a statement about calibration rather than a gap.
        assert _assessment(conformity)["conformance"] is True

    def test_the_status_is_carried_as_the_source_states_it(self) -> None:
        # The 0.6.0 projection dropped it without a word. It travels now, as W3C writes
        # it, and UNTP's schema contradicts its own description of the member.
        _, source, projection = _projection("metas-calibration")
        status = projection.credential["credentialStatus"]
        member = untp_schema()["$defs"]["BitstringStatusListEntry"]["properties"][
            "statusListIndex"
        ]

        assert status == source["credentialStatus"]
        assert isinstance(status["statusListIndex"], str)
        assert member["type"] == "integer"
        assert "string in base 10" in member["description"]

    def test_no_identifier_names_two_things(self) -> None:
        # The 0.6.0 projection gave the credential, the attestation and the assessment one
        # identifier, and the scheme, its issuer, the endorsement and its authority
        # another. Read as linked data, each of those groups is one node.
        for name, subject in PROJECTED:
            _, _, projection = _projection(name, subject)
            # One identifier, one name. The type may differ, because the same party can
            # appear in two roles -- the BIPM as an anchor's issuer and as its registrar.
            seen: dict[str, set[Any]] = {}
            for node in _objects(projection.credential):
                if isinstance(node.get("id"), str) and "name" in node:
                    seen.setdefault(node["id"], set()).add(node["name"])
            shared = [identifier for identifier, named in seen.items() if len(named) > 1]
            assert not shared, f"{name}: {shared}"
            if subject is not None:
                continue

            credential = projection.credential
            identifiers = {
                credential["id"],
                credential["credentialSubject"]["id"],
                _assessment(projection)["id"],
            }
            assert len(identifiers) == 3, name

    def test_an_authority_is_the_issuer_of_its_evidence(self) -> None:
        # Never the evidence itself, which is what the 0.6.0 projection wrote.
        expected = {
            "metas-calibration": {"did:web:bipm.example"},
            "cab-conformity": {"did:web:sas.example"},
        }
        for name, authorities in expected.items():
            world, _, projection = _projection(name)
            endorsements = projection.credential["credentialSubject"]["authorisation"]
            for endorsement in endorsements:
                url = endorsement["endorsementEvidence"]["linkURL"]
                authority = endorsement["issuingAuthority"]["id"]
                assert authority == world.store.get(url)["issuer"]["id"]
                assert authority != url
            assert {item["issuingAuthority"]["id"] for item in endorsements} == authorities

    def test_without_lookup_the_authority_is_recorded_not_invented(self) -> None:
        _, _, projection = _projection("metas-calibration", lookup=False)
        _, _, with_lookup = _projection("metas-calibration")

        assert "authorisation" not in projection.credential["credentialSubject"]
        assert any(
            finding.kind == DROPPED and finding.path == "credentialSubject/authorisation"
            for finding in projection.findings
        )
        assert {finding.path for finding in projection.blocking} == {
            finding.path for finding in with_lookup.blocking
        }

    def test_value_objects_carry_no_type_and_class_nodes_do(self) -> None:
        # The 0.7.0 context defines a class's members inside the class's own type, so a
        # class node without its type has them dropped; and it defines no type for the
        # value objects, so one with a type fails expansion. Both directions matter.
        for name, _ in CERTIFICATES:
            _, _, projection = _projection(name)
            credential = projection.credential
            attestation = credential["credentialSubject"]
            assessment = _assessment(projection)
            endorsements = attestation.get("authorisation", [])
            performances = assessment.get("assessedPerformance", [])
            classes = [
                credential["issuer"],
                attestation,
                attestation["issuedToParty"],
                assessment,
                assessment["assessedProduct"][0]["product"],
                *assessment["assessmentCriteria"],
                *assessment["conformityTopic"],
                *(item["issuingAuthority"] for item in endorsements),
                *(item["metric"] for item in performances),
            ]
            values = [
                assessment["assessedProduct"][0],
                *endorsements,
                *(item["endorsementEvidence"] for item in endorsements),
                *performances,
                *(item["measure"] for item in performances),
                *assessment.get("evidence", []),
            ]
            assert all("type" in node for node in classes), name
            assert all("type" not in node for node in values), name

    def test_an_unknown_finding_kind_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown finding kind"):
            Finding("omitted", "name", "name", "a kind the interface cannot show")

    def test_the_audit_agrees_with_itself(self) -> None:
        audit = untp_audit(build_world())

        assert audit["version"] == UNTP_VERSION
        assert audit["accountedFor"]
        assert audit["expands"]
        probed = [(entry["name"], entry["subject"]) for entry in audit["credentials"]]
        assert probed == list(PROBED)
        for entry in audit["credentials"]:
            assert entry["findings"], "a projection that cost nothing would be suspicious"
            assert entry["accounted"]


class TestIdentityAnchor:
    """The recognitions as UNTP Digital Identity Anchors, one per recognised entity."""

    def test_one_anchor_per_recognised_entity(self) -> None:
        # A recognition lists several entities and an anchor names one, so each entity
        # gets its own anchor, with an identifier of its own.
        world = build_world()
        source = world.credential("bipm-recognition")
        anchors = {
            entity["id"]: project(source, world.store.get, entity["id"]).credential
            for entity in source["credentialSubject"]
        }

        assert set(anchors) == {"did:web:metas.example", "did:web:ptb.example"}
        assert len({anchor["id"] for anchor in anchors.values()}) == 2
        for subject, anchor in anchors.items():
            assert anchor["type"] == UNTP_DIA_TYPE
            assert anchor["@context"] == UNTP_CONTEXT
            assert anchor["credentialSubject"]["id"] == subject
            assert anchor["credentialSubject"]["type"] == ["RegisteredIdentity"]

    def test_a_recognition_needs_an_entity_named(self) -> None:
        world = build_world()
        source = world.credential("bipm-recognition")

        with pytest.raises(ValueError, match="recognised entities"):
            project(source, world.store.get)
        with pytest.raises(ValueError, match="recognised entities"):
            project(source, world.store.get, "did:web:cab.example")

    def test_the_anchors_reported_in_the_chapter_are_pinned(self) -> None:
        subject = "credentialSubject"
        _, _, metas = _projection("bipm-recognition", "did:web:metas.example")
        assert {(finding.kind, finding.path) for finding in metas.blocking} == {
            (CONFLICT, "credentialStatus/statusListIndex"),
            (REQUIRED, f"{subject}/registeredId"),
            (REQUIRED, f"{subject}/registeredDate"),
            (REQUIRED, f"{subject}/registerType"),
        }

        _, _, cab = _projection("sas-recognition", "did:web:cab.example")
        assert {(finding.kind, finding.path) for finding in cab.blocking} == {
            (CONFLICT, "credentialStatus/statusListIndex"),
            (REQUIRED, f"{subject}/registeredId"),
            (REQUIRED, f"{subject}/registeredDate"),
        }
        # Validated against the anchor's own schema, not the conformity credential's.
        members = {error["member"] for error in schema_errors(cab.credential)}
        assert f"{subject}/registeredId" in members
        assert "credentialSubject/conformityAssessment" not in " ".join(members)

    def test_the_registrar_is_the_issuer_and_the_scopes_are_the_capabilities(self) -> None:
        for name, subject in (
            ("bipm-recognition", "did:web:metas.example"),
            ("sas-recognition", "did:web:cab.example"),
        ):
            _, source, projection = _projection(name, subject)
            registered = projection.credential["credentialSubject"]
            entity = next(
                item for item in source["credentialSubject"] if item["id"] == subject
            )

            assert registered["registrar"]["id"] == source["issuer"]["id"]
            assert registered["registeredName"] == entity["legalName"]
            assert registered["registrationScope"] == [
                action["capabilityReference"]["id"] for action in entity["recognizedTo"]
            ]
            same_as = entity.get("sameAs") or [None]
            assert registered.get("publicInformation") == same_as[0]

    def test_the_register_type_is_a_judgement_only_for_accreditation_scopes(self) -> None:
        # The CAB is recognised within accreditation scopes, which is what UNTP's code
        # names. The CIPM MRA and the Global ACI MRA are peer recognition, and no code fits.
        for name, subject, expected in (
            ("sas-recognition", "did:web:cab.example", "accreditation"),
            ("bipm-recognition", "did:web:metas.example", None),
            ("global-aci-recognition", "did:web:sas.example", None),
        ):
            _, _, projection = _projection(name, subject)
            kinds = {
                finding.kind
                for finding in projection.findings
                if finding.path == "credentialSubject/registerType"
            }
            registered = projection.credential["credentialSubject"]
            assert registered.get("registerType") == expected
            assert kinds == ({JUDGEMENT} if expected else {REQUIRED}), name

    def test_what_a_verifier_acts_on_is_recorded_as_dropped(self) -> None:
        _, _, projection = _projection("bipm-recognition", "did:web:metas.example")
        dropped = {item.source for item in projection.findings if item.kind == DROPPED}

        assert {
            "recognizedTo[].action",
            "recognizedTo[].outputValidation",
            "recognizedTo[].validFrom",
        } <= dropped


class TestTermExpansion:
    """The offline stand-in for the Playground's JSON-LD step, and proof that it can fail."""

    def test_every_term_expands(self) -> None:
        for name, subject in PROJECTED:
            _, _, projection = _projection(name, subject)
            problems = term_problems(projection.credential, vendored_contexts())
            assert problems == [], f"{name}: {[problem.to_json() for problem in problems]}"

    def test_a_type_the_context_does_not_define_is_caught(self) -> None:
        # The 0.6.0 failure, reproduced: a default type on a value object, where the
        # parent's type-scoped context has already reverted.
        _, _, projection = _projection("metas-calibration")
        broken = copy.deepcopy(projection.credential)
        performance = broken["credentialSubject"]["conformityAssessment"][0][
            "assessedPerformance"
        ][0]
        performance["measure"]["type"] = ["Measure"]

        problems = term_problems(broken, vendored_contexts())

        assert [(item.kind, item.problem, item.term) for item in problems] == [
            ("type", "undefined", "Measure")
        ]

    def test_a_misspelt_property_is_caught(self) -> None:
        # Stricter than the Playground, whose safe mode expands this through the
        # assessment's @vocab and says nothing.
        _, _, projection = _projection("metas-calibration")
        broken = copy.deepcopy(projection.credential)
        assessment = broken["credentialSubject"]["conformityAssessment"][0]
        assessment["assesmentDate"] = assessment.pop("assessmentDate")

        problems = term_problems(broken, vendored_contexts())

        assert [(item.kind, item.problem, item.term) for item in problems] == [
            ("property", "vocab-only", "assesmentDate")
        ]

    def test_an_untyped_class_node_loses_its_members(self) -> None:
        _, _, projection = _projection("metas-calibration")
        broken = copy.deepcopy(projection.credential)
        verification = broken["credentialSubject"]["conformityAssessment"][0][
            "assessedProduct"
        ][0]
        del verification["product"]["type"]

        problems = term_problems(broken, vendored_contexts())

        assert {item.term for item in problems} == {"modelNumber", "itemNumber"}
        assert all(item.problem == "undefined" for item in problems)


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

    def test_exporting_the_untp_form_twice_produces_the_same_bytes(self) -> None:
        world = build_world()
        first = export_document(world, "cab-conformity", "untp")
        second = export_document(world, "cab-conformity", "untp")

        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    def test_a_recognition_exports_one_anchor_per_entity(self) -> None:
        world = build_world()
        first = export_document(
            world, "sas-recognition", "untp", subject="did:web:cab.example"
        )
        again = export_document(
            world, "sas-recognition", "untp", subject="did:web:cab.example"
        )

        assert first["type"] == UNTP_DIA_TYPE
        assert first["issuer"]["id"].startswith(DID_KEY_PREFIX)
        assert first["credentialSubject"]["id"] == "did:web:cab.example"
        assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
        with pytest.raises(ValueError):
            export_document(world, "sas-recognition", "untp")

    def test_an_unknown_form_is_refused(self) -> None:
        world = build_world()
        try:
            export_document(world, "metas-calibration", "pdf")
        except ValueError as error:
            assert "pdf" in str(error)
        else:  # pragma: no cover - the assertion above is the test
            raise AssertionError("an unknown export form was accepted")
