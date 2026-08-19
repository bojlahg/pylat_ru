"""tests/upstream/test_russian_grammar_examples.py

Executes all XML examples (incorrect and correct) from grammar.xml for all
CORE_0007_RUNNABLE rules and verifies 100% pass rate with zero false triggers
and zero missed detections.
"""

from __future__ import annotations

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
    """Verify that exactly 506 rules are classified as CORE_0007_RUNNABLE."""
    core_rules = engine.get_runnable_rules()
    assert len(core_rules) == 506, f"Expected 506 core runnable rules, got {len(core_rules)}"


def test_grammar_core_all_examples_execution(engine, disambiguator, chunker):
    """Execute all examples for all core runnable rules and assert 0 failures."""
    core_rules = engine.get_runnable_rules()
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
    assert not failures, f"Grammar examples execution failures ({len(failures)}):\n" + "\n".join(failures)
