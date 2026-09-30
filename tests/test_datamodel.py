"""Tests for the data model of each credential type, and the check that uses it.

Three things are held here.

The first is that the data models describe what this world actually issues. Every
credential validates against its type's model, and -- the part a plain validation cannot
say, because the models are deliberately open -- carries no member the model leaves out.
Without the second half, a member added to a builder in ``vc/model.py`` would appear on
every certificate and in no box in the issuing chapter, and nothing would notice.

The second is that the models are what the credentials say they are: self-contained, so
that the digest in ``credentialSchema`` covers everything a validator will read, and
published where the credentials point.

The third is the verifier's check, ``shape.data-model``, and above all the ways it has
to fail: a model changed at its address, a model the credential chose for itself, and a
credential that does not have the shape its type declares.
"""

from __future__ import annotations

import copy
import socket
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing.exceptions import Unresolvable

from vcqi.actors.registry import TRUST_ANCHORS
from vcqi.actors.scenarios import DEMO_NOW, build_world
from vcqi.actors.tamper import tamper_by_key
from vcqi.crypto.jcs import canonicalize
from vcqi.crypto.multibase import digest_multibase
from vcqi.vc.datamodel import (
    DATA_MODEL_URLS,
    JSON_SCHEMA_DIALECT,
    data_model,
    data_model_reference,
    validator_for,
)
from vcqi.vc.verify import verify_credential

#: The documents the issuing chapter offers, which are every credential except the
#: status lists.
EXAMPLES = (
    "bipm-recognition",
    "global-aci-recognition",
    "sas-recognition",
    "scope-SCS-0123",
    "scope-STS-0456",
    "scope-SCESp-0789",
    "metas-calibration",
    "callab-calibration",
    "metas-SR10K-0091",
    "metas-SR10K-0092",
    "metas-external-dcc",
    "testlab-report",
    "cab-conformity",
    "oiml-ia-recognition",
    "oiml-tl-recognition",
    "oiml-evaluation",
    "oiml-certificate",
)


@pytest.fixture(scope="module")
def world():
    """Build the demonstration world once for the module."""
    return build_world()


def _type_of(credential: dict[str, Any]) -> str:
    """Return the type that is not VerifiableCredential."""
    return next(name for name in credential["type"] if name != "VerifiableCredential")


def _carried(value: Any, path: str = "") -> set[str]:
    """Return every member path a document carries, arrays written as ``[]``.

    Args:
        value: The document, or any part of it.
        path: The path to ``value``.

    Returns:
        Paths such as ``.credentialSubject.calibration.results[].value``.
    """
    found: set[str] = set()
    if isinstance(value, dict):
        for name, item in value.items():
            found.add(f"{path}.{name}")
            found |= _carried(item, f"{path}.{name}")
    elif isinstance(value, list):
        for item in value:
            found |= _carried(item, f"{path}[]")
    return found


#: Keywords the walker below knows how to follow, or knows it may ignore because they
#: constrain values rather than declare members. Anything else fails the walk rather
#: than being skipped, because a keyword that declares members in a way the walker does
#: not follow -- ``patternProperties``, say -- would make every path under it look
#: undeclared, or worse, make an undeclared one look declared.
_UNDERSTOOD = {
    "$schema", "$id", "$ref", "$defs", "title", "description", "type", "required",
    "properties", "items", "prefixItems", "contains", "minItems", "anyOf", "oneOf",
    "allOf", "const", "enum", "format", "pattern",
}


def _declared(schema: dict[str, Any], root: dict[str, Any], path: str = "") -> set[str]:
    """Return every member path a data model declares.

    Follows ``properties``, ``items`` and ``prefixItems``, local ``$ref`` and the three
    combinators. The union across the branches of an ``anyOf`` or ``oneOf`` is taken,
    so this checks names, not which branch a document chose; ordinary validation checks
    the rest.

    Args:
        schema: The part of the model being walked.
        root: The whole model, for resolving ``#/$defs/...``.
        path: The path this part describes.

    Returns:
        The declared paths, in the form ``_carried`` produces.
    """
    unknown = set(schema) - _UNDERSTOOD
    assert not unknown, f"{root['$id']} {path or 'root'}: {sorted(unknown)} not understood"
    found: set[str] = set()
    reference = schema.get("$ref")
    if reference is not None:
        assert reference.startswith("#/$defs/"), f"{root['$id']}: remote $ref {reference}"
        found |= _declared(root["$defs"][reference.removeprefix("#/$defs/")], root, path)
    for keyword in ("allOf", "anyOf", "oneOf"):
        for branch in schema.get(keyword, []):
            found |= _declared(branch, root, path)
    for name, part in schema.get("properties", {}).items():
        found.add(f"{path}.{name}")
        found |= _declared(part, root, f"{path}.{name}")
    items = schema.get("items")
    if isinstance(items, dict):
        found |= _declared(items, root, f"{path}[]")
    for part in schema.get("prefixItems", []):
        found |= _declared(part, root, f"{path}[]")
    return found


