"""Unit tests for RussianWordTokenizer API, delimiter splitting, sentinels, and URLs."""

import pytest
from pylat_ru.tokenization.word import (
    RussianWordTokenizer,
    join_emails,
    join_urls,
    split_by_delimiters,
)


def test_russian_word_tokenizer_delimiters_and_empty():
    """Verify delimiter character sets and empty input behavior."""
    tokenizer = RussianWordTokenizer()
    assert tokenizer.tokenize("") == ()
    assert tokenizer.tokenize_spans("") == ()

    chars = tokenizer.get_tokenizing_characters()
    assert " " in chars
    assert "\u00A0" in chars
    assert "–" in chars
    assert "—" in chars
    assert "-" not in chars  # Regular hyphen-minus is not a delimiter
    assert "." in chars
    assert "'" in chars


def test_russian_sentinel_edge_cases():
    """Verify exact Russian sentinel logic for б/у, б/н, and dot variations."""
    tokenizer = RussianWordTokenizer()

    # б/у and б/н
    assert tokenizer.tokenize("Товар б/у") == ("Товар", " ", "б/у")
    assert tokenizer.tokenize("Документ б/н") == ("Документ", " ", "б/н")

    # Dot sentinels
    assert tokenizer.tokenize("слово . другое") == ("слово", " ", ".", " ", "другое")
    assert tokenizer.tokenize("слово .. другое") == ("слово", " ", ".", ".", " ", "другое")
    assert tokenizer.tokenize("слово .") == ("слово", " ", ".")


def test_hyphen_vs_dashes():
    """Verify hyphen-minus remains inside word, while dashes split into separate tokens."""
    tokenizer = RussianWordTokenizer()

    # Hyphen-minus preserved in compound word
    tokens = tokenizer.tokenize("русско-английский")
    assert tokens == ("русско-английский",)

    # En dash and em dash split
    tokens_dash = tokenizer.tokenize("слово – слово — слово")
    assert tokens_dash == ("слово", " ", "–", " ", "слово", " ", "—", " ", "слово")


def test_url_and_email_detection_helpers():
    """Verify is_url and is_email helper methods."""
    tokenizer = RussianWordTokenizer()

    # URL positive & negative
    assert tokenizer.is_url("http://languagetool.org")
    assert tokenizer.is_url("https://languagetool.org/ru/")
    assert tokenizer.is_url("ftp://files.example.com")
    assert tokenizer.is_url("www.languagetool.org")
    assert tokenizer.is_url("sub.languagetool.org/test")
    assert not tokenizer.is_url("plain_word")

    # Email positive (full matches)
    assert tokenizer.is_email("user@example.com")
    assert tokenizer.is_email("dev.all@languagetool.org")
    assert tokenizer.is_email("first.last+tag@sub.domain.co.uk")

    # Email negative (prefixes with trailing text, malformed, or missing parts)
    assert not tokenizer.is_email("@invalid")
    assert not tokenizer.is_email("user@")
    assert not tokenizer.is_email("user@example.com/extra")
    assert not tokenizer.is_email("user@example.com?param=1")
    assert not tokenizer.is_email("user@example.com,")
    assert not tokenizer.is_email("user@example.com:")
    assert not tokenizer.is_email("text before user@example.com")
    assert not tokenizer.is_email("@test.de")
    assert not tokenizer.is_email("f.test@test")


def test_russian_word_tokenizer_exact_reconstruction():
    """Verify concatenated word spans reconstruct original text exactly."""
    texts = [
        "Товар б/у в отличном состоянии.",
        "Документ б/н от 12.05.",
        "This is\u00A0a test with NBSP and \t tabs.",
        "Слово – другое — третье (русско-английский).",
        "Пишите нам: dev.all@languagetool.org или http://foo.org.",
        "Привет 👍 мир!",
    ]
    tokenizer = RussianWordTokenizer()
    for text in texts:
        tokens = tokenizer.tokenize(text)
        assert "".join(tokens) == text

        spans = tokenizer.tokenize_spans(text)
        assert "".join(s.text for s in spans) == text
        for s in spans:
            assert text[s.start : s.end] == s.text
