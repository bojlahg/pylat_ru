"""Unit tests for SRX rule parsing, adaptation, deterministic ordering, and error handling."""

import json
from pathlib import Path
import pytest
import regex

from pylat_ru.tokenization.errors import (
    SRXFormatError,
    SRXRuleCompilationError,
    UnsupportedSRXFeatureError,
)
from pylat_ru.tokenization.srx import (
    SRXRule,
    SRXRuleManager,
    SRXRuleMatcher,
    SRXSegmenter,
    adapt_java_regex,
    finitize,
    load_russian_srx_rule_manager,
    remove_block_quotes,
)
from tools.russian_srx_inventory import (
    EXPECTED_SRX_HASH,
    analyze_srx,
    resolve_language_rules_for_code,
)


def test_adapt_java_regex():
    """Verify conversion of Java regex flags to Python inline flags."""
    assert adapt_java_regex("(?U)\\b[А-ЯЁ]\\.\\s") == "(?u)\\b[А-ЯЁ]\\.\\s"
    assert adapt_java_regex("(?iu)FRITZ!") == "(?iu)FRITZ!"
    assert adapt_java_regex("(?iU)FRITZ!") == "(?iu)FRITZ!"
    assert adapt_java_regex("(?Ui)FRITZ!") == "(?iu)FRITZ!"
    assert adapt_java_regex("") == ""


def test_remove_block_quotes_and_finitize():
    """Verify loomchild Util.removeBlockQuotes and Util.finitize lookbehind semantics."""
    # remove_block_quotes
    assert remove_block_quotes(r"\Qabc\E") == r"\a\b\c"
    assert remove_block_quotes(r"foo\Qbar\Ebaz") == r"foo\b\a\rbaz"
    assert remove_block_quotes(r"no_quotes") == r"no_quotes"

    # finitize unbounded quantifiers
    assert finitize(r"A[eur]\.[\s\u00A0]*", 100) == r"A[eur]\.[\s\u00A0]{0,100}"
    assert finitize(r"(?U)\b[0-9]+(гг|г)\.\s", 100) == r"(?U)\b[0-9]{1,100}(гг|г)\.\s"
    assert finitize(r"a{2,}", 100) == r"a{2,100}"
    assert finitize(r"\S*@", 100) == r"\S{0,100}@"
    assert finitize(r"(?U)\b[А-ЯЁ]\.[А-ЯЁ]\.", 100) == r"(?U)\b[А-ЯЁ]\.[А-ЯЁ]\."
    assert finitize("") == ""


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


def test_srx_inventory_and_rules_complete_regeneration(
    third_party_dir: Path, compat_dir: Path, repo_root: Path
):
    """Regenerate complete SRX inventory and rules and assert byte-for-byte / struct equality against committed files."""
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

    # Compare inventory
    inv_file = compat_dir / "russian_srx_inventory.json"
    assert inv_file.is_file(), f"Missing {inv_file}"
    committed_inv = json.loads(inv_file.read_text(encoding="utf-8"))
    assert inventory == committed_inv

    # Compare runtime rules
    rules_file = repo_root / "src" / "pylat_ru" / "resources" / "russian_srx_rules.json"
    assert rules_file.is_file(), f"Missing {rules_file}"
    committed_rules = json.loads(rules_file.read_text(encoding="utf-8"))
    assert runtime_rules == committed_rules


def test_srx_source_hash_mismatch_raises_error(tmp_path: Path):
    """Verify that an altered segment.srx fails with explicit error instead of silent acceptance."""
    fake_srx = tmp_path / "fake_segment.srx"
    fake_srx.write_text("<srx></srx>", encoding="utf-8")

    with pytest.raises(ValueError, match="SRX source hash mismatch"):
        analyze_srx(fake_srx, expected_hash=EXPECTED_SRX_HASH)


