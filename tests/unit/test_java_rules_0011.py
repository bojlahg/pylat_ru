"""Inventory, defaults, integration, and translated upstream Task-0011 tests."""

from __future__ import annotations

import unicodedata

import pytest

from pylat_ru import LanguageToolRU
from pylat_ru.native_rules import (
    RussianJavaRulesEngine,
    TASK_0011_RULE_CLASSES,
    _is_long_sentence_word,
)
from tools.differential_corpus_0014 import (
    CONFIG_CONTROL_WORDS,
    SUPPLEMENTARY_LETTER,
    SUPPLEMENTARY_LONG_SENTENCE_TEXT,
)


EXPECTED_IDS = {
    "COMMA_PARENTHESIS_WHITESPACE",
    "UPPERCASE_SENTENCE_START",
    "WHITESPACE_RULE",
    "SENTENCE_WHITESPACE",
    "WHITESPACE_PARAGRAPH",
    "WHITESPACE_PARAGRAPH_BEGIN",
    "TOO_LONG_SENTENCE",
    "TOO_LONG_PARAGRAPH",
    "PARAGRAPH_REPEAT_BEGINNING_RULE",
    "FILLER_WORDS_RU",
    "PUNCTUATION_PARAGRAPH_END2",
    "RU_UNPAIRED_BRACKETS",
    "RU_VERB_CONJUGATION",
    "RU_DASH_RULE",
    "RU_SPECIFIC_CASE",
}


def test_long_sentence_uses_pinned_utf16_first_code_unit_semantics() -> None:
    assert unicodedata.category(SUPPLEMENTARY_LETTER).startswith("L")
    assert _is_long_sentence_word("Слово")
    assert not _is_long_sentence_word("1слово")
    assert not _is_long_sentence_word(".слово")
    assert not _is_long_sentence_word(SUPPLEMENTARY_LETTER + "слово")

    engine = RussianJavaRulesEngine(
        {"TOO_LONG_SENTENCE": {"maxWords": 15}}
    )
    assert not engine.check_rule(
        SUPPLEMENTARY_LONG_SENTENCE_TEXT, "TOO_LONG_SENTENCE"
    )
    bmp_control = " ".join(CONFIG_CONTROL_WORDS[:16]) + "."
    assert engine.check_rule(bmp_control, "TOO_LONG_SENTENCE")


def test_task_0011_inventory_and_defaults() -> None:
    engine = RussianJavaRulesEngine()
    assert len(TASK_0011_RULE_CLASSES) == 15
    assert {cls.rule_id for cls in TASK_0011_RULE_CLASSES} == EXPECTED_IDS
    # Task 0012 registers the remaining eight rules alongside these fifteen.
    assert EXPECTED_IDS.issubset({rule.rule_id for rule in engine.rules})
    default_off = {
        rule.rule_id
        for rule in engine.rules
        if rule.default_off and rule.rule_id in EXPECTED_IDS
    }
    assert default_off == {
        "WHITESPACE_PARAGRAPH",
        "WHITESPACE_PARAGRAPH_BEGIN",
        "TOO_LONG_PARAGRAPH",
        "PARAGRAPH_REPEAT_BEGINNING_RULE",
        "FILLER_WORDS_RU",
        "PUNCTUATION_PARAGRAPH_END2",
    }
    assert engine.get_rule("RU_DASH_RULE").priority == 12
    assert engine.get_rule("TOO_LONG_PARAGRAPH").priority == -15
    # These are the effective pinned priorities: Russian.java's differently
    # named override keys do not bind either registered rule ID.
    assert engine.get_rule("RU_SPECIFIC_CASE").priority == 0
    assert engine.get_rule("PUNCTUATION_PARAGRAPH_END2").priority == 0


def test_explicit_enablement_and_disabling() -> None:
    engine = RussianJavaRulesEngine()
    assert engine.check_rule("ах слово", "FILLER_WORDS_RU")
    assert not engine.is_rule_enabled("FILLER_WORDS_RU")
    engine.enable_rule("FILLER_WORDS_RU")
    assert any(m.rule_id == "FILLER_WORDS_RU" for m in engine.check("ах слово"))
    engine.disable_rule("FILLER_WORDS_RU")
    assert not any(m.rule_id == "FILLER_WORDS_RU" for m in engine.check("ах слово"))


