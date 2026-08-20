"""Full observable-field parity for Task-0011 Java-rule oracle fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pylat_ru.native_rules import RussianJavaRulesEngine


FIXTURES = (
    Path("tests/fixtures/oracle_java_rules_0011_synthetic.json"),
    Path("tests/fixtures/oracle_java_rules_0011_russian.json"),
)


def _cases():
    values = []
    for path in FIXTURES:
        data = json.loads(path.read_text(encoding="utf-8"))
        values.extend((path.name, case) for case in data["cases"])
    return values


@pytest.fixture(scope="module")
def engine() -> RussianJavaRulesEngine:
    return RussianJavaRulesEngine()


@pytest.mark.parametrize("fixture_name,case", _cases(), ids=lambda value: value if isinstance(value, str) else value["id"])
def test_java_rule_oracle_parity(fixture_name: str, case: dict, engine: RussianJavaRulesEngine) -> None:
    actual = engine.check_rule(case["text"], case["rule_id"])
    normalized = [
        {
            "rule_id": finding.rule_id,
            "category_id": finding.category_id,
            "category_name": finding.category_name,
            "message": finding.message,
            "short_message": finding.short_message,
            "suggestions": list(finding.suggestions),
            "url": finding.url,
            "from_utf16": finding.from_pos_utf16,
            "to_utf16": finding.to_pos_utf16,
            "from": finding.from_pos,
            "to": finding.to_pos,
            "source_slice": case["text"][finding.from_pos:finding.to_pos],
        }
        for finding in actual
    ]
    assert normalized == case["expected"], f"{fixture_name}:{case['id']}"

