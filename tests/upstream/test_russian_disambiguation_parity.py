"""Upstream parity tests verifying all examples in Russian disambiguation.xml."""

from __future__ import annotations

import re
from typing import List

import pytest

from pylat_ru.analysis import AnalyzedSentence, AnalyzedTokenReadings
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.disambiguation.rules import DisambiguationPatternRuleReplacer
from pylat_ru.disambiguation.xml_loader import DisambiguationRuleLoader


def clean_xml_markers(text: str) -> tuple[str, int, int]:
    """Extract marker start and end character positions, and return clean text."""
    if "<marker>" in text and "</marker>" in text:
        marker_start = text.find("<marker>")
        text_without_start = text.replace("<marker>", "", 1)
        marker_end = text_without_start.find("</marker>")
        clean_text = text_without_start.replace("</marker>", "", 1)
        return clean_text, marker_start, marker_end
    return text, -1, -1


def test_upstream_disambiguation_xml_all_examples_parity() -> None:
    """Verify all ambiguous and untouched examples in disambiguation.xml pass exact parity."""
    hybrid = RussianHybridDisambiguator.get_instance()
    loader = DisambiguationRuleLoader(tagger=hybrid.tagger)
    rules = loader.parse_file("src/pylat_ru/resources/ru/disambiguation.xml")

    replacers = [DisambiguationPatternRuleReplacer(r) for r in rules]

    for rule_idx, rule in enumerate(rules):
        # 1. Test ambiguous examples
        for ex in rule.examples:
            clean_text, match_start, match_end = clean_xml_markers(ex.example)

            # Create raw analyzed sentence
            raw_sent = hybrid.create_analyzed_sentence(clean_text)

            # Run previous rules up to this rule
            curr_sent = raw_sent
            for prev_idx in range(rule_idx):
                curr_sent = replacers[prev_idx].replace(curr_sent)

            # Apply target rule
            disambiguated_sent = replacers[rule_idx].replace(curr_sent)

            # Locate the marked token in sentence
            target_token_before = None
            target_token_after = None

            for t in curr_sent.get_tokens():
                if not t.is_sentence_start and match_start != -1 and t.start_pos == match_start:
                    target_token_before = t
                    break

            for t in disambiguated_sent.get_tokens():
                if not t.is_sentence_start and match_start != -1 and t.start_pos == match_start:
                    target_token_after = t
                    break

            if ex.output_form:
                assert target_token_after is not None, f"Rule {rule.id}: token at offset {match_start} not found in '{clean_text}'"
                actual_output = target_token_after.to_short_string()
                assert actual_output == ex.output_form, (
                    f"Rule '{rule.id}' output mismatch for '{ex.example}':\n"
                    f"  Expected: {ex.output_form}\n"
                    f"  Actual:   {actual_output}"
                )

        # 2. Test untouched examples
        for untouched_text in rule.untouched_examples:
            clean_text, _, _ = clean_xml_markers(untouched_text)
            raw_sent = hybrid.create_analyzed_sentence(clean_text)

            curr_sent = raw_sent
            for prev_idx in range(rule_idx):
                curr_sent = replacers[prev_idx].replace(curr_sent)

            disambiguated_sent = replacers[rule_idx].replace(curr_sent)
            assert curr_sent.to_string() == disambiguated_sent.to_string(), (
                f"Rule '{rule.id}' touched untouched example '{untouched_text}'"
            )


def test_upstream_disambiguation_end_to_end_examples() -> None:
    """Verify end-to-end RussianHybridDisambiguator on all official disambiguation examples."""
    disambiguator = RussianHybridDisambiguator.get_instance()

    cases = [
        ("73 процента", "73", "NumD_D"),
        ("71 процент", "71", "NumD_S"),
        ("75 процентов", "75", "NumD_P"),
        ("11 процентов", "11", "NumD_P"),
        ("12 процентов", "12", "NumD_P"),
        ("Ваня, дай-ка мне этот молоток.", "дай-ка", "VB:IMP:TRANS:PFV:Sin:P2"),
        ("Ваня, пой-ка эту песню!", "пой-ка", "VB:IMP:TRANS:IMPFV:Sin:P2"),
        ("Ваня, прыгай-ка сюда быстрее!", "прыгай-ка", "VB:IMP:INTR:IMPFV:Sin:P2"),
    ]

    for text, word, tag in cases:
        sentence = disambiguator.disambiguate_text(text)
        token = next((t for t in sentence.get_tokens() if t.token == word), None)
        assert token is not None, f"Token '{word}' not found in '{text}'"
        assert token.has_pos_tag(tag), f"Token '{word}' missing POS tag '{tag}', got: {[str(r) for r in token.readings]}"
