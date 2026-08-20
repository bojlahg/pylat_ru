"""Deterministic upstream-test inventory generator for Task 0013.

Reads the pinned, vendored LanguageTool 6.8 JUnit sources under
``third_party/languagetool`` with :mod:`tools.java_test_parser`, derives the
executable method and scenario inventory mechanically, joins it with the
explicit Python/oracle mapping recorded below, and writes
``compat/upstream_test_inventory_0013.json``.

The generator is fail-closed: any executable method or delegated contract that
carries at least one assertion/scenario unit and has no mapping entry aborts the
run, and any mapping entry that no longer resolves to a pinned method aborts the
run as well.  Development-only; never imported by production code.

Usage::

    python -m tools.inventory_upstream_tests_0013
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tools.java_test_parser import (
    JavaMethod,
    JavaTestFile,
    MethodResolver,
    analyze_method,
    parse_java_file,
)

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "third_party" / "languagetool"
OUTPUT = ROOT / "compat" / "upstream_test_inventory_0013.json"

PINNED_COMMIT = "e807fcde6a6506191e1470744d2345da28c26be6"
PINNED_TAG = "v6.8"
RU_MODULE = "languagetool-language-modules/ru"

STATUS_ENUM = (
    "DIRECT_PYTHON_PARITY",
    "ORACLE_PARITY",
    "ALREADY_COVERED_EQUIVALENTLY",
    "NOT_EXECUTABLE_HELPER",
    "LANGUAGE_MODEL_DEFERRED",
    "NOT_APPLICABLE_WITH_PROOF",
    "BLOCKED",
)

COUNTING_RULE = {
    "unit_of_account": "parenthesis-depth-0 invocation inside an executable method body",
    "assertion_call": "one JUnit/Hamcrest assertion call = one assertion unit",
    "throw_guard": "one `throw new X(...)` fail-closed guard = one assertion unit",
    "delegation": (
        "one call to a method declared by the same class or a vendored superclass "
        "(including `new Helper(...).method(...)`) = one scenario unit, and the "
        "target is itself inventoried"
    ),
    "vector_loop": (
        "a for-each over a field initialised from a literal collection contributes "
        "len(unique elements) * (units inside the loop body); the invocations inside "
        "the loop body are not counted again"
    ),
    "nested_calls": "invocations nested inside another invocation's argument list are arguments, not scenarios",
    "comments": "commented-out code is never counted",
    "setup": "allow-listed construction/accessor/plumbing calls contribute zero units",
    "fail_closed": (
        "an unclassified depth-0 invocation aborts the extraction rather than being "
        "silently skipped"
    ),
}

TAGGER_DICTIONARY_AUDIT = {
    "tool": "tools/audit_tagger_dictionary_0013.py",
    "dictionary_path": "src/pylat_ru/resources/ru/russian.dict",
    "dictionary_sha256": "387f9fcf652a574c9d361397c30aa87ef6f7397a76d3d51cd04c94e8dcbc4015",
    "dictionary_size_bytes": 2322253,
    "entries_total": 7176385,
    "entries_without_pos_tag": 0,
    "upstream_contract": (
        "TestTools.testDictionary reads the tagger dictionary, iterates every "
        "WordData entry and warns (never fails) about entries lacking a POS tag"
    ),
}

RU013 = "tests/upstream/test_upstream_russian_rule_tests_0013.py"
PAT013 = "tests/upstream/test_upstream_pattern_rule_contract_0013.py"
LANG013 = "tests/upstream/test_upstream_language_contract_0013.py"
ORACLE013 = "tests/upstream/test_upstream_tests_0013_oracle_parity.py"
JR0012 = "tests/upstream/test_java_rules_0012_upstream_tests.py"


def _m(status: str, semantics: str, python_tests: List[str] | None = None, **extra: Any) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "status": status,
        "semantics": semantics,
        "python_tests": python_tests or [],
        "oracle_cases": extra.pop("oracle_cases", []),
    }
    record.update(extra)
    return record


# --- explicit mapping ------------------------------------------------------
# Keyed by "<fully qualified class>#<method>/<declared parameter count>".

MAPPING: Dict[str, Dict[str, Any]] = {
    # ---- RussianConcurrencyTest ------------------------------------------
    "org.languagetool.language.AbstractLanguageConcurrencyTest#testSpellCheckerFailure/0": _m(
        "DIRECT_PYTHON_PARITY",
        "concurrent checks of the pinned sample text must not raise and must stay deterministic",
        [f"{RU013}::test_concurrency_fresh_instance_per_run",
         f"{RU013}::test_concurrency_shared_instance_and_state_isolation"],
        upstream_ignored=True,
        upstream_ignore_reason="too slow to run every time",
        notes=(
            "The pinned method carries @Ignore and therefore never executes at the pin. "
            "The Python port executes on every run, adds a shared-instance sharing model "
            "that upstream does not test, and asserts singleton identity plus result "
            "determinism; the per-thread stress level is reduced to 12 threads x 3 runs "
            "because a Python pipeline construction costs ~0.3s."
        ),
    ),
    # ---- DateCheckFilterTest ---------------------------------------------
    "org.languagetool.rules.ru.DateCheckFilterTest#testGetDayOfWeek/0": _m(
        "DIRECT_PYTHON_PARITY",
        "DateCheckFilter.getDayOfWeek for the four uncommented pinned inputs",
        [f"{RU013}::test_date_check_filter_get_day_of_week"],
    ),
    "org.languagetool.rules.ru.DateCheckFilterTest#testMonth/0": _m(
        "DIRECT_PYTHON_PARITY",
        "DateCheckFilter.getMonth for roman numerals and cased month names",
        [f"{RU013}::test_date_check_filter_get_month"],
    ),
    # ---- LanguageSpecificSpellcheckerTest ---------------------------------
    "org.languagetool.rules.ru.LanguageSpecificSpellcheckerTest#testRules/0": _m(
        "DIRECT_PYTHON_PARITY",
        "delegates to SpellcheckerTest#runLanguageSpecificTest",
        [f"{RU013}::test_language_specific_spellchecker_word_lists"],
    ),
    "org.languagetool.rules.spelling.SpellcheckerTest#runLanguageSpecificTest/0": _m(
        "DIRECT_PYTHON_PARITY",
        "prohibit.txt and spelling.txt must not share a word; the language set must not be empty",
        [f"{RU013}::test_language_specific_spellchecker_word_lists"],
        notes=(
            "The third guard (totalProhibited == 0) only fires for more than five "
            "languages and is unreachable for the single-language Russian module; the "
            "Python port asserts a non-empty prohibited list instead, which is stronger."
        ),
    ),
    # ---- Morfologik spelling ---------------------------------------------
    "org.languagetool.rules.ru.MorfologikRussianSpellerRuleTest#testMorfologikSpeller/0": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "seven MORFOLOGIK_RULE_RU_RU match-count assertions",
        [f"{JR0012}::test_morfologik_russian_speller_rule"],
        oracle_cases=["spell_correct_cyrillic", "spell_correct_yo", "spell_correct_ye",
                      "spell_hyphen_wrong", "spell_hyphen_correct",
                      "spell_proper_hyphen_correct", "spell_proper_hyphen_wrong"],
    ),
    "org.languagetool.rules.ru.MorfologikRussianYOSpellerRuleTest#testMorfologikSpeller/0": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "six MORFOLOGIK_RULE_RU_RU_YO match-count assertions",
        [f"{JR0012}::test_morfologik_russian_yo_speller_rule"],
        oracle_cases=["spell_yo_correct_yo", "spell_yo_incorrect_ye"],
    ),
    # ---- RussianCompoundRuleTest -----------------------------------------
    "org.languagetool.rules.ru.RussianCompoundRuleTest#testRule/0": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "nineteen AbstractCompoundRuleTest#check scenarios",
        [f"{JR0012}::test_russian_compound_rule"],
    ),
    "org.languagetool.rules.AbstractCompoundRuleTest#check/2": _m(
        "DIRECT_PYTHON_PARITY",
        "two-argument overload widening to check(expected, text, null)",
        [f"{JR0012}::test_russian_compound_rule"],
    ),
    "org.languagetool.rules.AbstractCompoundRuleTest#check/3": _m(
        "DIRECT_PYTHON_PARITY",
        "exact match count plus exact suggestion list and order when suggestions are given",
        [f"{JR0012}::test_russian_compound_rule"],
    ),
    # ---- RussianDashRuleTest ---------------------------------------------
    "org.languagetool.rules.ru.RussianDashRuleTest#testRule/0": _m(
        "DIRECT_PYTHON_PARITY",
        "five RU_DASH_RULE scenarios with exact suggestion lists",
        [f"{RU013}::test_russian_dash_rule"],
    ),
    "org.languagetool.rules.ru.RussianDashRuleTest#check/2": _m(
        "DIRECT_PYTHON_PARITY",
        "two-argument overload widening to check(expected, text, null)",
        [f"{RU013}::test_russian_dash_rule"],
    ),
    "org.languagetool.rules.ru.RussianDashRuleTest#check/3": _m(
        "DIRECT_PYTHON_PARITY",
        "exact match count plus exact suggestion list and order",
        [f"{RU013}::test_russian_dash_rule"],
    ),
    # ---- RussianPatternRuleTest ------------------------------------------
    "org.languagetool.rules.ru.RussianPatternRuleTest#testRules/0": _m(
        "DIRECT_PYTHON_PARITY",
        "delegates to PatternRuleTest#runGrammarRulesFromXmlTest",
        [f"{PAT013}::test_run_grammar_rules_from_xml_aggregate"],
    ),
    "org.languagetool.rules.patterns.PatternRuleTest#runGrammarRulesFromXmlTest/0": _m(
        "DIRECT_PYTHON_PARITY",
        "runs runGrammarRuleForLanguage once for every language on the classpath",
        [f"{PAT013}::test_run_grammar_rules_from_xml_aggregate"],
    ),
    "org.languagetool.rules.patterns.PatternRuleTest#runGrammarRuleForLanguage/1": _m(
        "DIRECT_PYTHON_PARITY",
        "German-only branching, country-variant skipping, then runTestForLanguage",
        [f"{PAT013}::test_run_grammar_rules_from_xml_aggregate"],
    ),
    "org.languagetool.rules.patterns.PatternRuleTest#runTestForLanguage/1": _m(
        "DIRECT_PYTHON_PARITY",
        "the eleven grammar validation sub-contracts for one language",
        [f"{PAT013}::test_run_grammar_rules_from_xml_aggregate"],
    ),
    "org.languagetool.rules.patterns.PatternRuleTest#validatePatternFile/1": _m(
        "DIRECT_PYTHON_PARITY",
        "ru/grammar.xml validates and loads completely",
        [f"{PAT013}::test_validate_pattern_file"],
    ),
    "org.languagetool.rules.patterns.PatternRuleTest#createToolForTesting/1": _m(
        "NOT_APPLICABLE_WITH_PROOF",
        "optionally disables spelling rules before the example run",
        [],
        reason=(
            "Guarded by `private static final boolean CHECK_WITH_SENTENCE_SPLITTING = false;` "
            "in PatternRuleTest, so disableSpellingRules() never executes at the pin."
        ),
    ),
    "org.languagetool.rules.patterns.PatternRuleTest#validateRuleIds/2": _m(
        "DIRECT_PYTHON_PARITY",
        "rule id shape (no DB_ prefix, no brackets, no space, <= 79 chars) and id uniqueness",
        [f"{PAT013}::test_validate_rule_ids", f"{PAT013}::test_rule_id_uniqueness",
         f"{PAT013}::test_validate_category_ids"],
    ),
    "org.languagetool.rules.patterns.RuleIdValidator#validateUniqueness/0": _m(
        "DIRECT_PYTHON_PARITY",
        "no XML rule/rulegroup id may collide with a Java rule id or another file's id",
        [f"{PAT013}::test_rule_id_uniqueness"],
    ),
    "org.languagetool.rules.patterns.PatternRuleTest#validateUnifyIgnoreAtTheStartOfUnify/1": _m(
        "DIRECT_PYTHON_PARITY",
        "the first unified pattern token of a rule may not be unification neutral",
        [f"{PAT013}::test_validate_unify_ignore_not_at_start_of_unify"],
    ),
    "org.languagetool.rules.patterns.PatternRuleTest#validateParenthesisInSynthesisMatches/1": _m(
        "DIRECT_PYTHON_PARITY",
        "a synthesis match may not use a back reference above its parenthesis count",
        [f"{PAT013}::test_validate_parenthesis_in_synthesis_matches"],
    ),
    "org.languagetool.rules.patterns.PatternRuleTest#testMessages/2": _m(
        "DIRECT_PYTHON_PARITY",
        "no empty message, no 'todo'/'lorem ipsum'/'tbd' message",
        [f"{PAT013}::test_messages"],
        notes=(
            "The 'did you mean' warning and the trailing punctuation checks are guarded "
            "by language-code tests that exclude ru."
        ),
    ),
    "org.languagetool.rules.patterns.PatternRuleTest#testGrammarRulesFromXML/3": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "every rule's correct and incorrect example sentences",
        ["tests/upstream/test_russian_grammar_examples.py::test_grammar_core_trigger_parity",
         "tests/upstream/test_russian_grammar_examples.py::test_grammar_core_full_example_parity",
         "tests/upstream/test_russian_grammar_examples.py::test_grammar_all_runnable_0010_trigger_parity",
         f"{PAT013}::test_every_rule_has_incorrect_examples",
         f"{PAT013}::test_incorrect_examples_have_marker_and_non_empty_text",
         f"{PAT013}::test_suggestions_do_not_create_errors",
         f"{PAT013}::test_no_error_triggering_examples_at_the_pin"],
    ),
    "org.languagetool.rules.patterns.PatternRuleTest#testSupportsLanguage/0": _m(
        "NOT_APPLICABLE_WITH_PROOF",
        "PatternRule.supportsLanguage for language variants",
        [],
        reason=(
            "The method builds `new FakeLanguage(\"yy\")`, `new FakeLanguage(\"zz\")` and "
            "`new FakeLanguage(\"zz\", \"VAR1\"/\"VAR2\")` only; Russian is never involved, "
            "and pylat_ru is a single-language library with no Language abstraction."
        ),
    ),
    "org.languagetool.rules.patterns.AbstractPatternRuleTest#shortMessageIsLongerThanErrorMessage/0": _m(
        "DIRECT_PYTHON_PARITY",
        "warning-only sweep over every pattern rule's <short>/<message> pair",
        [f"{PAT013}::test_short_message_sweep"],
    ),
    # ---- RussianSimpleReplaceRuleTest ------------------------------------
    "org.languagetool.rules.ru.RussianSimpleReplaceRuleTest#testRule/0": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "five RU_SIMPLE_REPLACE assertions including the exact single suggestion",
        [f"{JR0012}::test_russian_simple_replace_rule"],
    ),
    # ---- RussianSpecificCaseRuleTest -------------------------------------
    "org.languagetool.rules.ru.RussianSpecificCaseRuleTest#testRule/0": _m(
        "DIRECT_PYTHON_PARITY",
        "five RU_SPECIFIC_CASE verdicts plus exact offsets, suggestions and message",
        [f"{RU013}::test_russian_specific_case_rule"],
    ),
    "org.languagetool.rules.ru.RussianSpecificCaseRuleTest#assertGood/1": _m(
        "DIRECT_PYTHON_PARITY",
        "zero matches for the given input",
        [f"{RU013}::test_russian_specific_case_rule"],
    ),
    "org.languagetool.rules.ru.RussianSpecificCaseRuleTest#assertBad/1": _m(
        "DIRECT_PYTHON_PARITY",
        "exactly one match for the given input",
        [f"{RU013}::test_russian_specific_case_rule"],
    ),
    # ---- RussianTest ------------------------------------------------------
    "org.languagetool.rules.ru.RussianTest#testLanguage/0": _m(
        "DIRECT_PYTHON_PARITY",
        "demo text rule ids plus the whole LanguageSpecificTest#runTests suite",
        [f"{LANG013}::test_demo_text", f"{LANG013}::test_run_tests_aggregate"],
    ),
    "org.languagetool.LanguageSpecificTest#testDemoText/3": _m(
        "DIRECT_PYTHON_PARITY",
        "lt.check(demo text) must yield exactly the expected specific rule ids in order",
        [f"{LANG013}::test_demo_text"],
    ),
    "org.languagetool.LanguageSpecificTest#failTest/4": _m(
        "NOT_APPLICABLE_WITH_PROOF",
        "failure message formatter for testDemoText",
        [],
        reason="Only reached when testDemoText already failed; it formats the failure text.",
    ),
    "org.languagetool.LanguageSpecificTest#runTests/1": _m(
        "DIRECT_PYTHON_PARITY",
        "widens to runTests(lang, null, \"\")",
        [f"{LANG013}::test_run_tests_aggregate"],
    ),
    "org.languagetool.LanguageSpecificTest#runTests/3": _m(
        "DIRECT_PYTHON_PARITY",
        "widens to runTests(lang, lang, onlyRunCode, additionalValidationChars)",
        [f"{LANG013}::test_run_tests_aggregate"],
    ),
    "org.languagetool.LanguageSpecificTest#runTests/4": _m(
        "DIRECT_PYTHON_PARITY",
        "the nine language-wide sub-contracts",
        [f"{LANG013}::test_run_tests_aggregate"],
    ),
    "org.languagetool.rules.WordListValidatorTest#testWordListValidity/1": _m(
        "NOT_APPLICABLE_WITH_PROOF",
        "spelling word list character validation",
        [f"{LANG013}::test_word_list_validator_skips_russian"],
        reason=(
            "The pinned method opens with `if (lang.getShortCode().equals(\"ru\")) { return; }"
            "   // skipping, Cyrillic chars not part of the validation yet`, so no Russian "
            "word list is ever validated."
        ),
    ),
    "org.languagetool.rules.WordListValidatorTest#validateWords/2": _m(
        "NOT_APPLICABLE_WITH_PROOF",
        "regex validation of a loaded spelling word list",
        [f"{LANG013}::test_word_list_validator_skips_russian"],
        reason="Unreachable for Russian because testWordListValidity returns before calling it.",
    ),
    "org.languagetool.LanguageSpecificTest#testNoQuotesAroundSuggestion/1": _m(
        "DIRECT_PYTHON_PARITY",
        "no rule message may wrap <suggestion>...</suggestion> in quotes",
        [f"{LANG013}::test_no_quotes_around_suggestion"],
    ),
    "org.languagetool.LanguageSpecificTest#testJavaRules/1": _m(
        "DIRECT_PYTHON_PARITY",
        "id/description validity, id uniqueness and example pairs of every non-pattern rule",
        [f"{LANG013}::test_java_rules_id_and_description_validity",
         f"{LANG013}::test_java_rules_id_uniqueness",
         f"{LANG013}::test_java_rules_examples"],
    ),
    "org.languagetool.LanguageSpecificTest#assertIdAndDescriptionValidity/2": _m(
        "DIRECT_PYTHON_PARITY",
        "rule id and description must not be empty",
        [f"{LANG013}::test_java_rules_id_and_description_validity"],
    ),
    "org.languagetool.LanguageSpecificTest#assertIdValidity/2": _m(
        "DIRECT_PYTHON_PARITY",
        "rule id must match ^[A-Z_][A-Z0-9_]+$",
        [f"{LANG013}::test_java_rules_id_and_description_validity"],
    ),
    "org.languagetool.LanguageSpecificTest#assertIdUniqueness/4": _m(
        "DIRECT_PYTHON_PARITY",
        "a rule id may not occur twice across rule classes",
        [f"{LANG013}::test_java_rules_id_uniqueness"],
    ),
    "org.languagetool.LanguageSpecificTest#testExamples/2": _m(
        "DIRECT_PYTHON_PARITY",
        "runs the correct and incorrect example checks for one rule",
        [f"{LANG013}::test_java_rules_examples"],
    ),
    "org.languagetool.LanguageSpecificTest#testCorrectExamples/2": _m(
        "DIRECT_PYTHON_PARITY",
        "a correct example must produce zero matches with only that rule enabled",
        [f"{LANG013}::test_java_rules_examples"],
    ),
    "org.languagetool.LanguageSpecificTest#testIncorrectExamples/2": _m(
        "DIRECT_PYTHON_PARITY",
        "an incorrect example must produce exactly one match with only that rule enabled",
        [f"{LANG013}::test_java_rules_examples"],
    ),
    "org.languagetool.LanguageSpecificTest#testConfusionSetLoading/0": _m(
        "LANGUAGE_MODEL_DEFERRED",
        "ru/confusion_sets.txt must load when the language exposes language-model rules",
        [f"{LANG013}::test_confusion_set_loading_is_language_model_deferred"],
        reason=(
            "The loader only runs when getRelevantLanguageModelRules() is non-empty; for "
            "Russian that list is exactly RussianConfusionProbabilityRule, which Task 0013 "
            "keeps deferred."
        ),
    ),
    "org.languagetool.LanguageSpecificTest#testCoherencyBaseformIsOtherForm/1": _m(
        "DIRECT_PYTHON_PARITY",
        "no synthesised form of a coherency.txt key may trigger the coherency rule",
        [f"{LANG013}::test_coherency_baseform_is_other_form"],
        notes=(
            "Upstream enables only EN_WORD_COHERENCY, an id Russian does not have, so the "
            "pinned check is vacuous for ru; the Python port asserts both the vacuity "
            "condition and the strengthened RU_WORD_COHERENCY reading."
        ),
    ),
    "org.languagetool.tagging.disambiguation.rules.DisambiguationRuleTest#testDisambiguationRulesFromXML/0": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "disambiguation.xml loads, validates and reproduces all its examples",
        ["tests/upstream/test_russian_disambiguation_parity.py::test_upstream_disambiguation_xml_all_examples_parity",
         "tests/upstream/test_russian_disambiguation_parity.py::test_upstream_disambiguation_end_to_end_examples"],
    ),
    "org.languagetool.tagging.disambiguation.rules.DisambiguationRuleTest#testDisambiguationRulesFromXML/1": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "per-language loop over the disambiguation rule files",
        ["tests/upstream/test_russian_disambiguation_parity.py::test_upstream_disambiguation_xml_all_examples_parity"],
    ),
    "org.languagetool.tagging.disambiguation.rules.DisambiguationRuleTest#testDisambiguationRulesFromXML/3": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "untouched examples stay untouched and disambiguated examples reach the expected readings",
        ["tests/upstream/test_russian_disambiguation_parity.py::test_upstream_disambiguation_xml_all_examples_parity",
         "tests/upstream/test_russian_disambiguation_parity.py::test_upstream_disambiguation_end_to_end_examples",
         "tests/upstream/test_russian_disambiguation_oracle_parity.py"],
    ),
    # ---- RussianUnpairedBracketsRuleTest ---------------------------------
    "org.languagetool.rules.ru.RussianUnpairedBracketsRuleTest#testRuleRussian/0": _m(
        "DIRECT_PYTHON_PARITY",
        "five RU_UNPAIRED_BRACKETS match-count assertions",
        [f"{RU013}::test_russian_unpaired_brackets_rule"],
    ),
    # ---- RussianVerbConjugationRuleTest ----------------------------------
    "org.languagetool.rules.ru.RussianVerbConjugationRuleTest#testRussianVerbConjugationRule/0": _m(
        "DIRECT_PYTHON_PARITY",
        "19 wrong-sentence and 22 right-sentence RU_VERB_CONJUGATION vectors",
        [f"{RU013}::test_russian_verb_conjugation_rule_wrong",
         f"{RU013}::test_russian_verb_conjugation_rule_right",
         f"{RU013}::test_russian_verb_conjugation_vectors_match_pinned_source"],
    ),
    # ---- RussianWordCoherencyRuleTest ------------------------------------
    "org.languagetool.rules.ru.RussianWordCoherencyRuleTest#testRule/0": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "two good and one bad RU_WORD_COHERENCY sentence",
        [f"{JR0012}::test_russian_word_coherency_rule"],
    ),
    "org.languagetool.rules.ru.RussianWordCoherencyRuleTest#testCallIndependence/0": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "separate calls must not share the 'should not appear' map",
        [f"{JR0012}::test_russian_word_coherency_call_independence"],
    ),
    "org.languagetool.rules.ru.RussianWordCoherencyRuleTest#assertGood/1": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "zero matches for the given text",
        [f"{JR0012}::test_russian_word_coherency_rule",
         f"{JR0012}::test_russian_word_coherency_call_independence"],
    ),
    "org.languagetool.rules.ru.RussianWordCoherencyRuleTest#assertError/1": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "exactly one match for the given text",
        [f"{JR0012}::test_russian_word_coherency_rule"],
    ),
    "org.languagetool.rules.ru.RussianWordCoherencyRuleTest#testRuleCompleteTexts/0": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "whole-pipeline checks including a cross-paragraph text",
        [f"{JR0012}::test_russian_word_coherency_complete_texts"],
    ),
    # ---- RussianWordRepeatRuleTest ---------------------------------------
    "org.languagetool.rules.ru.RussianWordRepeatRuleTest#testRule/0": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "one correct and one incorrect RU_WORD_REPEAT sentence",
        [f"{JR0012}::test_russian_word_repeat_rule"],
    ),
    # ---- RussianSynthesizerTest ------------------------------------------
    "org.languagetool.synthesis.ru.RussianSynthesizerTest#testSynthesizeString/0": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "unknown lemma yields no form; two exact single-form synthesis results",
        ["tests/upstream/test_russian_synthesizer.py::test_synthesize_string"],
        oracle_cases=["tests/fixtures/oracle_russian_synthesizer_sample.json"],
    ),
    # ---- RussianTaggerTest -----------------------------------------------
    "org.languagetool.tagging.ru.RussianTaggerTest#testDictionary/0": _m(
        "DIRECT_PYTHON_PARITY",
        "the packaged tagger dictionary loads and every entry carries a POS tag",
        [f"{RU013}::test_russian_tagger_dictionary"],
        notes=(
            "Upstream only warns; the exhaustive 7,176,385-entry sweep is recorded under "
            "tagger_dictionary_audit and asserted by the inventory test, while the pytest "
            "port performs the load and a bounded deterministic prefix sweep."
        ),
    ),
    "org.languagetool.TestTools#testDictionary/2": _m(
        "DIRECT_PYTHON_PARITY",
        "iterate every WordData entry of the tagger dictionary, warning about missing tags",
        [f"{RU013}::test_russian_tagger_dictionary"],
    ),
    "org.languagetool.tagging.ru.RussianTaggerTest#testTagger/0": _m(
        "DIRECT_PYTHON_PARITY",
        "four exact TestTools.myAssert reading strings",
        [f"{RU013}::test_russian_tagger_exact_readings"],
    ),
    "org.languagetool.TestTools#myAssert/4": _m(
        "DIRECT_PYTHON_PARITY",
        "tokenize, drop non-word tokens, tag, render sorted token/[lemma]POS readings",
        [f"{RU013}::test_russian_tagger_exact_readings"],
    ),
    # ---- RussianSRXSentenceTokenizerTest ---------------------------------
    "org.languagetool.tokenizers.ru.RussianSRXSentenceTokenizerTest#testTokenize/0": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "nine Russian abbreviation segmentation scenarios",
        ["tests/upstream/test_russian_sentence_tokenizer_parity.py::test_upstream_russian_srx_sentence_tokenizer_test_suite"],
    ),
    "org.languagetool.tokenizers.ru.RussianSRXSentenceTokenizerTest#testSplit/1": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "delegates to TestTools.testSplit",
        ["tests/upstream/test_russian_sentence_tokenizer_parity.py::test_upstream_russian_srx_sentence_tokenizer_test_suite"],
    ),
    "org.languagetool.TestTools#testSplit/2": _m(
        "ALREADY_COVERED_EQUIVALENTLY",
        "concatenating the expected sentences and re-splitting must return them unchanged",
        ["tests/upstream/test_russian_sentence_tokenizer_parity.py::test_upstream_russian_srx_sentence_tokenizer_test_suite"],
    ),
}

# --- generic/core evidence sources ----------------------------------------
# Core test files that Tasks 0007-0012 claimed as Russian compatibility
# evidence, with the reconciliation required by Task 0013 section 25.

GENERIC_CORE_EVIDENCE: Dict[str, Dict[str, Any]] = {
    "languagetool-core/src/test/java/org/languagetool/rules/CommaWhitespaceRuleTest.java": {
        "russian_dependency": "COMMA_PARENTHESIS_WHITESPACE (CommaWhitespaceRule)",
        "claimed_by": ["compat/russian_java_rules_inventory.json"],
        "status": "ORACLE_PARITY",
        "python_tests": [f"{ORACLE013}::test_upstream_test_oracle_parity"],
        "oracle_case_prefix": "comma_ws_",
        "reason": (
            "The pinned method runs against TestTools.getDemoLanguage(), so its literal "
            "expectations are Demo-language outcomes.  All 45 pinned scenario inputs were "
            "replayed through the trusted Java oracle with the Russian language and are "
            "asserted field for field."
        ),
    },
    "languagetool-core/src/test/java/org/languagetool/rules/MultipleWhitespaceRuleTest.java": {
        "russian_dependency": "WHITESPACE_RULE (MultipleWhitespaceRule)",
        "claimed_by": ["compat/russian_java_rules_inventory.json"],
        "status": "ORACLE_PARITY",
        "python_tests": [f"{ORACLE013}::test_upstream_test_oracle_parity"],
        "oracle_case_prefix": "multi_ws_",
        "reason": "Demo-language test; all 17 pinned scenario inputs replayed under Russian.",
    },
    "languagetool-core/src/test/java/org/languagetool/rules/SentenceWhitespaceRuleTest.java": {
        "russian_dependency": "SENTENCE_WHITESPACE (SentenceWhitespaceRule)",
        "claimed_by": ["compat/russian_java_rules_inventory.json"],
        "status": "ORACLE_PARITY",
        "python_tests": [f"{ORACLE013}::test_upstream_test_oracle_parity"],
        "oracle_case_prefix": "sentence_ws_",
        "reason": "FakeLanguage test; all 7 pinned scenario inputs replayed under Russian.",
    },
    "languagetool-core/src/test/java/org/languagetool/rules/UppercaseSentenceStartRuleTest.java": {
        "russian_dependency": "UPPERCASE_SENTENCE_START (UppercaseSentenceStartRule)",
        "claimed_by": ["compat/russian_java_rules_inventory.json"],
        "status": "ORACLE_PARITY",
        "python_tests": [f"{ORACLE013}::test_upstream_test_oracle_parity"],
        "oracle_case_prefix": "uppercase_start_",
        "reason": "Demo-language test; all 23 pinned scenario inputs replayed under Russian.",
    },
    "languagetool-core/src/test/java/org/languagetool/rules/LongSentenceRuleTest.java": {
        "russian_dependency": "TOO_LONG_SENTENCE (LongSentenceRule)",
        "claimed_by": ["compat/russian_java_rules_inventory.json"],
        "status": "ORACLE_PARITY",
        "python_tests": [f"{ORACLE013}::test_upstream_test_oracle_parity"],
        "oracle_case_prefix": "long_sentence",
        "reason": (
            "Demo-language test; all 24 pinned scenario inputs replayed under Russian with "
            "the pinned maxWords values 40 and 6."
        ),
    },
    "languagetool-core/src/test/java/org/languagetool/rules/LongParagraphRuleTest.java": {
        "russian_dependency": "TOO_LONG_PARAGRAPH (LongParagraphRule)",
        "claimed_by": ["compat/russian_java_rules_inventory.json"],
        "status": "ORACLE_PARITY",
        "python_tests": [f"{ORACLE013}::test_upstream_test_oracle_parity"],
        "oracle_case_prefix": "long_paragraph_",
        "reason": "Demo-language test; all 8 pinned scenario inputs replayed under Russian with maxWords=6.",
    },
    "languagetool-core/src/test/java/org/languagetool/rules/PunctuationMarkAtParagraphEnd2Test.java": {
        "russian_dependency": "PUNCTUATION_PARAGRAPH_END2 (PunctuationMarkAtParagraphEnd2)",
        "claimed_by": ["compat/russian_java_rules_inventory.json"],
        "status": "ORACLE_PARITY",
        "python_tests": [f"{ORACLE013}::test_upstream_test_oracle_parity"],
        "oracle_case_prefix": "punct_par_end2_",
        "reason": "Demo-language test; all 22 pinned scenario inputs replayed under Russian.",
    },
    "languagetool-core/src/test/java/org/languagetool/rules/patterns/PatternRuleLoaderTest.java": {
        "russian_dependency": "XML grammar loading (Task 0007)",
        "claimed_by": ["compat/russian_grammar_core_inventory.json", "reports/0007_xml_grammar_engine_core.md"],
        "status": "ALREADY_COVERED_EQUIVALENTLY",
        "python_tests": ["tests/upstream/test_upstream_pattern_rules.py::test_pattern_rule_loader_structure",
                          "tests/upstream/test_upstream_pattern_rules.py::test_pattern_rule_loader_fail_closed_validation"],
        "reason": "Translated by Task 0007; the loader contract is reproduced directly.",
    },
    "languagetool-core/src/test/java/org/languagetool/rules/patterns/PatternRuleMatcherTest.java": {
        "russian_dependency": "pattern matcher min/max/skip semantics (Tasks 0007-0008)",
        "claimed_by": ["compat/russian_grammar_core_inventory.json", "reports/0008_advanced_xml_matching.md"],
        "status": "ALREADY_COVERED_EQUIVALENTLY",
        "python_tests": ["tests/unit/test_advanced_grammar_matcher.py",
                          "tests/upstream/test_upstream_pattern_rules.py::test_pattern_rule_matcher_simple_match",
                          "tests/upstream/test_upstream_pattern_rules.py::test_pattern_rule_matcher_case_sensitivity",
                          "tests/upstream/test_upstream_pattern_rules.py::test_pattern_rule_matcher_regex_and_negation",
                          "tests/upstream/test_upstream_pattern_rules.py::test_pattern_rule_matcher_inflected_exact_semantics"],
        "reason": "Translated by Tasks 0007-0008.",
    },
    "languagetool-core/src/test/java/org/languagetool/rules/patterns/PatternRuleTest.java": {
        "russian_dependency": "RussianPatternRuleTest base class",
        "claimed_by": ["compat/upstream_test_inventory.json", "reports/0007_xml_grammar_engine_core.md"],
        "status": "DIRECT_PYTHON_PARITY",
        "python_tests": [PAT013],
        "reason": "Decomposed into its eleven Russian sub-contracts by Task 0013.",
    },
    "languagetool-core/src/test/java/org/languagetool/rules/patterns/RuleFilterEvaluatorTest.java": {
        "russian_dependency": "XML filter argument resolution (Task 0010)",
        "claimed_by": ["reports/0010_xml_filters.md"],
        "status": "ALREADY_COVERED_EQUIVALENTLY",
        "python_tests": ["tests/unit/test_filters.py"],
        "reason": "All five methods translated by Task 0010.",
    },
    "languagetool-core/src/test/java/org/languagetool/rules/patterns/UnifierTest.java": {
        "russian_dependency": "feature unification (Task 0009)",
        "claimed_by": ["reports/0009_unification.md"],
        "status": "ALREADY_COVERED_EQUIVALENTLY",
        "python_tests": ["tests/upstream/test_unifier_oracle_parity.py"],
        "reason": "All seven methods translated by Task 0009.",
    },
    "languagetool-core/src/test/java/org/languagetool/rules/GenericUnpairedBracketsRuleTest.java": {
        "russian_dependency": "RU_UNPAIRED_BRACKETS base class (GenericUnpairedBracketsRule)",
        "claimed_by": [],
        "status": "NOT_APPLICABLE_WITH_PROOF",
        "python_tests": [],
        "reason": (
            "Vendored but never claimed as Russian evidence.  Its setUpRule builds "
            "`new GenericUnpairedBracketsRule(messages, Arrays.asList(\"\\u00bb\"), "
            "Arrays.asList(\"\\u00ab\"))` on `new FakeLanguage()`; RussianUnpairedBracketsRule "
            "uses a different symbol set, so none of its scenarios is a Russian contract.  "
            "The Russian contract is RussianUnpairedBracketsRuleTest."
        ),
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_sources() -> Dict[str, JavaTestFile]:
    files: Dict[str, JavaTestFile] = {}
    for path in sorted(VENDOR.rglob("*.java")):
        rel = path.relative_to(VENDOR).as_posix()
        if "/src/test/" not in rel:
            continue
        files[rel] = parse_java_file(path, rel, _sha256(path))
    return files


def _method_record(owner: JavaTestFile, method: JavaMethod, inherited_from: str | None) -> Dict[str, Any]:
    return {
        "java_class": owner.fq_class,
        "method": method.name,
        "declared_parameters": method.param_count,
        "key": f"{owner.fq_class}#{method.key}",
        "signature": method.signature,
        "source_line": method.line,
        "annotations": list(method.annotations),
        "is_test": method.is_test,
        "upstream_ignored": method.is_ignored,
        "upstream_ignore_reason": method.ignore_reason,
        "inherited_from": inherited_from,
        "assertion_units": method.assertion_units,
        "scenario_units": method.scenario_units,
        "throw_guards": method.throw_guards,
        "vector_loops": [
            {"field": name, "elements": elements, "units_per_element": units}
            for name, elements, units in method.vector_loops
        ],
        "delegates_to": list(method.delegates_to),
    }


def build() -> Dict[str, Any]:
    files = _load_sources()
    resolver = MethodResolver(files)
    by_fq = {f.fq_class: f for f in files.values()}
    russian_paths = sorted(rel for rel in files if rel.startswith(RU_MODULE))

    # --- analyse every Russian-module method and the delegation closure ----
    analysed: Dict[str, Tuple[JavaTestFile, JavaMethod, str | None]] = {}
    queue: List[Tuple[JavaTestFile, JavaMethod, str | None]] = []
    for rel in russian_paths:
        parsed = files[rel]
        for method in parsed.methods:
            queue.append((parsed, method, None))
        for cls, method in resolver.inherited_test_methods(parsed):
            queue.append((by_fq[cls], method, parsed.fq_class))

    order: List[str] = []
    while queue:
        owner, method, inherited_from = queue.pop(0)
        key = f"{owner.fq_class}#{method.key}"
        if key in analysed:
            continue
        analyze_method(owner, method, resolver)
        analysed[key] = (owner, method, inherited_from)
        order.append(key)
        for target in method.delegates_to:
            cls_name, member = target.split("#")
            name, arity = member.rsplit("/", 1)
            target_file = by_fq.get(cls_name)
            if target_file is None:
                continue
            target_method = target_file.method(name, int(arity))
            if target_method is not None:
                queue.append((target_file, target_method, None))

    # --- assemble per-file records ----------------------------------------
    russian_files: List[Dict[str, Any]] = []
    for rel in russian_paths:
        parsed = files[rel]
        executable: List[Dict[str, Any]] = []
        helpers: List[Dict[str, Any]] = []
        for method in parsed.methods:
            record = _method_record(parsed, method, None)
            (executable if method.is_test else helpers).append(record)
        inherited: List[Dict[str, Any]] = []
        for cls, method in resolver.inherited_test_methods(parsed):
            inherited.append(_method_record(by_fq[cls], method, parsed.fq_class))
        classification = (
            "EXECUTABLE_TEST_CLASS" if executable or inherited else "FIXTURE_ONLY_SUBCLASS"
        )
        russian_files.append({
            "source_path": rel,
            "source_sha256": parsed.sha256,
            "source_size_bytes": parsed.size_bytes,
            "module": RU_MODULE,
            "java_class": parsed.fq_class,
            "extends": parsed.extends,
            "file_classification": classification,
            "declared_test_methods": executable,
            "inherited_test_methods": inherited,
            "declared_helper_methods": helpers,
            "executable_method_count": len(executable) + len(inherited),
            "scenario_unit_count": sum(
                r["scenario_units"] for r in executable + inherited
            ),
            "literal_vectors": {name: len(values) for name, values in sorted(parsed.vectors.items())},
        })

    # --- contract closure --------------------------------------------------
    contracts: List[Dict[str, Any]] = []
    missing: List[str] = []
    for key in order:
        owner, method, inherited_from = analysed[key]
        record = _method_record(owner, method, inherited_from)
        mapping = MAPPING.get(key)
        if mapping is None:
            if method.scenario_units == 0 and not method.is_test:
                mapping = {
                    "status": "NOT_EXECUTABLE_HELPER",
                    "semantics": "plumbing or warning-only helper with no assertion or scenario unit",
                    "python_tests": [],
                    "oracle_cases": [],
                    "derived": True,
                }
            else:
                missing.append(key)
                continue
        if mapping["status"] not in STATUS_ENUM:
            raise ValueError(f"{key}: unknown status {mapping['status']!r}")
        record.update(mapping)
        record["declaring_source_path"] = owner.rel_path
        record["declaring_source_sha256"] = owner.sha256
        contracts.append(record)

    if missing:
        raise SystemExit(
            "unmapped executable contracts (add an entry to MAPPING):\n  "
            + "\n  ".join(missing)
        )
    stale = sorted(set(MAPPING) - set(order))
    if stale:
        raise SystemExit("stale MAPPING entries (no longer in the pinned closure):\n  " + "\n  ".join(stale))

    # --- generic/core evidence --------------------------------------------
    evidence: List[Dict[str, Any]] = []
    for rel, meta in sorted(GENERIC_CORE_EVIDENCE.items()):
        parsed = files.get(rel)
        if parsed is None:
            raise SystemExit(f"generic evidence source not vendored: {rel}")
        if meta["status"] not in STATUS_ENUM:
            raise ValueError(f"{rel}: unknown status {meta['status']!r}")
        evidence.append({
            "source_path": rel,
            "source_sha256": parsed.sha256,
            "source_size_bytes": parsed.size_bytes,
            "java_class": parsed.fq_class,
            "test_methods": [m.name for m in parsed.methods if m.is_test],
            "test_method_count": sum(1 for m in parsed.methods if m.is_test),
            **meta,
        })

    # --- totals -------------------------------------------------------------
    executable_methods = [
        record
        for entry in russian_files
        for record in entry["declared_test_methods"] + entry["inherited_test_methods"]
    ]
    executable_keys = {record["key"] for record in executable_methods}
    by_key = {record["key"]: record for record in contracts}
    status_counts: Dict[str, int] = {status: 0 for status in STATUS_ENUM}
    for record in contracts:
        status_counts[record["status"]] += 1

    lm_keys = {r["key"] for r in contracts if r["status"] == "LANGUAGE_MODEL_DEFERRED"}
    ordinary_contracts = [r for r in contracts if r["key"] not in lm_keys]

    totals = {
        "russian_module_test_files_total": len(russian_paths),
        "russian_module_test_files_accounted": len(russian_files),
        "executable_methods_total": len(executable_methods),
        "executable_methods_mapped": sum(1 for key in executable_keys if key in by_key),
        "contract_closure_total": len(contracts),
        "contract_scenario_units_total": sum(r["scenario_units"] for r in contracts),
        "contract_assertion_units_total": sum(r["assertion_units"] for r in contracts),
        "ordinary_non_lm_contracts_total": len(ordinary_contracts),
        "ordinary_non_lm_contracts_mapped": len(ordinary_contracts),
        "ordinary_non_lm_scenario_units_total": sum(r["scenario_units"] for r in ordinary_contracts),
        "ordinary_non_lm_scenario_units_mapped": sum(r["scenario_units"] for r in ordinary_contracts),
        "status_counts": status_counts,
        "blocked": status_counts["BLOCKED"],
        "unmapped": 0,
        "unknown": 0,
        "generic_core_evidence_sources_total": len(evidence),
        "generic_core_evidence_sources_reconciled": len(evidence),
    }

    return {
        "schema_version": "1.0.0",
        "task": "0013_complete_upstream_russian_test_parity",
        "generated_by": "tools/inventory_upstream_tests_0013.py",
        "pinned_upstream": {
            "repository": "https://github.com/languagetool-org/languagetool.git",
            "tag": PINNED_TAG,
            "commit": PINNED_COMMIT,
        },
        "status_enum": list(STATUS_ENUM),
        "counting_rule": COUNTING_RULE,
        "tagger_dictionary_audit": TAGGER_DICTIONARY_AUDIT,
        "russian_module_test_files": russian_files,
        "contract_closure": contracts,
        "generic_core_evidence_sources": evidence,
        "totals": totals,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    data = build()
    args.output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    totals = data["totals"]
    print(f"wrote {args.output}")
    print(f"  files: {totals['russian_module_test_files_accounted']}/"
          f"{totals['russian_module_test_files_total']}")
    print(f"  executable methods: {totals['executable_methods_mapped']}/"
          f"{totals['executable_methods_total']}")
    print(f"  contract closure: {totals['contract_closure_total']}")
    print(f"  scenario units: {totals['contract_scenario_units_total']}")


if __name__ == "__main__":
    main()
