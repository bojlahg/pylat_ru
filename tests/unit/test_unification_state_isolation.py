"""tests/unit/test_unification_state_isolation.py

State-isolation regression tests for LanguageTool Russian Unification engine.
Verifies complete reset and zero cross-contamination across:
1. Two start positions in the same sentence;
2. Two physical variants of an expanded rule;
3. Two distinct logical rules executed sequentially;
4. Two unify scopes within the same pattern;
5. Two sentences evaluated sequentially;
6. Repeated calls on the singleton engine instance;
7. Matching candidate followed by failing candidate;
8. Failing candidate followed by matching candidate;
9. Execution after producing filtered unified token readings.
"""

from __future__ import annotations

import pytest

from pylat_ru.analysis import AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.matcher import CompiledPatternToken, CompiledRuleVariant
from pylat_ru.grammar.model import ExecutionState, PatternToken
from pylat_ru.grammar.unification import UnifierConfiguration


@pytest.fixture(scope="module")
def disambiguator():
    return RussianHybridDisambiguator.get_instance()


@pytest.fixture(scope="module")
def chunker():
    return RussianChunker()


@pytest.fixture(scope="module")
def engine():
    return RussianGrammarEngine.get_instance()


SYNTHETIC_RULES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rules lang="ru">
  <unification feature="number">
    <equivalence type="Sin">
      <token postag=".*:Sin(:.*)*|((ADJ|Ord|PT:(Past|Real):.*|PT_Short:Real|VB:Past):.*:(Masc|Fem|Neut)(:.*)*)|NN:.*:(Masc|Fem|Neut)" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="PL">
      <token postag=".*:PL(:.*)*|NN:.*:(Masc|Fem|Neut)" postag_regexp="yes"/>
    </equivalence>
  </unification>

  <unification feature="gender">
    <equivalence type="Masc">
      <token postag=".*:Masc(:.*)*" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="Fem">
      <token postag=".*:Fem(:.*)*" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="Neut">
      <token postag=".*:Neut(:.*)*" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="Plural">
      <token postag=".*:PL(:.*)*|NN:.*:(Masc|Fem|Neut)" postag_regexp="yes"/>
    </equivalence>
  </unification>

  <category id="ISO_TEST" name="State Isolation Test Rules">
    <rule id="ISO_NUM_AGREE" name="Number agreement">
      <pattern>
        <unify>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Number agree</message>
    </rule>

    <rule id="ISO_GEN_AGREE" name="Gender agreement">
      <pattern>
        <unify>
          <feature id="gender"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Gender agree</message>
    </rule>

    <rule id="ISO_OR_VARIANTS" name="Two variants with unify">
      <pattern>
        <unify>
          <feature id="number"/>
          <or>
            <token postag_regexp="yes" postag="ADJ:.*"/>
            <token postag_regexp="yes" postag="PT:.*"/>
          </or>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>OR variant agree</message>
    </rule>

    <rule id="ISO_TWO_SCOPES" name="Two unify scopes in one rule">
      <pattern>
        <unify>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
        <token>и</token>
        <unify>
          <feature id="gender"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Two scopes agree</message>
    </rule>
  </category>
