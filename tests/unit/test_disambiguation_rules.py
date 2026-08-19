"""Unit tests for XML disambiguation rule engine, pattern matching, and actions."""

from __future__ import annotations

import pytest

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.disambiguation.errors import DisambiguationFormatError
from pylat_ru.disambiguation.pattern_matcher import PatternRuleMatcher, PatternToken, PatternTokenException
from pylat_ru.disambiguation.rules import (
    DisambiguationPatternRule,
    DisambiguationPatternRuleReplacer,
    DisambiguatorAction,
)
from pylat_ru.disambiguation.xml_loader import DisambiguationRuleLoader, XmlRuleDisambiguator


def _build_sentence(token_readings: list[tuple[str, str, str]]) -> AnalyzedSentence:
    """Helper to build AnalyzedSentence from list of (token, lemma, pos_tag)."""
    sent_start = AnalyzedTokenReadings.create_sentence_start_token(start_pos=0)
    current_pos = 0
    readings_list: list[AnalyzedTokenReadings] = []
    for tok, lemma, tag in token_readings:
        r = AnalyzedTokenReadings(
            readings=[AnalyzedToken(token=tok, lemma=lemma, pos_tag=tag)],
            start_pos=current_pos,
        )
        readings_list.append(r)
        current_pos += len(tok)
    return AnalyzedSentence([sent_start] + readings_list)


def test_load_all_77_rules_from_disambiguation_xml() -> None:
    """Verify all 77 rules in pinned disambiguation.xml load without errors."""
    loader = DisambiguationRuleLoader()
    rules = loader.parse_file("src/pylat_ru/resources/ru/disambiguation.xml")
    assert len(rules) == 77

    # Check known rule IDs
    rule_ids = {r.id for r in rules}
    assert "NN_Inanim_Neut" in rule_ids
    assert "NN_Inanim_Masc" in rule_ids
    assert "NN_Inanim_Fem" in rule_ids
    assert "i_Co" in rule_ids
    assert "NOUN_V" in rule_ids
    assert "NOUN_V2" in rule_ids
    assert "NumD_D_tag" in rule_ids


def test_action_add_rule() -> None:
    """Verify ADD action adds new reading to marked token."""
    rule = DisambiguationPatternRule(
        id="TEST_ADD",
        name="Test Add",
        pattern_tokens=[
            PatternToken(
                string="город",
                is_inside_marker=True,
            )
        ],
        action=DisambiguatorAction.ADD,
        new_token_readings=[AnalyzedToken(token="город", pos_tag="NN:Inanim:Masc:Sin:Nom", lemma="город")],
    )
    sentence = _build_sentence([("город", "город", "NN:Inanim:Masc:Sin:V")])
    replacer = DisambiguationPatternRuleReplacer(rule)
    result = replacer.replace(sentence)

    tok = result.get_tokens_without_whitespace()[1]
    assert len(tok.readings) == 2
    assert tok.has_pos_tag("NN:Inanim:Masc:Sin:Nom")
    assert tok.has_pos_tag("NN:Inanim:Masc:Sin:V")


def test_action_remove_rule() -> None:
    """Verify REMOVE action removes matching reading by POS regex."""
    rule = DisambiguationPatternRule(
        id="TEST_REMOVE",
        name="Test Remove",
        pattern_tokens=[
            PatternToken(string="в"),
            PatternToken(
                postag="NN:.*:Nom",
                is_postag_regex=True,
                is_inside_marker=True,
            ),
        ],
        action=DisambiguatorAction.REMOVE,
        disambiguated_pos="NN:.*:Nom",
    )
    # Token "город" has both Nom and V readings
    sent_start = AnalyzedTokenReadings.create_sentence_start_token(0)
    tok1 = AnalyzedTokenReadings([AnalyzedToken("в", "в", "PREP")], start_pos=0)
    tok2 = AnalyzedTokenReadings(
        [
            AnalyzedToken("город", "город", "NN:Inanim:Masc:Sin:Nom"),
            AnalyzedToken("город", "город", "NN:Inanim:Masc:Sin:V"),
        ],
        start_pos=2,
    )
    sentence = AnalyzedSentence([sent_start, tok1, tok2])
    replacer = DisambiguationPatternRuleReplacer(rule)
    result = replacer.replace(sentence)

    res_tok = result.get_tokens_without_whitespace()[2]
    assert len(res_tok.readings) == 1
    assert res_tok.readings[0].pos_tag == "NN:Inanim:Masc:Sin:V"


def test_action_ignore_spelling() -> None:
    """Verify IGNORE_SPELLING action marks target token to ignore spelling."""
    rule = DisambiguationPatternRule(
        id="TEST_IGNORE_SPELL",
        name="Test Ignore Spell",
        pattern_tokens=[
            PatternToken(string="дай-ка", is_inside_marker=True)
        ],
        action=DisambiguatorAction.IGNORE_SPELLING,
    )
    sentence = _build_sentence([("дай-ка", "дай-ка", "VB:IMP:TRANS:PFV:Sin:P2")])
    replacer = DisambiguationPatternRuleReplacer(rule)
    result = replacer.replace(sentence)

    res_tok = result.get_tokens_without_whitespace()[1]
    assert res_tok.is_ignore_spelling is True


