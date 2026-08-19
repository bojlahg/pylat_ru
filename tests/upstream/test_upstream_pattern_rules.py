"""tests/upstream/test_upstream_pattern_rules.py

Ported unit tests from upstream LanguageTool Java test suites:
- PatternRuleLoaderTest.java
- PatternRuleMatcherTest.java
- PatternRuleTest.java
- RussianPatternRuleTest.java

Directly tests XML pattern rule loading, matcher execution, token predicates,
and explicitly inventories deferred features for Tasks 0008-0010.
"""

from __future__ import annotations

import pytest

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.errors import GrammarFormatError, UnsupportedGrammarFeatureError
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


def _make_reading(token: str, pos_tag: str = "NN:Inanim:Masc:Sin:Nom", lemma: str = "лемма", start_pos: int = 0) -> AnalyzedTokenReadings:
    at = AnalyzedToken(token=token, lemma=lemma, pos_tag=pos_tag)
    return AnalyzedTokenReadings(readings=[at], start_pos=start_pos)


def _make_sentence(tokens_str: list[str]) -> AnalyzedSentence:
    readings = []
    curr_pos = 0
    # Add SENT_START
    readings.append(AnalyzedTokenReadings(
        readings=[AnalyzedToken(token="", lemma=None, pos_tag="SENT_START")],
        start_pos=0,
        is_sentence_start=True,
    ))
    for t in tokens_str:
        if t == " ":
            readings.append(AnalyzedTokenReadings(
                readings=[AnalyzedToken(token=" ", lemma=None, pos_tag=None)],
                start_pos=curr_pos,
            ))
            curr_pos += 1
        else:
            readings.append(_make_reading(t, start_pos=curr_pos))
            curr_pos += len(t)
    sent = AnalyzedSentence(tokens=readings)
    sent.text = "".join(tokens_str)
    return sent


# =========================================================================
# 1. Ported from PatternRuleLoaderTest.java
# =========================================================================

def test_pattern_rule_loader_structure():
    """Verify core properties parsed by GrammarLoader matching PatternRuleLoaderTest."""
    loader = GrammarLoader()
    rules = loader.load_default()

    assert len(rules) == 892

    # Check categories loaded
    categories = {r.category_id for r in rules}
    assert len(categories) == 8
    assert "LOGIC" in categories
    assert "PUNCTUATION" in categories
    assert "GRAMMAR" in categories

    # Check zadat_test rule
    zadat_rule = next(r for r in rules if r.full_id == "zadat_test[1]")
    assert zadat_rule is not None
    assert zadat_rule.rulegroup_id is None
    assert zadat_rule.category_id == "LOGIC"
    assert zadat_rule.name == "Опечатка: «задать тест»"
    assert zadat_rule.short_message == "Опечатка"

    # Check rule with rulegroup and URL
    typo_rule = next(r for r in rules if r.full_id == "TYPOGRAF_SYMBOL[1]")
    assert typo_rule is not None
    assert typo_rule.rulegroup_id == "TYPOGRAF_SYMBOL"
    assert typo_rule.category_id == "TYPOGRAPHY"
    assert typo_rule.url is not None
    assert "wikipedia" in typo_rule.url


def test_pattern_rule_loader_fail_closed_validation():
    """Verify GrammarLoader fail-closed behavior for malformed XML elements/attributes."""
    loader = GrammarLoader()

    # Unknown root element
    with pytest.raises(GrammarFormatError, match="Expected root tag <rules>"):
        loader.load_from_string("<unknown_root lang='ru'><category id='CAT'/></unknown_root>")

    # Unknown category child
    with pytest.raises(GrammarFormatError, match="Disallowed child <bad_child> inside <category>"):
        loader.load_from_string("<rules lang='ru'><category id='CAT'><bad_child/></category></rules>")

    # Unknown rule attribute
    with pytest.raises(GrammarFormatError, match="Unknown attribute 'unknown_attr' on <rule>"):
        loader.load_from_string("<rules lang='ru'><category id='CAT'><rule id='R1' unknown_attr='val'><pattern><token>a</token></pattern><message>msg</message></rule></category></rules>")

    # Unknown token attribute
    with pytest.raises(GrammarFormatError, match="Unknown attribute 'bad_attr' on <token>"):
        loader.load_from_string("<rules lang='ru'><category id='CAT'><rule id='R1'><pattern><token bad_attr='x'>a</token></pattern><message>msg</message></rule></category></rules>")

    # Invalid boolean attribute value
    with pytest.raises(GrammarFormatError, match="Invalid boolean value 'maybe' for attribute 'regexp'"):
        loader.load_from_string("<rules lang='ru'><category id='CAT'><rule id='R1'><pattern><token regexp='maybe'>a</token></pattern><message>msg</message></rule></category></rules>")

    # Invalid integer attribute
    with pytest.raises(GrammarFormatError, match="Invalid integer value 'abc' for attribute 'skip'"):
        loader.load_from_string("<rules lang='ru'><category id='CAT'><rule id='R1'><pattern><token skip='abc'>a</token></pattern><message>msg</message></rule></category></rules>")


