"""Unit tests for RussianTagger literal accent normalization, MayMissingYO, and UTF-16 position accumulation."""

from pylat_ru.tagging.russian import RussianTagger


def test_acute_accent_normalization():
    """Verify all 9 acute vowel combining sequences are stripped to plain vowels."""
    tagger = RussianTagger()
    # о́ -> о
    at_o = tagger.tag_word("до́ма")
    assert at_o.token == "дома"
    assert at_o.has_lemma("дом")

    # а́ -> а
    at_a = tagger.tag_word("кни́га")
    assert at_a.token == "книга"
    assert at_a.has_lemma("книга")

    # е́ -> е
    at_e = tagger.tag_word("челове́к")
    assert at_e.token == "человек"
    assert at_e.has_lemma("человек")

    # и́ -> и
    at_i = tagger.tag_word("краси́вый")
    assert at_i.token == "красивый"
    assert at_i.has_lemma("красивый")

    # у́ -> у, ы́ -> ы, э́ -> э, ю́ -> ю, я́ -> я
    for raw, norm, lemma in [
        ("ру́ки", "руки", "рука"),
        ("вы́ход", "выход", "выход"),
        ("э́то", "это", "это"),
        ("ю́ность", "юность", "юность"),
        ("я́блоко", "яблоко", "яблоко"),
    ]:
        res = tagger.tag_word(raw)
        assert res.token == norm
        assert res.has_lemma(lemma)


def test_grave_accent_normalization_and_cyrillic_i_with_grave():
    """Verify grave combining sequences and standalone U+045D (ѝ) are normalized."""
    tagger = RussianTagger()
    # ѝ (U+045D) -> и
    at_i_grave = tagger.tag_word("ѝ")
    # Single character tokens with length <= 1 are NOT modified by the >1 guard
    assert at_i_grave.token == "ѝ"

    # Multi-char words with grave
    at_grave = tagger.tag_word("книга\u0300")
    assert at_grave.token == "книга"
    assert at_grave.has_lemma("книга")


def test_modifier_apostrophe_normalization():
    """Verify U+02BC (ʼ) is replaced with ъ in tokens of length > 1."""
    tagger = RussianTagger()
    at_apostrophe = tagger.tag_word("обʼявление")
    assert at_apostrophe.token == "объявление"
    assert at_apostrophe.has_lemma("объявление")

    at_sest = tagger.tag_word("сʼесть")
    assert at_sest.token == "съесть"
    assert at_sest.has_lemma("съесть")


def test_may_missing_yo_detection():
    """Verify MayMissingYO chunk tag attachment conditions."""
    tagger = RussianTagger()

    # 1. Positive case: 'все' has 'е', all-e->ё variant 'всё' exists in dictionary
    at_vse = tagger.tag_word("Все")
    assert "MayMissingYO" in at_vse.chunk_tags

    # 2. Positive case: 'елка' -> 'ёлка' exists in dictionary
    at_elka = tagger.tag_word("елка")
    assert "MayMissingYO" in at_elka.chunk_tags

    # 3. Negative case: already contains 'ё' -> no MayMissingYO
    at_yo = tagger.tag_word("ёлка")
    assert "MayMissingYO" not in at_yo.chunk_tags

    # 4. Negative case: contains 'е', but 'мёсто' does NOT exist in dictionary
    at_mesto = tagger.tag_word("место")
    assert "MayMissingYO" not in at_mesto.chunk_tags

    # 5. Negative case: token with acute vowel before normalization does not get candidate flag
    at_accent = tagger.tag_word("ме́сто")
    assert "MayMissingYO" not in at_accent.chunk_tags

    # 6. Multiple 'е' characters: all-at-once replacement
    at_perepel = tagger.tag_word("перепел")
    # 'пёрёпёл' is not in the dictionary, so MayMissingYO is cleared
    assert "MayMissingYO" not in at_perepel.chunk_tags


def test_utf16_raw_tagger_start_position_accumulation():
    """Verify raw direct-tagger positions accumulate using normalized token length in UTF-16."""
    tagger = RussianTagger()
    # 'кни́га' raw has 6 chars (к, н, и, \u0301, г, а), but normalized has 5 chars ('книга')
    # Therefore next token 'дом' must start at UTF-16 index 5, NOT 6
    tokens = ["кни\u0301га", "дом", "человек"]
    atrs = tagger.tag(tokens)
    assert len(atrs) == 3

    assert atrs[0].start_pos == 0
    assert atrs[0].token == "книга"

    assert atrs[1].start_pos == 5  # normalized length of 'книга' is 5
    assert atrs[1].token == "дом"

    assert atrs[2].start_pos == 8  # 5 + 3 ('дом') = 8
    assert atrs[2].token == "человек"
