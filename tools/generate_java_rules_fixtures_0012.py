"""Generate deterministic Task-0012 fixtures from the trusted Java LT oracle.

Covers the eight remaining ordinary Russian rules, direct speller queries, the
final Russian XML rule filter, and combined-pipeline runs with all 23 ordinary
rules active according to the pinned defaults.
"""

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
JAVA_SOURCE = ROOT / "tools" / "JavaRulesOracle0012.java"
PINNED_LT_COMMIT = "e807fcde6a6506191e1470744d2345da28c26be6"

RULES = {
    "MorfologikRussianSpellerRule": "MORFOLOGIK_RULE_RU_RU",
    "MorfologikRussianYOSpellerRule": "MORFOLOGIK_RULE_RU_RU_YO",
    "RussianCompoundRule": "RU_COMPOUNDS",
    "RussianSimpleReplaceRule": "RU_SIMPLE_REPLACE",
    "RussianSimpleWordRepeatRule": "WORD_REPEAT_RULE",
    "RussianWordCoherencyRule": "RU_WORD_COHERENCY",
    "RussianWordRepeatRule": "RU_WORD_REPEAT",
    "RussianWordRootRepeatRule": "RU_WORD_ROOT_REPEAT",
}

DEFAULT_OFF_RULE_IDS = ["MORFOLOGIK_RULE_RU_RU_YO", "RU_WORD_REPEAT", "RU_WORD_ROOT_REPEAT"]


def _case(
    case_id: str,
    rule_class: str,
    text: str,
    *coverage: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "rule_class": rule_class,
        "text": text,
        "coverage": list(coverage),
        "config": config or {},
    }


def _spell(case_id: str, rule_class: str, word: str, *coverage: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": case_id,
        "rule_class": rule_class,
        "text": word,
        "coverage": list(coverage),
        "config": config or {},
    }


# ---------------------------------------------------------------------------
# Direct speller queries (isMisspelled + full suggestion surface)
# ---------------------------------------------------------------------------

