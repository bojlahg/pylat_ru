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
    deferred_rule = next(
        r for r in engine.get_all_rules()
        if r.execution_state not in (ExecutionState.CORE_0007_RUNNABLE, ExecutionState.ADVANCED_0008_RUNNABLE)
    )
    with pytest.raises(UnsupportedGrammarFeatureError):
        engine.check_rule(sent, deferred_rule)


def test_grammar_engine_emoji_and_non_bmp_offsets():
    """Verify separate Python codepoint and Java UTF-16 offsets with non-BMP emoji."""
    disambiguator = RussianHybridDisambiguator.get_instance()
    engine = RussianGrammarEngine.get_instance()

    # Case 1: Non-BMP emoji before match
    text_before = "🚀 Ученик решил задать тест учителю."
    sent_before = disambiguator.disambiguate_text(text_before)
    sent_before.text = text_before

    matches1 = engine.check_rule(sent_before, "zadat_test")
    assert len(matches1) == 1
    m1 = matches1[0]

    # Codepoint slice matches exact error substring
    assert text_before[m1.from_pos:m1.to_pos] == "задать тест"
    # Codepoint offset is 15..26 (1 emoji + 1 space + 13 chars)
    assert m1.from_pos == 15
    assert m1.to_pos == 26
    # UTF-16 code units offset is 16..27 (2 surrogate units + 1 space + 13 chars)
    assert m1.from_pos_utf16 == 16
    assert m1.to_pos_utf16 == 27
    assert m1.pattern_from_pos == 15
    assert m1.pattern_to_pos == 26

    # Case 2: Full pattern span vs marker span
    pat = Pattern(
        tokens=[
            PatternToken(text="решил"),
            PatternToken(text="задать", is_in_marker=True),
            PatternToken(text="тест", is_in_marker=True),
        ],
        has_marker=True,
        marker_start_idx=1,
        marker_end_idx=3,
    )
    rule = GrammarRule(
        id="custom_marker_test",
        sub_id="1",
        full_id="custom_marker_test[1]",
        name="Custom Marker Test",
        category_id="TEST",
        category_name="Test",
        rulegroup_id=None,
        rulegroup_name=None,
        default_off=False,
        tags=[],
        source_order_index=0,
        pattern=pat,
        antipatterns=[],
        filters=[],
        unifications=[],
        message_template=MessageTemplate(elements=["Error"]),
        short_message=None,
        suggestions=[],
        examples=[],
        url=None,
        rule_type=None,
        prio=None,
        tone_tags=[],
        is_goal_specific=False,
        execution_state=ExecutionState.CORE_0007_RUNNABLE,
        blockers=[],
    )
    custom_engine = RussianGrammarEngine(rules=[rule])
    matches2 = custom_engine.check_rule(sent_before, rule)
    assert len(matches2) == 1
    m2 = matches2[0]
    # Marker span: "задать тест"
    assert text_before[m2.from_pos:m2.to_pos] == "задать тест"
    assert m2.from_pos == 15
    assert m2.to_pos == 26
    # Pattern span: "решил задать тест"
    assert text_before[m2.pattern_from_pos:m2.pattern_to_pos] == "решил задать тест"
    assert m2.pattern_from_pos == 9
    assert m2.pattern_to_pos == 26
    assert m2.pattern_from_pos_utf16 == 10
    assert m2.pattern_to_pos_utf16 == 27


