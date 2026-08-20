"""Task 0013 - full observable-field parity for the upstream-test oracle fixture.

The seven core/generic upstream rule tests that Tasks 0007-0012 claimed as
Russian compatibility evidence execute against the ``Demo``/``FakeLanguage``
classpath, so their literal expectations are not a Russian contract.  Every one
of their pinned scenario inputs was replayed through the trusted Java oracle
*with the Russian language*, and this test asserts that ``pylat_ru`` reproduces
that Java output field for field.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pylat_ru.native_rules import RussianJavaRulesEngine

FIXTURE = Path("tests/fixtures/oracle_upstream_tests_0013.json")
PINNED_LT_COMMIT = "e807fcde6a6506191e1470744d2345da28c26be6"

EXPECTED_SOURCES = {
    "languagetool-core/src/test/java/org/languagetool/rules/CommaWhitespaceRuleTest.java": 45,
    "languagetool-core/src/test/java/org/languagetool/rules/MultipleWhitespaceRuleTest.java": 17,
    "languagetool-core/src/test/java/org/languagetool/rules/SentenceWhitespaceRuleTest.java": 7,
    "languagetool-core/src/test/java/org/languagetool/rules/UppercaseSentenceStartRuleTest.java": 23,
    "languagetool-core/src/test/java/org/languagetool/rules/LongSentenceRuleTest.java": 24,
    "languagetool-core/src/test/java/org/languagetool/rules/LongParagraphRuleTest.java": 8,
    "languagetool-core/src/test/java/org/languagetool/rules/PunctuationMarkAtParagraphEnd2Test.java": 22,
}


def _data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _cases() -> list[dict]:
    return _data()["cases"]


@pytest.fixture(scope="module")
def engine() -> RussianJavaRulesEngine:
    return RussianJavaRulesEngine()


def test_fixture_metadata_and_source_coverage() -> None:
    data = _data()
    metadata = data["metadata"]
    assert metadata["schema_version"] == "1.0.0"
    assert metadata["task"] == "0013"
    assert metadata["pinned_lt_commit"] == PINNED_LT_COMMIT
    assert metadata["oracle_build_id"] == "lt_6.8_source_build_jdk17_stefan"
    assert metadata["language"] == "ru"
    assert metadata["case_count"] == len(data["cases"]) == 146

    counts: dict[str, int] = {}
    for case in data["cases"]:
        counts[case["upstream_source"]] = counts.get(case["upstream_source"], 0) + 1
    assert counts == EXPECTED_SOURCES


def test_fixture_identity_and_signature_integrity() -> None:
    cases = _cases()
    ids = [case["id"] for case in cases]
    signatures = [case["semantic_signature"] for case in cases]
    assert len(ids) == len(set(ids)), "duplicate case id"
    assert len(signatures) == len(set(signatures)), "duplicate semantic signature"
    for case in cases:
        assert len(case["semantic_signature"]) == 64
        assert case["execution_mode"] == "single_rule"
        assert case["explicitly_enabled"] is True
        assert case["finding_count"] == len(case["expected"])
        assert case["upstream_method"]
        assert case["upstream_scenario"]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["id"])
def test_upstream_test_oracle_parity(case: dict, engine: RussianJavaRulesEngine) -> None:
    case_engine = (
        RussianJavaRulesEngine({case["rule_id"]: case["config"]}) if case["config"] else engine
    )
    actual = case_engine.check_rule(case["text"], case["rule_id"])
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
    assert normalized == case["expected"], case["id"]
