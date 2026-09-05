"""RFC 8785 JSON Canonicalization Scheme (JCS).

Implemented in-repo rather than taken as a dependency so that the whole signing path
stays inspectable in a demonstrator whose purpose is to explain how a signature is
formed.

The canonical form is what actually gets hashed and signed, so every rule here is
load-bearing:

* object members are sorted by the UTF-16 code units of their names;
* no insignificant whitespace is emitted;
* strings use the shortest legal JSON escaping and are emitted as UTF-8;
* numbers use the ECMAScript Number::toString representation.
"""

from __future__ import annotations

import math
from typing import Any

__all__ = ["canonicalize", "canonicalize_str", "serialize_number"]

_BACKSLASH = chr(0x5C)

# Characters that have a short escape in JSON. The values are the two-character
# escape sequences themselves, built with chr() so that the source is unambiguous
# about which bytes end up in the canonical form.
_SHORT_ESCAPES = {
    0x08: _BACKSLASH + "b",
    0x09: _BACKSLASH + "t",
    0x0A: _BACKSLASH + "n",
    0x0C: _BACKSLASH + "f",
    0x0D: _BACKSLASH + "r",
    0x22: _BACKSLASH + chr(0x22),
    0x5C: _BACKSLASH + _BACKSLASH,
}

# Above 2**53 an int is no longer exactly representable as an IEEE-754 double, so it
# cannot be canonicalized without silently changing its value.
_MAX_EXACT_INT = 9007199254740992


def canonicalize(value: Any) -> bytes:
    """Return the RFC 8785 canonical UTF-8 encoding of a JSON-compatible value.

    Args:
        value: A value built only from dict, list, str, int, float, bool and None.

    Returns:
        The canonical serialization as UTF-8 bytes.

    Raises:
        ValueError: If the value contains a non-finite float, an integer too large to
            be represented exactly as a double, or a non-string object key.
        TypeError: If the value contains a type with no JSON representation.
    """
    out: list[str] = []
    _write(value, out)
    return "".join(out).encode("utf-8")


def canonicalize_str(value: Any) -> str:
    """Return the RFC 8785 canonical form as a string.

    Args:
        value: A JSON-compatible value, as for canonicalize().

    Returns:
        The canonical serialization. Convenient for display; canonicalize() returns the
        bytes that are actually hashed.
    """
    return canonicalize(value).decode("utf-8")


def _write(value: Any, out: list[str]) -> None:
    """Append the canonical form of a value to an output accumulator.

    Args:
        value: The value to serialize.
        out: Accumulator of output fragments, mutated in place.
    """
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, str):
        out.append(_serialize_string(value))
    elif isinstance(value, int):
        # bool is a subclass of int and is already handled above.
        if abs(value) > _MAX_EXACT_INT:
            raise ValueError(
                f"integer {value} cannot be canonicalized exactly as a double"
            )
        out.append(str(value))
    elif isinstance(value, float):
        out.append(serialize_number(value))
    elif isinstance(value, dict):
        _write_object(value, out)
    elif isinstance(value, (list, tuple)):
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(",")
            _write(item, out)
        out.append("]")
    else:
        raise TypeError(f"{type(value).__name__} is not JSON-serializable")


def _write_object(value: dict[Any, Any], out: list[str]) -> None:
    """Append the canonical form of a JSON object to an output accumulator.

    Args:
        value: The mapping to serialize. Keys must be strings.
        out: Accumulator of output fragments, mutated in place.
    """
    for key in value:
        if not isinstance(key, str):
            raise ValueError(f"object key must be a string, got {type(key).__name__}")
    # RFC 8785 orders members by UTF-16 code unit. Python compares by code point, which
    # differs for astral characters, so compare the actual UTF-16 encoding instead.
    out.append("{")
    for index, key in enumerate(sorted(value, key=lambda k: k.encode("utf-16-be"))):
        if index:
            out.append(",")
        out.append(_serialize_string(key))
        out.append(":")
        _write(value[key], out)
    out.append("}")


def _serialize_string(value: str) -> str:
    """Return the canonical JSON string literal for a string.

    Non-ASCII characters are emitted literally; only the characters JSON requires to be
    escaped are escaped, and control characters without a short escape use lowercase
    four-digit hex.

    Args:
        value: The string to serialize.

    Returns:
        The quoted, escaped string literal.
    """
    out = [chr(0x22)]
    for char in value:
        code = ord(char)
        short = _SHORT_ESCAPES.get(code)
        if short is not None:
            out.append(short)
        elif code < 0x20:
            out.append(_BACKSLASH + f"u{code:04x}")
        else:
            out.append(char)
    out.append(chr(0x22))
    return "".join(out)


def serialize_number(value: float) -> str:
    """Return the ECMAScript Number::toString representation of a double.

    This is the representation RFC 8785 mandates for JSON numbers: the shortest decimal
    string that round-trips, written as a plain decimal when the decimal exponent lies
    in the range ECMAScript uses for plain notation, and in exponential form otherwise.

    Args:
        value: A finite float.

    Returns:
        The canonical decimal representation, for example "4.5", "0.002", "1e+30" or
        "5e-324".

    Raises:
        ValueError: If the value is NaN or infinite, neither of which RFC 8785 permits.
    """
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"{value!r} has no JSON representation")
    if value == 0.0:
        # Canonicalization erases the sign of negative zero.
        return "0"

    sign = "-" if value < 0 else ""
    digits, exponent = _decompose(abs(value))
    length = len(digits)

    if length <= exponent <= 21:
        # Integral value that fits without an exponent, for example 100.
        return sign + digits + "0" * (exponent - length)
    if 0 < exponent <= 21:
        # Decimal point falls inside the digits, for example 4.5.
        return sign + digits[:exponent] + "." + digits[exponent:]
    if -6 < exponent <= 0:
        # Leading zeros after the point, for example 0.002.
        return sign + "0." + "0" * (-exponent) + digits
    # Exponential form. ECMAScript reports the exponent relative to the first digit.
    power = exponent - 1
    mantissa = digits if length == 1 else digits[0] + "." + digits[1:]
    marker = "e+" if power >= 0 else "e-"
    return sign + mantissa + marker + str(abs(power))


def _decompose(value: float) -> tuple[str, int]:
    """Split a positive double into its shortest round-tripping digits and exponent.

    Args:
        value: A positive, finite float.

    Returns:
        A tuple (digits, exponent) such that the value equals
        int(digits) * 10 ** (exponent - len(digits)), where digits carries no leading
        or trailing zeros.
    """
    text = repr(value)
    mantissa, _, exponent_text = text.partition("e")
    exponent = int(exponent_text) if exponent_text else 0
    integer_part, _, fraction_part = mantissa.partition(".")

    all_digits = integer_part + fraction_part
    significant = all_digits.lstrip("0")
    trimmed = significant.rstrip("0") or "0"
    dropped_trailing = len(significant) - len(trimmed)

    power = exponent - len(fraction_part) + dropped_trailing
    return trimmed, power + len(trimmed)
