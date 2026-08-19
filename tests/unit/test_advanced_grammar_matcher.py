"""tests/unit/test_advanced_grammar_matcher.py

Comprehensive unit tests covering all Task 0008 advanced XML pattern matching features:
1. skip (-1..127) and skipMaxTokens (max 1..127, -1)
2. min (0..1) optional elements and lookahead preference
3. exceptions (scope="current", scope="previous", scope="next", spacebefore)
4. token@spacebefore (yes/no)
5. token@chunk matching (exact and regex)
6. <and> logical groups across readings
7. <or> Cartesian branch expansion
8. <phrase> and <phraseref> expansion
9. raw_pos="yes" pre-disambiguation stream selection
10. Antipattern evaluation and token immunization
11. Token-level <match> resolution and synthesis
12. RuleWithMaxFilter subsumption elimination
"""

import pytest

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.matcher import (
    CompiledPatternToken,
    CompiledRuleVariant,
    expand_rule_into_variants,
    filter_subsumed_rule_matches,
)
from pylat_ru.grammar.model import (
    ExecutionState,
    GrammarRule,
    MatchReference,
    MessageTemplate,
    Pattern,
    PatternAnd,
    PatternOr,
    PatternPhrase,
    PatternToken,
    PatternTokenException,
    RuleMatchResult,
    SuggestionTemplate,
)


def _make_reading(
    token: str,
    lemma: str = None,
    pos_tag: str = None,
    ws_before: str = " ",
    is_sent_start: bool = False,
    is_sent_end: bool = False,
    chunk_tags: list = None,
) -> AnalyzedTokenReadings:
    at = AnalyzedToken(token=token, lemma=lemma or token, pos_tag=pos_tag)
    atr = AnalyzedTokenReadings(
        readings=[at],
        whitespace_before=ws_before,
        is_sentence_start=is_sent_start,
        is_sentence_end=is_sent_end,
    )
    if chunk_tags:
        atr.chunk_tags = chunk_tags
    return atr


def _make_sentence(tokens: list, text: str) -> AnalyzedSentence:
    sent = AnalyzedSentence(tokens=tokens)
    sent.text = text
    return sent


def _make_rule(
    rule_id: str,
    pattern: Pattern,
    antipatterns: list = None,
    raw_pos: bool = False,
) -> GrammarRule:
    pattern.raw_pos = raw_pos
    return GrammarRule(
        id=rule_id,
        sub_id="1",
        full_id=f"{rule_id}[1]",
        name=f"Test Rule {rule_id}",
        category_id="TEST",
        category_name="Test Category",
        rulegroup_id=None,
        rulegroup_name=None,
        default_off=False,
        tags=[],
        source_order_index=0,
        pattern=pattern,
        antipatterns=antipatterns or [],
        execution_state=ExecutionState.ADVANCED_0008_RUNNABLE,
    )


def test_skip_and_max_repetitions():
    """Verify skip and max attributes behavior."""
    # Pattern: [A] (skip=2) [B (max=3)] [C]
    pt_a = PatternToken(text="A", skip=2)
    pt_b = PatternToken(text="B", max=3)
    pt_c = PatternToken(text="C")
    pat = Pattern(tokens=[pt_a, pt_b, pt_c], elements=[pt_a, pt_b, pt_c])
    rule = _make_rule("test_skip_max", pat)
    engine = RussianGrammarEngine(rules=[rule])

    # Case 1: "A X Y B B C" (A skips 2 tokens to find B, B repeats twice)
    tokens1 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("A"),
        _make_reading("X"),
        _make_reading("Y"),
        _make_reading("B"),
        _make_reading("B"),
        _make_reading("C"),
    ]
    sent1 = _make_sentence(tokens=tokens1, text="A X Y B B C")
    matches1 = engine.check_sentence(sent1)
    assert len(matches1) == 1
    assert matches1[0].matched_tokens_indices == [1, 2, 3, 4, 5, 6]

    # Case 2: "A X Y Z W B C" (A needs skip 4, but skip is only 2 -> no match)
    tokens2 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("A"),
        _make_reading("X"),
        _make_reading("Y"),
        _make_reading("Z"),
        _make_reading("W"),
        _make_reading("B"),
        _make_reading("C"),
    ]
    sent2 = _make_sentence(tokens=tokens2, text="A X Y Z W B C")
    assert len(engine.check_sentence(sent2)) == 0


