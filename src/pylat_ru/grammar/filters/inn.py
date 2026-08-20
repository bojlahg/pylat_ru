import re
from typing import List, Dict, Optional
from pylat_ru.analysis import AnalyzedTokenReadings
from pylat_ru.grammar.model import RuleMatchResult
from .base import RuleFilter

class INNNumberFilter(RuleFilter):
    """Checks if INN number is incorrect.
    
    Port of org.languagetool.rules.ru.INNNumberFilter.
    """

    DIGIT_SYMBOL_PATTERN = re.compile(r"([0-9]*)")

    def accept_rule_match(
        self,
        match: RuleMatchResult,
        arguments: Dict[str, str],
        pattern_token_pos: int,
        pattern_tokens: List[AnalyzedTokenReadings],
        token_positions: List[int]
    ) -> Optional[RuleMatchResult]:
        inn_str = self.get_required("inn", arguments)

        try:
            if self.DIGIT_SYMBOL_PATTERN.fullmatch(inn_str):
                int_tab = [int(c) for c in inn_str]
                length = len(int_tab)

                if length == 10:
                    kz1 = (
                        int_tab[0] * 2 +
                        int_tab[1] * 4 +
                        int_tab[2] * 10 +
                        int_tab[3] * 3 +
                        int_tab[4] * 5 +
                        int_tab[5] * 9 +
                        int_tab[6] * 4 +
                        int_tab[7] * 6 +
                        int_tab[8] * 8
                    ) % 11
                    if kz1 > 9:
                        kz1 -= 10
                    if int_tab[9] == kz1:
                        return None
                    else:
                        return match

                elif length == 12:
                    kz1 = (
                        int_tab[0] * 7 +
                        int_tab[1] * 2 +
                        int_tab[2] * 4 +
                        int_tab[3] * 10 +
                        int_tab[4] * 3 +
                        int_tab[5] * 5 +
                        int_tab[6] * 9 +
                        int_tab[7] * 4 +
                        int_tab[8] * 6 +
                        int_tab[9] * 8
                    ) % 11
                    kz2 = (
                        int_tab[0] * 3 +
                        int_tab[1] * 7 +
                        int_tab[2] * 2 +
                        int_tab[3] * 4 +
                        int_tab[4] * 10 +
                        int_tab[5] * 3 +
                        int_tab[6] * 5 +
                        int_tab[7] * 9 +
                        int_tab[8] * 4 +
                        int_tab[9] * 6 +
                        int_tab[10] * 8
                    ) % 11
                    if kz1 > 9:
                        kz1 -= 10
                    if kz2 > 9:
                        kz2 -= 10

                    if int_tab[10] == kz1 and int_tab[11] == kz2:
                        return None
                    else:
                        return match

                else:
                    return None
            else:
                return None
        except ValueError:
            return None
        except Exception:
            return None
