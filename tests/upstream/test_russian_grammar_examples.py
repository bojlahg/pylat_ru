"""tests/upstream/test_russian_grammar_examples.py

Executes all XML examples (incorrect and correct) from grammar.xml for all
CORE_0007_RUNNABLE rules and verifies 100% trigger pass rate with zero false triggers
and zero missed detections.
Also asserts marker span and suggested replacements for examples with markers/corrections.
"""

from __future__ import annotations

from typing import List, Tuple
import pytest

from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine


from pylat_ru.grammar.model import ExecutionState


@pytest.fixture(scope="module")
def engine():
    return RussianGrammarEngine.get_instance()


@pytest.fixture(scope="module")
def disambiguator():
    return RussianHybridDisambiguator.get_instance()


@pytest.fixture(scope="module")
def chunker():
    return RussianChunker()


def test_grammar_core_runnable_rules_count(engine):
    """Verify that 506 CORE, 229 ADVANCED, 24 UNIFICATION rules are classified (759 total runnable)."""
    all_rules = engine.get_runnable_rules()
    assert len(all_rules) == 759, f"Expected 759 total runnable rules, got {len(all_rules)}"
    core_rules = [r for r in all_rules if r.execution_state == ExecutionState.CORE_0007_RUNNABLE]
    advanced_rules = [r for r in all_rules if r.execution_state == ExecutionState.ADVANCED_0008_RUNNABLE]
    unification_rules = [r for r in all_rules if r.execution_state == ExecutionState.UNIFICATION_0009_RUNNABLE]
    assert len(core_rules) == 506, f"Expected 506 core runnable rules, got {len(core_rules)}"
    assert len(advanced_rules) == 229, f"Expected 229 advanced runnable rules, got {len(advanced_rules)}"
    assert len(unification_rules) == 24, f"Expected 24 unification runnable rules, got {len(unification_rules)}"


def test_grammar_core_trigger_parity(engine, disambiguator, chunker):
    """Execute all examples for all core runnable rules and assert 100% trigger parity."""
    core_rules = [r for r in engine.get_runnable_rules() if r.execution_state == ExecutionState.CORE_0007_RUNNABLE]
    total_examples = 0
    failures = []

    for rule in core_rules:
        for ex_idx, ex in enumerate(rule.examples):
            total_examples += 1
            text = ex.text

            sent = disambiguator.disambiguate_text(text)
            sent.text = text
            chunker.chunk(sent)

            matches = engine.check_rule(sent, rule.full_id)
            has_match = (len(matches) > 0)

            if ex.is_incorrect and not has_match:
                failures.append(
                    f"[{rule.full_id}] Incorrect example #{ex_idx} failed to trigger rule: {text!r}"
                )
            elif not ex.is_incorrect and has_match:
                failures.append(
                    f"[{rule.full_id}] Correct example #{ex_idx} falsely triggered rule: {text!r}"
                )

    assert total_examples == 988, f"Expected 988 total examples, got {total_examples}"
    assert not failures, f"Grammar examples trigger failures ({len(failures)}):\n" + "\n".join(failures)


def test_grammar_core_full_example_parity(engine, disambiguator, chunker):
    """Verify marker spans and suggested replacements for core examples with markers/corrections."""
    core_rules = [r for r in engine.get_runnable_rules() if r.execution_state == ExecutionState.CORE_0007_RUNNABLE]
    total_examples = 0
    full_parity_matches = 0
    span_failures: List[str] = []
    suggestion_failures: List[str] = []

    for rule in core_rules:
        for ex_idx, ex in enumerate(rule.examples):
            total_examples += 1
            text = ex.text

            sent = disambiguator.disambiguate_text(text)
            sent.text = text
            chunker.chunk(sent)

            matches = engine.check_rule(sent, rule.full_id)

            if not ex.is_incorrect:
                if len(matches) == 0:
                    full_parity_matches += 1
                continue

            if not matches:
                continue

            m = matches[0]
            is_perfect = True

            # Check marker span if present - strict exact offset equality
            if ex.marker_spans:
                exp_span = ex.marker_spans[0]
                if (m.from_pos, m.to_pos) != exp_span:
                    is_perfect = False
                    exp_text = text[exp_span[0]:exp_span[1]]
                    act_text = text[m.from_pos:m.to_pos]
                    span_failures.append(
                        f"[{rule.full_id}] Exact span mismatch: exp {exp_span} ({exp_text!r}), got ({m.from_pos}, {m.to_pos}) ({act_text!r})"
                    )

            # Check suggested replacements if present - strict exact string & order equality
            if ex.correction:
                exp_suggs = ex.correction.split("|")
                if m.suggestions != exp_suggs:
                    is_perfect = False
                    suggestion_failures.append(
                        f"[{rule.full_id}] Exact suggestions mismatch: exp {exp_suggs}, got {m.suggestions}"
                    )

            if is_perfect:
                full_parity_matches += 1

    assert not span_failures, f"Marker span failures ({len(span_failures)}):\n" + "\n".join(span_failures)
    assert not suggestion_failures, f"Suggestion failures ({len(suggestion_failures)}):\n" + "\n".join(suggestion_failures)
    assert full_parity_matches == total_examples, f"Full parity: {full_parity_matches}/{total_examples}"