SPELLING_DIRECT_CASES = [
    _spell("spell_correct_cyrillic", "MorfologikRussianSpellerRule", "русский", "negative", "correct_cyrillic", "upstream_assertion"),
    _spell("spell_correct_yo", "MorfologikRussianSpellerRule", "ёжик", "negative", "yo_vs_ye", "upstream_assertion"),
    _spell("spell_correct_ye", "MorfologikRussianSpellerRule", "ежик", "negative", "yo_vs_ye", "upstream_assertion"),
    _spell("spell_misspelled_cyrillic", "MorfologikRussianSpellerRule", "каждя", "positive", "misspelled_cyrillic", "several_suggestions", "suggestion_order"),
    _spell("spell_hyphen_wrong", "MorfologikRussianSpellerRule", "юго-зпдный", "positive", "hyphenated", "upstream_assertion"),
    _spell("spell_hyphen_correct", "MorfologikRussianSpellerRule", "северо-восточный", "negative", "hyphenated", "upstream_assertion"),
    _spell("spell_proper_hyphen_correct", "MorfologikRussianSpellerRule", "Ростов-на-Дону", "negative", "hyphenated", "title_case", "upstream_assertion"),
    _spell("spell_proper_hyphen_wrong", "MorfologikRussianSpellerRule", "Ростов-на-дону", "positive", "hyphenated", "title_case", "upstream_assertion"),
    _spell("spell_sentence_start_case", "MorfologikRussianSpellerRule", "Превет", "positive", "sentence_start_capitalization", "suggestion_capitalization"),
    _spell("spell_all_caps", "MorfologikRussianSpellerRule", "ПРЕВЕТ", "negative", "all_caps", "ignore_all_uppercase"),
    _spell("spell_all_caps_correct", "MorfologikRussianSpellerRule", "ПРИВЕТ", "negative", "all_caps"),
    _spell("spell_mixed_case", "MorfologikRussianSpellerRule", "ПрИвЕт", "negative", "mixed_case", "ignore_all_uppercase"),
    _spell("spell_title_case_wrong", "MorfologikRussianSpellerRule", "Каждя", "positive", "title_case", "suggestion_capitalization", "several_suggestions"),
    _spell("spell_combining_acute", "MorfologikRussianSpellerRule", "ко́т", "positive", "combining_acute", "unmappable_in_dictionary_charset", "several_suggestions"),
    _spell("spell_combining_grave", "MorfologikRussianSpellerRule", "ко̀т", "positive", "combining_grave", "unmappable_in_dictionary_charset", "several_suggestions"),
    _spell("spell_modifier_apostrophe", "MorfologikRussianSpellerRule", "котʼ", "positive", "modifier_apostrophe", "unmappable_in_dictionary_charset", "several_suggestions"),
    _spell("spell_digits", "MorfologikRussianSpellerRule", "12345", "negative", "digits"),
    _spell("spell_punctuation", "MorfologikRussianSpellerRule", "!!!", "negative", "punctuation"),
    _spell("spell_latin_default_config", "MorfologikRussianSpellerRule", "wordd", "positive", "non_russian", "config_zero", "config_not_applied_by_direct_query"),
    _spell("spell_latin_config_one", "MorfologikRussianSpellerRule", "wordd", "positive", "non_russian", "config_one", "several_suggestions", config={"conf_ru_Value": 1}),
    _spell("spell_latin_config_minus_one", "MorfologikRussianSpellerRule", "wordd", "positive", "non_russian", "config_out_of_ui_bounds", "config_not_applied_by_direct_query", config={"conf_ru_Value": -1}),
    _spell("spell_latin_config_two", "MorfologikRussianSpellerRule", "wordd", "positive", "non_russian", "config_out_of_ui_bounds", "config_not_applied_by_direct_query", config={"conf_ru_Value": 2}),
    _spell("spell_mixed_script", "MorfologikRussianSpellerRule", "teхt", "positive", "mixed_script", "config_zero", "no_suggestions"),
    _spell("spell_mixed_script_config_one", "MorfologikRussianSpellerRule", "teхt", "positive", "mixed_script", "config_one", "no_suggestions", config={"conf_ru_Value": 1}),
    _spell("spell_spelling_txt_addition", "MorfologikRussianSpellerRule", "ГИБДД", "negative", "spelling_addition"),
    _spell("spell_prohibited_word", "MorfologikRussianSpellerRule", "Тайланд", "negative", "prohibit_resource", "prohibition_not_applied_by_direct_query"),
    _spell("spell_prohibited_lowercase", "MorfologikRussianSpellerRule", "друшлаг", "positive", "prohibit_resource"),
    _spell("spell_ignore_txt_entry", "MorfologikRussianSpellerRule", "что-что", "positive", "ignore_resource", "ignore_list_not_applied_by_direct_query", "no_suggestions"),
    _spell("spell_nosuggest_blogger", "MorfologikRussianSpellerRule", "блогер", "negative", "nosuggest"),
    _spell("spell_no_suggestion_result", "MorfologikRussianSpellerRule", "ыфвацйщшгн", "positive", "no_suggestions"),
    _spell("spell_url_token", "MorfologikRussianSpellerRule", "http://example.com/абв", "positive", "url", "url_check_not_applied_by_direct_query", "no_suggestions", config={"conf_ru_Value": 1}),
    _spell("spell_email_token", "MorfologikRussianSpellerRule", "user@example.com", "positive", "email", "email_check_not_applied_by_direct_query", "no_suggestions", config={"conf_ru_Value": 1}),
    _spell("spell_global_spelling_phrase_token", "MorfologikRussianSpellerRule", "Facebook", "negative", "global_spelling_resource", config={"conf_ru_Value": 1}),
    _spell("spell_languagetool", "MorfologikRussianSpellerRule", "LanguageTool", "negative", "languagetool_special", config={"conf_ru_Value": 1}),
    _spell("spell_yo_correct", "MorfologikRussianYOSpellerRule", "ёжик", "negative", "yo_dictionary", "upstream_assertion"),
    _spell("spell_yo_ye_is_wrong", "MorfologikRussianYOSpellerRule", "ежик", "positive", "yo_dictionary", "upstream_assertion"),
    _spell("spell_yo_russian", "MorfologikRussianYOSpellerRule", "русский", "negative", "yo_dictionary", "upstream_assertion"),
    _spell("spell_yo_hyphen_wrong", "MorfologikRussianYOSpellerRule", "юго-зпдный", "positive", "yo_dictionary", "hyphenated", "upstream_assertion"),
    _spell("spell_yo_hyphen_correct", "MorfologikRussianYOSpellerRule", "северо-восточный", "negative", "yo_dictionary", "hyphenated", "upstream_assertion"),
    _spell("spell_yo_proper_hyphen", "MorfologikRussianYOSpellerRule", "Ростов-на-Дону", "negative", "yo_dictionary", "hyphenated", "upstream_assertion"),
    _spell("spell_yo_nosuggest_elka", "MorfologikRussianYOSpellerRule", "елка", "positive", "yo_dictionary", "nosuggest"),
]


# ---------------------------------------------------------------------------
# Single-rule checks over full sentences
# ---------------------------------------------------------------------------

