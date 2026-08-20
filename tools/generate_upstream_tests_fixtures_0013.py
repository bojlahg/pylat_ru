"""Generate the Task-0013 upstream-test oracle fixture from the trusted Java LT oracle.

Task 0013 section 25 requires that every core/generic upstream test method that
earlier tasks claimed as Russian compatibility evidence is reconciled.  Those
seven core rule tests execute against the ``Demo``/``FakeLanguage`` classpath,
so their literal expectations are not a Russian contract.  This generator runs
the exact pinned scenario inputs through the trusted Java oracle **with the
Russian language**, which is the contract ``pylat_ru`` must reproduce.

Development-only.  Never imported by production code.

Usage::

    python -m tools.generate_upstream_tests_fixtures_0013
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from pylat_ru.tokenization.offsets import Utf16CodePointMapper
from tools.differential_lt import JavaLanguageToolOracle

ROOT = Path(__file__).resolve().parents[1]
JAVA_SOURCE = ROOT / "tools" / "JavaRulesOracle0012.java"
PINNED_LT_COMMIT = "e807fcde6a6506191e1470744d2345da28c26be6"

CORE = "languagetool-core/src/test/java/org/languagetool/rules"

LONG_SENTENCE_40 = (
    "Now this is not "
    + "a a a a a a a a a a a " * 4
)
QUOTE_BODY = (
    "When days grow dark and nights grow dreary, we can be thankful that our God "
    "combines in his nature a creative synthesis of love and justice which will "
    "lead us through life’s dark valleys and into sunlit pathways of hope and "
    "fulfillment"
)


def _case(
    case_id: str,
    source: str,
    method: str,
    scenario: str,
    rule_id: str,
    text: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "upstream_source": source,
        "upstream_method": method,
        "upstream_scenario": scenario,
        "rule_id": rule_id,
        "text": text,
        "config": config or {},
    }


def _comma(index: int, text: str) -> dict[str, Any]:
    return _case(
        f"comma_ws_{index:02d}",
        f"{CORE}/CommaWhitespaceRuleTest.java",
        "testRule",
        f"assertMatches[{index}]",
        "COMMA_PARENTHESIS_WHITESPACE",
        text,
    )


COMMA_TEXTS = [
    "This is a test sentence.",
    "I work with the technology .Net and Azure.",
    "I work with the technology .NET and Azure.",
    "I use .MP3 or .WAV file suffix",
    "This, is, a test sentence.",
    "This (foo bar) is a test!.",
    "Das kostet €2,45.",
    "Das kostet 50,- Euro",
    "This is a sentence with ellipsis ...",
    "This is a figure: .5 and it's correct.",
    "This is $1,000,000.",
    "This is 1,5.",
    "This is a ,,test''.",
    "Run ./validate.sh to check the file.",
    "This is, really, non-breaking whitespace.",
    "In his book, Einstein proved this to be true.",
    "- [ ] A checkbox at GitHub",
    "- [x] A checked checkbox at GitHub",
    "A sentence 'with' ten \"correct\" examples of ’using’ quotation “marks” at «once» in it.",
    "I'd recommend resaving the .DOC as a PDF file.",
    "I'd recommend resaving the .mp3 as a WAV file.",
    "I'd suggest buying the .org domain.",
    ". This isn't good.",
    "), this isn't good.",
    "Das sind .exe-Dateien",
    "I live in .Los Angeles",
    "Die Vertriebsniederlassu­ng der Versorgungstechnik..­.",
    "Die Vertriebsniederlassu­ng der Versorgungstechnik..­.\n",
    "This,is a test sentence.",
    "This , is a test sentence.",
    "This ,is a test sentence.",
    ",is a test sentence.",
    "This ( foo bar) is a test!.",
    "This (foo bar ) is a test!.",
    "This is a sentence with an orphaned full stop .",
    "This is a test with a OOo footnote, which is denoted by 0x2 in the text.",
    "A sentence ' with ' ten \" incorrect \" examples of ’ using ’ quotation “ marks ” at « once » in it.",
    "A sentence ' with' one examples of wrong quotations marks in it.",
    "A sentence 'with ' one examples of wrong quotations marks in it.",
    "ABB (  z.B. )",
    "This ,",
    "You \" fixed\" it.",
    "You \"fixed \" it.",
    "Ellipsis . . . as suggested by The Chicago Manual of Style",
    "Ellipsis . . . . as suggested by The Chicago Manual of Style",
]

MULTIPLE_WHITESPACE_TEXTS = [
    "This is a test sentence.",
    "This﻿ is a test sentence.",
    "This﻿﻿ is a test sentence.",
    "This ﻿is a test sentence.",
    "This﻿⁠ is a test sentence.",
    "﻿﻿This is a\n⁠\ntest sentence...",
    "This is a test sentence...",
    "\n\tThis is a test sentence...",
    "Multiple tabs\t\tare okay",
    "\n This is a test sentence...",
    "\n    This is a test sentence...",
    "This  is a test sentence.",
    "\n   This  is a test sentence.",
    "This is a test   sentence.",
    "This is   a  test   sentence.",
    "\t\t\t    \t\t\t\t  ",
    "This  is a test sentence.",
]

SENTENCE_WHITESPACE_TEXTS = [
    "This is a text. And there's the next sentence.",
    "This is a text! And there's the next sentence.",
    "This is a text\nAnd there's the next sentence.",
    "This is a text\n\nAnd there's the next sentence.",
    "This is a text.And there's the next sentence.",
    "This is a text!And there's the next sentence.",
    "This is a text?And there's the next sentence.",
]

UPPERCASE_TEXTS = [
    "this",
    "a) This is a test sentence.",
    "iv. This is a test sentence...",
    "\"iv. This is a test sentence...\"",
    "»iv. This is a test sentence...",
    "This",
    "This is",
    "This is a test sentence",
    "",
    "http://www.languagetool.org",
    "eBay can be at sentence start in lowercase.",
    "¿Esto es una pregunta?",
    "¿Esto es una pregunta?, ¿y esto?",
    "ø This is a test sentence with a wrong bullet character.",
    "this is a test sentence.",
    "this!",
    "'this is a sentence'.",
    "\"this is a sentence.\"",
    "„this is a sentence.",
    "«this is a sentence.",
    "‘this is a sentence.",
    "¿esto es una pregunta?",
    "¿Esto es una pregunta? ¿y esto?",
]

LONG_SENTENCE_40_CASES = [
    " is a rather short text.",
    LONG_SENTENCE_40 + "rather that short text.",
    LONG_SENTENCE_40 + "rather that short text",
    "The sun slowly set behind the majestic mountains, casting a warm golden glow "
    "over the tranquil valley below, where a gentle breeze rustled the leaves of "
    "the trees, and the sound of a distant stream provided a soothing backdrop to "
    "the peaceful scene.",
    f"The quote “{QUOTE_BODY}” (p. 9) refers to God’s nature as a combination of love and justice.",
    f"The quote \"{QUOTE_BODY}\" (p. 9) refers to God’s nature as a combination of love and justice.",
    f"The quote «{QUOTE_BODY}» (p. 9) refers to God’s nature as a combination of love and justice.",
    f"The quote „{QUOTE_BODY}“ (p. 9) refers to God’s nature as a combination of love and justice.",
    "The quote \"When days\" grow dark and nights grow dreary, we can be thankful "
    "that our God combines in his nature a creative synthesis of love and justice "
    "which will lead us through life’s dark valleys and into sunlit pathways of "
    "hope \"and fulfillment\" (p. 9) refers to God’s nature as a combination of love and justice.",
    f"The quote {QUOTE_BODY} (p. 9) refers to God’s nature as a combination of love and justice.",
    f"The quote “{QUOTE_BODY}» (p. 9) refers to God’s nature as a combination of love and justice.",
]

LONG_SENTENCE_6_CASES = [
    "This is a rather short text.",
    "This is also a rather short text.",
    "These ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ don't count.",
    "one two three four five six.",
    "one two three (four) five six.",
    "one two three four five six seven.",
    "Eins zwei drei vier fünf sechs.",
    "\n\n\nEins zwei drei vier fünf sechs seven",
    "Eins zwei drei vier fünf sechs seven\n\n\n",
    "\n\n\nEins zwei drei vier fünf sechs seven\n\n\n",
    "\n\n\nEins zwei drei vier fünf sechs seven.",
    "Eins zwei drei vier fünf sechs seven.\n\n\n",
    "\n\n\nEins zwei drei vier fünf sechs seven.\n\n\n",
]

LONG_PARAGRAPH_CASES = [
    "This is a short paragraph.",
    "This is only almost long paragraph by unit test standards.",
    "Here's some text as a filler. This is a long paragraph by unit test standards.",
    "Here's some text as a filler.  A test. A long paragraph by unit test standards.",
    "Here's some text as a filler.  A test.\nNot a long paragraph.\nBecause of the line breaks.\n",
    "- [ ] A test.\n- [ ] Not a long paragraph.\n- [ ] Because of the line breaks.\n- [ ] More text even.\n",
    "This is a short paragraph.\n\nHere's some text as filler. This is a long paragraph by unit test standards.",
    "Here's some text as filler. This is a long paragraph by unit test standards.\n\n"
    "Another paragraph.\n\nHere's some text as morefiller - this is a long paragraph by unit test standards.",
]

PUNCTUATION_PARAGRAPH_END2_CASES = [
    "2. This is an item in a list",
    "2.2.2. This is an item in a list",
    "This is a test.",
    "This is a test",
    "This is a really nice test",
    "This is a really nice test, and it has enough tokens\n",
    "This is a really nice test, and it has enough tokens\n\n",
    "\"This is a really nice test, and it has enough tokens.\"\n\n",
    "\"This is a really nice test, and it has enough tokens\"\n",
    "\"This is a really nice test, and it has enough tokens\"\n\n",
    "This is a test.\n\nRegards,\nJim",
    "This is a test.\n\nRegards,\n\nJim",
    "This is a test.\n\nKind Regards,\nJim",
    "This is a test.\n\nKind Regards,\n\nJim",
    "This is a test.\n\nKind Regards,\n\nJim Tester",
    "This is a test.\n\nKind Regards,\n\nJim van Tester",
    "This is headline-style text",
    "This is headline-style text.",
    "This is headline-style text. If it gets longer, a dot is needed.",
    "This is headline-style text. If it gets longer, a dot is needed",
    "This is a test\n\nKind Regards,\n\nJim van Tester",
    "This is a really nice test, and it has enough tokens\n\nKind Regards,\n\nJim van Tester",
]


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index, text in enumerate(COMMA_TEXTS):
        cases.append(_comma(index, text))
    for index, text in enumerate(MULTIPLE_WHITESPACE_TEXTS):
        cases.append(_case(
            f"multi_ws_{index:02d}", f"{CORE}/MultipleWhitespaceRuleTest.java",
            "testRule", f"scenario[{index}]", "WHITESPACE_RULE", text,
        ))
    for index, text in enumerate(SENTENCE_WHITESPACE_TEXTS):
        cases.append(_case(
            f"sentence_ws_{index:02d}", f"{CORE}/SentenceWhitespaceRuleTest.java",
            "testMatch", f"scenario[{index}]", "SENTENCE_WHITESPACE", text,
        ))
    for index, text in enumerate(UPPERCASE_TEXTS):
        cases.append(_case(
            f"uppercase_start_{index:02d}", f"{CORE}/UppercaseSentenceStartRuleTest.java",
            "testRule", f"scenario[{index}]", "UPPERCASE_SENTENCE_START", text,
        ))
    for index, text in enumerate(LONG_SENTENCE_40_CASES):
        cases.append(_case(
            f"long_sentence40_{index:02d}", f"{CORE}/LongSentenceRuleTest.java",
            "testMatch", f"maxWords=40 scenario[{index}]", "TOO_LONG_SENTENCE", text,
            {"maxWords": 40},
        ))
    for index, text in enumerate(LONG_SENTENCE_6_CASES):
        cases.append(_case(
            f"long_sentence6_{index:02d}", f"{CORE}/LongSentenceRuleTest.java",
            "testMatch", f"maxWords=6 scenario[{index}]", "TOO_LONG_SENTENCE", text,
            {"maxWords": 6},
        ))
    for index, text in enumerate(LONG_PARAGRAPH_CASES):
        cases.append(_case(
            f"long_paragraph_{index:02d}", f"{CORE}/LongParagraphRuleTest.java",
            "testRule", f"maxWords=6 scenario[{index}]", "TOO_LONG_PARAGRAPH", text,
            {"maxWords": 6},
        ))
    for index, text in enumerate(PUNCTUATION_PARAGRAPH_END2_CASES):
        cases.append(_case(
            f"punct_par_end2_{index:02d}", f"{CORE}/PunctuationMarkAtParagraphEnd2Test.java",
            "test", f"scenario[{index}]", "PUNCTUATION_PARAGRAPH_END2", text,
        ))
    return cases


def _decode(value: str) -> str:
    return base64.b64decode(value).decode("utf-8") if value else ""


def _config_arg(config: dict[str, Any]) -> str:
    return ";".join(
        f"{key}={str(value).lower() if isinstance(value, bool) else value}"
        for key, value in sorted(config.items())
    )


def _probe(jar: Path, rule_id: str, text: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    config_encoded = base64.b64encode(_config_arg(config).encode("utf-8")).decode("ascii")
    proc = subprocess.run(
        ["java", "-Dfile.encoding=UTF-8", "-cp", f"{JAVA_SOURCE.parent}{os.pathsep}{jar}",
         "JavaRulesOracle0012", "--check", rule_id, encoded, config_encoded],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    mapper = Utf16CodePointMapper(text)
    findings = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        fields.extend([""] * (9 - len(fields)))
        start16, end16 = int(fields[0]), int(fields[1])
        suggestions_raw = _decode(fields[7])
        start, end = mapper.utf16_to_codepoint(start16), mapper.utf16_to_codepoint(end16)
        findings.append({
            "rule_id": fields[2],
            "category_id": fields[3],
            "category_name": _decode(fields[4]),
            "message": _decode(fields[5]),
            "short_message": _decode(fields[6]),
            "suggestions": suggestions_raw.split(chr(0)) if suggestions_raw else [],
            "url": _decode(fields[8]) or None,
            "from_utf16": start16,
            "to_utf16": end16,
            "from": start,
            "to": end,
            "source_slice": text[start:end],
        })
    return findings


def _signature(case: dict[str, Any]) -> str:
    """Semantic signature over query semantics only (Task 0013 section 14)."""
    payload = {
        "execution_mode": "single_rule",
        "rule_id": case["rule_id"],
        "text": case["text"],
        "config": case["config"],
        "explicitly_enabled": True,
        "explicitly_enabled_rules": [],
        "explicitly_disabled_rules": [],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=ROOT / "tests" / "fixtures" / "oracle_upstream_tests_0013.json")
    args = parser.parse_args()

    oracle = JavaLanguageToolOracle()
    identity = oracle.validate_oracle()
    jar = Path(identity["jar_path"])
    subprocess.run(["javac", "-encoding", "UTF-8", "-cp", str(jar), str(JAVA_SOURCE)], check=True)

    compiled = []
    seen_ids: set[str] = set()
    seen_signatures: set[str] = set()
    for raw in build_cases():
        case = dict(raw)
        case["execution_mode"] = "single_rule"
        case["explicitly_enabled"] = True
        case["expected"] = _probe(jar, case["rule_id"], case["text"], case["config"])
        case["finding_count"] = len(case["expected"])
        case["semantic_signature"] = _signature(case)
        if case["id"] in seen_ids:
            raise ValueError(f"duplicate case id: {case['id']}")
        if case["semantic_signature"] in seen_signatures:
            raise ValueError(f"duplicate semantic signature for case: {case['id']}")
        seen_ids.add(case["id"])
        seen_signatures.add(case["semantic_signature"])
        compiled.append(case)

    data = {
        "metadata": {
            "schema_version": "1.0.0",
            "task": "0013",
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": identity["oracle_build_id"],
            "oracle_generated": True,
            "language": "ru",
            "case_count": len(compiled),
            "description": (
                "Pinned core/generic upstream test scenarios executed against the "
                "trusted Java oracle with the Russian language."
            ),
        },
        "cases": compiled,
    }
    args.output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {len(compiled)} cases to {args.output}")


if __name__ == "__main__":
    main()
