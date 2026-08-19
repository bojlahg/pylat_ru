"""tests/upstream/test_russian_synthesizer_oracle_parity.py

Compares Python RussianSynthesizer output against committed Java LanguageTool v6.8 oracle fixture.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from pylat_ru.analysis import AnalyzedToken
from pylat_ru.synthesis import RussianSynthesizer

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "oracle_russian_synthesizer_sample.json"


def test_oracle_synthesizer_fixture_parity():
    """Assert 100% exact parity on all queries in oracle_russian_synthesizer_sample.json."""
    assert FIXTURE_PATH.is_file(), f"Missing oracle fixture at {FIXTURE_PATH}"

    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        fixture_data = json.load(f)

    synth = RussianSynthesizer.get_instance()
    queries = fixture_data.get("queries", [])
    assert len(queries) > 0

    mismatches = []
    for q in queries:
        qid = q["id"]
        token_str = q.get("token", q.get("lemma", ""))
        lemma_str = q.get("lemma", token_str)
        pos_tag = q["pos_tag"]
        is_regex = q.get("pos_tag_is_regex", False)
        expected_forms = q["expected_forms"]

        tok = AnalyzedToken(token=token_str, lemma=lemma_str, pos_tag="DUMMY")
        actual_forms = synth.synthesize(tok, pos_tag, pos_tag_is_regex=is_regex)

        if actual_forms != expected_forms:
            mismatches.append(
                f"Query {qid} ({lemma_str}|{pos_tag}, is_regex={is_regex}): "
                f"expected {expected_forms}, got {actual_forms}"
            )

    assert not mismatches, f"Synthesizer oracle parity mismatches:\n" + "\n".join(mismatches)
