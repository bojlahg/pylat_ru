"""tests/upstream/test_russian_chunker_oracle_parity.py

Differential test suite validating exact parity between pylat_ru RussianChunker
and the pinned Java LanguageTool RussianChunker oracle across all fixture cases.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "oracle_russian_chunker.json"


@pytest.fixture(scope="module")
def fixture_data():
    assert FIXTURE_PATH.is_file(), f"Missing fixture file: {FIXTURE_PATH}"
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_chunker_oracle_cases_count(fixture_data):
    """Verify minimum required test cases in chunker fixture."""
    cases = fixture_data.get("cases", [])
    assert len(cases) >= 25, f"Expected at least 25 chunker test cases, found {len(cases)}"


def test_chunker_oracle_parity_all_cases(fixture_data):
    """Verify exact parity for all sentences between Java LT oracle and pylat_ru chunker."""
    disambiguator = RussianHybridDisambiguator.get_instance()
    chunker = RussianChunker()

    cases = fixture_data.get("cases", [])
    mismatches = []

    for case in cases:
        case_id = case["id"]
        text = case["text"]
        expected_post_chunker = case["stages"]["post_chunker"]

        # Run pylat_ru pipeline
        sent = disambiguator.disambiguate_text(text)
        chunker.chunk(sent)

        # Filter non-whitespace tokens (or compare all tokens)
        pylat_tokens = [t for t in sent.tokens]

        if len(pylat_tokens) != len(expected_post_chunker):
            mismatches.append(
                f"[{case_id}] Token count mismatch: expected {len(expected_post_chunker)}, got {len(pylat_tokens)} for text {text!r}"
            )
            continue

        for i, (p_tok, exp_tok) in enumerate(zip(pylat_tokens, expected_post_chunker)):
            assert p_tok.token == exp_tok["token"]
            exp_chunks = exp_tok["chunk_tags"]
            act_chunks = p_tok.chunk_tags

            # Normalize empty vs None
            exp_chunks_clean = [c for c in exp_chunks if c]
            act_chunks_clean = [c for c in act_chunks if c]

            if exp_chunks_clean != act_chunks_clean:
                mismatches.append(
                    f"[{case_id}] Token {i} ({p_tok.token!r}) chunk tag mismatch: expected {exp_chunks_clean}, got {act_chunks_clean} in sentence {text!r}"
                )

    assert not mismatches, f"Chunker parity failures ({len(mismatches)}):\n" + "\n".join(mismatches)
