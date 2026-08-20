import re
from typing import List, Dict, Optional
from pylat_ru.analysis import AnalyzedTokenReadings
from pylat_ru.grammar.model import RuleMatchResult
from .base import RuleFilter

class RuleFilterEvaluator:
    """Evaluates a RuleFilter.
    
    Corresponds to org.languagetool.rules.patterns.RuleFilterEvaluator in Java.
    """

    def __init__(self, filter_instance: RuleFilter):
        self.filter = filter_instance

    def run_filter(
        self,
        filter_args: str,
        rule_match: RuleMatchResult,
        pattern_tokens: List[AnalyzedTokenReadings],
        pattern_token_pos: int,
        token_positions: List[int]
    ) -> Optional[RuleMatchResult]:
        args = self.get_resolved_arguments(filter_args, pattern_tokens, pattern_token_pos, token_positions)
        return self.filter.accept_rule_match(rule_match, args, pattern_token_pos, pattern_tokens, token_positions)

    def get_resolved_arguments(
        self,
        filter_args: str,
        pattern_tokens: List[AnalyzedTokenReadings],
        pattern_token_pos: int,
        token_positions: List[int]
    ) -> Dict[str, str]:
        if not filter_args:
            return {}
        result: Dict[str, str] = {}
        # whitespace split
        arguments = [arg for arg in re.split(r"\s+", filter_args) if arg]
        for arg in arguments:
            delim_pos = arg.find(':')
            if delim_pos == -1:
                raise ValueError(f"Invalid syntax for key/value, expected 'key:value', got: '{arg}'")
            key = arg[:delim_pos]
            val = arg[delim_pos + 1:]
            
            if val.startswith("\\"):
                try:
                    ref_number = int(val[1:])
                except ValueError:
                    raise ValueError(f"Invalid backreference format in: '{val}'")
                
                if ref_number > len(token_positions):
                    raise ValueError(f"Your reference number {ref_number} is bigger than the number of tokens: {len(token_positions)}")
                
                corrected_ref = self.get_skip_corrected_reference(token_positions, ref_number)
                if corrected_ref >= len(pattern_tokens):
                    raise ValueError(f"Your reference number {ref_number} is bigger than number of matching tokens: {len(pattern_tokens)}")
                
                if key in result:
                    raise ValueError(f"Duplicate key '{key}'")
                result[key] = pattern_tokens[corrected_ref].token
            else:
                result[key] = val
        return result

    def get_skip_corrected_reference(self, token_positions: List[int], ref_number: int) -> int:
        if ref_number < 0:
            return ref_number
        corrected_ref = 0
        i = 0
        for token_position in token_positions:
            if i >= ref_number:
                break
            corrected_ref += token_position
            i += 1
        return corrected_ref - 1
