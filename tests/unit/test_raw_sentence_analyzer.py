"""Unit tests for RussianSentenceAnalyzer raw sentence assembly."""

from __future__ import annotations

import pytest

from pylat_ru.analysis import SENT_END_TAG, SENT_START_TAG
from pylat_ru.sentence_analyzer import RussianSentenceAnalyzer, create_raw_analyzed_sentence


def test_sent_start_and_sent_end_basic():
    """Verify SENT_START pseudo-token and SENT_END reading attachment on last non-whitespace token."""
    analyzer = RussianSentenceAnalyzer.get_instance()
    sent = analyzer.analyze_raw("Солнце светит ярко.")

    tokens = sent.get_tokens()
    assert len(tokens) >= 5  # SENT_START, Солнце, ' ', светит, ' ', ярко, '.'

    # 1. SENT_START
    first = tokens[0]
    assert first.is_sentence_start is True
    assert first.start_pos == 0
    assert len(first.readings) == 1
    assert first.readings[0].pos_tag == SENT_START_TAG
    assert first.readings[0].token == ""

    # 2. SENT_END on last non-whitespace token (period '.')
    last_non_ws = sent.get_tokens_without_whitespace()[-1]
    assert last_non_ws.token == "."
    assert last_non_ws.is_sentence_end is True
    assert any(r.pos_tag == SENT_END_TAG for r in last_non_ws.readings)


def test_trailing_whitespace_sent_end_location():
    """Verify SENT_END attaches to last non-whitespace token even with trailing spaces/tabs/newlines."""
    analyzer = RussianSentenceAnalyzer.get_instance()
    sent = analyzer.analyze_raw("Привет мир!   \t \n")

    non_ws = sent.get_tokens_without_whitespace()
    assert non_ws[-1].token == "!"
    assert non_ws[-1].is_sentence_end is True
    assert any(r.pos_tag == SENT_END_TAG for r in non_ws[-1].readings)

    # Trailing whitespace tokens must NOT have SENT_END
    all_tokens = sent.get_tokens()
    for tok in all_tokens:
        if tok.is_whitespace():
            assert tok.is_sentence_end is False
            assert not any(r.pos_tag == SENT_END_TAG for r in tok.readings)


def test_ignored_characters_combining_acute():
    """Verify combining acute U+0301 is stripped for morphology and pos_fix is calculated."""
    accented_text = "Краси́вый за́мок"  # Краси\u0301вый за\u0301мок
    sent = create_raw_analyzed_sentence(accented_text)
    tokens = sent.get_tokens_without_whitespace()

    # token 1: SENT_START
    assert tokens[0].is_pos_tag_unknown is False
    # token 2: Краси́вый
    tok_kras = tokens[1]
    assert tok_kras.clean_token == "Красивый"
    assert tok_kras.source_token == "Краси\u0301вый"
    assert tok_kras.is_tagged is True
    # token 3: за́мок
    tok_zam = tokens[2]
    assert tok_zam.clean_token == "замок"
    assert tok_zam.source_token == "за\u0301мок"
    assert tok_zam.is_tagged is True


def test_ignored_characters_combining_grave():
    """Verify combining grave U+0300 is stripped and source token preserved."""
    text = "Перѐд домом"  # Пере\u0300д
    sent = create_raw_analyzed_sentence(text)
    tokens = sent.get_tokens_without_whitespace()

    tok_pered = tokens[1]
    assert tok_pered.clean_token == "Перед"
    assert tok_pered.source_token == "Пере\u0300д"
    assert tok_pered.is_tagged is True


def test_ignored_characters_soft_hyphen():
    """Verify soft hyphen U+00AD is stripped for morphology lookup."""
    text = "авто\u00adмобиль"
    sent = create_raw_analyzed_sentence(text)
    tokens = sent.get_tokens_without_whitespace()

    tok_auto = tokens[1]
    assert tok_auto.clean_token == "автомобиль"
    assert tok_auto.source_token == "авто\u00adмобиль"
    assert tok_auto.is_tagged is True


