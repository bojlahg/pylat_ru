"""Upstream test parity for Russian word tokenization matching LanguageTool v6.8."""

import json
from pathlib import Path
import pytest

from pylat_ru.tokenization.word import RussianWordTokenizer


def test_oracle_word_tokenization_corpus(fixtures_dir: Path):
    """Verify entire committed oracle word tokenization test fixture corpus."""
    fixture_path = fixtures_dir / "oracle_russian_word_tokenization.json"
    assert fixture_path.is_file(), f"Missing oracle word fixture: {fixture_path}"

    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert data["metadata"]["target_pin"].startswith("v6.8")

    tokenizer = RussianWordTokenizer()

    for case in data["cases"]:
        text = case["text"]
        expected = tuple(case["expected_tokens"])

        actual = tokenizer.tokenize(text)

        assert actual == expected, (
            f"Word tokenization mismatch in case '{case['id']}':\n"
            f"  Input:    {text!r}\n"
            f"  Expected: {expected}\n"
            f"  Actual:   {actual}"
        )

        # Invariant checks on spans
        spans = tokenizer.tokenize_spans(text)
        assert len(spans) == len(expected)
        assert "".join(s.text for s in spans) == text

        for idx, span in enumerate(spans):
            assert span.text == expected[idx]
            assert text[span.start : span.end] == span.text