SPELLING_RULE_CASES = [
    _case("spell_rule_registered_example", "MorfologikRussianSpellerRule", "Все счастливые семьи похожи друг на друга, каждя несчастливая семья несчастлива по-своему.", "positive", "registered_example", "exact_span", "suggestion_order"),
    _case("spell_rule_sentence_start", "MorfologikRussianSpellerRule", "Превет мир!", "positive", "sentence_start_capitalization", "suggestion_capitalization"),
    _case("spell_rule_multiple_errors", "MorfologikRussianSpellerRule", "Это тест с ыфвацй и жщшгн.", "positive", "multi_finding", "multiple_misspellings"),
    _case("spell_rule_correct_sentence", "MorfologikRussianSpellerRule", "Это правильное предложение.", "negative", "correct_cyrillic"),
    _case("spell_rule_url_and_email", "MorfologikRussianSpellerRule", "Смотри http://example.com/page и user@example.com.", "negative", "url", "email"),
    _case("spell_rule_numbers_punctuation", "MorfologikRussianSpellerRule", "Число 12345 и знак §.", "negative", "digits", "punctuation"),
    _case("spell_rule_non_bmp_prefix", "MorfologikRussianSpellerRule", "😀 каждя.", "positive", "non_bmp", "exact_span"),
    _case("spell_rule_soft_hyphen_inside", "MorfologikRussianSpellerRule", "каж­dя слово.", "negative", "ignored_characters", "russian_letter_pattern"),
    _case("spell_rule_soft_hyphen_inside_config_one", "MorfologikRussianSpellerRule", "каж­dя слово.", "positive", "ignored_characters", "hidden_char_offset", "exact_span", config={"conf_ru_Value": 1}),
    _case("spell_rule_combining_acute_word", "MorfologikRussianSpellerRule", "ко́т сидит.", "negative", "combining_acute"),
    _case("spell_rule_prohibited", "MorfologikRussianSpellerRule", "Тайланд красив.", "positive", "prohibit_resource"),
    _case("spell_rule_spelling_addition", "MorfologikRussianSpellerRule", "ГИБДД и ОСАГО работают.", "negative", "spelling_addition"),
    _case("spell_rule_antipattern_phrase", "MorfologikRussianSpellerRule", "Microsoft Entra тут.", "negative", "ignore_spelling_antipattern", config={"conf_ru_Value": 1}),
    _case("spell_rule_antipattern_tokenized", "MorfologikRussianSpellerRule", "Он использует log4j сегодня.", "negative", "ignore_spelling_antipattern", config={"conf_ru_Value": 1}),
    _case("spell_rule_latin_config_one", "MorfologikRussianSpellerRule", "The quick brown fox.", "positive", "non_russian", "config_one", "multi_finding", config={"conf_ru_Value": 1}),
    _case("spell_rule_latin_config_zero", "MorfologikRussianSpellerRule", "The quick brown fox.", "negative", "non_russian", "config_zero"),
    _case("spell_rule_yo_default_dictionary", "MorfologikRussianYOSpellerRule", "Ежик и елка.", "positive", "yo_dictionary", "multi_finding", "default_off"),
    _case("spell_rule_yo_correct", "MorfologikRussianYOSpellerRule", "Ёжик и ёлка.", "negative", "yo_dictionary", "default_off"),
]

