"""Strict parity for Task 0010's real and controlled low-level Java evidence."""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Mapping

import pytest

from pylat_ru.analysis import AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.filters import RuleFilterEvaluator, get_filter_instance
from pylat_ru.grammar.filters.base import FilterIllegalArgumentError, FilterRuntimeError
from pylat_ru.grammar.filters.date_check import SystemClock
from pylat_ru.grammar.model import RuleMatchResult
from pylat_ru.synthesis.synthesizer import RussianSynthesizer

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = PROJECT_ROOT / "compat" / "oracle_manifest.json"
SYNTHETIC_PATH = PROJECT_ROOT / "tests" / "fixtures" / "oracle_filters_synthetic.json"
REAL_PATH = PROJECT_ROOT / "tests" / "fixtures" / "oracle_filters_russian_rules.json"


@pytest.fixture(autouse=True)
def restore_system_clock():
    original_test_mode = SystemClock.is_test_mode
    original_override = SystemClock._override_now
    yield
    SystemClock.is_test_mode = original_test_mode
    SystemClock._override_now = original_override


def check_case_with_engine(engine, rule, text):
    sentence = RussianHybridDisambiguator.get_instance().disambiguate_text(text)
    sentence.text = text
    RussianChunker().chunk(sentence)
    return engine.check_rule(sentence, rule)


def canonical_signature(case: Mapping[str, Any], fields: list[str]) -> str:
    semantic = {field: case.get(field) for field in fields}
    payload = json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def controlled_tokens(case: Mapping[str, Any]) -> list[AnalyzedTokenReadings]:
    result = []
    for item in case["tokens"]:
        readings = [AnalyzedToken(raw["token"], raw.get("lemma"), raw.get("pos_tag")) for raw in item["readings"]]
        result.append(AnalyzedTokenReadings(readings, start_pos=item["start_pos"],
                                            is_sentence_start=bool(readings and readings[0].pos_tag == "SENT_START")))
    return result


def controlled_match(case: Mapping[str, Any]) -> RuleMatchResult:
    raw = case["match"]
    start, end = raw.get("from_pos", 0), raw.get("to_pos", 1)
    return RuleMatchResult(
        rule_id="LOW_LEVEL_FILTER_ORACLE", full_rule_id="LOW_LEVEL_FILTER_ORACLE",
        category_id="ORACLE", category_name="Oracle", description="Low-level filter oracle",
        message=raw.get("message", "message"), short_message=raw.get("short_message", "short"),
        suggestions=list(raw.get("suggestions", [])), from_pos=start, to_pos=end,
        from_pos_utf16=start, to_pos_utf16=end, pattern_from_pos=start, pattern_to_pos=end,
        pattern_from_pos_utf16=start, pattern_to_pos_utf16=end,
        matched_tokens_indices=[], marker_tokens_indices=[], url=None,
    )


def python_exception_category(error: BaseException) -> str:
    if type(error) is FilterIllegalArgumentError:
        return "illegal_argument"
    if type(error) is FilterRuntimeError:
        return "runtime"
    if type(error) is IndexError:
        return "index_bounds"
    if type(error) is re.error:
        return "regex_syntax"
    raise AssertionError(f"Unmapped Python exception type: {type(error).__module__}.{type(error).__name__}: {error}")


def run_python_low_level(case: Mapping[str, Any]) -> Dict[str, Any]:
    tokens = controlled_tokens(case)
    try:
        if case["operation"] == "evaluator":
            resolved = RuleFilterEvaluator(None).get_resolved_arguments(
                case["filter_args"], tokens, case["pattern_token_pos"], case["token_positions"]
            )
            result: Dict[str, Any] = {"status": "RESULT", "resolved_args": resolved,
                                      "selected_position": -1}
            if case.get("selected_key") is not None:
                selected_value = resolved.get(case["selected_key"])
                if selected_value is not None and re.fullmatch(r"marker(?:[+-]\d+)?|[+-]?\d+", selected_value):
                    probe = get_filter_instance("org.languagetool.rules.ru.INNNumberFilter")
                    result["selected_position"] = probe.get_position(
                        selected_value, tokens, controlled_match(case)
                    )
                else:
                    result["selected_position"] = next(
                        (index for index, item in enumerate(tokens) if item.token == selected_value), -1
                    )
            return result

        filter_instance = get_filter_instance(case["filter_class"])
        filter_instance.set_synthesizer(RussianSynthesizer.get_instance())
        original = controlled_match(case)
        filtered = filter_instance.accept_rule_match(
            original, case["arguments"], case["pattern_token_pos"], tokens, case["token_positions"]
        )
        if filtered is None:
            return {"status": "RESULT", "decision": "reject"}
        return {
            "status": "RESULT", "decision": "preserve" if filtered is original else "modify",
            "from_utf16": filtered.from_pos_utf16, "to_utf16": filtered.to_pos_utf16,
            "message": filtered.message, "short_message": filtered.short_message,
            "suggestions": filtered.suggestions, "url": filtered.url or "",
        }
    except (FilterIllegalArgumentError, FilterRuntimeError, IndexError, re.error) as error:
        return {"status": "EXCEPTION", "exception_category": python_exception_category(error)}


def utf16_to_codepoint(text: str, offset: int) -> int:
    encoded = text.encode("utf-16-le")
    return len(encoded[: offset * 2].decode("utf-16-le"))


