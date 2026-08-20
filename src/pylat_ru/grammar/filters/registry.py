from typing import Dict, Type
from .base import RuleFilter
from .advanced_synthesizer import AdvancedSynthesizerFilter
from .date_check import DateCheckFilter
from .future_date import FutureDateFilter
from .inn import INNNumberFilter
from .partial_pos import RussianPartialPosTagFilter
from .suppress_misspelled import RussianSuppressMisspelledSuggestionsFilter

FILTER_CLASSES: Dict[str, Type[RuleFilter]] = {
    "org.languagetool.rules.ru.AdvancedSynthesizerFilter": AdvancedSynthesizerFilter,
    "org.languagetool.rules.ru.DateCheckFilter": DateCheckFilter,
    "org.languagetool.rules.ru.FutureDateFilter": FutureDateFilter,
    "org.languagetool.rules.ru.INNNumberFilter": INNNumberFilter,
    "org.languagetool.rules.ru.RussianPartialPosTagFilter": RussianPartialPosTagFilter,
    "org.languagetool.rules.ru.RussianSuppressMisspelledSuggestionsFilter": RussianSuppressMisspelledSuggestionsFilter,
}

# Singletons cache
_instances: Dict[str, RuleFilter] = {}

def get_filter_instance(class_name: str) -> RuleFilter:
    """Return singleton instance of the registered filter class.
    
    Raises KeyError if the class name is not registered.
    """
    if class_name not in FILTER_CLASSES:
        raise KeyError(f"Unknown filter class: '{class_name}'")
    
    if class_name not in _instances:
        _instances[class_name] = FILTER_CLASSES[class_name]()
    return _instances[class_name]