RULE_CASES = [
    # RussianCompoundRule -- all assertions from RussianCompoundRuleTest
    _case("compound_correct_hyphen", "RussianCompoundRule", "Он вышел из-за дома.", "negative", "upstream_assertion"),
    _case("compound_correct_abbrev", "RussianCompoundRule", "Разработка ПО за идею.", "negative", "upstream_assertion"),
    _case("compound_either_form_ok", "RussianCompoundRule", "естественно-научный", "negative", "upstream_assertion", "either_form"),
    _case("compound_space_to_hyphen", "RussianCompoundRule", "из за", "positive", "upstream_assertion", "space_to_hyphen", "exact_span"),
    _case("compound_space_to_hyphen_po", "RussianCompoundRule", "по за", "positive", "upstream_assertion", "space_to_hyphen"),
    _case("compound_inside_longer_text", "RussianCompoundRule", "нет нет из за да да", "positive", "upstream_assertion", "token_boundaries"),
    _case("compound_multi_token", "RussianCompoundRule", "Ростов на Дону", "positive", "upstream_assertion", "multi_token", "exact_span"),
    _case("compound_joined_only", "RussianCompoundRule", "кругло суточный", "positive", "upstream_assertion", "space_to_joined"),
    _case("compound_wrong_case", "RussianCompoundRule", "Ростов на дону", "negative", "upstream_assertion", "case_sensitivity"),
    _case("compound_wrong_case_lower", "RussianCompoundRule", "Ведь сейчас в лос Анджелесе", "negative", "upstream_assertion", "case_sensitivity"),
    _case("compound_partial_hyphen", "RussianCompoundRule", "Ростов-на Дону", "positive", "upstream_assertion", "partial_hyphen", "exact_span"),
    _case("compound_single_char_correct", "RussianCompoundRule", "во-первых", "negative", "upstream_assertion", "single_char_first_part"),
    _case("compound_single_char_wrong", "RussianCompoundRule", "во первых", "positive", "upstream_assertion", "single_char_first_part"),
    _case("compound_los_angeles", "RussianCompoundRule", "Лос Анджелес", "positive", "upstream_assertion", "exact_span"),
    _case("compound_los_angeles_inflected", "RussianCompoundRule", "Ведь сейчас в Лос Анджелесе", "positive", "upstream_assertion"),
    _case("compound_los_angeles_sentence", "RussianCompoundRule", "Ведь сейчас в Лос Анджелесе хорошая погода.", "positive", "upstream_assertion"),
    _case("compound_sentence_start_upper", "RussianCompoundRule", "Во первых, мы были довольно высоко над уровнем моря.", "positive", "upstream_assertion", "sentence_start_uppercase"),
    _case("compound_mid_sentence", "RussianCompoundRule", "Мы, во первых, были довольно высоко над уровнем моря.", "positive", "upstream_assertion", "punctuation_boundary"),
    _case("compound_registered_example", "RussianCompoundRule", "Собрание состоится в конференц зале.", "positive", "registered_example", "exact_span"),
    _case("compound_all_uppercase", "RussianCompoundRule", "ЛОС АНДЖЕЛЕС", "negative", "all_uppercase"),

    # RussianSimpleReplaceRule
    _case("replace_correct_a", "RussianSimpleReplaceRule", "Рост кораллов тут самый быстрый,", "negative", "upstream_assertion"),
    _case("replace_correct_b", "RussianSimpleReplaceRule", "Книга была порвана.", "negative", "upstream_assertion"),
    _case("replace_single_word", "RussianSimpleReplaceRule", "Книга была порвата.", "positive", "upstream_assertion", "single_word", "exact_span"),
    _case("replace_registered_example", "RussianSimpleReplaceRule", "Экспрессо – крепкий кофе.", "positive", "registered_example", "sentence_start_case"),
    _case("replace_all_uppercase", "RussianSimpleReplaceRule", "ЭКСПРЕССО – крепкий кофе.", "positive", "all_uppercase", "case_adaptation"),
    _case("replace_sentence_start", "RussianSimpleReplaceRule", "Порвата книга.", "positive", "sentence_start_case", "case_adaptation"),
    _case("replace_multi_word", "RussianSimpleReplaceRule", "по-крайней мере это так.", "positive", "multi_word"),
    _case("replace_multi_word_space", "RussianSimpleReplaceRule", "Он хотел ни будь там.", "positive", "multi_word"),
    _case("replace_digits_form", "RussianSimpleReplaceRule", "Здесь было 2-ух человек.", "positive", "digit_form"),
    _case("replace_punctuation_adjacent", "RussianSimpleReplaceRule", "«порвата» книга.", "positive", "punctuation_adjacency"),
    _case("replace_multiple_findings", "RussianSimpleReplaceRule", "Книга была порвата, и другая книга была порвата.", "positive", "multi_finding"),

    # RussianSimpleWordRepeatRule
    _case("simple_repeat_positive", "RussianSimpleWordRepeatRule", "Это это тест.", "positive", "immediate_repeat", "exact_span"),
    _case("simple_repeat_negative", "RussianSimpleWordRepeatRule", "Это тест.", "negative", "immediate_repeat"),
    _case("simple_repeat_case_variant", "RussianSimpleWordRepeatRule", "Дом дом стоит.", "positive", "case_variants"),
    _case("simple_repeat_ignored_i", "RussianSimpleWordRepeatRule", "Он и и она.", "negative", "ignored_word"),
    _case("simple_repeat_ignored_po", "RussianSimpleWordRepeatRule", "Он по по дороге.", "negative", "ignored_word"),
    _case("simple_repeat_ignored_po_abbrev", "RussianSimpleWordRepeatRule", "Установил ПО по инструкции.", "negative", "ignored_word"),
    _case("simple_repeat_ignored_chto", "RussianSimpleWordRepeatRule", "Он сказал что что.", "negative", "ignored_word"),
    _case("simple_repeat_single_letters", "RussianSimpleWordRepeatRule", "Буквы а а б.", "negative", "single_letter_spelling"),
    _case("simple_repeat_punctuation_between", "RussianSimpleWordRepeatRule", "Дом, дом стоит.", "negative", "punctuation_between"),
    _case("simple_repeat_sentence_boundary", "RussianSimpleWordRepeatRule", "Это дом. Дом стоит.", "negative", "sentence_boundary"),
    _case("simple_repeat_multiple", "RussianSimpleWordRepeatRule", "Дом дом стоит. Сад сад цветёт.", "positive", "multi_finding"),
    _case("simple_repeat_numbers", "RussianSimpleWordRepeatRule", "Число 1 1 тут.", "negative", "numeric"),
    _case("simple_repeat_ellipsis", "RussianSimpleWordRepeatRule", "Пауза ... ... конец.", "negative", "punctuation_only"),
    _case("simple_repeat_quoted", "RussianSimpleWordRepeatRule", "Он сказал «дом дом».", "positive", "quoted_text"),
    _case("simple_repeat_paragraph_boundary", "RussianSimpleWordRepeatRule", "Это дом.\n\nДом стоит.", "negative", "paragraph_boundary"),

    # RussianWordCoherencyRule
    _case("coherency_negative_upstream", "RussianWordCoherencyRule", "По шкале Цельсия абсолютному нулю соответствует температура −273,15 °C.", "negative", "upstream_assertion"),
    _case("coherency_positive_upstream", "RussianWordCoherencyRule", "По шкале Цельсия абсолютному нулю соответствует температура −273,15 °C или ноль по шкале Кельвина.", "positive", "upstream_assertion", "exact_span"),
    _case("coherency_consistent_spelling", "RussianWordCoherencyRule", "По шкале Цельсия абсолютному нулю соответствует температура −273,15 °C или нуль по шкале Кельвина.", "negative", "upstream_assertion"),
    _case("coherency_call_independence_a", "RussianWordCoherencyRule", "Абсолютный нуль.", "negative", "upstream_assertion", "call_independence"),
    _case("coherency_call_independence_b", "RussianWordCoherencyRule", "Ноль по шкале Кельвина.", "negative", "upstream_assertion", "call_independence"),
    _case("coherency_cross_paragraph", "RussianWordCoherencyRule", "Абсолютный нуль.\n\nСовсем недостижим. И ноль по шкале Кельвина.", "positive", "upstream_assertion", "paragraph_boundary"),
    _case("coherency_registered_example", "RussianWordCoherencyRule", "Понятие «оффлайн» тоже имеет английские корни и связано со словом «offline», что означает «вне сети». Принтер перешёл в состояние офлайн.", "positive", "registered_example", "exact_span"),
    _case("coherency_blogger", "RussianWordCoherencyRule", "Он блогер. Другой блоггер тоже.", "positive", "resource_entry"),
    _case("coherency_case_adaptation", "RussianWordCoherencyRule", "Он блогер. Другая блоггер тут.", "positive", "case_adaptation"),

    # RussianWordRepeatRule (default off)
    _case("word_repeat_negative_upstream", "RussianWordRepeatRule", "Повтор слов в предложении.", "negative", "upstream_assertion", "default_off"),
    _case("word_repeat_positive_upstream", "RussianWordRepeatRule", "Повтор слов в повтор предложении.", "positive", "upstream_assertion", "default_off", "exact_span"),
    _case("word_repeat_registered_example", "RussianWordRepeatRule", "Всё смешалось в доме доме Облонских.", "positive", "registered_example", "default_off"),
    _case("word_repeat_excluded_word", "RussianWordRepeatRule", "Он не пошёл и не поехал.", "negative", "excluded_word", "default_off"),
    _case("word_repeat_excluded_pos", "RussianWordRepeatRule", "Он шёл в дом в сад.", "negative", "excluded_pos", "default_off"),
    _case("word_repeat_numbers", "RussianWordRepeatRule", "Было 5 и 5 предметов.", "negative", "excluded_nonwords", "default_off"),
    _case("word_repeat_distance", "RussianWordRepeatRule", "Дом стоял высоко, а другой дом стоял низко.", "positive", "distance", "default_off"),

    # RussianWordRootRepeatRule (default off)
    _case("root_repeat_registered_example", "RussianWordRootRepeatRule", "Абрикос рос в саду. У меня на столе стоит абрикосный сок.", "positive", "registered_example", "default_off", "exact_span"),
    _case("root_repeat_negative", "RussianWordRootRepeatRule", "Абрикос рос в саду.", "negative", "default_off"),
    _case("root_repeat_single_sentence", "RussianWordRootRepeatRule", "Абрикосный сок и абрикос.", "positive", "same_sentence", "default_off"),
    _case("root_repeat_unrelated", "RussianWordRootRepeatRule", "Яблоко лежит на столе. Груша тоже.", "negative", "unrelated_words", "default_off"),
    _case("root_repeat_paragraph_boundary", "RussianWordRootRepeatRule", "Абрикос рос в саду.\n\nСок абрикосный вкусный.", "positive", "paragraph_boundary", "default_off"),
]


