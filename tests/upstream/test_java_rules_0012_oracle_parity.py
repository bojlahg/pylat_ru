"""Full observable-field parity for Task-0012 Java-rule oracle fixtures.

Covers the eight remaining ordinary Russian rules (single-rule execution and
direct speller queries) and the XML rules that depend on the final Russian
suppress-misspelled filter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.native_rules import RussianJavaRulesEngine
from pylat_ru.spelling import RussianSpeller, RussianYoSpeller, SpellerToken
from pylat_ru.tokenization.offsets import Utf16CodePointMapper


SPELLING_FIXTURE = Path("tests/fixtures/oracle_java_rules_0012_spelling.json")
RULES_FIXTURE = Path("tests/fixtures/oracle_java_rules_0012_rules.json")
FILTER_FIXTURE = Path("tests/fixtures/oracle_java_rules_0012_filter.json")

SPELLER_CLASSES = {
    "MORFOLOGIK_RULE_RU_RU": RussianSpeller,
    "MORFOLOGIK_RULE_RU_RU_YO": RussianYoSpeller,
}


def _load(path: Path) -> list[tuple[str, dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [(path.name, case) for case in data["cases"]]


def _normalize(findings, text: str) -> list[dict]:
    return [
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
            "source_slice": text[finding.from_pos:finding.to_pos],
        }
        for finding in findings
    ]


@pytest.fixture(scope="module")
def engine() -> RussianJavaRulesEngine:
    return RussianJavaRulesEngine()


@pytest.mark.parametrize(
    "fixture_name,case",
    _load(SPELLING_FIXTURE) + _load(RULES_FIXTURE),
    ids=lambda value: value if isinstance(value, str) else value["id"],
)
def test_java_rule_oracle_parity(fixture_name: str, case: dict, engine: RussianJavaRulesEngine) -> None:
    if case["execution_mode"] == "direct_speller":
        speller = SPELLER_CLASSES[case["rule_id"]](
            conf_ru_value=case["config"].get("conf_ru_Value", 0)
        )
        word = case["text"]
        matches = speller.match([SpellerToken(token=word, clean_token=word, start_pos=0)])
        actual = {
            "misspelled": speller.is_misspelled(word),
            "suggestions": list(matches[0].suggestions) if matches else [],
        }
        assert actual == case["expected"], f"{fixture_name}:{case['id']}"
        return

    case_engine = (
        RussianJavaRulesEngine({case["rule_id"]: case["config"]}) if case["config"] else engine
    )
    actual = case_engine.check_rule(case["text"], case["rule_id"])
    assert _normalize(actual, case["text"]) == case["expected"], f"{fixture_name}:{case['id']}"


def _check_xml_rule(text: str, full_rule_id: str) -> list[dict]:
    """Run one XML grammar rule over the whole text, sentence by sentence."""
    grammar = RussianGrammarEngine.get_instance()
    disambiguator = RussianHybridDisambiguator.get_instance()
    java_engine = RussianJavaRulesEngine()
    mapper = Utf16CodePointMapper(text)
    out: list[dict] = []
    for unit in java_engine.analyze(text).sentences:
        sentence = disambiguator.disambiguate_text(unit.text)
        sentence.text = unit.text
        for finding in grammar.check_rule(sentence, full_rule_id):
            start = unit.start + finding.from_pos
            end = unit.start + finding.to_pos
            out.append({
                "rule_id": finding.rule_id,
                "category_id": finding.category_id,
                "category_name": finding.category_name,
                "message": finding.message,
                "short_message": finding.short_message or "",
                "suggestions": list(finding.suggestions),
                "url": finding.url,
                "from_utf16": mapper.codepoint_to_utf16(start),
                "to_utf16": mapper.codepoint_to_utf16(end),
                "from": start,
                "to": end,
                "source_slice": text[start:end],
            })
    return out


@pytest.mark.parametrize(
    "fixture_name,case",
    _load(FILTER_FIXTURE),
    ids=lambda value: value if isinstance(value, str) else value["id"],
)
def test_suppress_misspelled_filter_oracle_parity(fixture_name: str, case: dict) -> None:
    actual = _check_xml_rule(case["text"], case["rule_id"])
    assert actual == case["expected"], f"{fixture_name}:{case['id']}"
