"""Focused translation of pinned SameRuleGroup/CleanOverlapping semantics."""

from __future__ import annotations

from pylat_ru import RuleMatch
from pylat_ru.match_filters import clean_overlapping_filter, same_rule_group_filter


def _match(rule_id: str, start: int, end: int, *, priority: int = 0,
           tags: tuple[str, ...] = (), suggestions: tuple[str, ...] = (),
           included: bool = False, original: str = "") -> RuleMatch:
    return RuleMatch(
        rule_id=rule_id, category_id="TEST", message=rule_id, offset=start,
        length=end - start, replacements=suggestions, priority=priority,
        tags=tags, included_in_errors_corrected_all_at_once=included,
        original_error=original, utf16_offset=start, utf16_length=end - start,
    )


def test_same_rule_group_stable_position_sort_and_inclusive_overlap() -> None:
    later = _match("A", 4, 7)
    first = _match("A", 0, 4)
    duplicate = _match("A", 3, 6)
    other = _match("B", 3, 6)
    assert same_rule_group_filter([later, first, duplicate, other]) == [first, other, later]


def test_clean_overlapping_priority_picky_length_and_last_ties() -> None:
    picky = _match("PICKY", 0, 20, priority=12, tags=("picky",))
    inner = _match("INNER", 5, 7)
    assert clean_overlapping_filter([picky, inner], "x" * 20) == [inner]
    short = _match("SHORT", 0, 3)
    long = _match("LONG", 0, 5)
    assert clean_overlapping_filter([short, long], "x" * 5) == [long]
    first = _match("FIRST", 0, 5)
    last = _match("LAST", 0, 5)
    assert clean_overlapping_filter([first, last], "x" * 5) == [last]


def test_clean_overlapping_keeps_adjacent_and_suppresses_duplicate_suggestion() -> None:
    left = _match("LEFT", 0, 2, suggestions=("foo,",))
    right = _match("RIGHT", 2, 4, suggestions=(", bar",))
    assert clean_overlapping_filter([left, right], "abcd") == [right]
    plain_right = _match("RIGHT", 2, 4, suggestions=("bar",))
    assert clean_overlapping_filter([left, plain_right], "abcd") == [left, plain_right]


def test_punctuation_only_prefers_correction_all_flag_when_priority_is_lower() -> None:
    ordinary = _match("ORDINARY", 0, 2, priority=2, suggestions=("a,",), original="a ")
    correct_all = _match("ALL", 0, 2, priority=1, suggestions=("a;",), included=True, original="a ")
    assert clean_overlapping_filter([ordinary, correct_all], "a ") == [correct_all]
