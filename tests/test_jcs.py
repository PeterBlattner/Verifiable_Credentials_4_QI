"""RFC 8785 conformance tests for the in-repo JSON canonicalizer.

Control characters and backslashes are built with chr() rather than written as literals
so that the expectations state exactly which bytes the canonical form must contain.
"""

from __future__ import annotations

import pytest

from vcqi.crypto.jcs import canonicalize, canonicalize_str, serialize_number

BACKSLASH = chr(0x5C)
QUOTE = chr(0x22)
EURO = chr(0x20AC)

# ECMAScript Number::toString cases, several taken from RFC 8785 appendix B.
NUMBER_CASES = [
    (0.0, "0"),
    (-0.0, "0"),
    (1.0, "1"),
    (4.50, "4.5"),
    (-0.5, "-0.5"),
    (100.0, "100"),
    (2e-3, "0.002"),
    (1e-7, "1e-7"),
    (1e-6, "0.000001"),
    (1e21, "1e+21"),
    (1e20, "100000000000000000000"),
    (1e30, "1e+30"),
    (1e-27, "1e-27"),
    (333333333.33333329, "333333333.3333333"),
    (5e-324, "5e-324"),
    (1.7976931348623157e308, "1.7976931348623157e+308"),
    (9.999999999999997e22, "9.999999999999997e+22"),
]


@pytest.mark.parametrize(("value", "expected"), NUMBER_CASES)
def test_serialize_number(value: float, expected: str) -> None:
    """Doubles serialize exactly as ECMAScript Number::toString would render them."""
    assert serialize_number(value) == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_rejected(value: float) -> None:
    """RFC 8785 has no representation for NaN or infinity."""
    with pytest.raises(ValueError):
        serialize_number(value)


def test_rfc8785_appendix_b_example() -> None:
    """The worked example from RFC 8785 canonicalizes to the published output."""
    tricky = (
        EURO + "$" + chr(0x0F) + chr(0x0A) + "A'B"
        + QUOTE + BACKSLASH + BACKSLASH + QUOTE + "/"
    )
    document = {
        "numbers": [333333333.33333329, 1e30, 4.50, 2e-3, 1e-27],
        "string": tricky,
        "literals": [None, True, False],
    }
    expected = (
        '{"literals":[null,true,false],'
        '"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],'
        '"string":"'
        + EURO + "$"
        + BACKSLASH + "u000f"
        + BACKSLASH + "n"
        + "A'B"
        + BACKSLASH + QUOTE
        + BACKSLASH + BACKSLASH
        + BACKSLASH + BACKSLASH
        + BACKSLASH + QUOTE
        + '/"}'
    )
    assert canonicalize_str(document) == expected


def test_member_ordering_ignores_locale() -> None:
    """Members sort by code unit, not by any language-specific collation."""
    document = {
        "peach": "This sorting order",
        "p" + chr(0xE9) + "ch" + chr(0xE9): "is wrong according to French",
        "p" + chr(0xEA) + "che": "but canonicalization MUST",
        "sin": "ignore locale",
    }
    canonical = canonicalize_str(document)
    names = ["peach", "p" + chr(0xE9) + "ch" + chr(0xE9), "p" + chr(0xEA) + "che", "sin"]
    positions = [canonical.index(QUOTE + name + QUOTE) for name in names]
    assert positions == sorted(positions)


def test_member_ordering_is_by_utf16_code_unit() -> None:
    """Ordering follows UTF-16 code units, which is not the same as code point order.

    U+1F600 is encoded as the surrogate pair D83D DE00, and 0xD83D is below 0xFB00, so
    it sorts before U+FB00 even though its code point is far higher. Sorting Python
    strings directly would put them the other way round.
    """
    astral = chr(0x1F600)
    ligature = chr(0xFB00)
    canonical = canonicalize_str({astral: "emoji", ligature: "ligature"})
    assert canonical.index(astral) < canonical.index(ligature)
    assert sorted([astral, ligature]) == [ligature, astral]


def test_output_is_utf8_bytes_without_whitespace() -> None:
    """Canonical output is compact UTF-8 with no insignificant whitespace."""
    canonical = canonicalize({"b": 1, "a": [1, 2]})
    assert canonical == b'{"a":[1,2],"b":1}'
    assert isinstance(canonical, bytes)


def test_non_ascii_is_not_escaped() -> None:
    """Only the characters JSON requires to be escaped are escaped."""
    text = chr(0xE4) + EURO + chr(0x1F600)
    assert canonicalize_str({"k": text}) == '{"k":"' + text + '"}'


def test_control_characters_use_lowercase_hex() -> None:
    """Control characters without a short escape use lowercase four-digit hex."""
    document = {"k": chr(0x01) + chr(0x1F)}
    expected = '{"k":"' + BACKSLASH + "u0001" + BACKSLASH + "u001f" + '"}'
    assert canonicalize_str(document) == expected


def test_short_escapes_are_preferred() -> None:
    """Backspace, tab, newline, form feed and carriage return use short escapes."""
    document = {"k": chr(0x08) + chr(0x09) + chr(0x0A) + chr(0x0C) + chr(0x0D)}
    expected = '{"k":"' + BACKSLASH.join(["", "b", "t", "n", "f", "r"]) + '"}'
    assert canonicalize_str(document) == expected


def test_integers_are_emitted_exactly() -> None:
    """Integers within the exactly representable range keep their integer form."""
    assert canonicalize_str({"k": 10}) == '{"k":10}'
    assert canonicalize_str({"k": -0}) == '{"k":0}'


def test_oversized_integer_is_rejected() -> None:
    """An integer beyond 2**53 cannot round-trip through a double."""
    with pytest.raises(ValueError):
        canonicalize({"k": 2**53 + 1})


def test_booleans_are_not_treated_as_integers() -> None:
    """bool subclasses int, so it must be matched before the integer branch."""
    assert canonicalize_str({"k": True, "j": False}) == '{"j":false,"k":true}'


def test_non_string_key_is_rejected() -> None:
    """JSON object names are strings; anything else is a programming error."""
    with pytest.raises(ValueError):
        canonicalize({1: "one"})


def test_unsupported_type_is_rejected() -> None:
    """Types with no JSON representation raise rather than serialize approximately."""
    with pytest.raises(TypeError):
        canonicalize({"k": {1, 2}})
