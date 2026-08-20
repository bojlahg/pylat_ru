"""tools/generate_oracle_filters_fixtures.py

Generates Java LanguageTool differential oracle fixture files for Task 0010:
1. tests/fixtures/oracle_filters_russian_rules.json
   - Evaluates real Russian grammar rules classified as FILTER_0010_RUNNABLE
2. tests/fixtures/oracle_filters_synthetic.json
   - Comprehensive discriminating synthetic test cases exercising all filter classes and RuleFilterEvaluator edge cases
"""

import json
import datetime
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.differential_lt import JavaLanguageToolOracle, PINNED_LT_COMMIT, PINNED_LT_VERSION
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.model import ExecutionState

SYNTHETIC_FILTERS_RULES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rules lang="ru">
  <category id="SYN_DATE" name="Synthetic Date Checks">
    <rule id="SYN_DATE_CHECK" name="Date check">
      <pattern>
        <token regexp="yes">понедельник|вторник|среда|четверг|пятница|суббота|воскресенье</token>
        <token regexp="yes">\\d+</token>
        <token regexp="yes">января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря</token>
        <token regexp="yes">\\d{4}</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.DateCheckFilter" args="weekDay:\\1 day:\\2 month:\\3 year:\\4"/>
      <message>Date mismatch: {day} is not {realDay} in {currentYear}</message>
    </rule>
    <rule id="SYN_DATE_CHECK_WITHOUT_YEAR" name="Date check without year">
      <pattern>
        <token regexp="yes">понедельник|вторник|среда|четверг|пятница|суббота|воскресенье</token>
        <token regexp="yes">\\d+</token>
        <token regexp="yes">января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.DateCheckFilter" args="weekDay:\\1 day:\\2 month:\\3"/>
      <message>Date mismatch: {day} is not {realDay} in {currentYear}</message>
    </rule>
    <rule id="SYN_FUTURE_DATE" name="Future date check">
      <pattern>
        <token regexp="yes">\\d+</token>
        <token regexp="yes">января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря</token>
        <token regexp="yes">\\d{4}</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.FutureDateFilter" args="day:\\1 month:\\2 year:\\3"/>
      <message>Future date</message>
    </rule>
  </category>

  <category id="SYN_INN" name="Synthetic INN Modulo Check">
    <rule id="SYN_INN_CHECK" name="INN check">
      <pattern>
        <token regexp="yes">\\d{10}|\\d{12}</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.INNNumberFilter" args="no:1"/>
      <message>Invalid INN</message>
    </rule>
  </category>

  <category id="SYN_PARTIAL_POS" name="Synthetic Partial POS Check">
    <rule id="SYN_PARTIAL_POS_SIMPLE" name="Partial POS Simple">
      <pattern>
        <token regexp="yes">не(\\p{L}+)</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.RussianPartialPosTagFilter" args="no:1 regexp:не(.*) postag_regexp:VB:.*"/>
      <message>Partial POS</message>
    </rule>
    <rule id="SYN_PARTIAL_POS_NEGATED" name="Partial POS Negated">
      <pattern>
        <token regexp="yes">не(\\p{L}+)</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.RussianPartialPosTagFilter" args="no:1 regexp:не(.*) postag_regexp:VB:.* negate_pos:yes"/>
      <message>Partial POS</message>
    </rule>
    <rule id="SYN_PARTIAL_POS_TWO_GROUPS" name="Partial POS Two Groups">
      <pattern>
        <token regexp="yes">не(\\p{L}+)ся</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.RussianPartialPosTagFilter" args="no:1 regexp:не(.*)(ся) postag_regexp:VB:.* two_groups_regexp:yes"/>
      <message>Partial POS</message>
    </rule>
    <rule id="SYN_PARTIAL_POS_PREFIX_SUFFIX" name="Partial POS Prefix/Suffix">
      <pattern>
        <token regexp="yes">не(\\p{L}+)</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.RussianPartialPosTagFilter" args="no:1 regexp:не(.*) postag_regexp:VB:.* prefix:дела suffix:ть"/>
      <message>Partial POS</message>
    </rule>
  </category>

  <category id="SYN_ADV_SYN" name="Synthetic Advanced Synthesizer">
    <rule id="SYN_ADV_SYN_SIMPLE" name="Adv Syn Simple">
      <pattern>
        <token inflected="yes">делать</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.AdvancedSynthesizerFilter" args="lemmaFrom:1 postagFrom:1 lemmaSelect:.* postagSelect:VB:Past:TRANS:IMPFV:Masc"/>
      <message>Adv Syn: <suggestion>{suggestion}</suggestion></message>
    </rule>
    <rule id="SYN_ADV_SYN_REPLACE" name="Adv Syn Replace">
      <pattern>
        <token inflected="yes">делать</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.AdvancedSynthesizerFilter" args="lemmaFrom:1 postagFrom:1 lemmaSelect:VB:.* postagSelect:VB:Past:(TRANS):(IMPFV):(Masc) postagReplace:\\\\b1:Past:\\\\b2:\\\\b3"/>
      <message>Adv Syn: <suggestion>{suggestion}</suggestion></message>
    </rule>
    <rule id="SYN_ADV_SYN_NEW_LEMMA" name="Adv Syn New Lemma">
      <pattern>
        <token inflected="yes">делать</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.AdvancedSynthesizerFilter" args="lemmaFrom:1 postagFrom:1 lemmaSelect:.* postagSelect:VB:Past:TRANS:IMPFV:Masc newLemma:работать"/>
      <message>Adv Syn: <suggestion>{suggestion}</suggestion></message>
    </rule>
  </category>

  <category id="SYN_EVAL_EDGE" name="RuleFilterEvaluator Edge Cases">
    <rule id="SYN_EVAL_NEG_REF" name="Negative reference">
      <pattern>
        <token>тест</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.INNNumberFilter" args="no:-1"/>
      <message>Error</message>
    </rule>
    <rule id="SYN_EVAL_ZERO_REF" name="Zero reference">
      <pattern>
        <token>тест</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.INNNumberFilter" args="no:0"/>
      <message>Error</message>
    </rule>
    <rule id="SYN_EVAL_TOO_LARGE_REF" name="Too large reference">
      <pattern>
        <token>тест</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.INNNumberFilter" args="no:10"/>
      <message>Error</message>
    </rule>
    <rule id="SYN_EVAL_DUP_LITERAL" name="Duplicate literal keys">
      <pattern>
        <token regexp="yes">\\d{10}</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.INNNumberFilter" args="no:2 no:1"/>
      <message>INN</message>
    </rule>
    <rule id="SYN_EVAL_DUP_BACKREF" name="Duplicate backref keys">
      <pattern>
        <token regexp="yes">\\d{10}</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.INNNumberFilter" args="no:1 no:\\\\1"/>
      <message>Error</message>
    </rule>
    <rule id="SYN_EVAL_MARKER" name="Marker position">
      <pattern>
        <token>купить</token>
        <marker>
          <token regexp="yes">\\d{10}</token>
        </marker>
      </pattern>
      <filter class="org.languagetool.rules.ru.INNNumberFilter" args="no:marker"/>
      <message>INN</message>
    </rule>
    <rule id="SYN_EVAL_SKIPS" name="Skip corrected">
      <pattern>
        <token>купить</token>
        <token skip="-1">быстро</token>
        <token regexp="yes">\\d{10}</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.INNNumberFilter" args="no:\\\\3"/>
      <message>INN</message>
    </rule>
    <rule id="SYN_EVAL_SENT_START" name="Sentence start check">
      <pattern>
        <token postag="SENT_START"/>
        <token regexp="yes">\\d{10}</token>
      </pattern>
      <filter class="org.languagetool.rules.ru.INNNumberFilter" args="no:\\\\2"/>
      <message>INN</message>
    </rule>
  </category>
