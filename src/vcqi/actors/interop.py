"""Check this project's credentials against somebody else's implementation.

Everything verified in this demonstration has so far been verified by the verifier in
this same repository, written by the same hand as the issuer. That arrangement cannot
catch a misreading the two halves share. The UN/CEFACT UNTP Playground is an independent
implementation with no stake in our assumptions, and handing it a credential is the
cheapest available way to find out whether the shared misreading exists.

The Playground runs seven steps. Five of them are about the W3C Verifiable Credentials
specification -- proof type, VCDM version, VCDM schema, cryptographic verification, and
JSON-LD context expansion -- and those are the ones this project answers to. The sixth,
UNTP Schema Validation, is about UNTP conformance, which a calibration certificate is
under no obligation to achieve; it is run here as a mapping probe rather than a target.

It runs them only over UNTP's own credential types. Since its release 0.4.0 of
21 September 2026 the Playground refuses any other ``type`` at upload, before the first
step, so of the three forms below only ``untp`` reaches it. The other two remain the
forms to hand to a verifier that takes an arbitrary W3C credential.

This module produces the three artefacts to hand over and reports what can be determined
without leaving the machine:

* **native** -- the credential exactly as issued. Fails cryptographic verification
  outside this world, because ``did:web:metas.example`` resolves nowhere, and fails
  context expansion, because ``https://vcqi.example/contexts/v1`` is fictional. Both are
  recorded in ARCHITECTURE.md already; an outside tool saying so independently is
  confirmation rather than news.
* **portable** -- the same claims, same key, re-issued under the ``did:key`` that key
  stands for. This is the one that makes the cryptographic step answerable by a stranger.
* **untp** -- the projection into UNTP's vocabulary, signed the same portable way: a
  certificate as a Digital Conformity Credential, a recognition as a Digital Identity
  Anchor for one of the entities it lists. The only form the Playground accepts, and it
  carries published contexts only.

Two of the Playground's steps can be answered here, offline, for the projection: what
the schema step says, against the vendored UNTP schema, and whether every term expands,
against the vendored contexts -- a stand-in for the JSON-LD step, written by the same hand
(see :mod:`vcqi.vc.jsonld_terms`). What the other steps say has to come from the
Playground itself, and is recorded in the working plan, PLAN.md, when somebody runs it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from vcqi.actors.registry import actor_key
from vcqi.actors.scenarios import DEMO_NOW, World
from vcqi.vc.jsonld_terms import term_problems
from vcqi.vc.portable import portable_copy
from vcqi.vc.untp import UNTP_VERSION, project, schema_errors, vendored_contexts

#: What the probe is run over, as the credential and, for a recognition, the entity it
#: anchors. At each layer, the case UNTP was not built for and the case it was: a
#: calibration and a certificate of conformity, and the CIPM MRA's recognition of METAS
#: and an accreditation body's recognition of a certification body. Both are needed --
#: one of them failing alone would say nothing about which of the format and the
#: document was the reason.
PROBED: tuple[tuple[str, str | None], ...] = (
    ("metas-calibration", None),
    ("cab-conformity", None),
    ("bipm-recognition", "did:web:metas.example"),
    ("sas-recognition", "did:web:cab.example"),
)

#: The three forms a credential can be exported in.
FORMS = ("native", "portable", "untp")


def export_document(
    world: World,
    name: str,
    form: str,
    *,
    subject: str | None = None,
    created: datetime = DEMO_NOW,
) -> dict[str, Any]:
    """Return one credential in one of the three exportable forms.

    Args:
        world: The built demonstration world.
        name: Short name of the credential, for example ``metas-calibration``.
        form: One of :data:`FORMS`.
        subject: For the ``untp`` form of a recognition, the DID of the entity to
            anchor; UNTP anchors one entity where a recognition lists several.
        created: When a re-issued proof was created. Fixed by default, so that exporting
            the same credential twice produces the same bytes.

    Returns:
        The document, signed.

    Raises:
        KeyError: If no credential is registered under that name.
        ValueError: If the form is not one of :data:`FORMS`, the credential has no
            UNTP projection, or a recognition's entity is missing or unknown.
    """
    credential = world.credential(name)
    if form == "native":
        return credential

    key = actor_key(credential["issuer"]["id"])
    if form == "portable":
        signed, _ = portable_copy(credential, key, created=created)
        return signed
    if form == "untp":
        projected = project(credential, world.store.get, subject).credential
        signed, _ = portable_copy(projected, key, created=created)
        return signed
    raise ValueError(f"unknown export form {form!r}")


def untp_audit(world: World) -> dict[str, Any]:
    """Project the probed credentials into UNTP and report what the mapping cost.

    Args:
        world: The built demonstration world.

    Returns:
        The UNTP version probed, whether every schema error is accounted for and every
        term expands, and one entry per credential carrying its name, the findings the
        mapping recorded, the errors the pinned UNTP schema reports against the result,
        and the terms that do not expand against the vendored contexts.
    """
    contexts = vendored_contexts()
    entries = []
    for name, subject in PROBED:
        credential = world.credential(name)
        projection = project(credential, world.store.get, subject)
        errors = schema_errors(projection.credential)
        problems = term_problems(projection.credential, contexts)
        entries.append(
            {
                "name": name,
                "subject": subject,
                "title": projection.credential.get("name"),
                "sourceType": _own_type(credential),
                "untpType": _own_type(projection.credential),
                "findings": [finding.to_json() for finding in projection.findings],
                "blocking": len(projection.blocking),
                "schemaErrors": errors,
                "termProblems": [problem.to_json() for problem in problems],
                "valid": not errors,
                # Member by member, not by count: a count agrees when a plausible value
                # fills one required member and an unrecorded gap opens another, which is
                # exactly the fill the projection's rule forbids.
                "accounted": {error["member"] for error in errors}
                == {finding.path for finding in projection.blocking},
            }
        )
    return {
        "version": UNTP_VERSION,
        "credentials": entries,
        # Every schema error should be a finding this module recorded and can explain. If
        # these ever disagree, the projection has a bug rather than a finding.
        "accountedFor": all(entry["accounted"] for entry in entries),
        "expands": all(not entry["termProblems"] for entry in entries),
    }


def _own_type(credential: dict[str, Any]) -> str:
    """Return the credential type that is not ``VerifiableCredential``.

    Args:
        credential: The credential to read.

    Returns:
        The specific type, or an empty string if there is none.
    """
    for name in credential.get("type", []):
        if name != "VerifiableCredential":
            return str(name)
    return ""
