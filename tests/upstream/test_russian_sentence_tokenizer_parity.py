"""Upstream test parity for Russian sentence segmentation matching LanguageTool v6.8."""

import json
from pathlib import Path
import pytest

from pylat_ru.tokenization.sentence import RussianSentenceTokenizer


def test_upstream_russian_srx_sentence_tokenizer_test_suite():
    """Exact port of upstream RussianSRXSentenceTokenizerTest.java test cases."""
    stokenizer = RussianSentenceTokenizer()

    # From the Russian abbreviation list in RussianSRXSentenceTokenizerTest.java:
    cases = [
        "Отток капитала из России составил 7 млрд. долларов, сообщил министр финансов Алексей Кудрин.",
        "Журнал издаётся с 1967 г., пользуется большой популярностью в мире.",
        "С 2007 г. периодичность выхода газеты – 120 раз в год.",
        "Редакция журнала находится в здании по адресу: г. Москва, 110000, улица Мира, д. 1.",
        "Все эти вопросы заставляют нас искать ответы в нашей истории 60-80-х гг. прошлого столетия.",
        "Более 300 тыс. документов и справочников.",
        "Скидки до 50000 руб. на автомобили.",
        "Изготовление визиток любыми тиражами (от 20 шт. до 10 тысяч) в минимальные сроки (от 20 минут).",
        "Временно не работает, т.к. не поддерживается.",
    ]

    for sentence in cases:
        tokens = stokenizer.tokenize(sentence)
        assert len(tokens) == 1
        assert tokens[0] == sentence


def test_oracle_sentence_tokenization_corpus(fixtures_dir: Path):
    """Verify entire committed oracle sentence tokenization test fixture corpus."""
    fixture_path = fixtures_dir / "oracle_russian_sentence_tokenization.json"
    assert fixture_path.is_file(), f"Missing oracle sentence fixture: {fixture_path}"

    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert data["metadata"]["target_pin"].startswith("v6.8")

    manifest_path = fixtures_dir.parent.parent / "compat" / "oracle_manifest.json"
    assert manifest_path.is_file(), f"Missing manifest: {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    meta = data["metadata"]
    build_id = meta.get("oracle_build_id")
    assert build_id is not None, "Missing oracle_build_id in fixture metadata"
    build_map = {b["build_id"]: b for b in manifest["trusted_oracle_builds"]}
    assert build_id in build_map, f"Build ID '{build_id}' not found in trusted manifest builds"
    build = build_map[build_id]
    assert meta["oracle_jar_sha256"] == build["jar_sha256"]

    tokenizer_ru_two = RussianSentenceTokenizer(single_line_breaks_marks_paragraph=False)
    tokenizer_ru_one = RussianSentenceTokenizer(single_line_breaks_marks_paragraph=True)

    for case in data["cases"]:
        text = case["text"]
        mode = case.get("mode", "ru_two")
        expected = tuple(case["expected_sentences"])

        tokenizer = tokenizer_ru_one if mode == "ru_one" else tokenizer_ru_two
        actual = tokenizer.tokenize(text)

        assert actual == expected, (
            f"Sentence segmentation mismatch in case '{case['id']}':\n"
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

        # UTF-16 surrogate checks for non-BMP cases
        if case.get("utf16_offsets_divergence"):
            has_divergence = any(s.utf16_end != s.end for s in spans)
            assert has_divergence, f"Expected UTF-16 divergence in case {case['id']}"
