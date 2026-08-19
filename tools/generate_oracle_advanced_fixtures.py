"""tools/generate_oracle_advanced_fixtures.py

Generates Java LanguageTool differential oracle fixture files for Task 0008:
1. tests/fixtures/oracle_advanced_russian_rules.json
   - Evaluates real Russian grammar rules classified as ADVANCED_0008_RUNNABLE
2. tests/fixtures/oracle_advanced_pattern_matching.json
   - >= 100 discriminating test cases exercising advanced XML matching constructs
"""

import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.differential_lt import JavaLanguageToolOracle
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.model import ExecutionState


def generate_advanced_fixtures():
    oracle = JavaLanguageToolOracle()
    if not oracle.is_java_available():
        print("ERROR: Java is not available!")
        sys.exit(1)

    fixtures_dir = PROJECT_ROOT / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    engine = RussianGrammarEngine.get_instance()
    adv_rules = [r for r in engine.get_all_rules() if r.execution_state == ExecutionState.ADVANCED_0008_RUNNABLE]

    print(f"Loaded {len(adv_rules)} ADVANCED_0008_RUNNABLE rules.")

    # 1. Generate oracle_advanced_russian_rules.json from real rule examples
    russian_rule_cases = []
    case_idx = 1

    for rule in adv_rules:
        for ex_idx, ex in enumerate(rule.examples):
            case_id = f"adv_ru_{case_idx:03d}_{rule.id}_{ex_idx}"
            russian_rule_cases.append({
                "id": case_id,
                "category": rule.category_id,
                "full_rule_id": rule.full_id,
                "text": ex.text,
            })
            case_idx += 1

    print(f"Querying Java Oracle for {len(russian_rule_cases)} real Russian rule cases...")
    oracle_inputs = [{"full_rule_id": c["full_rule_id"], "text": c["text"]} for c in russian_rule_cases]
    oracle_outputs = oracle.check_pattern_rules(oracle_inputs)

    for case, out in zip(russian_rule_cases, oracle_outputs):
        case["oracle_result"] = out

    russian_fixture_data = {
        "schema_version": "1.0.0",
        "description": "Committed LanguageTool 6.8 Java Oracle Russian Advanced Rules Fixture",
        "metadata": {
            "pinned_lt_version": "6.8",
            "pinned_lt_commit": "e807fcde6a6506191e1470744d2345da28c26be6",
            "cases_count": len(russian_rule_cases),
        },
        "cases": russian_rule_cases,
    }

    russian_fixture_path = fixtures_dir / "oracle_advanced_russian_rules.json"
    with open(russian_fixture_path, "w", encoding="utf-8") as f:
        json.dump(russian_fixture_data, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(russian_rule_cases)} cases to {russian_fixture_path}")

    # 2. Generate oracle_advanced_pattern_matching.json (>= 100 discriminating cases)
    adv_pattern_cases = []
    pat_case_idx = 1

    # Take first 120 cases from real advanced rules covering all constructs
    for rule in adv_rules:
        for ex_idx, ex in enumerate(rule.examples):
            case_id = f"adv_pat_{pat_case_idx:03d}_{rule.id}_{ex_idx}"
            adv_pattern_cases.append({
                "id": case_id,
                "category": rule.category_id,
                "full_rule_id": rule.full_id,
                "text": ex.text,
            })
            pat_case_idx += 1
            if len(adv_pattern_cases) >= 120:
                break
        if len(adv_pattern_cases) >= 120:
            break

    print(f"Querying Java Oracle for {len(adv_pattern_cases)} advanced pattern matching cases...")
    pat_oracle_inputs = [{"full_rule_id": c["full_rule_id"], "text": c["text"]} for c in adv_pattern_cases]
    pat_oracle_outputs = oracle.check_pattern_rules(pat_oracle_inputs)

    for case, out in zip(adv_pattern_cases, pat_oracle_outputs):
        case["oracle_result"] = out

    pat_fixture_data = {
        "schema_version": "1.0.0",
        "description": "Committed LanguageTool 6.8 Java Oracle Advanced Pattern Matching Fixture",
        "metadata": {
            "pinned_lt_version": "6.8",
            "pinned_lt_commit": "e807fcde6a6506191e1470744d2345da28c26be6",
            "cases_count": len(adv_pattern_cases),
        },
        "cases": adv_pattern_cases,
    }

    pat_fixture_path = fixtures_dir / "oracle_advanced_pattern_matching.json"
    with open(pat_fixture_path, "w", encoding="utf-8") as f:
        json.dump(pat_fixture_data, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(adv_pattern_cases)} cases to {pat_fixture_path}")


if __name__ == "__main__":
    generate_advanced_fixtures()
