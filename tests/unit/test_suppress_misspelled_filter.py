"""Tests for RussianSuppressMisspelledSuggestionsFilter and suppress_misspelled markup."""

from __future__ import annotations

import pytest

from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.filters.base import FilterIllegalArgumentError
from pylat_ru.grammar.filters.registry import get_filter_instance
from pylat_ru.grammar.model import ExecutionState, RuleMatchResult


FILTER_CLASS = "org.languagetool.rules.ru.RussianSuppressMisspelledSuggestionsFilter"


def _match(suggestions: list[str]) -> RuleMatchResult:
    return RuleMatchResult(
        rule_id="TEST_RULE",
        full_rule_id="TEST_RULE[1]",
        category_id="GRAMMAR",
        category_name="Грамматика",
        description="test",
        message="msg",
        short_message="short",
        suggestions=list(suggestions),
        from_pos=0,
        to_pos=1,
        from_pos_utf16=0,
        to_pos_utf16=1,
        pattern_from_pos=0,
        pattern_to_pos=1,
        pattern_from_pos_utf16=0,
        pattern_to_pos_utf16=1,
        matched_tokens_indices=[0],
        marker_tokens_indices=[0],
    )


def _run(suggestions: list[str], args: dict[str, str]):
    return get_filter_instance(FILTER_CLASS).accept_rule_match(
        _match(suggestions), args, 0, [], []
    )


def test_all_replacements_valid_are_kept() -> None:
    result = _run(["слово", "дом"], {"suppressMatch": "true"})
    assert result is not None
    assert result.suggestions == ["слово", "дом"]


def test_misspelled_replacement_is_dropped() -> None:
    result = _run(["слово", "ыфвацй"], {"suppressMatch": "true"})
    assert result is not None
    assert result.suggestions == ["слово"]


def test_all_misspelled_with_suppress_match_true_removes_the_match() -> None:
    assert _run(["ыфвацй", "жщшгн"], {"suppressMatch": "true"}) is None


def test_all_misspelled_with_suppress_match_false_keeps_an_empty_match() -> None:
    result = _run(["ыфвацй", "жщшгн"], {"suppressMatch": "false"})
    assert result is not None
    assert result.suggestions == []


def test_suppress_match_comparison_ignores_case() -> None:
    assert _run(["ыфвацй"], {"suppressMatch": "FALSE"}) is not None
    assert _run(["ыфвацй"], {"suppressMatch": "False"}) is not None
    # Anything that is not literally "false" suppresses.
    assert _run(["ыфвацй"], {"suppressMatch": "no"}) is None


def test_suppress_match_argument_is_required() -> None:
    with pytest.raises(FilterIllegalArgumentError):
        _run(["слово"], {})


def test_suppress_postag_removes_matching_candidates() -> None:
    result = _run(["дом", "быстро"], {"suppressMatch": "true", "SuppressPostag": "ADV.*"})
    assert result is not None
    assert result.suggestions == ["дом"]


def test_suppress_postag_removing_all_candidates_suppresses_the_match() -> None:
    assert _run(["быстро"], {"suppressMatch": "true", "SuppressPostag": "ADV.*"}) is None


def test_suppress_postag_key_is_case_sensitive() -> None:
    # Only the exact "SuppressPostag" spelling is read by the pinned filter.
    result = _run(["быстро"], {"suppressMatch": "true", "suppresspostag": "ADV.*"})
    assert result is not None
    assert result.suggestions == ["быстро"]


def test_multi_token_replacement_is_misspelled_if_any_token_is() -> None:
    result = _run(["новый дом", "новый ыфвацй"], {"suppressMatch": "true"})
    assert result is not None
    assert result.suggestions == ["новый дом"]


def test_non_bmp_prefix_preserves_offsets() -> None:
    text = "😀 Сегодня на ужин жареная на масле картошка."
    engine = RussianGrammarEngine.get_instance()
    sentence = RussianHybridDisambiguator.get_instance().disambiguate_text(text)
    sentence.text = text
    matches = engine.check_rule(sentence, "NN_N_pril_prich[1]")
    assert len(matches) == 1
    assert text[matches[0].from_pos:matches[0].to_pos] == "жареная"
    assert matches[0].from_pos_utf16 == matches[0].from_pos + 1
    assert list(matches[0].suggestions) == ["жаренная"]


def test_real_grammar_rule_uses_the_filter_and_is_runnable() -> None:
    engine = RussianGrammarEngine.get_instance()
    rule = engine.get_rule("NN_N_pril_prich[1]")
    assert rule.execution_state == ExecutionState.FILTER_0010_RUNNABLE
    assert [f.class_name for f in rule.filters] == [FILTER_CLASS]
    assert rule.filters[0].args == "suppressMatch:true"


def test_message_level_suppress_misspelled_drops_the_whole_match() -> None:
    """A suppress_misspelled message with no surviving suggestion yields no match."""
    engine = RussianGrammarEngine.get_instance()
    disambiguator = RussianHybridDisambiguator.get_instance()

    good = "более умнее"
    sentence = disambiguator.disambiguate_text(good)
    sentence.text = good
    matches = engine.check_rule(sentence, "grammar_bolee_interesnee")
    assert [list(m.suggestions) for m in matches] == [
        ["более умная", "более умное", "более умные", "более умный"]
    ]

    quiet = "Раньше в этом регионе."
    sentence = disambiguator.disambiguate_text(quiet)
    sentence.text = quiet
    assert engine.check_rule(sentence, "NN_N_pril_prich[2]") == []
