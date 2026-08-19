"""tests/unit/test_grammar_engine_core.py

Unit tests for GrammarLoader, Pattern matcher, TemplateFormatter,
and RussianGrammarEngine core execution.
"""

from __future__ import annotations

import pytest

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.classifier import classify_rule_element
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.errors import (
    GrammarError,
    GrammarFormatError,
    UnsupportedGrammarFeatureError,
)
from pylat_ru.grammar.formatter import TemplateFormatter
from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.matcher import CompiledPattern
from pylat_ru.grammar.model import (
    ExecutionState,
    GrammarRule,
    MatchReference,
    MessageTemplate,
    Pattern,
    PatternToken,
    PatternTokenException,
    SuggestionTemplate,
)


def _make_reading(token: str, pos_tag: str | None = None, lemma: str | None = None) -> AnalyzedTokenReadings:
    at = AnalyzedToken(token=token, lemma=lemma or token, pos_tag=pos_tag)
    return AnalyzedTokenReadings(readings=[at], start_pos=0)


def test_grammar_loader_default():
    """Verify loading packaged grammar.xml produces 892 total rules and 506 core runnable rules."""
    import hashlib
    from pathlib import Path
    
    xml_path = Path(__file__).resolve().parent.parent.parent / "src" / "pylat_ru" / "resources" / "rules" / "ru" / "grammar.xml"
    assert xml_path.is_file()
    sha = hashlib.sha256(xml_path.read_bytes()).hexdigest()
    assert sha == "e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec"

    loader = GrammarLoader()
    rules = loader.load_default()
    assert len(rules) == 892

    core_rules = [r for r in rules if r.execution_state == ExecutionState.CORE_0007_RUNNABLE]
    assert len(core_rules) == 506

    # Verify all rules have valid fields
    for r in rules:
        assert r.id
        assert r.full_id
        assert r.category_id
        assert r.category_name
        assert isinstance(r.default_off, bool)


def test_pattern_token_matching_text_and_pos():
    """Verify CompiledPattern matching with literal text and POS tags."""
    tok1 = PatternToken(text="тест", case_sensitive=False)
    tok2 = PatternToken(postag="NN:.*", postag_regexp=True)
    pat = Pattern(tokens=[tok1, tok2])
    compiled = CompiledPattern(pat)

    atr1 = _make_reading("Тест", "NN:Inanim:Masc:Sin:Nom")
    atr2 = _make_reading("программы", "NN:Inanim:Fem:Sin:R")
    atr3 = _make_reading("работает", "VB:Pres:Sin")

    # Match at index 0
    res = compiled.match_at([atr1, atr2, atr3], 0)
    assert res is not None
    match_start, match_end, err_start, err_end = res
    assert (match_start, match_end) == (0, 2)
    assert (err_start, err_end) == (0, 2)

    # No match at index 1
    res2 = compiled.match_at([atr1, atr2, atr3], 1)
    assert res2 is None


def test_pattern_token_exceptions():
    """Verify exception predicates exclude matching readings."""
    exc = PatternTokenException(text="исключение", case_sensitive=False)
    tok = PatternToken(postag="NN:.*", postag_regexp=True, exceptions=[exc])
    pat = Pattern(tokens=[tok])
    compiled = CompiledPattern(pat)

    atr_normal = _make_reading("слово", "NN:Inanim:Neut:Sin:Nom")
    atr_exc = _make_reading("исключение", "NN:Inanim:Neut:Sin:Nom")

    assert compiled.match_at([atr_normal], 0) is not None
    assert compiled.match_at([atr_exc], 0) is None


def test_pattern_marker_spans():
    """Verify marker defines error span distinct from total matched tokens."""
    tok1 = PatternToken(text="в")
    tok2 = PatternToken(text="течении", is_in_marker=True)
    tok3 = PatternToken(text="дня", is_in_marker=True)
    pat = Pattern(tokens=[tok1, tok2, tok3], has_marker=True, marker_start_idx=1, marker_end_idx=3)
    compiled = CompiledPattern(pat)

    atr1 = _make_reading("в")
    atr2 = _make_reading("течении")
    atr3 = _make_reading("дня")

    res = compiled.match_at([atr1, atr2, atr3], 0)
    assert res is not None
    match_start, match_end, err_start, err_end = res
    assert (match_start, match_end) == (0, 3)
    assert (err_start, err_end) == (1, 3)


def test_template_formatter_message_and_suggestion():
    """Verify template formatting with <match no="X"> references and capitalization."""
    msg_tmpl = MessageTemplate(
        elements=["Ошибка в слове: <suggestion>", MatchReference(no=1), " ", MatchReference(no=2), "</suggestion>."]
    )
    sug_tmpl = SuggestionTemplate(elements=[MatchReference(no=1), " ", MatchReference(no=2)])

    atr1 = _make_reading("Большой")
    atr2 = _make_reading("дом")

    msg = TemplateFormatter.format_message(msg_tmpl, [atr1, atr2])
    assert msg == "Ошибка в слове: <suggestion>Большой дом</suggestion>."

    sug = TemplateFormatter.format_suggestion(sug_tmpl, [atr1, atr2], [atr1, atr2])
    assert sug == "Большой дом"


def test_grammar_engine_execution_and_disabling():
    """Verify RussianGrammarEngine rule checking, enabling, and disabling."""
    disambiguator = RussianHybridDisambiguator.get_instance()
    engine = RussianGrammarEngine.get_instance()

    sent = disambiguator.disambiguate_text("Ученик решил задать тест учителю.")
    sent.text = "Ученик решил задать тест учителю."

    # Check rule
    matches = engine.check_rule(sent, "zadat_test")
    assert len(matches) == 1
    m = matches[0]
    assert m.rule_id == "zadat_test"
    assert m.from_pos == 13
    assert m.to_pos == 24

    # Disable rule and verify check_sentence ignores it
    engine.disable_rule("zadat_test")
    assert not engine.is_rule_enabled("zadat_test")
    matches_all = engine.check_sentence(sent, include_disabled=False)
    assert not any(x.rule_id == "zadat_test" for x in matches_all)

    # Re-enable rule
    engine.enable_rule("zadat_test")
    assert engine.is_rule_enabled("zadat_test")
    matches_all_re = engine.check_sentence(sent, include_disabled=False)
    assert any(x.rule_id == "zadat_test" for x in matches_all_re)


def test_grammar_engine_deferred_rule_fail_closed():
    """Verify attempting to run a deferred rule raises UnsupportedGrammarFeatureError."""
    engine = RussianGrammarEngine.get_instance()
    disambiguator = RussianHybridDisambiguator.get_instance()
    sent = disambiguator.disambiguate_text("Тестовое предложение.")

    # Find any deferred rule
    deferred_rule = next(r for r in engine.get_all_rules() if r.execution_state != ExecutionState.CORE_0007_RUNNABLE)
    with pytest.raises(UnsupportedGrammarFeatureError):
        engine.check_rule(sent, deferred_rule)
