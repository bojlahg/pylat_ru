"""Unit tests for AnalyzedTokenReadings mutation semantics against LanguageTool."""

from __future__ import annotations

import re
import pytest

from pylat_ru.analysis import AnalyzedToken, AnalyzedTokenReadings, SENT_END_TAG, SENT_START_TAG


def test_add_reading_does_not_deduplicate():
    """Verify add_reading appends readings without generic deduplication matching Java LT."""
    r1 = AnalyzedToken(token="тест", lemma="тест", pos_tag="NN:Inan:Masc:Nom")
    r2 = AnalyzedToken(token="тест", lemma="тест", pos_tag="NN:Inan:Masc:Nom")

    atr = AnalyzedTokenReadings(readings=[r1], start_pos=5)
    atr.add_reading(r2)

    assert len(atr.readings) == 2
    assert atr.readings[0] == r1
    assert atr.readings[1] == r2


def test_remove_reading_exact():
    """Verify removing exact reading removes matching readings and preserves others."""
    r1 = AnalyzedToken(token="дом", lemma="дом", pos_tag="NN:Inan:Masc:Nom")
    r2 = AnalyzedToken(token="дом", lemma="дом", pos_tag="NN:Inan:Masc:Acc")

    atr = AnalyzedTokenReadings(readings=[r1, r2], start_pos=0)
    atr.remove_reading(r1)

    assert len(atr.readings) == 1
    assert atr.readings[0] == r2


def test_remove_reading_regex():
    """Verify removing readings by regex pattern."""
    r1 = AnalyzedToken(token="бег", lemma="бег", pos_tag="NN:Inan:Masc:Nom")
    r2 = AnalyzedToken(token="бег", lemma="бег", pos_tag="NN:Inan:Masc:Acc")
    r3 = AnalyzedToken(token="бег", lemma="бежать", pos_tag="VB:Imp:Past:Masc")

    atr = AnalyzedTokenReadings(readings=[r1, r2, r3], start_pos=0)
    atr.remove_reading(re.compile(r"^NN:.*"))

    assert len(atr.readings) == 1
    assert atr.readings[0] == r3


def test_remove_all_readings_falls_back_to_null_token_with_original_surface():
    """Verify removing all readings creates a null reading with original surface, NOT empty string."""
    r1 = AnalyzedToken(token="неизвестно", lemma="неизвестный", pos_tag="ADJ:Short:Neut")
    atr = AnalyzedTokenReadings(readings=[r1], start_pos=10, source_token="неизвестно")

    atr.remove_reading(r1)

    assert len(atr.readings) == 1
    null_reading = atr.readings[0]
    assert null_reading.token == "неизвестно"
    assert null_reading.lemma is None
    assert null_reading.pos_tag is None


def test_remove_all_readings_preserves_sent_end():
    """Verify if token is marked as sentence end, removing normal readings retains SENT_END."""
    r1 = AnalyzedToken(token="конец", lemma="конец", pos_tag="NN:Inan:Masc:Nom")
    atr = AnalyzedTokenReadings(readings=[r1], start_pos=20)
    atr.set_sentence_end(True)

    # Initial state has r1 and SENT_END
    assert len(atr.readings) == 2

    # Remove r1: SENT_END remains
    atr.remove_reading(r1)

    assert atr.is_sentence_end is True
    assert len(atr.readings) == 1
    assert atr.readings[0].pos_tag == SENT_END_TAG

    # Removing SENT_END falls back to null token then set_sentence_end restores single SENT_END
    sent_end_reading = atr.readings[0]
    atr.remove_reading(sent_end_reading)
    assert len(atr.readings) == 1
    assert atr.readings[0].token == "конец"
    assert atr.readings[0].pos_tag == SENT_END_TAG


def test_remove_sent_end_while_ordinary_reading_remains_restores_sent_end():
    """Verify removing SENT_END while ordinary reading remains restores SENT_END matching Java LT."""
    r1 = AnalyzedToken(token="слово", lemma="слово", pos_tag="NN:Inan:Neut:Nom")
    atr = AnalyzedTokenReadings(readings=[r1], start_pos=10)
    atr.set_sentence_end(True)

    assert len(atr.readings) == 2
    assert atr.readings[0] == r1
    assert atr.readings[1].pos_tag == SENT_END_TAG

    # Explicitly remove the SENT_END reading
    sent_end_reading = atr.readings[1]
    atr.remove_reading(sent_end_reading)

    # In Java LT removeReading, removedSentEnd triggers setSentEnd(), restoring SENT_END
    assert atr.is_sentence_end is True
    assert len(atr.readings) == 2
    assert atr.readings[0] == r1
    assert atr.readings[1].pos_tag == SENT_END_TAG
    assert atr.readings[1].lemma == "слово"


def test_metadata_preservation_on_copy_and_init():
    """Verify container metadata is preserved when constructing or cloning AnalyzedTokenReadings."""
    r = AnalyzedToken(token="слово", lemma="слово", pos_tag="NN:Inan:Neut:Nom")
    atr = AnalyzedTokenReadings(
        readings=[r],
        start_pos=15,
        chunk_tags=["ChunkTag1", "ChunkTag2"],
        is_sentence_start=False,
        is_sentence_end=True,
        is_paragraph_end=True,
        is_immunized=True,
        is_ignore_spelling=True,
        whitespace_before="   ",
        pos_fix=2,
        clean_token="слово",
        source_token="сло́во",
    )

    clone = AnalyzedTokenReadings(atr)
    assert clone.start_pos == 15
    assert clone.chunk_tags == ["ChunkTag1", "ChunkTag2"]
    assert clone.is_sentence_end is True
    assert clone.is_paragraph_end is True
    assert clone.is_immunized is True
    assert clone.is_ignore_spelling is True
    assert clone.whitespace_before == "   "
    assert clone.pos_fix == 2
    assert clone.clean_token == "слово"
    assert clone.source_token == "сло́во"