def test_emoji_surrogates_utf16_offsets():
    """Verify non-BMP emoji characters contribute 2 UTF-16 code units to start_pos."""
    text = "🌟 Привет 🚀 мир!"
    sent = create_raw_analyzed_sentence(text)
    tokens = sent.get_tokens()

    # Find tokens and check their start_pos
    # 🌟 is 2 UTF-16 code units (surrogate pair)
    # ' ' is 1 UTF-16 code unit
    # Привет starts at offset 3
    privet_tok = [t for t in tokens if t.token == "Привет"][0]
    assert privet_tok.start_pos == 3


def test_whitespace_and_mapping():
    """Verify token array, non-whitespace array, and position mappings."""
    text = "Слово \t еще   слово."
    sent = create_raw_analyzed_sentence(text)

    all_tokens = sent.get_tokens()
    non_ws = sent.get_tokens_without_whitespace()

    # SENT_START is at non_ws[0] -> all_tokens[0]
    assert sent.get_original_position(0) == 0

    # "Слово" is non_ws[1] -> all_tokens[1]
    assert non_ws[1].token == "Слово"
    assert sent.get_original_position(1) == 1

    # "еще" is non_ws[2] -> all_tokens[3] (since all_tokens[2] is " \t ")
    assert non_ws[2].token == "еще"
    assert all_tokens[sent.get_original_position(2)].token == "еще"


def test_whitespace_before_punctuation_and_words():
    """Verify whitespace_before and is_whitespace_before across different whitespace patterns."""
    # 1. Word + punctuation without whitespace: "Привет!"
    s1 = create_raw_analyzed_sentence("Привет!")
    t1 = s1.get_tokens()
    # t1[0] = SENT_START (ws_before = "")
    # t1[1] = "Привет" (prev is "" -> ws_before = "")
    # t1[2] = "!" (prev is "Привет" -> ws_before = "")
    assert t1[0].whitespace_before == ""
    assert t1[0].is_whitespace_before is False
    assert t1[1].whitespace_before == ""
    assert t1[1].is_whitespace_before is False
    assert t1[2].whitespace_before == ""
    assert t1[2].is_whitespace_before is False

    # 2. Word + one space + word: "Привет мир"
    s2 = create_raw_analyzed_sentence("Привет мир")
    t2 = s2.get_tokens()
    # t2[0] = SENT_START
    # t2[1] = "Привет" (ws_before = "")
    # t2[2] = " " (prev is "Привет" -> ws_before = "")
    # t2[3] = "мир" (prev is " " -> ws_before = " ")
    assert t2[1].whitespace_before == ""
    assert t2[1].is_whitespace_before is False
    assert t2[2].whitespace_before == ""
    assert t2[2].is_whitespace_before is False
    assert t2[3].whitespace_before == " "
    assert t2[3].is_whitespace_before is True

    # 3. Multiple spaces: "Привет   мир"
    s3 = create_raw_analyzed_sentence("Привет   мир")
    t3 = s3.get_tokens()
    # t3: [SENT_START, "Привет", " ", " ", " ", "мир"]
    mir_tok3 = [t for t in t3 if t.token == "мир"][0]
    assert mir_tok3.whitespace_before == " "
    assert mir_tok3.is_whitespace_before is True

    # 4. Tabs and newlines: "Привет\tмир\nтест"
    s4 = create_raw_analyzed_sentence("Привет\tмир\nтест")
    t4 = s4.get_tokens()
    assert t4[3].token == "мир"
    assert t4[3].whitespace_before == "\t"
    assert t4[3].is_whitespace_before is True
    assert t4[5].token == "тест"
    assert t4[5].whitespace_before == "\n"
    assert t4[5].is_whitespace_before is True

    # 5. Leading and trailing whitespace: "  Привет мир  "
    s5 = create_raw_analyzed_sentence("  Привет мир  ")
    t5 = s5.get_tokens()
    privet_tok5 = [t for t in t5 if t.token == "Привет"][0]
    mir_tok5 = [t for t in t5 if t.token == "мир"][0]
    assert privet_tok5.whitespace_before == " "
    assert privet_tok5.is_whitespace_before is True
    assert mir_tok5.whitespace_before == " "
    assert mir_tok5.is_whitespace_before is True


