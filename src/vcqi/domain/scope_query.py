"""Asking a register what a testing laboratory is accredited for.

A calibration scope and a testing scope are both tables, and they are read in opposite
directions. A calibration row states a capability and the check is a numeric
adjudication: you need the floor formula in hand to decide whether a claimed uncertainty
clears it, so the row has to travel to the verifier. A testing row states a *method*, and
the check is a membership test -- is this standard covered? -- whose answer is one bit.

Three things about a real testing scope push that bit towards being asked for rather than
read out of a document.

**Size.** A published testing scope runs to fourteen pages and several hundred standard
designations across three columns: the product or material group, the principle of
measurement, and the test methods. Shipping that to every verifier to answer one question
is absurd.

**Equivalence.** The methods column lists designations in sets rather than singly --
``EN 61000-3-2, IEC 61000-3-2`` -- because the European adoption and the international
standard are the same test. A verifier holding a report that names one of them has to
know it matches a row listing the other, which is a lookup rather than a comparison.

**Flexibility.** Every page of a published scope declares, in its footer, which scope of
application each row has: Type A is fixed, Types B and C are flexible. A flexible row
covers editions of its standards that did not exist when the scope was granted, which
means the answer is *derived* and not stored. No document can hold it: a frozen list
cannot say "and whatever comes next". Something has to apply the rule, and the only party
entitled to apply it is the body that granted the scope.

So this module is the rule, kept free of credentials and transport in the same way
:mod:`vcqi.domain.scope` is. :func:`answer_coverage` decides; who signs the answer and how
it is addressed belongs to ``vc/`` and ``actors/``.

**The date is part of the question.** A scope grows and shrinks between certificates, and
a test report is evidence about the day it was tested. Asking whether a standard is
covered *now* answers a different question from the one a verifier needs, and answers it
in the dangerous direction: a laboratory that tested outside its scope in May passes in
September once the scope has been extended. So a question carries the date it is asked
about, and a row carries the dates it entered and left the scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

__all__ = [
    "FLEXIBILITY_TYPES",
    "FLEXIBLE",
    "TestScopeRow",
    "test_scope_row_from_json",
    "CoverageQuestion",
    "CoverageAnswer",
    "answer_coverage",
]


#: The scopes of application a published testing scope declares for each of its rows,
#: per the accreditation body's own definition document. Type A is fixed: the row covers
#: the designations it lists and nothing else. Types B and C are flexible, and differ in
#: how much the laboratory may vary a method without telling anybody -- a distinction
#: this demonstration records and does not act on, because acting on it needs the
#: definition document and that is not a thing this project is entitled to invent.
FLEXIBILITY_TYPES: frozenset[str] = frozenset({"A", "B", "C"})

#: The types under which a row covers editions of its standards that it does not list.
FLEXIBLE: frozenset[str] = frozenset({"B", "C"})


def _split_designation(designation: str) -> tuple[str, str | None]:
    """Separate a standard designation from its edition.

    Args:
        designation: A designation as a register or a report writes it, for example
            ``IEC 60335-1:2010`` or ``IEC 60335-1``.

    Returns:
        The base designation and the edition, or None when none is stated.
    """
    base, separator, edition = designation.partition(":")
    return (base.strip(), edition.strip() if separator else None)


@dataclass(frozen=True)
class TestScopeRow:
    """One row of a published testing scope.

    Attributes:
        label: Short identifier for messages, for example ``STS 0456 row 2``.
        product_group: The product or material group the row applies to, as the register
            writes it in its first column.
        principle: The principle of measurement, characteristic or type of test, as the
            register writes it in its second column.
        standards: The designations the row covers, as a set of equivalents. A register
            writes ``EN 60335-1, IEC 60335-1`` in one cell because they are the same
            test, and a report naming either one is inside the row.
        flexibility: ``A``, ``B`` or ``C``. See :data:`FLEXIBILITY_TYPES`.
        added_on: ISO 8601 date the row entered the scope.
        withdrawn_on: ISO 8601 date it left, or None while it is still in force.
    """

    label: str
    product_group: str
    principle: str
    standards: tuple[str, ...]
    flexibility: str
    added_on: str
    withdrawn_on: str | None = None

    def in_force_on(self, date: str) -> bool:
        """Return whether this row was part of the scope on a given date.

        Args:
            date: The date asked about, as an ISO 8601 date. String comparison is
                correct for this format and avoids parsing a date to compare two of them.

        Returns:
            True when the row had been added and had not been withdrawn.
        """
        if date < self.added_on:
            return False
        return self.withdrawn_on is None or date < self.withdrawn_on

    def covers(self, standard: str) -> tuple[bool, str]:
        """Return whether this row covers a standard, and on what grounds.

        Args:
            standard: The designation a report names.

        Returns:
            Whether it is covered, and the reason -- which matters more here than in a
            lookup, because a flexible row answers for designations it does not list and
            an answer that cannot say why is not evidence of anything.
        """
        if standard in self.standards:
            return (True, f"{standard} is listed in {self.label}")

        base, _ = _split_designation(standard)
        listed = {_split_designation(entry)[0] for entry in self.standards}
        if base not in listed:
            return (False, "")

        if self.flexibility in FLEXIBLE:
            return (
                True,
                f"{self.label} lists {', '.join(self.standards)} under a flexible scope "
                f"of application (Type {self.flexibility}), which covers {standard}",
            )
        return (
            False,
            f"{self.label} lists {', '.join(self.standards)} under a fixed scope of "
            f"application (Type {self.flexibility}), which does not extend to {standard}",
        )

    def to_json(self) -> dict[str, Any]:
        """Return the row as the accreditation body would publish it.

        Returns:
            A JSON-compatible dictionary.
        """
        document: dict[str, Any] = {
            "label": self.label,
            "productGroup": self.product_group,
            "principle": self.principle,
            "standards": list(self.standards),
            "flexibility": self.flexibility,
            "addedOn": self.added_on,
        }
        if self.withdrawn_on is not None:
            document["withdrawnOn"] = self.withdrawn_on
        return document


def test_scope_row_from_json(document: Any) -> TestScopeRow | None:
    """Rebuild a testing scope row from the form a register publishes it in.

    Args:
        document: One entry of a published scope's ``testRows``.

    Returns:
        The row, or None when it cannot be read.
    """
    if not isinstance(document, dict):
        return None
    standards = document.get("standards")
    if not isinstance(standards, list) or not standards:
        return None
    try:
        return TestScopeRow(
            label=str(document.get("label", "row")),
            product_group=str(document.get("productGroup", "")),
            principle=str(document.get("principle", "")),
            standards=tuple(str(entry) for entry in standards),
            flexibility=str(document["flexibility"]),
            added_on=str(document["addedOn"]),
            withdrawn_on=(
                str(document["withdrawnOn"]) if document.get("withdrawnOn") else None
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


@dataclass(frozen=True)
class CoverageQuestion:
    """What a verifier asks a register about a testing scope.

    Attributes:
        standard: The designation the report was issued against.
        at: The date the question is asked *about*, as an ISO 8601 date -- the date the
            testing was performed, never the date of the verification.
    """

    standard: str
    at: str

    def to_query(self) -> str:
        """Render the question as a query string.

        The parameters are sorted and percent-encoded, so one question has exactly one
        spelling. That is what lets the answer be addressed by the question: two
        verifiers asking the same thing compose the same address, and an answer stapled
        by a holder is found by the verifier that asks for it.

        Returns:
            The query string, without a leading ``?``.
        """
        pairs = sorted({"standard": self.standard, "at": self.at}.items())
        return "&".join(f"{key}={quote(value, safe='')}" for key, value in pairs)

    def address(self, endpoint: str) -> str:
        """Return the full address this question is asked at.

        Args:
            endpoint: The query endpoint the capability reference names.

        Returns:
            The endpoint with the question appended.
        """
        return f"{endpoint}?{self.to_query()}"

    def to_json(self) -> dict[str, Any]:
        """Return the question as it is echoed inside an answer.

        Returns:
            A JSON-compatible dictionary.
        """
        return {"standard": self.standard, "at": self.at}


@dataclass(frozen=True)
class CoverageAnswer:
    """What the register answers, and on what grounds.

    Attributes:
        covered: Whether the scope covered that standard on that date.
        row: Label of the row that decided it, or None when none did.
        flexibility: The scope of application of that row, or None.
        reason: Why, in the register's own terms. A derived answer that cannot say how it
            was derived is not evidence, and a refusal that cannot say what it looked at
            is not a finding.
        considered: How many rows were in force on the date asked about.
    """

    covered: bool
    row: str | None
    flexibility: str | None
    reason: str
    considered: int

    def to_json(self) -> dict[str, Any]:
        """Return the answer as it appears inside the credential carrying it.

        Returns:
            A JSON-compatible dictionary.
        """
        document: dict[str, Any] = {
            "covered": self.covered,
            "reason": self.reason,
            "rowsConsidered": self.considered,
        }
        if self.row is not None:
            document["row"] = self.row
        if self.flexibility is not None:
            document["flexibility"] = self.flexibility
        return document


def answer_coverage(
    rows: tuple[TestScopeRow, ...], question: CoverageQuestion
) -> CoverageAnswer:
    """Decide whether a testing scope covered a standard on a date.

    Args:
        rows: The published rows, in register order.
        question: What is being asked.

    Returns:
        The answer, carrying the row that decided it and why.
    """
    in_force = [row for row in rows if row.in_force_on(question.at)]

    refusals: list[str] = []
    for row in in_force:
        covered, reason = row.covers(question.standard)
        if covered:
            return CoverageAnswer(
                covered=True,
                row=row.label,
                flexibility=row.flexibility,
                reason=reason,
                considered=len(in_force),
            )
        if reason:
            refusals.append(reason)

    if refusals:
        detail = "; ".join(refusals)
    elif in_force:
        detail = (
            f"no row in force on {question.at} lists {question.standard} or anything "
            f"equivalent to it"
        )
    else:
        detail = f"the scope had no rows in force on {question.at}"

    return CoverageAnswer(
        covered=False,
        row=None,
        flexibility=None,
        reason=detail,
        considered=len(in_force),
    )
