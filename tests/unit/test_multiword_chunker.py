"""Unit tests for MultiWordChunker."""

from __future__ import annotations

import pytest

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.disambiguation.multiwords import MultiWordChunker


def _build_sentence(tokens: list[str]) -> AnalyzedSentence:
    """Helper to build AnalyzedSentence from token strings."""
    sent_start = AnalyzedTokenReadings.create_sentence_start_token(start_pos=0)
    current_pos = 0
    readings_list: list[AnalyzedTokenReadings] = []
    for t in tokens:
        r = AnalyzedTokenReadings(
            readings=[AnalyzedToken(token=t, lemma=t.lower(), pos_tag=None if t.isspace() else "UNKNOWN")],
            start_pos=current_pos,
        )
        readings_list.append(r)
        current_pos += len(t)
    return AnalyzedSentence([sent_start] + readings_list)


def test_multiword_chunker_loading() -> None:
    """Verify MultiWordChunker loads and indexes multiwords.txt correctly."""
    chunker = MultiWordChunker.get_instance()
    chunker._ensure_initialized()

    assert len(chunker._m_full_space) > 200
    assert "в целом" in chunker._m_full_space
    assert chunker._m_full_space["в целом"].pos_tag == "ADV"
    assert "до мажор" in chunker._m_full_space
    assert chunker._m_full_space["до мажор"].pos_tag == "NN:Masc"
    assert "во что бы то ни стало" in chunker._m_full_space
    assert chunker._m_full_space["во что бы то ни стало"].pos_tag == "ADV"


def test_multiword_chunker_two_words() -> None:
    """Verify 2-word phrase chunking emits <TAG> and </TAG> on start and end tokens."""
    chunker = MultiWordChunker.get_instance()
    sentence = _build_sentence(["В", " ", "целом", ",", " ", "все", " ", "хорошо", "."])

    chunked = chunker.disambiguate(sentence)
    tokens = chunked.get_tokens()

    # Index 1: "В", Index 2: " ", Index 3: "целом"
    v_token = tokens[1]
    tselom_token = tokens[3]

    assert v_token.has_pos_tag("<ADV>")
    assert v_token.reading_with_tag_regex("<ADV>").lemma == "В целом"
    assert tselom_token.has_pos_tag("</ADV>")
    assert tselom_token.reading_with_tag_regex("</ADV>").lemma == "В целом"


def test_multiword_chunker_six_words() -> None:
    """Verify 6-word phrase chunking across multiple intermediate words."""
    chunker = MultiWordChunker.get_instance()
    sentence = _build_sentence(["Мы", " ", "сделаем", " ", "это", " ", "во", " ", "что", " ", "бы", " ", "то", " ", "ни", " ", "стало", "."])

    chunked = chunker.disambiguate(sentence)
    tokens = chunked.get_tokens()

    # Find "во" and "стало"
    vo_token = next(t for t in tokens if t.token == "во")
    stalo_token = next(t for t in tokens if t.token == "стало")

    assert vo_token.has_pos_tag("<ADV>")
    assert stalo_token.has_pos_tag("</ADV>")
    assert vo_token.reading_with_tag_regex("<ADV>").lemma == "во что бы то ни стало"


def test_multiword_chunker_whitespace_invariance() -> None:
    """Verify multiword matching is unaffected by multiple spaces or punctuation outside the phrase."""
    chunker = MultiWordChunker.get_instance()
    sentence = _build_sentence(["до", "   ", "свидания", "!"])

    chunked = chunker.disambiguate(sentence)
    tokens = chunked.get_tokens()

    do_tok = next(t for t in tokens if t.token == "до")
    svid_tok = next(t for t in tokens if t.token == "свидания")

    assert do_tok.has_pos_tag("<ADV>")
    assert svid_tok.has_pos_tag("</ADV>")