def test_dynamic_languagemap_cascade_resolution():
    """Verify dynamic language map resolution with cascade='yes' vs cascade='no'."""
    test_mappings = [
        {"languagepattern": r".*", "languagerulename": "GeneralImportant"},
        {"languagepattern": r"[a-z]{2,3}_two", "languagerulename": "ByTwoLineBreaks"},
        {"languagepattern": r"(RU|ru).*", "languagerulename": "Russian"},
        {"languagepattern": r".*", "languagerulename": "Default"},
    ]

    # cascade=True collects all matching
    resolved_two = resolve_language_rules_for_code(test_mappings, "ru_two", cascade=True)
    assert resolved_two == ["GeneralImportant", "ByTwoLineBreaks", "Russian", "Default"]

    # cascade=False stops at first match
    resolved_nocascade = resolve_language_rules_for_code(test_mappings, "ru_two", cascade=False)
    assert resolved_nocascade == ["GeneralImportant"]

    # Unmatched language returns empty list
    resolved_none = resolve_language_rules_for_code(
        [{"languagepattern": r"en_.*", "languagerulename": "English"}],
        "ru_two",
        cascade=True,
    )
    assert resolved_none == []


def test_load_russian_srx_rule_manager_modes():
    """Verify load_russian_srx_rule_manager loads ru_two and ru_one correctly."""
    mgr_two = load_russian_srx_rule_manager("ru_two")
    mgr_one = load_russian_srx_rule_manager("ru_one")

    assert len(mgr_two.break_rules) == 12
    assert len(mgr_one.break_rules) == 11

    with pytest.raises(
        UnsupportedSRXFeatureError, match="Unsupported SRX Russian configuration mode"
    ):
        load_russian_srx_rule_manager("ru_unknown_mode")


def test_strict_srx_runtime_resource_validation(tmp_path: Path):
    """Verify strict validation on missing metadata, missing configs, or invalid break attributes."""
    fake_path = tmp_path / "bad_rules.json"

    # Missing metadata
    fake_path.write_text(json.dumps({"configurations": {}, "groups": {}}), encoding="utf-8")
    with pytest.raises(SRXFormatError, match="missing required top-level keys"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=fake_path)

    # Missing required metadata field
    fake_path.write_text(
        json.dumps({
            "metadata": {"languagetool_tag": "v6.8"},
            "configurations": {"ru_two": {"rules": []}},
            "groups": {},
        }),
        encoding="utf-8",
    )
    with pytest.raises(SRXFormatError, match="metadata missing required keys"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=fake_path)

    # Invalid break attribute value
    fake_path.write_text(
        json.dumps({
            "metadata": {
                "languagetool_commit": "abc",
                "languagetool_tag": "v6.8",
                "loomchild_version": "2.0.3",
                "source_sha256": "123",
            },
            "configurations": {
                "ru_two": {
                    "rules": [
                        {
                            "group": "G",
                            "rule_index": 1,
                            "break": "maybe",
                            "beforebreak": ".",
                            "afterbreak": "",
                        }
                    ]
                }
            },
            "groups": {},
        }),
        encoding="utf-8",
    )
    with pytest.raises(SRXFormatError, match="invalid break value"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=fake_path)


def test_srx_rule_matcher_advancement_and_zero_width():
    """Verify Java Matcher.find() advancement semantics with non-empty and zero-width matches."""
    # 1. Non-empty match: before="ab", after="cd" in text="ab_abcd_abcd"
    rule = SRXRule(
        is_break=True,
        before_pattern_str="ab",
        after_pattern_str="cd",
        group_name="Test",
        rule_index=1,
    )
    matcher = SRXRuleMatcher(rule, "ab_abcd_abcd")

    assert matcher.find()
    assert matcher.get_start_position() == 3
    assert matcher.get_break_position() == 5
    assert matcher.get_end_position() == 7

    assert matcher.find()
    assert matcher.get_start_position() == 8
    assert matcher.get_break_position() == 10
    assert matcher.get_end_position() == 12

    assert not matcher.find()

    # 2. Zero-width beforebreak: before="", after="a" in text="aaa"
    rule_zw = SRXRule(
        is_break=True,
        before_pattern_str="",
        after_pattern_str="a",
        group_name="TestZW",
        rule_index=2,
    )
    matcher_zw = SRXRuleMatcher(rule_zw, "aaa")

    assert matcher_zw.find()
    assert matcher_zw.get_break_position() == 0

    assert matcher_zw.find()
    assert matcher_zw.get_break_position() == 1

    assert matcher_zw.find()
    assert matcher_zw.get_break_position() == 2

    assert not matcher_zw.find()
