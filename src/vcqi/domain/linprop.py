"""Linear uncertainty propagation, in pure Python, over the subset UncLib is used for.

METAS UncLib is the reference implementation of this arithmetic, and the demonstrator
uses it wherever it is installed. It cannot be the *deployed* implementation. The METAS
UncLib licence grants a designated-computer licence and prohibits distribution to third
parties "whether modified, incorporated into a software package, incorporated into any
kind of device or machine, reproduced or left in its original form". A container image
on a hosting provider is three of those at once, so a public deployment needs an engine
it is allowed to ship.

So this module implements the part of UncLib the demonstrator actually exercises, and
``tests/test_linprop_equivalence.py`` asserts that the two agree: identical values,
identical budgets, and byte-identical XML. The subset is worth stating plainly, because
its smallness is what makes the claim checkable: real-valued scalars, the four
arithmetic operations, and the LinProp propagation law

    u_c(y)^2 = sum_i ( dy/dx_i * u(x_i) )^2

evaluated by carrying the sensitivities forward rather than differentiating afterwards.
Every measurement model in this project is a sum of products of scalars, so first-order
propagation is not an approximation here: the sensitivities are exact, and the agreement
with UncLib is exact rather than close.

The thing that matters more than the arithmetic is *identity*. Each independent input
carries an identifier, and an uncertain number is a value plus a sensitivity to each
identified input it depends on. Two results computed from the same input therefore
depend on the same identifier, and combining them accounts for the correlation instead
of treating them as independent. That is the property this demonstrator argues for, and
it belongs to the representation rather than to the library: keeping the sensitivity
vector keyed on input identity is the entire mechanism.

Deliberately absent: DistProp and MCProp, complex numbers, arrays and linear algebra,
degrees of freedom, distributions other than normal, and the compact binary
serialisation. Nothing here needs them. If the demonstration ever does, the equivalence
test fails on a licensed machine rather than quietly producing a plausible wrong number.
"""

from __future__ import annotations

import math
import os
import xml.etree.ElementTree as ElementTree
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "UncNumber",
    "ufloat",
    "get_value",
    "get_stdunc",
    "get_unc_component",
    "get_covariance",
    "get_correlation",
    "ustorage",
    "use_linprop",
]

#: The XML declaration UncLib writes. It says utf-16 while the string it belongs to is
#: passed around as text and encoded by the caller as UTF-8 (see vc/model.py, which
#: digests it). That is UncLib's behaviour and not a defect to be corrected here: the
#: digests recorded in every credential are taken over exactly these bytes.
_DECLARATION = '<?xml version="1.0" encoding="utf-16"?>'

_ROOT_OPEN = (
    '<UncNumber xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
    ' xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
)

#: .NET's XmlWriter writes CRLF and no trailing newline.
_NEWLINE = "\r\n"


def _format_double(value: float) -> str:
    """Render a float as .NET's round-trip double formatting does.

    UncLib serialises through .NET, whose round-trip format tries fifteen significant
    digits and falls back to seventeen when that does not read back as the same double.
    Python's ``%g`` happens to share .NET's "G" format exactly in the two places that
    would otherwise differ -- when to switch to exponential notation, and how trailing
    zeros are trimmed -- so the only remaining difference is the case of the exponent
    marker. Validated against UncLib over several hundred values, including random bit
    patterns across the whole double range.

    Args:
        value: The number to render.

    Returns:
        The number as .NET would write it.
    """
    for precision in (15, 17):
        text = "%.*g" % (precision, value)
        if float(text) == value:
            break
    return text.replace("e", "E")


def _identifier_bytes(identifier: Any) -> bytes:
    """Normalise the forms an input identifier arrives in to sixteen bytes.

    Args:
        identifier: ``None`` to mint a fresh identifier, sixteen raw bytes, or the four
            little-endian words that
            :func:`vcqi.domain.uncertainty.seeded_input_id` produces.

    Returns:
        The identifier as sixteen bytes.

    Raises:
        TypeError: If the identifier is none of those forms.
        ValueError: If it is the right type but the wrong length.
    """
    if identifier is None:
        # UncLib mints a fresh GUID per input, and so does this. The demonstrator
        # overrides it with a seeded identifier precisely so its output is diffable.
        return os.urandom(16)
    if isinstance(identifier, (bytes, bytearray)):
        if len(identifier) != 16:
            raise ValueError("an input identifier is sixteen bytes")
        return bytes(identifier)
    if isinstance(identifier, Sequence) and not isinstance(identifier, str):
        words = list(identifier)
        if len(words) != 4:
            raise ValueError("an input identifier is four 32 bit words")
        return b"".join(int(word).to_bytes(4, "little") for word in words)
    raise TypeError(f"cannot read {type(identifier).__name__} as an input identifier")


