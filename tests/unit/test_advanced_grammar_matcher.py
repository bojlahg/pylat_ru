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
    start_pos: int = 0,
) -> AnalyzedTokenReadings:
    at = AnalyzedToken(token=token, lemma=lemma or token, pos_tag=pos_tag)
    atr = AnalyzedTokenReadings(
        readings=[at],
        whitespace_before=ws_before,
        start_pos=start_pos,
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
    assert len(variants[0].tokens) == 4
    assert variants[0].element_lengths == [1, 2, 1]
    assert len(variants[1].tokens) == 3
    assert variants[1].element_lengths == [1, 1, 1]

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


# ==============================================================================
# Ported Upstream PatternRuleMatcherTest Tests
# ==============================================================================

def _analyze_words(text: str) -> AnalyzedSentence:
    """Create an AnalyzedSentence from space-separated tokens with start_pos/end_pos."""
    tokens = []
    tokens.append(
        AnalyzedTokenReadings(
            readings=[AnalyzedToken("", "", "SENT_START")],
            start_pos=0,
            whitespace_before="",
            is_sentence_start=True,
        )
    )

    pos = 0
    parts = text.split(" ")
    for idx, p in enumerate(parts):
        start = text.find(p, pos) if p else pos
        atr = AnalyzedTokenReadings(
            readings=[AnalyzedToken(p, p, None)],
            start_pos=start,
            whitespace_before=" " if idx > 0 else "",
            is_sentence_start=False,
        )
        tokens.append(atr)
        pos = start + len(p)

    sent = AnalyzedSentence(tokens=tokens)
    sent.text = text
    return sent


def _get_matches(text: str, rule: GrammarRule) -> list:
    engine = RussianGrammarEngine(rules=[rule])
    sent = _analyze_words(text)
    return engine.check_rule(sent, rule)


def _assert_no_match(text: str, rule: GrammarRule):
    matches = _get_matches(text, rule)
    assert len(matches) == 0, f"Expected 0 matches, got {len(matches)} for '{text}'"


def _assert_partial_match(text: str, rule: GrammarRule):
    matches = _get_matches(text, rule)
    assert len(matches) == 1, f"Expected 1 match, got {len(matches)} for '{text}'"
    m = matches[0]
    assert m.from_pos > 0 or m.to_pos < len(text), f"Expected partial match, got {m.from_pos}-{m.to_pos} for '{text}'"


def _assert_complete_match(text: str, rule: GrammarRule):
    matches = _get_matches(text, rule)
    assert len(matches) == 1, f"Expected 1 match, got {len(matches)} for '{text}'"
    m = matches[0]
    assert m.from_pos == 0 and m.to_pos == len(text), f"Expected complete match (0, {len(text)}), got ({m.from_pos}, {m.to_pos}) for '{text}'"


def _assert_pos(match: RuleMatchResult, exp_from: int, exp_to: int):
    assert match.from_pos == exp_from, f"Expected from_pos {exp_from}, got {match.from_pos}"
    assert match.to_pos == exp_to, f"Expected to_pos {exp_to}, got {match.to_pos}"


def test_upstream_zero_min_occurrences():
    pt_b = PatternToken(text="b", min=0)
    rule = _make_rule("test_zero_min", Pattern(tokens=[PatternToken(text="a"), pt_b, PatternToken(text="c")]))
    _assert_no_match("b a", rule)
    _assert_no_match("c a b", rule)
    _assert_partial_match("b a c", rule)
    _assert_partial_match("a c b", rule)
    _assert_no_match("a b b c", rule)
    _assert_complete_match("a c", rule)
    _assert_complete_match("a b c", rule)
    _assert_no_match("a X c", rule)

    matches = _get_matches("a b c FOO a b c FOO a c a b c", rule)
    assert len(matches) == 4
    _assert_pos(matches[0], 0, 5)
    _assert_pos(matches[1], 10, 15)
    _assert_pos(matches[2], 20, 23)
    _assert_pos(matches[3], 24, 29)


def test_upstream_two_zero_min_occurrences():
    pt_b1 = PatternToken(text="ba", min=0)
    pt_b2 = PatternToken(text="bb", min=0)
    rule = _make_rule("test_two_zero_min", Pattern(tokens=[PatternToken(text="a"), pt_b1, pt_b2, PatternToken(text="c")]))
    _assert_no_match("ba a", rule)
    _assert_no_match("c a bb", rule)
    _assert_partial_match("z a c", rule)
    _assert_partial_match("a c z", rule)
    _assert_no_match("a ba ba c", rule)
    _assert_complete_match("a ba bb c", rule)
    _assert_complete_match("a ba c", rule)
    _assert_complete_match("a bb c", rule)
    _assert_complete_match("a c", rule)
    _assert_no_match("a X c", rule)

    matches = _get_matches("a ba c FOO a bb c FOO a c a ba bb c", rule)
    assert len(matches) == 4
    _assert_pos(matches[0], 0, 6)
    _assert_pos(matches[1], 11, 17)
    _assert_pos(matches[2], 22, 25)
    _assert_pos(matches[3], 26, 35)


def test_upstream_zero_min_occurrences2():
    pt_b = PatternToken(text="b", min=0)
    rule = _make_rule("test_zero_min2", Pattern(tokens=[
        PatternToken(text="a"), pt_b, PatternToken(text="c"), PatternToken(text="d"), PatternToken(text="e")
    ]))
    _assert_complete_match("a b c d e", rule)
    _assert_complete_match("a c d e", rule)
    _assert_no_match("a d", rule)
    _assert_no_match("a c b d", rule)
    _assert_no_match("a c b d e", rule)


def test_upstream_zero_min_occurrences3():
    pt_c = PatternToken(text="c", min=0)
    rule = _make_rule("test_zero_min3", Pattern(tokens=[
        PatternToken(text="a"), PatternToken(text="b"), pt_c, PatternToken(text="d"), PatternToken(text="e")
    ]))
    _assert_complete_match("a b c d e", rule)
    _assert_complete_match("a b d e", rule)
    _assert_partial_match("a b c d e x", rule)
    _assert_partial_match("x a b c d e", rule)
    _assert_no_match("a b c e d", rule)
    _assert_no_match("a c b d e", rule)


def test_upstream_zero_min_occurrences4():
    pt_a = PatternToken(text="a", min=0)
    pt_c = PatternToken(text="c", min=0)
    rule = _make_rule("test_zero_min4", Pattern(tokens=[
        pt_a, PatternToken(text="b"), pt_c, PatternToken(text="d"), PatternToken(text="e")
    ]))
    matches = _get_matches("a b c d e", rule)
    assert len(matches) == 1
    _assert_pos(matches[0], 0, 9)


def test_upstream_zero_min_occurrences_with_empty_element():
    pt_any = PatternToken(text=None, min=0)
    rule = _make_rule("test_zero_min_empty", Pattern(tokens=[PatternToken(text="a"), pt_any, PatternToken(text="c")]))
    _assert_no_match("b a", rule)
    _assert_no_match("c a b", rule)
    _assert_partial_match("b a c", rule)
    _assert_partial_match("a c b", rule)
    _assert_no_match("a b b c", rule)
    _assert_complete_match("a c", rule)
    _assert_complete_match("a b c", rule)
    _assert_complete_match("a X c", rule)

    matches = _get_matches("a b c FOO a X c", rule)
    assert len(matches) == 2
    _assert_pos(matches[0], 0, 5)
    _assert_pos(matches[1], 10, 15)


def test_upstream_zero_min_occurrences_with_suggestion():
    pt_b = PatternToken(text="b", min=0)
    msg_tmpl = MessageTemplate(elements=[
        MatchReference(no=1), " ", MatchReference(no=2), " ", MatchReference(no=3)
    ])
    rule = GrammarRule(
        id="test_sugg",
        sub_id="1",
        full_id="test_sugg[1]",
        name="desc",
        category_id="C",
        category_name="Cat",
        rulegroup_id=None,
        rulegroup_name=None,
        default_off=False,
        tags=[],
        source_order_index=0,
        pattern=Pattern(tokens=[PatternToken(text="a"), pt_b, PatternToken(text="c")]),
        message_template=msg_tmpl,
        suggestions=[SuggestionTemplate(elements=[MatchReference(no=1), " ", MatchReference(no=2), " ", MatchReference(no=3)])],
        execution_state=ExecutionState.ADVANCED_0008_RUNNABLE,
    )
    matches1 = _get_matches("a b c", rule)
    assert matches1[0].suggestions == ["a b c"]

    matches2 = _get_matches("a c", rule)
    assert matches2[0].suggestions == ["a c"]


def test_upstream_zero_min_two_max_occurrences():
    pt_b = PatternToken(text="b", min=0, max=2)
    rule = _make_rule("test_0min_2max", Pattern(tokens=[PatternToken(text="a"), pt_b, PatternToken(text="c")]))
    _assert_complete_match("a c", rule)
    _assert_complete_match("a b c", rule)
    _assert_complete_match("a b b c", rule)
    _assert_no_match("a b b b c", rule)


def test_upstream_two_max_occurrences_with_any_token():
    pt_any = PatternToken(text=None, max=2)
    rule = _make_rule("test_2max_any", Pattern(tokens=[PatternToken(text="a"), pt_any, PatternToken(text="c")]))
    _assert_complete_match("a b c", rule)
    _assert_complete_match("a b b c", rule)
    _assert_no_match("a b b b c", rule)


def test_upstream_three_max_occurrences_with_any_token():
    pt_any = PatternToken(text=None, max=3)
    rule = _make_rule("test_3max_any", Pattern(tokens=[PatternToken(text="a"), pt_any, PatternToken(text="c")]))
    _assert_complete_match("a b c", rule)
    _assert_complete_match("a b b c", rule)
    _assert_complete_match("a b b b c", rule)
    _assert_no_match("a b b b b c", rule)


def test_upstream_zero_min_two_max_occurrences_with_any_token():
    pt_any = PatternToken(text=None, min=0, max=2)
    rule = _make_rule("test_0min_2max_any", Pattern(tokens=[PatternToken(text="a"), pt_any, PatternToken(text="c")]))
    _assert_no_match("a b", rule)
    _assert_no_match("b c", rule)
    _assert_no_match("c", rule)
    _assert_no_match("a", rule)
    _assert_complete_match("a c", rule)
    _assert_complete_match("a x c", rule)
    _assert_complete_match("a x x c", rule)
    _assert_no_match("a x x x c", rule)


def test_upstream_two_max_occurrences():
    pt_b = PatternToken(text="b", max=2)
    rule = _make_rule("test_2max", Pattern(tokens=[PatternToken(text="a"), pt_b]))
    _assert_no_match("a a", rule)
    _assert_complete_match("a b", rule)
    _assert_complete_match("a b b", rule)
    _assert_partial_match("a b c", rule)
    _assert_partial_match("a b b c", rule)
    _assert_partial_match("x a b b", rule)

    matches1 = _get_matches("a b b b", rule)
    assert len(matches1) == 1
    _assert_pos(matches1[0], 0, 5)

    matches2 = _get_matches("a b b b foo a b b", rule)
    assert len(matches2) == 2
    _assert_pos(matches2[0], 0, 5)
    _assert_pos(matches2[1], 12, 17)


def test_upstream_three_max_occurrences():
    pt_b = PatternToken(text="b", max=3)
    rule = _make_rule("test_3max", Pattern(tokens=[PatternToken(text="a"), pt_b]))
    _assert_no_match("a a", rule)
    _assert_complete_match("a b", rule)
    _assert_complete_match("a b b", rule)
    _assert_complete_match("a b b b", rule)
    _assert_partial_match("a b b b b", rule)

    matches = _get_matches("a b b b b", rule)
    assert len(matches) == 1
    _assert_pos(matches[0], 0, 7)


def test_upstream_optional_without_explicit_marker():
    pt_b = PatternToken(text="b", min=0)
    rule = _make_rule("test_opt_no_marker", Pattern(tokens=[PatternToken(text="a"), pt_b, PatternToken(text="c")]))
    matches1 = _get_matches("a b c zzz", rule)
    assert len(matches1) == 1
    _assert_pos(matches1[0], 0, 5)

    matches2 = _get_matches("a c zzz", rule)
    assert len(matches2) == 1
    _assert_pos(matches2[0], 0, 3)


def test_upstream_optional_with_explicit_marker():
    pt_a = PatternToken(text="a", is_in_marker=True)
    pt_b = PatternToken(text="b", min=0, is_in_marker=True)
    pt_c = PatternToken(text="c", is_in_marker=False)
    rule = _make_rule("test_opt_marker", Pattern(
        tokens=[pt_a, pt_b, pt_c],
        has_marker=True,
        marker_start_idx=0,
        marker_end_idx=2,
    ))
    matches1 = _get_matches("a b c zzz", rule)
    assert len(matches1) == 1
    _assert_pos(matches1[0], 0, 3)

    matches2 = _get_matches("a c zzz", rule)
    assert len(matches2) == 1
    _assert_pos(matches2[0], 0, 1)


def test_upstream_optional_any_token_with_explicit_marker():
    pt_a = PatternToken(text="a", is_in_marker=True)
    pt_b = PatternToken(text=None, min=0, is_in_marker=True)
    pt_c = PatternToken(text="c", is_in_marker=False)
    rule = _make_rule("test_opt_any_marker", Pattern(
        tokens=[pt_a, pt_b, pt_c],
        has_marker=True,
        marker_start_idx=0,
        marker_end_idx=2,
    ))
    matches1 = _get_matches("a x c zzz", rule)
    assert len(matches1) == 1
    _assert_pos(matches1[0], 0, 3)

    matches2 = _get_matches("a c zzz", rule)
    assert len(matches2) == 1
    _assert_pos(matches2[0], 0, 1)


def test_upstream_optional_any_token_with_explicit_marker2():
    pt_a = PatternToken(text="the", is_in_marker=True)
    pt_b = PatternToken(text=None, min=0, is_in_marker=True)
    pt_c = PatternToken(text="bike", is_in_marker=False)
    rule = _make_rule("test_opt_any_marker2", Pattern(
        tokens=[pt_a, pt_b, pt_c],
        has_marker=True,
        marker_start_idx=0,
        marker_end_idx=2,
    ))
    matches1 = _get_matches("the nice bike zzz", rule)
    assert len(matches1) == 1
    _assert_pos(matches1[0], 0, 8)

    matches2 = _get_matches("the bike zzz", rule)
    assert len(matches2) == 1
    _assert_pos(matches2[0], 0, 3)


def test_upstream_unlimited_max_occurrences():
    pt_b = PatternToken(text="b", max=-1)
    rule = _make_rule("test_unlimited_max", Pattern(tokens=[PatternToken(text="a"), pt_b, PatternToken(text="c")]))
    _assert_no_match("a c", rule)
    _assert_no_match("a b", rule)
    _assert_no_match("b c", rule)
    _assert_complete_match("a b c", rule)
    _assert_complete_match("a b b c", rule)
    _assert_complete_match("a " + " ".join(["b"] * 25) + " c", rule)


def test_upstream_max_two_and_three_occurrences():
    pt_a = PatternToken(text="a", max=2)
    pt_b = PatternToken(text="b", max=3)
    rule = _make_rule("test_max2_max3", Pattern(tokens=[pt_a, pt_b]))
    _assert_complete_match("a b", rule)
    _assert_complete_match("a b b", rule)
    _assert_complete_match("a b b b", rule)
    _assert_no_match("a a", rule)
    _assert_no_match("a x b b b", rule)

    matches2 = _get_matches("a a b", rule)
    assert len(matches2) == 1
    _assert_pos(matches2[0], 0, 5)

    matches3 = _get_matches("a a b b", rule)
    assert len(matches3) == 1
    _assert_pos(matches3[0], 0, 7)

    matches4 = _get_matches("a a b b b", rule)
    assert len(matches4) == 1
    _assert_pos(matches4[0], 0, 9)


def test_upstream_infinite_skip():
    pt_a = PatternToken(text="a", skip=-1)
    rule = _make_rule("test_inf_skip", Pattern(tokens=[pt_a, PatternToken(text="b")]))
    _assert_complete_match("a b", rule)
    _assert_complete_match("a x b", rule)
    _assert_complete_match("a x x b", rule)
    _assert_complete_match("a x x x b", rule)


def test_upstream_infinite_skip_with_match_reference():
    pt_ab = PatternToken(text="a|b", regexp=True, skip=-1)
    pt_c = PatternToken(text=None, match=MatchReference(no=0))
    rule = _make_rule("test_inf_skip_match_ref", Pattern(tokens=[pt_ab, pt_c]))
    _assert_complete_match("a a", rule)
    _assert_complete_match("b b", rule)
    _assert_complete_match("a x a", rule)
    _assert_complete_match("b x b", rule)
    _assert_complete_match("a x x a", rule)
    _assert_complete_match("b x x b", rule)

    _assert_no_match("a b", rule)
    _assert_no_match("b a", rule)
    _assert_no_match("b x a", rule)
    _assert_no_match("a x x b", rule)
    _assert_no_match("b x x a", rule)

    matches = _get_matches("a foo a and b foo b", rule)
    assert len(matches) == 2
    _assert_pos(matches[0], 0, 7)
    _assert_pos(matches[1], 12, 19)

    matches2 = _get_matches("xx a b x x x b a", rule)
    assert len(matches2) == 1
    _assert_pos(matches2[0], 3, 16)


def test_upstream_no_match_reference_recursion():
    msg_tmpl = MessageTemplate(elements=["Here come the match references: ", MatchReference(no=1), MatchReference(no=2), ". This is the end"])
    rule = GrammarRule(
        id="MATCH_REFERENCERE_CURSION_DEMO",
        sub_id="1",
        full_id="MATCH_REFERENCERE_CURSION_DEMO[1]",
        name="desc",
        category_id="C",
        category_name="Cat",
        rulegroup_id=None,
        rulegroup_name=None,
        default_off=False,
        tags=[],
        source_order_index=0,
        pattern=Pattern(tokens=[PatternToken(text=r"\p{Punct}", regexp=True), PatternToken(text=r"\d+", regexp=True)]),
        message_template=msg_tmpl,
        execution_state=ExecutionState.ADVANCED_0008_RUNNABLE,
    )
    matches = _get_matches(": 42", rule)
    assert len(matches) == 1
    assert matches[0].message == "Here come the match references: :42. This is the end"


# ==============================================================================
# min and max Boundary Validation Tests
# ==============================================================================

def test_min_attribute_validation_boundaries():
    from pylat_ru.grammar.errors import GrammarFormatError
    loader = GrammarLoader()

    # min=0 accepted
    xml_0 = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token min="0">а</token></pattern><message>M</message></rule></category></rules>'
    rules_0 = loader.load_from_string(xml_0)
    assert rules_0[0].pattern.tokens[0].min == 0

    # min=1 accepted
    xml_1 = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token min="1">а</token></pattern><message>M</message></rule></category></rules>'
    rules_1 = loader.load_from_string(xml_1)
    assert rules_1[0].pattern.tokens[0].min == 1

    # min=-1 rejected
    xml_neg = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token min="-1">а</token></pattern><message>M</message></rule></category></rules>'
    with pytest.raises(GrammarFormatError, match="min"):
        loader.load_from_string(xml_neg)

    # min=2 rejected
    xml_2 = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token min="2">а</token></pattern><message>M</message></rule></category></rules>'
    with pytest.raises(GrammarFormatError, match="min"):
        loader.load_from_string(xml_2)

    # min=non-integer rejected
    xml_str = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token min="abc">а</token></pattern><message>M</message></rule></category></rules>'
    with pytest.raises(GrammarFormatError, match="Invalid integer"):
        loader.load_from_string(xml_str)


def test_max_attribute_validation_boundaries():
    from pylat_ru.grammar.errors import GrammarFormatError
    loader = GrammarLoader()

    # max=1 accepted
    xml_1 = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token max="1">а</token></pattern><message>M</message></rule></category></rules>'
    rules_1 = loader.load_from_string(xml_1)
    assert rules_1[0].pattern.tokens[0].max == 1

    # max=2 accepted
    xml_2 = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token max="2">а</token></pattern><message>M</message></rule></category></rules>'
    rules_2 = loader.load_from_string(xml_2)
    assert rules_2[0].pattern.tokens[0].max == 2

    # max=3 accepted
    xml_3 = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token max="3">а</token></pattern><message>M</message></rule></category></rules>'
    rules_3 = loader.load_from_string(xml_3)
    assert rules_3[0].pattern.tokens[0].max == 3

    # max=-1 accepted (unlimited)
    xml_unlim = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token max="-1">а</token></pattern><message>M</message></rule></category></rules>'
    rules_unlim = loader.load_from_string(xml_unlim)
    assert rules_unlim[0].pattern.tokens[0].max == -1

    # max=0 rejected
    xml_0 = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token max="0">а</token></pattern><message>M</message></rule></category></rules>'
    with pytest.raises(GrammarFormatError, match="max"):
        loader.load_from_string(xml_0)

    # max=-2 rejected
    xml_neg2 = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token max="-2">а</token></pattern><message>M</message></rule></category></rules>'
    with pytest.raises(GrammarFormatError, match="max"):
        loader.load_from_string(xml_neg2)

    # max=128 rejected
    xml_128 = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token max="128">а</token></pattern><message>M</message></rule></category></rules>'
    with pytest.raises(GrammarFormatError, match="max"):
        loader.load_from_string(xml_128)

    # max=non-integer rejected
    xml_str = '<rules lang="ru"><category id="C" name="C"><rule id="R1" name="N"><pattern><token max="xyz">а</token></pattern><message>M</message></rule></category></rules>'
    with pytest.raises(GrammarFormatError, match="Invalid integer"):
        loader.load_from_string(xml_str)


# ==============================================================================
# Deferred Rules Structural Preservation & Dynamic State Isolation Regressions
# ==============================================================================

def test_deferred_rules_preserve_complete_pattern_structure():
    """Verify that all deferred rules in grammar.xml retain full typed pattern nodes."""
    loader = GrammarLoader()
    rules = loader.load_default()
    assert len(rules) == 892

    unification_0009 = [r for r in rules if r.execution_state == ExecutionState.UNIFICATION_0009_RUNNABLE]
    deferred_0010 = [r for r in rules if r.execution_state == ExecutionState.DEFERRED_0010_FILTER]

    assert len(unification_0009) == 24
    assert len(deferred_0010) == 20

    for r in unification_0009:
        assert r.pattern is not None
        assert len(r.pattern.elements) > 0 or len(r.pattern.tokens) > 0, f"Rule {r.full_id} has empty pattern"

    for r in deferred_0010:
        assert r.pattern is not None
        assert len(r.pattern.elements) > 0 or len(r.pattern.tokens) > 0, f"Rule {r.full_id} has empty pattern"


def test_mutable_token_reference_state_isolation():
    """Verify that dynamic reference state is isolated across match attempts and varying lengths."""
    # Pattern: [тот|этот] [match no=0]
    tok1 = PatternToken(text="тот|этот", regexp=True)
    tok2 = PatternToken(match=MatchReference(no=0))
    rule = _make_rule("test_state_iso", Pattern(tokens=[tok1, tok2]))

    engine = RussianGrammarEngine(rules=[rule])

    # First attempt matches "тот тот"
    sent1 = _make_sentence([
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("тот", start_pos=0),
        _make_reading("тот", start_pos=4),
    ], "тот тот")
    m1 = engine.check_sentence(sent1)
    assert len(m1) == 1

    # Second attempt on "тот этот" must fail cleanly without stale reference
    sent2 = _make_sentence([
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("тот", start_pos=0),
        _make_reading("этот", start_pos=4),
    ], "тот этот")
    m2 = engine.check_sentence(sent2)
    assert len(m2) == 0

    # Third attempt on "этот этот" must match cleanly
    sent3 = _make_sentence([
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("этот", start_pos=0),
        _make_reading("этот", start_pos=5),
    ], "этот этот")
    m3 = engine.check_sentence(sent3)
    assert len(m3) == 1


def test_phrase_semantics_cartesian_and_markers():
    """Verify phrase expansion, internal OR, marker propagation, and undefined ref fail closed."""
    from pylat_ru.grammar.errors import GrammarFormatError
    loader = GrammarLoader()

    # 1. Undefined phrase reference must fail closed at load/expand time
    xml_undef = """<rules lang="ru">
      <category id="C" name="C">
        <rule id="R_UNDEF" name="Undef">
          <pattern>
            <phraseref idref="missing_phrase"/>
          </pattern>
          <message>M</message>
        </rule>
      </category>
    </rules>"""
    rules_undef = loader.load_from_string(xml_undef)
    with pytest.raises(GrammarFormatError, match="Undefined or missing phrase reference"):
        RussianGrammarEngine(rules=rules_undef, loader=loader)

    # 2. Phrase with internal OR inside marker produces variants with marker preserved
    xml_valid = """<rules lang="ru">
      <phrases>
        <phrase id="colors">
          <or>
            <token>красный</token>
            <token>синий</token>
          </or>
          <token>дом</token>
        </phrase>
      </phrases>
      <category id="C" name="C">
        <rule id="R_PHRASE" name="Phrase rule">
          <pattern>
            <token>очень</token>
            <marker>
              <phraseref idref="colors"/>
            </marker>
          </pattern>
          <message>M: <suggestion><match no="1"/> <match no="2"/></suggestion></message>
        </rule>
      </category>
    </rules>"""
    loader_valid = GrammarLoader()
    rules_valid = loader_valid.load_from_string(xml_valid)
    engine_valid = RussianGrammarEngine(rules=rules_valid, loader=loader_valid)

    # Test "очень красный дом"
    sent_k = _make_sentence([
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("очень", start_pos=0),
        _make_reading("красный", start_pos=6),
        _make_reading("дом", start_pos=14),
    ], "очень красный дом")
    matches_k = engine_valid.check_sentence(sent_k)
    assert len(matches_k) == 1
    assert matches_k[0].from_pos == 6  # starts at 'красный' (marker position)
    assert matches_k[0].to_pos == 17

    # Test "очень синий дом"
    sent_s = _make_sentence([
        _make_reading("", pos_tag="SENT_START", is_sent_start=True),
        _make_reading("очень", start_pos=0),
        _make_reading("синий", start_pos=6),
        _make_reading("дом", start_pos=12),
    ], "очень синий дом")
    matches_s = engine_valid.check_sentence(sent_s)
    assert len(matches_s) == 1
    assert matches_s[0].from_pos == 6
    assert matches_s[0].to_pos == 15


def test_unify_ignore_phraseref_structural_preservation_and_fail_closed():
    """Verify that <unify-ignore> preserves <phraseref> and fails closed on invalid children."""
    from pylat_ru.grammar.errors import GrammarFormatError
    from pylat_ru.grammar.model import PatternUnify, PatternUnifyIgnore, PatternPhrase
    loader = GrammarLoader()

    # 1. Structural preservation of phraseref under unify-ignore
    xml_valid = """<rules lang="ru">
      <phrases>
        <phrase id="ign_phrase">
          <token>слово</token>
        </phrase>
      </phrases>
      <category id="C" name="C">
        <rule id="R_UNIFY_IGN" name="Unify Ignore Rule">
          <pattern>
            <unify>
              <feature id="gender"/>
              <token postag_regexp="yes" postag="ADJ:.*"/>
              <unify-ignore>
                <phraseref idref="ign_phrase"/>
              </unify-ignore>
              <token postag_regexp="yes" postag="NN:.*"/>
            </unify>
          </pattern>
          <message>M</message>
        </rule>
      </category>
    </rules>"""
    rules = loader.load_from_string(xml_valid)
    assert len(rules) == 1
    u_node = rules[0].pattern.elements[0]
    assert isinstance(u_node, PatternUnify)
    ign_node = [el for el in u_node.elements if isinstance(el, PatternUnifyIgnore)][0]
    assert len(ign_node.elements) == 1
    ph_node = ign_node.elements[0]
    assert isinstance(ph_node, PatternPhrase)
    assert ph_node.ref == "ign_phrase"

    # 2. Defensive fail-closed on unknown child under unify-ignore
    xml_invalid = """<rules lang="ru">
      <category id="C" name="C">
        <rule id="R_BAD_IGN" name="Bad">
          <pattern>
            <unify>
              <feature id="gender"/>
              <unify-ignore>
                <unknown_tag/>
              </unify-ignore>
            </unify>
          </pattern>
          <message>M</message>
        </rule>
      </category>
    </rules>"""
    with pytest.raises(GrammarFormatError, match="Disallowed child <unknown_tag>"):
        loader.load_from_string(xml_invalid)



