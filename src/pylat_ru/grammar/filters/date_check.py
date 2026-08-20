import datetime
import re
import dataclasses
from typing import List, Dict, Optional
from pylat_ru.analysis import AnalyzedTokenReadings
from pylat_ru.grammar.model import RuleMatchResult
from .base import RuleFilter, FilterIllegalArgumentError, FilterRuntimeError

class SystemClock:
    """Wrapper to control date/time deterministically in tests."""
    
    _override_now: Optional[datetime.datetime] = None
    is_test_mode: bool = False

    @classmethod
    def now(cls) -> datetime.datetime:
        if cls._override_now is not None:
            return cls._override_now
        return datetime.datetime.now()

    @classmethod
    def get_current_year(cls) -> int:
        return cls.now().year


def trim_special_characters(s: str) -> str:
    if not s:
        return s
    start = 0
    while start < len(s) and not s[start].isalnum():
        start += 1
    end = len(s)
    while end > start and not s[end - 1].isalnum():
        end -= 1
    return s[start:end]


class DateCheckFilter(RuleFilter):
    """Russian localization of AbstractDateCheckFilter.
    
    Port of org.languagetool.rules.ru.DateCheckFilter.
    """

    DAY_OF_MONTH_PATTERN = re.compile(r"(\d+).*")

    WEEKDAYS_RU = {
        1: "воскресенье",
        2: "понедельник",
        3: "вторник",
        4: "среда",
        5: "четверг",
        6: "пятница",
        7: "суббота"
    }

    def get_day_of_week(self, day_str: str) -> int:
        day = day_str.lower()
        if day.startswith("пн") or day == "понедельник":
            return 2  # Calendar.MONDAY
        if day.startswith("вт"):
            return 3  # Calendar.TUESDAY
        if day.startswith("ср"):
            return 4  # Calendar.WEDNESDAY
        if day.startswith("чт") or day == "четверг":
            return 5  # Calendar.THURSDAY
        if day == "пт" or day.startswith("пятниц"):
            return 6  # Calendar.FRIDAY
        if day.startswith("сб") or day.startswith("суббот"):
            return 7  # Calendar.SATURDAY
        if day.startswith("вс") or day == "воскресенье":
            return 1  # Calendar.SUNDAY
        raise FilterRuntimeError(f"Could not find day of week for '{day_str}'")

    def get_month(self, month_str: str) -> int:
        mon = month_str.lower()
        if mon == "январь" or month_str == "I" or mon == "января" or mon == "янв":
            return 1
        if mon == "февраль" or month_str == "II" or mon == "февраля" or mon == "фев":
            return 2
        if mon == "март" or month_str == "III" or mon == "марта" or mon == "мар":
            return 3
        if mon == "апрель" or month_str == "IV" or mon == "апреля" or mon == "апр":
            return 4
        if mon == "май" or month_str == "V" or mon == "мая":
            return 5
        if mon == "июнь" or month_str == "VI" or mon == "июня" or mon == "ин":
            return 6
        if mon == "июль" or month_str == "VII" or mon == "июля" or mon == "ил":
            return 7
        if mon == "август" or month_str == "VIII" or mon == "августа" or mon == "авг":
            return 8
        if mon == "сентябрь" or month_str == "IX" or mon == "сентября" or mon == "сен":
            return 9
        if mon == "октябрь" or month_str == "X" or mon == "октября" or mon == "окт":
            return 10
        if mon == "ноябрь" or month_str == "XI" or mon == "ноября" or mon == "ноя":
            return 11
        if mon == "декабрь" or month_str == "XII" or mon == "декабря" or mon == "дек":
            return 12
        raise FilterRuntimeError(f"Could not find month '{month_str}'")

    def get_date(self, args: Dict[str, str]) -> datetime.date:
        year_arg = args.get("year")
        if year_arg is None and SystemClock.is_test_mode:
            year = 2014
        elif year_arg is None:
            year = SystemClock.get_current_year()
        else:
            try:
                year = int(year_arg)
            except ValueError:
                raise FilterIllegalArgumentError(f"Invalid year: '{year_arg}'")

        month_str = self.get_required("month", args)
        if month_str.isdigit():
            month = int(month_str)
        else:
            month = self.get_month(trim_special_characters(month_str))

        day_str = self.get_required("day", args)
        m = self.DAY_OF_MONTH_PATTERN.fullmatch(day_str)
        if m:
            try:
                day = int(m.group(1))
            except ValueError:
                raise FilterIllegalArgumentError(f"Invalid day: '{day_str}'")
        else:
            day = 0

        # Construct and validate strict date
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
            weekday_str = self.get_required("weekDay", arguments).replace("\u00AD", "")
            day_of_week_from_string = self.get_day_of_week(weekday_str)

            try:
                date_from_date = self.get_date(arguments)
                day_of_week_from_date = (date_from_date.weekday() + 1) % 7 + 1
            except FilterIllegalArgumentError:
                raise
            except (ValueError, OverflowError):
                return None

            if day_of_week_from_string != day_of_week_from_date:
                real_day_name = self.WEEKDAYS_RU[day_of_week_from_date]
                claimed_day_name = self.WEEKDAYS_RU[day_of_week_from_string]
                current_year_str = str(SystemClock.get_current_year())

                message = (
                    match.message
                    .replace("{realDay}", real_day_name)
                    .replace("{day}", claimed_day_name)
                    .replace("{currentYear}", current_year_str)
                )

                url = f"https://www.timeanddate.com/calendar/?year={date_from_date.year}"

                # Java constructs a fresh RuleMatch and does not copy the
                # provisional match's replacement list.
                return dataclasses.replace(
                    match,
                    message=message,
                    suggestions=[],
                    pattern_from_pos=match.from_pos,
                    pattern_to_pos=match.to_pos,
                    pattern_from_pos_utf16=match.from_pos_utf16,
                    pattern_to_pos_utf16=match.to_pos_utf16,
                    url=url,
                )
            else:
                return None
        except FilterIllegalArgumentError as e:
            raise e
        except FilterRuntimeError:
            return None
        except Exception:
            return None
