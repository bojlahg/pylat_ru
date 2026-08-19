"""Roman numeral formatting for LanguageTool synthesis matching Roman.sor."""

from __future__ import annotations

_ROMAN_VALS = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]


def int_to_roman(num: int) -> str:
    """Convert a positive integer to Roman numerals."""
    if num <= 0:
        return str(num)
    res = []
    for val, sym in _ROMAN_VALS:
        while num >= val:
            res.append(sym)
            num -= val
    return "".join(res)


def get_roman_number(num_str: str) -> str:
    """Convert number string to Roman numeral representation matching LanguageTool Roman.sor.

    If the input string cannot be parsed as a positive integer, returns num_str unchanged.
    """
    stripped = num_str.strip()
    if not stripped.isdigit():
        return num_str
    try:
        val = int(stripped)
        if val <= 0:
            return num_str
        return int_to_roman(val)
    except ValueError:
        return num_str
