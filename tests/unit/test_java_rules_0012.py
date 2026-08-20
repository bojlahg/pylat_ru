"""Behavioral tests for the eight Task-0012 Russian rule equivalents."""

from __future__ import annotations

import pytest

from pylat_ru import LanguageToolRU
from pylat_ru.native_rules import (
    RUSSIAN_RULE_CLASSES,
    TASK_0011_RULE_CLASSES,
    TASK_0012_RULE_CLASSES,
    RussianJavaRulesEngine,
    java_hash_set_order,
)
from pylat_ru.spelling import RussianSpeller, RussianYoSpeller, get_default_spelling_rule


TASK_0012_IDS = {
    "MORFOLOGIK_RULE_RU_RU",
    "MORFOLOGIK_RULE_RU_RU_YO",
    "RU_COMPOUNDS",
    "RU_SIMPLE_REPLACE",
    "WORD_REPEAT_RULE",
    "RU_WORD_COHERENCY",
    "RU_WORD_REPEAT",
    "RU_WORD_ROOT_REPEAT",
}


@pytest.fixture(scope="module")
def engine() -> RussianJavaRulesEngine:
    return RussianJavaRulesEngine()


def test_full_registration_surface_matches_pinned_order(engine: RussianJavaRulesEngine) -> None:
    assert len(RUSSIAN_RULE_CLASSES) == 23
    assert len(TASK_0011_RULE_CLASSES) == 15
    assert len(TASK_0012_RULE_CLASSES) == 8
    assert set(TASK_0011_RULE_CLASSES) | set(TASK_0012_RULE_CLASSES) == set(RUSSIAN_RULE_CLASSES)
    assert [rule.rule_id for rule in engine.rules] == [
        "COMMA_PARENTHESIS_WHITESPACE",
        "UPPERCASE_SENTENCE_START",
        "MORFOLOGIK_RULE_RU_RU",
        "WHITESPACE_RULE",
        "SENTENCE_WHITESPACE",
        "WHITESPACE_PARAGRAPH",
        "WHITESPACE_PARAGRAPH_BEGIN",
        "TOO_LONG_SENTENCE",
        "TOO_LONG_PARAGRAPH",
        "PARAGRAPH_REPEAT_BEGINNING_RULE",
        "FILLER_WORDS_RU",
        "PUNCTUATION_PARAGRAPH_END2",
        "MORFOLOGIK_RULE_RU_RU_YO",
        "RU_UNPAIRED_BRACKETS",
        "RU_COMPOUNDS",
        "RU_SIMPLE_REPLACE",
        "WORD_REPEAT_RULE",
        "RU_WORD_COHERENCY",
        "RU_WORD_REPEAT",
        "RU_WORD_ROOT_REPEAT",
        "RU_VERB_CONJUGATION",
        "RU_DASH_RULE",
        "RU_SPECIFIC_CASE",
    ]


def test_task_0012_default_states_and_priorities(engine: RussianJavaRulesEngine) -> None:
    default_off = {rule.rule_id for rule in engine.rules if rule.default_off}
    assert default_off & TASK_0012_IDS == {
        "MORFOLOGIK_RULE_RU_RU_YO", "RU_WORD_REPEAT", "RU_WORD_ROOT_REPEAT",
    }
    assert engine.get_rule("RU_COMPOUNDS").priority == 11
    # Russian.java's override keys do not bind these four registered IDs.
    for rule_id in ("MORFOLOGIK_RULE_RU_RU", "MORFOLOGIK_RULE_RU_RU_YO",
                    "RU_SIMPLE_REPLACE", "RU_WORD_ROOT_REPEAT"):
        assert engine.get_rule(rule_id).priority == 0


def test_default_off_rules_only_run_when_explicitly_enabled() -> None:
    engine = RussianJavaRulesEngine()
    text = "Ежик и елка."
    assert engine.check_rule(text, "MORFOLOGIK_RULE_RU_RU_YO")
    assert not any(m.rule_id == "MORFOLOGIK_RULE_RU_RU_YO" for m in engine.check(text))
    engine.enable_rule("MORFOLOGIK_RULE_RU_RU_YO")
    assert any(m.rule_id == "MORFOLOGIK_RULE_RU_RU_YO" for m in engine.check(text))
    engine.disable_rule("MORFOLOGIK_RULE_RU_RU_YO")
    assert not any(m.rule_id == "MORFOLOGIK_RULE_RU_RU_YO" for m in engine.check(text))


def test_speller_user_config_surface() -> None:
    text = "The quick brown fox."
    assert not RussianJavaRulesEngine().check_rule(text, "MORFOLOGIK_RULE_RU_RU")
    configured = RussianJavaRulesEngine({"MORFOLOGIK_RULE_RU_RU": {"conf_ru_Value": 1}})
    assert len(configured.check_rule(text, "MORFOLOGIK_RULE_RU_RU")) == 4
    # Values outside the RuleOption(0, 1) UI bounds are accepted at runtime and
    # behave like every value other than 1, exactly as in the pinned Java rule.
    for value in (-1, 2):
        engine = RussianJavaRulesEngine({"MORFOLOGIK_RULE_RU_RU": {"conf_ru_Value": value}})
        assert not engine.check_rule(text, "MORFOLOGIK_RULE_RU_RU")


def test_unknown_rule_configuration_keys_fail_explicitly() -> None:
    with pytest.raises(KeyError):
        RussianJavaRulesEngine({"NO_SUCH_RULE": {"conf_ru_Value": 1}})
    with pytest.raises(KeyError):
        RussianJavaRulesEngine({"MORFOLOGIK_RULE_RU_RU": {"unknownOption": 1}})
    with pytest.raises(TypeError):
        RussianJavaRulesEngine({"MORFOLOGIK_RULE_RU_RU": {"conf_ru_Value": "1"}})