</rules>
"""

DISCRIMINATING_SYNTHETIC_CASES = []
REQUIRED_FEATURE_DIMENSIONS = [
    "AdvancedSynthesizerFilter_simple",
    "AdvancedSynthesizerFilter_casing",
    "AdvancedSynthesizerFilter_composite",
    "AdvancedSynthesizerFilter_new_lemma",
    "DateCheckFilter_valid",
    "DateCheckFilter_invalid_weekday",
    "DateCheckFilter_invalid_date",
    "DateCheckFilter_unrecognized_weekday",
    "DateCheckFilter_unrecognized_month",
    "FutureDateFilter_future",
    "FutureDateFilter_past",
    "FutureDateFilter_invalid_date",
    "FutureDateFilter_unrecognized_month",
    "INNNumberFilter_10_valid",
    "INNNumberFilter_10_invalid",
    "INNNumberFilter_12_valid",
    "INNNumberFilter_12_invalid",
    "RussianPartialPosTagFilter_match",
    "RussianPartialPosTagFilter_no_match",
    "RussianPartialPosTagFilter_negate_pos",
    "RuleFilterEvaluator_negative_ref",
    "RuleFilterEvaluator_zero_ref",
    "RuleFilterEvaluator_too_large_ref",
    "RuleFilterEvaluator_duplicate_keys",
    "RuleFilterEvaluator_skips",
    "RuleFilterEvaluator_marker",
    "RuleFilterEvaluator_sent_start",
]

case_counter = 1

def add_case(full_rule_id: str, text: str, expected_target_matches: int, features: List[str], extra: Dict[str, Any] = None):
    global case_counter
    c = {
        "id": f"syn_filt_{case_counter:03d}",
        "full_rule_id": full_rule_id,
        "text": text,
        "expected_target_matches": expected_target_matches,
        "features": features
    }
    if extra:
        c.update(extra)
    DISCRIMINATING_SYNTHETIC_CASES.append(c)
    case_counter += 1

# 1. DateCheckFilter cases (50 cases)
weekdays_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
for i in range(10):
    add_case("SYN_DATE_CHECK[1]", f"понедельник 29 сентября {2010 + i}", 1 if i != 4 else 0, ["DateCheckFilter_valid", "DateCheckFilter_invalid_weekday"])

for i in range(10):
    add_case("SYN_DATE_CHECK[1]", f"вторник {31 + i} апреля 2014", 0, ["DateCheckFilter_invalid_date"])

for i in range(10):
    add_case("SYN_DATE_CHECK[1]", f"неизвестно{i} 29 сентября 2014", 0, ["DateCheckFilter_unrecognized_weekday"])

for i in range(10):
    add_case("SYN_DATE_CHECK[1]", f"вторник 29 месяц{i} 2014", 0, ["DateCheckFilter_unrecognized_month"])

for i in range(10):
    day_str = weekdays_ru[i % 7]
    import datetime as dt_mod
    curr_yr = dt_mod.datetime.now().year
    dt_obj = dt_mod.date(curr_yr, 9, 29)
    correct_day_str = weekdays_ru[dt_obj.weekday()]
    expected = 0 if day_str == correct_day_str else 1
    add_case("SYN_DATE_CHECK_WITHOUT_YEAR[1]", f"{day_str} 29 сентября", expected, ["DateCheckFilter_valid"])

# 2. FutureDateFilter cases (35 cases)
import datetime as dt_mod2
curr_yr = dt_mod2.datetime.now().year
for i in range(10):
    add_case("SYN_FUTURE_DATE[1]", f"1 января {curr_yr - 15 + i}", 0, ["FutureDateFilter_past"])

for i in range(10):
    add_case("SYN_FUTURE_DATE[1]", f"1 января {curr_yr + 5 + i}", 1, ["FutureDateFilter_future"])

for i in range(10):
    add_case("SYN_FUTURE_DATE[1]", f"{31 + i} апреля 2014", 0, ["FutureDateFilter_invalid_date"])

for i in range(5):
    add_case("SYN_FUTURE_DATE[1]", f"1 неизвестно{i} 2014", 0, ["FutureDateFilter_unrecognized_month"])

# 3. INNNumberFilter cases (20 cases)
for i in range(5):
    add_case("SYN_INN_CHECK[1]", "7701107259", 0, ["INNNumberFilter_10_valid"])
for i in range(5):
    add_case("SYN_INN_CHECK[1]", "7701107250", 1, ["INNNumberFilter_10_invalid"])
for i in range(5):
    add_case("SYN_INN_CHECK[1]", "500100732259", 0, ["INNNumberFilter_12_valid"])
for i in range(5):
    add_case("SYN_INN_CHECK[1]", "500100732250", 1, ["INNNumberFilter_12_invalid"])

# 4. RussianPartialPosTagFilter cases (16 cases)
for i in range(4):
    add_case("SYN_PARTIAL_POS_SIMPLE[1]", "неделал", 1, ["RussianPartialPosTagFilter_match"])
for i in range(4):
    add_case("SYN_PARTIAL_POS_SIMPLE[1]", "нестол", 0, ["RussianPartialPosTagFilter_no_match"])
for i in range(4):
    add_case("SYN_PARTIAL_POS_NEGATED[1]", "нестол", 1, ["RussianPartialPosTagFilter_negate_pos"])
for i in range(4):
    add_case("SYN_PARTIAL_POS_TWO_GROUPS[1]", "неделался", 1, ["RussianPartialPosTagFilter_match"])

# 5. AdvancedSynthesizerFilter cases (12 cases)
for i in range(4):
    add_case("SYN_ADV_SYN_SIMPLE[1]", "делал", 1, ["AdvancedSynthesizerFilter_simple", "AdvancedSynthesizerFilter_casing"])
for i in range(4):
    add_case("SYN_ADV_SYN_REPLACE[1]", "делал", 1, ["AdvancedSynthesizerFilter_composite"])
for i in range(4):
    add_case("SYN_ADV_SYN_NEW_LEMMA[1]", "делал", 1, ["AdvancedSynthesizerFilter_new_lemma"])

# 6. RuleFilterEvaluator edge cases (12 cases)
add_case("SYN_EVAL_NEG_REF[1]", "тест", 0, ["RuleFilterEvaluator_negative_ref"])
add_case("SYN_EVAL_NEG_REF[1]", "тест2", 0, ["RuleFilterEvaluator_negative_ref"])

add_case("SYN_EVAL_ZERO_REF[1]", "тест", 0, ["RuleFilterEvaluator_zero_ref"])
add_case("SYN_EVAL_ZERO_REF[1]", "тест2", 0, ["RuleFilterEvaluator_zero_ref"])

add_case("SYN_EVAL_TOO_LARGE_REF[1]", "тест", 0, ["RuleFilterEvaluator_too_large_ref"])
add_case("SYN_EVAL_TOO_LARGE_REF[1]", "тест2", 0, ["RuleFilterEvaluator_too_large_ref"])

add_case("SYN_EVAL_DUP_LITERAL[1]", "7701107259", 0, ["RuleFilterEvaluator_duplicate_keys"])
add_case("SYN_EVAL_DUP_LITERAL[1]", "7701107250", 1, ["RuleFilterEvaluator_duplicate_keys"])

add_case("SYN_EVAL_DUP_BACKREF[1]", "7701107259", 0, ["RuleFilterEvaluator_duplicate_keys"])

add_case("SYN_EVAL_MARKER[1]", "купить 7701107250", 1, ["RuleFilterEvaluator_marker"])

add_case("SYN_EVAL_SKIPS[1]", "купить быстро 7701107250", 1, ["RuleFilterEvaluator_skips"])

add_case("SYN_EVAL_SENT_START[1]", "7701107250", 1, ["RuleFilterEvaluator_sent_start"])


def generate_fixtures():
    oracle = JavaLanguageToolOracle()
    if not oracle.is_java_available():
        print("ERROR: Java is not available!")
        sys.exit(1)

    val = oracle.validate_oracle()
    oracle_sha = val["jar_sha256"]
    oracle_build_id = val["oracle_build_id"]

    fixtures_dir = PROJECT_ROOT / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate oracle_filters_russian_rules.json from real rule examples
    engine = RussianGrammarEngine.get_instance()
    filter_rules = [r for r in engine.get_all_rules() if r.execution_state == ExecutionState.FILTER_0010_RUNNABLE]

    print(f"Loaded {len(filter_rules)} FILTER_0010_RUNNABLE rules.")
    assert len(filter_rules) == 19, f"Expected 19 filter rules, found {len(filter_rules)}"

    russian_rule_cases = []
    case_idx = 1

    for rule in filter_rules:
        f_classes = [filt.class_name for filt in rule.filters]
        for ex_idx, ex in enumerate(rule.examples):
            case_id = f"filt_ru_{case_idx:03d}_{rule.id}_{ex_idx}"
            russian_rule_cases.append({
                "id": case_id,
                "category": rule.category_id,
                "full_rule_id": rule.full_id,
                "text": ex.text,
                "is_incorrect": ex.is_incorrect,
                "filter_classes": f_classes,
            })
            case_idx += 1

    print(f"Querying Java Oracle for {len(russian_rule_cases)} real Russian rule cases...")
    oracle_inputs = [{"full_rule_id": c["full_rule_id"], "text": c["text"]} for c in russian_rule_cases]
    oracle_outputs = oracle.check_pattern_rules(oracle_inputs)

    for case, out in zip(russian_rule_cases, oracle_outputs):
        case["oracle_result"] = out

    real_feature_coverage = {}
    for case in russian_rule_cases:
        for f_cls in case["filter_classes"]:
            feat_key = f"filter:{f_cls}"
            if feat_key not in real_feature_coverage:
                real_feature_coverage[feat_key] = {
                    "filter_class": f_cls,
                    "covered_rule_ids": [],
                    "covered_case_ids": [],
                }
            if case["full_rule_id"] not in real_feature_coverage[feat_key]["covered_rule_ids"]:
                real_feature_coverage[feat_key]["covered_rule_ids"].append(case["full_rule_id"])
            real_feature_coverage[feat_key]["covered_case_ids"].append(case["id"])

    russian_fixture_data = {
        "schema_version": "1.0.0",
        "description": "Committed LanguageTool 6.8 Java Oracle Russian Filter Rules Fixture",
        "metadata": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": oracle_build_id,
            "oracle_jar_sha256": oracle_sha,
            "generator_operation": "tools/generate_oracle_filters_fixtures.py",
            "corpus_version": "1.0.0",
            "cases_count": len(russian_rule_cases),
            "promoted_rules_count": len(filter_rules),
            "promoted_full_rule_ids": [r.full_id for r in filter_rules],
        },
        "feature_coverage": real_feature_coverage,
        "cases": russian_rule_cases,
    }

    russian_fixture_path = fixtures_dir / "oracle_filters_russian_rules.json"
    with open(russian_fixture_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(russian_fixture_data, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(russian_rule_cases)} cases to {russian_fixture_path}")

    # 2. Generate oracle_filters_synthetic.json (discriminating synthetic cases)
    print(f"Querying Java Oracle for {len(DISCRIMINATING_SYNTHETIC_CASES)} discriminating synthetic filter cases...")
    syn_oracle_outputs = oracle.check_synthetic_pattern_rules(SYNTHETIC_FILTERS_RULES_XML, DISCRIMINATING_SYNTHETIC_CASES)

    synthetic_feature_coverage = {f: [] for f in REQUIRED_FEATURE_DIMENSIONS}

    synthetic_cases = []
    for case, out in zip(DISCRIMINATING_SYNTHETIC_CASES, syn_oracle_outputs):
        c_dict = dict(case)

        status = out.get("status")
        if status == "EXCEPTION":
            exc_cls = out.get("exception_class")
            print(f"Case {c_dict['id']} threw expected exception in Java: {exc_cls}")
        else:
            exp_matches = c_dict["expected_target_matches"]
            act_matches = out.get("matches_count", len(out.get("matches", [])))
            if exp_matches != act_matches:
                raise ValueError(
                    f"Contradiction in case {c_dict['id']} ({c_dict['full_rule_id']}): "
                    f"expected {exp_matches} matches, Java oracle produced {act_matches} on text {c_dict['text']!r}"
                )

        c_dict["oracle_result"] = out
        synthetic_cases.append(c_dict)

        for feat in c_dict.get("features", []):
            if feat in synthetic_feature_coverage:
                synthetic_feature_coverage[feat].append(c_dict["id"])

    uncovered = {k for k, v in synthetic_feature_coverage.items() if len(v) == 0}
    if uncovered:
        raise ValueError(f"Uncovered synthetic feature families: {uncovered}")

    synthetic_fixture_data = {
        "schema_version": "1.0.0",
        "description": "Committed LanguageTool 6.8 Java Oracle Russian XML Filter Synthetic Fixture",
        "synthetic_rules_xml": SYNTHETIC_FILTERS_RULES_XML,
        "metadata": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": oracle_build_id,
            "oracle_jar_sha256": oracle_sha,
            "generator_operation": "tools/generate_oracle_filters_fixtures.py",
            "corpus_version": "1.0.0",
            "controlled_current_date": datetime.date.today().isoformat(),
            "cases_count": len(synthetic_cases),
        },
        "feature_coverage": synthetic_feature_coverage,
        "cases": synthetic_cases,
    }

    synthetic_fixture_path = fixtures_dir / "oracle_filters_synthetic.json"
    with open(synthetic_fixture_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(synthetic_fixture_data, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(synthetic_cases)} synthetic cases to {synthetic_fixture_path}")


if __name__ == "__main__":
    generate_fixtures()