def _local_references(schema: Any) -> set[str]:
    """Return every ``$ref`` anywhere in a schema."""
    found: set[str] = set()
    if isinstance(schema, dict):
        if isinstance(schema.get("$ref"), str):
            found.add(schema["$ref"])
        for value in schema.values():
            found |= _local_references(value)
    elif isinstance(schema, list):
        for value in schema:
            found |= _local_references(value)
    return found


def _verify(world, credential: dict[str, Any]):
    """Verify a credential against a world, trusting the three roots."""
    return verify_credential(
        credential, store=world.store, now=DEMO_NOW, trusted_issuers=TRUST_ANCHORS
    )


def _data_model_step(report):
    """Return the ``shape.data-model`` step of a report."""
    shape = report.steps[0]
    assert shape.id == "shape"
    return next(step for step in shape.children if step.id == "shape.data-model")


class TestTheModelsDescribeWhatIsIssued:
    """Every credential fits its model, and the model leaves none of it out."""

    def test_every_type_offered_has_a_model_and_every_model_a_type(self, world) -> None:
        """No type without a data model, and no data model nobody issues."""
        served = {
            _type_of(credential)
            for name, credential in world.credentials.items()
            if not name.startswith("status-")
        }
        assert served == set(DATA_MODEL_URLS)

    def test_the_examples_are_every_credential_but_the_status_lists(self, world) -> None:
        """The list above is the one the issuing chapter offers, held to the world."""
        assert set(EXAMPLES) == {
            name for name in world.credentials if not name.startswith("status-")
        }

    @pytest.mark.parametrize("name", EXAMPLES)
    def test_the_credential_validates_signed_and_unsigned(self, world, name) -> None:
        """Signed, as verified; unsigned, as the issuing chapter first shows it."""
        credential = world.credential(name)
        schema = data_model(_type_of(credential))
        unsigned = {key: value for key, value in credential.items() if key != "proof"}
        for document in (credential, unsigned):
            found = validator_for(schema).iter_errors(document)
            errors = [error.message for error in found]
            assert errors == [], f"{name}: {errors[:3]}"

    @pytest.mark.parametrize("name", EXAMPLES)
    def test_no_member_goes_undeclared(self, world, name) -> None:
        """What a credential carries, its model names -- so the box leaves nothing out."""
        credential = world.credential(name)
        schema = data_model(_type_of(credential))
        undeclared = _carried(credential) - _declared(schema, schema)
        assert undeclared == set(), f"{name} carries undeclared: {sorted(undeclared)}"

    def test_the_undeclared_check_is_not_vacuous(self, world) -> None:
        """An invented member is named, and a missing required one fails validation."""
        credential = copy.deepcopy(world.credential("metas-calibration"))
        schema = data_model("CalibrationCertificateCredential")
        credential["credentialSubject"]["calibration"]["surprise"] = True
        undeclared = _carried(credential) - _declared(schema, schema)
        assert undeclared == {".credentialSubject.calibration.surprise"}

        del credential["credentialSubject"]["calibration"]["results"]
        errors = validator_for(schema).iter_errors(credential)
        paths = [list(error.absolute_path) for error in errors]
        assert ["credentialSubject", "calibration"] in paths

    def test_a_recognition_may_name_several_output_schemas(self, world) -> None:
        """The specification's "one or more": a list is as well-formed as one reference."""
        credential = copy.deepcopy(world.credential("bipm-recognition"))
        action = credential["credentialSubject"][0]["recognizedTo"][0]
        action["outputValidation"] = [action["outputValidation"]] * 2
        schema = data_model("RecognizedEntityCredential")
        assert [error.message for error in validator_for(schema).iter_errors(credential)] == []

        # And the list has to name something, or it is a claim of bounds with none in it.
        action["outputValidation"] = []
        assert list(validator_for(schema).iter_errors(credential))

    @pytest.mark.parametrize("name", EXAMPLES)
    def test_the_credential_names_its_type_s_model(self, world, name) -> None:
        """The reference is exactly the one published for the type, digests included."""
        credential = world.credential(name)
        assert credential["credentialSchema"] == data_model_reference(_type_of(credential))

    def test_the_status_lists_name_no_model(self, world) -> None:
        """A status list is defined by its own specification, not by this project."""
        for name, credential in world.credentials.items():
            if name.startswith("status-"):
                assert "credentialSchema" not in credential, name


