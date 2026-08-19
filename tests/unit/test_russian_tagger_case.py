"""Unit tests for StringTools case methods and BaseTagger case fallback semantics."""

from pylat_ru.analysis import AnalyzedToken
from pylat_ru.tagging.russian import RussianTagger
from pylat_ru.tagging.string_tools import (
    change_first_char_case,
    is_all_uppercase,
    is_capitalized_word,
    is_mixed_case,
    is_not_all_lowercase,
    lowercase_first_char,
    uppercase_first_char,
)


def test_string_tools_is_all_uppercase():
    """Verify StringTools.isAllUppercase semantics."""
    assert is_all_uppercase("СЛОВО") is True
    assert is_all_uppercase("СЛОВО!") is True
    assert is_all_uppercase("123") is True
    assert is_all_uppercase("") is True
    assert is_all_uppercase("Слово") is False
    assert is_all_uppercase("слово") is False
    assert is_all_uppercase("мИкс") is False


def test_string_tools_is_not_all_lowercase():
    """Verify StringTools.isNotAllLowercase semantics."""
    assert is_not_all_lowercase("СЛОВО") is True
    assert is_not_all_lowercase("Слово") is True
    assert is_not_all_lowercase("мИкс") is True
    assert is_not_all_lowercase("слово") is False
    assert is_not_all_lowercase("123") is False
    assert is_not_all_lowercase("") is False


def test_string_tools_is_capitalized_word():
    """Verify StringTools.isCapitalizedWord semantics."""
    assert is_capitalized_word("Слово") is True
    assert is_capitalized_word("А") is True
    assert is_capitalized_word("СЛОВО") is False
    assert is_capitalized_word("слово") is False
    assert is_capitalized_word("мИкс") is False
    assert is_capitalized_word("СлоВо") is False
    assert is_capitalized_word("") is False
    assert is_capitalized_word("123") is False


def test_string_tools_is_mixed_case():
    """Verify StringTools.isMixedCase semantics."""
    assert is_mixed_case("слово") is False
    assert is_mixed_case("Слово") is False
    assert is_mixed_case("СЛОВО") is False
    assert is_mixed_case("123") is False
    assert is_mixed_case("") is False

    assert is_mixed_case("мИкс") is True
    assert is_mixed_case("СлоВо") is True
    assert is_mixed_case("iPod") is True
    assert is_mixed_case("eBay") is True


def test_string_tools_change_first_char_case():
    """Verify changeFirstCharCase / uppercaseFirstChar / lowercaseFirstChar forward scanning."""
    assert uppercase_first_char("слово") == "Слово"
    assert lowercase_first_char("Слово") == "слово"
    assert uppercase_first_char("«слово»") == "«Слово»"
    assert lowercase_first_char("«Слово»") == "«слово»"
    assert uppercase_first_char("(слово)") == "(Слово)"
    assert uppercase_first_char("123слово") == "123слово"
    assert uppercase_first_char("") == ""
    assert uppercase_first_char("а") == "А"
    assert lowercase_first_char("А") == "а"


def test_basetagger_case_fallback_order():
    """Verify BaseTagger case lookup sequence on RussianTagger."""
    tagger = RussianTagger()

    # 1. Lowercase word: returns exact lowercase readings
    readings_lower = tagger.tag_word("дом")
    assert len(readings_lower.readings) == 2
    assert all(r.token == "дом" for r in readings_lower.readings)
    assert any(r.lemma == "дом" and r.pos_tag == "NN:Inanim:Masc:Sin:Nom" for r in readings_lower.readings)

    # 2. Capitalized word: returns exact capitalized readings + lowercase readings
    readings_cap = tagger.tag_word("Дом")
    assert len(readings_cap.readings) == 2
    assert all(r.token == "Дом" for r in readings_cap.readings)
    assert any(r.lemma == "дом" and r.pos_tag == "NN:Inanim:Masc:Sin:Nom" for r in readings_cap.readings)

    # 3. All uppercase word: returns exact uppercase readings + lowercase readings
    readings_upper = tagger.tag_word("ДОМ")
    assert len(readings_upper.readings) == 2
    assert all(r.token == "ДОМ" for r in readings_upper.readings)

    # 4. Mixed case: returns exact only (does not append lower readings if exact is empty)
    readings_mixed = tagger.tag_word("дОм")
    assert readings_mixed.is_pos_tag_unknown is True
    assert readings_mixed.readings[0] == AnalyzedToken(token="дОм", lemma=None, pos_tag=None)

    # 5. Lowercase word whose only reading exists under capitalized form in manual additions (Абдуллаевы)
    readings_abbr = tagger.tag_word("абдуллаев")
    assert any(r.lemma == "абдуллаев" and "NN:Fam" in (r.pos_tag or "") for r in readings_abbr.readings)

    # 6. Completely unknown word returns exactly one null reading
    readings_unknown = tagger.tag_word("несуществующеесловоxyz")
    assert len(readings_unknown.readings) == 1
    assert readings_unknown.is_pos_tag_unknown is True
    assert readings_unknown.readings[0] == AnalyzedToken(
        token="несуществующеесловоxyz", lemma=None, pos_tag=None
    )
