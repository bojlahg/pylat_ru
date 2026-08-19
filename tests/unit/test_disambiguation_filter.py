"""Unit tests for NoDisambiguationRussianPartialPosTagFilter."""

from __future__ import annotations

import pytest

from pylat_ru.analysis import AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.disambiguation.errors import DisambiguationFilterError
from pylat_ru.disambiguation.filters import NoDisambiguationRussianPartialPosTagFilter


def test_partial_filter_verb_ka() -> None:
    """Verify filter extracts 'дай' from 'дай-ка' and verifies VB:IMP:TRANS:PFV:Sin:P2."""
    filter_inst = NoDisambiguationRussianPartialPosTagFilter()
    token = AnalyzedTokenReadings([AnalyzedToken("дай-ка", None, None)], start_pos=0)

    args = "no:1 regexp:([А-ЯЁа-яё]+)-ка postag_regexp:VB:IMP:TRANS:PFV:Sin:P2"
    result = filter_inst.matches(args, [token], 0, [1])
    assert result is True


def test_partial_filter_verb_ka_rejects_non_verb() -> None:
    """Verify filter rejects non-verb words followed by -ка (e.g. 'стол-ка')."""
    filter_inst = NoDisambiguationRussianPartialPosTagFilter()
    token = AnalyzedTokenReadings([AnalyzedToken("стол-ка", None, None)], start_pos=0)

    args = "no:1 regexp:([А-ЯЁа-яё]+)-ка postag_regexp:VB:IMP:TRANS:PFV:Sin:P2"
    result = filter_inst.matches(args, [token], 0, [1])
    assert result is False


def test_partial_filter_pol_word() -> None:
    """Verify filter extracts noun from 'пол-яблока' and matches genitive noun (NN:.*:R)."""
    filter_inst = NoDisambiguationRussianPartialPosTagFilter()
    token = AnalyzedTokenReadings([AnalyzedToken("пол-яблока", None, None)], start_pos=0)

    args = "no:1 regexp:[Пп]ол-([АаЕеЁёИиОоУуЭэЮюЯялЛ][а-яё]+) postag_regexp:NN:.*:R"
    result = filter_inst.matches(args, [token], 0, [1])
    assert result is True


def test_partial_filter_missing_args_raises_error() -> None:
    """Verify missing required arguments raise explicit DisambiguationFilterError."""
    filter_inst = NoDisambiguationRussianPartialPosTagFilter()
    token = AnalyzedTokenReadings([AnalyzedToken("дай-ка", None, None)], start_pos=0)

    with pytest.raises(DisambiguationFilterError, match="requires 'no', 'regexp', and 'postag_regexp'"):
        filter_inst.matches("no:1 regexp:.*", [token], 0, [1])