class TestTheModelsAreWhatTheReferencesSay:
    """Published where credentials point, whole, and never an outputValidation schema."""

    @pytest.mark.parametrize("type_name", list(DATA_MODEL_URLS))
    def test_the_model_is_a_valid_schema_published_at_its_id(self, world, type_name) -> None:
        """Draft 2020-12, ``$id`` as the address, published with its own kind."""
        url = DATA_MODEL_URLS[type_name]
        schema = world.store.get(url)
        assert schema == data_model(type_name)
        assert schema["$schema"] == JSON_SCHEMA_DIALECT
        assert schema["$id"] == url
        assert world.store.kind_of(url) == "data-model"
        Draft202012Validator.check_schema(schema)

    @pytest.mark.parametrize("type_name", list(DATA_MODEL_URLS))
    def test_every_reference_stays_inside_the_document(self, type_name) -> None:
        """So that the digest in the credential covers everything a validator reads."""
        schema = data_model(type_name)
        for reference in _local_references(schema):
            assert reference.startswith("#/$defs/"), reference
            assert reference.removeprefix("#/$defs/") in schema["$defs"], reference

    def test_no_model_carries_a_definition_it_does_not_use(self) -> None:
        """Each box shows what its type uses, and nothing it does not."""
        for type_name in DATA_MODEL_URLS:
            schema = data_model(type_name)
            references = _local_references(schema)
            used = {reference.removeprefix("#/$defs/") for reference in references}
            assert set(schema["$defs"]) == used, type_name

    def test_a_data_model_is_not_a_permission(self, world) -> None:
        """The two kinds of schema never share an address, and neither names the other."""
        assert not set(world.schemas) & set(world.data_models)
        assert set(world.data_models) == set(DATA_MODEL_URLS.values())

    def test_a_changed_model_changes_the_reference(self) -> None:
        """The digest moves with a single constraint, which is what makes it a pin."""
        schema = data_model("TestReportCredential")
        schema["description"] = "Something else."
        assert digest_multibase(canonicalize(schema)) != data_model_reference(
            "TestReportCredential"
        )["digestMultibase"]

    def test_a_model_is_a_fresh_document_every_time(self) -> None:
        """So a caller changing one -- the failure case does -- changes nobody else's."""
        first = data_model("CalibrationCertificateCredential")
        first["title"] = "changed"
        assert data_model("CalibrationCertificateCredential")["title"] != "changed"

    def test_validation_never_reaches_for_the_network(self, monkeypatch) -> None:
        """A reference outside the document is an error, not a request."""

        def refuse(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("the validator tried to open a connection")

        monkeypatch.setattr(socket.socket, "connect", refuse)
        schema = {
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": "https://vcqi.example/schemas/elsewhere.json",
            "$ref": "https://elsewhere.example/loose.json",
        }
        with pytest.raises(Unresolvable):
            list(validator_for(schema).iter_errors({}))


class TestTheVerifierChecksIt:
    """``shape.data-model``: passing where it should, and each way it has to fail."""

    @pytest.mark.parametrize("name", EXAMPLES)
    def test_every_example_passes(self, world, name) -> None:
        """Each of the seventeen has the shape its type declares."""
        step = _data_model_step(_verify(world, world.credential(name)))
        assert step.status == "pass", step.detail
        assert step.evidence["dataModel"] == DATA_MODEL_URLS[_type_of(world.credential(name))]

    def test_a_status_list_is_skipped(self, world) -> None:
        """Nothing to check, and saying so is not a failure."""
        step = _data_model_step(_verify(world, world.credential("status-metas.example")))
        assert step.status == "skip"

    def test_the_top_level_does_not_grow(self, world) -> None:
        """The check nests under ``shape``; the eleven top-level steps stay eleven."""
        report = _verify(world, world.credential("callab-calibration"))
        assert len(report.steps) == 11
        assert [child.id for child in report.steps[0].children] == ["shape.data-model"]

    def test_a_model_loosened_at_its_address_is_refused(self) -> None:
        """The failure case: the credential is untouched, only the digest catches it."""
        result = tamper_by_key("loosened-data-model").apply()
        report = verify_credential(
            result.credential,
            store=result.world.store,
            now=result.verify_at,
            trusted_issuers=TRUST_ANCHORS,
        )
        assert [step.id for step in report.failures] == ["shape", "shape.data-model"]
        assert "changed since the credential was issued" in _data_model_step(report).detail

    def test_a_model_of_the_credential_s_own_choosing_is_refused(self, world) -> None:
        """Naming a schema that admits anything fails, however well it validates."""
        credential = copy.deepcopy(world.credential("metas-calibration"))
        credential["credentialSchema"] = {
            "id": "https://metas.example/schemas/anything-goes.json",
            "type": "JsonSchema",
        }
        permissive = {"$schema": JSON_SCHEMA_DIALECT, "$id": credential["credentialSchema"]["id"]}
        world_copy = build_world()
        world_copy.store.publish(permissive["$id"], permissive, "data-model")
        step = _data_model_step(_verify(world_copy, credential))
        assert step.status == "fail"
        assert DATA_MODEL_URLS["CalibrationCertificateCredential"] in step.detail

    def test_a_credential_without_its_shape_fails_with_the_member_named(self, world) -> None:
        """Validation proper: the right model, the right digest, the wrong document."""
        credential = copy.deepcopy(world.credential("metas-calibration"))
        del credential["credentialSubject"]["owner"]
        step = _data_model_step(_verify(world, credential))
        assert step.status == "fail"
        assert "credentialSubject" in step.detail and "owner" in step.detail

    def test_a_missing_reference_is_a_warning_for_a_known_type(self, world) -> None:
        """The shape went unchecked, which a reader should be told rather than assured."""
        credential = copy.deepcopy(world.credential("testlab-report"))
        del credential["credentialSchema"]
        step = _data_model_step(_verify(world, credential))
        assert step.status == "warn"
