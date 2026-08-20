"""Pinned full-JLanguageTool ordering parity for XML + Task-0011 rules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pylat_ru import LanguageToolRU
from pylat_ru.tokenization.offsets import Utf16CodePointMapper


FIXTURE = Path("tests/fixtures/oracle_java_rules_0011_combined.json")
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_combined_xml_and_java_pipeline_matches_pinned_order(case: dict) -> None:
    tool = LanguageToolRU(enabled_rules=case["explicitly_enabled_rules"])
    mapper = Utf16CodePointMapper(case["text"])
    actual = []
    for finding in tool.check(case["text"]):
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
            "source_slice": case["text"][start:end],
        })
    assert actual == case["expected"]
