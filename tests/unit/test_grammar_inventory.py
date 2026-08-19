"""tests/unit/test_grammar_inventory.py

Unit tests for deterministic Russian grammar core inventory generation,
schema validation, hash parity, and complete classification coverage.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from tools.russian_grammar_core_inventory import (
    INVENTORY_OUTPUT_PATH,
    generate_inventory,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_grammar_core_inventory_byte_exact_regeneration():
    """Verify that regenerating the inventory produces byte-for-byte identical output."""
    assert INVENTORY_OUTPUT_PATH.is_file(), f"Missing {INVENTORY_OUTPUT_PATH}"
    committed_text = INVENTORY_OUTPUT_PATH.read_text(encoding="utf-8")

    fresh_inv = generate_inventory()
    fresh_text = json.dumps(fresh_inv, ensure_ascii=False, indent=2) + "\n"

    assert fresh_text == committed_text, "Regenerated inventory differs from committed JSON"


def test_grammar_core_inventory_structure_counts():
    """Verify key counts and invariant totals in the inventory."""
    data = json.loads(INVENTORY_OUTPUT_PATH.read_text(encoding="utf-8"))

    assert data["schema_version"] == "1.0.0"
    assert data["pinned_upstream"]["tag"] == "v6.8"
    assert data["pinned_upstream"]["commit"] == "e807fcde6a6506191e1470744d2345da28c26be6"

    grammar = data["grammar"]
    assert grammar["categories_count"] == 8
    assert grammar["rulegroups_count"] == 297
    assert grammar["rules_total_count"] == 892
    assert grammar["direct_rules_count"] == 180
    assert grammar["grouped_rules_count"] == 712

    # Examples counts
    tot_ex = grammar["total_examples_counts"]
    assert tot_ex["total"] == 2446
    assert tot_ex["incorrect"] == 1083
    assert tot_ex["correct"] == 1363
    assert tot_ex["with_correction"] == 1026

    # Classification counts
    summary = grammar["classification_summary"]
    assert "UNKNOWN" not in summary or summary["UNKNOWN"] == 0
    assert summary["CORE_0007_RUNNABLE"] == 506
    assert sum(summary.values()) == 892

    # Verify all rules have non-empty full IDs and valid source order
    rules = grammar["rules"]
    assert len(rules) == 892
    seen_ids = set()
    for idx, r in enumerate(rules):
        assert r["source_order_index"] == idx
        assert r["full_rule_id"]
        assert r["category_id"]
        assert r["execution_state"] in (
            "CORE_0007_RUNNABLE",
            "DEFERRED_0008_ADVANCED_MATCHING",
            "DEFERRED_0009_UNIFICATION",
            "DEFERRED_0010_FILTER",
            "DEFERRED_0012_SPELLING_OR_SUPPRESSION",
            "MULTI_BLOCKER",
        )
        if r["execution_state"] == "CORE_0007_RUNNABLE":
            assert len(r["blockers"]) == 0
        else:
            assert len(r["blockers"]) > 0
        seen_ids.add(r["full_rule_id"])

    assert len(seen_ids) == 892

    # Chunker inventory counts
    chunker = data["chunker"]
    assert chunker["regexes1_count"] == 21
    assert chunker["regexes2_count"] == 3
    assert chunker["total_chunker_regexes_count"] == 24
    assert len(chunker["filter_tags"]) == 8
    assert len(chunker["phrase_types"]) == 9
