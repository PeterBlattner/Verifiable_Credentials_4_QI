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

This module produces the three artefacts to hand over and reports what can be determined
without leaving the machine:

* **native** -- the credential exactly as issued. Fails cryptographic verification
  outside this world, because ``did:web:metas.example`` resolves nowhere, and fails
  context expansion, because ``https://vcqi.example/contexts/v1`` is fictional. Both are
  recorded in ARCHITECTURE.md already; an outside tool saying so independently is
  confirmation rather than news.
* **portable** -- the same claims, same key, re-issued under the ``did:key`` that key
  stands for. This is the one that makes the cryptographic step answerable by a stranger.
* **untp** -- the projection into UNTP's vocabulary, signed the same portable way.

What the schema step says about the projection is computed here, offline, against the
vendored schema. What the other steps say has to come from the Playground itself, and is
recorded in PLAN.md when somebody runs it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from vcqi.actors.registry import actor_key
from vcqi.actors.scenarios import DEMO_NOW, World
from vcqi.vc.portable import portable_copy
from vcqi.vc.untp import UNTP_VERSION, project, schema_errors

#: The credentials the probe is run over: the case UNTP was not built for, and the case
#: it was. Both are needed -- one of them failing alone would say nothing about which of
#: the format and the document was the reason.
PROBED = ("metas-calibration", "cab-conformity")

#: The three forms a credential can be exported in.
FORMS = ("native", "portable", "untp")


def export_document(
    world: World, name: str, form: str, *, created: datetime = DEMO_NOW
) -> dict[str, Any]:
    """Return one credential in one of the three exportable forms.

    Args:
        world: The built demonstration world.
        name: Short name of the credential, for example ``metas-calibration``.
        form: One of :data:`FORMS`.
        created: When a re-issued proof was created. Fixed by default, so that exporting
            the same credential twice produces the same bytes.

    Returns:
        The document, signed.

    Raises:
        KeyError: If no credential is registered under that name.
        ValueError: If the form is not one of :data:`FORMS`, or the credential has no
            UNTP projection.
    """
    credential = world.credential(name)
    if form == "native":
        return credential

    key = actor_key(credential["issuer"]["id"])
    if form == "portable":
        signed, _ = portable_copy(credential, key, created=created)
        return signed
    if form == "untp":
        signed, _ = portable_copy(project(credential).credential, key, created=created)
        return signed
    raise ValueError(f"unknown export form {form!r}")


def untp_audit(world: World) -> dict[str, Any]:
    """Project the probed credentials into UNTP and report what the mapping cost.

    Args:
        world: The built demonstration world.

    Returns:
        The UNTP version probed, and one entry per credential carrying its name, the
        omissions the mapping had to make, and the errors the pinned UNTP schema reports
        against the result.
    """
    entries = []
    for name in PROBED:
        credential = world.credential(name)
        projection = project(credential)
        errors = schema_errors(projection.credential)
        entries.append(
            {
                "name": name,
                "title": credential.get("name"),
                "sourceType": _own_type(credential),
                "omissions": [omission.to_json() for omission in projection.omissions],
                "blocking": len(projection.blocking),
                "schemaErrors": errors,
                "valid": not errors,
            }
        )
    return {
        "version": UNTP_VERSION,
        "credentials": entries,
        # Every schema error should be an omission this module chose and can explain. If
        # these ever disagree, the projection has a bug rather than a finding.
        "accountedFor": all(
            len(entry["schemaErrors"]) == entry["blocking"] for entry in entries
        ),
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
