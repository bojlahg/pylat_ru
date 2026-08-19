"""src/pylat_ru/utils.py

Shared utilities for string handling, regex splitting, and Java compatibility.
"""

from __future__ import annotations

import re


def java_regex_split(pattern: re.Pattern[str], text: str) -> list[str]:
    """Split text by regular expression matching Java Pattern.split(text, 0) semantics.

    Java Pattern.split(text) characteristics preserved:
      1. Capturing groups in pattern are not returned as extra items in the split array.
      2. Trailing empty strings at the end of the split array are discarded.
    """
    result: list[str] = []
    last_end = 0
    for match in pattern.finditer(text):
        result.append(text[last_end : match.start()])
        last_end = match.end()
    result.append(text[last_end:])

    while len(result) > 1 and result[-1] == "":
        result.pop()

    return result
