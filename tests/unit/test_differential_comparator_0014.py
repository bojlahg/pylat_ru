"""Task 0014 section 4 - the whole-finding comparator must be strict.

Entering Task 0014 ``compare_findings()`` compared suggestions as sets, matched
findings by rule-id membership rather than multiplicity, and could report an exact
result while messages or categories differed.  These tests pin the repaired
semantics: ``is_exact_match`` is true only when the ordered Java and Python finding
sequences agree on every observable field, duplicates and order included.

Every test here is Java-free.  The recorded pinned-Java offsets used by the UTF-16
tests come from the committed calibration fixture
``tests/fixtures/oracle_utf16_calibration_0014.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.differential_lt import (
    CATEGORY_MISMATCH,
    CATEGORY_NAME_MISMATCH,
    EXTRA_FINDING,
    FINDING_ORDER_MISMATCH,
    FULL_RULE_ID_MISMATCH,
    MESSAGE_MISMATCH,
    MISMATCH_KINDS,
    MISSING_FINDING,
    RULE_ID_MISMATCH,
    SHORT_MESSAGE_MISMATCH,
    SPAN_MISMATCH,
    SUGGESTION_CONTENT_MISMATCH,
    SUGGESTION_ORDER_MISMATCH,
    URL_MISMATCH,
    Finding,
    compare_findings,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def java(
    rule_id: str = "RULE_A",
    category_id: str = "TYPOS",
    category_name: str = "Опечатки",
    full_rule_id: str = "RULE_A",
    message: str = "сообщение",
    offset: int = 0,
    length: int = 4,
    suggestions: list[str] | None = None,
    short_message: str = "",
    url: str = "",
) -> Finding:
    return Finding(
        rule_id=rule_id,
        full_rule_id=full_rule_id,
        category_id=category_id,
        category_name=category_name,
        message=message,
        offset=offset,
        length=length,
        suggestions=list(suggestions or []),
        source="java_lt",
        short_message=short_message,
        url=url,
    )


def pylat(**kwargs) -> Finding:
    finding = java(**kwargs)
    return Finding(
        rule_id=finding.rule_id,
        full_rule_id=finding.full_rule_id,
        category_id=finding.category_id,
        category_name=finding.category_name,
        message=finding.message,
        offset=finding.offset,
        length=finding.length,
        suggestions=list(finding.suggestions),
        source="pylat_ru",
        short_message=finding.short_message,
        url=finding.url,
    )


TEXT = "Произвольный русский текст для сравнения."


def test_exact_repeated_findings_pass() -> None:
    """Two identical findings on both sides are exactly equal."""
    findings = [
        (java(offset=0), pylat(offset=0)),
        (java(offset=10), pylat(offset=10)),
    ]
    result = compare_findings(
        TEXT, [j for j, _ in findings], [p for _, p in findings]
    )
    assert result.is_exact_match is True
    assert result.mismatches == []
    assert result.span_matches == 2


def test_repeated_same_rule_findings_use_multiplicity() -> None:
    """Java reporting a rule twice and Python once is one missing occurrence."""
    result = compare_findings(
        TEXT,
        [java(offset=0), java(offset=10)],
        [pylat(offset=0)],
    )
    assert result.is_exact_match is False
    assert result.missing_in_pylat == ["RULE_A"]
    assert result.extra_in_pylat == []
    assert result.matching_rule_ids == ["RULE_A"]
    assert MISSING_FINDING in result.mismatch_kinds


def test_extra_python_occurrence_is_reported() -> None:
    """The multiplicity accounting is symmetric."""
    result = compare_findings(
        TEXT,
        [java(offset=0)],
        [pylat(offset=0), pylat(offset=10)],
    )
    assert result.is_exact_match is False
    assert result.extra_in_pylat == ["RULE_A"]
    assert result.missing_in_pylat == []
    assert EXTRA_FINDING in result.mismatch_kinds


def test_same_rule_different_spans_do_not_collapse() -> None:
    """A shared rule id must not hide a span difference."""
    result = compare_findings(TEXT, [java(offset=0)], [pylat(offset=7)])
    assert result.is_exact_match is False
    assert SPAN_MISMATCH in result.mismatch_kinds
    assert result.span_matches == 0


def test_category_mismatch_fails() -> None:
    result = compare_findings(
        TEXT, [java(category_id="TYPOS")], [pylat(category_id="TYPOGRAPHY")]
    )
    assert result.is_exact_match is False
    assert CATEGORY_MISMATCH in result.mismatch_kinds


def test_full_rule_id_mismatch_fails_with_same_base_id() -> None:
    result = compare_findings(
        TEXT,
        [java(rule_id="XML_RULE", full_rule_id="XML_RULE[1]")],
        [pylat(rule_id="XML_RULE", full_rule_id="XML_RULE[2]")],
    )
    assert result.is_exact_match is False
    assert FULL_RULE_ID_MISMATCH in result.mismatch_kinds


def test_identical_full_rule_id_is_exact() -> None:
    result = compare_findings(
        TEXT,
        [java(full_rule_id="XML_RULE[2]")],
        [pylat(full_rule_id="XML_RULE[2]")],
    )
    assert result.is_exact_match is True


def test_repeated_base_ids_with_distinct_full_ids_do_not_collapse() -> None:
    result = compare_findings(
        TEXT,
        [java(full_rule_id="RULE_A[1]"), java(full_rule_id="RULE_A[2]", offset=10)],
        [pylat(full_rule_id="RULE_A[1]")],
    )
    assert result.is_exact_match is False
    assert MISSING_FINDING in result.mismatch_kinds


def test_category_name_mismatch_fails_with_same_category_id() -> None:
    result = compare_findings(
        TEXT,
        [java(category_id="TYPOS", category_name="Опечатки")],
        [pylat(category_id="TYPOS", category_name="Другое имя")],
    )
    assert result.is_exact_match is False
    assert CATEGORY_NAME_MISMATCH in result.mismatch_kinds


def test_message_mismatch_fails() -> None:
    result = compare_findings(TEXT, [java(message="одно")], [pylat(message="другое")])
    assert result.is_exact_match is False
    assert MESSAGE_MISMATCH in result.mismatch_kinds


def test_message_whitespace_is_not_normalised() -> None:
    """No whitespace normalisation, case folding or punctuation smoothing."""
    result = compare_findings(
        TEXT, [java(message="одно  два")], [pylat(message="одно два")]
    )
    assert result.is_exact_match is False
    assert MESSAGE_MISMATCH in result.mismatch_kinds


def test_short_message_mismatch_fails() -> None:
    result = compare_findings(
        TEXT, [java(short_message="кратко")], [pylat(short_message="")]
    )
    assert result.is_exact_match is False
    assert SHORT_MESSAGE_MISMATCH in result.mismatch_kinds


def test_url_mismatch_fails() -> None:
    result = compare_findings(
        TEXT, [java(url="https://example.invalid/a")], [pylat(url="")]
    )
    assert result.is_exact_match is False
    assert URL_MISMATCH in result.mismatch_kinds


def test_rule_id_mismatch_on_identical_span_is_classified() -> None:
    result = compare_findings(
        TEXT, [java(rule_id="RULE_A")], [pylat(rule_id="RULE_B")]
    )
    assert result.is_exact_match is False
    assert RULE_ID_MISMATCH in result.mismatch_kinds


def test_suggestion_order_mismatch_fails() -> None:
    """['a', 'b'] != ['b', 'a'] - no set conversion."""
    result = compare_findings(
        TEXT,
        [java(suggestions=["первый", "второй"])],
        [pylat(suggestions=["второй", "первый"])],
    )
    assert result.is_exact_match is False
    assert SUGGESTION_ORDER_MISMATCH in result.mismatch_kinds
    assert SUGGESTION_CONTENT_MISMATCH not in result.mismatch_kinds
    assert result.suggestion_matches == 0


def test_duplicate_suggestion_mismatch_fails() -> None:
    """['a', 'a'] != ['a'] - duplicates are preserved."""
    result = compare_findings(
        TEXT,
        [java(suggestions=["слово", "слово"])],
        [pylat(suggestions=["слово"])],
    )
    assert result.is_exact_match is False
    assert SUGGESTION_CONTENT_MISMATCH in result.mismatch_kinds


def test_identical_suggestion_lists_match() -> None:
    result = compare_findings(
        TEXT,
        [java(suggestions=["слово", "слово", "иное"])],
        [pylat(suggestions=["слово", "слово", "иное"])],
    )
    assert result.is_exact_match is True
    assert result.suggestion_matches == 1


def test_finding_order_mismatch_fails() -> None:
    """The same two findings in a different sequence is a non-exact result."""
    first = dict(rule_id="RULE_A", offset=0)
    second = dict(rule_id="RULE_B", offset=10)
    result = compare_findings(
        TEXT,
        [java(**first), java(**second)],
        [pylat(**second), pylat(**first)],
    )
    assert result.is_exact_match is False
    assert result.mismatch_kinds == [FINDING_ORDER_MISMATCH]
    assert result.finding_count_match is True
    assert result.missing_in_pylat == []
    assert result.extra_in_pylat == []


def test_non_bmp_span_mismatch_fails() -> None:
    """A UTF-16 span that is off by one surrogate unit is not exact."""
    result = compare_findings(
        "\U0001F600 слово", [java(offset=3, length=5)], [pylat(offset=2, length=5)]
    )
    assert result.is_exact_match is False
    assert SPAN_MISMATCH in result.mismatch_kinds


def test_multiple_field_mismatches_are_all_classified() -> None:
    """One pair may carry several classifications at once."""
    result = compare_findings(
        TEXT,
        [java(category_id="TYPOS", message="одно", suggestions=["a", "b"])],
        [pylat(category_id="STYLE", message="другое", suggestions=["b", "a"])],
    )
    assert result.is_exact_match is False
    assert CATEGORY_MISMATCH in result.mismatch_kinds
    assert MESSAGE_MISMATCH in result.mismatch_kinds
    assert SUGGESTION_ORDER_MISMATCH in result.mismatch_kinds


def test_empty_sequences_are_exact() -> None:
    result = compare_findings(TEXT, [], [])
    assert result.is_exact_match is True
    assert result.mismatches == []


def test_mismatch_kinds_are_from_the_declared_vocabulary() -> None:
    result = compare_findings(
        TEXT,
        [java(rule_id="RULE_A"), java(rule_id="RULE_C", offset=20)],
        [pylat(rule_id="RULE_B", category_id="STYLE")],
    )
    assert result.mismatch_kinds
    for kind in result.mismatch_kinds:
        assert kind in MISMATCH_KINDS


def test_diagnostics_never_change_the_strict_verdict() -> None:
    """Diagnostic pairing is additive; the verdict comes from the ordered comparison."""
    java_findings = [java(offset=0), java(rule_id="RULE_B", offset=9)]
    pylat_findings = [pylat(offset=0), pylat(rule_id="RULE_B", offset=9)]
    result = compare_findings(TEXT, java_findings, pylat_findings)
    assert result.is_exact_match is True
    assert result.to_dict()["mismatches"] == []


def test_result_dict_round_trips_to_json() -> None:
    result = compare_findings(TEXT, [java()], [pylat(message="иное")])
    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    assert "MESSAGE_MISMATCH" in payload


# -- UTF-16 offset domain calibration ---------------------------------------

CALIBRATION_PATH = REPO_ROOT / "tests" / "fixtures" / "oracle_utf16_calibration_0014.json"


@pytest.fixture(scope="module")
def calibration() -> dict:
    return json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))


def test_calibration_fixture_records_the_utf16_domain(calibration: dict) -> None:
    """Section 4.2: the offset domain is proven from recorded pinned-Java output."""
    metadata = calibration["metadata"]
    assert metadata["position_domain"].startswith("UTF-16 code units")
    assert metadata["pinned_lt_version"] == "6.8"
    assert metadata["pinned_lt_commit"] == "e807fcde6a6506191e1470744d2345da28c26be6"

    cases = calibration["cases"]
    assert len(cases) >= 100
    assert sum(1 for c in cases if c["has_non_bmp"]) >= 50
    assert sum(1 for c in cases if c["has_combining"]) >= 10
    assert sum(1 for c in cases if c["has_soft_hyphen"]) >= 10


def test_recorded_java_offsets_are_utf16_not_code_points(calibration: dict) -> None:
    """A non-BMP prefix shifts the Java offset past what a code-point index would give."""
    shifted = 0
    for case in calibration["cases"]:
        if not case["has_non_bmp"] or not case["java_findings"]:
            continue
        text = case["text"]
        assert case["text_utf16_length"] > case["text_code_point_length"]
        for finding, (code_point_offset, _) in zip(
            case["java_findings"], case["python_code_point_spans"]
        ):
            java_offset = finding[6]
            surrogates = sum(1 for c in text[:code_point_offset] if ord(c) > 0xFFFF)
            assert java_offset == code_point_offset + surrogates
            if surrogates:
                shifted += 1
    assert shifted >= 50, "expected recorded non-BMP findings whose offsets are shifted"
