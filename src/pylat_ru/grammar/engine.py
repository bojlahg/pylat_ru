"""src/pylat_ru/grammar/engine.py

Core XML Grammar Engine for LanguageTool Russian rules.
Executes compiled pattern rule variants over AnalyzedSentence tokens to produce structured findings.
Supports Core 0007 and Advanced 0008 pattern matching rules.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set, Tuple, Union
import regex

from pylat_ru.analysis import AnalyzedSentence, AnalyzedTokenReadings
from pylat_ru.grammar.classifier import classify_rule_element
from pylat_ru.grammar.errors import (
    GrammarError,
    GrammarRuleDisabledError,
    UnsupportedGrammarFeatureError,
)
from pylat_ru.grammar.formatter import TemplateFormatter, uppercase_first_char
from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.matcher import (
    CompiledRuleVariant,
    MatchStateResult,
    expand_rule_into_variants,
    filter_subsumed_rule_matches,
)
from pylat_ru.grammar.model import (
    ExecutionState,
    GrammarRule,
    MatchReference,
    RuleMatchResult,
)
from pylat_ru.synthesis.synthesizer import RussianSynthesizer


def _utf16_len(s: Optional[str]) -> int:
    """Return length in UTF-16 code units."""
    if not s:
        return 0
    return len(s.encode("utf-16-le")) // 2


def _utf16_to_codepoint_offset(text: str, utf16_offset: int) -> int:
    """Convert Java UTF-16 code unit offset to Python character (codepoint) offset."""
    if not text or utf16_offset <= 0:
        return 0
    encoded = text.encode("utf-16-le")
    byte_offset = utf16_offset * 2
    if byte_offset >= len(encoded):
        return len(text)
    sub = encoded[:byte_offset]
    return len(sub.decode("utf-16-le"))


def _compute_utf16_offsets(text: str, char_from: int, char_to: int) -> Tuple[int, int]:
    """Compute Java-compatible UTF-16 code unit offsets from Python character offsets."""
    prefix = text[:char_from]
    span = text[char_from:char_to]
    utf16_from = len(prefix.encode("utf-16-le")) // 2
    utf16_to = utf16_from + (len(span.encode("utf-16-le")) // 2)
    return utf16_from, utf16_to


class RussianGrammarEngine:
    """Rule engine executing LanguageTool Russian grammar rules."""

    _default_instance: Optional[RussianGrammarEngine] = None

    def __init__(
        self,
        rules: Optional[Sequence[GrammarRule]] = None,
        synthesizer: Optional[RussianSynthesizer] = None,
        loader: Optional[GrammarLoader] = None,
    ) -> None:
        if rules is None:
            gloader = loader or GrammarLoader()
            rules = gloader.load_default()
            self._loader = gloader
        else:
            self._loader = loader or GrammarLoader()

        self._synthesizer = synthesizer or RussianSynthesizer.get_instance()
        self._all_rules: List[GrammarRule] = list(rules)
        self._rules_by_id: Dict[str, GrammarRule] = {}
        self._rules_by_full_id: Dict[str, GrammarRule] = {}
        self._compiled_variants: Dict[str, List[CompiledRuleVariant]] = {}
        self._disabled_rules: Set[str] = set()

        for r in self._all_rules:
            self._rules_by_full_id[r.full_id] = r
            self._rules_by_id.setdefault(r.id, r)
            if r.default_off:
                self._disabled_rules.add(r.full_id)

            if r.execution_state in (
                ExecutionState.CORE_0007_RUNNABLE,
                ExecutionState.ADVANCED_0008_RUNNABLE,
                ExecutionState.UNIFICATION_0009_RUNNABLE,
                ExecutionState.FILTER_0010_RUNNABLE,
            ):
                variants = expand_rule_into_variants(r, self._loader.global_phrases, self._loader.unifier_config)
                self._compiled_variants[r.full_id] = variants

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
        """Return all rules eligible for execution in 0007 core + 0008 advanced + 0009 unification engine."""
        return [
            r
            for r in self._all_rules
            if r.execution_state in (
                ExecutionState.CORE_0007_RUNNABLE,
                ExecutionState.ADVANCED_0008_RUNNABLE,
                ExecutionState.UNIFICATION_0009_RUNNABLE,
                ExecutionState.FILTER_0010_RUNNABLE,
            )
        ]

    def get_rule(self, rule_id_or_full_id: str) -> Optional[GrammarRule]:
        """Lookup rule by full_id (e.g. 'zadat_test[1]') or base id ('zadat_test')."""
        if rule_id_or_full_id in self._rules_by_full_id:
            return self._rules_by_full_id[rule_id_or_full_id]
        return self._rules_by_id.get(rule_id_or_full_id)

    def _resolve_full_ids(self, rule_id_or_full_id: str) -> List[str]:
        if rule_id_or_full_id in self._rules_by_full_id:
            return [rule_id_or_full_id]
        matched = [
            r.full_id
            for r in self._all_rules
            if r.id == rule_id_or_full_id or r.rulegroup_id == rule_id_or_full_id
        ]
        return matched if matched else [rule_id_or_full_id]

    def is_rule_enabled(self, rule_id_or_full_id: str) -> bool:
        """Return True if rule (or all rules in group) is currently enabled."""
        full_ids = self._resolve_full_ids(rule_id_or_full_id)
        return all(fid not in self._disabled_rules for fid in full_ids)

    def enable_rule(self, rule_id_or_full_id: str) -> None:
        """Enable a rule or all rules in a rulegroup."""
        for fid in self._resolve_full_ids(rule_id_or_full_id):
            self._disabled_rules.discard(fid)

    def disable_rule(self, rule_id_or_full_id: str) -> None:
        """Disable a rule or all rules in a rulegroup."""
        for fid in self._resolve_full_ids(rule_id_or_full_id):
            self._disabled_rules.add(fid)

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

        if rule.execution_state not in (
            ExecutionState.CORE_0007_RUNNABLE,
            ExecutionState.ADVANCED_0008_RUNNABLE,
            ExecutionState.UNIFICATION_0009_RUNNABLE,
            ExecutionState.FILTER_0010_RUNNABLE,
        ):
            blocker_desc = ", ".join(f"{b.feature} (task {b.target_task})" for b in rule.blockers)
            raise UnsupportedGrammarFeatureError(
                f"Rule {rule.full_id} is deferred: {blocker_desc}",
                feature=rule.blockers[0].feature if rule.blockers else "",
                rule_id=rule.full_id,
            )

        variants = self._compiled_variants.get(rule.full_id)
        if variants is None:
            variants = expand_rule_into_variants(rule, self._loader.global_phrases, self._loader.unifier_config)
            self._compiled_variants[rule.full_id] = variants

        return self._execute_rule(sentence, rule, variants)

    def check_sentence(
        self,
        sentence: AnalyzedSentence,
        include_disabled: bool = False,
    ) -> List[RuleMatchResult]:
        """Execute all runnable rules on an AnalyzedSentence."""
        results: List[RuleMatchResult] = []

        for rule in self.get_runnable_rules():
            if not include_disabled and not self.is_rule_enabled(rule.full_id):
                continue
            variants = self._compiled_variants.get(rule.full_id)
            if not variants:
                continue
            rule_matches = self._execute_rule(sentence, rule, variants)
            results.extend(rule_matches)

        return results

    def _execute_rule(
        self,
        sentence: AnalyzedSentence,
        rule: GrammarRule,
        variants: List[CompiledRuleVariant],
    ) -> List[RuleMatchResult]:
        """Match compiled rule variants against sentence tokens with antipatterns and RuleWithMaxFilter."""
        all_variant_matches: List[RuleMatchResult] = []
        text_full = sentence.text if hasattr(sentence, "text") and sentence.text else ""

        for variant in variants:
            # 1. Antipattern evaluation (immunize matched tokens)
            immunized_tokens: Set[int] = set()
            if variant.antipatterns:
                for ap_variant in variant.antipatterns:
                    ap_results = ap_variant.match_sentence(
                        sentence=sentence,
                        synthesizer=self._synthesizer,
                        immunized_tokens=set(),
                    )
                    for ap_res in ap_results:
                        for imm_idx in range(ap_res.error_start_idx, ap_res.error_end_idx):
                            immunized_tokens.add(imm_idx)

            # 2. Main pattern match
            match_results = variant.match_sentence(
                sentence=sentence,
                synthesizer=self._synthesizer,
                immunized_tokens=immunized_tokens,
            )

            if not match_results:
                continue

            # Select token stream
            all_tokens = sentence.pre_disambig_tokens if variant.raw_pos else sentence.tokens
            non_blank_tokens = [
                t for t in all_tokens if t.has_pos_tag("SENT_START") or (t.token and not t.is_whitespace())
            ]

            for match_res in match_results:
                matched_tokens = non_blank_tokens[match_res.match_start_idx : match_res.match_end_idx]
                error_tokens = non_blank_tokens[match_res.error_start_idx : match_res.error_end_idx]
                formatting_tokens = non_blank_tokens

                # Format message
                message = TemplateFormatter.format_message(
                    template=rule.message_template,
                    tokens=formatting_tokens,
                    token_positions=match_res.token_positions,
                    first_match_token=match_res.first_match_token,
                    element_lengths=variant.element_lengths,
                    synthesizer=self._synthesizer,
                )

                # Format suggestions
                sug_matches = regex.findall(r"<suggestion>(.*?)</suggestion>", message)
                first_err_tok = error_tokens[0].token or "" if error_tokens else ""
                is_sentence_start = bool(match_res.error_start_idx <= 1)

                has_case_conversion = False
                if rule.message_template and rule.message_template.elements:
                    has_case_conversion = any(
                        isinstance(elem, MatchReference) and elem.case_conversion is not None
                        for elem in rule.message_template.elements
                    )
                if not has_case_conversion and rule.suggestions:
                    for st in rule.suggestions:
                        if any(isinstance(elem, MatchReference) and elem.case_conversion is not None for elem in st.elements):
                            has_case_conversion = True
                            break

                is_first_upper = bool(is_sentence_start and first_err_tok and first_err_tok[0].isupper() and not has_case_conversion)
                if sug_matches:
                    if is_first_upper:
                        suggestions = [uppercase_first_char(s) for s in sug_matches]
                    else:
                        suggestions = sug_matches
                else:
                    suggestions = []
                    for sug_tmpl in rule.suggestions:
                        sug_list = TemplateFormatter.format_suggestions_list(
                            template=sug_tmpl,
                            tokens=formatting_tokens,
                            token_positions=match_res.token_positions,
                            first_match_token=match_res.first_match_token,
                            error_tokens=error_tokens,
                            element_lengths=variant.element_lengths,
                            synthesizer=self._synthesizer,
                        )
                        suggestions.extend(sug_list)

                # Error / Marker span offsets
                from_tok = non_blank_tokens[match_res.error_start_idx]
                to_tok = non_blank_tokens[match_res.error_end_idx - 1]
                from_utf16 = from_tok.start_pos
                to_utf16 = to_tok.start_pos + _utf16_len(to_tok.token)

                if from_utf16 >= to_utf16:
                    continue

                # Match Java LT PatternRuleMatcher comma-prepended whitespace semantics
                if match_res.error_start_idx >= 1:
                    has_comma_sugg = any(s.startswith(",") for s in suggestions) or ("<suggestion>," in message)
                    if has_comma_sugg:
                        prev_tok = non_blank_tokens[match_res.error_start_idx - 1]
                        from_utf16 = prev_tok.start_pos + _utf16_len(prev_tok.token)

                if text_full:
                    from_pos = _utf16_to_codepoint_offset(text_full, from_utf16)
                    to_pos = _utf16_to_codepoint_offset(text_full, to_utf16)
                else:
                    from_pos = from_utf16
                    to_pos = to_utf16

                # Full pattern span offsets
                pat_from_tok = non_blank_tokens[match_res.match_start_idx]
                pat_to_tok = non_blank_tokens[match_res.match_end_idx - 1]
                pat_from_utf16 = pat_from_tok.start_pos
                pat_to_utf16 = pat_to_tok.start_pos + _utf16_len(pat_to_tok.token)

                if text_full:
                    pat_from_pos = _utf16_to_codepoint_offset(text_full, pat_from_utf16)
                    pat_to_pos = _utf16_to_codepoint_offset(text_full, pat_to_utf16)
                else:
                    pat_from_pos = pat_from_utf16
                    pat_to_pos = pat_to_utf16

                res = RuleMatchResult(
                    rule_id=rule.id,
                    full_rule_id=rule.full_id,
                    category_id=rule.category_id,
                    category_name=rule.category_name,
                    description=rule.name,
                    message=message,
                    short_message=rule.short_message or "",
                    suggestions=suggestions,
                    from_pos=from_pos,
                    to_pos=to_pos,
                    from_pos_utf16=from_utf16,
                    to_pos_utf16=to_utf16,
                    pattern_from_pos=pat_from_pos,
                    pattern_to_pos=pat_to_pos,
                    pattern_from_pos_utf16=pat_from_utf16,
                    pattern_to_pos_utf16=pat_to_utf16,
                    matched_tokens_indices=list(range(match_res.match_start_idx, match_res.match_end_idx)),
                    marker_tokens_indices=list(range(match_res.error_start_idx, match_res.error_end_idx)),
                )

                if rule.filters:
                    for filt_config in rule.filters:
                        if res is None:
                            break
                        from pylat_ru.grammar.filters import get_filter_instance, RuleFilterEvaluator
                        filt = get_filter_instance(filt_config.class_name)
                        filt.set_synthesizer(self._synthesizer)
                        evaluator = RuleFilterEvaluator(filt)
                        res = evaluator.run_filter(
                            filt_config.args or "",
                            res,
                            matched_tokens,
                            match_res.first_match_token,
                            match_res.token_positions
                        )
                if res is None:
                    continue
                all_variant_matches.append(res)

        # Apply RuleWithMaxFilter overlap elimination across all variant matches of this rule
        return filter_subsumed_rule_matches(all_variant_matches)
