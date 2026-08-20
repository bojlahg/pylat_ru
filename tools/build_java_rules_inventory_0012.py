"""Build Task-0012 compatibility/provenance inventories deterministically.

Extends the Task-0011 registration inventory to all 23 ordinary Russian rules,
records the transitive spelling resource set, and refreshes the compatibility
and oracle-manifest accounting.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIN = "e807fcde6a6506191e1470744d2345da28c26be6"
CORE = "languagetool-core/src/main/java/org/languagetool/rules"
RU = "languagetool-language-modules/ru/src/main/java/org/languagetool/rules/ru"
CORE_TEST = "languagetool-core/src/test/java/org/languagetool/rules"
RU_TEST = "languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru"

# Resources reached at runtime by MorfologikSpellerRule + SpellingCheckRule.
SPELLING_RESOURCES = [
    "/ru/hunspell/ru_RU.dict",
    "/ru/hunspell/ru_RU.info",
    "/ru/hunspell/ignore.txt",
    "/ru/hunspell/spelling.txt",
    "/ru/hunspell/prohibit.txt",
    "spelling_global.txt",
]
YO_SPELLING_RESOURCES = [
    "/ru/hunspell/ru_RU_yo.dict",
    "/ru/hunspell/ru_RU_yo.info",
    "/ru/hunspell/ignore.txt",
    "/ru/hunspell/spelling.txt",
    "/ru/hunspell/prohibit.txt",
    "spelling_global.txt",
]

# class, id, kind, category, default_off, line, constructor, classification,
# resource dependencies, upstream tests, configured priority target/value
ROWS = [
    ("CommaWhitespaceRule", "COMMA_PARENTHESIS_WHITESPACE", "generic", "TYPOGRAPHY", False, 161, "messages, incorrect example, correct example", "TASK_0011", [], [f"{CORE_TEST}/CommaWhitespaceRuleTest.java"], None),
    ("UppercaseSentenceStartRule", "UPPERCASE_SENTENCE_START", "generic", "CASING", False, 165, "messages, Russian language, incorrect example, correct example", "TASK_0011", [], [f"{CORE_TEST}/UppercaseSentenceStartRuleTest.java"], None),
    ("MorfologikRussianSpellerRule", "MORFOLOGIK_RULE_RU_RU", "russian_specific", "TYPOS", False, 168, "messages, Russian language, userConfig, altLanguages", "TASK_0012", SPELLING_RESOURCES, [f"{RU_TEST}/MorfologikRussianSpellerRuleTest.java"], ("MORFOLOGIC_RULE_RU_RU", 1)),
    ("MultipleWhitespaceRule", "WHITESPACE_RULE", "generic", "TYPOGRAPHY", False, 170, "messages, Russian language", "TASK_0011", [], [f"{CORE_TEST}/MultipleWhitespaceRuleTest.java"], None),
    ("SentenceWhitespaceRule", "SENTENCE_WHITESPACE", "generic", "TYPOGRAPHY", False, 171, "messages", "TASK_0011", [], [f"{CORE_TEST}/SentenceWhitespaceRuleTest.java"], None),
    ("WhiteSpaceBeforeParagraphEnd", "WHITESPACE_PARAGRAPH", "generic", "STYLE", True, 172, "messages, Russian language", "TASK_0011", [], [], None),
    ("WhiteSpaceAtBeginOfParagraph", "WHITESPACE_PARAGRAPH_BEGIN", "generic", "STYLE", True, 173, "messages", "TASK_0011", [], [], None),
    ("LongSentenceRule", "TOO_LONG_SENTENCE", "generic", "STYLE", False, 175, "messages, userConfig, 50", "TASK_0011", [], [f"{CORE_TEST}/LongSentenceRuleTest.java"], None),
    ("LongParagraphRule", "TOO_LONG_PARAGRAPH", "generic", "STYLE", True, 176, "messages, Russian language, userConfig", "TASK_0011", [], [f"{CORE_TEST}/LongParagraphRuleTest.java"], ("TOO_LONG_PARAGRAPH", -15)),
    ("ParagraphRepeatBeginningRule", "PARAGRAPH_REPEAT_BEGINNING_RULE", "generic", "STYLE", True, 177, "messages, Russian language", "TASK_0011", [], [], None),
    ("RussianFillerWordsRule", "FILLER_WORDS_RU", "russian_specific", "CREATIVE_WRITING", True, 178, "messages, Russian language, userConfig", "TASK_0011", [], [], None),
    ("PunctuationMarkAtParagraphEnd2", "PUNCTUATION_PARAGRAPH_END2", "generic", "PUNCTUATION", True, 180, "messages, Russian language", "TASK_0011", [], [f"{CORE_TEST}/PunctuationMarkAtParagraphEnd2Test.java"], ("PUNCT_DPT_2", -2)),
    ("MorfologikRussianYOSpellerRule", "MORFOLOGIK_RULE_RU_RU_YO", "russian_specific", "TYPOS", True, 186, "messages, Russian language, userConfig, altLanguages", "TASK_0012", YO_SPELLING_RESOURCES, [f"{RU_TEST}/MorfologikRussianYOSpellerRuleTest.java"], ("MORFOLOGIC_RULE_RU_RU_YO", 2)),
    ("RussianUnpairedBracketsRule", "RU_UNPAIRED_BRACKETS", "russian_specific", "PUNCTUATION", False, 187, "messages, Russian language", "TASK_0011", [], [f"{RU_TEST}/RussianUnpairedBracketsRuleTest.java"], None),
    ("RussianCompoundRule", "RU_COMPOUNDS", "russian_specific", "MISC", False, 188, "messages, Russian language, userConfig", "TASK_0012", ["/ru/compounds.txt"], [f"{RU_TEST}/RussianCompoundRuleTest.java"], ("RU_COMPOUNDS", 11)),
    ("RussianSimpleReplaceRule", "RU_SIMPLE_REPLACE", "russian_specific", "MISC", False, 189, "messages", "TASK_0012", ["/ru/replace.txt"], [f"{RU_TEST}/RussianSimpleReplaceRuleTest.java"], ("RUSSIAN_SIMPLE_REPLACE_RULE", 10)),
    ("RussianSimpleWordRepeatRule", "WORD_REPEAT_RULE", "russian_specific", "MISC", False, 190, "messages, Russian language", "TASK_0012", [], [], None),
    ("RussianWordCoherencyRule", "RU_WORD_COHERENCY", "russian_specific", "MISC", False, 191, "messages", "TASK_0012", ["/ru/coherency.txt"], [f"{RU_TEST}/RussianWordCoherencyRuleTest.java"], None),
    ("RussianWordRepeatRule", "RU_WORD_REPEAT", "russian_specific", "MISC", True, 192, "messages", "TASK_0012", [], [f"{RU_TEST}/RussianWordRepeatRuleTest.java"], None),
    ("RussianWordRootRepeatRule", "RU_WORD_ROOT_REPEAT", "russian_specific", "MISC", True, 193, "messages", "TASK_0012", ["/ru/wordrootrep.txt"], [], ("Word_root_repeat", -1)),
    ("RussianVerbConjugationRule", "RU_VERB_CONJUGATION", "russian_specific", "GRAMMAR", False, 194, "messages", "TASK_0011", [], [f"{RU_TEST}/RussianVerbConjugationRuleTest.java"], None),
    ("RussianDashRule", "RU_DASH_RULE", "russian_specific", "TYPOGRAPHY", False, 195, "messages", "TASK_0011", ["/ru/compounds.txt"], [f"{RU_TEST}/RussianDashRuleTest.java"], ("RU_DASH_RULE", 12)),
    ("RussianSpecificCaseRule", "RU_SPECIFIC_CASE", "russian_specific", "CASING", False, 196, "messages", "TASK_0011", ["/ru/specific_case.txt"], [f"{RU_TEST}/RussianSpecificCaseRuleTest.java"], ("RUSSIAN_SPECIFIC_CASE", 9)),
]

# Base classes whose behavior is observable through the Task-0012 leaf rules.
INHERITED_SOURCES = {
    "MorfologikRussianSpellerRule": [
        f"{CORE}/spelling/morfologik/MorfologikSpellerRule.java",
        f"{CORE}/spelling/morfologik/MorfologikMultiSpeller.java",
        f"{CORE}/spelling/morfologik/MorfologikSpeller.java",
        f"{CORE}/spelling/morfologik/WeightedSuggestion.java",
        f"{CORE}/spelling/SpellingCheckRule.java",
        f"{CORE}/spelling/CachingWordListLoader.java",
    ],
    "MorfologikRussianYOSpellerRule": [
        f"{CORE}/spelling/morfologik/MorfologikSpellerRule.java",
        f"{CORE}/spelling/morfologik/MorfologikMultiSpeller.java",
        f"{CORE}/spelling/morfologik/MorfologikSpeller.java",
        f"{CORE}/spelling/morfologik/WeightedSuggestion.java",
        f"{CORE}/spelling/SpellingCheckRule.java",
        f"{CORE}/spelling/CachingWordListLoader.java",
    ],
    "RussianCompoundRule": [f"{CORE}/AbstractCompoundRule.java", f"{CORE}/CompoundRuleData.java"],
    "RussianSimpleReplaceRule": [f"{CORE}/AbstractSimpleReplaceRule2.java"],
    "RussianSimpleWordRepeatRule": [f"{CORE}/WordRepeatRule.java"],
    "RussianWordCoherencyRule": [f"{CORE}/AbstractWordCoherencyRule.java", f"{CORE}/WordCoherencyDataLoader.java"],
    "RussianWordRepeatRule": [f"{CORE}/AdvancedWordRepeatRule.java"],
    "RussianWordRootRepeatRule": [f"{CORE}/AbstractWordCoherencyRule.java", f"{CORE}/WordCoherencyDataLoader.java"],
}

RUNTIME_RESOURCES = {
    "/ru/hunspell/ru_RU.dict": ("src/pylat_ru/resources/ru/hunspell/ru_RU.dict", "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/hunspell/ru_RU.dict"),
    "/ru/hunspell/ru_RU.info": ("src/pylat_ru/resources/ru/hunspell/ru_RU.info", "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/hunspell/ru_RU.info"),
    "/ru/hunspell/ru_RU_yo.dict": ("src/pylat_ru/resources/ru/hunspell/ru_RU_yo.dict", "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/hunspell/ru_RU_yo.dict"),
    "/ru/hunspell/ru_RU_yo.info": ("src/pylat_ru/resources/ru/hunspell/ru_RU_yo.info", "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/hunspell/ru_RU_yo.info"),
    "/ru/hunspell/spelling.txt": ("src/pylat_ru/resources/ru/hunspell/spelling.txt", "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/hunspell/spelling.txt"),
    "/ru/hunspell/ignore.txt": ("src/pylat_ru/resources/ru/hunspell/ignore.txt", "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/hunspell/ignore.txt"),
    "/ru/hunspell/prohibit.txt": ("src/pylat_ru/resources/ru/hunspell/prohibit.txt", "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/hunspell/prohibit.txt"),
    "spelling_global.txt": ("src/pylat_ru/resources/spelling_global.txt", "languagetool-core/src/main/resources/org/languagetool/resource/spelling_global.txt"),
    "/ru/compounds.txt": ("src/pylat_ru/resources/ru/compounds.txt", "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/compounds.txt"),
    "/ru/replace.txt": ("src/pylat_ru/resources/rules/ru/replace.txt", "languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/replace.txt"),
    "/ru/coherency.txt": ("src/pylat_ru/resources/rules/ru/coherency.txt", "languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/coherency.txt"),
    "/ru/wordrootrep.txt": ("src/pylat_ru/resources/rules/ru/wordrootrep.txt", "languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/wordrootrep.txt"),
    "/ru/specific_case.txt": ("src/pylat_ru/resources/ru/specific_case.txt", "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/specific_case.txt"),
}

FIXTURE_NAMES = (
    "oracle_java_rules_0012_spelling.json",
    "oracle_java_rules_0012_rules.json",
    "oracle_java_rules_0012_filter.json",
    "oracle_java_rules_0012_combined.json",
)


def _source_path(cls: str, kind: str) -> str:
    return f"{CORE}/{cls}.java" if kind == "generic" else f"{RU}/{cls}.java"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def build_inventory() -> None:
    base_priorities = {"TOO_LONG_SENTENCE": -101}
    rules = []
    for order, row in enumerate(ROWS):
        cls, rule_id, kind, category, default_off, line, ctor, classification, resources, tests, override = row
        source = _source_path(cls, kind)
        target, configured = override if override else (None, 0)
        effective = configured if target == rule_id else base_priorities.get(rule_id, -50 if "STYLE" in category else 0)
        inherited = []
        for rel in INHERITED_SOURCES.get(cls, []):
            inherited.append({"source_file": rel, "source_sha256": _hash(ROOT / "third_party" / "languagetool" / rel)})
        rules.append({
            "registration_order": order,
            "registration_line": line,
            "registration_location": "Russian.java:getRelevantRules",
            "rule_class": cls,
            "rule_id": rule_id,
            "kind": kind,
            "category_id": category,
            "default_off": default_off,
            "constructor_arguments": ctor,
            "classification": classification,
            "compatibility_status": (
                "NATIVE_0011_IMPLEMENTED" if classification == "TASK_0011" else "NATIVE_0012_IMPLEMENTED"
            ),
            "source_file": source,
            "source_sha256": _hash(ROOT / "third_party" / "languagetool" / source),
            "inherited_sources": inherited,
            "resource_dependencies": resources,
            "upstream_test_sources": tests,
            "configured_priority_target": target,
            "configured_priority": configured if target else None,
            "effective_priority": effective,
            "priority_binding_status": "BOUND" if target == rule_id else ("ORPHAN_OVERRIDE_ID" if target else "BASE_PRIORITY"),
        })

    runtime_resources = []
    for logical, (runtime_rel, upstream_rel) in sorted(RUNTIME_RESOURCES.items()):
        runtime_path = ROOT / runtime_rel
        upstream_path = ROOT / "third_party" / "languagetool" / upstream_rel
        runtime_resources.append({
            "upstream_path": logical,
            "vendored_path": upstream_rel,
            "packaged_path": runtime_rel,
            "size_bytes": upstream_path.stat().st_size,
            "sha256": _hash(upstream_path),
            "packaged_sha256": _hash(runtime_path),
            "byte_exact": _hash(upstream_path) == _hash(runtime_path),
            "license": "LGPL-2.1-or-later",
        })

    lm_source = f"{RU}/RussianConfusionProbabilityRule.java"
    filter_source = f"{RU}/RussianSuppressMisspelledSuggestionsFilter.java"
    filter_base = f"{CORE}/AbstractSuppressMisspelledSuggestionsFilter.java"
    inventory = {
        "schema_version": "1.0.0",
        "pinned_lt_commit": PIN,
        "registration_source": "languagetool-language-modules/ru/src/main/java/org/languagetool/language/Russian.java",
        "registration_source_sha256": _hash(ROOT / "third_party" / "languagetool" / "languagetool-language-modules/ru/src/main/java/org/languagetool/language/Russian.java"),
        "accounting": {
            "relevant_total": 23,
            "implemented_total": 23,
            "implemented_0011": 15,
            "implemented_0012": 8,
            "deferred_ordinary": 0,
            "generic_implemented": 10,
            "generic_total": 10,
            "russian_specific_implemented": 13,
            "russian_specific_total": 13,
            "language_model_total": 1,
            "language_model_implemented": 0,
        },
        "rules": rules,
        "runtime_resources": runtime_resources,
        "xml_filters": {
            "total": 7,
            "implemented": 7,
            "deferred": 0,
            "final_filter": {
                "class": "org.languagetool.rules.ru.RussianSuppressMisspelledSuggestionsFilter",
                "source_file": filter_source,
                "source_sha256": _hash(ROOT / "third_party" / "languagetool" / filter_source),
                "base_source_file": filter_base,
                "base_source_sha256": _hash(ROOT / "third_party" / "languagetool" / filter_base),
                "default_spelling_rule": "MORFOLOGIK_RULE_RU_RU",
            },
        },
        "language_model_rules": [{
            "rule_class": "RussianConfusionProbabilityRule",
            "rule_id": "CONFUSION_RULE",
            "registration_line": 204,
            "classification": "LANGUAGE_MODEL_DEFERRED",
            "source_file": lm_source,
            "source_sha256": _hash(ROOT / "third_party" / "languagetool" / lm_source),
        }],
        "priority_conflicts": [r["rule_id"] for r in rules if r["priority_binding_status"] == "ORPHAN_OVERRIDE_ID"],
    }
    _write(ROOT / "compat" / "russian_java_rules_inventory.json", inventory)


def update_compatibility() -> None:
    path = ROOT / "compat" / "compatibility.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    state = data["compatibility_status"]
    state["task_milestone"] = "0012_russian_spelling_compounds_replace_repeats"
    state["overall_state"] = "ORDINARY_JAVA_RULES_AND_XML_FILTERS_IMPLEMENTED"
    state["implementation_progress"]["java_rules"] = {
        "status": "IMPLEMENTED",
        "all_java_rules_total": 24,
        "relevant_rules": {
            "implemented": 23,
            "total": 23,
            "russian_specific_implemented": 13,
            "russian_specific_total": 13,
            "generic_implemented": 10,
            "generic_total": 10,
        },
        "deferred_ordinary": 0,
        "language_model_rules": {
            "implemented": 0,
            "total": 1,
            "rules": ["RussianConfusionProbabilityRule"],
            "status": "LANGUAGE_MODEL_DEFERRED",
        },
        "inventory": "compat/russian_java_rules_inventory.json",
    }

    state["implementation_progress"]["xml_filters"] = {
        "status": "IMPLEMENTED",
        "implemented": 7,
        "total": 7,
        "filter_classes": [
            "org.languagetool.rules.ru.AdvancedSynthesizerFilter",
            "org.languagetool.rules.ru.DateCheckFilter",
            "org.languagetool.rules.ru.FutureDateFilter",
            "org.languagetool.rules.ru.INNNumberFilter",
            "org.languagetool.rules.ru.NoDisambiguationRussianPartialPosTagFilter",
            "org.languagetool.rules.ru.RussianPartialPosTagFilter",
            "org.languagetool.rules.ru.RussianSuppressMisspelledSuggestionsFilter",
        ],
        "recognized_deferred": 0,
    }
    state["implementation_progress"]["grammar_xml_examples"] = {
        "status": "ALL_RUNNABLE",
        "runnable_examples_total": 2446,
        "deferred_examples_total": 0,
        "total_examples": 2446,
    }

    summary = state["summary"]
    summary["grammar_core_runnable_source_rules_total"] = 506
    summary["grammar_advanced_runnable_source_rules_total"] = 339
    summary["grammar_unification_runnable_source_rules_total"] = 24
    summary["grammar_filter_runnable_source_rules_total"] = 23
    summary["grammar_total_runnable_source_rules"] = 892
    summary["grammar_deferred_source_rules_total"] = 0
    summary["grammar_deferred_0010_source_rules_total"] = 0
    summary["grammar_deferred_0012_source_rules_total"] = 0
    summary["grammar_remaining_multi_blocker_source_rules_total"] = 0
    summary["grammar_unknown_source_rules_total"] = 0
    summary["grammar_python_runnable_compiled_variants_total"] = 907
    summary["grammar_runnable_examples_total"] = 2446
    summary["grammar_runnable_examples_incorrect_total"] = 1039
    summary["grammar_runnable_examples_correct_total"] = 1407
    summary["grammar_deferred_examples_total"] = 0
    summary["grammar_deferred_examples_incorrect_total"] = 0
    summary["grammar_deferred_examples_correct_total"] = 0
    summary["xml_filters_implemented"] = 7

    fixture_root = ROOT / "tests" / "fixtures"
    counts = {}
    for name in FIXTURE_NAMES:
        counts[name] = len(json.loads((fixture_root / name).read_text(encoding="utf-8"))["cases"])
    spelling = counts["oracle_java_rules_0012_spelling.json"]
    rules_cases = counts["oracle_java_rules_0012_rules.json"]
    filter_cases = counts["oracle_java_rules_0012_filter.json"]
    combined = counts["oracle_java_rules_0012_combined.json"]
    summary["task_0012_spelling_oracle_cases_total"] = spelling
    summary["task_0012_rules_oracle_cases_total"] = rules_cases
    summary["task_0012_filter_oracle_cases_total"] = filter_cases
    summary["task_0012_combined_pipeline_oracle_cases_total"] = combined
    summary["task_0012_total_oracle_cases"] = spelling + rules_cases + filter_cases + combined

    state["implementation_progress"]["parity_metrics"]["task_0012_java_rules"] = {
        "spelling_cases": spelling,
        "rule_cases": rules_cases,
        "filter_cases": filter_cases,
        "combined_pipeline_cases": combined,
        "total_cases": spelling + rules_cases + filter_cases + combined,
        "semantic_signatures_unique": True,
        "config_parity": "SUPPORTED",
        "overlap_filter_parity": "SUPPORTED",
        "same_rule_group_parity": "SUPPORTED",
        "suggestion_order_parity": "SUPPORTED",
        "full_observable_field_parity": 1.0,
    }
    _write(path, data)


def update_oracle_manifest() -> None:
    path = ROOT / "compat" / "oracle_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    bindings = [b for b in data["fixture_bindings"] if "java_rules_0012" not in b["path"]]
    for name in FIXTURE_NAMES:
        fixture = ROOT / "tests" / "fixtures" / name
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        bindings.append({
            "path": f"tests/fixtures/{name}",
            "size_bytes": fixture.stat().st_size,
            "sha256": _hash(fixture),
            "oracle_build_id": "lt_6.8_source_build_jdk17_stefan",
            "case_count": len(payload["cases"]),
        })
    data["fixture_bindings"] = bindings
    _write(path, data)


if __name__ == "__main__":
    build_inventory()
    update_compatibility()
    update_oracle_manifest()