def _format_identifier(identifier: bytes) -> str:
    """Render an identifier as UncLib writes it in XML.

    Args:
        identifier: The sixteen bytes.

    Returns:
        Uppercase hex byte pairs joined by hyphens.
    """
    return "-".join("%02X" % byte for byte in identifier)


def _parse_identifier(text: str) -> bytes:
    """Read an identifier back out of its XML form.

    Args:
        text: Hyphen-separated hex byte pairs.

    Returns:
        The sixteen bytes.
    """
    return bytes(int(part, 16) for part in text.strip().split("-"))


def _number_of(text: str | None) -> float:
    """Read a number out of an element, tolerating an absent one.

    Args:
        text: The element text, or None when the element was missing.

    Returns:
        The value, or 0.0 when there was nothing to read.
    """
    if text is None:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


@dataclass(frozen=True)
class _Input:
    """An independent input quantity: an identity and a normal distribution.

    Attributes:
        identifier: The sixteen byte identity of the physical influence. Every result
            depending on this influence carries this same value, which is what makes
            their correlation computable rather than guessable.
        description: How the influence was described where it was declared.
        mean: Best estimate of the input.
        sigma: The Standard Uncertainty of the input.
    """

    identifier: bytes
    description: str
    mean: float
    sigma: float


class UncNumber:
    """A value together with its sensitivity to every independent input.

    This is the LinProp representation. ``value`` is the best estimate and ``terms``
    maps each input identifier to the partial derivative of the value with respect to
    that input. Arithmetic carries the derivatives forward by the chain rule, so the
    combined Standard Uncertainty is available at any point without differentiating the
    model again, and correlation between two results follows from their sharing an
    identifier.

    ``terms`` is ordered, and its order is the order the inputs serialise in. A number
    with no terms is a constant.
    """

    __slots__ = ("value", "terms", "inputs")

    def __init__(
        self,
        value: float,
        terms: Mapping[bytes, float] | None = None,
        inputs: Mapping[bytes, _Input] | None = None,
    ) -> None:
        """Build an uncertain number from a value and its sensitivities.

        Args:
            value: Best estimate.
            terms: Partial derivative with respect to each input identifier, in the
                order those inputs should be serialised.
            inputs: The declaration of each input the terms refer to.
        """
        self.value = float(value)
        self.terms: dict[bytes, float] = dict(terms or {})
        self.inputs: dict[bytes, _Input] = dict(inputs or {})

    # ---------------------------------------------------------------- arithmetic

    @staticmethod
    def _coerce(other: Any) -> UncNumber:
        """Read a plain number as a constant uncertain number.

        Args:
            other: An uncertain number, or an int or float.

        Returns:
            The operand as an uncertain number.

        Raises:
            TypeError: If it is neither.
        """
        if isinstance(other, UncNumber):
            return other
        if isinstance(other, (int, float)):
            return UncNumber(float(other))
        raise TypeError(f"cannot combine an uncertain number with {type(other).__name__}")

    def _combine(self, other: UncNumber, value: float, own: float, theirs: float) -> UncNumber:
        """Apply the chain rule to two operands.

        Args:
            other: The second operand.
            value: The value of the result.
            own: Partial derivative of the result with respect to this operand.
            theirs: Partial derivative of the result with respect to the other operand.

        Returns:
            The result, carrying the union of both operands' inputs. This operand's
            inputs come first, which is the order UncLib serialises in.
        """
        terms: dict[bytes, float] = {}
        for identifier, sensitivity in self.terms.items():
            terms[identifier] = own * sensitivity
        for identifier, sensitivity in other.terms.items():
            terms[identifier] = terms.get(identifier, 0.0) + theirs * sensitivity
        inputs = dict(self.inputs)
        inputs.update(other.inputs)
        return UncNumber(value, terms, inputs)

    def __add__(self, other: Any) -> UncNumber:
        second = self._coerce(other)
        return self._combine(second, self.value + second.value, 1.0, 1.0)

    def __radd__(self, other: Any) -> UncNumber:
        return self._coerce(other).__add__(self)

    def __sub__(self, other: Any) -> UncNumber:
        second = self._coerce(other)
        return self._combine(second, self.value - second.value, 1.0, -1.0)

    def __rsub__(self, other: Any) -> UncNumber:
        return self._coerce(other).__sub__(self)

    def __mul__(self, other: Any) -> UncNumber:
        second = self._coerce(other)
        return self._combine(second, self.value * second.value, second.value, self.value)

    def __rmul__(self, other: Any) -> UncNumber:
        return self._coerce(other).__mul__(self)

    def __truediv__(self, other: Any) -> UncNumber:
        second = self._coerce(other)
        value = self.value / second.value
        return self._combine(
            second,
            value,
            1.0 / second.value,
            # -(a/b)/b rather than the algebraically identical -a/(b*b): UncLib
            # evaluates it this way and the two differ in the last bit, which would
            # show up as a different Jacobian in the XML and so a different digest.
            -value / second.value,
        )

    def __rtruediv__(self, other: Any) -> UncNumber:
        return self._coerce(other).__truediv__(self)

    def __neg__(self) -> UncNumber:
        return UncNumber(-self.value, {k: -v for k, v in self.terms.items()}, self.inputs)

    def __pos__(self) -> UncNumber:
        return self

    # ---------------------------------------------------------------- reading

    @property
    def standard_uncertainty(self) -> float:
        """Return the combined Standard Uncertainty u.

        Returns:
            The root sum of squares of every input's contribution.
        """
        total = 0.0
        for contribution in self._contributions().values():
            total += contribution * contribution
        return math.sqrt(total)

    def _contributions(self) -> dict[bytes, float]:
        """Return each input's contribution to this number's Standard Uncertainty.

        Returns:
            Sensitivity multiplied by the input's own Standard Uncertainty, per input.
        """
        return {
            identifier: sensitivity * self.inputs[identifier].sigma
            for identifier, sensitivity in self.terms.items()
        }

    def component(self, other: UncNumber) -> float:
        """Return another quantity's contribution to this number's uncertainty.

        For an independent input this is the sensitivity to it multiplied by its own
        Standard Uncertainty. For a composite quantity -- one deserialised from a
        certificate, say -- it is the projection of this number's contribution vector
        onto that quantity's. The two agree when the quantity is a single input, and the
        projection reduces to the quantity's own Standard Uncertainty when this number
        depends on it with unit sensitivity, which is what makes an inherited
        contribution appear in a budget as the parent certificate stated it.

        Args:
            other: The quantity whose contribution is wanted.

        Returns:
            The contribution, in this number's unit, or 0.0 when the other quantity
            carries no uncertainty for this one to inherit. UncLib raises on that case;
            returning zero is the more useful answer and cannot change any budget the
            demonstrator produces, since none of its inputs has zero uncertainty.
        """
        theirs = other._contributions()
        mine = self._contributions()

        # An independent input is the overwhelmingly common case, and for it the
        # projection collapses to a single multiplication. Taking that path rather than
        # the general one is not an optimisation: dividing by sqrt(x*x) loses a bit for
        # some x, and these numbers reach a signed credential, so an avoidable rounding
        # difference is a changed document.
        if len(theirs) == 1:
            (identifier, contribution), = theirs.items()
            if contribution == 0.0:
                return 0.0
            # dot / |theirs| reduces to mine * sign(theirs). Multiplying by a unit
            # magnitude is exact, and it keeps this number's own sign -- a
            # contribution through a negative sensitivity is negative.
            return mine.get(identifier, 0.0) * math.copysign(1.0, contribution)

        variance = sum(value * value for value in theirs.values())
        if variance == 0.0:
            return 0.0
        dot = sum(value * mine.get(identifier, 0.0) for identifier, value in theirs.items())
        # Self-projection is exactly the other quantity's own Standard Uncertainty, and
        # saying so directly avoids dot/sqrt(variance) landing a bit away from it.
        if dot == variance:
            return math.sqrt(variance)
        return dot / math.sqrt(variance)

    def __repr__(self) -> str:
        return f"UncNumber({self.value!r}, u={self.standard_uncertainty!r})"


