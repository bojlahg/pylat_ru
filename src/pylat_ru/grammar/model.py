"""src/pylat_ru/grammar/model.py

Domain models for LanguageTool Russian grammar rules, XML patterns,
token predicates, match references, and engine findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Sequence, Tuple, Union


class ExecutionState(str, Enum):
    """Execution classification state for a grammar rule."""

    CORE_0007_RUNNABLE = "CORE_0007_RUNNABLE"
    ADVANCED_0008_RUNNABLE = "ADVANCED_0008_RUNNABLE"
    UNIFICATION_0009_RUNNABLE = "UNIFICATION_0009_RUNNABLE"
    FILTER_0010_RUNNABLE = "FILTER_0010_RUNNABLE"
    DEFERRED_0008_ADVANCED_MATCHING = "DEFERRED_0008_ADVANCED_MATCHING"
    DEFERRED_0009_UNIFICATION = "DEFERRED_0009_UNIFICATION"
    DEFERRED_0010_FILTER = "DEFERRED_0010_FILTER"
    DEFERRED_0012_SPELLING_OR_SUPPRESSION = "DEFERRED_0012_SPELLING_OR_SUPPRESSION"
    MULTI_BLOCKER = "MULTI_BLOCKER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RuleBlocker:
    """Explicit blocker preventing a rule from running in core 0007 engine."""

    feature: str
    target_task: str
    description: str = ""


@dataclass
class PatternTokenException:
    """Exception predicate inside a pattern token."""

    text: Optional[str] = None
    postag: Optional[str] = None
    postag_regexp: bool = False
    regexp: bool = False
    negate: bool = False
    negate_pos: bool = False
    inflected: bool = False
    case_sensitive: bool = False
    scope: str = "current"  # "current", "previous", "next"
    spacebefore: Optional[str] = None
    raw_pos: bool = False
    match: Optional[Any] = None  # MatchReference when token contains <match>


@dataclass
class PatternToken:
    """Atomic token matching descriptor in a grammar rule pattern."""

    text: Optional[str] = None
    postag: Optional[str] = None
    postag_regexp: bool = False
    regexp: bool = False
    negate: bool = False
    negate_pos: bool = False
    inflected: bool = False
    case_sensitive: bool = False
    skip: Optional[int] = None
    min: Optional[int] = None
    max: Optional[int] = None
    chunk: Optional[str] = None
    spacebefore: Optional[str] = None
    raw_pos: bool = False
    setpostag: Optional[str] = None
    exceptions: List[PatternTokenException] = field(default_factory=list)
    match: Optional[Any] = None  # MatchReference when token contains <match>
    is_in_marker: bool = False
    and_elements: List[Any] = field(default_factory=list)
    uni_features: Dict[str, List[str]] = field(default_factory=dict)
    is_unify: bool = False
    is_unify_negated: bool = False
    is_unify_neutral: bool = False
    is_last_in_unify: bool = False


@dataclass
class PatternAnd:
    """Logical AND construct inside a pattern."""

    elements: List[Any] = field(default_factory=list)
    exceptions: List[PatternTokenException] = field(default_factory=list)
    is_in_marker: bool = False


@dataclass
class PatternOr:
    """Logical OR construct inside a pattern."""

    elements: List[Any] = field(default_factory=list)
    is_in_marker: bool = False


@dataclass
class PatternUnify:
    """Unification construct inside a pattern."""

    negate: bool = False
    feature: Optional[str] = None
    features: List[FeatureDef] = field(default_factory=list)
    equivalences: List[EquivalenceDef] = field(default_factory=list)
    elements: List[Any] = field(default_factory=list)
    is_in_marker: bool = False


@dataclass
class PatternUnifyIgnore:
    """Unification ignore construct inside a pattern."""

    elements: List[Any] = field(default_factory=list)
    is_in_marker: bool = False


@dataclass
class PatternPhrase:
    """Phrase reference or inline phrase definition inside a pattern."""

    id: Optional[str] = None
    ref: Optional[str] = None
    raw_pos: bool = False
    elements: List[Any] = field(default_factory=list)
    is_in_marker: bool = False


PatternElement = Union[
    PatternToken,
    PatternAnd,
    PatternOr,
    PatternUnify,
    PatternUnifyIgnore,
    PatternPhrase,
]


@dataclass
class Pattern:
    """Complete token sequence pattern for a grammar rule or antipattern."""

    elements: List[PatternElement] = field(default_factory=list)
    tokens: List[PatternToken] = field(default_factory=list)
    case_sensitive: bool = False
    raw_pos: bool = False
    has_marker: bool = False
    marker_start_idx: Optional[int] = None  # 0-indexed token index in pattern.tokens
    marker_end_idx: Optional[int] = None    # exclusive index


@dataclass(frozen=True)
class MatchReference:
    """Dynamic reference to a matched pattern token inside message or suggestion."""

    no: int  # 1-indexed token index
    case_conversion: Optional[str] = None
    include_skipped: Optional[str] = None
    postag: Optional[str] = None
    postag_regexp: Optional[str] = None
    postag_replace: Optional[str] = None
    setpos: Optional[str] = None
    regexp_match: Optional[str] = None
    regexp_replace: Optional[str] = None
    sub_type: Optional[str] = None
    lemma: Optional[str] = None


@dataclass(frozen=True)
class FilterConfig:
    """Java filter class and arguments configured on a rule."""

    class_name: str
    args: Optional[str] = None


@dataclass
class FeatureDef:
    """Feature definition inside XML unification or local selection inside <unify>."""

    name: str
    types: List[str] = field(default_factory=list)
    tokens: List[PatternToken] = field(default_factory=list)


@dataclass
class EquivalenceDef:
    """Equivalence definition inside XML unification."""

    type: Optional[str] = None
    tokens: List[PatternToken] = field(default_factory=list)


@dataclass
class UnificationDef:
    """Unification container definition from XML."""

    feature: Optional[str] = None
    features: List[FeatureDef] = field(default_factory=list)
    equivalences: List[EquivalenceDef] = field(default_factory=list)


@dataclass
class MessageTemplate:
    """Structured message template with text segments and match references."""

    elements: List[Union[str, MatchReference]] = field(default_factory=list)
    suppress_misspelled: bool = False


@dataclass
class SuggestionTemplate:
    """Structured suggestion template with text segments and match references."""

    elements: List[Union[str, MatchReference]] = field(default_factory=list)
    suppress_misspelled: bool = False


@dataclass
class Example:
    """Executable example from grammar.xml."""

    text: str
    is_incorrect: bool
    correction: Optional[str] = None
    marker_spans: List[Tuple[int, int]] = field(default_factory=list)
    reason: Optional[str] = None


@dataclass
class GrammarRule:
    """Full representation of an XML pattern rule from grammar.xml."""

    id: str
    sub_id: Optional[str]
    full_id: str
    name: str
    category_id: str
    category_name: str
    rulegroup_id: Optional[str]
    rulegroup_name: Optional[str]
    default_off: bool
    tags: List[str]
    source_order_index: int
    pattern: Pattern
    antipatterns: List[Pattern] = field(default_factory=list)
    filters: List[FilterConfig] = field(default_factory=list)
    unifications: List[UnificationDef] = field(default_factory=list)
    message_template: MessageTemplate = field(default_factory=MessageTemplate)
    short_message: Optional[str] = None
    suggestions: List[SuggestionTemplate] = field(default_factory=list)
    examples: List[Example] = field(default_factory=list)
    url: Optional[str] = None
    rule_type: Optional[str] = None
    prio: Optional[int] = None
    tone_tags: List[str] = field(default_factory=list)
    is_goal_specific: bool = False
    tab: Optional[str] = None
    tabname: Optional[str] = None
    premium: bool = False
    minprevmatches: Optional[int] = None
    distancetokens: Optional[int] = None
    execution_state: ExecutionState = ExecutionState.CORE_0007_RUNNABLE
    blockers: List[RuleBlocker] = field(default_factory=list)


@dataclass
class RuleMatchResult:
    """Finding produced by executing a GrammarRule on an AnalyzedSentence."""

    rule_id: str
    full_rule_id: str
    category_id: str
    category_name: str
    description: str
    message: str
    short_message: Optional[str]
    suggestions: List[str]
    from_pos: int                  # Python Unicode character start offset (marker span)
    to_pos: int                    # Python Unicode character end offset (marker span)
    from_pos_utf16: int            # Java UTF-16 code unit start offset (marker span)
    to_pos_utf16: int              # Java UTF-16 code unit end offset (marker span)
    pattern_from_pos: int          # Python Unicode character start offset (full pattern span)
    pattern_to_pos: int            # Python Unicode character end offset (full pattern span)
    pattern_from_pos_utf16: int    # Java UTF-16 code unit start offset (full pattern span)
    pattern_to_pos_utf16: int      # Java UTF-16 code unit end offset (full pattern span)
    matched_tokens_indices: List[int]
    marker_tokens_indices: List[int]
    url: Optional[str] = None
