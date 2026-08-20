"""tests/unit/test_filter_state_isolation.py

State-isolation and exception regression tests for LanguageTool Russian Filter engine.
"""

from __future__ import annotations

import datetime
import pytest

from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.errors import UnsupportedGrammarFeatureError
from pylat_ru.grammar.filters.date_check import SystemClock
from pylat_ru.grammar.filters.registry import get_filter_instance
from pylat_ru.grammar.model import ExecutionState
from pylat_ru.analysis import AnalyzedSentence, AnalyzedTokenReadings, AnalyzedToken


@pytest.fixture
def clean_clock():
    """Ensure SystemClock is reset to original state before and after each test."""
    orig_override = SystemClock._override_now
    orig_test_mode = SystemClock.is_test_mode
    yield SystemClock
    SystemClock._override_now = orig_override
    SystemClock.is_test_mode = orig_test_mode


def test_system_clock_isolation(clean_clock):
    # Test that clock mock can be set and is isolated
    SystemClock._override_now = datetime.datetime(2014, 1, 1)
    SystemClock.is_test_mode = True
    
    assert SystemClock.now().year == 2014
    assert SystemClock.get_current_year() == 2014
    assert SystemClock.is_test_mode is True


def test_system_clock_restored_isolation(clean_clock):
    # This runs after test_system_clock_isolation.
    # The clean_clock fixture should have restored the state.
    assert SystemClock._override_now is None
    assert SystemClock.is_test_mode is False


def test_spelling_dependent_filter_rule_is_runnable():
    """NN_N_pril_prich[1] uses RussianSuppressMisspelledSuggestionsFilter (Task 0012)."""
    engine = RussianGrammarEngine.get_instance()
    rule = engine.get_rule("NN_N_pril_prich[1]")

    assert rule is not None
    assert rule.execution_state == ExecutionState.FILTER_0010_RUNNABLE
    assert rule.blockers == []
    assert any(
        f.class_name == "org.languagetool.rules.ru.RussianSuppressMisspelledSuggestionsFilter"
        for f in rule.filters
    )

    text = "Сегодня на ужин жареная на масле картошка."
    sent = RussianHybridDisambiguator.get_instance().disambiguate_text(text)
    sent.text = text
    matches = engine.check_rule(sent, "NN_N_pril_prich[1]")
    assert [list(m.suggestions) for m in matches] == [["жаренная"]]



def test_filter_registry_returns_match_local_instances():
    class_name = "org.languagetool.rules.ru.AdvancedSynthesizerFilter"
    first = get_filter_instance(class_name)
    second = get_filter_instance(class_name)

    first.set_synthesizer(object())
    assert first is not second
    assert second.synthesizer is None