def test_grammar_loader_strict_fail_closed_contexts():
    """Verify GrammarLoader fail-closed validation across all element contexts."""
    loader = GrammarLoader()

    # Disallowed child in <rules>
    with pytest.raises(GrammarFormatError, match="Disallowed child <bad_tag> inside <rules>"):
        loader.load_from_string("<rules lang='ru'><bad_tag/></rules>")

    # Disallowed child in <rulegroup>
    with pytest.raises(GrammarFormatError, match="Disallowed child <token> inside <rulegroup>"):
        loader.load_from_string("<rules lang='ru'><category id='C'><rulegroup id='G'><token/></rulegroup></category></rules>")

    # Disallowed child in <pattern>
    with pytest.raises(GrammarFormatError, match="Disallowed child <message> inside <pattern>"):
        loader.load_from_string("<rules lang='ru'><category id='C'><rule id='R'><pattern><message/></pattern><message>m</message></rule></category></rules>")

    # Disallowed child in <marker>
    with pytest.raises(GrammarFormatError, match="Disallowed child <marker> inside <marker>"):
        loader.load_from_string("<rules lang='ru'><category id='C'><rule id='R'><pattern><marker><marker/></marker></pattern><message>m</message></rule></category></rules>")

    # Disallowed child in <message>
    with pytest.raises(GrammarFormatError, match="Disallowed child <token> inside <message>"):
        loader.load_from_string("<rules lang='ru'><category id='C'><rule id='R'><pattern><token>a</token></pattern><message>m <token/></message></rule></category></rules>")

    # Disallowed child in <suggestion>
    with pytest.raises(GrammarFormatError, match="Disallowed child <pattern> inside <suggestion>"):
        loader.load_from_string("<rules lang='ru'><category id='C'><rule id='R'><pattern><token>a</token></pattern><message><suggestion><pattern/></suggestion></message></rule></category></rules>")

    # Disallowed attribute on <match>
    with pytest.raises(GrammarFormatError, match="Unknown attribute 'bad_match_attr' on <match>"):
        loader.load_from_string("<rules lang='ru'><category id='C'><rule id='R'><pattern><token>a</token></pattern><message><suggestion><match no='1' bad_match_attr='v'/></suggestion></message></rule></category></rules>")

    # Disallowed attribute on <antipattern>
    with pytest.raises(GrammarFormatError, match="Unknown attribute 'bad_anti_attr' on <antipattern>"):
        loader.load_from_string("<rules lang='ru'><category id='C'><rule id='R'><antipattern bad_anti_attr='v'><token>a</token></antipattern><pattern><token>a</token></pattern><message>m</message></rule></category></rules>")

    # Disallowed attribute on <token>
    with pytest.raises(GrammarFormatError, match="Unknown attribute 'invalid_attr' on <token>"):
        loader.load_from_string("<rules lang='ru'><category id='C'><rule id='R'><pattern><token invalid_attr='true'>a</token></pattern><message>m</message></rule></category></rules>")

    # Disallowed attribute on <exception>
    with pytest.raises(GrammarFormatError, match="Unknown attribute 'unknown_exc_attr' on <exception>"):
        loader.load_from_string("<rules lang='ru'><category id='C'><rule id='R'><pattern><token>a<exception unknown_exc_attr='1'>b</exception></token></pattern><message>m</message></rule></category></rules>")


def test_grammar_loader_preserves_root_phrase_and_token_attributes():
    """Verify GrammarLoader preserves root-level phrases, raw_pos, setpostag, and metadata."""
    loader = GrammarLoader()
    xml = """<rules lang="ru">
      <phrase id="my_phrase" raw_pos="yes">
        <token postag="VB:.*" postag_regexp="yes"/>
      </phrase>
      <category id="TEST_CAT" tab="grammar_tab" tabname="Grammar" premium="yes">
        <rulegroup id="TEST_GROUP" minprevmatches="2" distancetokens="5">
          <rule id="R1" name="Rule 1">
            <pattern>
              <token raw_pos="yes" setpostag="NN:Inan:Masc">слово<exception raw_pos="yes">искл</exception></token>
            </pattern>
            <message>Error</message>
          </rule>
        </rulegroup>
      </category>
    </rules>"""

    rules = loader.load_from_string(xml)
    assert len(rules) == 1
    r = rules[0]

    # Verify global phrases preserved
    assert "my_phrase" in loader.global_phrases
    phrase = loader.global_phrases["my_phrase"]
    assert phrase.id == "my_phrase"
    assert phrase.raw_pos is True
    assert len(phrase.elements) == 1

    # Verify rule metadata inherited/preserved
    assert r.tab == "grammar_tab"
    assert r.tabname == "Grammar"
    assert r.premium is True
    assert r.minprevmatches == 2
    assert r.distancetokens == 5

    # Verify token attributes preserved
    assert len(r.pattern.tokens) == 1
    tok = r.pattern.tokens[0]
    assert tok.text == "слово"
    assert tok.raw_pos is True
    assert tok.setpostag == "NN:Inan:Masc"
    assert len(tok.exceptions) == 1
    exc = tok.exceptions[0]
    assert exc.text == "искл"
    assert exc.raw_pos is True

