"""LanguageTool Russian synthesis subsystem."""

from __future__ import annotations

from pylat_ru.synthesis.manual import ManualSynthesizer
from pylat_ru.synthesis.roman import get_roman_number, int_to_roman
from pylat_ru.synthesis.synthesizer import (
    BaseSynthesizer,
    RussianSynthesizer,
    Synthesizer,
)

__all__ = [
    "Synthesizer",
    "BaseSynthesizer",
    "RussianSynthesizer",
    "ManualSynthesizer",
    "int_to_roman",
    "get_roman_number",
]