@pytest.mark.parametrize("fixture_name", ["oracle_filters_synthetic.json", "oracle_filters_russian_rules.json"])
def test_filter_fixture_manifest_binding(fixture_name):
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    bindings = {Path(item["path"]).name: item for item in manifest["fixture_bindings"]}
    binding = bindings[fixture_name]
    fixture_path = PROJECT_ROOT / binding["path"]
    payload = fixture_path.read_bytes()
    data = json.loads(payload)
    assert len(payload) == binding["size_bytes"]
    assert hashlib.sha256(payload).hexdigest() == binding["sha256"]
    assert len(data["cases"]) == binding["case_count"] == data["metadata"]["cases_count"]
    assert data["metadata"]["oracle_build_id"] == binding["oracle_build_id"]


def test_synthetic_fixture_integrity_and_fail_closed_coverage():
    data = json.loads(SYNTHETIC_PATH.read_text(encoding="utf-8"))
    cases = data["cases"]
    fields = data["metadata"]["semantic_signature_fields"]
    ids = [case["id"] for case in cases]
    signatures = [canonical_signature(case, fields) for case in cases]
    assert len(cases) >= 120
    assert len(ids) == len(set(ids))
    assert signatures == [case["semantic_signature"] for case in cases]
    assert len(signatures) == len(set(signatures))
    by_id = {case["id"]: case for case in cases}
    for feature, coverage in data["feature_coverage"].items():
        assert coverage["exercising_case_ids"], feature
        for case_id in coverage["exercising_case_ids"]:
            case = by_id[case_id]
            assert feature in case["features"]
            result = case["oracle_result"]
            if coverage["exception_feature"]:
                assert result["status"] == "EXCEPTION"
                assert result["exception_category"] == coverage["expected_exception_category"]
            else:
                assert result["status"] == "RESULT"
    for case in cases:
        assert case["expected_java"].items() <= case["oracle_result"].items()
        if any(feature.startswith("inn:valid") or feature.startswith("inn:invalid") for feature in case["features"]):
            assert case["oracle_result"]["status"] == "RESULT"


def test_filters_synthetic_low_level_oracle_parity():
    data = json.loads(SYNTHETIC_PATH.read_text(encoding="utf-8"))
    controlled_date = datetime.date.fromisoformat(data["metadata"]["controlled_current_date"])
    SystemClock.is_test_mode = False
    SystemClock._override_now = datetime.datetime.combine(controlled_date, datetime.time())
    for case in data["cases"]:
        java = case["oracle_result"]
        python = run_python_low_level(case)
        assert python["status"] == java["status"], case["id"]
        if java["status"] == "EXCEPTION":
            assert python["exception_category"] == java["exception_category"], case["id"]
        elif case["operation"] == "evaluator":
            assert python["resolved_args"] == java["resolved_args"], case["id"]
            if "selected_position" in java:
                assert python["selected_position"] == java["selected_position"], case["id"]
        else:
            assert python["decision"] == java["decision"], case["id"]
            if java["decision"] != "reject":
                for field in ("from_utf16", "to_utf16", "message", "short_message", "suggestions", "url"):
                    assert python[field] == java[field], f"{case['id']}:{field}"


def test_filters_russian_rules_oracle_parity():
    data = json.loads(REAL_PATH.read_text(encoding="utf-8"))
    engine = RussianGrammarEngine.get_instance()
    SystemClock.is_test_mode = True
    SystemClock._override_now = None
    for case in data["cases"]:
        rule = engine.get_rule(case["full_rule_id"])
        assert rule is not None, case["id"]
        java = case["oracle_result"]
        assert rule.id == java["rule_id"]
        assert rule.full_id == java["full_rule_id"]
        assert rule.category_id == java["category_id"]
        assert rule.category_name == java["category_name"]
        assert rule.name == java["description"]
        assert rule.default_off == java["is_default_off"]
        python_matches = check_case_with_engine(engine, rule, case["text"])
        assert len(python_matches) == java["matches_count"], case["id"]
        for python, expected in zip(python_matches, java["matches"]):
            assert python.rule_id == java["rule_id"]
            assert python.full_rule_id == java["full_rule_id"]
            assert python.category_id == java["category_id"]
            assert python.category_name == java["category_name"]
            assert python.from_pos_utf16 == expected["from_utf16"]
            assert python.to_pos_utf16 == expected["to_utf16"]
            assert python.pattern_from_pos_utf16 == expected["pattern_from_utf16"]
            assert python.pattern_to_pos_utf16 == expected["pattern_to_utf16"]
            assert python.message == expected["message"]
            assert python.short_message == expected["short_message"]
            assert python.suggestions == expected["suggestions"]
            assert python.url == expected["url"]
            expected_from = utf16_to_codepoint(case["text"], expected["from_utf16"])
            expected_to = utf16_to_codepoint(case["text"], expected["to_utf16"])
            expected_pattern_from = utf16_to_codepoint(case["text"], expected["pattern_from_utf16"])
            expected_pattern_to = utf16_to_codepoint(case["text"], expected["pattern_to_utf16"])
            assert (python.from_pos, python.to_pos) == (expected_from, expected_to)
            assert (python.pattern_from_pos, python.pattern_to_pos) == (expected_pattern_from, expected_pattern_to)
            assert case["text"][python.from_pos:python.to_pos] == case["text"][expected_from:expected_to]
            assert case["text"][python.pattern_from_pos:python.pattern_to_pos] == case["text"][expected_pattern_from:expected_pattern_to]
