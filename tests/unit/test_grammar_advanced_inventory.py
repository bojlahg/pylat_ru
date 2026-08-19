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
    assert prov["baseline_0007_commit"] == "b75bc4dfa84c1549d22f83388785dd9b2988f6de"
    assert prov["generator_path"] == "tools/russian_grammar_advanced_inventory.py"

    totals = data["source_totals"]
    assert totals["categories"] == 8
    assert totals["rulegroups"] == 297
    assert totals["source_rule_elements"] == 892
    assert totals["embedded_examples_total"] == 2446

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
