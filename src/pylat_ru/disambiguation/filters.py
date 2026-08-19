"""Disambiguation XML filter implementations matching LanguageTool."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Pattern, Sequence, Union

from pylat_ru.analysis import AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.disambiguation.errors import DisambiguationFilterError
from pylat_ru.tagging.russian import RussianTagger


class DisambiguationFilter(ABC):
    """Abstract base class for XML rule disambiguation filters."""

    @abstractmethod
    def matches(
        self,
        args: Dict[str, str],
        tokens: Sequence[AnalyzedTokenReadings],
        first_match_token: int,
        token_positions: Sequence[int],
    ) -> bool:
        """Evaluate filter against matched token sequence."""


class NoDisambiguationRussianPartialPosTagFilter(DisambiguationFilter):
    """Filters rule matches by checking POS tags of a sub-token via raw RussianTagger.

    Port of org.languagetool.rules.ru.NoDisambiguationRussianPartialPosTagFilter.
    Splits hyphenated compounds using regex group extraction and performs raw tagger
    lookup without disambiguation recursion.
    """

    def __init__(self, tagger: Optional[RussianTagger] = None) -> None:
        self.tagger = tagger or RussianTagger.get_instance()

    def parse_args(self, args_str: str) -> Dict[str, str]:
        """Parse 'key:value' space-separated argument string."""
        res: Dict[str, str] = {}
        tokens = args_str.strip().split()
        for token in tokens:
            if ":" not in token:
                raise DisambiguationFilterError(
                    f"Invalid syntax for filter argument, expected 'key:value', got: '{token}'"
                )
            key, val = token.split(":", 1)
            res[key.strip()] = val.strip()
        return res

    def matches(
        self,
        args: Union[Dict[str, str], str],
        tokens: Sequence[AnalyzedTokenReadings],
        first_match_token: int,
        token_positions: Sequence[int],
    ) -> bool:
        """Check if partial token matches required POS tag regex."""
        resolved_args = self.parse_args(args) if isinstance(args, str) else args

        if "no" not in resolved_args or "regexp" not in resolved_args or "postag_regexp" not in resolved_args:
            raise DisambiguationFilterError(
                "NoDisambiguationRussianPartialPosTagFilter requires 'no', 'regexp', and 'postag_regexp'"
            )

        token_pos = int(resolved_args["no"])
        regex_pattern = resolved_args["regexp"]
        required_tag_pattern = resolved_args["postag_regexp"]
        negate_pos = resolved_args.get("negate_pos", "no").lower() in ("yes", "true", "1")
        two_groups = resolved_args.get("two_groups_regexp", "no").lower() in ("yes", "true", "1")

        prefix = resolved_args.get("prefix", "")
        suffix = resolved_args.get("suffix", "")

        if token_pos - 1 >= len(tokens):
            return False

        target_token_str = prefix + tokens[token_pos - 1].token + suffix
        regex = re.compile(regex_pattern)
        m = regex.fullmatch(target_token_str)
        if m is None:
            return False

        if not two_groups and m.lastindex != 1:
            raise DisambiguationFilterError(
                f"Got {m.lastindex} groups for regex '{regex_pattern}', expected 1"
            )
        if two_groups and m.lastindex != 2:
            raise DisambiguationFilterError(
                f"Got {m.lastindex} groups for regex '{regex_pattern}', expected 2"
            )

        partial_token = m.group(1)
        if two_groups and m.lastindex == 2:
            partial_token += m.group(2)

        # Raw RussianTagger lookup without disambiguation
        tags = self.tagger.tag([partial_token])
        if not tags:
            return False

        tag_regex = re.compile(required_tag_pattern)
        postag_count = 0

        for tag_reading in tags:
            for reading in tag_reading.readings:
                if reading.pos_tag is not None:
                    postag_count += 1
                    matches_tag = tag_regex.fullmatch(reading.pos_tag) is not None
                    if negate_pos:
                        if matches_tag:
                            return False
                    else:
                        if matches_tag:
                            return True

        if postag_count == 0:
            return False
        return negate_pos
