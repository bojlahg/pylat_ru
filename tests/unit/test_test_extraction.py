"""Unit tests for upstream test extraction and fixture generation."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest

from tools.extract_upstream_tests import (
    extract_grammar_examples,
    inventory_junit_tests,
    parse_example_element,
)


def test_parse_example_element_incorrect_with_marker():
    """Test parsing an incorrect example element with marker."""
    xml_str = '<example type="incorrect">Это <marker>ошибка</marker> в слове.</example>'
    elem = ET.fromstring(xml_str)
    parsed = parse_example_element(
        example_elem=elem,
        rule_id="RULE_1",
        rule_name="Rule 1",
        rulegroup_id="RG_1",
        rulegroup_name="Rule Group 1",
        category_id="CAT_1",
        category_name="Category 1",
        example_index=0,
    )

    assert parsed["type"] == "incorrect"
    assert parsed["text"] == "Это ошибка в слове."
    assert parsed["has_marker"] is True
    assert parsed["marker_text"] == "ошибка"
    assert parsed["marker_offset"] == 4
    assert parsed["marker_length"] == 6
    assert parsed["corrections"] == []


def test_parse_example_element_with_corrections():
    """Test parsing an incorrect example with corrections."""
    xml_str = '<example type="incorrect" correction="исправление|вариант">Это <marker>баг</marker>.</example>'
    elem = ET.fromstring(xml_str)
    parsed = parse_example_element(
        example_elem=elem,
        rule_id="RULE_2",
        rule_name="Rule 2",
        rulegroup_id=None,
        rulegroup_name=None,
        category_id="CAT_1",
        category_name="Category 1",
        example_index=0,
    )

    assert parsed["type"] == "incorrect"
    assert parsed["text"] == "Это баг."
    assert parsed["marker_text"] == "баг"
    assert parsed["marker_offset"] == 4
    assert parsed["marker_length"] == 3
    assert parsed["corrections"] == ["исправление", "вариант"]


def test_parse_example_element_correct():
    """Test parsing a correct example without markers."""
    xml_str = "<example type=\"correct\">Это правильное предложение.</example>"
    elem = ET.fromstring(xml_str)
    parsed = parse_example_element(
        example_elem=elem,
        rule_id="RULE_3",
        rule_name="Rule 3",
        rulegroup_id=None,
        rulegroup_name=None,
        category_id="CAT_1",
        category_name="Category 1",
        example_index=1,
    )

    assert parsed["type"] == "correct"
    assert parsed["text"] == "Это правильное предложение."
    assert parsed["has_marker"] is False
    assert parsed["marker_offset"] is None
    assert parsed["marker_length"] is None


def test_extract_grammar_examples_fixture(fixtures_dir: Path):
    """Test grammar examples extraction from sample fixture."""
    res = extract_grammar_examples(fixtures_dir / "sample_grammar.xml")
    assert res["summary"]["total_examples"] == 6
    assert res["summary"]["incorrect_examples"] == 3
    assert res["summary"]["correct_examples"] == 3
    assert len(res["examples"]) == 6


def test_extracted_grammar_examples_pinned_upstream(compat_dir: Path):
    """Verify extracted_grammar_examples.json has correct structure and counts."""
    extracted_file = compat_dir / "extracted_grammar_examples.json"
    assert extracted_file.is_file()

    data = json.loads(extracted_file.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0.0"
    assert data["summary"]["total_examples"] == 2446
    assert data["summary"]["incorrect_examples"] == 1083
    assert data["summary"]["correct_examples"] == 1363
    assert len(data["examples"]) == 2446


def test_inventory_junit_tests_pinned_upstream(third_party_dir: Path, compat_dir: Path):
    """Verify JUnit test inventory on pinned upstream tree."""
    res = inventory_junit_tests(third_party_dir)
    assert res["total_test_files"] == 18
    assert res["total_test_methods"] == 21

    # Check that key tests are catalogued
    file_names = [tf["file_name"] for tf in res["test_files"]]
    assert "RussianPatternRuleTest.java" in file_names
    assert "RussianTaggerTest.java" in file_names
    assert "RussianSynthesizerTest.java" in file_names
    assert "RussianSRXSentenceTokenizerTest.java" in file_names
    assert "DateCheckFilterTest.java" in file_names
