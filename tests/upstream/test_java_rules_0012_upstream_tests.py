"""Direct translations of the pinned upstream JUnit tests for the Task-0012 rules.

Each test mirrors one ``@Test`` method of the corresponding LanguageTool 6.8
Russian test class, assertion for assertion:

* ``MorfologikRussianSpellerRuleTest#testMorfologikSpeller``
* ``MorfologikRussianYOSpellerRuleTest#testMorfologikSpeller``
* ``RussianCompoundRuleTest#testRule``
* ``RussianSimpleReplaceRuleTest#testRule``
* ``RussianWordCoherencyRuleTest#testRule``/``#testCallIndependence``/``#testRuleCompleteTexts``
* ``RussianWordRepeatRuleTest#testRule``

``RussianSimpleWordRepeatRule`` and ``RussianWordRootRepeatRule`` have no
dedicated upstream test at the pin; they are covered by the generated Java
oracle fixtures instead.
"""

from __future__ import annotations

import pytest

from pylat_ru import LanguageToolRU
from pylat_ru.native_rules import RussianJavaRulesEngine


@pytest.fixture(scope="module")
def engine() -> RussianJavaRulesEngine:
    return RussianJavaRulesEngine()


def _count(engine: RussianJavaRulesEngine, rule_id: str, text: str) -> int:
    return len(engine.check_rule(text, rule_id))


# --- MorfologikRussianSpellerRuleTest --------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("русский", 0),
        ("ёжик", 0),
        ("ежик", 0),
        ("юго-зпдный", 1),
        ("северо-восточный", 0),
        ("Ростов-на-Дону", 0),
        ("Ростов-на-дону", 1),
    ],
)
def test_morfologik_russian_speller_rule(engine: RussianJavaRulesEngine, text: str, expected: int) -> None:
    assert _count(engine, "MORFOLOGIK_RULE_RU_RU", text) == expected


# --- MorfologikRussianYOSpellerRuleTest ------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("русский", 0),
        ("ёжик", 0),
        ("ежик", 1),
        ("юго-зпдный", 1),
        ("северо-восточный", 0),
        ("Ростов-на-Дону", 0),
    ],
)
def test_morfologik_russian_yo_speller_rule(engine: RussianJavaRulesEngine, text: str, expected: int) -> None:
    assert _count(engine, "MORFOLOGIK_RULE_RU_RU_YO", text) == expected


# --- RussianCompoundRuleTest -----------------------------------------------

@pytest.mark.parametrize(
    "expected,text,suggestion",
    [
        (0, "Он вышел из-за дома.", None),
        (0, "Разработка ПО за идею.", None),
        (0, "естественно-научный", None),
        (1, "из за", "из-за"),
        (1, "по за", "по-за"),
        (1, "нет нет из за да да", None),
        (1, "Ростов на Дону", "Ростов-на-Дону"),
        (1, "Ростов на Дону — крупнейший город на юге Российской Федерации, административный "
            "центр Южного федерального округа и Ростовской области.", None),
        (1, "кругло суточный", "круглосуточный"),
        (0, "Ростов на дону", None),
        (0, "Ведь сейчас в лос Анджелесе", None),
        (1, "Ростов-на Дону", "Ростов-на-Дону"),
        (0, "во-первых", None),
        (1, "во первых", "во-первых"),
        (1, "Лос Анджелес", "Лос-Анджелес"),
        (1, "Ведь сейчас в Лос Анджелесе", None),
        (1, "Ведь сейчас в Лос Анджелесе хорошая погода.", None),
        (1, "Во первых, мы были довольно высоко над уровнем моря.", None),
        (1, "Мы, во первых, были довольно высоко над уровнем моря.", None),
    ],
)
def test_russian_compound_rule(
    engine: RussianJavaRulesEngine, expected: int, text: str, suggestion: str | None
) -> None:
    matches = engine.check_rule(text, "RU_COMPOUNDS")
    assert len(matches) == expected
    if suggestion is not None:
        assert suggestion in matches[0].suggestions


# --- RussianSimpleReplaceRuleTest ------------------------------------------

def test_russian_simple_replace_rule(engine: RussianJavaRulesEngine) -> None:
    assert _count(engine, "RU_SIMPLE_REPLACE", "Рост кораллов тут самый быстрый,") == 0
    assert _count(engine, "RU_SIMPLE_REPLACE", "Книга была порвана.") == 0
    matches = engine.check_rule("Книга была порвата.", "RU_SIMPLE_REPLACE")
    assert len(matches) == 1
    assert len(matches[0].suggestions) == 1
    assert matches[0].suggestions[0] == "порвана"


# --- RussianWordCoherencyRuleTest ------------------------------------------

def test_russian_word_coherency_rule(engine: RussianJavaRulesEngine) -> None:
    good = "По шкале Цельсия абсолютному нулю соответствует температура −273,15 °C."
    bad = (
        "По шкале Цельсия абсолютному нулю соответствует температура −273,15 °C "
        "или ноль по шкале Кельвина."
    )
    assert _count(engine, "RU_WORD_COHERENCY", good) == 0
    assert _count(engine, "RU_WORD_COHERENCY", good) == 0
    assert _count(engine, "RU_WORD_COHERENCY", bad) == 1


def test_russian_word_coherency_call_independence(engine: RussianJavaRulesEngine) -> None:
    # Each call starts with an empty "should not appear" map.
    assert _count(engine, "RU_WORD_COHERENCY", "Абсолютный нуль.") == 0
    assert _count(engine, "RU_WORD_COHERENCY", "Ноль по шкале Кельвина.") == 0


def test_russian_word_coherency_complete_texts() -> None:
    tool = LanguageToolRU()
    assert len(tool.check(
        "По шкале Цельсия абсолютному нулю соответствует температура −273,15 °C "
        "или нуль по шкале Кельвина."
    )) == 0
    assert len(tool.check(
        "По шкале Цельсия абсолютному нулю соответствует температура −273,15 °C "
        "или ноль по шкале Кельвина."
    )) == 1
    # cross-paragraph check
    assert len(tool.check("Абсолютный нуль.\n\nСовсем недостижим. И ноль по шкале Кельвина.")) == 1


# --- RussianWordRepeatRuleTest ---------------------------------------------

def test_russian_word_repeat_rule(engine: RussianJavaRulesEngine) -> None:
    assert _count(engine, "RU_WORD_REPEAT", "Повтор слов в предложении.") == 0
    assert _count(engine, "RU_WORD_REPEAT", "Повтор слов в повтор предложении.") == 1
