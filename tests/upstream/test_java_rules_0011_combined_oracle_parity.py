"""Pinned full-JLanguageTool ordering parity for XML + Task-0011 rules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pylat_ru import LanguageToolRU
from pylat_ru.match_filters import same_rule_group_filter
from pylat_ru.tokenization.offsets import Utf16CodePointMapper


FIXTURE = Path("tests/fixtures/oracle_java_rules_0011_combined.json")
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def _normalize(findings, text: str) -> list[dict]:
    mapper = Utf16CodePointMapper(text)
    actual = []
    for finding in findings:
        start, end = finding.offset, finding.offset + finding.length
        actual.append({
            "rule_id": finding.rule_id,
            "category_id": finding.category_id,
            "category_name": finding.category_name,
            "message": finding.message,
            "short_message": finding.short_message,
            "suggestions": list(finding.replacements),
            "url": finding.url,
            "from_utf16": mapper.codepoint_to_utf16(start),
            "to_utf16": mapper.codepoint_to_utf16(end),
            "from": start,
            "to": end,
            "source_slice": text[start:end],
        })
    return actual


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_combined_xml_and_java_pipeline_matches_pinned_order(case: dict) -> None:
    # The fixture was generated with the eight Task-0012 rules disabled in Java,
    # so the Python pipeline is configured the same way for this comparison.
    tool = LanguageToolRU(
        enabled_rules=case["explicitly_enabled_rules"],
        disabled_rules=case["explicitly_disabled_rules"],
    )
    assert _normalize(tool.check(case["text"]), case["text"]) == case["expected"]
    pre_overlap = same_rule_group_filter(tool._collect_matches(case["text"]))
    assert _normalize(pre_overlap, case["text"]) == case["pre_overlap_expected"]

    for rule_id, expected in case["raw_rule_expected"].items():
        raw = tool.java_rules_engine.check_rule(case["text"], rule_id)
        public = [tool._native_to_public(finding) for finding in raw]
        assert _normalize(public, case["text"]) == expected
