"""tests/unit/test_russian_chunker.py

Unit tests for RussianChunker, TokenExpression parsing and evaluation,
phrase types, and chunk tag assignment.
"""

from __future__ import annotations

import pytest

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.chunking.token_expression import (
    ChunkTaggedToken,
    TokenCondition,
    TokenExpression,
    parse_token_predicate,
)


def _make_reading(
    token: str,
    pos_tag: str | None = None,
    lemma: str | None = None,
    chunk_tags: list[str] | None = None,
) -> AnalyzedTokenReadings:
    at = AnalyzedToken(token=token, lemma=lemma or token, pos_tag=pos_tag)
    atr = AnalyzedTokenReadings(readings=[at], start_pos=0)
    if chunk_tags:
        atr.chunk_tags = list(chunk_tags)
    return atr


def test_token_condition_string_case():
    """Verify string condition case sensitivity options."""
    cond_ci = TokenCondition("string", "если", case_sensitive=False)
    tok = ChunkTaggedToken("Если", ["O"], None)
    assert cond_ci.evaluate(tok)

    cond_cs = TokenCondition("string", "если", case_sensitive=True)
    assert not cond_cs.evaluate(tok)
    assert cond_cs.evaluate(ChunkTaggedToken("если", ["O"], None))


def test_token_condition_pos_and_regex():
    """Verify pos substring and regex matching on AnalyzedTokenReadings."""
    atr = _make_reading("Иван", "NN:Name:Masc:Sin:Nom", "Иван")
    tok = ChunkTaggedToken("Иван", ["O"], atr)

    cond_pos = TokenCondition("pos", "NN:Name")
    assert cond_pos.evaluate(tok)

    cond_posre = TokenCondition("posre", r"NN:(Name|Fam):.*")
    assert cond_posre.evaluate(tok)

    cond_neg = TokenCondition("posre", r"VB:.*", negated=True)
    assert cond_neg.evaluate(tok)


def test_token_predicate_conjunction():
    """Verify boolean AND conjunction in TokenPredicate."""
    pred = parse_token_predicate("posre='VB:.*' & !posre='NN:.*'")
    # Pure verb
    atr_vb = _make_reading("шел", "VB:Past:Masc", "идти")
    assert pred.matches(ChunkTaggedToken("шел", ["O"], atr_vb))

    # Dual reading (both VB and NN)
    at1 = AnalyzedToken("тест", "тест", "VB:Pres:Sin")
    at2 = AnalyzedToken("тест", "тест", "NN:Inanim:Masc:Sin:Nom")
    atr_dual = AnalyzedTokenReadings(readings=[at1, at2], start_pos=0)
    assert not pred.matches(ChunkTaggedToken("тест", ["O"], atr_dual))


def test_token_expression_quantifiers():
    """Verify greedy quantifiers in TokenExpression."""
    expr = TokenExpression("<posre='NN:Name:.*'>+", case_sensitive=False)
    atr1 = _make_reading("Иван", "NN:Name:Masc:Sin:Nom")
    atr2 = _make_reading("Иванович", "NN:Name:Masc:Sin:Nom")
    atr3 = _make_reading("пошел", "VB:Past:Masc")

    tokens = [
        ChunkTaggedToken("Иван", ["O"], atr1),
        ChunkTaggedToken("Иванович", ["O"], atr2),
        ChunkTaggedToken("пошел", ["O"], atr3),
    ]

    matches = expr.find_all(tokens)
    assert len(matches) == 1
    assert matches[0] == (0, 2)


def test_russian_chunker_basic_application():
    """Verify RussianChunker applies NP, VP, and MayMissingYO preservation."""
    chunker = RussianChunker()

    atr_name1 = _make_reading("Иван", "NN:Name:Masc:Sin:Nom")
    atr_name2 = _make_reading("Иванович", "NN:Name:Masc:Sin:Nom")
    atr_yo = _make_reading("пошел", "VB:Past:Masc", chunk_tags=["MayMissingYO"])
    atr_prep = _make_reading("в", "PREP")
    atr_noun = _make_reading("лес", "NN:Inanim:Masc:Sin:V")

    tokens = [atr_name1, atr_name2, atr_yo, atr_prep, atr_noun]
    sent = AnalyzedSentence(tokens=tokens)

    chunker.chunk(sent)

    assert sent.tokens[0].chunk_tags == ["B-NP"]
    assert sent.tokens[1].chunk_tags == ["I-NP"]
    assert sent.tokens[2].chunk_tags == ["MayMissingYO"]  # Preserved and skipped by chunker
    assert sent.tokens[3].chunk_tags == ["O"]
    assert sent.tokens[4].chunk_tags == ["O"]
