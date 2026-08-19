"""tests/unit/test_grammar_advanced_inventory.py

Unit tests for deterministic Russian grammar advanced inventory generation,
schema validation, hash parity, and Task 0008 transition coverage.
"""

from __future__ import annotations

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

    # Examples Invariants
    ex_sum = data["examples_summary"]
    assert ex_sum["runnable_0007_0008_total"] == 1738
    assert ex_sum["runnable_0007_0008_incorrect"] == 871
    assert ex_sum["runnable_0007_0008_correct"] == 867
    assert ex_sum["deferred_total"] == 708
    assert ex_sum["deferred_incorrect"] == 212
    assert ex_sum["deferred_correct"] == 496
    assert ex_sum["all_rules_examples_total"] == 2446
    assert ex_sum["all_rules_examples_incorrect"] == 1083
    assert ex_sum["all_rules_examples_correct"] == 1363

    assert ex_sum["by_state"]["CORE_0007_RUNNABLE"]["total"] == 988
    assert ex_sum["by_state"]["CORE_0007_RUNNABLE"]["incorrect"] == 546
    assert ex_sum["by_state"]["CORE_0007_RUNNABLE"]["correct"] == 442

    # Exception Scope Invariants
    feat_sum = data["feature_summary"]
    assert feat_sum["exception@scope=current"]["raw_xml_occurrences"] == 0
    assert feat_sum["exception@scope=current"]["effective_occurrences"] == 905
    assert feat_sum["exception@scope=previous"]["raw_xml_occurrences"] == 167
    assert feat_sum["exception@scope=previous"]["effective_occurrences"] == 167
    assert feat_sum["exception@scope=next"]["raw_xml_occurrences"] == 203
    assert feat_sum["exception@scope=next"]["effective_occurrences"] == 203

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
