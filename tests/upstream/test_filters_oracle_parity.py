"""tests/upstream/test_filters_oracle_parity.py

Differential oracle parity tests for Russian grammar XML filters.
Strictly verifies implementation parity against Java LanguageTool 6.8 oracle:
- 165 real Russian rule example cases (oracle_filters_russian_rules.json)
- 145 synthetic test cases covering all filter classes and RuleFilterEvaluator edge cases (oracle_filters_synthetic.json)
"""

import json
import datetime
import hashlib
from pathlib import Path
import pytest

from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.filters.date_check import SystemClock
from pylat_ru.grammar.filters.base import FilterIllegalArgumentError, FilterRuntimeError

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = PROJECT_ROOT / "compat" / "oracle_manifest.json"


@pytest.fixture(autouse=True)
def restore_system_clock():
    original_test_mode = SystemClock.is_test_mode
    original_override = SystemClock._override_now
    yield
    SystemClock.is_test_mode = original_test_mode
    SystemClock._override_now = original_override


def check_case_with_engine(engine, rule, text):
    disambiguator = RussianHybridDisambiguator.get_instance()
    sent = disambiguator.disambiguate_text(text)
    sent.text = text
    RussianChunker().chunk(sent)
    return engine.check_rule(sent, rule)


@pytest.mark.parametrize(
    "fixture_name",
    ["oracle_filters_synthetic.json", "oracle_filters_russian_rules.json"],
)
def test_filter_fixture_manifest_binding(fixture_name):
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    bindings = {Path(item["path"]).name: item for item in manifest["fixture_bindings"]}
    binding = bindings[fixture_name]
    fixture_path = PROJECT_ROOT / binding["path"]
    payload = fixture_path.read_bytes()
    data = json.loads(payload.decode("utf-8"))

    assert len(payload) == binding["size_bytes"]
    assert hashlib.sha256(payload).hexdigest() == binding["sha256"]
    assert len(data["cases"]) == binding["case_count"]
    assert data["metadata"]["oracle_build_id"] == binding["oracle_build_id"]


def test_synthetic_fixture_coverage_and_expectations():
    data = json.loads(
        (PROJECT_ROOT / "tests" / "fixtures" / "oracle_filters_synthetic.json").read_text(encoding="utf-8")
    )
    cases = data["cases"]
    case_ids = [case["id"] for case in cases]

    assert len(cases) >= 120
    assert len(case_ids) == len(set(case_ids))
    assert all(data["feature_coverage"].values())
    for case in cases:
        oracle_result = case["oracle_result"]
        if oracle_result["status"] != "EXCEPTION":
            assert oracle_result["matches_count"] == case["expected_target_matches"]


def test_filters_synthetic_oracle_parity():
    """Verify parity for discriminating synthetic cases."""
    fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "oracle_filters_synthetic.json"
    assert fixture_path.is_file(), f"Missing synthetic fixture: {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    xml_rules_content = data["synthetic_rules_xml"]
    loader = GrammarLoader()
    rules = loader.load_from_string(xml_rules_content)
    engine = RussianGrammarEngine(rules=rules)

    # The committed oracle was captured with this explicit production-mode date.
    # Keeping it in fixture metadata makes omitted-year cases wall-clock stable.
    controlled_date = datetime.date.fromisoformat(data["metadata"]["controlled_current_date"])
    SystemClock.is_test_mode = False
    SystemClock._override_now = datetime.datetime.combine(controlled_date, datetime.time())

    for case in data["cases"]:
        case_id = case["id"]
        full_rule_id = case["full_rule_id"]
        text = case["text"]
        oracle_res = case["oracle_result"]

        rule = engine.get_rule(full_rule_id)
        assert rule is not None, f"Synthetic rule {full_rule_id} not found in compiled engine"

        if oracle_res["status"] == "EXCEPTION":
            # Java threw an exception (IllegalArgumentException or RuntimeException)
            # Python evaluator/filter should raise a corresponding Filter exception
            with pytest.raises((FilterIllegalArgumentError, FilterRuntimeError, ValueError, IndexError)):
                check_case_with_engine(engine, rule, text)
        else:
            # Java returned matches or no-match
            py_matches = check_case_with_engine(engine, rule, text)
            assert len(py_matches) == oracle_res["matches_count"], (
                f"Match count mismatch for synthetic case {case_id} ({full_rule_id}): "
                f"expected {oracle_res['matches_count']}, got {len(py_matches)}"
            )

            for py_m, java_m in zip(py_matches, oracle_res.get("matches", [])):
                assert py_m.from_pos_utf16 == java_m["from_utf16"], f"Start offset mismatch in case {case_id}"
                assert py_m.to_pos_utf16 == java_m["to_utf16"], f"End offset mismatch in case {case_id}"
                assert py_m.message == java_m["message"], f"Message mismatch in case {case_id}"
                assert py_m.suggestions == java_m["suggestions"], f"Suggestions mismatch in case {case_id}"


def test_filters_russian_rules_oracle_parity():
    """Verify parity for 19 promoted Russian rules against example cases."""
    fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "oracle_filters_russian_rules.json"
    assert fixture_path.is_file(), f"Missing Russian rules fixture: {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Load default rules
    engine = RussianGrammarEngine.get_instance()

    # Use test mode clock to align with JUnit Volkswagen-style test mode (2014)
    SystemClock.is_test_mode = True
    SystemClock._override_now = None

    for case in data["cases"]:
        case_id = case["id"]
        full_rule_id = case["full_rule_id"]
        text = case["text"]
        oracle_res = case["oracle_result"]

        rule = engine.get_rule(full_rule_id)
        assert rule is not None, f"Russian rule {full_rule_id} not found in grammar engine"

        py_matches = check_case_with_engine(engine, rule, text)
        assert len(py_matches) == oracle_res["matches_count"], (
            f"Match count mismatch for Russian rule case {case_id} ({full_rule_id}): "
            f"expected {oracle_res['matches_count']}, got {len(py_matches)}"
        )

        for py_m, java_m in zip(py_matches, oracle_res.get("matches", [])):
            assert py_m.from_pos_utf16 == java_m["from_utf16"], f"Start offset mismatch in case {case_id}"
            assert py_m.to_pos_utf16 == java_m["to_utf16"], f"End offset mismatch in case {case_id}"

            # Message check: JLanguageTool might escape/replace formatting.
            # Clean spaces/periods for robust matching, or compare directly.
            assert py_m.message == java_m["message"], f"Message mismatch in case {case_id}"

            # Suggestion check
            assert py_m.suggestions == java_m["suggestions"], f"Suggestions mismatch in case {case_id}"