def test_configuration_does_not_leak_between_rules() -> None:
    engine = RussianJavaRulesEngine({"MORFOLOGIK_RULE_RU_RU": {"conf_ru_Value": 1}})
    assert not engine.check_rule("The quick brown fox.", "MORFOLOGIK_RULE_RU_RU_YO")


def test_nosuggest_words_are_filtered_from_suggestions() -> None:
    speller = RussianSpeller()
    for word in ("блоггер", "дрочим", "анальный", "орочем"):
        assert all(
            word not in [s.lower() for s in speller.calc_speller_suggestions(probe)]
            for probe in (word[:-1], word + "а")
        )
    yo = RussianYoSpeller()
    assert "елка" not in [s.lower() for s in yo.calc_speller_suggestions("елкаа")]


def test_prohibited_and_ignored_words() -> None:
    speller = RussianSpeller()
    # prohibit.txt marks a word as an error even when the dictionary accepts it
    assert speller.is_prohibited("Тайланд")
    assert speller.is_misspelled("Тайланд") is False
    assert RussianJavaRulesEngine().check_rule("Тайланд красив.", "MORFOLOGIK_RULE_RU_RU")
    # ignore.txt / spelling.txt words are skipped by the rule but not by the speller
    assert speller.is_ignored_no_case("что-что")
    assert not RussianJavaRulesEngine().check_rule("что-что тут.", "MORFOLOGIK_RULE_RU_RU")


def test_default_spelling_rule_is_the_ordinary_speller() -> None:
    rule = get_default_spelling_rule()
    assert isinstance(rule, RussianSpeller)
    assert rule.rule_id == "MORFOLOGIK_RULE_RU_RU"
    assert rule.conf_ru_value == 0
    assert get_default_spelling_rule() is rule


def test_compound_rule_suggestion_forms() -> None:
    engine = RussianJavaRulesEngine()
    hyphen = engine.check_rule("Ростов на Дону", "RU_COMPOUNDS")
    assert [m.suggestions for m in hyphen] == [("Ростов-на-Дону",)]
    assert hyphen[0].message == "Эти слова должны быть написаны через дефис."
    joined = engine.check_rule("кругло суточный", "RU_COMPOUNDS")
    assert [m.suggestions for m in joined] == [("круглосуточный",)]
    assert joined[0].message == "Эти слова должны быть написаны слитно."
    assert not engine.check_rule("естественно-научный", "RU_COMPOUNDS")


def test_simple_replace_rule_message_and_case_adaptation() -> None:
    engine = RussianJavaRulesEngine()
    match = engine.check_rule("Книга была порвата.", "RU_SIMPLE_REPLACE")[0]
    assert match.suggestions == ("порвана",)
    assert match.short_message == "Ошибка?"
    assert "<suggestion>порвана</suggestion>" in match.message
    upper = engine.check_rule("ЭКСПРЕССО – крепкий кофе.", "RU_SIMPLE_REPLACE")[0]
    assert upper.suggestions == ("ЭСПРЕССО",)


def test_repeat_and_coherency_rules() -> None:
    engine = RussianJavaRulesEngine()
    simple = engine.check_rule("Это это тест.", "WORD_REPEAT_RULE")[0]
    assert simple.suggestions == ("Это",)
    assert simple.short_message == "Повтор слова"
    assert not engine.check_rule("Он и и она.", "WORD_REPEAT_RULE")

    coherency = engine.check_rule(
        "По шкале Цельсия абсолютному нулю соответствует температура −273,15 °C "
        "или ноль по шкале Кельвина.",
        "RU_WORD_COHERENCY",
    )
    assert len(coherency) == 1
    assert "не следует использовать одновременно" in coherency[0].message

    advanced = engine.check_rule("Повтор слов в повтор предложении.", "RU_WORD_REPEAT")
    assert len(advanced) == 1
    assert advanced[0].message == "Повтор слов в предложении"

    root = engine.check_rule(
        "Абрикос рос в саду. У меня на столе стоит абрикосный сок.", "RU_WORD_ROOT_REPEAT"
    )
    assert len(root) == 1
    assert "однокоренные слова" in root[0].message


def test_java_hash_set_order_is_deterministic_bucket_order() -> None:
    # java.util.HashSet iteration order decides which base form AbstractWordCoherencyRule
    # inspects first; it must be reproduced, not approximated by insertion order.
    assert java_hash_set_order(["b", "a"]) == java_hash_set_order(["a", "b"])
    assert java_hash_set_order([None, "a"])[0] is None
    assert java_hash_set_order(["a", "a", "b"]) == java_hash_set_order(["a", "b"])
    assert len(java_hash_set_order([str(i) for i in range(40)])) == 40


def test_public_api_runs_all_rules_and_honors_explicit_state() -> None:
    tool = LanguageToolRU()
    matches = tool.check("Все счастливые семьи похожи друг на друга, каждя несчастливая семья.")
    assert [m.rule_id for m in matches] == ["MORFOLOGIK_RULE_RU_RU"]
    assert matches[0].replacements[:3] == ("дождя", "кадя", "каждая")

    disabled = LanguageToolRU(disabled_rules=["MORFOLOGIK_RULE_RU_RU"])
    assert not [
        m for m in disabled.check("каждя несчастливая семья.")
        if m.rule_id == "MORFOLOGIK_RULE_RU_RU"
    ]
