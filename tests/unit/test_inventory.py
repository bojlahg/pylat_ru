"""Unit tests for upstream inventory tooling."""

import json
from pathlib import Path
import pytest

from tools.upstream_inventory import (
    analyze_disambiguation_xml,
    analyze_grammar_xml,
    analyze_russian_java,
    analyze_xml_structure,
    generate_inventory,
    resolve_filters,
    scan_resource_files,
)


def test_analyze_xml_structure_fixture(fixtures_dir: Path):
    """Test XML structural analyzer on sample fixture."""
    import xml.etree.ElementTree as ET
    tree = ET.parse(fixtures_dir / "sample_grammar.xml")
    res = analyze_xml_structure(tree.getroot())

    assert "tag_counts" in res
    assert "attribute_counts" in res
    assert res["tag_counts"]["rule"] == 3
    assert res["tag_counts"]["rulegroup"] == 1
    assert res["tag_counts"]["category"] == 1
    assert res["tag_counts"]["filter"] == 1
    assert res["tag_counts"]["unification"] == 1
    assert res["attribute_counts"]["category@id"] == 1
    assert res["attribute_counts"]["filter@class"] == 1


def test_analyze_grammar_xml_fixture(fixtures_dir: Path):
    """Test grammar.xml analysis on fixture."""
    grammar_res = analyze_grammar_xml(fixtures_dir / "sample_grammar.xml")

    assert grammar_res["category_count"] == 1
    assert grammar_res["rulegroup_count"] == 1
    assert grammar_res["total_rule_count"] == 3
    assert grammar_res["examples_summary"]["total_examples"] == 6
    assert grammar_res["examples_summary"]["incorrect_examples"] == 3
    assert grammar_res["examples_summary"]["correct_examples"] == 3
    assert len(grammar_res["unifications"]) == 1
    assert "org.languagetool.rules.ru.DateCheckFilter" in grammar_res["filters_referenced"]


def test_analyze_disambiguation_xml_fixture(fixtures_dir: Path):
    """Test disambiguation.xml analysis on fixture."""
    disambig_res = analyze_disambiguation_xml(fixtures_dir / "sample_disambiguation.xml")

    assert disambig_res["rulegroup_count"] == 1
    assert disambig_res["total_rule_count"] == 2
    assert disambig_res["disambig_actions"] == {"add": 1, "remove": 1}
    assert "org.languagetool.rules.ru.NoDisambiguationRussianPartialPosTagFilter" in disambig_res["filters_referenced"]


def test_resolve_filters_known_and_unknown(third_party_dir: Path):
    """Test filter resolution against Java sources in upstream tree."""
    filters = {
        "org.languagetool.rules.ru.DateCheckFilter",
        "org.languagetool.rules.ru.NonExistentFakeFilter",
    }
    res = resolve_filters(filters, third_party_dir)

    assert res["org.languagetool.rules.ru.DateCheckFilter"]["status"] == "RESOLVED_IN_TREE"
    assert res["org.languagetool.rules.ru.DateCheckFilter"]["source_file"] is not None

    assert res["org.languagetool.rules.ru.NonExistentFakeFilter"]["status"] == "UNRESOLVED_UNKNOWN"
    assert res["org.languagetool.rules.ru.NonExistentFakeFilter"]["source_file"] is None


def test_generate_inventory_full_tree(third_party_dir: Path, compat_dir: Path):
    """Test full inventory generation against pinned upstream tree."""
    inv = generate_inventory(third_party_dir)

    assert inv["schema_version"] == "1.0.0"
    assert inv["pinned_upstream"]["tag"] == "v6.8"
    assert inv["pinned_upstream"]["commit"] == "e807fcde6a6506191e1470744d2345da28c26be6"

    summary = inv["summary"]
    assert summary["grammar_rules_total"] == 892
    assert summary["grammar_rulegroups_total"] == 297
    assert summary["grammar_categories_total"] == 8
    assert summary["grammar_examples_total"] == 2446
    assert summary["disambiguation_rules_total"] == 77
    assert summary["disambiguation_rulegroups_total"] == 11
    assert summary["enabled_java_rules_total"] == 23
    assert summary["russian_specific_java_rules_total"] == 13
    assert summary["generic_java_rules_total"] == 10
    assert summary["xml_filters_total"] == 7
    assert summary["unresolved_filters_count"] == 0

    # Ensure all 7 filters are resolved in tree
    for f_cls, f_info in inv["filters_resolution"].items():
        assert f_info["status"] == "RESOLVED_IN_TREE"


def test_inventory_file_consistency(compat_dir: Path):
    """Verify compat/inventory.json matches generate_inventory output."""
    inv_path = compat_dir / "inventory.json"
    assert inv_path.is_file()
    saved = json.loads(inv_path.read_text(encoding="utf-8"))
    assert saved["summary"]["grammar_rules_total"] == 892
    assert saved["summary"]["unresolved_filters_count"] == 0
