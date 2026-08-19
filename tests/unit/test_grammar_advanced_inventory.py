"""tests/unit/test_grammar_advanced_inventory.py

Unit tests for deterministic Russian grammar advanced inventory generation,
schema validation, hash parity, and Task 0008 transition coverage.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import pytest

from tools.russian_grammar_advanced_inventory import (
    ADVANCED_INVENTORY_OUTPUT_PATH,
    generate_advanced_inventory,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_grammar_advanced_inventory_byte_exact_regeneration():
    """Verify that regenerating the advanced inventory produces byte-for-byte identical output."""
    assert ADVANCED_INVENTORY_OUTPUT_PATH.is_file(), f"Missing {ADVANCED_INVENTORY_OUTPUT_PATH}"
    committed_text = ADVANCED_INVENTORY_OUTPUT_PATH.read_text(encoding="utf-8")

    fresh_inv = generate_advanced_inventory()
    fresh_text = json.dumps(fresh_inv, ensure_ascii=False, indent=2) + "\n"

    assert fresh_text == committed_text, "Regenerated advanced inventory differs from committed JSON"


def test_grammar_advanced_inventory_structure_counts():
    """Verify key counts and invariant totals in the advanced inventory."""
    data = json.loads(ADVANCED_INVENTORY_OUTPUT_PATH.read_text(encoding="utf-8"))

    assert data["schema_version"] == "1.0.0"
    prov = data["provenance"]
    assert prov["pinned_lt_version"] == "6.8"
    assert prov["pinned_lt_commit"] == "e807fcde6a6506191e1470744d2345da28c26be6"
    assert prov["baseline_task_0007_commit"] == "b75bc4dfa84c1549d22f83388785dd9b2988f6de"
    assert prov["generator_path"] == "tools/russian_grammar_advanced_inventory.py"

    totals = data["source_totals"]
    assert totals["categories"] == 8
    assert totals["rulegroups"] == 297
    assert totals["source_rule_elements"] == 892
    assert totals["embedded_examples_total"] == 2446

    # Baseline 0007 Invariants
    base_0007 = data["baseline_task_0007"]
    assert base_0007["CORE_0007_RUNNABLE"] == 506
    assert base_0007["DEFERRED_0008_ADVANCED_MATCHING"] == 157
    assert base_0007["DEFERRED_0009_UNIFICATION"] == 8
    assert base_0007["DEFERRED_0010_FILTER"] == 64
    assert base_0007["MULTI_BLOCKER"] == 157
    assert base_0007["UNRECOGNIZED"] == 0

    # Transitions Invariants
    transitions = data["task_0007_to_0008_transitions"]
    assert sum(transitions.values()) == 892
    assert transitions["CORE_0007_RUNNABLE -> CORE_0007_RUNNABLE"] == 506
    assert transitions["DEFERRED_0008_ADVANCED_MATCHING -> ADVANCED_0008_RUNNABLE"] == 157
    assert transitions["DEFERRED_0010_FILTER -> ADVANCED_0008_RUNNABLE"] == 57
    assert transitions["MULTI_BLOCKER -> ADVANCED_0008_RUNNABLE"] == 15

    # Provenance fields
    assert prov["grammar_xml_path"] == "third_party/languagetool/languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/grammar.xml"
    assert prov["grammar_xml_sha256"] == "e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec"
    assert prov["grammar_xml_size_bytes"] == 1194903

    # Classification counts
    summary = data["classification_summary"]
    assert summary["UNKNOWN"] == 0
    assert summary["CORE_0007_RUNNABLE"] == 506
    assert summary["ADVANCED_0008_RUNNABLE"] == 229
    assert summary["TOTAL_0007_0008_RUNNABLE"] == 735
    assert summary["DEFERRED_0009_UNIFICATION"] == 24
    assert summary["DEFERRED_0010_FILTER"] == 16
    assert summary["DEFERRED_0012_SPELLING_OR_SUPPRESSION"] == 110
    assert summary["MULTI_BLOCKER"] == 7

    # Assert sum of all rule states equals 892
    rule_states_sum = (
        summary["CORE_0007_RUNNABLE"]
        + summary["ADVANCED_0008_RUNNABLE"]
        + summary["DEFERRED_0009_UNIFICATION"]
        + summary["DEFERRED_0010_FILTER"]
        + summary["DEFERRED_0012_SPELLING_OR_SUPPRESSION"]
        + summary["MULTI_BLOCKER"]
        + summary["UNKNOWN"]
    )
    assert rule_states_sum == 892

    # Examples Invariants (Runtime GrammarLoader semantics)
    ex_sum = data["examples_summary"]
    assert ex_sum["runnable_0007_0008_total"] == 1738
    assert ex_sum["runnable_0007_0008_incorrect"] == 837
    assert ex_sum["runnable_0007_0008_correct"] == 901
    assert ex_sum["deferred_total"] == 708
    assert ex_sum["deferred_incorrect"] == 202
    assert ex_sum["deferred_correct"] == 506
    assert ex_sum["all_rules_examples_total"] == 2446
    assert ex_sum["all_rules_examples_incorrect"] == 1039
    assert ex_sum["all_rules_examples_correct"] == 1407

    # Explicit correction fields in runtime summary
    assert ex_sum["correction_attribute_present"] == 1026
    assert ex_sum["correction_value_non_empty"] == 871
    assert ex_sum["correction_value_empty"] == 155

    assert ex_sum["by_state"]["CORE_0007_RUNNABLE"]["total"] == 988
    assert ex_sum["by_state"]["CORE_0007_RUNNABLE"]["incorrect"] == 525
    assert ex_sum["by_state"]["CORE_0007_RUNNABLE"]["correct"] == 463
    assert ex_sum["by_state"]["CORE_0007_RUNNABLE"]["correction_attribute_present"] == 519
    assert ex_sum["by_state"]["CORE_0007_RUNNABLE"]["correction_value_non_empty"] == 454
    assert ex_sum["by_state"]["CORE_0007_RUNNABLE"]["correction_value_empty"] == 65

    # Raw markup error-like statistics (markers, corrections, triggers_error)
    raw_mk = ex_sum["raw_markup_error_like_examples"]
    assert raw_mk["total_examples"] == 2446
    assert raw_mk["markup_error_like_examples"] == 1083
    assert raw_mk["markup_untouched_or_correct_examples"] == 1363
    assert raw_mk["correction_attribute_present"] == 1026
    assert raw_mk["correction_value_non_empty"] == 871
    assert raw_mk["correction_value_empty"] == 155

    # Exception Scope Invariants
    feat_sum = data["feature_summary"]
    assert feat_sum["exception@scope=current"]["raw_xml_occurrences"] == 0
    assert feat_sum["exception@scope=current"]["effective_occurrences"] == 905
    assert feat_sum["exception@scope=previous"]["raw_xml_occurrences"] == 167
    assert feat_sum["exception@scope=previous"]["effective_occurrences"] == 167
    assert feat_sum["exception@scope=next"]["raw_xml_occurrences"] == 203
    assert feat_sum["exception@scope=next"]["effective_occurrences"] == 203

    # Feature blocker overlap structure check
    for feat, feat_data in feat_sum.items():
        assert "remaining_blocker_target_tasks" in feat_data
        assert "remaining_blocker_features" in feat_data
        assert "execution_state_distribution" in feat_data

    # Java loader expansions
    java_loader = data["java_loader_expansion"]
    assert java_loader["total_physical_rules"] == 907
    assert java_loader["unique_full_ids"] == 892
    assert java_loader["multi_variant_rules_count"] == 15
    assert java_loader["max_variants_per_rule"] == 2

    # Rules records
    rules = data["rules"]
    assert len(rules) == 892
    seen_ids = set()
    for idx, r in enumerate(rules):
        assert r["source_order"] == idx
        assert r["full_id"]
        assert r["category_id"]
        assert r["task_0008_state"] in (
            "CORE_0007_RUNNABLE",
            "ADVANCED_0008_RUNNABLE",
            "DEFERRED_0009_UNIFICATION",
            "DEFERRED_0010_FILTER",
            "DEFERRED_0012_SPELLING_OR_SUPPRESSION",
            "MULTI_BLOCKER",
        )
        if r["task_0008_state"] in ("CORE_0007_RUNNABLE", "ADVANCED_0008_RUNNABLE"):
            assert len(r["remaining_blockers_after_0008"]) == 0
        else:
            assert len(r["remaining_blockers_after_0008"]) > 0
        seen_ids.add(r["full_id"])

    assert len(seen_ids) == 892


def test_trusted_java_variant_evidence_fail_closed_validation(tmp_path: Path) -> None:
    """Validate that load_trusted_java_variant_evidence() is fail-closed and strictly manifest-bound."""
    from tools.russian_grammar_advanced_inventory import load_trusted_java_variant_evidence

    # Base valid manifests
    canonical_inv = REPO_ROOT / "compat" / "rule_variant_inventory.json"
    canonical_oracle = REPO_ROOT / "compat" / "oracle_manifest.json"

    # 1. Canonical loading must succeed
    res = load_trusted_java_variant_evidence(canonical_inv, canonical_oracle)
    assert res["total_physical_rules"] == 907
    assert res["unique_full_ids"] == 892
    assert res["multi_variant_rules_count"] == 15
    assert res["provenance"]["oracle_build_id"] == "lt_6.8_source_build_jdk17_stefan"
    assert res["provenance"]["oracle_jar_sha256"] == "b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc"

    # Prepare base data
    base_inv_data = json.loads(canonical_inv.read_text(encoding="utf-8"))

    # 2. Wrong build_id raises ValueError
    bad_data = copy.deepcopy(base_inv_data)
    bad_data["provenance"]["oracle_build_id"] = "nonexistent_untrusted_build"
    inv_file = tmp_path / "inv_bad_build.json"
    inv_file.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="Untrusted or missing oracle_build_id"):
        load_trusted_java_variant_evidence(inv_file, canonical_oracle)

    # 3. Wrong JAR SHA raises ValueError
    bad_data = copy.deepcopy(base_inv_data)
    bad_data["provenance"]["oracle_jar_sha256"] = "0000000000000000000000000000000000000000000000000000000000000000"
    inv_file = tmp_path / "inv_bad_sha.json"
    inv_file.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="JAR SHA-256 mismatch"):
        load_trusted_java_variant_evidence(inv_file, canonical_oracle)

    # 4. Wrong pinned version raises ValueError
    bad_data = copy.deepcopy(base_inv_data)
    bad_data["provenance"]["pinned_lt_version"] = "5.9"
    inv_file = tmp_path / "inv_bad_ver.json"
    inv_file.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid pinned_lt_version"):
        load_trusted_java_variant_evidence(inv_file, canonical_oracle)

    # 5. Wrong pinned commit raises ValueError
    bad_data = copy.deepcopy(base_inv_data)
    bad_data["provenance"]["pinned_lt_commit"] = "badcommit1234567890"
    inv_file = tmp_path / "inv_bad_commit.json"
    inv_file.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid pinned_lt_commit"):
        load_trusted_java_variant_evidence(inv_file, canonical_oracle)

    # 6. Missing required variant-count field raises ValueError
    bad_data = copy.deepcopy(base_inv_data)
    del bad_data["java_total_physical_rules"]
    inv_file = tmp_path / "inv_missing_field.json"
    inv_file.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="Missing required field 'java_total_physical_rules'"):
        load_trusted_java_variant_evidence(inv_file, canonical_oracle)

    # 7. Missing required multi_variant_source_rules_count field raises ValueError
    bad_data = copy.deepcopy(base_inv_data)
    del bad_data["multi_variant_source_rules_count"]
    inv_file = tmp_path / "inv_missing_multi_field.json"
    inv_file.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="Missing required field 'multi_variant_source_rules_count'"):
        load_trusted_java_variant_evidence(inv_file, canonical_oracle)

