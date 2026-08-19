"""Unit tests for ManualTagger parsing, comments, separators, and error handling."""

import io
from pathlib import Path
import pytest

from pylat_ru.tagging.errors import ManualTaggerFormatError, TaggerResourceError
from pylat_ru.tagging.word_tagger import ManualTagger, TaggedWord


def test_manual_tagger_basic_tsv_parsing():
    """Verify parsing of clean 3-field tab-separated lines."""
    data = (
        "мадам\tмадам\tNN:Name:Fem:PL\n"
        "полу\tпол\tNN:Inanim:Masc:Sin:2R\n"
        "попозже\tпоздний\tADJ:Comp\n"
    )
    tagger = ManualTagger(data)
    assert tagger.entry_count == 3
    assert tagger.total_readings_count == 3

    readings = tagger.tag("мадам")
    assert readings == (TaggedWord(lemma="мадам", pos_tag="NN:Name:Fem:PL"),)

    readings_pol = tagger.tag("полу")
    assert readings_pol == (TaggedWord(lemma="пол", pos_tag="NN:Inanim:Masc:Sin:2R"),)


def test_manual_tagger_comments_and_blank_lines():
    """Verify comment lines, blank lines, and inline comments are handled correctly."""
    data = (
        "# Top level comment\n"
        "\n"
        "  # Indented comment\n"
        "авто\tавто\tNN:Inanim:Masc # inline comment\n"
        "боулинг\tбоулинг\tNN:Inanim:Masc:Sin:V\n"
        "боулинг\tбоулинг\tNN:Inanim:Masc:Sin:Nom\n"
    )
    tagger = ManualTagger(data)
    assert tagger.entry_count == 2
    assert tagger.total_readings_count == 3

    # Preserves multiple readings for 'боулинг' in exact insertion order
    readings = tagger.tag("боулинг")
    assert len(readings) == 2
    assert readings[0] == TaggedWord(lemma="боулинг", pos_tag="NN:Inanim:Masc:Sin:V")
    assert readings[1] == TaggedWord(lemma="боулинг", pos_tag="NN:Inanim:Masc:Sin:Nom")


def test_manual_tagger_pos_tag_trimming():
    """Verify trailing and leading spaces on POS tags are trimmed exactly matching upstream."""
    data = "трассерные\tтрассерный\tADJ:Posit:PL:Nom \n"
    tagger = ManualTagger(data)
    readings = tagger.tag("трассерные")
    assert readings == (TaggedWord(lemma="трассерный", pos_tag="ADJ:Posit:PL:Nom"),)


def test_manual_tagger_custom_separator():
    """Verify #separatorRegExp= directive alters field splitting."""
    data = (
        "#separatorRegExp=;\n"
        "мадам;мадам;NN:Name:Fem:PL\n"
        "полу;пол;NN:Inanim:Masc:Sin:2R\n"
    )
    tagger = ManualTagger(data)
    assert tagger.entry_count == 2
    assert tagger.tag("мадам") == (TaggedWord(lemma="мадам", pos_tag="NN:Name:Fem:PL"),)


def test_manual_tagger_rejects_nbsp():
    """Verify non-breaking space (\\u00A0) in data line raises ManualTaggerFormatError."""
    data = "слово\tслово\tNN:Inanim:Masc:Sin:Nom\u00a0\n"
    with pytest.raises(ManualTaggerFormatError) as exc_info:
        ManualTagger(data)
    assert "non-breaking space" in str(exc_info.value)
    assert "Line 1" in str(exc_info.value)


def test_manual_tagger_rejects_invalid_field_count():
    """Verify data lines with fewer or more than 3 fields raise ManualTaggerFormatError."""
    # Only 2 fields
    data_2 = "слово\tслово\n"
    with pytest.raises(ManualTaggerFormatError) as exc_info:
        ManualTagger(data_2)
    assert "expected 3 fields, got 2" in str(exc_info.value)
    assert "Line 1" in str(exc_info.value)

    # 4 fields
    data_4 = "слово\tслово\tTAG\textra\n"
    with pytest.raises(ManualTaggerFormatError) as exc_info4:
        ManualTagger(data_4)
    assert "expected 3 fields, got 4" in str(exc_info4.value)


def test_manual_tagger_multiple_sources_merge():
    """Verify multiple file/stream sources are parsed sequentially into the same tagger."""
    src1 = "форма1\tбаза1\tTAG1\n"
    src2 = "форма2\tбаза2\tTAG2\n"
    tagger = ManualTagger([src1, src2])
    assert tagger.entry_count == 2
    assert tagger.tag("форма1") == (TaggedWord(lemma="база1", pos_tag="TAG1"),)
    assert tagger.tag("форма2") == (TaggedWord(lemma="база2", pos_tag="TAG2"),)


def test_manual_tagger_missing_file_raises_resource_error(tmp_path: Path):
    """Verify non-existent file path raises TaggerResourceError."""
    missing = tmp_path / "non_existent.txt"
    with pytest.raises(TaggerResourceError):
        ManualTagger(missing)


def test_manual_tagger_malformed_separator_regexp():
    """Verify malformed regex in #separatorRegExp= raises ManualTaggerFormatError with context."""
    data = (
        "#separatorRegExp=[(\n"
        "слово;слово;TAG\n"
    )
    with pytest.raises(ManualTaggerFormatError) as exc_info:
        ManualTagger(data)
    assert "Invalid regular expression" in str(exc_info.value)
    assert "Line 1" in str(exc_info.value)


def test_manual_tagger_empty_separator_regexp():
    """Verify empty regex in #separatorRegExp= raises ManualTaggerFormatError with context."""
    data = (
        "#separatorRegExp=\n"
        "слово\tслово\tTAG\n"
    )
    with pytest.raises(ManualTaggerFormatError) as exc_info:
        ManualTagger(data)
    assert "Empty regular expression" in str(exc_info.value)
    assert "Line 1" in str(exc_info.value)


def test_manual_tagger_capturing_group_separator():
    """Verify regex with capturing group (;|\t) does not insert delimiters as extra fields."""
    data = (
        "#separatorRegExp=(;|\t)\n"
        "форма1;база1\tTAG1\n"
        "форма2\tбаза2;TAG2\n"
    )
    tagger = ManualTagger(data)
    assert tagger.entry_count == 2
    assert tagger.tag("форма1") == (TaggedWord(lemma="база1", pos_tag="TAG1"),)
    assert tagger.tag("форма2") == (TaggedWord(lemma="база2", pos_tag="TAG2"),)