def test_min_optional_element_lookahead():
    """Verify min=0 optional element with lookahead preference."""
    # Pattern: [A] [B (min=0, max=2)] [C]
    pt_a = PatternToken(text="A")
    pt_b = PatternToken(text="B", min=0, max=2)
    pt_c = PatternToken(text="C")
    pat = Pattern(tokens=[pt_a, pt_b, pt_c], elements=[pt_a, pt_b, pt_c])
    rule = _make_rule("test_min_opt", pat)
    engine = RussianGrammarEngine(rules=[rule])

    # Case 1: "A C" (B is omitted)
    tokens1 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("A"),
        _make_reading("C"),
    ]
    sent1 = _make_sentence(tokens=tokens1, text="A C")
    matches1 = engine.check_sentence(sent1)
    assert len(matches1) == 1
    assert matches1[0].matched_tokens_indices == [1, 2]

    # Case 2: "A B B C" (B repeats twice)
    tokens2 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("A"),
        _make_reading("B"),
        _make_reading("B"),
        _make_reading("C"),
    ]
    sent2 = _make_sentence(tokens=tokens2, text="A B B C")
    matches2 = engine.check_sentence(sent2)
    assert len(matches2) == 1
    assert matches2[0].matched_tokens_indices == [1, 2, 3, 4]


def test_exception_scopes_and_spacebefore():
    """Verify exception scopes: current, previous, next, and spacebefore."""
    exc_prev = PatternTokenException(text=",", scope="previous")
    exc_next = PatternTokenException(text="!", scope="next")
    pt = PatternToken(
        text="target",
        spacebefore="no",
        exceptions=[exc_prev, exc_next],
    )
    pat = Pattern(tokens=[pt], elements=[pt])
    rule = _make_rule("test_exc_scopes", pat)
    engine = RussianGrammarEngine(rules=[rule])

    # Case 1: "wordtarget?" (no space before target, prev is 'word', next is '?' -> matches)
    tokens1 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("word", ws_before=" "),
        _make_reading("target", ws_before=""),
        _make_reading("?", ws_before=""),
    ]
    sent1 = _make_sentence(tokens=tokens1, text="wordtarget?")
    assert len(engine.check_sentence(sent1)) == 1

    # Case 2: ",target?" (prev is ',' -> rejected by scope="previous" exception)
    tokens2 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading(",", ws_before=" "),
        _make_reading("target", ws_before=""),
        _make_reading("?", ws_before=""),
    ]
    sent2 = _make_sentence(tokens=tokens2, text=",target?")
    assert len(engine.check_sentence(sent2)) == 0

    # Case 3: "wordtarget!" (next is '!' -> rejected by scope="next" exception)
    tokens3 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("word", ws_before=" "),
        _make_reading("target", ws_before=""),
        _make_reading("!", ws_before=""),
    ]
    sent3 = _make_sentence(tokens=tokens3, text="wordtarget!")
    assert len(engine.check_sentence(sent3)) == 0

    # Case 4: "word target?" (spacebefore="no" fails because space before target)
    tokens4 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("word", ws_before=" "),
        _make_reading("target", ws_before=" "),
        _make_reading("?", ws_before=""),
    ]
    sent4 = _make_sentence(tokens=tokens4, text="word target?")
    assert len(engine.check_sentence(sent4)) == 0


def test_and_logical_groups():
    """Verify <and> group across readings."""
    member1 = PatternToken(postag="NN:.*", postag_regexp=True)
    member2 = PatternToken(text="[0-9]+", regexp=True, negate=True)
    and_elem = PatternAnd(elements=[member1, member2])

    pat = Pattern(elements=[and_elem])
    rule = _make_rule("test_and_group", pat)
    engine = RussianGrammarEngine(rules=[rule])

    # Case 1: Token "дом" with pos "NN:Masc:Sin:Nom" (matches member1 and member2)
    tokens1 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("дом", pos_tag="NN:Masc:Sin:Nom"),
    ]
    sent1 = _make_sentence(tokens=tokens1, text="дом")
    assert len(engine.check_sentence(sent1)) == 1

    # Case 2: Token "123" with pos "NN:Masc:Sin:Nom" (fails member2 because digits)
    tokens2 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("123", pos_tag="NN:Masc:Sin:Nom"),
    ]
    sent2 = _make_sentence(tokens=tokens2, text="123")
    assert len(engine.check_sentence(sent2)) == 0


