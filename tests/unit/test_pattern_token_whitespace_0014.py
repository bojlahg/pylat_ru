"""Task 0014 - pinned pattern-token whitespace normalisation.

Discovered by the Task-0014 differential campaign: a rule whose regular-expression
alternation is written across several indented XML lines lost every alternative that
began a line, because ``pylat_ru`` kept the raw text where pinned LanguageTool
normalises it.

Upstream evidence, ``org.languagetool.rules.patterns.PatternToken``::

    public void setStringElement(String token) {
      setTextMatcher(StringMatcher.create(normalizeTextPattern(token), ...));
    }

    static String normalizeTextPattern(String token) {
      return token == null ? "" : StringTools.trimWhitespace(token);
    }

``StringTools.trimWhitespace`` trims the ends, collapses runs of characters at or below
U+0020, and drops line feeds, tabs and carriage returns.  A *single* interior space is
kept; a run of two or more disappears entirely.

These tests are Java-free.
"""

from __future__ import annotations

import pytest

from pylat_ru import LanguageToolRU
from pylat_ru.grammar import RussianGrammarEngine
from pylat_ru.tagging.string_tools import java_trim, trim_whitespace


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("plain", "plain"),
        ("  padded  ", "padded"),
        ("hello world", "hello world"),
        ("hello  world", "helloworld"),
        ("hello   world", "helloworld"),
        ("a|b|\n                    c|d", "a|b|c|d"),
        ("a\tb", "ab"),
        ("a\r\nb", "ab"),
        ("   ", ""),
        ("", ""),
    ],
)
def test_trim_whitespace_matches_pinned_semantics(raw: str, expected: str) -> None:
    assert trim_whitespace(raw) == expected


def test_java_trim_keeps_characters_above_u0020() -> None:
    """``String.trim`` cuts at U+0020; Python's ``strip`` would also eat NBSP."""
    assert java_trim(" x ") == " x "
    assert " x ".strip() == "x"
    assert java_trim(" \t\nx\n\t ") == "x"


def test_multiline_alternation_keeps_every_alternative() -> None:
    """``OPREDELENIA`` writes its alternation across indented lines."""
    engine = RussianGrammarEngine.get_instance()
    variants = engine._compiled_variants["OPREDELENIA[1]"]
    assert variants
    for variant in variants:
        for token in variant.tokens:
            if not token.text:
                continue
            alternatives = token.text.split("|")
            assert all(
                alternative == alternative.strip() for alternative in alternatives
            ), token.text
            assert "которое" in alternatives
            assert "котором" in alternatives


def test_rule_matches_an_alternative_written_at_a_line_start() -> None:
    """The end-to-end symptom: ``котором`` began an XML line and never matched."""
    tool = LanguageToolRU()
    text = "Слово, на которое любят ссылаться, и барельеф, на котором некий человек."
    matches = [m for m in tool.check(text) if m.rule_id == "OPREDELENIA"]
    assert [(m.offset, m.length) for m in matches] == [(10, 47)]


def test_rule_still_matches_alternatives_written_mid_line() -> None:
    tool = LanguageToolRU()
    text = "Они пошли к реке, по которой плавала лодка, которая была окрашена в белый цвет."
    matches = [m for m in tool.check(text) if m.rule_id == "OPREDELENIA"]
    assert [(m.offset, m.length) for m in matches] == [(21, 30)]
