"""Generate deterministic Task-0011 fixtures from the trusted Java LT oracle."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from pylat_ru.tokenization.offsets import Utf16CodePointMapper
from tools.differential_lt import JavaLanguageToolOracle


ROOT = Path(__file__).resolve().parents[1]
JAVA_SOURCE = ROOT / "tools" / "JavaRulesOracle0011.java"
RULES = {
    "CommaWhitespaceRule": "COMMA_PARENTHESIS_WHITESPACE",
    "UppercaseSentenceStartRule": "UPPERCASE_SENTENCE_START",
    "MultipleWhitespaceRule": "WHITESPACE_RULE",
    "SentenceWhitespaceRule": "SENTENCE_WHITESPACE",
    "WhiteSpaceBeforeParagraphEnd": "WHITESPACE_PARAGRAPH",
    "WhiteSpaceAtBeginOfParagraph": "WHITESPACE_PARAGRAPH_BEGIN",
    "LongSentenceRule": "TOO_LONG_SENTENCE",
    "LongParagraphRule": "TOO_LONG_PARAGRAPH",
    "ParagraphRepeatBeginningRule": "PARAGRAPH_REPEAT_BEGINNING_RULE",
    "RussianFillerWordsRule": "FILLER_WORDS_RU",
    "PunctuationMarkAtParagraphEnd2": "PUNCTUATION_PARAGRAPH_END2",
    "RussianUnpairedBracketsRule": "RU_UNPAIRED_BRACKETS",
    "RussianVerbConjugationRule": "RU_VERB_CONJUGATION",
    "RussianDashRule": "RU_DASH_RULE",
    "RussianSpecificCaseRule": "RU_SPECIFIC_CASE",
}
DEFERRED_RULE_IDS = [
    "MORFOLOGIK_RULE_RU_RU", "MORFOLOGIK_RULE_RU_RU_YO", "RU_COMPOUNDS",
    "RU_SIMPLE_REPLACE", "WORD_REPEAT_RULE", "RU_WORD_COHERENCY", "RU_WORD_REPEAT", "RU_WORD_ROOT_REPEAT",
]


def _words(n: int, ending: str = ".") -> str:
    return " ".join("слово" for _ in range(n)) + ending


def _case(case_id: str, rule_class: str, text: str, *coverage: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": case_id, "rule_class": rule_class, "text": text, "coverage": list(coverage), "config": config or {}}


SYNTHETIC_CASES = [
    _case("comma_normal", "CommaWhitespaceRule", "Это обычное, правильное предложение.", "negative", "normal_comma"),
    _case("comma_space_before", "CommaWhitespaceRule", "Это ошибка , в предложении.", "positive", "space_before"),
    _case("comma_missing_after", "CommaWhitespaceRule", "Это ошибка,в предложении.", "positive", "missing_space_after"),
    _case("comma_both_sides", "CommaWhitespaceRule", "Это ошибка ,в предложении.", "positive", "both_sides", "multi_finding"),
    _case("comma_text_start", "CommaWhitespaceRule", ",ошибка в начале.", "positive", "text_start", "multi_finding"),
    _case("comma_decimal", "CommaWhitespaceRule", "Число 12,34 корректно.", "negative", "decimal"),
    _case("comma_thousands", "CommaWhitespaceRule", "Значение 1,000 условных единиц.", "negative", "thousands"),
    _case("comma_nbsp", "CommaWhitespaceRule", "Это ошибка,\u00a0в тексте.", "negative", "nbsp"),
    _case("comma_ellipsis", "CommaWhitespaceRule", "Пауза . . . продолжается.", "positive", "ellipsis"),
    _case("comma_extensions", "CommaWhitespaceRule", "Файлы .DOC .mp3 .org и .exe допустимы.", "negative", "file_extensions"),
    _case("comma_quote_left", "CommaWhitespaceRule", "A sentence ' with' one example.", "positive", "quote_spacing", "upstream_assertion"),
    _case("comma_quote_right", "CommaWhitespaceRule", "A sentence 'with ' one example.", "positive", "quote_spacing", "upstream_assertion"),
    _case("comma_quote_suggestions_left", "CommaWhitespaceRule", "You \" fixed\" it.", "positive", "quote_suggestion_order", "exact_span"),
    _case("comma_quote_suggestions_right", "CommaWhitespaceRule", "You \"fixed \" it.", "positive", "quote_suggestion_order", "exact_span"),
    _case("comma_parenthesis_after", "CommaWhitespaceRule", "ABB (  например )", "positive", "parentheses", "exact_span"),
    _case("comma_parenthesis_before", "CommaWhitespaceRule", "Это (пример ) текста.", "positive", "parentheses"),
    _case("comma_control", "CommaWhitespaceRule", "Сноска\u0002, продолжение.", "negative", "control_character"),
    _case("comma_non_bmp_multiple", "CommaWhitespaceRule", "😀 Раз ,два ,три.", "positive", "multi_finding", "non_bmp"),
    ("uppercase_negative", "UppercaseSentenceStartRule", "Закончилось лето. Дети снова сели.", ["negative", "sentence_boundary"]),
    _case("uppercase_text_start", "UppercaseSentenceStartRule", "строчная буква начинает предложение.", "positive", "upstream_assertion", "text_start", "exact_span"),
    _case("uppercase_single_word", "UppercaseSentenceStartRule", "строчная", "negative", "upstream_assertion", "single_word"),
    _case("uppercase_enumeration", "UppercaseSentenceStartRule", "а) Правильный пункт.", "positive", "upstream_assertion", "enumeration"),
    _case("uppercase_quoted", "UppercaseSentenceStartRule", "«строчная буква в кавычках.", "positive", "upstream_assertion", "quote"),
    ("multiple_ws_positive", "MultipleWhitespaceRule", "Это  тест.", ["positive", "whitespace"]),
    ("multiple_ws_negative", "MultipleWhitespaceRule", "Это тест.", ["negative", "whitespace"]),
    _case("multiple_ws_three", "MultipleWhitespaceRule", "Это   тест  с   пробелами.", "positive", "upstream_assertion", "multi_finding", "exact_span"),
    _case("multiple_ws_nbsp", "MultipleWhitespaceRule", "Это \u00a0тест.", "positive", "upstream_assertion", "nbsp"),
    _case("multiple_ws_tabs", "MultipleWhitespaceRule", "Табы\t\tдопустимы.", "negative", "upstream_assertion", "tabs"),
    _case("multiple_ws_bom", "MultipleWhitespaceRule", "Это\ufeff\ufeff тест.", "negative", "upstream_assertion", "ignored_character"),
    ("sentence_ws_positive", "SentenceWhitespaceRule", "Первое.Второе.", ["positive", "sentence_boundary"]),
    ("sentence_ws_negative", "SentenceWhitespaceRule", "Первое. Второе.", ["negative", "sentence_boundary"]),
    _case("sentence_ws_exclamation", "SentenceWhitespaceRule", "Первое!Второе.", "positive", "upstream_assertion", "exclamation"),
    _case("sentence_ws_question", "SentenceWhitespaceRule", "Первое?Второе.", "positive", "upstream_assertion", "question"),
    _case("sentence_ws_newline", "SentenceWhitespaceRule", "Первое.\nВторое.", "negative", "upstream_assertion", "newline"),
    ("paragraph_end_ws_positive", "WhiteSpaceBeforeParagraphEnd", "Текст.  \n\nСледующий.", ["positive", "paragraph_boundary", "default_off"]),
    ("paragraph_end_ws_negative", "WhiteSpaceBeforeParagraphEnd", "Текст.\n\nСледующий.", ["negative", "paragraph_boundary", "default_off"]),
    ("paragraph_begin_ws_positive", "WhiteSpaceAtBeginOfParagraph", "  Текст.", ["positive", "paragraph_boundary", "default_off"]),
    ("paragraph_begin_ws_negative", "WhiteSpaceAtBeginOfParagraph", "Текст.", ["negative", "paragraph_boundary", "default_off"]),
    _case("long_sentence_equal", "LongSentenceRule", _words(50), "negative", "threshold_equal"),
    _case("long_sentence_above", "LongSentenceRule", _words(51), "positive", "threshold_above", "exact_span"),
    _case("long_sentence_semicolon", "LongSentenceRule", "коротко; " + _words(51), "positive", "semicolon_segment", "exact_span"),
    _case("long_sentence_colon", "LongSentenceRule", "коротко: " + _words(51), "positive", "colon_segment", "exact_span"),
    _case("long_sentence_newline", "LongSentenceRule", "коротко\n" + _words(51), "positive", "newline_segment", "exact_span"),
    _case("long_sentence_quoted", "LongSentenceRule", "начало «" + _words(55, "") + "» конец.", "negative", "quoted_material"),
    _case("long_sentence_bracketed", "LongSentenceRule", "начало (" + _words(55, "") + ") конец.", "negative", "bracketed_material"),
    _case("long_sentence_dash_quote", "LongSentenceRule", "начало — " + _words(55, "") + " — конец.", "negative", "dash_delimited"),
    _case("long_sentence_quoted_end", "LongSentenceRule", _words(51, ".»"), "negative", "quoted_sentence_end"),
    _case("long_sentence_punctuation", "LongSentenceRule", "~ ~ ~ ~ ~ ~ " + _words(5), "negative", "non_word_punctuation", config={"maxWords": 6}),
    _case("long_sentence_config_below", "LongSentenceRule", _words(5), "negative", "config", "below", config={"maxWords": 6}),
    _case("long_sentence_config_equal", "LongSentenceRule", _words(6), "negative", "config", "equal", config={"maxWords": 6}),
    _case("long_sentence_config_above", "LongSentenceRule", _words(7), "positive", "config", "above", config={"maxWords": 6}),
    _case("long_paragraph_equal", "LongParagraphRule", _words(220), "negative", "threshold_equal", "default_off"),
    _case("long_paragraph_guard_band_final_without_separator", "LongParagraphRule", _words(221, ""), "negative", "final_without_separator", "paragraph_end_guard_band", "default_off"),
    _case("long_paragraph_guard_band", "LongParagraphRule", _words(225), "negative", "paragraph_end_guard_band", "default_off"),
    _case("long_paragraph_above_guard", "LongParagraphRule", _words(226), "positive", "paragraph_end_guard_band", "exact_span", "default_off"),
    _case("long_paragraph_final_no_separator", "LongParagraphRule", _words(226, ""), "positive", "final_without_separator", "exact_span", "default_off"),
    _case("long_paragraph_linebreak", "LongParagraphRule", _words(120, ".\n") + _words(106), "negative", "internal_linebreak", "default_off"),
    _case("long_paragraph_checklist", "LongParagraphRule", "- [ ] " + _words(80, ".\n- [ ] ") + _words(80, ".\n- [ ] ") + _words(80), "negative", "checklist_linebreak", "default_off"),
    _case("long_paragraph_multiple", "LongParagraphRule", _words(226, "\n\n") + _words(226), "positive", "multiple_paragraphs", "multi_finding", "default_off"),
    _case("long_paragraph_config_below", "LongParagraphRule", _words(6), "negative", "config", "below", config={"maxWords": 6}),
    _case("long_paragraph_config_equal", "LongParagraphRule", _words(6, ""), "negative", "config", "equal", config={"maxWords": 6}),
    _case("long_paragraph_config_above", "LongParagraphRule", _words(12, ""), "positive", "config", "above_guard", config={"maxWords": 6}),
    ("repeat_paragraph_positive", "ParagraphRepeatBeginningRule", "Текст один.\n\nТекст два.", ["positive", "paragraph_boundary", "multi_finding", "default_off"]),
    ("repeat_paragraph_negative", "ParagraphRepeatBeginningRule", "Первый текст.\n\nДругой текст.", ["negative", "paragraph_boundary", "default_off"]),
    _case("filler_default_above", "RussianFillerWordsRule", "ах слово", "positive", "percentage", "default_config", "default_off"),
    _case("filler_default_below", "RussianFillerWordsRule", "ах " + " ".join("слово" for _ in range(12)), "negative", "percentage", "below", "default_off"),
    _case("filler_default_quote_adjacent", "RussianFillerWordsRule", "«ах слово»", "negative", "default_config", "direct_speech", "quote_adjacent"),
    _case("filler_default_quote_spaced", "RussianFillerWordsRule", "« ах слово»", "positive", "default_config", "direct_speech", "quote_spacing"),
    _case("filler_zero", "RussianFillerWordsRule", "ах слово", "positive", "config", "zero_percent", config={"minPercent": 0, "excludeDirectSpeech": True}),
    _case("filler_eight_equal", "RussianFillerWordsRule", "ах " + " ".join("слово" for _ in range(11)) + " слово", "negative", "config", "eight_percent_equal", config={"minPercent": 8, "excludeDirectSpeech": True}),
    _case("filler_custom_above", "RussianFillerWordsRule", "ах слово слово", "positive", "config", "custom_percent", config={"minPercent": 20, "excludeDirectSpeech": True}),
    _case("filler_custom_below", "RussianFillerWordsRule", "ах слово слово", "negative", "config", "custom_percent", config={"minPercent": 40, "excludeDirectSpeech": True}),
    _case("filler_zero_quote_adjacent", "RussianFillerWordsRule", "«ах слово»", "positive", "direct_speech", "quote_adjacent", "zero_percent", config={"minPercent": 0, "excludeDirectSpeech": True}),
    _case("filler_quote_spaced", "RussianFillerWordsRule", "« ах слово»", "positive", "direct_speech", "quote_spacing", config={"minPercent": 0, "excludeDirectSpeech": True}),
    _case("filler_include_direct", "RussianFillerWordsRule", "«ах слово»", "positive", "direct_speech", "include", config={"minPercent": 0, "excludeDirectSpeech": False}),
    _case("long_sentence_config_ui_below", "LongSentenceRule", _words(5), "positive", "config", "outside_ui_bounds", config={"maxWords": 4}),
    _case("long_sentence_config_ui_above", "LongSentenceRule", _words(102), "positive", "config", "outside_ui_bounds", config={"maxWords": 101}),
    _case("long_paragraph_config_ui_below", "LongParagraphRule", _words(10, ""), "positive", "config", "outside_ui_bounds", config={"maxWords": 4}),
    _case("long_paragraph_config_ui_above", "LongParagraphRule", _words(307, ""), "positive", "config", "outside_ui_bounds", config={"maxWords": 301}),
    _case("filler_config_ui_below", "RussianFillerWordsRule", "ах слово", "positive", "config", "outside_ui_bounds", config={"minPercent": -1, "excludeDirectSpeech": True}),
    _case("filler_config_ui_above", "RussianFillerWordsRule", "ах слово", "negative", "config", "outside_ui_bounds", config={"minPercent": 101, "excludeDirectSpeech": True}),
    ("paragraph_punctuation_positive", "PunctuationMarkAtParagraphEnd2", "один два три четыре пять шесть семь восемь девять десять одиннадцать", ["positive", "threshold", "default_off"]),
    ("paragraph_punctuation_negative", "PunctuationMarkAtParagraphEnd2", "один два три четыре пять шесть семь восемь девять десять одиннадцать.", ["negative", "threshold", "default_off"]),
    _case("paragraph_punctuation_too_short", "PunctuationMarkAtParagraphEnd2", "Это короткий текст без точки", "negative", "upstream_assertion", "too_short", "default_off"),
    _case("paragraph_punctuation_numbered_list", "PunctuationMarkAtParagraphEnd2", "2. Это элемент нумерованного списка", "negative", "upstream_assertion", "list", "default_off"),
    _case("paragraph_punctuation_quoted", "PunctuationMarkAtParagraphEnd2", "\"Это достаточно длинный текст абзаца, состоящий более чем из десяти отдельных слов.\"\n\n", "negative", "upstream_assertion", "quoted", "default_off"),
    _case("brackets_balanced", "RussianUnpairedBracketsRule", "Это (тест).", "negative", "balanced"),
    _case("brackets_missing_closer", "RussianUnpairedBracketsRule", "Это (тест.", "positive", "missing_closer", "exact_span"),
    _case("brackets_unfinished_fragment", "RussianUnpairedBracketsRule", "Это (тест", "negative", "unfinished_last_sentence", "inherited_condition"),
    _case("brackets_missing_opener", "RussianUnpairedBracketsRule", "Это тест).", "positive", "missing_opener", "exact_span"),
    _case("brackets_nested", "RussianUnpairedBracketsRule", "Это {вложенный (тест)}.", "negative", "nested"),
    _case("brackets_mismatch", "RussianUnpairedBracketsRule", "Это (неверно}.", "positive", "mismatched_closing", "multi_finding"),
    _case("brackets_symmetric_balanced", "RussianUnpairedBracketsRule", "Он сказал \"текст\".", "negative", "symmetric_quotes"),
    _case("brackets_cross_sentence", "RussianUnpairedBracketsRule", "Он сказал \"первая фраза. Вторая фраза\".", "negative", "cross_sentence"),
    _case("brackets_cross_paragraph", "RussianUnpairedBracketsRule", "Он сказал \"первая фраза.\n\nВторая фраза\".", "negative", "cross_paragraph"),
    _case("brackets_smileys", "RussianUnpairedBracketsRule", ":-) :-( ;-) ;-( :) :( ;) ;(", "negative", "smileys"),
    _case("brackets_enumeration_latin", "RussianUnpairedBracketsRule", "a) пункт один\nb) пункт два", "negative", "enumeration", "latin_numerals"),
    _case("brackets_enumeration_russian", "RussianUnpairedBracketsRule", "а) пункт один\nб) пункт два\n1) пункт три\n2а) пункт четыре", "negative", "enumeration", "russian_numerals"),
    _case("brackets_url", "RussianUnpairedBracketsRule", "См. https://ru.wikipedia.org/wiki/Тест_(значения)", "negative", "url_parentheses"),
    _case("brackets_punctuation", "RussianUnpairedBracketsRule", "Текст, (пример!", "positive", "punctuation_adjacency"),
    _case("brackets_multiple", "RussianUnpairedBracketsRule", "Текст) и другой {пример.", "positive", "multi_finding", "order"),
    ("verb_positive", "RussianVerbConjugationRule", "Я идёт.", ["positive", "morphology"]),
    ("verb_negative", "RussianVerbConjugationRule", "Я иду.", ["negative", "morphology"]),
    _case("dash_hyphen", "RussianDashRule", "из-за", "negative", "canonical"),
    _case("dash_em", "RussianDashRule", "из—за", "positive", "em_dash"),
    _case("dash_spaced_en", "RussianDashRule", "из – за", "positive", "spaced_en_dash"),
    _case("dash_rostov_spaced_em", "RussianDashRule", "Ростов — на — Дону", "positive", "multi_hyphen", "spaced_em_dash"),
    _case("dash_rostov_spaced_en", "RussianDashRule", "Ростов – на – Дону", "positive", "multi_hyphen", "spaced_en_dash"),
    _case("dash_rostov_em", "RussianDashRule", "Ростов—на—Дону", "positive", "multi_hyphen", "em_dash"),
    _case("dash_rostov_en", "RussianDashRule", "Ростов–на–Дону", "positive", "multi_hyphen", "en_dash"),
    _case("dash_rostov_mixed_one", "RussianDashRule", "Ростов — на – Дону", "negative", "multi_hyphen", "mixed_variant"),
    _case("dash_rostov_mixed_two", "RussianDashRule", "Ростов – на — Дону", "negative", "multi_hyphen", "mixed_variant"),
    ("specific_case_positive", "RussianSpecificCaseRule", "Рытый банк", ["positive", "resource"]),
    ("specific_case_negative", "RussianSpecificCaseRule", "Рытый Банк", ["negative", "resource"]),
]

RUSSIAN_CASES = [
    ("upstream_dash_correct", "RussianDashRule", "Он вышел из-за забора.", ["negative", "upstream_test"]),
    ("upstream_specific_air_france", "RussianSpecificCaseRule", "I like air France.", ["positive", "upstream_test"]),
    ("upstream_specific_central_bank", "RussianSpecificCaseRule", "центральный банк РФ", ["positive", "upstream_test"]),
    ("upstream_specific_correct", "RussianSpecificCaseRule", "Центральный банк РФ", ["negative", "upstream_test"]),
    ("upstream_brackets_apostrophe", "RussianUnpairedBracketsRule", "В таком ключе был начат в мае 1823 в Кишинёве роман в стихах 'Евгений Онегин.", ["positive", "upstream_test"]),
    ("upstream_brackets_balanced", "RussianUnpairedBracketsRule", "(О жене и детях не беспокойся, я беру их на свои руки).", ["negative", "upstream_test"]),
    ("upstream_brackets_numerals", "RussianUnpairedBracketsRule", "а), б), Д)..., ДД), аа) и 1а)", ["negative", "upstream_test"]),
    ("upstream_verb_wrong_present", "RussianVerbConjugationRule", "Мы думаю", ["positive", "upstream_test", "morphology"]),
    ("upstream_verb_wrong_past", "RussianVerbConjugationRule", "Она ходил", ["positive", "upstream_test", "morphology"]),
    ("upstream_verb_correct", "RussianVerbConjugationRule", "Они пишут", ["negative", "upstream_test", "morphology"]),
    ("upstream_comma", "CommaWhitespaceRule", "Не род , а ум поставлю в воеводы.", ["positive", "registered_example", "upstream_assertion"]),
    ("upstream_uppercase", "UppercaseSentenceStartRule", "Закончилось лето. дети снова сели за школьные парты.", ["positive", "registered_example"]),
]

COMBINED_CASES = [
    {"id": "combined_xml_then_comma", "text": "Ученик решил задать тест учителю. Не род , а ум.", "explicitly_enabled_rules": [], "coverage": ["xml", "java_rule", "different_offsets", "ordering"]},
    {"id": "combined_comma_then_xml", "text": "Не род , а ум. Ученик решил задать тест учителю.", "explicitly_enabled_rules": [], "coverage": ["xml", "java_rule", "different_offsets", "ordering"]},
    {"id": "combined_same_offset_priority", "text": "из—за", "explicitly_enabled_rules": [], "coverage": ["java_rule", "same_offset", "priority", "ordering"]},
    {"id": "combined_same_offset_casing", "text": "центральный банк РФ", "explicitly_enabled_rules": [], "coverage": ["java_rule", "overlap", "ordering"]},
    {"id": "combined_default_off_filler", "text": "ах слово. Ученик решил задать тест учителю.", "explicitly_enabled_rules": ["FILLER_WORDS_RU"], "coverage": ["xml", "java_rule", "default_off", "explicit_enablement", "multiple_findings"]},
    {"id": "combined_multiple_findings", "text": "Ученик решил задать тест учителю ,а затем задать тест преподавателю.", "explicitly_enabled_rules": [], "coverage": ["xml", "java_rule", "multiple_findings", "ordering"]},
    {
        "id": "combined_picky_long_sentence_comma_overlap",
        "text": " ".join(["Слово"] + ["слово"] * 24 + ["слово", ",слово"] + ["слово"] * 25) + ".",
        "explicitly_enabled_rules": ["TOO_LONG_SENTENCE"],
        "config": {"level": "picky"},
        "raw_rule_ids": ["TOO_LONG_SENTENCE", "COMMA_PARENTHESIS_WHITESPACE"],
        "coverage": ["picky", "overlap", "raw_rule_triggers", "same_rule_group", "priority"],
    },
    {
        "id": "combined_picky_long_sentence_xml_overlap",
        "text": " ".join(["Слово"] + ["слово"] * 18) + " ученик решил задать тест учителю " + " ".join(["слово"] * 31) + ".",
        "explicitly_enabled_rules": ["TOO_LONG_SENTENCE"],
        "config": {"level": "picky"},
        "raw_rule_ids": ["TOO_LONG_SENTENCE"],
        "coverage": ["picky", "overlap", "xml", "priority"],
    },
    {"id": "combined_equal_priority_same_length_last_tie", "text": "Привет друзья!", "explicitly_enabled_rules": [], "coverage": ["xml", "equal_priority", "same_length", "last_match_tie"]},
    {"id": "combined_equal_priority_nested_longest_tie", "text": "Сделано таким образом что работает.", "explicitly_enabled_rules": [], "coverage": ["xml", "equal_priority", "nested", "longest_span_tie"]},
    {"id": "combined_adjacent_non_overlapping", "text": "Не род ,а ум. Не чин ,а честь.", "explicitly_enabled_rules": [], "coverage": ["java_rule", "adjacent", "non_overlapping", "ordering"]},
]


def _decode(value: str) -> str:
    return base64.b64decode(value).decode("utf-8") if value else ""


def _config_arg(config: dict[str, Any]) -> str:
    return ";".join(f"{key}={str(value).lower() if isinstance(value, bool) else value}" for key, value in sorted(config.items()))


def _probe(java: str, jar: Path, rule_id: str, text: str, config: dict[str, Any] | None = None, *, mode: str = "single", enabled: list[str] | None = None) -> list[dict[str, Any]]:
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    config_encoded = base64.b64encode(_config_arg(config or {}).encode("utf-8")).decode("ascii")
    command = {"single": "--check", "combined": "--combined", "combined_raw": "--combined-raw"}[mode]
    selector = rule_id if mode == "single" else ",".join(enabled or [])
    proc = subprocess.run(
        [java, "-Dfile.encoding=UTF-8", "-cp", f"{JAVA_SOURCE.parent}{os.pathsep}{jar}", "JavaRulesOracle0011", command, selector, encoded, config_encoded],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    mapper = Utf16CodePointMapper(text)
    findings = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        fields.extend([""] * (9 - len(fields)))
        start16, end16 = int(fields[0]), int(fields[1])
        suggestions = tuple(_decode(fields[7]).split("\u0000")) if fields[7] else ()
        start, end = mapper.utf16_to_codepoint(start16), mapper.utf16_to_codepoint(end16)
        findings.append({
            "rule_id": fields[2],
            "category_id": fields[3],
            "category_name": _decode(fields[4]),
            "message": _decode(fields[5]),
            "short_message": _decode(fields[6]),
            "suggestions": list(suggestions),
            "url": _decode(fields[8]) or None,
            "from_utf16": start16,
            "to_utf16": end16,
            "from": start,
            "to": end,
            "source_slice": text[start:end],
        })
    return findings


def _signature(case: dict[str, Any]) -> str:
    payload = {key: case.get(key, []) if key == "raw_rule_ids" else case[key] for key in ("execution_mode", "rule_class", "rule_id", "text", "explicitly_enabled", "explicitly_enabled_rules", "explicitly_disabled_rules", "config", "raw_rule_ids")}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_coverage(case: dict[str, Any]) -> None:
    coverage = set(case["coverage"])
    count = case["finding_count"]
    if "positive" in coverage and "negative" in coverage:
        raise ValueError(f"{case['id']}: coverage cannot be both positive and negative")
    if "positive" in coverage and count == 0:
        raise ValueError(f"{case['id']}: positive coverage requires at least one Java finding")
    if "negative" in coverage and count != 0:
        raise ValueError(f"{case['id']}: negative coverage requires zero Java findings, got {count}")
    if coverage.intersection({"multi_finding", "multiple_findings"}) and count <= 1:
        raise ValueError(f"{case['id']}: multiple-finding coverage requires more than one Java finding")


def generate(cases: list[Any], path: Path, jar: Path, build_id: str) -> None:
    compiled = []
    for raw_case in cases:
        if isinstance(raw_case, tuple):
            case_id, rule_class, text, coverage = raw_case
            raw_case = _case(case_id, rule_class, text, *coverage)
        case_id, rule_class, text = raw_case["id"], raw_case["rule_class"], raw_case["text"]
        rule_id = RULES[rule_class]
        case = {
            "id": case_id,
            "rule_class": rule_class,
            "rule_id": rule_id,
            "text": text,
            "execution_mode": "single_rule",
            "explicitly_enabled": True,
            "explicitly_enabled_rules": [],
            "explicitly_disabled_rules": [],
            "config": raw_case.get("config", {}),
            "coverage": raw_case["coverage"],
            "expected": _probe("java", jar, rule_id, text, raw_case.get("config")),
        }
        case["finding_count"] = len(case["expected"])
        _validate_coverage(case)
        case["semantic_signature"] = _signature(case)
        compiled.append(case)
    data = {
        "metadata": {
            "schema_version": "1.0.0",
            "task": "0011",
            "pinned_lt_commit": "e807fcde6a6506191e1470744d2345da28c26be6",
            "oracle_build_id": build_id,
            "oracle_generated": True,
            "case_count": len(compiled),
        },
        "cases": compiled,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def generate_combined(path: Path, jar: Path, build_id: str) -> None:
    compiled = []
    for raw_case in COMBINED_CASES:
        case = {
            **raw_case,
            "rule_class": "JLanguageTool",
            "rule_id": "*",
            "execution_mode": "combined_pipeline",
            "explicitly_enabled": False,
            "explicitly_disabled_rules": DEFERRED_RULE_IDS,
            "config": raw_case.get("config", {}),
            "raw_rule_ids": raw_case.get("raw_rule_ids", []),
        }
        case["pre_overlap_expected"] = _probe("java", jar, "", case["text"], case["config"], mode="combined_raw", enabled=case["explicitly_enabled_rules"])
        case["raw_rule_expected"] = {
            rule_id: _probe("java", jar, rule_id, case["text"], case["config"])
            for rule_id in case["raw_rule_ids"]
        }
        case["expected"] = _probe("java", jar, "", case["text"], case["config"], mode="combined", enabled=case["explicitly_enabled_rules"])
        case["finding_count"] = len(case["expected"])
        _validate_coverage(case)
        case["semantic_signature"] = _signature(case)
        compiled.append(case)
    data = {"metadata": {"schema_version": "1.0.0", "task": "0011", "pinned_lt_commit": "e807fcde6a6506191e1470744d2345da28c26be6", "oracle_build_id": build_id, "oracle_generated": True, "case_count": len(compiled)}, "cases": compiled}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "tests" / "fixtures")
    args = parser.parse_args()
    oracle = JavaLanguageToolOracle()
    identity = oracle.validate_oracle()
    jar = Path(identity["jar_path"])
    subprocess.run(["javac", "-encoding", "UTF-8", "-cp", str(jar), str(JAVA_SOURCE)], check=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    generate(SYNTHETIC_CASES, args.output_dir / "oracle_java_rules_0011_synthetic.json", jar, identity["oracle_build_id"])
    generate(RUSSIAN_CASES, args.output_dir / "oracle_java_rules_0011_russian.json", jar, identity["oracle_build_id"])
    generate_combined(args.output_dir / "oracle_java_rules_0011_combined.json", jar, identity["oracle_build_id"])


if __name__ == "__main__":
    main()
