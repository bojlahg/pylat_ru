"""Task 0014 - pinned checking-level semantics for picky-tagged rules.

Discovered by the Task-0014 differential campaign: ``pylat_ru`` ran picky-tagged rules
at the default whole-pipeline level, while pinned ``JLanguageTool.check(text)`` runs at
``Level.DEFAULT`` and drops those matches.

Upstream evidence, from ``org.languagetool.JLanguageTool`` in the trusted pinned jar
(``lt_6.8_source_build_jdk17_stefan``)::

    static boolean isRuleActiveForLevelAndToneTags(Rule rule, Level level, Set<ToneTag> t) {
      if (level == Level.DEFAULT && rule.hasTag(Tag.picky)) {
        return false;
      }
      ...
    }

and ``filterMatches`` applies that predicate as a stream filter *before*
``SameRuleGroupFilter``, ``LanguageDependentRuleMatchFilter`` and
``CleanOverlappingFilter``.

These tests are Java-free; the pinned behaviour they pin down was captured from the
trusted oracle during the campaign.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from pylat_ru import LanguageToolRU
from pylat_ru.grammar import RussianGrammarEngine
from pylat_ru.match_filters import (
    LEVEL_DEFAULT,
    LEVEL_PICKY,
    filter_rule_matches,
    level_filter,
)
from pylat_ru.native_rules import RUSSIAN_RULE_CLASSES


@dataclass(frozen=True)
class FakeMatch:
    """Minimal match shape the filter pipeline consumes."""

    rule_id: str
    offset: int
    length: int
    tags: tuple[str, ...] = ()
    priority: int = 0
    replacements: tuple[str, ...] = ()
    original_error: str = ""
    utf16_offset: int = 0
    utf16_length: int = 0
    included_in_errors_corrected_all_at_once: bool = False


def test_level_filter_drops_picky_matches_at_default_level() -> None:
    matches = [
        FakeMatch("ORDINARY", 0, 4),
        FakeMatch("PICKY_ONE", 10, 4, tags=("picky",)),
    ]
    assert [m.rule_id for m in level_filter(matches, LEVEL_DEFAULT)] == ["ORDINARY"]


def test_level_filter_keeps_picky_matches_at_picky_level() -> None:
    matches = [
        FakeMatch("ORDINARY", 0, 4),
        FakeMatch("PICKY_ONE", 10, 4, tags=("picky",)),
    ]
    assert [m.rule_id for m in level_filter(matches, LEVEL_PICKY)] == [
        "ORDINARY",
        "PICKY_ONE",
    ]


def test_level_filter_defaults_to_the_pinned_default_level() -> None:
    matches = [FakeMatch("PICKY_ONE", 0, 4, tags=("picky",))]
    assert level_filter(matches) == []


def test_unknown_checking_level_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported checking level"):
        LanguageToolRU().check("Обычный текст.", level="UNKNOWN")


def test_level_filter_runs_before_grouping_and_overlap_resolution() -> None:
    """A suppressed picky match must not influence grouping or overlap cleanup.

    Here the picky match sits between two ordinary ones and overlaps both.  Upstream
    removes it first, so both ordinary matches survive.
    """
    matches = [
        FakeMatch("ORDINARY_A", 0, 5, utf16_offset=0, utf16_length=5),
        FakeMatch("PICKY_MID", 3, 5, tags=("picky",), utf16_offset=3, utf16_length=5),
        FakeMatch("ORDINARY_B", 6, 5, utf16_offset=6, utf16_length=5),
    ]
    kept = filter_rule_matches(matches, "0123456789ab")
    assert [m.rule_id for m in kept] == ["ORDINARY_A", "ORDINARY_B"]


def test_picky_rules_are_never_reported_by_the_default_pipeline() -> None:
    """The regression that started this: ``kak_bi`` is picky and must not fire."""
    tool = LanguageToolRU()
    text = "Ну, в общем, это как бы просто, ну, такой, в общем, текст."
    assert [match.rule_id for match in tool.check(text)] == []


def test_public_check_level_exposes_picky_candidates_without_reimplementing_filtering() -> None:
    tool = LanguageToolRU(rule_config={"TOO_LONG_SENTENCE": {"maxWords": 4}})
    text = "Один два три четыре пять."
    assert "TOO_LONG_SENTENCE" not in {m.rule_id for m in tool.check(text)}
    assert "TOO_LONG_SENTENCE" in {
        m.rule_id for m in tool.check(text, level=LEVEL_PICKY)
    }


def test_no_picky_rule_id_can_reach_a_default_check() -> None:
    picky_ids = {
        rule.id for rule in RussianGrammarEngine.get_instance().get_all_rules() if "picky" in (rule.tags or [])
    } | {
        rule_class.rule_id
        for rule_class in RUSSIAN_RULE_CLASSES
        if "picky" in getattr(rule_class, "tags", ())
    }
    assert picky_ids, "expected the pinned Russian surface to carry picky rules"
    assert "TOO_LONG_SENTENCE" in picky_ids
    assert "kak_bi" in picky_ids

    tool = LanguageToolRU(enabled_rules=sorted(picky_ids))
    texts = (
        "Ну, в общем, это как бы просто, ну, такой, в общем, текст.",
        " ".join(["слово"] * 120) + ".",
        "Он тебе как бы нравится?",
    )
    for text in texts:
        assert not (
            picky_ids & {match.rule_id for match in tool.check(text)}
        ), text


@pytest.mark.parametrize("level", [LEVEL_DEFAULT, LEVEL_PICKY])
def test_level_filter_never_reorders_surviving_matches(level: str) -> None:
    matches = [
        FakeMatch("A", 0, 1),
        FakeMatch("B", 1, 1, tags=("picky",)),
        FakeMatch("C", 2, 1),
        FakeMatch("D", 3, 1),
    ]
    survivors = [m.rule_id for m in level_filter(matches, level)]
    assert survivors == sorted(survivors)
