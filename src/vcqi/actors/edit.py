"""The fields a reader may edit by hand, and the check each one is meant to reach.

``tamper.py`` is a catalogue of failures somebody else chose. This is the other half: a
reader picks a document, changes one named field, decides whether the issuer signs it
again, and watches the pipeline. The cases there reach further -- several of them change
the world around the credential, suspending an accreditation or republishing a parent
certificate, and no amount of editing one document reproduces that. What this adds is
that the reader's own hand is on it.

Fields are addressed by key and never by a path the caller writes. That is the difference
between "change this stated value and sign it again" and "rewrite any member of any
document and have a national metrology institute sign the result", and only the first is
worth building. Every path here is a literal in this file, checked against the documents
by the test suite.

Three properties of the pipeline decide the shape of what follows, and all three were
measured rather than assumed.

*Only ``shape`` short-circuits.* A failing proof does not stop the report, so a reader who
leaves the signature broken still sees every later check run. That is what makes the
re-sign toggle worth having rather than merely convenient: with it off the document is
unsigned and otherwise intact, with it on the document is perfect and something else has
to catch it.

*Nothing in the pipeline writes to the store, and no step re-fetches the credential under
test by its own identifier.* So an edited credential is verified against the shared world
exactly as ``/api/keys/issue`` already does, and no world has to be rebuilt per request.
The reader is playing a holder who presents an altered copy; the pristine document is
still published at that address, and nothing compares the two, which is worth saying out
loud rather than letting a reader infer a check that is not there.

*Most single edits fail more than one step.* Lowering a stated Expanded Uncertainty is
caught by ``scope``, because it is better than the published capability, and also by
``uncertainty.coverage``, because it no longer equals k times the Standard Uncertainty.
Both are true and the pair is the better lesson, so nothing here recomputes a budget to
tidy the second one away. ``expected_step`` names the check the field exists to reach, and
the interface reports what actually failed beside it.

A few fields change nothing at all. They are here on purpose: an editable field that
verifies clean is a hole in the pipeline stated honestly, and the three collected here are
real ones.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field as dataclass_field
from typing import Any

from vcqi.actors.registry import actor_by_did

__all__ = [
    "EditableField",
    "Change",
    "EDITABLE_FIELDS",
    "EDITABLE_DOCUMENTS",
    "fields_for",
    "field_by_key",
    "read_path",
    "write_path",
    "coerce",
    "apply_edits",
]

#: The documents a reader may edit, in the order the interface offers them.
#:
#: The five end documents, and not the recognition credentials: those are infrastructure,
#: they are what the chain is followed *through* rather than what is presented, and the
#: interesting ways to break them change the world rather than the document.
EDITABLE_DOCUMENTS: tuple[str, ...] = (
    "metas-calibration",
    "callab-calibration",
    "testlab-report",
    "cab-conformity",
    "oiml-certificate",
)


@dataclass(frozen=True)
class EditableField:
    """One field a reader may change, and what changing it is expected to reach.

    Attributes:
        key: Stable identifier, unique within the document.
        document: Short name of the credential this field belongs to.
        label: What the interface calls it.
        path: Dotted path into the credential. A segment of digits indexes a list.
        kind: ``number``, ``text``, ``date``, ``boolean`` or ``choice``.
        note: What the field is, and what changing it is likely to show.
        expected_step: Identifier of the check this field exists to reach, or None when
            the field is here precisely because nothing catches it.
        unit: Unit of a numeric field, for display beside the input.
        minimum: Smallest value accepted, in the unit of the field.
        maximum: Largest value accepted, in the unit of the field.
        choices: The values offered, for ``choice``.
    """

    key: str
    document: str
    label: str
    path: str
    kind: str
    note: str
    expected_step: str | None
    unit: str = ""
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = dataclass_field(default_factory=tuple)

    def to_json(self) -> dict[str, Any]:
        """Return the field as a JSON-compatible dictionary.

        Returns:
            Everything the interface needs to draw the input and label it, without it
            having to know anything about the document behind it.
        """
        return {
            "key": self.key,
            "document": self.document,
            "label": self.label,
            "path": self.path,
            "kind": self.kind,
            "note": self.note,
            "expectedStep": self.expected_step,
            "unit": self.unit,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "choices": list(self.choices),
        }


@dataclass(frozen=True)
class Change:
    """One field that actually moved.

    Attributes:
        key: Identifier of the field.
        label: What the interface calls it.
        path: Where in the document it sits.
        before: The pristine value.
        after: The value the reader asked for.
    """

    key: str
    label: str
    path: str
    before: Any
    after: Any

    def to_json(self) -> dict[str, Any]:
        """Return the change as a JSON-compatible dictionary.

        Returns:
            The field and both of its values, for the interface to show as a diff.
        """
        return {
            "key": self.key,
            "label": self.label,
            "path": self.path,
            "from": self.before,
            "to": self.after,
        }


#: The identifiers a reader may issue as.
#:
#: A closed list rather than a text box, and not only for tidiness: `actor_key` caches
#: derivations without bound, so feeding it arbitrary strings would grow one entry per
#: string forever. Every one of these is an organisation the reader has already met.
_ISSUERS: tuple[str, ...] = (
    "did:web:metas.example",
    "did:web:callab.example",
    "did:web:testlab.example",
    "did:web:cab.example",
    "did:web:legal-ia.example",
)


def _issuer_field(document: str, note: str, expected_step: str) -> EditableField:
    """Build the "issue it as somebody else" field for a document.

    Args:
        document: Short name of the credential.
        note: What this particular substitution shows.
        expected_step: The check expected to notice.

    Returns:
        The field.
    """
    return EditableField(
        key="issuer",
        document=document,
        label="Issued by",
        path="issuer.id",
        kind="choice",
        note=note,
        expected_step=expected_step,
        choices=_ISSUERS,
    )


EDITABLE_FIELDS: tuple[EditableField, ...] = (
    # ---------------------------------------------------------- metas-calibration
    EditableField(
        key="value",
        document="metas-calibration",
        label="Certified value",
        path="credentialSubject.calibration.results.0.value",
        kind="number",
        note=(
            "The number the certificate exists to state. CMC CH-EM-0042 runs from 1 ohm "
            "to 100 kohm, and the uncertainty the institute may claim grows with the "
            "level, so moving this far enough leaves the capability in two ways at once."
        ),
        expected_step="scope",
        unit="ohm",
        minimum=1.0e-3,
        maximum=1.0e9,
    ),
    EditableField(
        key="expanded-uncertainty",
        document="metas-calibration",
        label="Expanded Uncertainty U (k = 2)",
        path="credentialSubject.calibration.results.0.expandedUncertainty",
        kind="number",
        note=(
            "Claim a better uncertainty than the institute has ever demonstrated. The "
            "budget underneath is left alone, so two checks answer: the capability says "
            "the claim is too good, and the arithmetic says it no longer matches the "
            "contributions offered for it."
        ),
        expected_step="scope",
        unit="ohm",
        minimum=1.0e-6,
        maximum=1.0,
    ),
    EditableField(
        key="coverage-factor",
        document="metas-calibration",
        label="Coverage factor k",
        path="credentialSubject.calibration.results.0.coverageFactor",
        kind="number",
        note=(
            "Report at k = 1 while printing the k = 2 figure. The schema the recognition "
            "names pins this at 2, so the document stops being the shape the capability "
            "was granted for."
        ),
        expected_step="output-validation",
        minimum=0.5,
        maximum=6.0,
    ),
    EditableField(
        key="valid-until",
        document="metas-calibration",
        label="Valid until",
        path="validUntil",
        kind="date",
        note=(
            "Validity is evaluated against the moment of verification rather than the "
            "moment of issue, so a date in the past is refused today and was not "
            "yesterday."
        ),
        expected_step="validity",
    ),
    EditableField(
        key="mra-logo",
        document="metas-calibration",
        label="Claims CIPM MRA coverage",
        path="credentialSubject.calibration.mraLogoAsserted",
        kind="boolean",
        note=(
            "Withdrawing a claim is not a failure, which is why this one stays green. "
            "The claim is adjudicated when it is made, not when it is dropped."
        ),
        expected_step=None,
    ),
    _issuer_field(
        "metas-calibration",
        "Issue the institute's certificate as somebody else. Nothing about the document "
        "is malformed and the signature will be genuine; there is simply no route from "
        "the new identifier to the BIPM.",
        "recognition",
    ),
    # --------------------------------------------------------- callab-calibration
    EditableField(
        key="value",
        document="callab-calibration",
        label="Certified value",
        path="credentialSubject.calibration.results.0.value",
        kind="number",
        note=(
            "Worth watching carefully. The row of the accreditation scope is chosen on "
            "the nominal value, which this does not touch, while the uncertainty floor "
            "is evaluated at the measured value, which it does."
        ),
        expected_step="scope",
        unit="ohm",
        minimum=1.0e-3,
        maximum=1.0e9,
    ),
    EditableField(
        key="expanded-uncertainty",
        document="callab-calibration",
        label="Expanded Uncertainty U (k = 2)",
        path="credentialSubject.calibration.results.0.expandedUncertainty",
        kind="number",
        note=(
            "There is very little room here: the laboratory reports 0.052 ohm against a "
            "floor of 0.050, so a claim that looks only slightly better is already "
            "outside what SCS 0123 permits."
        ),
        expected_step="scope",
        unit="ohm",
        minimum=1.0e-4,
        maximum=10.0,
    ),
    EditableField(
        key="mra-logo",
        document="callab-calibration",
        label="Claims CIPM MRA coverage",
        path="credentialSubject.calibration.mraLogoAsserted",
        kind="boolean",
        note=(
            "The logo belongs to the institutes that signed the arrangement, not to the "
            "laboratories they calibrate for. Stated as a machine-readable claim, it can "
            "be adjudicated instead of being taken on trust from an image."
        ),
        expected_step="mra-logo",
    ),
    EditableField(
        key="frequency",
        document="callab-calibration",
        label="Frequency of the measurement",
        path="credentialSubject.calibration.conditionQuantities.0.value",
        kind="number",
        note=(
            "The laboratory is accredited for direct current. An accreditation scope is "
            "a table, and the conditions are one of the columns that decides which row "
            "applies, so this asks the verifier to find a row and it cannot."
        ),
        expected_step="scope",
        unit="Hz",
        minimum=0.0,
        maximum=1.0e6,
    ),
    EditableField(
        key="traced-object",
        document="callab-calibration",
        label="Transfer standard the chain is traced through",
        path="credentialSubject.calibration.traceableTo.instrument",
        kind="text",
        note=(
            "Following a chain by identifier and digest establishes which documents are "
            "in it and nothing about what they are about. Name a different resistor and "
            "every signature still verifies, every digest still matches, and the chain "
            "is no longer a chain."
        ),
        expected_step="traceability",
    ),
    EditableField(
        key="traced-digest",
        document="callab-calibration",
        label="Digest of the parent certificate",
        path="credentialSubject.calibration.traceableTo.digestMultibase",
        kind="text",
        note=(
            "A traceability reference carries a content digest, so the reference is only "
            "satisfied by the exact document that was referenced."
        ),
        expected_step="traceability",
    ),
    EditableField(
        key="valid-until",
        document="callab-calibration",
        label="Valid until",
        path="validUntil",
        kind="date",
        note="The same check as on the institute's certificate, one level down.",
        expected_step="validity",
    ),
    _issuer_field(
        "callab-calibration",
        "The same substitution as on the institute's certificate reaches a different "
        "check here, which is worth seeing: the testing laboratory really is recognised "
        "by the accreditation body, just not for this.",
        "action",
    ),
    # ------------------------------------------------------------- testlab-report
    EditableField(
        key="standard",
        document="testlab-report",
        label="Standard tested against",
        path="credentialSubject.testing.standard",
        kind="choice",
        note=(
            "Two of these are refused and one is not. A scope lists its methods as sets "
            "of equivalent designations, so the dated form of the same standard is "
            "covered and a different standard is not."
        ),
        expected_step="scope",
        choices=("IEC 60335-1", "IEC 60335-1:2020", "IEC 62368-1", "IEC 61010-1"),
    ),
    EditableField(
        key="performed-on",
        document="testlab-report",
        label="Date the testing was performed",
        path="credentialSubject.testing.performedOn",
        kind="date",
        note=(
            "The register is asked what the accreditation covered on the day the testing "
            "was performed, not what it covers now. Move the date far enough back and "
            "the register answers honestly, about a day the scope had no rows in force."
        ),
        expected_step="scope",
    ),
    EditableField(
        key="scope-digest",
        document="testlab-report",
        label="Digest of the accreditation scope",
        path="credentialSubject.testing.capabilityReference.digestMultibase",
        kind="text",
        note=(
            "The report pins the scope it was issued under by content digest. Without "
            "that a verifier could only fetch whatever the register serves today."
        ),
        expected_step="scope",
    ),
    EditableField(
        key="equipment-digest",
        document="testlab-report",
        label="Digest of the equipment's calibration",
        path="credentialSubject.testing.equipmentTraceability.0.digestMultibase",
        kind="text",
        note=(
            "What makes a test report a measurement rather than an opinion is the "
            "equipment behind it, referenced as a document rather than named in prose."
        ),
        expected_step="traceability",
    ),
    EditableField(
        key="equipment-object",
        document="testlab-report",
        label="Instrument the measurements were made with",
        path="credentialSubject.testing.equipmentTraceability.0.equipment",
        kind="text",
        note=(
            "Nothing catches this, and that is the point of offering it. The object "
            "identity check looks for a member called `instrument`, which is what a "
            "calibration certificate uses; a test report names its equipment under "
            "`equipment`, so the check reports that the reference names no object and "
            "moves on. A real hole, left visible rather than tidied away."
        ),
        expected_step=None,
    ),
    _issuer_field(
        "testlab-report",
        "The calibration laboratory is genuinely accredited and genuinely recognised. It "
        "is accredited for calibration.",
        "action",
    ),
    # ------------------------------------------------------------- cab-conformity
    EditableField(
        key="standard",
        document="cab-conformity",
        label="Standard certified against",
        path="credentialSubject.conformity.standard",
        kind="choice",
        note=(
            "A certification scope lists the standards it covers, so certifying against "
            "one it does not name is refused even though everything else is in order."
        ),
        expected_step="scope",
        choices=("IEC 60335-1", "IEC 62368-1", "IEC 61010-1"),
    ),
    EditableField(
        key="report-digest",
        document="cab-conformity",
        label="Digest of the test report relied on",
        path="credentialSubject.conformity.testReports.0.digestMultibase",
        kind="text",
        note=(
            "The certificate of conformity is only as good as the report beneath it, and "
            "referencing that report as a document is what lets a recipient check the "
            "level down."
        ),
        expected_step="traceability",
    ),
    EditableField(
        key="statement",
        document="cab-conformity",
        label="Statement of conformity",
        path="credentialSubject.conformity.conformityStatement",
        kind="text",
        note=(
            "The sentence a person reads, and nothing whatever adjudicates it. Every "
            "check that means anything here is against the standard, the scope and the "
            "report; the prose is decoration, and editing it is the quickest way to see "
            "that a verifier never reads the certificate the way a person does."
        ),
        expected_step=None,
    ),
    EditableField(
        key="valid-until",
        document="cab-conformity",
        label="Valid until",
        path="validUntil",
        kind="date",
        note="A certificate of conformity presented after it ran out.",
        expected_step="validity",
    ),
    _issuer_field(
        "cab-conformity",
        "Certification is a different main scope from testing and from calibration, "
        "assessed against a different standard.",
        "action",
    ),
    # ---------------------------------------------------------- oiml-certificate
    EditableField(
        key="legal-effect",
        document="oiml-certificate",
        label="Legal effect claimed",
        path="credentialSubject.oimlCertificate.legalEffect",
        kind="choice",
        note=(
            "An OIML certificate is type-evaluation evidence and not an approval. The "
            "disclaimer is a schema requirement rather than a courtesy, so claiming more "
            "makes the document the wrong shape."
        ),
        expected_step="output-validation",
        choices=("none", "national", "regional"),
    ),
    EditableField(
        key="standard",
        document="oiml-certificate",
        label="Recommendation certified against",
        path="credentialSubject.oimlCertificate.standard",
        kind="choice",
        note=(
            "A Recommendation bounds an Issuing Authority exactly as a published CMC "
            "bounds an institute. Recognition is never recognition to do anything at all."
        ),
        expected_step="scope",
        choices=("OIML R 46:2012", "OIML R 49:2013", "OIML R 60:2017"),
    ),
    EditableField(
        key="report-digest",
        document="oiml-certificate",
        label="Digest of the type evaluation report",
        path="credentialSubject.oimlCertificate.testReport.digestMultibase",
        kind="text",
        note=(
            "Reviewing the test results is the Issuing Authority's defined job under the "
            "scheme, which is why the report is referenced rather than summarised."
        ),
        expected_step="traceability",
    ),
    EditableField(
        key="range-maximum",
        document="oiml-certificate",
        label="Upper limit of the Recommendation",
        path="credentialSubject.oimlCertificate.recommendation.rangeMaximum",
        kind="number",
        note=(
            "Nothing catches this either, and for a better reason than the last one. The "
            "credential carries a copy of the Recommendation for a reader's convenience, "
            "and the verifier adjudicates against the register's copy. Editing your copy "
            "of somebody else's document changes nothing, which is the property you would "
            "want."
        ),
        expected_step=None,
        unit="%",
        minimum=-100.0,
        maximum=100.0,
    ),
    EditableField(
        key="valid-until",
        document="oiml-certificate",
        label="Valid until",
        path="validUntil",
        kind="date",
        note="A type certificate presented after it ran out.",
        expected_step="validity",
    ),
    _issuer_field(
        "oiml-certificate",
        "The testing laboratory is recognised by the OIML, as a Test Laboratory. Issuing "
        "certificates is the Issuing Authority's role, and they are two rosters.",
        "recognition",
    ),
)

_BY_DOCUMENT: dict[str, tuple[EditableField, ...]] = {
    document: tuple(f for f in EDITABLE_FIELDS if f.document == document)
    for document in EDITABLE_DOCUMENTS
}


def fields_for(document: str) -> tuple[EditableField, ...]:
    """Return the fields offered for one document.

    Args:
        document: Short name of the credential.

    Returns:
        The fields, in the order the interface offers them. Empty for a document that
        offers none.
    """
    return _BY_DOCUMENT.get(document, ())


def field_by_key(document: str, key: str) -> EditableField | None:
    """Look up one field.

    Args:
        document: Short name of the credential.
        key: Identifier of the field within that document.

    Returns:
        The field, or None when the document does not offer it.
    """
    for candidate in fields_for(document):
        if candidate.key == key:
            return candidate
    return None


def _segments(path: str) -> list[str]:
    """Split a dotted path into its segments.

    Args:
        path: The dotted path.

    Returns:
        The segments, in order.
    """
    return path.split(".")


def read_path(document: dict[str, Any], path: str) -> Any:
    """Read the value at a dotted path.

    Args:
        document: The document to read from.
        path: Dotted path, where a segment of digits indexes a list.

    Returns:
        The value.

    Raises:
        KeyError: If the path does not resolve.
    """
    here: Any = document
    for segment in _segments(path):
        if isinstance(here, list):
            if not segment.isdigit() or int(segment) >= len(here):
                raise KeyError(f"{path} does not resolve at {segment!r}")
            here = here[int(segment)]
        elif isinstance(here, dict):
            if segment not in here:
                raise KeyError(f"{path} does not resolve at {segment!r}")
            here = here[segment]
        else:
            raise KeyError(f"{path} does not resolve at {segment!r}")
    return here


def write_path(document: dict[str, Any], path: str, value: Any) -> None:
    """Overwrite the value at a dotted path.

    Overwrites only. A path that does not already resolve raises rather than creating the
    member, so a typo in the catalogue fails loudly instead of quietly growing the
    document into a shape the schema was never written for.

    Args:
        document: The document to modify, in place.
        path: Dotted path, where a segment of digits indexes a list.
        value: The replacement.

    Raises:
        KeyError: If the path does not already resolve.
    """
    segments = _segments(path)
    parent = read_path(document, ".".join(segments[:-1])) if len(segments) > 1 else document
    last = segments[-1]
    if isinstance(parent, list):
        if not last.isdigit() or int(last) >= len(parent):
            raise KeyError(f"{path} does not resolve at {last!r}")
        parent[int(last)] = value
    elif isinstance(parent, dict):
        if last not in parent:
            raise KeyError(f"{path} does not resolve at {last!r}")
        parent[last] = value
    else:
        raise KeyError(f"{path} does not resolve at {last!r}")


def coerce(field: EditableField, value: Any) -> Any:
    """Read one submitted value as the kind its field declares.

    Every rejection here is a rejection the pipeline would otherwise turn into something
    worse than a refusal. A date that cannot be parsed is treated by the validity check as
    no date at all and *passes*, which would teach a reader the opposite of the truth. A
    non-finite number is accepted by JSON and rejected by the canonicalization the
    signature is computed over, which would be an unexplained failure rather than a lesson.

    Args:
        field: The field being written.
        value: What the caller submitted.

    Returns:
        The value, in the type the document should carry.

    Raises:
        ValueError: If the value cannot be read as that kind, is outside the field's
            range, or is not one of its choices.
    """
    if field.kind == "boolean":
        if isinstance(value, bool):
            return value
        raise ValueError(f"{field.label} is either true or false")

    if field.kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field.label} is a number")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{field.label} has to be a finite number")
        if field.minimum is not None and number < field.minimum:
            raise ValueError(f"{field.label} cannot be below {field.minimum:g}")
        if field.maximum is not None and number > field.maximum:
            raise ValueError(f"{field.label} cannot be above {field.maximum:g}")
        return number

    if not isinstance(value, str):
        raise ValueError(f"{field.label} is text")
    text = value.strip()
    if not text:
        raise ValueError(f"{field.label} cannot be empty")

    if field.kind == "choice":
        if text not in field.choices:
            raise ValueError(f"{field.label} is not one of the values offered")
        if field.path == "issuer.id" and actor_by_did(text) is None:
            raise ValueError(f"{text} is not an organisation in this demonstration")
        return text

    if field.kind == "date":
        # The documents carry XML Schema dateTime, and the interface sends a plain date.
        # Widening it to the whole day rather than to midnight would be a second rule for
        # a reader to learn; midnight is what a date input means everywhere else.
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            head, tail = text, "T00:00:00Z"
        else:
            head, tail = text, ""
        try:
            year, month, day = (int(part) for part in head[:10].split("-"))
            _ = year, month, day
        except ValueError as error:
            raise ValueError(f"{field.label} is a date, as YYYY-MM-DD") from error
        return f"{head}{tail}"

    return text


def apply_edits(
    credential: dict[str, Any], edits: dict[str, Any], *, document: str
) -> list[Change]:
    """Write the reader's edits into a credential, in place.

    Args:
        credential: A copy of the document to modify. Never the world's own.
        edits: Submitted values, keyed by field identifier.
        document: Short name of the credential, for looking fields up.

    Returns:
        One entry per field that actually moved, in catalogue order. A field submitted
        at its pristine value is not a change and is not reported as one.

    Raises:
        KeyError: If a key names no field of this document.
        ValueError: If a value cannot be read as the kind its field declares.
    """
    changes: list[Change] = []
    for field in fields_for(document):
        if field.key not in edits:
            continue
        wanted = coerce(field, edits[field.key])
        before = read_path(credential, field.path)
        if before == wanted and type(before) is type(wanted):
            continue
        write_path(credential, field.path, wanted)
        changes.append(
            Change(
                key=field.key,
                label=field.label,
                path=field.path,
                before=before,
                after=wanted,
            )
        )

    unknown = set(edits) - {field.key for field in fields_for(document)}
    if unknown:
        raise KeyError(f"{document} offers no field named {sorted(unknown)[0]!r}")
    return changes