# ---------------------------------------------------------------------------
# XML rules that depend on the final Russian filter / suppress_misspelled
# ---------------------------------------------------------------------------

FILTER_CASES = [
    _case("filter_nn_pril_prich_incorrect", "PatternRule", "Сегодня на ужин жареная на масле картошка.", "positive", "real_grammar_rule", "suppress_match_true", "exact_span"),
    _case("filter_nn_pril_prich_incorrect_2", "PatternRule", "Сегодня на ужин жареная в этом масле картошка.", "positive", "real_grammar_rule", "suppress_match_true"),
    _case("filter_nn_pril_prich_correct", "PatternRule", "Сегодня на ужин жаренная на масле картошка.", "negative", "real_grammar_rule", "suppress_match_true"),
    _case("filter_nn_pril_prich_exception", "PatternRule", "Стеклянный, оловянный и деревянный – это исключения из правила.", "negative", "real_grammar_rule", "suppress_match_true"),
    _case("filter_nn_pril_prich_suppressed", "PatternRule", "Вводится единый для всех ведомств госбюджет, с едиными остатками.", "negative", "real_grammar_rule", "all_misspelled_suppressed"),
    _case("filter_nn_pril_prich_zelenoy", "PatternRule", "Это сделано с целью получения «самой зеленой в мире» электроэнергии.", "negative", "real_grammar_rule", "token_exception"),
    _case("filter_nn_pril_prich_woman", "PatternRule", "Я не уверена в том, что он говорит правду.", "negative", "real_grammar_rule", "all_misspelled_suppressed"),
    _case("suggestion_suppress_nn_to_n", "PatternRule", "Сегодня на ужин жаренная картошка.", "positive", "suggestion_suppress_misspelled", "exact_span"),
    _case("suggestion_suppress_nn_to_n_negative", "PatternRule", "Сегодня у нас на ужин жаренная Иваном картошка.", "negative", "suggestion_suppress_misspelled"),
    _case("message_suppress_vodnyy", "PatternRule", "Раньше в этом регионе.", "negative", "message_suppress_misspelled"),
]

