import datetime
import re
from typing import List, Dict, Optional
from pylat_ru.analysis import AnalyzedTokenReadings
from pylat_ru.grammar.model import RuleMatchResult
from .base import RuleFilter
from .date_check import SystemClock, trim_special_characters

class FutureDateFilter(RuleFilter):
    """Checks if a given date is in the future.
    
    Port of org.languagetool.rules.ru.FutureDateFilter.
    """

    DAY_OF_MONTH_PATTERN = re.compile(r"(\d+).*")

    def get_month(self, month_str: str) -> int:
        mon = trim_special_characters(month_str).lower()
        if mon.startswith("янв"):
            return 1
        if mon.startswith("фев"):
            return 2
        if mon.startswith("мар"):
            return 3
        if mon.startswith("апр"):
            return 4
        if mon.startswith("май") or mon.startswith("мая"):
            return 5
        if mon.startswith("июн"):
            return 6
        if mon.startswith("июл"):
            return 7
        if mon.startswith("авг"):
            return 8
        if mon.startswith("сен"):
            return 9
        if mon.startswith("окт"):
            return 10
        if mon.startswith("ноя"):
            return 11
        if mon.startswith("дек"):
            return 12
        raise ValueError(f"Could not find month '{month_str}'")

    def get_date(self, args: Dict[str, str]) -> datetime.date:
        year_str = self.get_required("year", args)
        year = int(year_str)

        month_str = self.get_required("month", args)
        if month_str.isdigit():
            month = int(month_str)
        else:
            month = self.get_month(month_str)

        day_str = self.get_required("day", args)
        m = self.DAY_OF_MONTH_PATTERN.fullmatch(day_str)
        if m:
            day = int(m.group(1))
        else:
            day = 0

        # Validate date
        return datetime.date(year, month, day)

    def accept_rule_match(
        self,
        match: RuleMatchResult,
        arguments: Dict[str, str],
        pattern_token_pos: int,
        pattern_tokens: List[AnalyzedTokenReadings],
        token_positions: List[int]
    ) -> Optional[RuleMatchResult]:
        try:
            date_from_date = self.get_date(arguments)
            
            if SystemClock.is_test_mode:
                current_date = datetime.date(2014, 1, 1)
            else:
                current_date = SystemClock.now().date()

            if date_from_date > current_date:
                return match
            else:
                return None
        except ValueError:
            return None
        except Exception:
            return None