def test_public_user_config_surface_and_pinned_option_ranges() -> None:
    tool = LanguageToolRU(
        enabled_rules=["FILLER_WORDS_RU", "TOO_LONG_PARAGRAPH"],
        rule_config={
            "TOO_LONG_SENTENCE": {"maxWords": 6},
            "TOO_LONG_PARAGRAPH": {"maxWords": 6},
            "FILLER_WORDS_RU": {"minPercent": 40, "excludeDirectSpeech": True},
        },
    )
    # TOO_LONG_SENTENCE carries the ``picky`` tag, and pinned
    # ``JLanguageTool.check(text)`` runs at ``Level.DEFAULT``, which drops every
    # picky-tagged match before grouping.  Task 0014 confirmed against the trusted
    # oracle that the pinned pipeline returns no match at all for this text, so the
    # configured threshold is asserted on the rule surface, where it is observable.
    long_sentence = "Один два три четыре пять шесть семь."
    assert tool.check(long_sentence) == []
    assert any(
        match.rule_id == "TOO_LONG_SENTENCE"
        for match in RussianJavaRulesEngine({"TOO_LONG_SENTENCE": {"maxWords": 6}}).check(
            long_sentence
        )
    )
    assert not any(match.rule_id == "FILLER_WORDS_RU" for match in tool.check("ах слово слово"))
    low_sentence = RussianJavaRulesEngine({"TOO_LONG_SENTENCE": {"maxWords": 4}})
    high_sentence = RussianJavaRulesEngine({"TOO_LONG_SENTENCE": {"maxWords": 101}})
    low_paragraph = RussianJavaRulesEngine({"TOO_LONG_PARAGRAPH": {"maxWords": 4}})
    high_paragraph = RussianJavaRulesEngine({"TOO_LONG_PARAGRAPH": {"maxWords": 301}})
    low_filler = RussianJavaRulesEngine({"FILLER_WORDS_RU": {"minPercent": -1}})
    high_filler = RussianJavaRulesEngine({"FILLER_WORDS_RU": {"minPercent": 101}})
    assert low_sentence.check_rule(" ".join(["слово"] * 5), "TOO_LONG_SENTENCE")
    assert high_sentence.check_rule(" ".join(["слово"] * 102), "TOO_LONG_SENTENCE")
    assert low_paragraph.check_rule(" ".join(["слово"] * 10), "TOO_LONG_PARAGRAPH")
    assert high_paragraph.check_rule(" ".join(["слово"] * 307), "TOO_LONG_PARAGRAPH")
    assert low_filler.check_rule("ах слово", "FILLER_WORDS_RU")
    assert not high_filler.check_rule("ах слово", "FILLER_WORDS_RU")


def test_translated_russian_verb_conjugation_upstream_assertions() -> None:
    engine = RussianJavaRulesEngine()
    good = (
        "Я иду", "Она сидит", "Оно думает", "Они пишут", "Мы думаем", "Ты читаешь",
        "Он творит", "Вы идёте", "Я ходил", "Они ходили", "Мы ходили", "Она ходила",
        "Оно ходило", "Я ходила", "Я пойду", "Она пойдёт", "Оно пойдёт", "Мы пойдём",
        "Ты пойдёшь", "Я согласился на предложение.", "Джек и я согласились",
        "Ты может быть не помнишь.",
    )
    bad = (
        "Я идёт", "Она сидят", "Оно думаешь", "Они идёте", "Мы думаю", "Ты читает",
        "Он творю", "Я ходили", "Они ходил", "Мы ходила", "Она ходил", "Оно ходила",
        "Я ходило", "Я пойдёт", "Она пойдут", "Оно пойдёте", "Мы пойдёшь", "Ты пойду",
        "Мы может поговорить здесь.",
    )
    assert all(not engine.check_rule(text, "RU_VERB_CONJUGATION") for text in good)
    assert all(len(engine.check_rule(text, "RU_VERB_CONJUGATION")) == 1 for text in bad)


def test_translated_dash_specific_case_and_bracket_assertions() -> None:
    engine = RussianJavaRulesEngine()
    assert engine.check_rule("Он вышел из-за забора.", "RU_DASH_RULE") == []
    assert engine.check_rule("Ростов — на — Дону", "RU_DASH_RULE")[0].suggestions == ("Ростов-на-Дону",)
    assert engine.check_rule("Центральный банк РФ", "RU_SPECIFIC_CASE") == []
    assert engine.check_rule("центральный банк РФ", "RU_SPECIFIC_CASE")[0].suggestions == ("Центральный банк РФ",)
    assert engine.check_rule("(О жене и детях не беспокойся).", "RU_UNPAIRED_BRACKETS") == []


def test_combined_public_xml_and_java_rule_pipeline() -> None:
    tool = LanguageToolRU()
    findings = tool.check("Ученик решил задать тест учителю. Не род , а ум.")
    ids = [finding.rule_id for finding in findings]
    assert "zadat_test" in ids
    assert "COMMA_PARENTHESIS_WHITESPACE" in ids
    assert all(finding.source in {"xml_grammar", "java_rule"} for finding in findings)


def test_non_bmp_offsets_and_priority_ordering() -> None:
    engine = RussianJavaRulesEngine()
    findings = engine.check_rule("😀 Раз ,два ,три.", "COMMA_PARENTHESIS_WHITESPACE")
    assert len(findings) == 4
    assert findings[0].from_pos_utf16 == findings[0].from_pos + 1
    assert findings[1].from_pos_utf16 == findings[1].from_pos + 1
    ordered = engine.check("из—за")
    assert [m.rule_id for m in ordered[:2]] == ["RU_DASH_RULE", "UPPERCASE_SENTENCE_START"]
