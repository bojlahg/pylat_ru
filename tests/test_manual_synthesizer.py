"""tests/test_manual_synthesizer.py

Unit tests for ManualSynthesizer: plain-text full forms, comments,
#separatorRegExp= directive, Java Pattern.split semantics, and error handling.
"""

from __future__ import annotations

import io
from pathlib import Path
import pytest

from pylat_ru.synthesis.errors import (
    ManualSynthesizerFormatError,
    SynthesisResourceError,
)
from pylat_ru.synthesis.manual import ManualSynthesizer


def test_manual_synthesizer_basic_parsing_and_no_suffix_decoding():
    """Verify plain-text full forms are preserved without suffix decoding (+, ++)."""
    content = """
# Sample manual synthesis file
мадам\tмадам\tNN:Name:Fem:PL
полу\tпол\tNN:Inanim:Masc:Sin:2R
# Regression test: forms starting with + or ++ must NOT be decoded as suffixes
+ой\tшлифмашина\tNN:Inanim:Masc:Sin:T
++ин\tшлифмашина\tNN:Inanim:Masc:Sin:R
"""
    stream = io.StringIO(content)
    manual = ManualSynthesizer(stream)

    assert len(manual) == 4
    assert manual.lookup("мадам", "NN:Name:Fem:PL") == ["мадам"]
    assert manual.lookup("пол", "NN:Inanim:Masc:Sin:2R") == ["полу"]
    # Form +ой is stored literally as +ой, NOT decoded as шлифмашина + ой
    assert manual.lookup("шлифмашина", "NN:Inanim:Masc:Sin:T") == ["+ой"]
    # Form ++ин is stored literally as ++ин, NOT decoded as шлифмашин + ин
    assert manual.lookup("шлифмашина", "NN:Inanim:Masc:Sin:R") == ["++ин"]
    assert manual.lookup("nonexistent", "TAG") is None


def test_manual_synthesizer_custom_separator_and_java_split():
    """Verify #separatorRegExp= directive and Java Pattern.split trailing empty field dropping."""
    content = """
#separatorRegExp=\\s+
слово\tлемма\tTAG1
форма   лемма   TAG2
"""
    stream = io.StringIO(content)
    manual = ManualSynthesizer(stream)

    assert manual.lookup("лемма", "TAG1") == ["слово"]
    assert manual.lookup("лемма", "TAG2") == ["форма"]


def test_manual_synthesizer_inline_comments():
    """Verify inline comments are stripped cleanly."""
    content = """
слово\tлемма\tTAG # inline comment here
"""
    stream = io.StringIO(content)
    manual = ManualSynthesizer(stream)

    assert manual.lookup("лемма", "TAG") == ["слово"]


def test_manual_synthesizer_invalid_line_raises_format_error():
    """Verify malformed line (not 3 fields) raises ManualSynthesizerFormatError."""
    content = "только_два\tполя\n"
    stream = io.StringIO(content)
    with pytest.raises(ManualSynthesizerFormatError, match="expected 3 fields"):
        ManualSynthesizer(stream)


def test_manual_synthesizer_empty_or_invalid_separator_regexp():
    """Verify empty or malformed regex directive raises ManualSynthesizerFormatError."""
    empty_sep = "#separatorRegExp=\nслово\tлемма\tTAG\n"
    with pytest.raises(ManualSynthesizerFormatError, match="Empty regular expression"):
        ManualSynthesizer(io.StringIO(empty_sep))

    bad_sep = "#separatorRegExp=[invalid(\nслово\tлемма\tTAG\n"
    with pytest.raises(ManualSynthesizerFormatError, match="Invalid regular expression"):
        ManualSynthesizer(io.StringIO(bad_sep))


def test_manual_synthesizer_non_breaking_space_rejection():
    """Verify non-breaking space (\\u00A0) raises ManualSynthesizerFormatError."""
    content = "слово\tлемма\tTAG\u00a0EXTRA\n"
    with pytest.raises(ManualSynthesizerFormatError, match="non-breaking space"):
        ManualSynthesizer(io.StringIO(content))


def test_manual_synthesizer_file_not_found_raises_resource_error():
    """Verify nonexistent file path raises SynthesisResourceError."""
    with pytest.raises(SynthesisResourceError):
        ManualSynthesizer(Path("nonexistent_file_path_xyz.txt"))


def test_manual_synthesizer_possible_tags():
    """Verify get_possible_tags returns all unique tags."""
    content = """
w1\tl1\tTAG_A
w2\tl2\tTAG_B
w3\tl3\tTAG_A
"""
    stream = io.StringIO(content)
    manual = ManualSynthesizer(stream)
    assert manual.get_possible_tags() == {"TAG_A", "TAG_B"}
