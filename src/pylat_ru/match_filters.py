"""Pinned JLanguageTool 6.8 match-group and overlap compatibility filters."""

from __future__ import annotations

import unicodedata
from typing import Sequence, TypeVar


MatchT = TypeVar("MatchT")
_PICKY_PENALTY = -(2**31) + 10_000

#: Checking levels of pinned ``JLanguageTool.Level``.  ``JLanguageTool.check(text)``
#: runs at ``DEFAULT``; ``PICKY`` additionally reports picky-tagged rules.
LEVEL_DEFAULT = "DEFAULT"
LEVEL_PICKY = "PICKY"


def _end(match: object) -> int:
    return match.offset + match.length  # type: ignore[attr-defined]


def same_rule_group_filter(matches: Sequence[MatchT]) -> list[MatchT]:
    """Port of SameRuleGroupFilter: stable start sort, first same-ID overlap wins."""
    ordered = sorted(matches, key=lambda match: match.offset)  # type: ignore[attr-defined]
    clean: list[MatchT] = []
    index = 0
    while index < len(ordered):
        match = ordered[index]
        next_index = index + 1
        while next_index < len(ordered):
            following = ordered[next_index]
            overlaps = match.offset <= _end(following) and _end(match) >= following.offset  # type: ignore[attr-defined]
            if not overlaps or match.rule_id != following.rule_id:  # type: ignore[attr-defined]
                break
            next_index += 1
        clean.append(match)
        index = next_index
    return clean


def _letters_and_digits(value: str) -> str:
    # Pinned Java iterates UTF-16 char values, so supplementary-plane code
    # points are seen as surrogates rather than letters/digits.
    return "".join(ch for ch in value if ord(ch) <= 0xFFFF and unicodedata.category(ch)[0] in {"L", "N"})


def _punctuation_only(match: object, text: str) -> bool:
    replacements = match.replacements  # type: ignore[attr-defined]
    if not replacements:
        return False
    original = match.original_error or text[match.offset:_end(match)]  # type: ignore[attr-defined]
    replacement = replacements[0]
    return replacement != original and _letters_and_digits(original) == _letters_and_digits(replacement)


def _java_split(value: str, separator: str) -> list[str]:
    """``String.split`` semantics: trailing empty strings are discarded."""
    parts = value.split(separator)
    while parts and parts[-1] == "":
        parts.pop()
    return parts


def _duplicate_adjacent_suggestion(previous: object, current: object) -> bool:
    prev_replacements = previous.replacements  # type: ignore[attr-defined]
    replacements = current.replacements  # type: ignore[attr-defined]
    if not prev_replacements or not replacements:
        return False
    previous_suggestion, suggestion = prev_replacements[0], replacements[0]
    current_utf16 = current.utf16_offset  # type: ignore[attr-defined]
    previous_utf16_end = previous.utf16_offset + previous.utf16_length  # type: ignore[attr-defined]
    if current_utf16 == previous_utf16_end and previous_suggestion.endswith(",") and suggestion.startswith(", "):
        return True
    # Pinned CleanOverlappingFilter tests ``indexOf(" ") > 0``, not ``contains``: a
    # suggestion whose only space is at index 0 -- notably the single-space
    # replacement of WHITESPACE_RULE -- is not a two-word suggestion.
    if suggestion.find(" ") <= 0 or previous_suggestion.find(" ") <= 0:
        return False
    previous_parts = _java_split(previous_suggestion, " ")
    parts = _java_split(suggestion, " ")
    return (
        current_utf16 == previous_utf16_end + 1
        and len(previous_parts) > 1
        and len(parts) > 1
        and previous_parts[1] == parts[0]
    )


def _effective_priority(match: object) -> int:
    priority = match.priority  # type: ignore[attr-defined]
    if "picky" in match.tags and priority != -(2**31):  # type: ignore[attr-defined]
        priority += _PICKY_PENALTY
    return priority


def clean_overlapping_filter(matches: Sequence[MatchT], text: str) -> list[MatchT]:
    """Port the observable open-source branch of LT 6.8 CleanOverlappingFilter.

    Premium hiding is deliberately absent: the shipped Russian XML and all
    Task-0011 native rules are open-source/non-premium.  Their correction-all
    flag is still carried and evaluated exactly where the upstream filter does.
    """
    if not matches:
        return []
    clean: list[MatchT] = []
    previous = matches[0]
    for current in matches[1:]:
        if current.offset < previous.offset:  # type: ignore[attr-defined]
            raise ValueError("match list must be ordered by start position")
        duplicate = _duplicate_adjacent_suggestion(previous, current)
        if current.offset >= _end(previous) and not duplicate:  # type: ignore[attr-defined]
            clean.append(previous)
            previous = current
            continue

        current_priority = _effective_priority(current)
        previous_priority = _effective_priority(previous)
        if _punctuation_only(current, text) and _punctuation_only(previous, text):
            current_included = current.included_in_errors_corrected_all_at_once  # type: ignore[attr-defined]
            previous_included = previous.included_in_errors_corrected_all_at_once  # type: ignore[attr-defined]
            if current_included and not previous_included and current_priority < previous_priority:
                current_priority = previous_priority + 1
            elif previous_included and not current_included and previous_priority < current_priority:
                previous_priority = current_priority + 1
        if current_priority == previous_priority:
            current_priority = current.utf16_length  # type: ignore[attr-defined]
            previous_priority = previous.utf16_length  # type: ignore[attr-defined]
        if current_priority == previous_priority:
            current_priority += 1
        if current_priority > previous_priority:
            previous = current
    clean.append(previous)
    return clean


def level_filter(matches: Sequence[MatchT], level: str = LEVEL_DEFAULT) -> list[MatchT]:
    """Port of the level predicate in pinned ``JLanguageTool.filterMatches``.

    Upstream ``isRuleActiveForLevelAndToneTags`` returns ``false`` — dropping the
    match — when the checking level is ``DEFAULT`` and the rule carries the ``picky``
    tag.  ``JLanguageTool.check(text)`` runs at ``DEFAULT``, so picky-tagged matches
    never reach a default whole-pipeline result.

    The upstream predicate continues with tone-tag handling, which is a no-op for
    Russian at the pinned revision: no Russian XML rule declares ``tone_tags`` and none
    is goal specific, so every Russian rule takes the early ``getToneTags().isEmpty()``
    return.  Only the level branch is modelled here.

    This filter runs before :func:`same_rule_group_filter`, exactly where the pinned
    stream pipeline places it, so a suppressed picky match can never influence group
    or overlap resolution.
    """
    if level == LEVEL_PICKY:
        return list(matches)
    return [
        match
        for match in matches
        if "picky" not in match.tags  # type: ignore[attr-defined]
    ]


def filter_rule_matches(
    matches: Sequence[MatchT], text: str, level: str = LEVEL_DEFAULT
) -> list[MatchT]:
    """Apply the pinned Russian post-execution filter sequence."""
    # Russian inherits identity language-dependent filters both before and
    # after overlapping cleanup at the pinned revision.
    return clean_overlapping_filter(
        same_rule_group_filter(level_filter(matches, level)), text
    )
