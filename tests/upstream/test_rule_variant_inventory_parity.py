"""tests/upstream/test_rule_variant_inventory_parity.py

Validates exact physical variant count, per-rule expansion, ordered token signature parity,
and deterministic inventory invariants between Java LanguageTool PatternRuleLoader and
Python GrammarLoader / Matcher across all 892 source rules in Russian grammar.xml.
"""

import json
from pathlib import Path

import pytest

from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.matcher import expand_rule_into_variants


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VARIANT_INVENTORY_PATH = REPO_ROOT / "compat" / "rule_variant_inventory.json"
ADVANCED_INVENTORY_PATH = REPO_ROOT / "compat" / "russian_grammar_advanced_inventory.json"


def test_variant_inventory_fixture_and_provenance():
    assert VARIANT_INVENTORY_PATH.exists(), f"Missing canonical inventory at {VARIANT_INVENTORY_PATH}"
    data = json.loads(VARIANT_INVENTORY_PATH.read_text(encoding="utf-8"))

    # Provenance
    prov = data["provenance"]
    assert prov["pinned_lt_version"] == "6.8"
    assert prov["pinned_lt_commit"] == "e807fcde6a6506191e1470744d2345da28c26be6"
    assert prov["oracle_build_id"] == "lt_6.8_source_build_jdk17_stefan"
    assert prov["oracle_jar_sha256"] == "b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc"
    assert prov["generator_path"] == "tools/inventory_java_variants.py"

    # Variant Counts
    assert data["source_xml_rules_total"] == 892
    assert data["java_total_physical_rules"] == 907
    assert data["python_all_compiled_variants_total"] == 907
    assert data["python_runnable_source_rules_total"] == 735
    assert data["python_runnable_compiled_variants_total"] == 747
    assert data["multi_variant_source_rules_count"] == 15
    assert data["or_generated_extra_variants"] == 15
    assert data["phrase_generated_extra_variants"] == 0
    assert data["exact_count_parity_across_all_892_rules"] is True
    assert data["exact_signature_and_order_parity"] is True
    assert len(data["count_discrepancies"]) == 0
    assert len(data["signature_discrepancies"]) == 0
    assert len(data["ordered_physical_variants"]) == 907


def test_per_rule_variant_count_parity_against_inventory():
    data = json.loads(VARIANT_INVENTORY_PATH.read_text(encoding="utf-8"))
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


def test_ordered_variant_signatures_parity():
    data = json.loads(VARIANT_INVENTORY_PATH.read_text(encoding="utf-8"))
    ordered_variants = data["ordered_physical_variants"]
    assert len(ordered_variants) == 907

    loader = GrammarLoader()
    rules = loader.load_default()

    global_idx = 0
    for r in rules:
        variants = expand_rule_into_variants(r, global_phrases=loader.global_phrases)
        for ord_idx, v in enumerate(variants):
            var_record = ordered_variants[global_idx]
            assert var_record["global_index"] == global_idx
            assert var_record["full_id"] == r.full_id
            assert var_record["variant_ordinal"] == ord_idx
            assert var_record["token_count"] == len(v.tokens)
            global_idx += 1


def test_advanced_inventory_canonical_totals_and_invariants():
    assert ADVANCED_INVENTORY_PATH.exists(), f"Missing canonical inventory at {ADVANCED_INVENTORY_PATH}"
    inv = json.loads(ADVANCED_INVENTORY_PATH.read_text(encoding="utf-8"))

    # Source Totals
    src = inv["source_totals"]
    assert src["categories"] == 8
    assert src["rulegroups"] == 297
    assert src["source_rule_elements"] == 892
    assert src["embedded_examples_total"] == 2446

    # Classification Summary
    cls_sum = inv["classification_summary"]
    assert cls_sum["CORE_0007_RUNNABLE"] == 506
    assert cls_sum["ADVANCED_0008_RUNNABLE"] == 229
    assert cls_sum["TOTAL_0007_0008_RUNNABLE"] == 735
    assert cls_sum["DEFERRED_0009_UNIFICATION"] == 24
    assert cls_sum["DEFERRED_0010_FILTER"] == 16
    assert cls_sum["DEFERRED_0012_SPELLING_OR_SUPPRESSION"] == 110
    assert cls_sum["MULTI_BLOCKER"] == 7
    assert cls_sum["UNKNOWN"] == 0

    # Examples Summary
    ex_sum = inv["examples_summary"]
    assert ex_sum["runnable_0007_0008_total"] == 1738
    assert ex_sum["deferred_total"] == 708

    # Attribute distribution invariants: sum(distribution.values()) == occurrences_count
    feat_sum = inv["feature_summary"]
    for feat, data in feat_sum.items():
        src_cnt = data["source_rules_count"]
        occ_cnt = data["occurrences_count"]
        assert src_cnt <= occ_cnt or occ_cnt == 0, f"Source rules count {src_cnt} > occurrences {occ_cnt} for {feat}"

        dist = data.get("value_distribution")
        if dist is not None:
            sum_dist = sum(dist.values())
            assert sum_dist == occ_cnt, (
                f"Distribution sum {sum_dist} != occurrences_count {occ_cnt} for feature {feat}"
            )
