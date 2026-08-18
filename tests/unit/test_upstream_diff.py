"""Unit tests for upstream drift detection tooling."""

import copy
import json
from pathlib import Path
import pytest

from tools.upstream_diff import (
    compare_inventories,
    compute_dict_diff,
    compute_set_diff,
)


def test_compute_dict_diff_identical():
    d1 = {"a": 1, "b": "val"}
    d2 = {"a": 1, "b": "val"}
    diff = compute_dict_diff(d1, d2)
    assert diff["is_different"] is False
    assert diff["added"] == []
    assert diff["removed"] == []
    assert diff["changed"] == {}


def test_compute_dict_diff_added_removed_changed():
    d1 = {"a": 1, "b": "old", "c": 3}
    d2 = {"b": "new", "c": 3, "d": 4}
    diff = compute_dict_diff(d1, d2)
    assert diff["is_different"] is True
    assert diff["added"] == ["d"]
    assert diff["removed"] == ["a"]
    assert "b" in diff["changed"]
    assert diff["changed"]["b"] == {"pinned": "old", "target": "new"}


def test_compute_set_diff():
    s1 = {"rule1", "rule2"}
    s2 = {"rule2", "rule3"}
    diff = compute_set_diff(s1, s2)
    assert diff["is_different"] is True
    assert diff["added"] == ["rule3"]
    assert diff["removed"] == ["rule1"]


def test_compare_inventories_no_drift(compat_dir: Path):
    """Comparing an inventory against itself should detect zero drift."""
    inv_file = compat_dir / "inventory.json"
    inv = json.loads(inv_file.read_text(encoding="utf-8"))

    diff = compare_inventories(inv, copy.deepcopy(inv))
    assert diff["has_drift"] is False
    assert diff["diff_schema_version"] == "1.0.0"


def test_compare_inventories_detects_drift(compat_dir: Path):
    """Mutating target inventory must trigger drift detection with exact reporting."""
    inv_file = compat_dir / "inventory.json"
    pinned = json.loads(inv_file.read_text(encoding="utf-8"))
    target = copy.deepcopy(pinned)

    # Simulate drift
    target["summary"]["grammar_rules_total"] += 5
    target["russian_java"]["russian_specific_rules"].append("NewRussianRule")
    target["filters_resolution"]["org.languagetool.rules.ru.NewFilter"] = {
        "status": "RESOLVED_IN_TREE"
    }

    diff = compare_inventories(pinned, target)
    assert diff["has_drift"] is True
    assert diff["summary_diff"]["changed"]["grammar_rules_total"]["target"] == pinned["summary"]["grammar_rules_total"] + 5
    assert "NewRussianRule" in diff["java_rules_diff"]["russian_specific"]["added"]
    assert "org.languagetool.rules.ru.NewFilter" in diff["xml_filters_diff"]["added"]
