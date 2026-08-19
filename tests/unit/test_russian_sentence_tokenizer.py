"""Unit tests for RussianSentenceTokenizer API, modes, and span behavior."""

import pytest
from pylat_ru.tokenization.sentence import RussianSentenceTokenizer


def test_russian_sentence_tokenizer_default_mode():
    """Verify default mode is ru_two with single_line_breaks_marks_paragraph=False."""
    tokenizer = RussianSentenceTokenizer()
    assert tokenizer.single_line_breaks_marks_paragraph is False
    assert tokenizer.mode == "ru_two"


def test_russian_sentence_tokenizer_single_line_mode():
    """Verify single-line mode is ru_one with single_line_breaks_marks_paragraph=True."""
    tokenizer = RussianSentenceTokenizer(single_line_breaks_marks_paragraph=True)
    assert tokenizer.single_line_breaks_marks_paragraph is True
    assert tokenizer.mode == "ru_one"


def test_russian_sentence_tokenizer_empty_and_whitespace():
    """Verify empty input and whitespace-only text handling."""
    tokenizer = RussianSentenceTokenizer()
    assert tokenizer.tokenize("") == ()
    assert tokenizer.tokenize_spans("") == ()

    # Whitespace text returns as single segment
    text = "   \n\t  "
    assert tokenizer.tokenize(text) == (text,)
    spans = tokenizer.tokenize_spans(text)
    assert len(spans) == 1
    assert spans[0].text == text
    assert spans[0].start == 0
    assert spans[0].end == len(text)


def test_russian_sentence_tokenizer_exact_reconstruction():
    """Verify concatenated sentence spans reconstruct original text exactly without alteration."""
    texts = [
        "Отток капитала из России составил 7 млрд. долларов, сообщил министр финансов Алексей Кудрин.",
        "Первое предложение. Второе предложение! И третье? Да.",
        "«Это великолепно!» — воскликнул он. Она лишь улыбнулась.",
        "Первый абзац.\n\nВторой абзац с переносом.",
        "Привет мир! 👍 Это эмодзи. 🎉 Еще одно предложение!",
    ]
    tokenizer = RussianSentenceTokenizer()
    for text in texts:
        sentences = tokenizer.tokenize(text)
        assert "".join(sentences) == text

        spans = tokenizer.tokenize_spans(text)
        assert "".join(s.text for s in spans) == text
        for s in spans:
            assert text[s.start : s.end] == s.text
