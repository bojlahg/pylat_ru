"""String utility functions matching LanguageTool StringTools case and capitalization behavior."""

from __future__ import annotations


def is_all_uppercase(text: str) -> bool:
    """Check if all alphabetic characters in text are uppercase (or if text contains no lowercase letters).

    Matches Java StringTools.isAllUppercase(String).
    """
    for c in text:
        if c.isalpha() and c.islower():
            return False
    return True


def is_not_all_lowercase(text: str) -> bool:
    """Check if text contains at least one alphabetic character that is not lowercase.

    Matches Java StringTools.isNotAllLowercase(String).
    """
    for c in text:
        if c.isalpha() and not c.islower():
            return True
    return False


def is_capitalized_word(text: str) -> bool:
    """Check if the first character is uppercase and all remaining alphabetic characters are lowercase.

    Matches Java StringTools.isCapitalizedWord(String).
    """
    if not text:
        return False
    if not text[0].isupper():
        return False
    for c in text[1:]:
        if c.isalpha() and not c.islower():
            return False
    return True


def is_mixed_case(text: str) -> bool:
    """Check if a word has mixed casing (i.e. neither all-uppercase, nor capitalized word, nor all-lowercase).

    Matches Java StringTools.isMixedCase(String).
    Examples:
        'слово' -> False
        'Слово' -> False
        'СЛОВО' -> False
        'мИкс' -> True
        'СлоВо' -> True
        'iPod' -> True
    """
    return (
        not is_all_uppercase(text)
        and not is_capitalized_word(text)
        and is_not_all_lowercase(text)
    )


def change_first_char_case(text: str, uppercase: bool) -> str:
    """Change the case of the first letter or digit in text.

    Scans forward past leading non-alphanumeric characters (such as quotes or brackets).
    Matches Java StringTools.changeFirstCharCase(String, boolean).
    """
    if not text:
        return text
    if len(text) == 1:
        return text.upper() if uppercase else text.lower()

    i = 0
    last = len(text) - 1
    while i < last and not text[i].isalnum():
        i += 1

    c = text[i]
    new_c = c.upper() if uppercase else c.lower()
    return text[:i] + new_c + text[i + 1 :]


def uppercase_first_char(text: str) -> str:
    """Change the first letter/digit in text to uppercase.

    Matches Java StringTools.uppercaseFirstChar(String).
    """
    return change_first_char_case(text, uppercase=True)


def lowercase_first_char(text: str) -> str:
    """Change the first letter/digit in text to lowercase.

    Matches Java StringTools.lowercaseFirstChar(String).
    """
    return change_first_char_case(text, uppercase=False)
