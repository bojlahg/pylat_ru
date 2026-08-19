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


CANONICAL_RAW_INVENTORY_PATH = REPO_ROOT / "compat" / "inventory.json"


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

    # Examples Summary (Runtime GrammarLoader semantics)
    ex_sum = inv["examples_summary"]
    assert ex_sum["runnable_0007_0008_total"] == 1738
    assert ex_sum["runnable_0007_0008_incorrect"] == 837
    assert ex_sum["runnable_0007_0008_correct"] == 901
    assert ex_sum["deferred_total"] == 708
    assert ex_sum["deferred_incorrect"] == 202
    assert ex_sum["deferred_correct"] == 506
    assert ex_sum["all_rules_examples_total"] == 2446
    assert ex_sum["all_rules_examples_incorrect"] == 1039
    assert ex_sum["all_rules_examples_correct"] == 1407

    # Core 0007 examples regression
    core_ex = ex_sum["by_state"]["CORE_0007_RUNNABLE"]
    assert core_ex["total"] == 988
    assert core_ex["incorrect"] == 525
    assert core_ex["correct"] == 463

    # Raw markup error-like statistics
    raw_ex = ex_sum["raw_markup_error_like_examples"]
    assert raw_ex["total_examples"] == 2446
    assert raw_ex["markup_error_like_examples"] == 1083
    assert raw_ex["markup_untouched_or_correct_examples"] == 1363
    assert raw_ex["markup_with_corrections"] == 1026

    # Attribute distribution invariants: sum(raw_value_distribution.values()) == raw_xml_occurrences
    feat_sum = inv["feature_summary"]
    for feat, data in feat_sum.items():
        src_cnt = data["source_rules_count"]
        raw_occ = data["raw_xml_occurrences"]

        raw_dist = data.get("raw_value_distribution")
        if raw_dist is not None:
            sum_dist = sum(raw_dist.values())
            assert sum_dist == raw_occ, (
                f"Raw distribution sum {sum_dist} != raw_xml_occurrences {raw_occ} for feature {feat}"
            )

        pos_dist = data.get("positive_pattern_value_distribution")
        if pos_dist is not None:
            pos_occ = data["positive_pattern_occurrences"]
            sum_pos = sum(pos_dist.values())
            assert sum_pos == pos_occ, (
                f"Positive distribution sum {sum_pos} != positive_pattern_occurrences {pos_occ} for {feat}"
            )


