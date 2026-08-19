"""tests/upstream/test_rule_variant_inventory_parity.py

Validates exact physical variant count, per-rule expansion, and deterministic order
parity between Java LanguageTool PatternRuleLoader and Python GrammarLoader / Matcher
across all 892 source rules in Russian grammar.xml.
"""

import json
from pathlib import Path

import pytest

from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.matcher import expand_rule_into_variants


INVENTORY_PATH = Path(__file__).resolve().parent.parent.parent / "compat" / "rule_variant_inventory.json"


def test_variant_inventory_fixture_exists():
    assert INVENTORY_PATH.exists(), f"Missing canonical inventory at {INVENTORY_PATH}"
    data = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    assert data["source_xml_rules_total"] == 892
    assert data["java_total_physical_rules"] == 907
    assert data["python_all_compiled_variants_total"] == 907
    assert data["python_runnable_source_rules_total"] == 735
    assert data["python_runnable_compiled_variants_total"] == 747
    assert data["multi_variant_source_rules_count"] == 15
    assert data["or_generated_extra_variants"] == 15
    assert data["phrase_generated_extra_variants"] == 0
    assert data["exact_parity_across_all_892_rules"] is True
    assert len(data["discrepancies"]) == 0


def test_per_rule_variant_count_parity_against_inventory():
    data = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    java_counts = data["per_full_id_counts"]

    loader = GrammarLoader()
    rules = loader.load_default()
    assert len(rules) == 892

    for r in rules:
        assert r.full_id in java_counts, f"Source rule {r.full_id} missing from Java counts"
        expected_java_count = java_counts[r.full_id]

        variants = expand_rule_into_variants(r, global_phrases=loader.global_phrases)
        assert len(variants) == expected_java_count, (
            f"Variant count mismatch for rule {r.full_id}: "
            f"Python produced {len(variants)}, Java expected {expected_java_count}"
        )


def test_runnable_engine_variant_counts():
    loader = GrammarLoader()
    rules = loader.load_default()
    engine = RussianGrammarEngine(rules=rules, loader=loader)

    runnable_rules = engine.get_runnable_rules()
    assert len(runnable_rules) == 735

    total_runnable_variants = sum(len(engine._compiled_variants.get(r.full_id, [])) for r in runnable_rules)
    assert total_runnable_variants == 747
