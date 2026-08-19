"""src/pylat_ru/tokenization/srx.py

SRX 2.0 / loomchild 2.0.3 sentence segmentation engine for Russian LanguageTool.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import regex

from pylat_ru.tokenization.errors import (
    SRXFormatError,
    SRXRuleCompilationError,
    UnsupportedSRXFeatureError,
)
from pylat_ru.tokenization.offsets import (
    SentenceSpan,
    Utf16CodePointMapper,
    sentences_to_spans,
)

DEFAULT_RULES_RESOURCE_NAME = "russian_srx_rules.json"


def adapt_java_regex(pattern: str) -> str:
    """Adapt Java regex syntax for Python regex engine.

    Converts Java flags such as (?U) (Pattern.UNICODE_CHARACTER_CLASS)
    to Python inline unicode flag (?u).
    """
    if not pattern:
        return ""
    p = pattern.replace("(?U)", "(?u)")
    p = p.replace("(?iU)", "(?iu)")
    p = p.replace("(?Ui)", "(?iu)")
    return p


class SRXRule:
    """Represents a single SRX break or exception rule."""

    def __init__(
        self,
        is_break: bool,
        before_pattern_str: str,
        after_pattern_str: str,
        group_name: str = "",
        rule_index: int = 0,
    ) -> None:
        self.is_break = is_break
        self.before_pattern_str = before_pattern_str
        self.after_pattern_str = after_pattern_str
        self.group_name = group_name
        self.rule_index = rule_index

        self.before_adapted = adapt_java_regex(before_pattern_str)
        self.after_adapted = adapt_java_regex(after_pattern_str)

        try:
            self.before_pattern = (
                regex.compile(self.before_adapted) if self.before_adapted else None
            )
        except Exception as e:
            raise SRXRuleCompilationError(
                f"Failed to compile beforebreak pattern for {group_name} R{rule_index}: "
                f"{self.before_adapted!r} ({e})"
            ) from e

        try:
            self.after_pattern = (
                regex.compile(self.after_adapted) if self.after_adapted else None
            )
        except Exception as e:
            raise SRXRuleCompilationError(
                f"Failed to compile afterbreak pattern for {group_name} R{rule_index}: "
                f"{self.after_adapted!r} ({e})"
            ) from e

    def __repr__(self) -> str:
        brk = "yes" if self.is_break else "no"
        return (
            f"SRXRule({self.group_name} R{self.rule_index} break={brk} "
            f"bb={self.before_adapted!r}, ab={self.after_adapted!r})"
        )


class SRXRuleMatcher:
    """Finds subsequent occurrences of a single break rule in a text."""

    def __init__(self, rule: SRXRule, text: str) -> None:
        self.rule = rule
        self.text = text
        self.found = False
        self.start_pos = 0
        self.break_pos = 0
        self.end_pos = 0
        self.search_pos = 0

    def find(self, start: Optional[int] = None) -> bool:
        """Find next match of rule after search_pos (or explicit start)."""
        if start is not None:
            self.search_pos = start
        self.found = False
        text_len = len(self.text)

        while self.search_pos <= text_len:
            if self.rule.before_pattern is not None:
                m_bb = self.rule.before_pattern.search(self.text, self.search_pos)
                if not m_bb:
                    break
                bb_start = m_bb.start()
                bb_end = m_bb.end()
            else:
                bb_start = self.search_pos
                bb_end = self.search_pos

            # Check afterbreak starting at bb_end
            if self.rule.after_pattern is not None:
                m_ab = self.rule.after_pattern.match(self.text, bb_end)
                if m_ab:
                    self.start_pos = bb_start
                    self.break_pos = bb_end
                    self.end_pos = m_ab.end()
                    self.found = True
                    self.search_pos = bb_start + 1
                    return True
            else:
                self.start_pos = bb_start
                self.break_pos = bb_end
                self.end_pos = bb_end
                self.found = True
                self.search_pos = bb_start + 1
                return True

            if self.rule.before_pattern is not None:
                self.search_pos = bb_start + 1
            else:
                self.search_pos += 1

        return False

    def hit_end(self) -> bool:
        return not self.found


class SRXRuleManager:
    """Manages the ordered break rules and cumulative exception patterns for a configuration."""

    def __init__(self, rules: Sequence[SRXRule]) -> None:
        self.break_rules: List[SRXRule] = []
        self.exception_patterns: Dict[SRXRule, Optional[regex.Pattern]] = {}

        exc_parts: List[str] = []

        for rule in rules:
            if rule.is_break:
                self.break_rules.append(rule)
                if exc_parts:
                    exc_str = "|".join(exc_parts)
                    try:
                        exc_pat = regex.compile(exc_str)
                    except Exception as e:
                        raise SRXRuleCompilationError(
                            f"Failed to compile combined exception pattern for {rule}: {exc_str!r} ({e})"
                        ) from e
                else:
                    exc_pat = None
                self.exception_patterns[rule] = exc_pat
            else:
                part = "(?:"
                if rule.before_adapted:
                    part += f"(?<={rule.before_adapted})"
                if rule.after_adapted:
                    part += f"(?={rule.after_adapted})"
                part += ")"
                exc_parts.append(part)

    def is_break_valid(self, matcher: SRXRuleMatcher, text: str) -> bool:
        """Return True if break position is NOT suppressed by preceding exception rules."""
        exc_pat = self.exception_patterns.get(matcher.rule)
        if exc_pat is None:
            return True
        # If exc_pat matches at break_pos, an exception applies (suppressing break)
        is_exception = exc_pat.match(text, matcher.break_pos) is not None
        return not is_exception


class SRXSegmenter:
    """Performs SRX sentence segmentation following loomchild 2.0.3 semantics."""

    def __init__(self, rule_manager: SRXRuleManager) -> None:
        self.rule_manager = rule_manager

    def tokenize(self, text: str) -> tuple[str, ...]:
        """Split text into sentence strings with exact whitespace and delimiter preservation."""
        if not text:
            return ()

        # Initialize matchers
        matchers: List[SRXRuleMatcher] = []
        for r in self.rule_manager.break_rules:
            m = SRXRuleMatcher(r, text)
            if m.find():
                matchers.append(m)

        segments: List[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            found_split = False
            end = text_len

            while not found_split:
                # Find matcher with minimal break_pos
                min_pos = 10**9
                min_matcher: Optional[SRXRuleMatcher] = None
                for m in matchers:
                    if m.break_pos < min_pos:
                        min_pos = m.break_pos
                        min_matcher = m

                if min_matcher is None:
                    found_split = True
                    end = text_len
                else:
                    end = min_matcher.break_pos
                    if end > start:
                        if self.rule_manager.is_break_valid(min_matcher, text):
                            found_split = True
                            # Cut matchers that start before this boundary
                            new_matchers = []
                            for m in matchers:
                                if m.start_pos < end:
                                    if m.find(end):
                                        new_matchers.append(m)
                                else:
                                    new_matchers.append(m)
                            matchers = new_matchers

                    # Advance matchers with break_pos <= end
                    new_matchers = []
                    for m in matchers:
                        while m.break_pos <= end:
                            if not m.find():
                                break
                        if m.found:
                            new_matchers.append(m)
                    matchers = new_matchers

            segments.append(text[start:end])
            start = end

        return tuple(segments)

    def tokenize_spans(self, text: str) -> tuple[SentenceSpan, ...]:
        """Split text into SentenceSpans with exact code-point and UTF-16 source offsets."""
        if not text:
            return ()
        sentences = self.tokenize(text)
        mapper = Utf16CodePointMapper(text)
        return sentences_to_spans(sentences, mapper=mapper)


# Cached singleton managers
_CACHE_RULE_MANAGERS: Dict[str, SRXRuleManager] = {}


def load_russian_srx_rule_manager(
    mode: str = "ru_two",
    rules_json_path: Optional[Path] = None,
) -> SRXRuleManager:
    """Load and compile the SRXRuleManager for Russian (ru_two or ru_one)."""
    cache_key = f"{mode}:{str(rules_json_path)}"
    if cache_key in _CACHE_RULE_MANAGERS:
        return _CACHE_RULE_MANAGERS[cache_key]

    if rules_json_path is not None:
        if not rules_json_path.is_file():
            raise SRXFormatError(f"SRX rules file not found: {rules_json_path}")
        raw_data = json.loads(rules_json_path.read_text(encoding="utf-8"))
    else:
        try:
            # Load from package resources
            ref = resources.files("pylat_ru.resources").joinpath(
                DEFAULT_RULES_RESOURCE_NAME
            )
            raw_data = json.loads(ref.read_text(encoding="utf-8"))
        except Exception as e:
            # Fallback to relative path if not installed as package
            fallback = (
                Path(__file__).resolve().parent.parent
                / "resources"
                / DEFAULT_RULES_RESOURCE_NAME
            )
            if fallback.is_file():
                raw_data = json.loads(fallback.read_text(encoding="utf-8"))
            else:
                raise SRXFormatError(
                    f"Could not load embedded SRX rules resource: {e}"
                ) from e

    configs = raw_data.get("configurations", {})
    if mode not in configs:
        raise UnsupportedSRXFeatureError(
            f"Unsupported SRX Russian configuration mode: {mode!r} (valid: ru_two, ru_one)"
        )

    rule_dicts = configs[mode].get("rules", [])
    srx_rules: List[SRXRule] = []
    for r in rule_dicts:
        srx_rules.append(
            SRXRule(
                is_break=(r.get("break") == "yes"),
                before_pattern_str=r.get("beforebreak", ""),
                after_pattern_str=r.get("afterbreak", ""),
                group_name=r.get("group", ""),
                rule_index=r.get("rule_index", 0),
            )
        )

    manager = SRXRuleManager(srx_rules)
    _CACHE_RULE_MANAGERS[cache_key] = manager
    return manager