# ------------------------------------------------------ the metas_unclib-compatible surface


def ufloat(
    value: float,
    standard_uncertainty: float = 0.0,
    idof: float = 0.0,
    id: Any = None,  # noqa: A002 - the name is UncLib's
    desc: str = "",
) -> UncNumber:
    """Declare an independent input quantity, or a constant.

    Args:
        value: Best estimate.
        standard_uncertainty: The Standard Uncertainty u. Zero declares a constant,
            matching UncLib, which writes no dependency for an input that has none.
        idof: Inverse degrees of freedom. Accepted for signature compatibility and
            ignored, because nothing in this demonstrator reads it back.
        id: The identifier, as four little-endian words or sixteen bytes. A fresh
            random identifier is minted when none is given.
        desc: How the influence should be described in a budget.

    Returns:
        The uncertain number.
    """
    if standard_uncertainty == 0.0:
        return UncNumber(value)
    identifier = _identifier_bytes(id)
    declaration = _Input(
        identifier=identifier,
        description=desc,
        mean=float(value),
        sigma=float(standard_uncertainty),
    )
    return UncNumber(value, {identifier: 1.0}, {identifier: declaration})


def get_value(number: Any) -> float:
    """Return the best estimate of an uncertain number.

    Args:
        number: The uncertain number, or a plain number.

    Returns:
        The value.
    """
    if isinstance(number, UncNumber):
        return number.value
    return float(number)


