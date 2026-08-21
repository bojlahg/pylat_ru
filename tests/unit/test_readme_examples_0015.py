from __future__ import annotations

from pylat_ru import LanguageToolRU, LEVEL_DEFAULT, LEVEL_PICKY, RuleMatch


def test_basic_readme_example() -> None:
    matches = LanguageToolRU().check("Ученик решил задать тест учителю.")
    assert any(m.rule_id == "zadat_test" for m in matches)
    assert all(isinstance(m, RuleMatch) for m in matches)


def test_default_picky_and_config_readme_example() -> None:
    tool = LanguageToolRU(rule_config={"TOO_LONG_SENTENCE": {"maxWords": 4}})
    text = "Один два три четыре пять."
    assert "TOO_LONG_SENTENCE" not in {m.rule_id for m in tool.check(text, LEVEL_DEFAULT)}
    assert "TOO_LONG_SENTENCE" in {m.rule_id for m in tool.check(text, LEVEL_PICKY)}


def test_enable_disable_readme_example() -> None:
    enabled = LanguageToolRU(enabled_rules=["MORFOLOGIK_RULE_RU_RU_YO"])
    assert any(m.rule_id == "MORFOLOGIK_RULE_RU_RU_YO" for m in enabled.check("Ежик и елка."))
    disabled = LanguageToolRU(disabled_rules=["zadat_test"])
    assert not any(m.rule_id == "zadat_test" for m in disabled.check("Ученик решил задать тест учителю."))


def test_non_bmp_coordinate_example() -> None:
    text = "😀 Ученик решил задать тест учителю."
    match = next(m for m in LanguageToolRU().check(text) if m.rule_id == "zadat_test")
    assert text[match.offset:match.offset + match.length] == "задать тест"
    assert match.utf16_offset == match.offset + 1
