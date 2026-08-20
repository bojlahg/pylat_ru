"""tests/unit/test_filter_state_isolation.py

State-isolation and exception regression tests for LanguageTool Russian Filter engine.
"""

from __future__ import annotations

import datetime
import pytest

from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.errors import UnsupportedGrammarFeatureError
from pylat_ru.grammar.filters.date_check import SystemClock
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


def test_spelling_dependency_exception():
    engine = RussianGrammarEngine.get_instance()
    
    # NN_N_pril_prich[1] is the spelling-filtered rule (deferred to Task 0012)
    # Ensure checking it raises UnsupportedGrammarFeatureError naming the task 0012 spelling dependency
    sent = AnalyzedSentence([])
    
    with pytest.raises(UnsupportedGrammarFeatureError) as exc_info:
        engine.check_rule(sent, "NN_N_pril_prich[1]")
        
    assert "0012" in str(exc_info.value)
    assert "RussianSuppressMisspelledSuggestionsFilter" in str(exc_info.value)