def get_stdunc(number: Any) -> float:
    """Return the combined Standard Uncertainty of an uncertain number.

    Args:
        number: The uncertain number, or a plain number.

    Returns:
        The Standard Uncertainty, zero for a plain number.
    """
    if isinstance(number, UncNumber):
        return number.standard_uncertainty
    return 0.0


def get_unc_component(number: Any, other: Any) -> list[list[float]]:
    """Return one quantity's contribution to another's uncertainty.

    The nesting matches UncLib, whose general form is a matrix over arrays of
    quantities. Callers here index ``[0][0]``.

    Args:
        number: The result.
        other: The quantity whose contribution is wanted.

    Returns:
        The contribution, wrapped in a one by one matrix.
    """
    if not isinstance(number, UncNumber) or not isinstance(other, UncNumber):
        return [[0.0]]
    return [[number.component(other)]]


def get_covariance(numbers: Sequence[Any]) -> list[list[float]]:
    """Return the covariance matrix of several uncertain numbers.

    Two results covary exactly to the extent that they depend on the same inputs, so
    the covariance is the dot product of their contribution vectors. Nothing has to be
    declared about the relationship: it follows from the identifiers.

    Args:
        numbers: The uncertain numbers.

    Returns:
        The symmetric covariance matrix, in row-major order.
    """
    contributions = [
        number._contributions() if isinstance(number, UncNumber) else {} for number in numbers
    ]
    size = len(contributions)
    matrix = [[0.0] * size for _ in range(size)]
    for row in range(size):
        for column in range(row, size):
            mine, theirs = contributions[row], contributions[column]
            # Iterate the smaller vector; the dot product only has terms where both
            # depend on the same input.
            if len(theirs) < len(mine):
                mine, theirs = theirs, mine
            value = sum(
                contribution * theirs.get(identifier, 0.0)
                for identifier, contribution in mine.items()
            )
            matrix[row][column] = matrix[column][row] = value
    return matrix


def get_correlation(numbers: Sequence[Any]) -> list[list[float]]:
    """Return the correlation matrix of several uncertain numbers.

    This is the mechanism behind the claim that two certificates resting on one
    national standard are not independent. Neither certificate says anything about the
    other; they simply name the same input quantity, and the correlation falls out of
    that.

    Args:
        numbers: The uncertain numbers.

    Returns:
        The symmetric correlation matrix, in row-major order. A number with no
        uncertainty correlates with nothing, and its row and column are zero apart
        from a unit diagonal.
    """
    covariance = get_covariance(numbers)
    size = len(covariance)
    deviations = [math.sqrt(covariance[index][index]) for index in range(size)]
    matrix = [[0.0] * size for _ in range(size)]
    for row in range(size):
        for column in range(size):
            if row == column:
                matrix[row][column] = 1.0
            elif deviations[row] > 0.0 and deviations[column] > 0.0:
                matrix[row][column] = covariance[row][column] / (
                    deviations[row] * deviations[column]
                )
    return matrix