def test_and_conjunction_matching() -> None:
    """Verify <and> conjunction requires all sub-tokens to match on the same token."""
    sub1 = PatternToken(postag="NN:Inanim:Neut", is_postag_regex=False)
    sub2 = PatternToken(postag="NN:Inanim:Neut:Sin:V", is_postag_regex=False)
    p_tok = PatternToken(and_tokens=[sub1, sub2])

    tok_matching = AnalyzedTokenReadings(
        [
            AnalyzedToken("окно", "окно", "NN:Inanim:Neut"),
            AnalyzedToken("окно", "окно", "NN:Inanim:Neut:Sin:V"),
        ],
        start_pos=0,
    )
    tok_failing = AnalyzedTokenReadings(
        [
            AnalyzedToken("окно", "окно", "NN:Inanim:Neut"),
            AnalyzedToken("окно", "окно", "NN:Inanim:Neut:Sin:Nom"),
        ],
        start_pos=0,
    )

    assert p_tok.matches_token(tok_matching) is True
    assert p_tok.matches_token(tok_failing) is False


def test_scope_next_exception_rejection() -> None:
    """Verify exception with scope='next' prevents match when next token satisfies exception."""
    exc_next = PatternTokenException(
        postag="NN:.*",
        is_postag_regex=True,
        scope="next",
    )
    p1 = PatternToken(string="в", exceptions=[exc_next], skip=1)
    p2 = PatternToken(string="город")

    matcher = PatternRuleMatcher([p1, p2])

    # Case 1: Next token after "в" is NN -> should be rejected by scope="next"
    sent1 = _build_sentence([
        ("в", "в", "PREP"),
        ("парке", "парк", "NN:Inanim:Masc:Sin:P"),
        ("город", "город", "NN:Inanim:Masc:Sin:Nom"),
    ])
    assert len(matcher.find_matches(sent1)) == 0

    # Case 2: Next token after "в" is ADJ -> should match!
    sent2 = _build_sentence([
        ("в", "в", "PREP"),
        ("красивый", "красивый", "ADJ:Masc:Sin:Nom"),
        ("город", "город", "NN:Inanim:Masc:Sin:Nom"),
    ])
    assert len(matcher.find_matches(sent2)) == 1


def test_antipattern_rejection() -> None:
    """Verify antipattern cancels rule application on overlapping span."""
    rule = DisambiguationPatternRule(
        id="TEST_RULE",
        name="Test Rule",
        pattern_tokens=[
            PatternToken(string="за"),
            PatternToken(string="два", is_inside_marker=True),
        ],
        action=DisambiguatorAction.IGNORE_SPELLING,
        antipatterns=[
            DisambiguationPatternRule(
                id="TEST_ANTI",
                name="Test Anti",
                pattern_tokens=[PatternToken(string="Что"), PatternToken(string="за")],
                action=DisambiguatorAction.IMMUNIZE,
            )
        ],
    )
    # Sentence contains "Что за два" -> antipattern matches "Что за", canceling rule
    sentence = _build_sentence([
        ("Что", "что", "CONJ"),
        ("за", "за", "PREP"),
        ("два", "два", "Num"),
    ])
    replacer = DisambiguationPatternRuleReplacer(rule)
    result = replacer.replace(sentence)

    tok = result.get_tokens_without_whitespace()[3]  # "два"
    assert tok.is_ignore_spelling is False


def test_unknown_xml_element_raises_explicit_format_error() -> None:
    """Verify unknown XML elements fail explicitly with DisambiguationFormatError."""
    bad_xml = """<rules lang="ru"><unknown_tag><token>test</token></unknown_tag></rules>"""
    loader = DisambiguationRuleLoader()
    with pytest.raises(DisambiguationFormatError, match="Unsupported XML element"):
        loader.parse_xml_string(bad_xml)


def test_unsupported_attribute_on_token_raises_format_error() -> None:
    """Verify unsupported attribute on token fails with DisambiguationFormatError."""
    bad_xml = """<rules lang="ru"><rule id="R1" name="R1"><pattern><token min="1">test</token></pattern><disambig postag="ADV"/></rule></rules>"""
    loader = DisambiguationRuleLoader()
    with pytest.raises(DisambiguationFormatError, match="Unsupported attribute 'min' on element <token>"):
        loader.parse_xml_string(bad_xml)


def test_unsupported_attribute_on_rule_raises_format_error() -> None:
    """Verify unsupported attribute on rule fails with DisambiguationFormatError."""
    bad_xml = """<rules lang="ru"><rule id="R1" name="R1" default="off"><pattern><token>test</token></pattern><disambig postag="ADV"/></rule></rules>"""
    loader = DisambiguationRuleLoader()
    with pytest.raises(DisambiguationFormatError, match="Unsupported attribute 'default' on element <rule>"):
        loader.parse_xml_string(bad_xml)


def test_invalid_child_nesting_raises_format_error() -> None:
    """Verify invalid child element hierarchy fails explicitly with DisambiguationFormatError."""
    # <token> directly inside <rules> is invalid
    bad_xml1 = """<rules lang="ru"><token>test</token></rules>"""
    loader = DisambiguationRuleLoader()
    with pytest.raises(DisambiguationFormatError, match="XML element <token> is not allowed inside parent <rules>"):
        loader.parse_xml_string(bad_xml1)

    # <disambig> inside <pattern> is invalid
    bad_xml2 = """<rules lang="ru"><rule id="R1" name="R1"><pattern><disambig postag="ADV"/></pattern></rule></rules>"""
    with pytest.raises(DisambiguationFormatError, match="XML element <disambig> is not allowed inside parent <pattern>"):
        loader.parse_xml_string(bad_xml2)

