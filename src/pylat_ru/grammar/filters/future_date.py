import datetime
import re
from typing import List, Dict, Optional
from pylat_ru.analysis import AnalyzedTokenReadings
from pylat_ru.grammar.model import RuleMatchResult
from .base import RuleFilter, FilterIllegalArgumentError, FilterRuntimeError
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
        raise FilterRuntimeError(f"Could not find month '{month_str}'")

    def get_date_components(self, args: Dict[str, str]) -> tuple[int, int, int]:
        year_str = self.get_required("year", args)
        try:
            year = int(year_str)
        except ValueError:
            raise FilterIllegalArgumentError(f"Invalid year: '{year_str}'")

        month_str = self.get_required("month", args)
        if month_str.isdigit():
            month = int(month_str)
        else:
            month = self.get_month(month_str)

        day_str = self.get_required("day", args)
        m = self.DAY_OF_MONTH_PATTERN.fullmatch(day_str)
        if m:
            try:
                day = int(m.group(1))
            except ValueError:
                raise FilterIllegalArgumentError(f"Invalid day: '{day_str}'")
        else:
            day = 0

        return year, month, day

    def accept_rule_match(
        self,
        match: RuleMatchResult,
        arguments: Dict[str, str],
        pattern_token_pos: int,
        pattern_tokens: List[AnalyzedTokenReadings],
        token_positions: List[int]
    ) -> Optional[RuleMatchResult]:
        year, month, day = self.get_date_components(arguments)

        if SystemClock.is_test_mode:
            current_date = datetime.date(2014, 1, 1)
        else:
            current_date = SystemClock.now().date()

        try:
            date_from_date = datetime.date(year, month, day)

            if date_from_date > current_date:
                return match
            else:
                return None
        except (ValueError, OverflowError):
            # Java Calendar.after() compares the pending calendar fields
            # without forcing strict-date validation in this path.  Thus an
            # invalid date in a future month/year is still considered future.
            return match if (year, month, day) > (
                current_date.year, current_date.month, current_date.day
            ) else None
