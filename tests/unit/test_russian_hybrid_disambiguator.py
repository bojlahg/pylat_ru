"""Unit tests for RussianHybridDisambiguator pipeline."""

from __future__ import annotations

import pytest

from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator


def test_russian_hybrid_disambiguator_singleton() -> None:
    """Verify RussianHybridDisambiguator singleton instantiation."""
    inst1 = RussianHybridDisambiguator.get_instance()
    inst2 = RussianHybridDisambiguator.get_instance()
    assert inst1 is inst2


def test_russian_hybrid_disambiguator_pipeline_multiword_and_xml() -> None:
    """Verify hybrid disambiguator applies multiword chunking followed by XML rules."""
    disambiguator = RussianHybridDisambiguator.get_instance()

    # 1. Multiword test: "В целом"
    sent_mw = disambiguator.disambiguate_text("В целом, все хорошо.")
    tokens_mw = sent_mw.get_tokens()

    v_tok = next(t for t in tokens_mw if t.token == "В")
    assert v_tok.has_pos_tag("<ADV>")

    # 2. XML rule test: "73 процента" -> "73" tagged as NumD_D
    sent_num = disambiguator.disambiguate_text("73 процента")
    tokens_num = sent_num.get_tokens()

    num_tok = next(t for t in tokens_num if t.token == "73")
    assert num_tok.has_pos_tag("NumD_D")

    # 3. Compound filter test: "дай-ка"
    sent_verb = disambiguator.disambiguate_text("Ваня, дай-ка мне этот молоток.")
    tokens_verb = sent_verb.get_tokens()

    verb_tok = next(t for t in tokens_verb if t.token == "дай-ка")
    assert verb_tok.has_pos_tag("VB:IMP:TRANS:PFV:Sin:P2")
    assert verb_tok.is_ignore_spelling is True
