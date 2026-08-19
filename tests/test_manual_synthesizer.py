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


def test_manual_synthesizer_basic_parsing():
    """Verify plain-text full forms are parsed and stored directly."""
    content = """
# Sample manual synthesis file
мадам\tмадам\tNN:Name:Fem:PL
полу\tпол\tNN:Inanim:Masc:Sin:2R
шлифмашиной\tшлифмашина\tNN:Inanim:Fem:Sin:T
"""
    stream = io.StringIO(content)
    manual = ManualSynthesizer(stream)

    assert len(manual) == 3
    assert manual.lookup("мадам", "NN:Name:Fem:PL") == ["мадам"]
    assert manual.lookup("пол", "NN:Inanim:Masc:Sin:2R") == ["полу"]
    assert manual.lookup("шлифмашина", "NN:Inanim:Fem:Sin:T") == ["шлифмашиной"]
    assert manual.lookup("nonexistent", "TAG") == []


def test_manual_synthesizer_rejects_forms_starting_with_plus():
    """Verify input full forms starting with '+' are rejected matching Java ManualSynthesizer."""
    content = "+ой\tшлифмашина\tNN:Inanim:Masc:Sin:T\n"
    stream = io.StringIO(content)
    with pytest.raises(ManualSynthesizerFormatError, match=r"Forms starting with '\+' are not supported"):
        ManualSynthesizer(stream)

    content2 = "++ин\tшлифмашина\tNN:Inanim:Masc:Sin:R\n"
    stream2 = io.StringIO(content2)
    with pytest.raises(ManualSynthesizerFormatError, match=r"Forms starting with '\+' are not supported"):
        ManualSynthesizer(stream2)


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


def test_manual_synthesizer_trailing_empty_field_split_rejection():
    """Verify trailing empty field in default tab separator is dropped, causing length != 3 failure."""
    content = "форма\tлемма\t\n"
    stream = io.StringIO(content)
    with pytest.raises(ManualSynthesizerFormatError, match="expected 3 fields, got 2"):
        ManualSynthesizer(stream)


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