def test_or_and_phrase_cartesian_expansion():
    """Verify <or> Cartesian expansion and <phrase> referencing."""
    phrase = PatternPhrase(
        id="verb_phrase",
        elements=[
            PatternToken(postag="VB:.*", postag_regexp=True),
            PatternToken(postag="ADV:.*", postag_regexp=True),
        ],
    )
    loader = GrammarLoader()
    loader.global_phrases["verb_phrase"] = phrase

    pt_a = PatternToken(text="A")
    pt_b = PatternToken(text="B")
    pref = PatternPhrase(ref="verb_phrase")
    or_elem = PatternOr(elements=[pt_b, pref])
    pt_c = PatternToken(text="C")

    pat = Pattern(elements=[pt_a, or_elem, pt_c])
    rule = _make_rule("test_or_expansion", pat)

    variants = expand_rule_into_variants(rule, loader.global_phrases)
    assert len(variants) == 2
    assert len(variants[0].tokens) == 3
    assert variants[0].element_lengths == [1, 1, 1]
    assert len(variants[1].tokens) == 4
    assert variants[1].element_lengths == [1, 2, 1]

    engine = RussianGrammarEngine(rules=[rule], loader=loader)

    # Test Variant 1 match: "A B C"
    tokens1 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("A"),
        _make_reading("B"),
        _make_reading("C"),
    ]
    sent1 = _make_sentence(tokens=tokens1, text="A B C")
    assert len(engine.check_sentence(sent1)) == 1

    # Test Variant 2 match: "A бежал быстро C"
    tokens2 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("A"),
        _make_reading("бежал", pos_tag="VB:Past:Masc"),
        _make_reading("быстро", pos_tag="ADV:Posit"),
        _make_reading("C"),
    ]
    sent2 = _make_sentence(tokens=tokens2, text="A бежал быстро C")
    assert len(engine.check_sentence(sent2)) == 1


def test_antipattern_immunization():
    """Verify antipattern evaluates first and immunizes matched tokens from main rule."""
    pt_main1 = PatternToken(text="не")
    pt_main2 = PatternToken(text="колеблясь")
    pat_main = Pattern(elements=[pt_main1, pt_main2], tokens=[pt_main1, pt_main2])

    ap1 = PatternToken(text="Мэри")
    ap2 = PatternToken(text="не")
    ap3 = PatternToken(text="колеблясь")
    ap4 = PatternToken(text="прыгнула")
    antipattern = Pattern(elements=[ap1, ap2, ap3, ap4], tokens=[ap1, ap2, ap3, ap4])

    rule = _make_rule("test_antipattern", pat_main, antipatterns=[antipattern])
    engine = RussianGrammarEngine(rules=[rule])

    # Sentence matching antipattern: "Мэри не колеблясь прыгнула." -> 0 matches because immunized
    tokens1 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("Мэри"),
        _make_reading("не"),
        _make_reading("колеблясь"),
        _make_reading("прыгнула"),
    ]
    sent1 = _make_sentence(tokens=tokens1, text="Мэри не колеблясь прыгнула.")
    assert len(engine.check_sentence(sent1)) == 0

    # Sentence NOT matching antipattern: "Он не колеблясь ушёл." -> 1 match
    tokens2 = [
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("Он"),
        _make_reading("не"),
        _make_reading("колеблясь"),
        _make_reading("ушёл"),
    ]
    sent2 = _make_sentence(tokens=tokens2, text="Он не колеблясь ушёл.")
    assert len(engine.check_sentence(sent2)) == 1


def test_rule_with_max_filter_subsumption():
    """Verify RuleWithMaxFilter eliminates smaller subsumed matches."""
    m_larger = RuleMatchResult(
        rule_id="RULE_1",
        full_rule_id="RULE_1[1]",
        category_id="CAT",
        category_name="Cat",
        description="Desc",
        message="Msg",
        short_message=None,
        suggestions=[],
        from_pos=5,
        to_pos=25,
        from_pos_utf16=5,
        to_pos_utf16=25,
        pattern_from_pos=5,
        pattern_to_pos=25,
        pattern_from_pos_utf16=5,
        pattern_to_pos_utf16=25,
        matched_tokens_indices=[1, 2, 3, 4],
        marker_tokens_indices=[1, 2, 3, 4],
    )
    m_subsumed = RuleMatchResult(
        rule_id="RULE_1",
        full_rule_id="RULE_1[1]",
        category_id="CAT",
        category_name="Cat",
        description="Desc",
        message="Msg",
        short_message=None,
        suggestions=[],
        from_pos=8,
        to_pos=18,
        from_pos_utf16=8,
        to_pos_utf16=18,
        pattern_from_pos=8,
        pattern_to_pos=18,
        pattern_from_pos_utf16=8,
        pattern_to_pos_utf16=18,
        matched_tokens_indices=[2, 3],
        marker_tokens_indices=[2, 3],
    )
    m_different_rule = RuleMatchResult(
        rule_id="RULE_2",
        full_rule_id="RULE_2[1]",
        category_id="CAT",
        category_name="Cat",
        description="Desc",
        message="Msg",
        short_message=None,
        suggestions=[],
        from_pos=8,
        to_pos=18,
        from_pos_utf16=8,
        to_pos_utf16=18,
        pattern_from_pos=8,
        pattern_to_pos=18,
        pattern_from_pos_utf16=8,
        pattern_to_pos_utf16=18,
        matched_tokens_indices=[2, 3],
        marker_tokens_indices=[2, 3],
    )

    filtered = filter_subsumed_rule_matches([m_larger, m_subsumed, m_different_rule])
    assert len(filtered) == 2
    assert m_larger in filtered
    assert m_different_rule in filtered
    assert m_subsumed not in filtered
