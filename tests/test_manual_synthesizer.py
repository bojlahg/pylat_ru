"""tests/test_manual_synthesizer.py

Unit tests for ManualSynthesizer: parsing, suffix decoding (+, ++),
comments, custom separator directives (#separatorRegExp=), and lookup.
"""

from __future__ import annotations

import io
import pytest
from pathlib import Path

from pylat_ru.synthesis.manual import ManualSynthesizer


def test_manual_synthesizer_basic_parsing():
    """Verify standard tab-separated parsing and form decoding."""
    content = """
# Sample manual synthesis file
мадам\tмадам\tNN:Name:Fem:PL
полу\tпол\tNN:Inanim:Masc:Sin:2R
# Suffix encoding test:
+ой\tшлифмашина\tNN:Inanim:Masc:Sin:T
++ин\tшлифмашина\tNN:Inanim:Masc:Sin:R
"""
    stream = io.StringIO(content)
    manual = ManualSynthesizer(stream)

    assert len(manual) == 4
    assert manual.lookup("мадам", "NN:Name:Fem:PL") == ["мадам"]
    assert manual.lookup("пол", "NN:Inanim:Masc:Sin:2R") == ["полу"]
    # +ой -> шлифмашина + ой = шлифмашинаой (or as encoded)
    assert manual.lookup("шлифмашина", "NN:Inanim:Masc:Sin:T") == ["шлифмашинаой"]
    # ++ин -> шлифмашин + ин = шлифмашинин
    assert manual.lookup("шлифмашина", "NN:Inanim:Masc:Sin:R") == ["шлифмашинин"]
    assert manual.lookup("nonexistent", "TAG") is None


def test_manual_synthesizer_custom_separator():
    """Verify #separatorRegExp= directive."""
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


def test_manual_synthesizer_invalid_line():
    """Verify malformed line raises ValueError."""
    content = "только_два\tполя\n"
    stream = io.StringIO(content)
    with pytest.raises(ValueError, match="Expected 3"):
        ManualSynthesizer(stream)


def test_manual_synthesizer_file_not_found():
    """Verify nonexistent file path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
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
