"""Unit tests for SRX rule parsing, adaptation, deterministic ordering, and error handling."""

import json
from pathlib import Path
import pytest

from pylat_ru.tokenization.errors import (
    SRXFormatError,
    SRXRuleCompilationError,
    UnsupportedSRXFeatureError,
)
from pylat_ru.tokenization.srx import (
    SRXRule,
    SRXRuleManager,
    adapt_java_regex,
    load_russian_srx_rule_manager,
)
from tools.russian_srx_inventory import analyze_srx


def test_adapt_java_regex():
    """Verify conversion of Java regex flags to Python inline flags."""
    assert adapt_java_regex("(?U)\\b[А-ЯЁ]\\.\\s") == "(?u)\\b[А-ЯЁ]\\.\\s"
    assert adapt_java_regex("(?iu)FRITZ!") == "(?iu)FRITZ!"
    assert adapt_java_regex("(?iU)FRITZ!") == "(?iu)FRITZ!"
    assert adapt_java_regex("(?Ui)FRITZ!") == "(?iu)FRITZ!"
    assert adapt_java_regex("") == ""


def test_srx_rule_compilation_and_failure():
    """Verify SRXRule compilation succeeds on valid patterns and raises SRXRuleCompilationError on bad patterns."""
    rule = SRXRule(
        is_break=True,
        before_pattern_str="(?U)\\p{L}\\.",
        after_pattern_str="(?U)\\p{L}\\.",
        group_name="Russian",
        rule_index=6,
    )
    assert rule.is_break is True
    assert rule.before_pattern is not None
    assert rule.after_pattern is not None

    with pytest.raises(SRXRuleCompilationError):
        SRXRule(
            is_break=True,
            before_pattern_str="(?P<invalid",
            after_pattern_str="",
            group_name="Test",
            rule_index=1,
        )


def test_srx_inventory_and_rules_exact_generation(third_party_dir: Path):
    """Verify segment.srx generates exact expected inventory and counts without drift."""
    srx_path = (
        third_party_dir
        / "languagetool-core"
        / "src"
        / "main"
        / "resources"
        / "org"
        / "languagetool"
        / "resource"
        / "segment.srx"
    )
    inventory, runtime_rules = analyze_srx(srx_path)

    assert inventory["srx_header"]["cascade"] == "yes"
    assert inventory["mappings"]["ru_two"]["total_rules_count"] == 45
    assert inventory["mappings"]["ru_two"]["break_yes_count"] == 12
    assert inventory["mappings"]["ru_two"]["break_no_count"] == 33

    assert inventory["mappings"]["ru_one"]["total_rules_count"] == 44
    assert inventory["mappings"]["ru_one"]["break_yes_count"] == 11
    assert inventory["mappings"]["ru_one"]["break_no_count"] == 33

    assert inventory["regex_feature_inventory"]["unsupported_features_count"] == 0
    assert "Pe" in inventory["regex_feature_inventory"]["unicode_properties_used"]
    assert "Ll" in inventory["regex_feature_inventory"]["unicode_properties_used"]
    assert "Lu" in inventory["regex_feature_inventory"]["unicode_properties_used"]
    assert "L" in inventory["regex_feature_inventory"]["unicode_properties_used"]


def test_load_russian_srx_rule_manager_modes():
    """Verify load_russian_srx_rule_manager loads ru_two and ru_one correctly."""
    mgr_two = load_russian_srx_rule_manager("ru_two")
    mgr_one = load_russian_srx_rule_manager("ru_one")

    assert len(mgr_two.break_rules) == 12
    assert len(mgr_one.break_rules) == 11

    with pytest.raises(UnsupportedSRXFeatureError, match="Unsupported SRX Russian configuration mode"):
        load_russian_srx_rule_manager("ru_unknown_mode")


def test_load_russian_srx_rule_manager_missing_file(tmp_path: Path):
    """Verify missing file raises SRXFormatError."""
    fake_path = tmp_path / "non_existent.json"
    with pytest.raises(SRXFormatError, match="SRX rules file not found"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=fake_path)