def test_grammar_unification_0009_trigger_parity(engine, disambiguator, chunker):
    """Execute all examples for all 24 newly runnable unification rules and assert 100% trigger accuracy."""
    uni_rules = [r for r in engine.get_runnable_rules() if r.execution_state == ExecutionState.UNIFICATION_0009_RUNNABLE]
    assert len(uni_rules) == 24
    total_examples = 0
    failures = []

    for rule in uni_rules:
        for ex_idx, ex in enumerate(rule.examples):
            total_examples += 1
            text = ex.text

            sent = disambiguator.disambiguate_text(text)
            sent.text = text
            chunker.chunk(sent)

            matches = engine.check_rule(sent, rule.full_id)
            has_match = (len(matches) > 0)

            if ex.is_incorrect and not has_match:
                failures.append(
                    f"[{rule.full_id}] Incorrect example #{ex_idx} failed to trigger rule: {text!r}"
                )
            elif not ex.is_incorrect and has_match:
                failures.append(
                    f"[{rule.full_id}] Correct example #{ex_idx} falsely triggered rule: {text!r}"
                )

    assert total_examples == 216, f"Expected 216 unification examples, got {total_examples}"
    assert not failures, f"Unification 0009 grammar examples trigger failures ({len(failures)}):\n" + "\n".join(failures)


def test_grammar_unification_0009_full_example_parity(engine, disambiguator, chunker):
    """Verify marker spans and suggested replacements for all 216 unification examples with markers/corrections."""
    uni_rules = [r for r in engine.get_runnable_rules() if r.execution_state == ExecutionState.UNIFICATION_0009_RUNNABLE]
    total_examples = 0
    full_parity_matches = 0
    span_failures: List[str] = []
    suggestion_failures: List[str] = []

    for rule in uni_rules:
        for ex_idx, ex in enumerate(rule.examples):
            total_examples += 1
            text = ex.text

            sent = disambiguator.disambiguate_text(text)
            sent.text = text
            chunker.chunk(sent)

            matches = engine.check_rule(sent, rule.full_id)

            if not ex.is_incorrect:
                if len(matches) == 0:
                    full_parity_matches += 1
                continue

            if not matches:
                continue

            m = matches[0]
            is_perfect = True

            # Check marker span if present - strict exact offset equality
            if ex.marker_spans:
                exp_span = ex.marker_spans[0]
                if (m.from_pos, m.to_pos) != exp_span:
                    is_perfect = False
                    exp_text = text[exp_span[0]:exp_span[1]]
                    act_text = text[m.from_pos:m.to_pos]
                    span_failures.append(
                        f"[{rule.full_id}] Exact span mismatch: exp {exp_span} ({exp_text!r}), got ({m.from_pos}, {m.to_pos}) ({act_text!r})"
                    )

            # Check suggested replacements if present - strict exact string & order equality
            if ex.correction:
                exp_suggs = ex.correction.split("|")
                if m.suggestions != exp_suggs:
                    is_perfect = False
                    suggestion_failures.append(
                        f"[{rule.full_id}] Exact suggestions mismatch: exp {exp_suggs}, got {m.suggestions}"
                    )

            if is_perfect:
                full_parity_matches += 1

    assert not span_failures, f"Marker span failures ({len(span_failures)}):\n" + "\n".join(span_failures)
    assert not suggestion_failures, f"Suggestion failures ({len(suggestion_failures)}):\n" + "\n".join(suggestion_failures)
    assert full_parity_matches == total_examples, f"Full parity: {full_parity_matches}/{total_examples}"


def test_grammar_all_runnable_0009_trigger_parity(engine, disambiguator, chunker):
    """Execute all examples for all 759 (0007+0008+0009) runnable rules and assert 100% trigger accuracy."""
    all_rules = engine.get_runnable_rules()
    total_examples = 0
    failures = []

    for rule in all_rules:
        for ex_idx, ex in enumerate(rule.examples):
            total_examples += 1
            text = ex.text

            sent = disambiguator.disambiguate_text(text)
            sent.text = text
            chunker.chunk(sent)

            matches = engine.check_rule(sent, rule.full_id)
            has_match = (len(matches) > 0)

            if ex.is_incorrect and not has_match:
                failures.append(
                    f"[{rule.full_id}] Incorrect example #{ex_idx} failed to trigger rule: {text!r}"
                )
            elif not ex.is_incorrect and has_match:
                failures.append(
                    f"[{rule.full_id}] Correct example #{ex_idx} falsely triggered rule: {text!r}"
                )

    assert total_examples == 1954, f"Expected 1954 total examples, got {total_examples}"
    assert not failures, f"All 0009 runnable grammar examples trigger failures ({len(failures)}):\n" + "\n".join(failures)