def use_linprop(**_: Any) -> None:
    """Select linear propagation, which is the only mode this engine has."""


def _escape(text: str) -> str:
    """Escape text for an XML element body the way .NET's writer does.

    Args:
        text: The text.

    Returns:
        The text with the three markup characters replaced by entities.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class _Storage:
    """The serialisation surface, mirroring ``metas_unclib.ustorage``."""

    @staticmethod
    def to_xml_string(number: UncNumber) -> str:
        """Serialise an uncertain number as METAS UncLib XML.

        The output is byte-identical to UncLib's. That is a requirement rather than a
        nicety: every credential in the demonstration records a digest over these
        bytes, so a merely equivalent document would invalidate all of them.

        Args:
            number: The uncertain number.

        Returns:
            The XML document, CRLF-separated and without a trailing newline.
        """
        lines = [
            _DECLARATION,
            _ROOT_OPEN,
            f"  <Value>{_format_double(number.value)}</Value>",
        ]
        if not number.terms:
            lines.append("  <Dependencies />")
        else:
            lines.append("  <Dependencies>")
            for identifier, sensitivity in number.terms.items():
                declaration = number.inputs[identifier]
                lines += [
                    "    <DependsOn>",
                    "      <Input>",
                    f"        <Id>{_format_identifier(identifier)}</Id>",
                    f"        <Description>{_escape(declaration.description)}</Description>",
                    '        <Distribution xsi:type="Normal">',
                    f"          <mu>{_format_double(declaration.mean)}</mu>",
                    f"          <sigma>{_format_double(declaration.sigma)}</sigma>",
                    "        </Distribution>",
                    "      </Input>",
                    f"      <Jacobi>{_format_double(sensitivity)}</Jacobi>",
                    "    </DependsOn>",
                ]
            lines.append("  </Dependencies>")
        lines.append("</UncNumber>")
        return _NEWLINE.join(lines)

    @staticmethod
    def from_xml_string(text: str) -> UncNumber:
        """Read an uncertain number back from METAS UncLib XML.

        Args:
            text: The XML document.

        Returns:
            The uncertain number, every input keeping the identifier it arrived with so
            that correlations survive the round trip. That is the whole reason a
            certificate carries this document rather than two numbers.

        Raises:
            ValueError: If the document is not an uncertain number.
        """
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError as error:
            raise ValueError(f"could not parse the uncertain number: {error}") from error
        if root.tag != "UncNumber":
            raise ValueError(f"expected an UncNumber document, found {root.tag!r}")

        value_text = root.findtext("./Value")
        if value_text is None:
            raise ValueError("the document states no value")

        terms: dict[bytes, float] = {}
        inputs: dict[bytes, _Input] = {}
        for depends_on in root.iterfind("./Dependencies/DependsOn"):
            node = depends_on.find("./Input")
            if node is None:
                continue
            identifier = _parse_identifier(node.findtext("./Id") or "")
            distribution = node.find("./Distribution")
            mean = sigma = 0.0
            if distribution is not None:
                mean = _number_of(distribution.findtext("./mu"))
                sigma = _number_of(distribution.findtext("./sigma"))
            terms[identifier] = _number_of(depends_on.findtext("./Jacobi"))
            inputs[identifier] = _Input(
                identifier=identifier,
                description=node.findtext("./Description") or "",
                mean=mean,
                sigma=sigma,
            )
        return UncNumber(float(value_text), terms, inputs)

    @staticmethod
    def to_byte_array(number: UncNumber) -> bytes:
        """Refuse the compact binary form, which this engine does not implement.

        UncLib's binary layout is undocumented, so the demonstrator carries blobs
        generated on a licensed machine instead. See :mod:`vcqi.domain.unclib_blobs`.

        Args:
            number: The uncertain number.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            "the compact binary form is produced only by METAS UncLib itself; "
            "the demonstrator carries blobs generated with the 'unclib' extra installed"
        )


#: Mirrors ``metas_unclib.ustorage``.
ustorage = _Storage()