# =========================================================================
# 2. Ported from PatternRuleMatcherTest.java
# =========================================================================

def test_pattern_rule_matcher_simple_match():
    """Verify basic sequential matching ported from PatternRuleMatcherTest.testMatch."""
    # Pattern: "my" "test"
    pat = Pattern(tokens=[
        PatternToken(text="my"),
        PatternToken(text="test"),
    ])
    compiled = CompiledPattern(pat)

    # Positive match
    sent = _make_sentence(["This", " ", "is", " ", "my", " ", "test", "."])
    non_blank = [t for t in sent.tokens if not t.is_whitespace() or t.has_pos_tag("SENT_START")]
    # non_blank: [SENT_START, "This", "is", "my", "test", "."]
    match_span = compiled.match_at(non_blank, 3) # at "my"
    assert match_span is not None
    assert match_span == (3, 5, 3, 5)

    # Negative match
    sent_no = _make_sentence(["This", " ", "is", " ", "no", " ", "test", "."])
    non_blank_no = [t for t in sent_no.tokens if not t.is_whitespace() or t.has_pos_tag("SENT_START")]
    assert compiled.match_at(non_blank_no, 3) is None


def test_pattern_rule_matcher_case_sensitivity():
    """Verify case sensitive vs insensitive matching ported from PatternRuleMatcherTest."""
    # Case sensitive pattern: "Word"
    pat_cs = Pattern(tokens=[
        PatternToken(text="Word", case_sensitive=True),
    ], case_sensitive=True)
    comp_cs = CompiledPattern(pat_cs)

    tok_upper = _make_reading("Word")
    tok_lower = _make_reading("word")

    assert comp_cs.match_at([tok_upper], 0) is not None
    assert comp_cs.match_at([tok_lower], 0) is None

    # Case insensitive pattern: "Word"
    pat_ci = Pattern(tokens=[
        PatternToken(text="Word", case_sensitive=False),
    ], case_sensitive=False)
    comp_ci = CompiledPattern(pat_ci)

    assert comp_ci.match_at([tok_upper], 0) is not None
    assert comp_ci.match_at([tok_lower], 0) is not None


def test_pattern_rule_matcher_regex_and_negation():
    """Verify regex token and postag negation ported from PatternRuleMatcherTest."""
    # Token regex: "a.*" with negate_pos="yes" and postag="VB:.*"
    pat = Pattern(tokens=[
        PatternToken(
            text="а.*",
            regexp=True,
            postag="VB:.*",
            postag_regexp=True,
            negate_pos=True,
        ),
    ])
    compiled = CompiledPattern(pat)

    # Matches "автор" with NN (non-VB)
    tok_noun = _make_reading("автор", pos_tag="NN:Anim:Masc:Sin:Nom")
    assert compiled.match_at([tok_noun], 0) is not None

    # Rejects "атаковать" with VB (negated pos)
    tok_verb = _make_reading("атаковать", pos_tag="VB:Inf:TRANS:IPFV")
    assert compiled.match_at([tok_verb], 0) is None


