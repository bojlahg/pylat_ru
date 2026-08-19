"""Unit tests for tokenization span types and UTF-16 / Python code-point offsets."""

import pytest
from pylat_ru.tokenization.offsets import (
    SentenceSpan,
    TextSpan,
    TokenSpan,
    Utf16CodePointMapper,
    sentences_to_spans,
    tokens_to_spans,
    validate_spans_invariants,
)


def test_text_span_properties_and_validation():
    """Verify TextSpan invariants, lengths, and validation checks."""
    span = TextSpan("Привет", start=0, end=6, utf16_start=0, utf16_end=6)
    assert span.length == 6
    assert span.utf16_length == 6
    assert span.text == "Привет"

    # Start > end error
    with pytest.raises(ValueError, match="Invalid code-point offsets"):
        TextSpan("Привет", start=6, end=0, utf16_start=0, utf16_end=6)

    # UTF16 start > end error
    with pytest.raises(ValueError, match="Invalid UTF-16 offsets"):
        TextSpan("Привет", start=0, end=6, utf16_start=6, utf16_end=0)

    # Text length mismatch
    with pytest.raises(ValueError, match="Text length"):
        TextSpan("Привет", start=0, end=5, utf16_start=0, utf16_end=5)


def test_utf16_code_point_mapper_bmp_text():
    """BMP text (Russian, English, ASCII, Latin) has 1:1 code-point and UTF-16 offsets."""
    text = "Текст на русском языке! 123"
    mapper = Utf16CodePointMapper(text)
    assert not mapper.has_non_bmp
    assert mapper.total_utf16_length == len(text)

    for i in range(len(text) + 1):
        assert mapper.codepoint_to_utf16(i) == i
        assert mapper.utf16_to_codepoint(i) == i


def test_utf16_code_point_mapper_non_bmp_emoji():
    """Non-BMP characters (emoji > 0xFFFF) take 2 UTF-16 code units (surrogate pair)."""
    # "А👍Б" -> 'А' (1 cp, 1 utf16), '👍' (1 cp, 2 utf16), 'Б' (1 cp, 1 utf16)
    text = "А👍Б"
    assert len(text) == 3
    mapper = Utf16CodePointMapper(text)
    assert mapper.has_non_bmp
    assert mapper.total_utf16_length == 4

    # Code point 0: 'А' -> utf16 0
    assert mapper.codepoint_to_utf16(0) == 0
    # Code point 1: '👍' -> utf16 1
    assert mapper.codepoint_to_utf16(1) == 1
    # Code point 2: 'Б' -> utf16 3 (after surrogate pair)
    assert mapper.codepoint_to_utf16(2) == 3
    # Code point 3: end -> utf16 4
    assert mapper.codepoint_to_utf16(3) == 4

    # Reverse lookup
    assert mapper.utf16_to_codepoint(0) == 0
    assert mapper.utf16_to_codepoint(1) == 1
    assert mapper.utf16_to_codepoint(3) == 2
    assert mapper.utf16_to_codepoint(4) == 3


def test_tokens_to_spans_cumulative_and_repeated_tokens():
    """Verify tokens_to_spans builds correct offsets for repeated identical tokens without substring search."""
    tokens = ["слово", " ", "слово", " ", "слово"]
    spans = tokens_to_spans(tokens)

    assert len(spans) == 5
    assert spans[0] == TokenSpan("слово", 0, 5, 0, 5)
    assert spans[1] == TokenSpan(" ", 5, 6, 5, 6)
    assert spans[2] == TokenSpan("слово", 6, 11, 6, 11)
    assert spans[3] == TokenSpan(" ", 11, 12, 11, 12)
    assert spans[4] == TokenSpan("слово", 12, 17, 12, 17)

    validate_spans_invariants(spans, "".join(tokens))


def test_nested_sentence_to_word_spans():
    """Verify word tokenization over multiple SentenceSpans preserves absolute base offsets."""
    text = "Первое предложение. Второе предложение."
    s1 = "Первое предложение. "
    s2 = "Второе предложение."

    mapper = Utf16CodePointMapper(text)
    sentences = sentences_to_spans([s1, s2], mapper=mapper)

    assert sentences[0].start == 0
    assert sentences[0].end == len(s1)
    assert sentences[1].start == len(s1)
    assert sentences[1].end == len(text)

    # Word tokenize s2 with base offset
    s2_tokens = ["Второе", " ", "предложение", "."]
    s2_spans = tokens_to_spans(
        s2_tokens,
        base_offset=sentences[1].start,
        base_utf16_offset=sentences[1].utf16_start,
        mapper=mapper,
    )

    assert s2_spans[0].text == "Второе"
    assert s2_spans[0].start == len(s1)
    assert s2_spans[0].end == len(s1) + 6
    assert text[s2_spans[0].start : s2_spans[0].end] == "Второе"
    assert s2_spans[-1].end == len(text)
    validate_spans_invariants(s2_spans, s2, base_offset=sentences[1].start)
