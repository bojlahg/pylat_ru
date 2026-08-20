"""Generate Task 0010's real-rule and controlled low-level Java fixtures."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.model import ExecutionState
from tools.differential_lt import JavaLanguageToolOracle, PINNED_LT_COMMIT, PINNED_LT_VERSION

FILTERS = {
    "advanced": "org.languagetool.rules.ru.AdvancedSynthesizerFilter",
    "date": "org.languagetool.rules.ru.DateCheckFilter",
    "future": "org.languagetool.rules.ru.FutureDateFilter",
    "inn": "org.languagetool.rules.ru.INNNumberFilter",
    "partial": "org.languagetool.rules.ru.RussianPartialPosTagFilter",
}
SIGNATURE_FIELDS = (
    "operation", "filter_class", "filter_args", "selected_key", "arguments",
    "tokens", "token_positions", "pattern_token_pos", "match",
)
EXCEPTION_FEATURES = {
    "evaluator:negative-reference": "index_bounds",
    "evaluator:zero-reference": "index_bounds",
    "evaluator:too-large-reference": "runtime",
    "evaluator:duplicate-backref-key": "runtime",
    "evaluator:malformed-argument": "runtime",
    "evaluator:malformed-backreference": "illegal_argument",
    "date:malformed-year": "illegal_argument",
    "future:unknown-month": "runtime",
    "future:malformed-year": "illegal_argument",
    "advanced:undefined-postag": "illegal_argument",
    "advanced:invalid-position": "illegal_argument",
    "partial:wrong-group-count": "runtime",
}
EXPECTED_EXCEPTION_CLASSES = {
    "evaluator:negative-reference": "java.lang.ArrayIndexOutOfBoundsException",
    "evaluator:zero-reference": "java.lang.ArrayIndexOutOfBoundsException",
    "evaluator:too-large-reference": "java.lang.RuntimeException",
    "evaluator:duplicate-backref-key": "java.lang.RuntimeException",
    "evaluator:malformed-argument": "java.lang.RuntimeException",
    "evaluator:malformed-backreference": "java.lang.NumberFormatException",
    "date:malformed-year": "java.lang.NumberFormatException",
    "future:unknown-month": "java.lang.RuntimeException",
    "future:malformed-year": "java.lang.NumberFormatException",
    "advanced:undefined-postag": "java.lang.IllegalArgumentException",
    "advanced:invalid-position": "java.lang.IllegalArgumentException",
    "partial:wrong-group-count": "java.lang.RuntimeException",
}


def token(surface: str, lemma: str | None = None, pos: str | None = None,
          start: int = 0, readings: Iterable[tuple[str | None, str | None]] = ()) -> Dict[str, Any]:
    raw = [{"token": surface, "lemma": lemma, "pos_tag": pos}]
    raw.extend({"token": surface, "lemma": lem, "pos_tag": tag} for lem, tag in readings)
    return {"token": surface, "start_pos": start, "readings": raw}


def semantic_signature(case: Mapping[str, Any]) -> str:
    semantic = {field: case.get(field) for field in SIGNATURE_FIELDS}
    payload = json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def java_exception_category(class_name: str) -> str:
    simple = class_name.rsplit(".", 1)[-1]
    if simple in {"IllegalArgumentException", "NumberFormatException"}:
        return "illegal_argument"
    if simple in {"ArrayIndexOutOfBoundsException", "IndexOutOfBoundsException"}:
        return "index_bounds"
    if simple == "PatternSyntaxException":
        return "regex_syntax"
    if simple == "RuntimeException":
        return "runtime"
    return "unexpected:" + simple


class Corpus:
    def __init__(self) -> None:
        self.cases: List[Dict[str, Any]] = []

    def add(self, stem: str, *, features: Iterable[str], expected: Mapping[str, Any], **semantic: Any) -> None:
        feature_list = list(features)
        expected_java = dict(expected)
        exception_classes = {
            EXPECTED_EXCEPTION_CLASSES[feature]
            for feature in feature_list if feature in EXPECTED_EXCEPTION_CLASSES
        }
        if exception_classes:
            if len(exception_classes) != 1 or expected_java.get("status") != "EXCEPTION":
                raise ValueError(f"Invalid exception expectation for {stem}: {feature_list}")
            expected_java["exception_class"] = exception_classes.pop()
        case = {"id": f"syn_{len(self.cases) + 1:03d}_{stem}", "features": feature_list,
                "expected_java": expected_java, **semantic}
        case["semantic_signature"] = semantic_signature(case)
        self.cases.append(case)

    def evaluator(self, stem: str, args: str, tokens: List[Dict[str, Any]], positions: List[int],
                  *, features: Iterable[str], expected: Mapping[str, Any], selected_key: str | None = None,
                  pattern_token_pos: int = 0, match: Mapping[str, Any] | None = None) -> None:
        self.add(stem, features=features, expected=expected, operation="evaluator", filter_class="",
                 filter_args=args, selected_key=selected_key, arguments={}, tokens=tokens,
                 token_positions=positions, pattern_token_pos=pattern_token_pos,
                 match=dict(match or {}))

    def filter(self, stem: str, filter_key: str, arguments: Mapping[str, str], *,
               features: Iterable[str], expected: Mapping[str, Any],
               tokens: List[Dict[str, Any]] | None = None, positions: List[int] | None = None,
               pattern_token_pos: int = 0, match: Mapping[str, Any] | None = None) -> None:
        self.add(stem, features=features, expected=expected, operation="filter",
                 filter_class=FILTERS[filter_key], filter_args="", selected_key=None,
                 arguments=dict(arguments), tokens=tokens or [token("x")],
                 token_positions=positions or [1], pattern_token_pos=pattern_token_pos,
                 match=dict(match or {"from_pos": 0, "to_pos": 1, "message": "message",
                                      "short_message": "short", "suggestions": ["{suggestion}"]}))


def build_evaluator_cases(c: Corpus) -> None:
    abc = [token("SENT_START", None, "SENT_START"), token("альфа", "альфа", "NN", 0),
           token("бета", "бета", "NN", 6), token("😀", "😀", "SYM", 11)]
    result = {"status": "RESULT"}
    c.evaluator("literal", "kind:value", abc, [1] * 4, features=["evaluator:literal"], expected={**result, "resolved_args": {"kind": "value"}})
    c.evaluator("literal_colon", "url:https://example.test:8443/a", abc, [1] * 4, features=["evaluator:colon-literal"], expected={**result, "resolved_args": {"url": "https://example.test:8443/a"}})
    c.evaluator("backref", r"word:\2", abc, [1] * 4, features=["evaluator:backreference"], expected={**result, "resolved_args": {"word": "альфа"}, "selected_position": 1}, selected_key="word")
    c.evaluator("two_backrefs", r"left:\2 right:\3", abc, [1] * 4, features=["evaluator:backreference", "evaluator:multiple-arguments"], expected={**result, "resolved_args": {"left": "альфа", "right": "бета"}})
    c.evaluator("skip", r"word:\2", abc, [1, 2, 1], features=["evaluator:skip-correction"], expected={**result, "resolved_args": {"word": "бета"}, "selected_position": 2}, selected_key="word")
    c.evaluator("optional_present", r"word:\2", abc, [1, 1, 1], features=["evaluator:optional-present"], expected={**result, "resolved_args": {"word": "альфа"}})
    c.evaluator("optional_absent", r"word:\2", abc, [1, 0, 1], features=["evaluator:optional-absent"], expected={**result, "resolved_args": {"word": "SENT_START"}})
    c.evaluator("repeated", r"word:\2", abc, [1, 2], features=["evaluator:repeated-token"], expected={**result, "resolved_args": {"word": "бета"}})
    for stem, ref, feature, category in (("negative", "-1", "negative-reference", "index_bounds"), ("zero", "0", "zero-reference", "index_bounds"), ("too_large", "9", "too-large-reference", "runtime")):
        c.evaluator(stem, "word:\\" + ref, abc, [1] * 4, features=["evaluator:" + feature], expected={"status": "EXCEPTION", "exception_category": category})
    c.evaluator("duplicate_literal", "key:first key:second", abc, [1] * 4, features=["evaluator:duplicate-literal-key"], expected={**result, "resolved_args": {"key": "second"}})
    c.evaluator("duplicate_backref", r"key:\2 key:\3", abc, [1] * 4, features=["evaluator:duplicate-backref-key"], expected={"status": "EXCEPTION", "exception_category": "runtime"})
    c.evaluator("marker", "position:marker", abc, [1] * 4, pattern_token_pos=2,
                features=["evaluator:marker-position"],
                expected={**result, "resolved_args": {"position": "marker"}, "selected_position": 2},
                selected_key="position", match={"from_pos": 6, "to_pos": 10})
    c.evaluator("numeric_position", "position:3", abc, [1] * 4,
                features=["evaluator:numeric-position"],
                expected={**result, "resolved_args": {"position": "3"}, "selected_position": 2},
                selected_key="position")
    c.evaluator("sent_start", r"word:\1", abc, [1] * 4, features=["evaluator:SENT_START"], expected={**result, "resolved_args": {"word": "SENT_START"}, "selected_position": 0}, selected_key="word")
    c.evaluator("non_bmp", r"word:\4", abc, [1] * 4, features=["evaluator:non-BMP-token"], expected={**result, "resolved_args": {"word": "😀"}, "selected_position": 3}, selected_key="word")
    c.evaluator("malformed", "missing_colon", abc, [1] * 4, features=["evaluator:malformed-argument"], expected={"status": "EXCEPTION", "exception_category": "runtime"})
    c.evaluator("bad_backref", r"word:\x", abc, [1] * 4, features=["evaluator:malformed-backreference"], expected={"status": "EXCEPTION", "exception_category": "illegal_argument"})


def inn10(prefix: str) -> str:
    value = sum(int(ch) * weight for ch, weight in zip(prefix, (2, 4, 10, 3, 5, 9, 4, 6, 8))) % 11
    return prefix + str(value - 10 if value > 9 else value)


def inn12(prefix: str) -> str:
    first = sum(int(ch) * weight for ch, weight in zip(prefix, (7, 2, 4, 10, 3, 5, 9, 4, 6, 8))) % 11
    first = first - 10 if first > 9 else first
    eleven = prefix + str(first)
    second = sum(int(ch) * weight for ch, weight in zip(eleven, (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8))) % 11
    return eleven + str(second - 10 if second > 9 else second)


def inn12_second(eleven: str) -> str:
    second = sum(int(ch) * weight for ch, weight in zip(eleven, (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8))) % 11
    return str(second - 10 if second > 9 else second)


def different_digit(ch: str) -> str:
    return str((int(ch) + 1) % 10)


def inn12_checksum_state(value: str) -> tuple[bool, bool]:
    expected = inn12(value[:10])
    first_valid = value[10] == expected[10]
    second_valid = value[11] == inn12_second(value[:11])
    return first_valid, second_valid


def build_inn_cases(c: Corpus) -> None:
    valid10 = [inn10(p) for p in ("770110725", "500100732", "010101010", "123456789", "987654321", "540813769", "667100001", "246802468")]
    valid12 = [inn12(p) for p in ("5001007322", "7707083893", "0101010101", "1234567890", "9876543210", "5408137699", "6671000010", "2468024680")]
    for i, value in enumerate(valid10):
        c.filter(f"inn10_valid_{i}", "inn", {"inn": value}, features=["inn:valid-10"] + (["inn:leading-zero"] if value.startswith("0") else []), expected={"status": "RESULT", "decision": "reject"})
        c.filter(f"inn10_invalid_{i}", "inn", {"inn": value[:-1] + different_digit(value[-1])}, features=["inn:invalid-10"], expected={"status": "RESULT", "decision": "preserve"})
    for i, value in enumerate(valid12):
        c.filter(f"inn12_valid_{i}", "inn", {"inn": value}, features=["inn:valid-12"] + (["inn:leading-zero"] if value.startswith("0") else []), expected={"status": "RESULT", "decision": "reject"})
        bad_first_eleven = value[:10] + different_digit(value[10])
        c.filter(f"inn12_first_{i}", "inn", {"inn": bad_first_eleven + inn12_second(bad_first_eleven)}, features=["inn:invalid-first-checksum"], expected={"status": "RESULT", "decision": "preserve"})
        c.filter(f"inn12_second_{i}", "inn", {"inn": value[:11] + different_digit(value[11])}, features=["inn:invalid-second-checksum"], expected={"status": "RESULT", "decision": "preserve"})
        c.filter(f"inn12_both_{i}", "inn", {"inn": value[:10] + different_digit(value[10]) + different_digit(value[11])}, features=["inn:both-checksums-invalid"], expected={"status": "RESULT", "decision": "preserve"})
    for stem, value, feature in (("nine", "123456789", "9-digits"), ("eleven", "12345678901", "11-digits"), ("thirteen", "1234567890123", "13-digits"), ("ascii", "12345A7890", "ASCII-nondigit"), ("space", "770110 7259", "whitespace"), ("arabic", "٧٧٠١١٠٧٢٥٩", "Unicode-digits"), ("fullwidth", "７７０１１０７２５９", "Unicode-digits")):
        c.filter("inn_" + stem, "inn", {"inn": value}, features=["inn:" + feature], expected={"status": "RESULT", "decision": "reject"})


WEEKDAYS = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")
MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")


def date_args(value: dt.date, weekday: str | None = None, month: str | None = None, year: str | None = "date") -> Dict[str, str]:
    args = {"weekDay": weekday or WEEKDAYS[value.weekday()], "day": str(value.day), "month": month or MONTHS[value.month - 1]}
    if year is not None:
        args["year"] = str(value.year) if year == "date" else year
    return args


def build_date_cases(c: Corpus) -> None:
    dates = [dt.date(2001 + i, i % 12 + 1, 10 + i % 17) for i in range(18)]
    for i, value in enumerate(dates):
        month = MONTHS[value.month - 1] if i < 6 else (str(value.month) if i < 12 else ("I", "II", "III", "IV", "V", "VI")[i - 12])
        feature = "date:localized-month" if i < 6 else ("date:numeric-month" if i < 12 else "date:roman-month")
        c.filter(f"date_correct_{i}", "date", date_args(value, month=month), features=["date:correct-weekday", feature], expected={"status": "RESULT", "decision": "reject"})
        wrong = WEEKDAYS[(value.weekday() + 1) % 7]
        c.filter(f"date_wrong_{i}", "date", date_args(value, weekday=wrong, month=month), features=["date:wrong-weekday", "date:message-placeholders", "date:URL"], expected={"status": "RESULT", "decision": "modify"}, match={"from_pos": 2, "to_pos": 7, "message": "{day}/{realDay}/{currentYear}", "short_message": "date", "suggestions": []})
    current = dt.date.today()
    omitted = dt.date(current.year, 9, 29)
    c.filter("date_omitted_correct", "date", date_args(omitted, year=None), features=["date:omitted-year"], expected={"status": "RESULT", "decision": "reject"})
    c.filter("date_omitted_wrong", "date", date_args(omitted, weekday=WEEKDAYS[(omitted.weekday() + 2) % 7], year=None), features=["date:omitted-year", "date:wrong-weekday"], expected={"status": "RESULT", "decision": "modify"})
    special = [
        ("unknown_weekday", {"weekDay": "фрудень", "day": "1", "month": "января", "year": "2020"}, "date:unknown-weekday", {"status": "RESULT", "decision": "reject"}),
        ("unknown_month", {"weekDay": "среда", "day": "1", "month": "тридецембря", "year": "2020"}, "date:unknown-month", {"status": "RESULT", "decision": "reject"}),
        ("malformed_year", {"weekDay": "среда", "day": "1", "month": "января", "year": "20x0"}, "date:malformed-year", {"status": "EXCEPTION", "exception_category": "illegal_argument"}),
        ("malformed_day", {"weekDay": "среда", "day": "день", "month": "января", "year": "2020"}, "date:malformed-day", {"status": "RESULT", "decision": "reject"}),
        ("impossible", {"weekDay": "среда", "day": "31", "month": "апреля", "year": "2020"}, "date:impossible-strict-date", {"status": "RESULT", "decision": "reject"}),
        ("soft_hyphen", {"weekDay": "сре\u00adда", "day": "1", "month": "января", "year": "2020"}, "date:soft-hyphen", {"status": "RESULT", "decision": "reject"}),
    ]
    for stem, args, feature, expected in special:
        c.filter("date_" + stem, "date", args, features=[feature], expected=expected)


def build_future_cases(c: Corpus) -> None:
    for i in range(12):
        c.filter(f"future_{i}", "future", {"day": str(1 + i), "month": MONTHS[i], "year": "2999"}, features=["future:future", "future:localized-month"], expected={"status": "RESULT", "decision": "preserve"})
        c.filter(f"past_{i}", "future", {"day": str(1 + i), "month": str(i + 1), "year": "1900"}, features=["future:past", "future:numeric-month"], expected={"status": "RESULT", "decision": "reject"})
    special = [
        ("unknown_month", {"day": "1", "month": "тридецембря", "year": "2999"}, "future:unknown-month", {"status": "EXCEPTION", "exception_category": "runtime"}),
        ("malformed_year", {"day": "1", "month": "января", "year": "29x9"}, "future:malformed-year", {"status": "EXCEPTION", "exception_category": "illegal_argument"}),
        ("malformed_day", {"day": "завтра", "month": "января", "year": "2999"}, "future:malformed-day", {"status": "RESULT", "decision": "preserve"}),
        ("impossible", {"day": "31", "month": "апреля", "year": "2999"}, "future:impossible-rollover", {"status": "RESULT", "decision": "preserve"}),
        ("trim_month", {"day": "1", "month": "января,", "year": "2999"}, "future:trimmed-localized-month", {"status": "RESULT", "decision": "preserve"}),
        ("leap_valid", {"day": "29", "month": "февраля", "year": "2996"}, "future:leap-valid", {"status": "RESULT", "decision": "preserve"}),
        ("leap_invalid", {"day": "29", "month": "февраля", "year": "2999"}, "future:leap-invalid-not-forced", {"status": "RESULT", "decision": "preserve"}),
    ]
    for stem, args, feature, expected in special:
        c.filter("future_" + stem, "future", args, features=[feature], expected=expected)


def build_partial_cases(c: Corpus) -> None:
    samples = [
        ("неделал", r"не(.*)", "VB:.*", {}, "preserve", "positive"),
        ("неработал", r"не(.*)", "VB:.*", {}, "preserve", "positive"),
        ("нестол", r"не(.*)", "VB:.*", {}, "reject", "no-match"),
        ("некнига", r"не(.*)", "VB:.*", {}, "reject", "no-match"),
        ("нестол", r"не(.*)", "VB:.*", {"negate_pos": "yes"}, "preserve", "negate-pos"),
        ("некнига", r"не(.*)", "VB:.*", {"negate_pos": "yes"}, "preserve", "negate-pos"),
        ("неделался", r"не(.*)(ся)", "VB:.*", {"two_groups_regexp": "yes"}, "preserve", "two-groups"),
        ("неработался", r"не(.*)(ся)", "VB:.*", {"two_groups_regexp": "yes"}, "reject", "two-groups-no-match"),
        ("т", r"(.*)", "VB:.*", {"prefix": "дела", "suffix": "ь"}, "preserve", "prefix-suffix"),
        ("та", r"(.*)", "NN:.*", {"prefix": "рабо"}, "preserve", "prefix"),
    ]
    for i, (surface, regexp, postag, extra, decision, feature) in enumerate(samples):
        c.filter(f"partial_{i}", "partial", {"no": "1", "regexp": regexp, "postag_regexp": postag, **extra}, tokens=[token(surface)], features=["partial:" + feature], expected={"status": "RESULT", "decision": decision})
    c.filter("partial_wrong_groups", "partial", {"no": "1", "regexp": r"не(.*)(ся)", "postag_regexp": "VB:.*"}, tokens=[token("неделался")], features=["partial:wrong-group-count"], expected={"status": "EXCEPTION", "exception_category": "runtime"})


def build_advanced_cases(c: Corpus) -> None:
    verb = token("делал", "делать", "VB:Past:TRANS:IMPFV:Masc", readings=[("делать", "VB:Inf")])
    upper = token("ДЕЛАЛ", "делать", "VB:Past:TRANS:IMPFV:Masc")
    title = token("Делал", "делать", "VB:Past:TRANS:IMPFV:Masc")
    base = {"lemmaFrom": "1", "postagFrom": "1", "lemmaSelect": r"VB:(Past):(TRANS):(IMPFV):(Masc)", "postagSelect": r"VB:(Past):(TRANS):(IMPFV):(Masc)"}
    variants = [
        ("simple_lower", verb, {}, ["{suggestion}"], ["advanced:simple", "advanced:placeholder-lower"]),
        ("placeholder_title", verb, {}, ["{Suggestion}"], ["advanced:placeholder-title"]),
        ("placeholder_upper", verb, {}, ["{SUGGESTION}"], ["advanced:placeholder-upper"]),
        ("capitalization", title, {}, ["{suggestion}"], ["advanced:capitalization"]),
        ("all_upper", upper, {}, ["{suggestion}"], ["advanced:all-uppercase"]),
        ("no_placeholder", verb, {}, ["literal"], ["advanced:no-placeholder"]),
        ("a_capture", verb, {"postagReplace": r"VB:\a1:TRANS:IMPFV:Masc"}, ["{suggestion}"], [r"advanced:\aN-capture"]),
        ("b_capture", verb, {"postagReplace": r"VB:\b1:TRANS:IMPFV:Masc"}, ["{suggestion}"], [r"advanced:\bN-capture"]),
        ("mixed_capture", verb, {"postagReplace": r"VB:\a1:\b2:\a3:\b4"}, ["{suggestion}"], [r"advanced:mixed-\aN-\bN"]),
        ("new_lemma", verb, {"newLemma": "читать"}, ["{suggestion}"], ["advanced:new-lemma"]),
    ]
    for stem, tok, extra, suggestions, features in variants:
        c.filter("advanced_" + stem, "advanced", {**base, **extra}, tokens=[tok], features=features, expected={"status": "RESULT", "decision": "modify"}, match={"from_pos": 0, "to_pos": len(tok["token"]), "message": "advanced", "short_message": "adv", "suggestions": suggestions})
    fallback = {"lemmaFrom": "1", "postagFrom": "1", "lemmaSelect": "NO_MATCH", "postagSelect": "NO_MATCH"}
    c.filter("advanced_first_reading", "advanced", fallback, tokens=[verb], features=["advanced:first-reading-fallback"], expected={"status": "RESULT", "decision": "modify"})
    c.filter("advanced_numeric_positions", "advanced", {**base, "lemmaFrom": "1", "postagFrom": "2"}, tokens=[verb, verb], positions=[1, 1], features=["advanced:numeric-positions"], expected={"status": "RESULT", "decision": "modify"})
    c.filter("advanced_marker_positions", "advanced", {**base, "lemmaFrom": "marker-1", "postagFrom": "marker"}, tokens=[token("делал", "делать", "VB:Past:TRANS:IMPFV:Masc", start=0), token("делал", "делать", "VB:Past:TRANS:IMPFV:Masc", start=5)], positions=[1, 1], pattern_token_pos=1, features=["advanced:marker-positions"], expected={"status": "RESULT", "decision": "modify"}, match={"from_pos": 5, "to_pos": 10, "message": "advanced", "short_message": "adv", "suggestions": ["{suggestion}"]})
    c.filter("advanced_distinct_sources", "advanced", {"lemmaFrom": "1", "postagFrom": "2", "lemmaSelect": "ADJ:.*", "postagSelect": "NN:.*", "newLemma": "книга"}, tokens=[token("красивый", "красивый", "ADJ:Posit:Masc:Nom"), token("книги", "книга", "NN:Inanim:Fem:Sin:R")], positions=[1, 1], features=["advanced:distinct-sources"], expected={"status": "RESULT", "decision": "modify"})
    c.filter("advanced_empty_synthesis", "advanced", {**base, "newLemma": "несуществоватькслову"}, tokens=[verb], features=["advanced:empty-synthesis-result"], expected={"status": "RESULT", "decision": "preserve"})
    c.filter("advanced_null_lemma", "advanced", {**base, "newLemma": "_unsupported"}, tokens=[verb], features=["advanced:null-new-lemma"], expected={"status": "RESULT", "decision": "reject"})
    c.filter("advanced_undefined_postag", "advanced", base, tokens=[token("x", "x", None)], features=["advanced:undefined-postag"], expected={"status": "EXCEPTION", "exception_category": "illegal_argument"})
    c.filter("advanced_invalid_position", "advanced", {**base, "lemmaFrom": "9"}, tokens=[verb], features=["advanced:invalid-position"], expected={"status": "EXCEPTION", "exception_category": "illegal_argument"})


def build_synthetic_corpus() -> List[Dict[str, Any]]:
    corpus = Corpus()
    for builder in (build_evaluator_cases, build_inn_cases, build_date_cases, build_future_cases, build_partial_cases, build_advanced_cases):
        builder(corpus)
    signatures = [case["semantic_signature"] for case in corpus.cases]
    if len(corpus.cases) < 120:
        raise ValueError(f"Synthetic corpus has only {len(corpus.cases)} cases; at least 120 required")
    if len(signatures) != len(set(signatures)):
        raise ValueError("Duplicate semantic case signatures")
    expected_states = {
        "inn:invalid-first-checksum": (False, True),
        "inn:invalid-second-checksum": (True, False),
        "inn:both-checksums-invalid": (False, False),
    }
    for case in corpus.cases:
        for feature, expected_state in expected_states.items():
            if feature in case["features"]:
                actual_state = inn12_checksum_state(case["arguments"]["inn"])
                if actual_state != expected_state:
                    raise ValueError(
                        f"{case['id']} does not encode {feature}: {actual_state}"
                    )
    return corpus.cases


def assert_expected(case: Mapping[str, Any], actual: Dict[str, Any]) -> None:
    if actual.get("status") == "EXCEPTION":
        actual["exception_category"] = java_exception_category(actual["exception_class"])
    for key, value in case["expected_java"].items():
        if actual.get(key) != value:
            raise ValueError(f"Java contradiction for {case['id']} field {key}: expected {value!r}, got {actual.get(key)!r}; {actual}")


def make_coverage(cases: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    coverage: Dict[str, Dict[str, Any]] = {}
    for case in cases:
        actual = case["oracle_result"]
        for feature in case["features"]:
            allowed = EXCEPTION_FEATURES.get(feature)
            if actual["status"] != "RESULT" and not (allowed and actual.get("exception_category") == allowed):
                raise ValueError(f"Feature {feature} not exercised by {case['id']}: {actual}")
            entry = coverage.setdefault(feature, {"exception_feature": allowed is not None, "expected_exception_category": allowed, "exercising_case_ids": []})
            entry["exercising_case_ids"].append(case["id"])
    required = {
        "inn:valid-10", "inn:invalid-10", "inn:valid-12", "inn:invalid-first-checksum", "inn:invalid-second-checksum", "inn:both-checksums-invalid", "inn:leading-zero", "inn:9-digits", "inn:11-digits", "inn:13-digits", "inn:ASCII-nondigit", "inn:whitespace", "inn:Unicode-digits",
        "date:unknown-weekday", "date:unknown-month", "date:malformed-year", "date:malformed-day", "date:impossible-strict-date", "date:omitted-year", "date:soft-hyphen", "date:numeric-month", "date:localized-month",
        r"advanced:\aN-capture", r"advanced:\bN-capture", r"advanced:mixed-\aN-\bN", "advanced:first-reading-fallback", "advanced:marker-positions", "advanced:numeric-positions", "advanced:placeholder-lower", "advanced:placeholder-title", "advanced:placeholder-upper", "advanced:no-placeholder", "advanced:capitalization", "advanced:all-uppercase", "advanced:empty-synthesis-result",
        "evaluator:literal", "evaluator:colon-literal", "evaluator:backreference", "evaluator:skip-correction", "evaluator:optional-present", "evaluator:optional-absent", "evaluator:repeated-token", "evaluator:negative-reference", "evaluator:zero-reference", "evaluator:too-large-reference", "evaluator:duplicate-literal-key", "evaluator:duplicate-backref-key", "evaluator:marker-position", "evaluator:numeric-position", "evaluator:SENT_START", "evaluator:non-BMP-token",
    }
    missing = required - coverage.keys()
    if missing:
        raise ValueError(f"Required feature dimensions missing: {sorted(missing)}")
    return dict(sorted(coverage.items()))


def generate_fixtures() -> None:
    oracle = JavaLanguageToolOracle()
    if not oracle.is_java_available():
        raise SystemExit("ERROR: Java unavailable")
    validation = oracle.validate_oracle()
    fixtures_dir = PROJECT_ROOT / "tests" / "fixtures"
    engine = RussianGrammarEngine.get_instance()
    rules = [rule for rule in engine.get_all_rules() if rule.execution_state == ExecutionState.FILTER_0010_RUNNABLE]
    if len(rules) != 19:
        raise ValueError(f"Expected 19 FILTER_0010_RUNNABLE rules, got {len(rules)}")
    real_cases: List[Dict[str, Any]] = []
    for rule in rules:
        for index, example in enumerate(rule.examples):
            real_cases.append({"id": f"filt_ru_{len(real_cases) + 1:03d}_{rule.id}_{index}", "category": rule.category_id, "full_rule_id": rule.full_id, "text": example.text, "is_incorrect": example.is_incorrect, "filter_classes": [item.class_name for item in rule.filters]})
    print(f"Querying Java oracle for {len(real_cases)} real examples")
    outputs = oracle.check_pattern_rules([{"full_rule_id": case["full_rule_id"], "text": case["text"]} for case in real_cases])
    for case, output in zip(real_cases, outputs):
        if output["status"] != "FOUND":
            raise ValueError(f"Real rule missing: {case['id']} {output}")
        case["oracle_result"] = output
    real_coverage: Dict[str, Dict[str, Any]] = {}
    for case in real_cases:
        for class_name in case["filter_classes"]:
            entry = real_coverage.setdefault("filter:" + class_name, {"filter_class": class_name, "covered_rule_ids": [], "covered_case_ids": []})
            if case["full_rule_id"] not in entry["covered_rule_ids"]:
                entry["covered_rule_ids"].append(case["full_rule_id"])
            entry["covered_case_ids"].append(case["id"])
    metadata = {"pinned_lt_version": PINNED_LT_VERSION, "pinned_lt_commit": PINNED_LT_COMMIT, "oracle_build_id": validation["oracle_build_id"], "oracle_jar_sha256": validation["jar_sha256"], "generator_operation": "tools/generate_oracle_filters_fixtures.py"}
    real_fixture = {"schema_version": "2.0.0", "description": "Pinned Java LT Russian filter-rule examples", "metadata": {**metadata, "corpus_version": "2.0.0", "cases_count": len(real_cases), "promoted_rules_count": len(rules), "promoted_full_rule_ids": [rule.full_id for rule in rules]}, "feature_coverage": real_coverage, "cases": real_cases}
    with (fixtures_dir / "oracle_filters_russian_rules.json").open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        json.dump(real_fixture, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

    synthetic_cases = build_synthetic_corpus()
    print(f"Querying Java oracle for {len(synthetic_cases)} distinct low-level cases")
    outputs = oracle.check_low_level_filter_cases(synthetic_cases)
    for case, output in zip(synthetic_cases, outputs):
        if output["id"] != case["id"]:
            raise ValueError("Java result order/id mismatch")
        assert_expected(case, output)
        case["oracle_result"] = output
    coverage = make_coverage(synthetic_cases)
    synthetic_fixture = {"schema_version": "2.0.0", "description": "Pinned Java LT controlled low-level filter/evaluator evidence", "metadata": {**metadata, "corpus_version": "2.0.0", "controlled_current_date": dt.date.today().isoformat(), "cases_count": len(synthetic_cases), "semantic_signature_algorithm": "sha256-canonical-json-v1", "semantic_signature_fields": list(SIGNATURE_FIELDS)}, "feature_coverage": coverage, "cases": synthetic_cases}
    with (fixtures_dir / "oracle_filters_synthetic.json").open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        json.dump(synthetic_fixture, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"Saved {len(real_cases)} real and {len(synthetic_cases)} synthetic cases")


if __name__ == "__main__":
    generate_fixtures()
