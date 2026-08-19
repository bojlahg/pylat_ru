"""tests/upstream/test_russian_grammar_oracle_parity.py

Differential test suite validating 100% parity between pylat_ru RussianGrammarEngine
and the pinned Java LanguageTool Russian grammar rules oracle across all fixture cases.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "oracle_russian_grammar_core.json"


@pytest.fixture(scope="module")
def fixture_data():
    assert FIXTURE_PATH.is_file(), f"Missing fixture file: {FIXTURE_PATH}"
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_grammar_core_oracle_cases_count(fixture_data):
    """Verify minimum required test cases in grammar core fixture."""
    cases = fixture_data.get("cases", [])
    assert len(cases) >= 60, f"Expected at least 60 test cases, found {len(cases)}"


def test_grammar_core_oracle_parity_all_cases(fixture_data):
    """Verify exact parity for all pattern rule cases between Java LT oracle and pylat_ru."""
    disambiguator = RussianHybridDisambiguator.get_instance()
    chunker = RussianChunker()
    engine = RussianGrammarEngine.get_instance()

    cases = fixture_data.get("cases", [])
    mismatches = []

    for case in cases:
        case_id = case["id"]
        text = case["text"]
        full_rule_id = case["full_rule_id"]
        oracle_res = case["oracle_result"]

        # Run pylat_ru pipeline
        sent = disambiguator.disambiguate_text(text)
        sent.text = text
        chunker.chunk(sent)

        act_matches = engine.check_rule(sent, full_rule_id)
        exp_matches = oracle_res.get("matches", [])

        if len(act_matches) != len(exp_matches):
            mismatches.append(
                f"[{case_id}] ({full_rule_id}) Match count mismatch: expected {len(exp_matches)}, got {len(act_matches)} for text {text!r}"
            )
            continue

        for i, (act_m, exp_m) in enumerate(zip(act_matches, exp_matches)):
            # Verify offsets
            if act_m.from_pos_utf16 != exp_m["from_utf16"] or act_m.to_pos_utf16 != exp_m["to_utf16"]:
                mismatches.append(
                    f"[{case_id}] ({full_rule_id}) Match {i} offset mismatch: expected ({exp_m['from_utf16']}, {exp_m['to_utf16']}), got ({act_m.from_pos_utf16}, {act_m.to_pos_utf16})"
                )

            # Verify suggestions
            exp_suggs = exp_m.get("suggestions", [])
            if act_m.suggestions != exp_suggs:
                mismatches.append(
                    f"[{case_id}] ({full_rule_id}) Match {i} suggestions mismatch: expected {exp_suggs}, got {act_m.suggestions}"
                )

    assert not mismatches, f"Grammar core parity failures ({len(mismatches)}):\n" + "\n".join(mismatches)
