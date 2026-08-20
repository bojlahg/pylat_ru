"""tests/unit/test_grammar_unification_inventory.py

Unit tests for Task 0009 unification inventory generation, schema conformance,
rule state transitions, and counts.
"""

import json
from pathlib import Path
import pytest

from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.model import ExecutionState
from tools.russian_grammar_unification_inventory import generate_unification_inventory


def test_grammar_unification_inventory_file_consistency():
    """Verify compat/russian_grammar_unification_inventory.json exists and is up to date."""
    compat_path = Path("compat/russian_grammar_unification_inventory.json")
    assert compat_path.is_file(), f"Inventory file missing: {compat_path}"

    disk_data = json.loads(compat_path.read_text(encoding="utf-8"))
    fresh_data = generate_unification_inventory()

    assert disk_data == fresh_data, "compat/russian_grammar_unification_inventory.json out of date"


def test_grammar_unification_inventory_schema_and_counts():
    """Verify inventory counts, schema versions, context split, and transitions."""
    data = generate_unification_inventory()

    assert data["schema_version"] == "1.0.0"
    prov = data["provenance"]
    assert prov["pinned_lt_version"] == "6.8"
    assert prov["pinned_lt_commit"] == "e807fcde6a6506191e1470744d2345da28c26be6"
    assert prov["baseline_task_0008_commit"] == "5a2f4c032609ee2ce371ca5bb886883a186a3d83"

    src_totals = data["source_totals"]
    assert src_totals["categories"] == 8
    assert src_totals["rulegroups"] == 297
    assert src_totals["source_rule_elements"] == 892
    assert src_totals["embedded_examples_total"] == 2446

    # Context split verification
    ctx_split = data["context_split"]
    assert ctx_split["root_level_unifications_count"] == 8
    assert ctx_split["category_level_unifications_count"] == 0
    assert ctx_split["rulegroup_level_unifications_count"] == 0
    assert ctx_split["rule_level_unifications_count"] == 0
    assert ctx_split["rule_local_unify_scopes_count"] == 28
    assert ctx_split["rule_local_unify_ignore_scopes_count"] == 12
    assert len(ctx_split["configuration_definitions"]) == 8

    # Disposition and transitions verification
    disposition = data["task_0009_disposition"]
    assert disposition["runnable_source_rules_total"] == 759
    assert disposition["deferred_source_rules_total"] == 133
    assert disposition["unknown_count"] == 0

    state_counts = disposition["state_counts"]
    assert state_counts["CORE_0007_RUNNABLE"] == 506
    assert state_counts["ADVANCED_0008_RUNNABLE"] == 229
    assert state_counts["UNIFICATION_0009_RUNNABLE"] == 24
    assert state_counts["DEFERRED_0010_FILTER"] == 20
    assert state_counts["DEFERRED_0012_SPELLING_OR_SUPPRESSION"] == 110
    assert state_counts["MULTI_BLOCKER"] == 3

    transitions = data["task_0008_to_0009_transitions"]
    assert transitions["CORE_0007_RUNNABLE -> CORE_0007_RUNNABLE"] == 506
    assert transitions["ADVANCED_0008_RUNNABLE -> ADVANCED_0008_RUNNABLE"] == 229
    assert transitions["DEFERRED_0009_UNIFICATION -> UNIFICATION_0009_RUNNABLE"] == 24
    assert transitions["MULTI_BLOCKER -> DEFERRED_0010_FILTER"] == 4
    assert transitions["DEFERRED_0010_FILTER -> DEFERRED_0010_FILTER"] == 16
    assert transitions["DEFERRED_0012_SPELLING_OR_SUPPRESSION -> DEFERRED_0012_SPELLING_OR_SUPPRESSION"] == 110
    assert transitions["MULTI_BLOCKER -> MULTI_BLOCKER"] == 3

    # Rule records identity and uniqueness verification
    rules_records = data["rules"]
    assert len(rules_records) == 892
    full_ids = [r["full_id"] for r in rules_records]
    assert len(set(full_ids)) == 892, f"Duplicate full IDs found: {len(full_ids) - len(set(full_ids))}"

    # Verify no duplicates like dlitelnij_dlinnij[1] or Vazhno_chto_etogo[1]
    assert full_ids.count("dlitelnij_dlinnij[1]") == 1
    assert full_ids.count("dlitelnij_dlinnij[2]") == 1
    assert full_ids.count("Vazhno_chto_etogo[1]") == 1
    assert full_ids.count("Vazhno_chto_etogo[2]") == 1

    # Unification rules specific inventory
    uni_rules = [r for r in rules_records if r["has_unify"]]
    assert len(uni_rules) == 28
    pure_uni = [r for r in uni_rules if r["state_task_0009"] == "UNIFICATION_0009_RUNNABLE"]
    assert len(pure_uni) == 24
    filter_uni = [r for r in uni_rules if r["state_task_0009"] == "DEFERRED_0010_FILTER"]
    assert len(filter_uni) == 4


def test_grammar_unification_invariants():
    """Verify structural invariants across loaded rules and classification."""
    loader = GrammarLoader()
    rules = loader.load_default()
    assert len(rules) == 892

    runnable_0007 = [r for r in rules if r.execution_state == ExecutionState.CORE_0007_RUNNABLE]
    runnable_0008 = [r for r in rules if r.execution_state == ExecutionState.ADVANCED_0008_RUNNABLE]
    runnable_0009 = [r for r in rules if r.execution_state == ExecutionState.UNIFICATION_0009_RUNNABLE]
    deferred_0010 = [r for r in rules if r.execution_state == ExecutionState.DEFERRED_0010_FILTER]
    deferred_0012 = [r for r in rules if r.execution_state == ExecutionState.DEFERRED_0012_SPELLING_OR_SUPPRESSION]
    multi_blocker = [r for r in rules if r.execution_state == ExecutionState.MULTI_BLOCKER]

    assert len(runnable_0007) == 506
    assert len(runnable_0008) == 229
    assert len(runnable_0009) == 24
    assert len(deferred_0010) == 20
    assert len(deferred_0012) == 110
    assert len(multi_blocker) == 3

    assert len(runnable_0007) + len(runnable_0008) + len(runnable_0009) == 759
    assert len(deferred_0010) + len(deferred_0012) + len(multi_blocker) == 133
    assert 759 + 133 == 892
