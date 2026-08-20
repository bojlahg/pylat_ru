"""Accounting proof that Task 0012 promotes every previously deferred XML rule.

At the Task-0011 baseline, 114 source rules (327 embedded examples) were deferred
because of ``suppress_misspelled`` markup or the spelling-dependent Russian rule
filter.  These tests re-derive that blocker set from the pinned grammar and prove
that implementing the filter plus native spelling leaves nothing deferred.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from pylat_ru.grammar.classifier import classify_rule_element
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.model import ExecutionState


ROOT = Path(__file__).resolve().parents[2]
GRAMMAR_XML = ROOT / "src/pylat_ru/resources/rules/ru/grammar.xml"
SUPPRESS_FILTER = "org.languagetool.rules.ru.RussianSuppressMisspelledSuggestionsFilter"


def _rule_elements() -> list[ET.Element]:
    return list(ET.parse(GRAMMAR_XML).getroot().iter("rule"))


def _example_count(rule_elem: ET.Element) -> int:
    return len(rule_elem.findall("example"))


def test_baseline_deferred_set_was_exactly_the_spelling_and_suppression_blockers() -> None:
    """Every Task-0011 deferred rule was blocked only by a Task-0012 dependency."""
    deferred_rules = 0
    deferred_examples = 0
    reasons: collections.Counter = collections.Counter()
    for rule_elem in _rule_elements():
        blocked = False
        for message in rule_elem.findall("message"):
            if message.attrib.get("suppress_misspelled") == "yes":
                reasons["message@suppress_misspelled"] += 1
                blocked = True
        for suggestion in rule_elem.findall(".//suggestion"):
            if suggestion.attrib.get("suppress_misspelled") == "yes":
                reasons["suggestion@suppress_misspelled"] += 1
                blocked = True
        for filt in rule_elem.findall("filter"):
            if filt.attrib.get("class") == SUPPRESS_FILTER:
                reasons[f"filter:{SUPPRESS_FILTER}"] += 1
                blocked = True
        if blocked:
            deferred_rules += 1
            deferred_examples += _example_count(rule_elem)

    assert deferred_rules == 114
    assert deferred_examples == 327
    assert reasons == collections.Counter({
        "message@suppress_misspelled": 111,
        "suggestion@suppress_misspelled": 2,
        f"filter:{SUPPRESS_FILTER}": 1,
    })


def test_no_grammar_rule_is_deferred_after_task_0012() -> None:
    counts: collections.Counter = collections.Counter()
    blockers: list = []
    elements = _rule_elements()
    for rule_elem in elements:
        state, rule_blockers = classify_rule_element(rule_elem)
        counts[state.name] += 1
        blockers.extend(rule_blockers)

    assert len(elements) == 892
    assert blockers == []
    assert counts == collections.Counter({
        "CORE_0007_RUNNABLE": 506,
        "ADVANCED_0008_RUNNABLE": 339,
        "UNIFICATION_0009_RUNNABLE": 24,
        "FILTER_0010_RUNNABLE": 23,
    })
    assert counts["DEFERRED_0012_SPELLING_OR_SUPPRESSION"] == 0
    assert counts["MULTI_BLOCKER"] == 0
    assert counts["UNKNOWN"] == 0


def test_engine_runs_every_source_rule_and_variant() -> None:
    loader = GrammarLoader()
    rules = loader.load_default()
    engine = RussianGrammarEngine(rules=rules, loader=loader)
    runnable = engine.get_runnable_rules()

    assert len(rules) == 892
    assert len(runnable) == 892
    assert all(rule.blockers == [] for rule in rules)
    assert all(
        rule.execution_state != ExecutionState.DEFERRED_0012_SPELLING_OR_SUPPRESSION
        for rule in rules
    )
    variants = sum(len(engine._compiled_variants.get(rule.full_id, [])) for rule in runnable)
    assert variants == 907


def test_promotion_is_recorded_in_deterministic_accounting() -> None:
    summary = json.loads((ROOT / "compat/compatibility.json").read_text(encoding="utf-8"))
    summary = summary["compatibility_status"]["summary"]
    assert summary["grammar_rules_total"] == 892
    assert summary["grammar_total_runnable_source_rules"] == 892
    assert summary["grammar_deferred_source_rules_total"] == 0
    assert summary["grammar_deferred_0012_source_rules_total"] == 0
    assert summary["grammar_unknown_source_rules_total"] == 0
    assert summary["grammar_examples_total"] == 2446
    assert summary["grammar_runnable_examples_total"] == 2446
    assert summary["grammar_deferred_examples_total"] == 0
    assert summary["grammar_java_physical_variants_total"] == 907
    assert summary["grammar_python_all_compiled_variants_total"] == 907
    assert summary["grammar_python_runnable_compiled_variants_total"] == 907
    assert summary["xml_filters_total"] == 7
    assert summary["xml_filters_implemented"] == 7


def test_all_seven_russian_xml_filters_are_registered() -> None:
    """Six grammar filters plus the disambiguation-only filter accepted in Task 0005."""
    from pylat_ru.disambiguation.xml_loader import KNOWN_FILTERS
    from pylat_ru.grammar.filters.registry import FILTER_CLASSES

    assert set(FILTER_CLASSES) == {
        "org.languagetool.rules.ru.AdvancedSynthesizerFilter",
        "org.languagetool.rules.ru.DateCheckFilter",
        "org.languagetool.rules.ru.FutureDateFilter",
        "org.languagetool.rules.ru.INNNumberFilter",
        "org.languagetool.rules.ru.RussianPartialPosTagFilter",
        SUPPRESS_FILTER,
    }
    assert "org.languagetool.rules.ru.NoDisambiguationRussianPartialPosTagFilter" in KNOWN_FILTERS
    assert len(set(FILTER_CLASSES) | set(KNOWN_FILTERS)) == 7


def test_unknown_filter_class_still_fails_closed() -> None:
    from pylat_ru.grammar.filters.registry import get_filter_instance

    with pytest.raises(KeyError):
        get_filter_instance("org.languagetool.rules.ru.NotARealFilter")
