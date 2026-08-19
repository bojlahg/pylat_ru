"""src/pylat_ru/tokenization/srx.py

SRX 2.0 sentence segmentation engine faithfully implementing net.loomchild.segment 2.0.3
algorithm for LanguageTool Russian rules (ru_two and ru_one).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

import regex

from pylat_ru.tokenization.errors import (
    SRXFormatError,
    SRXRuleCompilationError,
    UnsupportedSRXFeatureError,
)

DEFAULT_MAX_LOOKBEHIND_LENGTH = 100

STAR_PATTERN = regex.compile(r"(?<=(?<!\\)(?:\\\\)*)\*")
PLUS_PATTERN = regex.compile(
    r"(?<=(?<!\\)(?:\\\\)*)(?<![\?\*\+]|\{[0-9],?[0-9]?\}?\})\+"
)
RANGE_PATTERN = regex.compile(r"(?<=(?<!\\)(?:\\\\)*)\{\s*([0-9]+)\s*,\s*\}")


def remove_block_quotes(pattern: str) -> str:
    r"""Replace \Q...\E block quotes with escaped individual characters."""
    result: List[str] = []
    quote = False
    prev_char = ""
    for ch in pattern:
        if quote:
            if prev_char == "\\" and ch == "E":
                quote = False
                if result and result[-1] == "\\":
                    result.pop()
                if result and result[-1] == "\\":
                    result.pop()
            else:
                result.append("\\")
                result.append(ch)
        else:
            if prev_char == "\\" and ch == "Q":
                quote = True
                if result and result[-1] == "\\":
                    result.pop()
            else:
                result.append(ch)
        prev_char = ch
    return "".join(result)


def finitize(pattern: str, max_length: int = DEFAULT_MAX_LOOKBEHIND_LENGTH) -> str:
    """Finitize unlimited length patterns for lookbehind constructs.

    Matches loomchild segment 2.0.3 Util.finitize() semantics.
    """
    if not pattern:
        return ""
    finite = remove_block_quotes(pattern)
    finite = STAR_PATTERN.sub(f"{{0,{max_length}}}", finite)
    finite = PLUS_PATTERN.sub(f"{{1,{max_length}}}", finite)
    finite = RANGE_PATTERN.sub(rf"{{\1,{max_length}}}", finite)
    return finite


def adapt_java_regex(pattern: str) -> str:
    """Convert Java inline regex flags to Python equivalents."""
    if not pattern:
        return ""
    p = pattern.replace("(?U)", "(?u)")
    p = p.replace("(?iU)", "(?iu)")
    p = p.replace("(?Ui)", "(?iu)")
    return p


@dataclass
class SRXRule:
    """Represents a single SRX rule definition with compiled patterns."""

    is_break: bool
    before_pattern_str: str
    after_pattern_str: str
    group_name: str
    rule_index: int
    before_pattern: Optional[regex.Pattern] = None
    after_pattern: Optional[regex.Pattern] = None
    finitized_before_str: str = ""

    def __post_init__(self) -> None:
        if self.before_pattern is None and self.before_pattern_str:
            adapted = adapt_java_regex(self.before_pattern_str)
            try:
                self.before_pattern = regex.compile(adapted)
            except Exception as e:
                raise SRXRuleCompilationError(
                    f"Failed to compile beforebreak regex in group {self.group_name} "
                    f"rule {self.rule_index}: {self.before_pattern_str!r} ({e})"
                ) from e

        if self.after_pattern is None and self.after_pattern_str:
            adapted = adapt_java_regex(self.after_pattern_str)
            try:
                self.after_pattern = regex.compile(adapted)
            except Exception as e:
                raise SRXRuleCompilationError(
                    f"Failed to compile afterbreak regex in group {self.group_name} "
                    f"rule {self.rule_index}: {self.after_pattern_str!r} ({e})"
                ) from e

        if not self.finitized_before_str and self.before_pattern_str:
            adapted = adapt_java_regex(self.before_pattern_str)
            self.finitized_before_str = finitize(adapted)


class SRXRuleMatcher:
    """Matcher for a specific break rule over a text buffer.

    Replicates Java Matcher.find() advancement semantics matching
    net.loomchild.segment.srx.RuleMatcher.
    """

    def __init__(self, rule: SRXRule, text: str) -> None:
        self.rule = rule
        self.text = text
        self.before_pattern = rule.before_pattern
        self.after_pattern = rule.after_pattern

        self.search_pos: int = 0
        self.found: bool = False
        self.start_pos: int = 0
        self.break_pos: int = 0
        self.end_pos: int = 0

    def reset(self, text: Optional[str] = None) -> None:
        """Reset matcher state and optionally update target text."""
        if text is not None:
            self.text = text
        self.search_pos = 0
        self.found = False
        self.start_pos = 0
        self.break_pos = 0
        self.end_pos = 0

    def find(self, start: Optional[int] = None) -> bool:
        """Find next match of before_pattern followed by after_pattern.

        Advances search position according to Java Matcher.find() semantics:
        - after non-empty match: continues from before_match.end()
        - after zero-width match: advances by 1 code point
        """
        if start is not None:
            self.search_pos = start
        self.found = False
        text = self.text
        text_len = len(text)

        while not self.found:
            if self.search_pos > text_len:
                break

            if self.before_pattern is not None:
                m_bb = self.before_pattern.search(text, self.search_pos)
                if m_bb is None:
                    break
                bb_start = m_bb.start()
                bb_end = m_bb.end()
            else:
                bb_start = self.search_pos
                bb_end = self.search_pos

            # Java Matcher advance semantics
            if bb_end > bb_start:
                self.search_pos = bb_end
            else:
                self.search_pos = bb_start + 1

            if self.after_pattern is not None:
                m_ab = self.after_pattern.match(text, bb_end)
                if m_ab is not None:
                    self.found = True
                    self.start_pos = bb_start
                    self.break_pos = bb_end
                    self.end_pos = m_ab.end()
            else:
                self.found = True
                self.start_pos = bb_start
                self.break_pos = bb_end
                self.end_pos = bb_end

        return self.found

    def get_break_position(self) -> int:
        """Return the position between beforebreak and afterbreak."""
        if not self.found:
            raise ValueError("No match found")
        return self.break_pos

    def get_start_position(self) -> int:
        """Return the start position of beforebreak match."""
        if not self.found:
            raise ValueError("No match found")
        return self.start_pos

    def get_end_position(self) -> int:
        """Return the end position of afterbreak match."""
        if not self.found:
            raise ValueError("No match found")
        return self.end_pos


class SRXRuleManager:
    """Manages active break rules and their compiled exception patterns.

    Faithful to net.loomchild.segment.srx.RuleManager.
    """

    def __init__(
        self,
        break_rules: Sequence[SRXRule],
        exception_patterns: Sequence[Optional[regex.Pattern]],
    ) -> None:
        if len(break_rules) != len(exception_patterns):
            raise ValueError("break_rules and exception_patterns length mismatch")
        self.break_rules = tuple(break_rules)
        self.exception_patterns = tuple(exception_patterns)

    @classmethod
    def from_rules(cls, rules: Sequence[SRXRule]) -> SRXRuleManager:
        """Build SRXRuleManager compiling cumulative lookbehind exception patterns."""
        break_rules: List[SRXRule] = []
        exception_patterns: List[Optional[regex.Pattern]] = []
        preceding_exceptions: List[SRXRule] = []

        for rule in rules:
            if not rule.is_break:
                preceding_exceptions.append(rule)
            else:
                break_rules.append(rule)
                if preceding_exceptions:
                    parts: List[str] = []
                    for ex in preceding_exceptions:
                        bb = ex.finitized_before_str
                        ab = adapt_java_regex(ex.after_pattern_str)
                        if bb and ab:
                            parts.append(f"(?<={bb})(?={ab})")
                        elif bb:
                            parts.append(f"(?<={bb})")
                        elif ab:
                            parts.append(f"(?={ab})")
                    if parts:
                        combined = "(?:" + "|".join(parts) + ")"
                        try:
                            compiled = regex.compile(combined)
                        except Exception as e:
                            raise SRXRuleCompilationError(
                                f"Failed to compile combined exception pattern: {combined!r} ({e})"
                            ) from e
                        exception_patterns.append(compiled)
                    else:
                        exception_patterns.append(None)
                else:
                    exception_patterns.append(None)

        return cls(break_rules, exception_patterns)


class SRXSegmenter:
    """Executes SRX segmentation matching loomchild SrxTextIterator algorithm."""

    def __init__(self, rule_manager: SRXRuleManager) -> None:
        self.rule_manager = rule_manager
        self.break_rules = rule_manager.break_rules
        self.exception_patterns = rule_manager.exception_patterns

    def segment(self, text: str) -> tuple[str, ...]:
        """Segment input text into a tuple of sentence strings."""
        if not text:
            return ()

        # Initialize matchers
        matchers: List[SRXRuleMatcher] = [
            SRXRuleMatcher(rule, text) for rule in self.break_rules
        ]
        for m in matchers:
            m.find()

        segments: List[str] = []
        segment_start = 0
        text_len = len(text)

        while segment_start < text_len:
            # Find the active matcher with lowest break_position
            min_matcher_idx: Optional[int] = None
            min_break_pos = text_len + 1

            for idx, m in enumerate(matchers):
                if m.found and m.break_pos < min_break_pos:
                    min_break_pos = m.break_pos
                    min_matcher_idx = idx

            if min_matcher_idx is None:
                # No more breaks found; emit remainder
                segments.append(text[segment_start:])
                break

            break_pos = min_break_pos
            exception_pat = self.exception_patterns[min_matcher_idx]

            # Check if break is suppressed by exception pattern
            is_suppressed = False
            if exception_pat is not None:
                m_ex = exception_pat.match(text, break_pos)
                if m_ex is not None:
                    is_suppressed = True

            if not is_suppressed:
                if break_pos > segment_start:
                    segments.append(text[segment_start:break_pos])
                    segment_start = break_pos

                # Advance matchers according to loomchild algorithm
                for m in matchers:
                    if m.found:
                        if m.start_pos < segment_start:
                            m.find(segment_start)
                        elif m.break_pos <= segment_start:
                            m.find()
            else:
                # Suppressed: advance the triggering matcher
                matchers[min_matcher_idx].find()

        return tuple(segments)

    tokenize = segment


_CACHED_RULE_MANAGERS: Dict[str, SRXRuleManager] = {}


def load_russian_srx_rule_manager(
    mode: str = "ru_two",
    rules_json_path: Optional[Path] = None,
) -> SRXRuleManager:
    """Load and cache pre-extracted Russian SRX rules with strict validation.

    Supported modes: 'ru_two' (default), 'ru_one' (single-line paragraph).
    """
    if mode in _CACHED_RULE_MANAGERS and rules_json_path is None:
        return _CACHED_RULE_MANAGERS[mode]

    if rules_json_path is not None:
        if not rules_json_path.is_file():
            raise SRXFormatError(f"SRX rules file not found: {rules_json_path}")
        raw_json = rules_json_path.read_text(encoding="utf-8")
    else:
        try:
            raw_json = resources.files("pylat_ru.resources").joinpath("russian_srx_rules.json").read_text(encoding="utf-8")
        except Exception as e:
            raise SRXFormatError(f"Failed to read packaged russian_srx_rules.json: {e}") from e

    try:
        data = json.loads(raw_json)
    except Exception as e:
        raise SRXFormatError(f"Malformed JSON in SRX rules: {e}") from e

    # Strict metadata and structural validation
    if not isinstance(data, dict):
        raise SRXFormatError("SRX rules JSON root must be an object")

    required_top_keys = {"metadata", "configurations", "groups"}
    missing_top = required_top_keys - set(data.keys())
    if missing_top:
        raise SRXFormatError(f"SRX rules missing required top-level keys: {missing_top}")

    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        raise SRXFormatError("SRX rules metadata must be an object")

    required_meta = {"languagetool_commit", "languagetool_tag", "loomchild_version", "source_sha256"}
    missing_meta = required_meta - set(metadata.keys())
    if missing_meta:
        raise SRXFormatError(f"SRX rules metadata missing required keys: {missing_meta}")

    configs = data.get("configurations")
    if not isinstance(configs, dict):
        raise SRXFormatError("SRX rules configurations must be an object")

    if mode not in configs:
        raise UnsupportedSRXFeatureError(
            f"Unsupported SRX Russian configuration mode: {mode!r}. Available: {list(configs.keys())}"
        )

    config_data = configs[mode]
    if not isinstance(config_data, dict) or "rules" not in config_data:
        raise SRXFormatError(f"Configuration '{mode}' missing 'rules' array")

    raw_rules = config_data["rules"]
    if not isinstance(raw_rules, list):
        raise SRXFormatError(f"Rules for configuration '{mode}' must be a list")

    parsed_rules: List[SRXRule] = []
    for idx, r in enumerate(raw_rules):
        if not isinstance(r, dict):
            raise SRXFormatError(f"Rule {idx} in config '{mode}' is not an object")

        required_rule_keys = {"group", "rule_index", "break", "beforebreak", "afterbreak"}
        missing_rule = required_rule_keys - set(r.keys())
        if missing_rule:
            raise SRXFormatError(f"Rule {idx} in config '{mode}' missing keys: {missing_rule}")

        break_val = r["break"]
        if break_val not in ("yes", "no"):
            raise SRXFormatError(f"Rule {idx} in config '{mode}' has invalid break value: {break_val!r}")

        is_break = break_val == "yes"
        group_name = str(r["group"])
        rule_idx = int(r["rule_index"])
        bb_str = str(r["beforebreak"])
        ab_str = str(r["afterbreak"])

        parsed_rules.append(
            SRXRule(
                is_break=is_break,
                before_pattern_str=bb_str,
                after_pattern_str=ab_str,
                group_name=group_name,
                rule_index=rule_idx,
            )
        )

    mgr = SRXRuleManager.from_rules(parsed_rules)
    if rules_json_path is None:
        _CACHED_RULE_MANAGERS[mode] = mgr
    return mgr