</rules>
"""


@pytest.fixture(scope="module")
def iso_engine():
    loader = GrammarLoader()
    rules = loader.load_from_string(SYNTHETIC_RULES_XML)
    return RussianGrammarEngine(rules=rules, loader=loader)


def test_isolation_two_start_positions(iso_engine, disambiguator, chunker):
    """Verify that unifier finds multiple matches at distinct start positions without accumulating state."""
    text = "красивый дом и новый дом"
    sent = disambiguator.disambiguate_text(text)
    sent.text = text
    chunker.chunk(sent)

    matches = iso_engine.check_rule(sent, "ISO_NUM_AGREE[1]")
    assert len(matches) == 2
    assert (matches[0].from_pos, matches[0].to_pos) == (0, 12)
    assert (matches[1].from_pos, matches[1].to_pos) == (15, 24)


def test_isolation_two_physical_variants(iso_engine, disambiguator, chunker):
    """Verify state isolation across physical variants of an expanded rule."""
    # Variant 1: ADJ + NN
    text1 = "красивый дом"
    sent1 = disambiguator.disambiguate_text(text1)
    sent1.text = text1
    chunker.chunk(sent1)
    matches1 = iso_engine.check_rule(sent1, "ISO_OR_VARIANTS[1]")
    assert len(matches1) == 1

    # Variant 2: PT + NN
    text2 = "построенный дом"
    sent2 = disambiguator.disambiguate_text(text2)
    sent2.text = text2
    chunker.chunk(sent2)
    matches2 = iso_engine.check_rule(sent2, "ISO_OR_VARIANTS[1]")
    assert len(matches2) == 1


def test_isolation_two_logical_rules(iso_engine, disambiguator, chunker):
    """Verify sequential execution of two distinct logical rules without cross-contamination."""
    text_gen = "красивая книга"  # Fem Sin
    sent_gen = disambiguator.disambiguate_text(text_gen)
    sent_gen.text = text_gen
    chunker.chunk(sent_gen)

    # First run gender agreement rule
    m_gen = iso_engine.check_rule(sent_gen, "ISO_GEN_AGREE[1]")
    assert len(m_gen) == 1

    # Then run number agreement rule on same sentence
    m_num = iso_engine.check_rule(sent_gen, "ISO_NUM_AGREE[1]")
    assert len(m_num) == 1

    # Then run gender rule on mismatched gender
    text_bad_gen = "красивый книга"
    sent_bad_gen = disambiguator.disambiguate_text(text_bad_gen)
    sent_bad_gen.text = text_bad_gen
    chunker.chunk(sent_bad_gen)
    m_bad = iso_engine.check_rule(sent_bad_gen, "ISO_GEN_AGREE[1]")
    assert len(m_bad) == 0


def test_isolation_two_unify_scopes_in_one_rule(iso_engine, disambiguator, chunker):
    """Verify pattern with two sequential unify scopes resets unifier between scopes."""
    text_ok = "новый дом и новая книга"
    sent_ok = disambiguator.disambiguate_text(text_ok)
    sent_ok.text = text_ok
    chunker.chunk(sent_ok)
    m_ok = iso_engine.check_rule(sent_ok, "ISO_TWO_SCOPES[1]")
    assert len(m_ok) == 1

    # First scope fails, second scope passes -> whole rule must fail
    text_fail1 = "красивые дом и новая книга"
    sent_fail1 = disambiguator.disambiguate_text(text_fail1)
    sent_fail1.text = text_fail1
    chunker.chunk(sent_fail1)
    m_fail1 = iso_engine.check_rule(sent_fail1, "ISO_TWO_SCOPES[1]")
    assert len(m_fail1) == 0

    # First scope passes, second scope fails -> whole rule must fail
    text_fail2 = "новый дом и новый книга"
    sent_fail2 = disambiguator.disambiguate_text(text_fail2)
    sent_fail2.text = text_fail2
    chunker.chunk(sent_fail2)
    m_fail2 = iso_engine.check_rule(sent_fail2, "ISO_TWO_SCOPES[1]")
    assert len(m_fail2) == 0


def test_isolation_two_sentences_sequential(iso_engine, disambiguator, chunker):
    """Verify that evaluating distinct sentences sequentially produces isolated results."""
    sent1 = disambiguator.disambiguate_text("красивый дом")
    sent1.text = "красивый дом"
    chunker.chunk(sent1)

    sent2 = disambiguator.disambiguate_text("красивые дом")
    sent2.text = "красивые дом"
    chunker.chunk(sent2)

    assert len(iso_engine.check_rule(sent1, "ISO_NUM_AGREE[1]")) == 1
    assert len(iso_engine.check_rule(sent2, "ISO_NUM_AGREE[1]")) == 0
    assert len(iso_engine.check_rule(sent1, "ISO_NUM_AGREE[1]")) == 1


def test_isolation_repeated_engine_singleton_calls(engine, disambiguator, chunker):
    """Verify repeated calls to default singleton engine alternate matching and non-matching reliably."""
    incorrect_text = "Крыловский государственной научный центр"
    correct_text = "Крыловский государственный научный центр"

    inc_sent = disambiguator.disambiguate_text(incorrect_text)
    inc_sent.text = incorrect_text
    chunker.chunk(inc_sent)

    cor_sent = disambiguator.disambiguate_text(correct_text)
    cor_sent.text = correct_text
    chunker.chunk(cor_sent)

    for iteration in range(10):
        inc_matches = engine.check_rule(inc_sent, "Unify_Mult_Adj")
        assert len(inc_matches) == 1, f"Iteration {iteration} failed on incorrect sentence"

        cor_matches = engine.check_rule(cor_sent, "Unify_Mult_Adj")
        assert len(cor_matches) == 0, f"Iteration {iteration} failed on correct sentence"


def test_isolation_candidate_success_then_fail(iso_engine, disambiguator, chunker):
    """Verify candidate evaluation where a matching candidate is immediately followed by a failing one."""
    text = "красивый дом красивые дом"
    sent = disambiguator.disambiguate_text(text)
    sent.text = text
    chunker.chunk(sent)

    matches = iso_engine.check_rule(sent, "ISO_NUM_AGREE[1]")
    assert len(matches) == 1
    assert (matches[0].from_pos, matches[0].to_pos) == (0, 12)


def test_isolation_candidate_fail_then_success(iso_engine, disambiguator, chunker):
    """Verify candidate evaluation where a failing candidate is immediately followed by a matching one."""
    text = "красивые дом красивый дом"
    sent = disambiguator.disambiguate_text(text)
    sent.text = text
    chunker.chunk(sent)

    matches = iso_engine.check_rule(sent, "ISO_NUM_AGREE[1]")
    assert len(matches) == 1
    assert (matches[0].from_pos, matches[0].to_pos) == (13, 25)


def test_isolation_after_filtered_unified_atrs():
    """Verify that calling get_unified_tokens() leaves the unifier clean after reset."""
    loader = GrammarLoader()
    loader.load_from_string(SYNTHETIC_RULES_XML)
    unifier_config = loader.unifier_config
    assert unifier_config is not None
    uni = unifier_config.createUnifier()

    t1 = AnalyzedToken("красивый", "красивый", "ADJ:Masc:Sin:Nom")
    t2 = AnalyzedToken("дом", "дом", "NN:Masc:Sin:Nom")

    atr1 = AnalyzedTokenReadings([t1], start_pos=0, chunk_tags=["NP"], whitespace_before=" ")
    atr2 = AnalyzedTokenReadings([t2], start_pos=9, chunk_tags=["NP"], whitespace_before=" ")

    # Run unification cycle
    uni.is_unified(t1, {"gender": ["Masc"]}, last_reading=True, is_matched=True, orig_atr=atr1)
    uni.is_unified(t2, {"gender": ["Masc"]}, last_reading=True, is_matched=True, orig_atr=atr2)

    filtered = uni.get_unified_tokens()
    assert filtered is not None
    assert len(filtered) == 2
    assert filtered[0].start_pos == 0
    assert filtered[0].chunk_tags == ["NP"]
    assert filtered[0].whitespace_before == " "
    assert filtered[1].start_pos == 9
    assert filtered[1].chunk_tags == ["NP"]
    assert filtered[1].whitespace_before == " "

    # Reset and verify fresh state
    uni.reset()
    assert uni.in_unification is False
    assert len(uni.tok_sequence) == 0
    assert uni.get_unified_tokens() is None


def test_unification_identity_vs_equality_distinguishable():
    """Verify that multiple reading sets with identical values do not trigger premature is_last_in_unify resets."""
    loader = GrammarLoader()
    rules = loader.load_from_string(SYNTHETIC_RULES_XML)
    unifier_config = loader.unifier_config
    assert unifier_config is not None

    p_tok = PatternToken(postag="ADJ:.*", postag_regexp=True)
    p_tok.is_last_in_unify = True
    p_tok.uni_features = {"gender": ["Masc"]}
    c_tok = CompiledPatternToken(p_tok)

    variant = CompiledRuleVariant(
        source_rule=rules[0],
        variant_idx=0,
        tokens=[c_tok],
        element_lengths=[1],
        has_marker=False,
        marker_start_idx=None,
        marker_end_idx=None,
        unifier_config=unifier_config,
    )

    t1 = AnalyzedToken("красивый", "красивый", "ADJ:Masc:Sin:Nom")
    t2 = AnalyzedToken("красивый", "красивый", "ADJ:Masc:Sin:Nom")

    # Two distinct reading sets that have identical content values
    reading_set_1 = [t1]
    reading_set_2 = [t2]
    assert reading_set_1 == reading_set_2
    assert reading_set_1 is not reading_set_2

    to_unify = {c_tok: [reading_set_1, reading_set_2]}
    neutral_readings = {}

    # Under value equality (readings == reading_sets[-1]), set 1 would prematurely trigger is_last_in_unify reset.
    # Under index identity (set_idx == num_sets - 1), set 1 processes normally and only set 2 resets.
    res = variant._test_unification(to_unify, neutral_readings)
    assert res is True
    assert variant.unifier is not None
    assert len(variant.unifier.tok_sequence) == 0
    assert variant.unifier.get_unified_tokens() is None
