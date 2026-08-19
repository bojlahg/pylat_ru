"""src/pylat_ru/grammar/engine.py

Core XML Grammar Engine for LanguageTool Russian rules.
Executes compiled pattern rules over AnalyzedSentence tokens to produce structured findings.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set, Tuple, Union

from pylat_ru.analysis import AnalyzedSentence, AnalyzedTokenReadings
from pylat_ru.grammar.classifier import classify_rule_element
from pylat_ru.grammar.errors import (
    GrammarError,
    GrammarRuleDisabledError,
    UnsupportedGrammarFeatureError,
)
from pylat_ru.grammar.formatter import TemplateFormatter
from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.matcher import CompiledPattern
from pylat_ru.grammar.model import (
    ExecutionState,
    GrammarRule,
    RuleMatchResult,
)


def _compute_utf16_offsets(text: str, char_from: int, char_to: int) -> Tuple[int, int]:
    """Compute Java-compatible UTF-16 code unit offsets from Python character offsets."""
    prefix = text[:char_from]
    span = text[char_from:char_to]
    utf16_from = len(prefix.encode("utf-16-le")) // 2
    utf16_to = utf16_from + (len(span.encode("utf-16-le")) // 2)
    return utf16_from, utf16_to


class RussianGrammarEngine:
    """Core rule engine executing LanguageTool Russian grammar rules."""

    _default_instance: Optional[RussianGrammarEngine] = None

    def __init__(self, rules: Optional[Sequence[GrammarRule]] = None) -> None:
        if rules is None:
            loader = GrammarLoader()
            rules = loader.load_default()

        self._all_rules: List[GrammarRule] = list(rules)
        self._rules_by_id: Dict[str, GrammarRule] = {}
        self._rules_by_full_id: Dict[str, GrammarRule] = {}
        self._compiled_patterns: Dict[str, CompiledPattern] = {}
        self._disabled_rules: Set[str] = set()

        for r in self._all_rules:
            self._rules_by_full_id[r.full_id] = r
            self._rules_by_id.setdefault(r.id, r)
            if r.default_off:
                self._disabled_rules.add(r.full_id)

            if r.execution_state == ExecutionState.CORE_0007_RUNNABLE:
                self._compiled_patterns[r.full_id] = CompiledPattern(r.pattern)

    @classmethod
    def get_instance(cls) -> RussianGrammarEngine:
        """Get or create singleton default grammar engine instance."""
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def get_all_rules(self) -> List[GrammarRule]:
        """Return all loaded rules."""
        return list(self._all_rules)

    def get_runnable_rules(self) -> List[GrammarRule]:
        """Return all rules eligible for execution in core 0007 engine."""
        return [
            r for r in self._all_rules if r.execution_state == ExecutionState.CORE_0007_RUNNABLE
        ]

    def get_rule(self, rule_id_or_full_id: str) -> Optional[GrammarRule]:
        """Lookup rule by full_id (e.g. 'zadat_test[1]') or base id ('zadat_test')."""
        if rule_id_or_full_id in self._rules_by_full_id:
            return self._rules_by_full_id[rule_id_or_full_id]
        return self._rules_by_id.get(rule_id_or_full_id)

    def is_rule_enabled(self, full_id: str) -> bool:
        """Return True if rule is currently enabled."""
        return full_id not in self._disabled_rules

    def enable_rule(self, full_id: str) -> None:
        """Enable a rule."""
        self._disabled_rules.discard(full_id)

    def disable_rule(self, full_id: str) -> None:
        """Disable a rule."""
        self._disabled_rules.add(full_id)

    def check_rule(
        self,
        sentence: AnalyzedSentence,
        rule_or_id: Union[str, GrammarRule],
    ) -> List[RuleMatchResult]:
        """Execute a specific rule on an AnalyzedSentence."""
        if isinstance(rule_or_id, str):
            rule = self.get_rule(rule_or_id)
            if rule is None:
                raise GrammarError(f"Rule not found: {rule_or_id}")
        else:
            rule = rule_or_id

        if rule.execution_state != ExecutionState.CORE_0007_RUNNABLE:
            blocker_desc = ", ".join(f"{b.feature} (task {b.target_task})" for b in rule.blockers)
            raise UnsupportedGrammarFeatureError(
                f"Rule {rule.full_id} is deferred: {blocker_desc}",
                feature=rule.blockers[0].feature if rule.blockers else "",
                rule_id=rule.full_id,
            )

        compiled = self._compiled_patterns.get(rule.full_id)
        if compiled is None:
            compiled = CompiledPattern(rule.pattern)
            self._compiled_patterns[rule.full_id] = compiled

        return self._execute_rule(sentence, rule, compiled)

    def check_sentence(
        self,
        sentence: AnalyzedSentence,
        include_disabled: bool = False,
    ) -> List[RuleMatchResult]:
        """Execute all core-runnable rules on an AnalyzedSentence."""
        results: List[RuleMatchResult] = []

        for rule in self.get_runnable_rules():
            if not include_disabled and not self.is_rule_enabled(rule.full_id):
                continue
            compiled = self._compiled_patterns.get(rule.full_id)
            if compiled is None:
                continue
            rule_matches = self._execute_rule(sentence, rule, compiled)
            results.extend(rule_matches)

        return results

    def _execute_rule(
        self,
        sentence: AnalyzedSentence,
        rule: GrammarRule,
        compiled: CompiledPattern,
    ) -> List[RuleMatchResult]:
        """Match compiled rule against sentence non-blank tokens."""
        non_blank_tokens = [
            t for t in sentence.tokens if t.has_pos_tag("SENT_START") or (t.token and not t.is_whitespace())
        ]
        if not non_blank_tokens:
            return []

        results: List[RuleMatchResult] = []
        token_count = len(non_blank_tokens)
        text_full = sentence.text if hasattr(sentence, "text") and sentence.text else ""

        for start_idx in range(token_count):
            match_span = compiled.match_at(non_blank_tokens, start_idx)
            if match_span is None:
                continue

            match_start, match_end, error_start, error_end = match_span

            # Matched token objects
            matched_tokens = non_blank_tokens[match_start:match_end]
            error_tokens = non_blank_tokens[error_start:error_end]

            # Compute character offsets
            from_tok = non_blank_tokens[error_start]
            to_tok = non_blank_tokens[error_end - 1]
            from_pos = from_tok.start_pos
            to_pos = to_tok.start_pos + len(to_tok.token)

            from_utf16 = from_pos
            to_utf16 = to_pos

            # Format message and suggestions
            message = TemplateFormatter.format_message(rule.message_template, matched_tokens)
            suggestions = [
                TemplateFormatter.format_suggestion(sug_tmpl, matched_tokens, error_tokens)
                for sug_tmpl in rule.suggestions
            ]

            match_res = RuleMatchResult(
                rule_id=rule.id,
                full_rule_id=rule.full_id,
                category_id=rule.category_id,
                category_name=rule.category_name,
                description=rule.name,
                message=message,
                short_message=rule.short_message,
                suggestions=suggestions,
                from_pos=from_pos,
                to_pos=to_pos,
                from_pos_utf16=from_utf16,
                to_pos_utf16=to_utf16,
                matched_tokens_indices=list(range(match_start, match_end)),
                marker_tokens_indices=list(range(error_start, error_end)),
            )
            results.append(match_res)

        return results
