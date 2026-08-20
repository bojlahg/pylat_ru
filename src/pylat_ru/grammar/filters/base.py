from typing import List, Dict, Optional, Any
from pylat_ru.analysis import AnalyzedTokenReadings
from pylat_ru.grammar.model import RuleMatchResult

class FilterIllegalArgumentError(ValueError):
    """Equivalent to Java's IllegalArgumentException."""
    pass

class FilterRuntimeError(RuntimeError):
    """Equivalent to Java's RuntimeException (excluding IllegalArgumentException)."""
    pass

class RuleFilter:
    """Filter rule matches after a PatternRule has matched already.
    
    Corresponds to org.languagetool.rules.patterns.RuleFilter in Java.
    """

    def __init__(self) -> None:
        self.synthesizer: Any = None

    def set_synthesizer(self, synthesizer: Any) -> None:
        self.synthesizer = synthesizer

    def accept_rule_match(
        self,
        match: RuleMatchResult,
        arguments: Dict[str, str],
        pattern_token_pos: int,
        pattern_tokens: List[AnalyzedTokenReadings],
        token_positions: List[int]
    ) -> Optional[RuleMatchResult]:
        """Evaluate a provisional rule match.
        
        Returns the original RuleMatchResult, a modified one, or None if rejected.
        """
        raise NotImplementedError()

    def get_required(self, key: str, arguments: Dict[str, str]) -> str:
        val = arguments.get(key)
        if val is None:
            raise FilterIllegalArgumentError(f"Missing key '{key}'")
        return val

    def get_optional(self, key: str, arguments: Dict[str, str], default_value: Optional[str] = None) -> Optional[str]:
        val = arguments.get(key)
        if val is None:
            return default_value
        return val

    def get_position(self, from_str: str, pattern_tokens: List[AnalyzedTokenReadings], match: RuleMatchResult) -> int:
        if from_str.startswith("marker"):
            i = 0
            while i < len(pattern_tokens) and (pattern_tokens[i].start_pos < match.from_pos_utf16 or pattern_tokens[i].is_sentence_start):
                i += 1
            i += 1  # 1-indexed
            if len(from_str) > 6:
                i += int(from_str.replace("marker", ""))
        else:
            i = int(from_str)
        
        if i < 1 or i > len(pattern_tokens):
            raise FilterIllegalArgumentError(f"RuleFilter: Index out of bounds in {match.full_rule_id}, value: {from_str}")
        return i - 1

    def is_match_at_sentence_start(self, tokens: List[AnalyzedTokenReadings], match: RuleMatchResult) -> bool:
        i = 0
        while i < len(tokens) and tokens[i].start_pos < match.from_pos_utf16:
            i += 1
        
        def is_punctuation_mark(token: str) -> bool:
            return len(token) == 1 and token in ",;:.!?()[]\"`“‘’\"--"
        
        while i > 0 and is_punctuation_mark(tokens[i].token):
            i -= 1
        return i == 0

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
