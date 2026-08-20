"""Generate deterministic Task-0011 fixtures from the trusted Java LT oracle."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from pylat_ru.tokenization.offsets import Utf16CodePointMapper
from tools.differential_lt import JavaLanguageToolOracle


ROOT = Path(__file__).resolve().parents[1]
JAVA_SOURCE = ROOT / "tools" / "JavaRulesOracle0011.java"
RULES = {
    "CommaWhitespaceRule": "COMMA_PARENTHESIS_WHITESPACE",
    "UppercaseSentenceStartRule": "UPPERCASE_SENTENCE_START",
    "MultipleWhitespaceRule": "WHITESPACE_RULE",
    "SentenceWhitespaceRule": "SENTENCE_WHITESPACE",
    "WhiteSpaceBeforeParagraphEnd": "WHITESPACE_PARAGRAPH",
    "WhiteSpaceAtBeginOfParagraph": "WHITESPACE_PARAGRAPH_BEGIN",
    "LongSentenceRule": "TOO_LONG_SENTENCE",
    "LongParagraphRule": "TOO_LONG_PARAGRAPH",
    "ParagraphRepeatBeginningRule": "PARAGRAPH_REPEAT_BEGINNING_RULE",
    "RussianFillerWordsRule": "FILLER_WORDS_RU",
    "PunctuationMarkAtParagraphEnd2": "PUNCTUATION_PARAGRAPH_END2",
    "RussianUnpairedBracketsRule": "RU_UNPAIRED_BRACKETS",
    "RussianVerbConjugationRule": "RU_VERB_CONJUGATION",
    "RussianDashRule": "RU_DASH_RULE",
    "RussianSpecificCaseRule": "RU_SPECIFIC_CASE",
}


def _words(n: int) -> str:
    return " ".join("слово" for _ in range(n)) + "."


SYNTHETIC_CASES = [
    ("comma_positive", "CommaWhitespaceRule", "😀 Не род ,а ум.", ["positive", "non_bmp", "spacing"]),
    ("comma_negative", "CommaWhitespaceRule", "Не род, а ум.", ["negative", "spacing"]),
    ("uppercase_positive", "UppercaseSentenceStartRule", "Закончилось лето. дети снова сели.", ["positive", "sentence_boundary"]),
    ("uppercase_negative", "UppercaseSentenceStartRule", "Закончилось лето. Дети снова сели.", ["negative", "sentence_boundary"]),
    ("multiple_ws_positive", "MultipleWhitespaceRule", "Это  тест.", ["positive", "whitespace"]),
    ("multiple_ws_negative", "MultipleWhitespaceRule", "Это тест.", ["negative", "whitespace"]),
    ("sentence_ws_positive", "SentenceWhitespaceRule", "Первое.Второе.", ["positive", "sentence_boundary"]),
    ("sentence_ws_negative", "SentenceWhitespaceRule", "Первое. Второе.", ["negative", "sentence_boundary"]),
    ("paragraph_end_ws_positive", "WhiteSpaceBeforeParagraphEnd", "Текст.  \n\nСледующий.", ["positive", "paragraph_boundary", "default_off"]),
    ("paragraph_end_ws_negative", "WhiteSpaceBeforeParagraphEnd", "Текст.\n\nСледующий.", ["negative", "paragraph_boundary", "default_off"]),
    ("paragraph_begin_ws_positive", "WhiteSpaceAtBeginOfParagraph", "  Текст.", ["positive", "paragraph_boundary", "default_off"]),
    ("paragraph_begin_ws_negative", "WhiteSpaceAtBeginOfParagraph", "Текст.", ["negative", "paragraph_boundary", "default_off"]),
    ("long_sentence_positive", "LongSentenceRule", _words(51), ["positive", "threshold"]),
    ("long_sentence_negative", "LongSentenceRule", _words(50), ["negative", "threshold"]),
    ("long_paragraph_positive", "LongParagraphRule", _words(226), ["positive", "threshold", "default_off"]),
    ("long_paragraph_negative", "LongParagraphRule", _words(225), ["negative", "threshold", "default_off"]),
    ("repeat_paragraph_positive", "ParagraphRepeatBeginningRule", "Текст один.\n\nТекст два.", ["positive", "paragraph_boundary", "multi_finding", "default_off"]),
    ("repeat_paragraph_negative", "ParagraphRepeatBeginningRule", "Первый текст.\n\nДругой текст.", ["negative", "paragraph_boundary", "default_off"]),
    ("filler_positive", "RussianFillerWordsRule", "ах слово", ["positive", "percentage", "default_off"]),
    ("filler_negative", "RussianFillerWordsRule", "обычное слово", ["negative", "percentage", "default_off"]),
    ("paragraph_punctuation_positive", "PunctuationMarkAtParagraphEnd2", "один два три четыре пять шесть семь восемь девять десять одиннадцать", ["positive", "threshold", "default_off"]),
    ("paragraph_punctuation_negative", "PunctuationMarkAtParagraphEnd2", "один два три четыре пять шесть семь восемь девять десять одиннадцать.", ["negative", "threshold", "default_off"]),
    ("brackets_positive", "RussianUnpairedBracketsRule", "Это (тест.", ["positive", "pairing"]),
    ("brackets_negative", "RussianUnpairedBracketsRule", "Это (тест).", ["negative", "pairing"]),
    ("verb_positive", "RussianVerbConjugationRule", "Я идёт.", ["positive", "morphology"]),
    ("verb_negative", "RussianVerbConjugationRule", "Я иду.", ["negative", "morphology"]),
    ("dash_positive", "RussianDashRule", "из—за", ["positive", "resource"]),
    ("dash_negative", "RussianDashRule", "из-за", ["negative", "resource"]),
    ("specific_case_positive", "RussianSpecificCaseRule", "Рытый банк", ["positive", "resource"]),
    ("specific_case_negative", "RussianSpecificCaseRule", "Рытый Банк", ["negative", "resource"]),
]

RUSSIAN_CASES = [
    ("upstream_dash_iz_za", "RussianDashRule", "из—за", ["positive", "upstream_test"]),
    ("upstream_dash_rostov", "RussianDashRule", "Ростов — на — Дону", ["positive", "upstream_test"]),
    ("upstream_dash_correct", "RussianDashRule", "Он вышел из-за забора.", ["negative", "upstream_test"]),
    ("upstream_specific_air_france", "RussianSpecificCaseRule", "I like air France.", ["positive", "upstream_test"]),
    ("upstream_specific_central_bank", "RussianSpecificCaseRule", "центральный банк РФ", ["positive", "upstream_test"]),
    ("upstream_specific_correct", "RussianSpecificCaseRule", "Центральный банк РФ", ["negative", "upstream_test"]),
    ("upstream_brackets_apostrophe", "RussianUnpairedBracketsRule", "В таком ключе был начат в мае 1823 в Кишинёве роман в стихах 'Евгений Онегин.", ["positive", "upstream_test"]),
    ("upstream_brackets_balanced", "RussianUnpairedBracketsRule", "(О жене и детях не беспокойся, я беру их на свои руки).", ["negative", "upstream_test"]),
    ("upstream_brackets_numerals", "RussianUnpairedBracketsRule", "а), б), Д)..., ДД), аа) и 1а)", ["negative", "upstream_test"]),
    ("upstream_verb_wrong_present", "RussianVerbConjugationRule", "Мы думаю", ["positive", "upstream_test", "morphology"]),
    ("upstream_verb_wrong_past", "RussianVerbConjugationRule", "Она ходил", ["positive", "upstream_test", "morphology"]),
    ("upstream_verb_correct", "RussianVerbConjugationRule", "Они пишут", ["negative", "upstream_test", "morphology"]),
    ("upstream_comma", "CommaWhitespaceRule", "Не род , а ум поставлю в воеводы.", ["positive", "registered_example"]),
    ("upstream_uppercase", "UppercaseSentenceStartRule", "Закончилось лето. дети снова сели за школьные парты.", ["positive", "registered_example"]),
    ("real_multiple_findings", "CommaWhitespaceRule", "😀 Раз ,два ,три.", ["positive", "multi_finding", "non_bmp"]),
]


def _decode(value: str) -> str:
    return base64.b64decode(value).decode("utf-8") if value else ""


def _probe(java: str, jar: Path, rule_id: str, text: str) -> list[dict[str, Any]]:
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    proc = subprocess.run(
        [java, "-Dfile.encoding=UTF-8", "-cp", f"{JAVA_SOURCE.parent};{jar}", "JavaRulesOracle0011", "--check", rule_id, encoded],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    mapper = Utf16CodePointMapper(text)
    findings = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        fields.extend([""] * (9 - len(fields)))
        start16, end16 = int(fields[0]), int(fields[1])
        suggestions = tuple(_decode(fields[7]).split("\u0000")) if fields[7] else ()
        start, end = mapper.utf16_to_codepoint(start16), mapper.utf16_to_codepoint(end16)
        findings.append({
            "rule_id": fields[2],
            "category_id": fields[3],
            "category_name": _decode(fields[4]),
            "message": _decode(fields[5]),
            "short_message": _decode(fields[6]),
            "suggestions": list(suggestions),
            "url": _decode(fields[8]) or None,
            "from_utf16": start16,
            "to_utf16": end16,
            "from": start,
            "to": end,
            "source_slice": text[start:end],
        })
    return findings


def _signature(case: dict[str, Any]) -> str:
    payload = {key: case[key] for key in ("id", "rule_class", "rule_id", "text", "coverage", "expected")}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def generate(cases: list[tuple[str, str, str, list[str]]], path: Path, jar: Path, build_id: str) -> None:
    compiled = []
    for case_id, rule_class, text, coverage in cases:
        rule_id = RULES[rule_class]
        case = {
            "id": case_id,
            "rule_class": rule_class,
            "rule_id": rule_id,
            "text": text,
            "explicitly_enabled": True,
            "coverage": coverage,
            "expected": _probe("java", jar, rule_id, text),
        }
        case["finding_count"] = len(case["expected"])
        case["semantic_signature"] = _signature(case)
        compiled.append(case)
    data = {
        "metadata": {
            "schema_version": "1.0.0",
            "task": "0011",
            "pinned_lt_commit": "e807fcde6a6506191e1470744d2345da28c26be6",
            "oracle_build_id": build_id,
            "oracle_generated": True,
            "case_count": len(compiled),
        },
        "cases": compiled,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "tests" / "fixtures")
    args = parser.parse_args()
    oracle = JavaLanguageToolOracle()
    identity = oracle.validate_oracle()
    jar = Path(identity["jar_path"])
    subprocess.run(["javac", "-encoding", "UTF-8", "-cp", str(jar), str(JAVA_SOURCE)], check=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    generate(SYNTHETIC_CASES, args.output_dir / "oracle_java_rules_0011_synthetic.json", jar, identity["oracle_build_id"])
    generate(RUSSIAN_CASES, args.output_dir / "oracle_java_rules_0011_russian.json", jar, identity["oracle_build_id"])


if __name__ == "__main__":
    main()