FILTER_RULE_IDS = {
    "filter_nn_pril_prich_incorrect": "NN_N_pril_prich[1]",
    "filter_nn_pril_prich_incorrect_2": "NN_N_pril_prich[1]",
    "filter_nn_pril_prich_correct": "NN_N_pril_prich[1]",
    "filter_nn_pril_prich_exception": "NN_N_pril_prich[1]",
    "filter_nn_pril_prich_suppressed": "NN_N_pril_prich[1]",
    "filter_nn_pril_prich_zelenoy": "NN_N_pril_prich[1]",
    "filter_nn_pril_prich_woman": "NN_N_pril_prich[1]",
    "suggestion_suppress_nn_to_n": "NN_N_pril_prich[2]",
    "suggestion_suppress_nn_to_n_negative": "NN_N_pril_prich[2]",
    "message_suppress_vodnyy": "NN_N_pril_prich[2]",
}


# ---------------------------------------------------------------------------
# Combined pipeline
# ---------------------------------------------------------------------------

COMBINED_CASES = [
    {"id": "combined_spelling_only", "text": "Все счастливые семьи похожи друг на друга, каждя несчастливая семья несчастлива по-своему.", "explicitly_enabled_rules": [], "coverage": ["spelling", "ordering"]},
    {"id": "combined_compound_priority", "text": "Собрание состоится в конференц зале.", "explicitly_enabled_rules": [], "coverage": ["java_rule", "priority", "overlap"]},
    {"id": "combined_compound_vs_spelling", "text": "Ведь сейчас в Лос Анджелесе хорошая погода.", "explicitly_enabled_rules": [], "coverage": ["java_rule", "priority", "spelling", "overlap"]},
    {"id": "combined_replace_vs_spelling", "text": "Книга была порвата.", "explicitly_enabled_rules": [], "coverage": ["java_rule", "spelling", "overlap"]},
    {"id": "combined_repeat_vs_spelling", "text": "Это это превет.", "explicitly_enabled_rules": [], "coverage": ["java_rule", "spelling", "multiple_findings"]},
    {"id": "combined_yo_default_off", "text": "Ежик и елка.", "explicitly_enabled_rules": [], "coverage": ["default_off", "spelling"]},
    {"id": "combined_yo_explicitly_enabled", "text": "Ежик и елка.", "explicitly_enabled_rules": ["MORFOLOGIK_RULE_RU_RU_YO"], "coverage": ["default_off", "explicit_enablement", "spelling", "multiple_findings"]},
    {"id": "combined_repeat_rules_default_off", "text": "Повтор слов в повтор предложении.", "explicitly_enabled_rules": [], "coverage": ["default_off"]},
    {"id": "combined_repeat_rules_enabled", "text": "Повтор слов в повтор предложении.", "explicitly_enabled_rules": ["RU_WORD_REPEAT"], "coverage": ["default_off", "explicit_enablement"]},
    {"id": "combined_root_repeat_enabled", "text": "Абрикос рос в саду. У меня на столе стоит абрикосный сок.", "explicitly_enabled_rules": ["RU_WORD_ROOT_REPEAT"], "coverage": ["default_off", "explicit_enablement"]},
    {"id": "combined_coherency_and_spelling", "text": "Он блогер. Другой блоггер превет.", "explicitly_enabled_rules": [], "coverage": ["java_rule", "spelling", "multiple_findings"]},
    {"id": "combined_filter_rule", "text": "Сегодня на ужин жареная на масле картошка.", "explicitly_enabled_rules": [], "coverage": ["xml", "filter", "spelling"]},
    {"id": "combined_xml_and_spelling", "text": "Ученик решил задать тест учителю, но каждя задача сложна.", "explicitly_enabled_rules": [], "coverage": ["xml", "spelling", "multiple_findings", "ordering"]},
    {"id": "combined_dash_priority_with_spelling", "text": "из—за превет", "explicitly_enabled_rules": [], "coverage": ["java_rule", "priority", "spelling", "same_offset"]},
    {"id": "combined_non_bmp_offsets", "text": "😀 Раз каждя два.", "explicitly_enabled_rules": [], "coverage": ["non_bmp", "spelling", "offsets"]},
]