def test_advanced_inventory_raw_xml_reconciliation_against_inventory_json():
    """Verify exact parity between advanced inventory raw counts and canonical compat/inventory.json."""
    assert ADVANCED_INVENTORY_PATH.exists()
    assert CANONICAL_RAW_INVENTORY_PATH.exists()

    inv = json.loads(ADVANCED_INVENTORY_PATH.read_text(encoding="utf-8"))
    raw_canon = json.loads(CANONICAL_RAW_INVENTORY_PATH.read_text(encoding="utf-8"))

    raw_checks = inv["raw_xml_totals"]["reconciliation_checks"]
    tag_counts = raw_canon["grammar_xml"]["xml_structure"]["tag_counts"]
    attr_counts = raw_canon["grammar_xml"]["xml_structure"]["attribute_counts"]

    # 17 mandatory reconciliation points
    assert raw_checks["match_elements_total"] == 620
    assert raw_checks["match_elements_total"] == tag_counts["match"]

    assert raw_checks["antipattern_elements_total"] == 146
    assert raw_checks["antipattern_elements_total"] == tag_counts["antipattern"]
    assert raw_checks["antipattern_rulegroup_level"] == 20
    assert raw_checks["antipattern_rule_level"] == 126

    assert raw_checks["token_chunk_occurrences"] == 21
    assert raw_checks["token_chunk_occurrences"] == attr_counts["token@chunk"]

    assert raw_checks["token_spacebefore_occurrences"] == 33
    assert raw_checks["token_spacebefore_occurrences"] == attr_counts["token@spacebefore"]

    assert raw_checks["token_skip_occurrences"] == 218
    assert raw_checks["token_skip_occurrences"] == attr_counts["token@skip"]

    assert raw_checks["token_min_occurrences"] == 30
    assert raw_checks["token_min_occurrences"] == attr_counts["token@min"]

    assert raw_checks["token_max_occurrences"] == 30
    assert raw_checks["token_max_occurrences"] == attr_counts["token@max"]

    assert raw_checks["exception_spacebefore_occurrences"] == 1
    assert raw_checks["exception_spacebefore_occurrences"] == attr_counts["exception@spacebefore"]

    assert raw_checks["exception_scope_explicit_occurrences"] == 370
    assert raw_checks["exception_scope_explicit_occurrences"] == attr_counts["exception@scope"]

    assert raw_checks["match_case_conversion_occurrences"] == 17
    assert raw_checks["match_case_conversion_occurrences"] == attr_counts["match@case_conversion"]

    assert raw_checks["match_include_skipped_occurrences"] == 68
    assert raw_checks["match_include_skipped_occurrences"] == attr_counts["match@include_skipped"]

    assert raw_checks["match_postag_occurrences"] == 136
    assert raw_checks["match_postag_occurrences"] == attr_counts["match@postag"]

    assert raw_checks["match_postag_regexp_occurrences"] == 136
    assert raw_checks["match_postag_regexp_occurrences"] == attr_counts["match@postag_regexp"]

    assert raw_checks["match_postag_replace_occurrences"] == 133
    assert raw_checks["match_postag_replace_occurrences"] == attr_counts["match@postag_replace"]

    assert raw_checks["match_regexp_match_occurrences"] == 61
    assert raw_checks["match_regexp_match_occurrences"] == attr_counts["match@regexp_match"]

    assert raw_checks["match_regexp_replace_occurrences"] == 61
    assert raw_checks["match_regexp_replace_occurrences"] == attr_counts["match@regexp_replace"]

    assert raw_checks["match_setpos_occurrences"] == 4
    assert raw_checks["match_setpos_occurrences"] == attr_counts["match@setpos"]

    assert raw_checks["pattern_raw_pos_occurrences"] == 3
    assert raw_checks["pattern_raw_pos_occurrences"] == attr_counts["pattern@raw_pos"]

    # Antipattern details
    ap_details = inv["antipattern_details"]
    assert ap_details["raw_total_antipattern_elements"] == 146
    assert ap_details["raw_rule_antipattern_elements"] == 126
    assert ap_details["raw_rulegroup_antipattern_elements"] == 20
    assert ap_details["source_rules_with_direct_antipatterns_count"] == 49
    assert ap_details["source_rules_with_inherited_antipatterns_count"] == 5
    assert ap_details["source_rules_with_any_antipatterns_count"] == 51
    assert ap_details["effective_inherited_applications"] == 59

    # Exception scope details
    exc_details = inv["raw_xml_totals"]["exception_scope_summary"]
    assert exc_details["raw_total_exceptions"] == 1275
    assert exc_details["explicit_scope_raw_occurrences"] == 370
    assert exc_details["implicit_scope_raw_occurrences"] == 905
    assert exc_details["explicit_scope_distribution"] == {"next": 203, "previous": 167}
    assert exc_details["effective_scope_distribution"] == {"current": 905, "next": 203, "previous": 167}


def test_advanced_inventory_reproducibility_metadata():
    inv = json.loads(ADVANCED_INVENTORY_PATH.read_text(encoding="utf-8"))
    prov = inv["provenance"]

    assert prov["generator_path"] == "tools/russian_grammar_advanced_inventory.py"
    assert len(prov["generator_sha256"]) == 64
    assert prov["pinned_lt_version"] == "6.8"
    assert prov["pinned_lt_commit"] == "e807fcde6a6506191e1470744d2345da28c26be6"
    assert prov["baseline_task_0007_commit"] == "b75bc4dfa84c1549d22f83388785dd9b2988f6de"
    assert prov["grammar_xml_path"] == "third_party/languagetool/languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/grammar.xml"
    assert prov["grammar_xml_sha256"] == "e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec"
    assert prov["grammar_xml_size_bytes"] == 1194903



