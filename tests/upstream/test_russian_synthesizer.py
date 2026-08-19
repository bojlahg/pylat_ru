"""tests/upstream/test_russian_synthesizer.py

Direct port of upstream LanguageTool RussianSynthesizerTest.java.
Tests core synthesis behavior on Russian words using RussianSynthesizer.
"""

from __future__ import annotations

from pylat_ru.analysis import AnalyzedToken
from pylat_ru.synthesis import RussianSynthesizer


def dummy_token(token_str: str) -> AnalyzedToken:
    """Create dummy AnalyzedToken matching RussianSynthesizerTest.dummyToken."""
    return AnalyzedToken(token=token_str, lemma=token_str, pos_tag=token_str)


def test_synthesize_string():
    """Port of RussianSynthesizerTest.testSynthesizeString."""
    synth = RussianSynthesizer.get_instance()

    # Unknown token returns empty array
    assert len(synth.synthesize(dummy_token("blablabla"), "blablabla")) == 0

    # семья (Nom) -> [семья]
    assert synth.synthesize(dummy_token("семья"), "NN:Inanim:Fem:Sin:Nom") == ["семья"]

    # семья (Gen / R) -> [семьи]
    assert synth.synthesize(dummy_token("семья"), "NN:Inanim:Fem:Sin:R") == ["семьи"]