def _decode(value: str) -> str:
    return base64.b64decode(value).decode("utf-8") if value else ""


def _config_arg(config: dict[str, Any]) -> str:
    return ";".join(
        f"{key}={str(value).lower() if isinstance(value, bool) else value}"
        for key, value in sorted(config.items())
    )


def _run(jar: Path, *args: str) -> str:
    proc = subprocess.run(
        ["java", "-Dfile.encoding=UTF-8", "-cp", f"{JAVA_SOURCE.parent}{os.pathsep}{jar}",
         "JavaRulesOracle0012", *args],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    return proc.stdout


def _probe(
    jar: Path,
    rule_id: str,
    text: str,
    config: dict[str, Any] | None = None,
    *,
    mode: str = "single",
    enabled: list[str] | None = None,
) -> list[dict[str, Any]]:
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    config_encoded = base64.b64encode(_config_arg(config or {}).encode("utf-8")).decode("ascii")
    command = {"single": "--check", "combined": "--combined", "combined_raw": "--combined-raw"}[mode]
    selector = rule_id if mode == "single" else ",".join(enabled or [])
    stdout = _run(jar, command, selector, encoded, config_encoded)
    mapper = Utf16CodePointMapper(text)
    findings = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        fields.extend([""] * (9 - len(fields)))
        start16, end16 = int(fields[0]), int(fields[1])
        suggestions_raw = _decode(fields[7])
        start, end = mapper.utf16_to_codepoint(start16), mapper.utf16_to_codepoint(end16)
        findings.append({
            "rule_id": fields[2],
            "category_id": fields[3],
            "category_name": _decode(fields[4]),
            "message": _decode(fields[5]),
            "short_message": _decode(fields[6]),
            "suggestions": suggestions_raw.split("\u0000") if suggestions_raw else [],
            "url": _decode(fields[8]) or None,
            "from_utf16": start16,
            "to_utf16": end16,
            "from": start,
            "to": end,
            "source_slice": text[start:end],
        })
    return findings


def _probe_speller(jar: Path, rule_id: str, word: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    encoded = base64.b64encode(word.encode("utf-8")).decode("ascii")
    config_encoded = base64.b64encode(_config_arg(config or {}).encode("utf-8")).decode("ascii")
    stdout = _run(jar, "--spell", rule_id, encoded, config_encoded).rstrip("\r\n")
    fields = stdout.split("\t")
    fields.extend([""] * (2 - len(fields)))
    misspelled, suggestions_b64 = fields[0], fields[1]
    suggestions_raw = _decode(suggestions_b64)
    return {
        "misspelled": misspelled == "true",
        "suggestions": suggestions_raw.split("\u0000") if suggestions_raw else [],
    }


def _signature(case: dict[str, Any]) -> str:
    payload = {
        key: case.get(key, [] if key in ("raw_rule_ids", "explicitly_enabled_rules", "explicitly_disabled_rules") else "")
        for key in (
            "execution_mode", "rule_class", "rule_id", "text", "explicitly_enabled",
            "explicitly_enabled_rules", "explicitly_disabled_rules", "config", "raw_rule_ids",
        )
    }
    payload["config"] = case["config"]
    payload["explicitly_enabled"] = case["explicitly_enabled"]
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


def _validate_speller_coverage(case: dict[str, Any]) -> None:
    coverage = set(case["coverage"])
    expected = case["expected"]
    if "positive" in coverage and "negative" in coverage:
        raise ValueError(f"{case['id']}: coverage cannot be both positive and negative")
    if "positive" in coverage and not expected["misspelled"]:
        raise ValueError(f"{case['id']}: positive coverage requires a misspelled Java verdict")
    if "negative" in coverage and expected["misspelled"]:
        raise ValueError(f"{case['id']}: negative coverage requires a correct Java verdict")
    if "several_suggestions" in coverage and len(expected["suggestions"]) < 2:
        raise ValueError(f"{case['id']}: several_suggestions requires at least two Java suggestions")
    if "no_suggestions" in coverage and expected["suggestions"]:
        raise ValueError(f"{case['id']}: no_suggestions requires an empty Java suggestion list")


def _write(path: Path, cases: list[dict[str, Any]], build_id: str) -> None:
    data = {
        "metadata": {
            "schema_version": "1.0.0",
            "task": "0012",
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": build_id,
            "oracle_generated": True,
            "case_count": len(cases),
        },
        "cases": cases,
    }
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def generate_spelling(path: Path, jar: Path, build_id: str) -> None:
    compiled = []
    for raw_case in SPELLING_DIRECT_CASES:
        rule_id = RULES[raw_case["rule_class"]]
        case = {
            "id": raw_case["id"],
            "rule_class": raw_case["rule_class"],
            "rule_id": rule_id,
            "text": raw_case["text"],
            "execution_mode": "direct_speller",
            "explicitly_enabled": True,
            "explicitly_enabled_rules": [],
            "explicitly_disabled_rules": [],
            "config": raw_case["config"],
            "coverage": raw_case["coverage"],
            "expected": _probe_speller(jar, rule_id, raw_case["text"], raw_case["config"]),
        }
        case["finding_count"] = 1 if case["expected"]["misspelled"] else 0
        _validate_speller_coverage(case)
        case["semantic_signature"] = _signature(case)
        compiled.append(case)
    for raw_case in SPELLING_RULE_CASES:
        rule_id = RULES[raw_case["rule_class"]]
        case = {
            "id": raw_case["id"],
            "rule_class": raw_case["rule_class"],
            "rule_id": rule_id,
            "text": raw_case["text"],
            "execution_mode": "single_rule",
            "explicitly_enabled": True,
            "explicitly_enabled_rules": [],
            "explicitly_disabled_rules": [],
            "config": raw_case["config"],
            "coverage": raw_case["coverage"],
            "expected": _probe(jar, rule_id, raw_case["text"], raw_case["config"]),
        }
        case["finding_count"] = len(case["expected"])
        _validate_coverage(case)
        case["semantic_signature"] = _signature(case)
        compiled.append(case)
    _write(path, compiled, build_id)


def generate_rules(path: Path, jar: Path, build_id: str) -> None:
    compiled = []
    for raw_case in RULE_CASES:
        rule_id = RULES[raw_case["rule_class"]]
        case = {
            "id": raw_case["id"],
            "rule_class": raw_case["rule_class"],
            "rule_id": rule_id,
            "text": raw_case["text"],
            "execution_mode": "single_rule",
            "explicitly_enabled": True,
            "explicitly_enabled_rules": [],
            "explicitly_disabled_rules": [],
            "config": raw_case["config"],
            "coverage": raw_case["coverage"],
            "expected": _probe(jar, rule_id, raw_case["text"], raw_case["config"]),
        }
        case["finding_count"] = len(case["expected"])
        _validate_coverage(case)
        case["semantic_signature"] = _signature(case)
        compiled.append(case)
    _write(path, compiled, build_id)


def generate_filter(path: Path, jar: Path, build_id: str) -> None:
    compiled = []
    for raw_case in FILTER_CASES:
        rule_id = FILTER_RULE_IDS[raw_case["id"]]
        case = {
            "id": raw_case["id"],
            "rule_class": raw_case["rule_class"],
            "rule_id": rule_id,
            "text": raw_case["text"],
            "execution_mode": "single_rule",
            "explicitly_enabled": True,
            "explicitly_enabled_rules": [],
            "explicitly_disabled_rules": [],
            "config": raw_case["config"],
            "coverage": raw_case["coverage"],
            "expected": _probe(jar, rule_id, raw_case["text"], raw_case["config"]),
        }
        case["finding_count"] = len(case["expected"])
        _validate_coverage(case)
        case["semantic_signature"] = _signature(case)
        compiled.append(case)
    _write(path, compiled, build_id)


def generate_combined(path: Path, jar: Path, build_id: str) -> None:
    compiled = []
    for raw_case in COMBINED_CASES:
        case = {
            **raw_case,
            "rule_class": "JLanguageTool",
            "rule_id": "*",
            "execution_mode": "combined_pipeline",
            "explicitly_enabled": False,
            "explicitly_disabled_rules": [],
            "config": raw_case.get("config", {}),
            "raw_rule_ids": raw_case.get("raw_rule_ids", []),
        }
        case["pre_overlap_expected"] = _probe(
            jar, "", case["text"], case["config"], mode="combined_raw",
            enabled=case["explicitly_enabled_rules"],
        )
        case["raw_rule_expected"] = {
            rule_id: _probe(jar, rule_id, case["text"], case["config"])
            for rule_id in case["raw_rule_ids"]
        }
        case["expected"] = _probe(
            jar, "", case["text"], case["config"], mode="combined",
            enabled=case["explicitly_enabled_rules"],
        )
        case["finding_count"] = len(case["expected"])
        _validate_coverage(case)
        case["semantic_signature"] = _signature(case)
        compiled.append(case)
    _write(path, compiled, build_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "tests" / "fixtures")
    args = parser.parse_args()
    oracle = JavaLanguageToolOracle()
    identity = oracle.validate_oracle()
    jar = Path(identity["jar_path"])
    subprocess.run(["javac", "-encoding", "UTF-8", "-cp", str(jar), str(JAVA_SOURCE)], check=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    build_id = identity["oracle_build_id"]
    generate_spelling(args.output_dir / "oracle_java_rules_0012_spelling.json", jar, build_id)
    generate_rules(args.output_dir / "oracle_java_rules_0012_rules.json", jar, build_id)
    generate_filter(args.output_dir / "oracle_java_rules_0012_filter.json", jar, build_id)
    generate_combined(args.output_dir / "oracle_java_rules_0012_combined.json", jar, build_id)


if __name__ == "__main__":
    main()
