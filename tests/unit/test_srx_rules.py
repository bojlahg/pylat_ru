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
    EXPECTED_LOOMCHILD_VERSION,
    EXPECTED_LT_COMMIT,
    EXPECTED_LT_TAG,
    EXPECTED_SOURCE_SHA256,
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
    """Regenerate complete SRX inventory and rules and assert byte-exact serialized equality against committed files."""
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

    # Compare inventory serialized string exactly
    inv_file = compat_dir / "russian_srx_inventory.json"
    assert inv_file.is_file(), f"Missing {inv_file}"
    expected_inv_str = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    actual_inv_str = inv_file.read_text(encoding="utf-8")
    assert actual_inv_str == expected_inv_str, "Committed russian_srx_inventory.json differs from serialized regeneration"

    # Compare runtime rules serialized string exactly
    rules_file = repo_root / "src" / "pylat_ru" / "resources" / "russian_srx_rules.json"
    assert rules_file.is_file(), f"Missing {rules_file}"
    expected_rules_str = json.dumps(runtime_rules, indent=2, ensure_ascii=False) + "\n"
    actual_rules_str = rules_file.read_text(encoding="utf-8")
    assert actual_rules_str == expected_rules_str, "Committed russian_srx_rules.json differs from serialized regeneration"


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


def test_strict_srx_metadata_exact_values(tmp_path: Path):
    """Verify runtime SRX metadata strictly enforces exact expected commit, tag, version, and hash."""
    def make_rules_with_meta(meta: dict) -> Path:
        p = tmp_path / f"meta_test_{len(list(tmp_path.iterdir()))}.json"
        p.write_text(
            json.dumps({
                "metadata": meta,
                "configurations": {"ru_two": {"rules": []}},
                "groups": {},
            }),
            encoding="utf-8",
        )
        return p

    # Valid metadata
    valid_meta = {
        "languagetool_commit": EXPECTED_LT_COMMIT,
        "languagetool_tag": EXPECTED_LT_TAG,
        "loomchild_version": EXPECTED_LOOMCHILD_VERSION,
        "source_sha256": EXPECTED_SOURCE_SHA256,
    }
    p_valid = make_rules_with_meta(valid_meta)
    assert load_russian_srx_rule_manager("ru_two", rules_json_path=p_valid) is not None

    # Wrong commit
    p_bad_commit = make_rules_with_meta({**valid_meta, "languagetool_commit": "wrong_commit_123"})
    with pytest.raises(SRXFormatError, match="mismatching languagetool_commit"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=p_bad_commit)

    # Wrong tag
    p_bad_tag = make_rules_with_meta({**valid_meta, "languagetool_tag": "v6.7"})
    with pytest.raises(SRXFormatError, match="mismatching languagetool_tag"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=p_bad_tag)

    # Wrong loomchild version
    p_bad_loomchild = make_rules_with_meta({**valid_meta, "loomchild_version": "2.0.4"})
    with pytest.raises(SRXFormatError, match="mismatching loomchild_version"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=p_bad_loomchild)

    # Wrong source SHA-256
    p_bad_sha = make_rules_with_meta({**valid_meta, "source_sha256": "00000000000000000000000000000000"})
    with pytest.raises(SRXFormatError, match="mismatching source_sha256"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=p_bad_sha)


def test_strict_srx_rule_field_types(tmp_path: Path):
    """Verify strict type validation on rule dictionary fields without coercion."""
    valid_meta = {
        "languagetool_commit": EXPECTED_LT_COMMIT,
        "languagetool_tag": EXPECTED_LT_TAG,
        "loomchild_version": EXPECTED_LOOMCHILD_VERSION,
        "source_sha256": EXPECTED_SOURCE_SHA256,
    }

    def make_rules_with_rule(rule_dict: dict) -> Path:
        p = tmp_path / f"rule_type_{len(list(tmp_path.iterdir()))}.json"
        p.write_text(
            json.dumps({
                "metadata": valid_meta,
                "configurations": {"ru_two": {"rules": [rule_dict]}},
                "groups": {},
            }),
            encoding="utf-8",
        )
        return p

    valid_rule = {
        "group": "Russian",
        "rule_index": 1,
        "break": "yes",
        "beforebreak": "\\.",
        "afterbreak": "\\s",
    }

    # Valid rule passes
    assert load_russian_srx_rule_manager("ru_two", rules_json_path=make_rules_with_rule(valid_rule)) is not None

    # group is not a str (e.g. 123 or None)
    with pytest.raises(SRXFormatError, match="field 'group' must be a str"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=make_rules_with_rule({**valid_rule, "group": 123}))

    with pytest.raises(SRXFormatError, match="field 'group' must be a str"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=make_rules_with_rule({**valid_rule, "group": None}))

    # rule_index is not an int (e.g. "1", None, or bool True)
    with pytest.raises(SRXFormatError, match="field 'rule_index' must be an int"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=make_rules_with_rule({**valid_rule, "rule_index": "1"}))

    with pytest.raises(SRXFormatError, match="field 'rule_index' must be an int"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=make_rules_with_rule({**valid_rule, "rule_index": True}))

    # beforebreak / afterbreak is not a str
    with pytest.raises(SRXFormatError, match="field 'beforebreak' must be a str"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=make_rules_with_rule({**valid_rule, "beforebreak": None}))

    with pytest.raises(SRXFormatError, match="field 'afterbreak' must be a str"):
        load_russian_srx_rule_manager("ru_two", rules_json_path=make_rules_with_rule({**valid_rule, "afterbreak": 123}))


def test_synthetic_overlapping_and_same_boundary_rules():
    """Verify loomchild 2.0.3 cut_matchers() and move_matchers() semantics on overlapping and same-boundary rules."""
    # Construct rules:
    # Rule 1 (break=yes): before="[A-Z]\\.", after="\\s" (matches "A. ") -> break at 2
    # Rule 2 (break=yes): before="[0-9]\\.", after="\\s" (matches "1. ") -> break at 2
    # Rule 3 (break=no exception for Rule 4): before="Dr\\.", after="\\s"
    # Rule 4 (break=yes): before="\\.", after="\\s" (matches any dot-space)
    r1 = SRXRule(is_break=True, before_pattern_str="[A-Z]\\.", after_pattern_str="\\s", group_name="G1", rule_index=1)
    r2 = SRXRule(is_break=True, before_pattern_str="[0-9]\\.", after_pattern_str="\\s", group_name="G1", rule_index=2)
    r3 = SRXRule(is_break=False, before_pattern_str="Dr\\.", after_pattern_str="\\s", group_name="G2", rule_index=3)
    r4 = SRXRule(is_break=True, before_pattern_str="\\.", after_pattern_str="\\s", group_name="G2", rule_index=4)

    mgr = SRXRuleManager.from_rules([r1, r2, r3, r4])
    segmenter = SRXSegmenter(mgr)

    # 1. Text with suppressed break: "Dr. Watson is here. Next sentence."
    # Break at 3 ("Dr.") is suppressed by exception r3 for r4.
    # Break at 19 ("here.") is accepted by r4.
    sents = segmenter.segment("Dr. Watson is here. Next sentence.")
    assert sents == ("Dr. Watson is here.", " Next sentence.")

    # 2. Text with multi-rule match at same break boundary:
    # Text "A. B. C." -> R1 breaks at 2 ("A.") and R4 also breaks at 2 (".").
    # R1 fires first, cut_matchers / move_matchers must advance R4 past 2 without redundant zero-length split.
    sents_same = segmenter.segment("A. B. C.")
    assert sents_same == ("A.", " B.", " C.")


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