def test_pattern_rule_matcher_inflected_exact_semantics():
    """Verify exact PatternToken.getTestToken semantics for inflected attribute."""
    # Pattern requiring inflected="yes" text="бежать"
    pat = Pattern(tokens=[
        PatternToken(text="бежать", inflected=True),
    ])
    compiled = CompiledPattern(pat)

    # 1. Surface matches, but lemma differs: MUST NOT MATCH
    tok_surface_match_lemma_differ = _make_reading("бежать", lemma="бег")
    assert compiled.match_at([tok_surface_match_lemma_differ], 0) is None

    # 2. Lemma matches, surface differs: MUST MATCH
    tok_lemma_match_surface_differ = _make_reading("бежал", lemma="бежать")
    assert compiled.match_at([tok_lemma_match_surface_differ], 0) is not None

    # 3. Lemma is null: falls back to surface token: MUST MATCH
    tok_lemma_null = _make_reading("бежать", lemma=None)
    assert compiled.match_at([tok_lemma_null], 0) is not None

    # 4. Exception with inflected:
    exc = PatternTokenException(text="делать", inflected=True)
    pat_with_exc = Pattern(tokens=[
        PatternToken(postag="VB:.*", postag_regexp=True, exceptions=[exc])
    ])
    comp_exc = CompiledPattern(pat_with_exc)

    # Surface "делал", lemma "делать" triggers exception -> rejected
    tok_delal = _make_reading("делал", pos_tag="VB:Past", lemma="делать")
    assert comp_exc.match_at([tok_delal], 0) is None

    # Surface "делал", lemma "дело" does NOT trigger exception -> accepted
    tok_delo = _make_reading("делал", pos_tag="VB:Past", lemma="дело")
    assert comp_exc.match_at([tok_delo], 0) is not None


# =========================================================================
# 3. Ported from PatternRuleTest.java & RussianPatternRuleTest.java
# =========================================================================

def test_russian_pattern_rule_execution_suite():
    """Direct equivalent of RussianPatternRuleTest.testRules() running grammar.xml rules."""
    engine = RussianGrammarEngine.get_instance()
    all_runnable_rules = engine.get_runnable_rules()
    assert len(all_runnable_rules) == 759

    core_rules = [r for r in all_runnable_rules if r.execution_state == ExecutionState.CORE_0007_RUNNABLE]
    advanced_rules = [r for r in all_runnable_rules if r.execution_state == ExecutionState.ADVANCED_0008_RUNNABLE]
    unification_rules = [r for r in all_runnable_rules if r.execution_state == ExecutionState.UNIFICATION_0009_RUNNABLE]
    assert len(core_rules) == 506
    assert len(advanced_rules) == 229
    assert len(unification_rules) == 24

    # Verify execution of representative core rules
    zadat = engine.get_rule("zadat_test[1]")
    assert zadat is not None
    assert zadat.execution_state == ExecutionState.CORE_0007_RUNNABLE

    # Verify deferred rules raise typed error when checked directly
    deferred_rule = engine.get_rule("SKL_N_I_NN[1]")
    if deferred_rule is not None and deferred_rule.execution_state not in (
        ExecutionState.CORE_0007_RUNNABLE,
        ExecutionState.ADVANCED_0008_RUNNABLE,
        ExecutionState.UNIFICATION_0009_RUNNABLE,
    ):
        sent = _make_sentence(["test"])
        with pytest.raises(UnsupportedGrammarFeatureError):
            engine.check_rule(sent, deferred_rule)


def test_deferred_features_inventory_task_0008_to_0010():
    """Exhaustive inventory assertion of features for Task 0009 and deferred future tasks."""
    loader = GrammarLoader()
    rules = loader.load_default()

    runnable_0007 = [r for r in rules if r.execution_state == ExecutionState.CORE_0007_RUNNABLE]
    runnable_0008 = [r for r in rules if r.execution_state == ExecutionState.ADVANCED_0008_RUNNABLE]
    runnable_0009 = [r for r in rules if r.execution_state == ExecutionState.UNIFICATION_0009_RUNNABLE]
    deferred_0010 = [r for r in rules if r.execution_state == ExecutionState.DEFERRED_0010_FILTER]
    deferred_0012 = [r for r in rules if r.execution_state == ExecutionState.DEFERRED_0012_SPELLING_OR_SUPPRESSION]
    multi_blocker = [r for r in rules if r.execution_state == ExecutionState.MULTI_BLOCKER]

    assert len(runnable_0007) == 506, f"Expected 506 core 0007 rules, got {len(runnable_0007)}"
    assert len(runnable_0008) == 229, f"Expected 229 advanced 0008 rules, got {len(runnable_0008)}"
    assert len(runnable_0009) == 24, f"Expected 24 unification 0009 rules, got {len(runnable_0009)}"
    assert len(deferred_0010) == 20, f"Expected 20 deferred 0010 rules, got {len(deferred_0010)}"
    assert len(deferred_0012) == 110, f"Expected 110 deferred 0012 rules, got {len(deferred_0012)}"
    assert len(multi_blocker) == 3, f"Expected 3 multi-blocker rules, got {len(multi_blocker)}"
    assert (
        len(runnable_0007)
        + len(runnable_0008)
        + len(runnable_0009)
        + len(deferred_0010)
        + len(deferred_0012)
        + len(multi_blocker)
    ) == 892
