"""src/pylat_ru/tokenization/word.py

Native Russian word tokenizer matching LanguageTool v6.8 RussianWordTokenizer.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Set

import regex

from pylat_ru.tokenization.offsets import (
    SentenceSpan,
    TokenSpan,
    tokens_to_spans,
    validate_spans_invariants,
)

# Upstream delimiter set from WordTokenizer.TOKENIZING_CHARACTERS + ".'"
TOKENIZING_CHARACTERS: str = (
    "\u0020\u00A0\u115f\u1160\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007"
    "\u2008\u2009\u200A\u200B\u200c\u200d\u200e\u200f"
    "\u2028\u2029\u202a\u202b\u202c\u202d\u202e\u202f"
    "\u205F\u2060\u2061\u2062\u2063\u206A\u206b\u206c\u206d"
    "\u206E\u206F\u3000\u3164\ufeff\uffa0\ufff9\ufffa\ufffb"
    "¦‖∣|,.;()[]{}=*#∗+×·÷<>!?:~/\\\"'«»„”“‘’`´‛′›‹…¿¡‼⁇⁈⁉™®\u203d\u00B6\uFFEB\u2E2E"
    "\u2012\u2013\u2014\u2015"
    "\u2500\u3161\u2713"
    "\u25CF\u25CB\u25C6\u27A2\u25A0\u25A1\u2605\u274F\u2794\u21B5\u2756\u25AA\u2751\u2022"
    "\u2B9A\u2265\u2192\u21FE\u21C9\u21D2\u21E8\u21DB"
    "\u00b9\u00b2\u00b3\u2070\u2071\u2074\u2075\u2076\u2077\u2078\u2079"
    "\t\n\r\u000B"
    "'."
)

DELIMITER_SET: Set[str] = set(TOKENIZING_CHARACTERS)

PROTOCOLS: tuple[str, ...] = ("http", "https", "ftp")

URL_CHARS: regex.Pattern = regex.compile(r"^[a-zA-ZÄÖÜäöü0-9/%$-_.+!*'(),?#~]+$")
DOMAIN_CHARS: regex.Pattern = regex.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]+$")
NO_PROTOCOL_URL: regex.Pattern = regex.compile(
    r"^([a-zA-Z0-9][a-zA-Z0-9-]+\.)?([a-zA-Z0-9][a-zA-Z0-9-]+)\.([a-zA-Z0-9][a-zA-Z0-9-]+)/.*$"
)
E_MAIL: regex.Pattern = regex.compile(
    r"(?<!:)@?\b[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))\b"
)

EXTRA_WHITESPACE_CHARS: Set[str] = {
    "\u00A0",
    "\u115f",
    "\u1160",
    "\u1680",
    "\u2000",
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2009",
    "\u200A",
    "\u200B",
    "\u202F",
    "\u205F",
    "\u3000",
    "\uFEFF",
}

QUOTE_OR_DOT_SET: Set[str] = {'"', "»", "«", "‘", "’", "“", "”", "'", "."}
PUNCTUATION_TERMINATORS: Set[str] = {".", ",", ";", ":", "!", "?"}


def is_whitespace_token(token: str) -> bool:
    """Check if token consists entirely of whitespace characters (including Unicode spaces)."""
    if not token:
        return False
    return all(ch.isspace() or ch in EXTRA_WHITESPACE_CHARS for ch in token)


def split_by_delimiters(text: str, delim_set: Set[str]) -> List[str]:
    """Replicate Java StringTokenizer(text, delim, returnDelims=true) behavior."""
    tokens: List[str] = []
    current_word: List[str] = []

    for ch in text:
        if ch in delim_set:
            if current_word:
                tokens.append("".join(current_word))
                current_word.clear()
            tokens.append(ch)
        else:
            current_word.append(ch)

    if current_word:
        tokens.append("".join(current_word))

    return tokens


def join_emails(tokens: List[str]) -> List[str]:
    """Join separated tokens that form a valid email address."""
    full_text = "".join(tokens)
    if "@" in full_text and E_MAIL.search(full_text):
        new_list: List[str] = []
        current_pos = 0
        idx = 0
        for match in E_MAIL.finditer(full_text):
            start = match.start()
            end = match.end()
            while current_pos < end:
                if current_pos < start:
                    new_list.append(tokens[idx])
                elif current_pos == start:
                    new_list.append(match.group())
                current_pos += len(tokens[idx])
                idx += 1
        if current_pos < len(full_text):
            new_list.extend(tokens[idx:])
        return new_list
    return tokens


def url_starts_at(i: int, tokens: List[str]) -> bool:
    """Determine if a URL starts at token index i."""
    token = tokens[i]
    n_tokens = len(tokens)

    # http://, https://, ftp://
    if token in PROTOCOLS and n_tokens > i + 3:
        if tokens[i + 1] == ":" and tokens[i + 2] == "/" and tokens[i + 3] == "/":
            return True

    # www.domain
    if n_tokens > i + 1:
        if token == "www" and tokens[i + 1] == ".":
            return True

    # mydomain.org/
    if (
        n_tokens > i + 3
        and tokens[i + 1] == "."
        and tokens[i + 3] == "/"
        and DOMAIN_CHARS.match(token)
        and DOMAIN_CHARS.match(tokens[i + 2])
    ):
        return True

    # sub.mydomain.org/
    if (
        n_tokens > i + 5
        and tokens[i + 1] == "."
        and tokens[i + 3] == "."
        and tokens[i + 5] == "/"
        and DOMAIN_CHARS.match(token)
        and DOMAIN_CHARS.match(tokens[i + 2])
        and DOMAIN_CHARS.match(tokens[i + 4])
    ):
        return True

    return False


def url_ends_at(i: int, tokens: List[str], url_quote: Optional[str]) -> bool:
    """Determine if a URL ends at token index i."""
    token = tokens[i]
    n_tokens = len(tokens)

    if is_whitespace_token(token) or token in {")", "]"}:
        return True
    elif n_tokens > i + 1:
        next_token = tokens[i + 1]
        if (
            (is_whitespace_token(next_token) or next_token in QUOTE_OR_DOT_SET)
            and (token in PUNCTUATION_TERMINATORS or token == url_quote)
        ) or not URL_CHARS.match(token):
            return True
    else:
        if not URL_CHARS.match(token) or token == "." or token == url_quote:
            return True
    return False


def join_urls(tokens: List[str]) -> List[str]:
    """Join separated tokens that form a valid URL according to LanguageTool heuristics."""
    new_list: List[str] = []
    in_url = False
    url_chunks: List[str] = []
    url_quote: Optional[str] = None

    for i in range(len(tokens)):
        if url_starts_at(i, tokens) and not in_url:
            in_url = True
            if i - 1 >= 0:
                url_quote = tokens[i - 1]
            url_chunks.append(tokens[i])
        elif in_url and url_ends_at(i, tokens, url_quote):
            in_url = False
            url_quote = None
            new_list.append("".join(url_chunks))
            url_chunks.clear()
            new_list.append(tokens[i])
        elif in_url:
            url_chunks.append(tokens[i])
        else:
            new_list.append(tokens[i])

    if url_chunks:
        new_list.append("".join(url_chunks))

    return new_list


class RussianWordTokenizer:
    """Russian word tokenizer matching LanguageTool RussianWordTokenizer."""

    def __init__(self) -> None:
        self._delim_set = DELIMITER_SET

    def get_tokenizing_characters(self) -> str:
        """Return the string of tokenizing delimiter characters."""
        return TOKENIZING_CHARACTERS

    def is_url(self, token: str) -> bool:
        """Check if token is recognized as a URL."""
        for proto in PROTOCOLS:
            if token.startswith(proto + "://") or token.startswith("www."):
                return True
        return bool(NO_PROTOCOL_URL.match(token))

    def is_email(self, token: str) -> bool:
        """Check if token is recognized as an email address matching Java Matcher.matches()."""
        return bool(E_MAIL.fullmatch(token))

    def tokenize(self, text: str) -> tuple[str, ...]:
        """Tokenize text into words, punctuation, and whitespace strings."""
        if not text:
            return ()

        # Russian sentinel preprocessing matching RussianWordTokenizer.java
        aux_text = text
        aux_text = (
            aux_text.replace("б/у", "\u0001\u0001SOCR_BU\u0001\u0001")
            .replace("б/н", "\u0001\u0001SOCR_BN\u0001\u0001")
            .replace(" .. ", "\u0001\u0001SP_DDOT_SP\u0001\u0001")
            .replace(" . ", "\u0001\u0001SP_DOT_SP\u0001\u0001")
            .replace(" .", " \u0001\u0001SP_DOT\u0001\u0001")
            .replace("\u0001\u0001SP_DDOT_SP\u0001\u0001", " .. ")
            .replace("\u0001\u0001SP_DOT_SP\u0001\u0001", " . ")
        )

        st = split_by_delimiters(aux_text, self._delim_set)
        tokens: List[str] = []
        for s in st:
            s = (
                s.replace("\u0001\u0001SOCR_BU\u0001\u0001", "б/у")
                .replace("\u0001\u0001SOCR_BN\u0001\u0001", "б/н")
                .replace("\u0001\u0001SP_DOT\u0001\u0001", ".")
            )
            tokens.append(s)

        joined = join_urls(join_emails(tokens))
        return tuple(joined)

    def tokenize_spans(
        self,
        text: str,
        *,
        base_offset: int = 0,
        base_utf16_offset: int = 0,
    ) -> tuple[TokenSpan, ...]:
        """Tokenize text into TokenSpans with exact code-point and UTF-16 offsets."""
        if not text:
            return ()
        tokens = self.tokenize(text)
        spans = tokens_to_spans(
            tokens,
            base_offset=base_offset,
            base_utf16_offset=base_utf16_offset,
        )
        validate_spans_invariants(spans, text, base_offset=base_offset)
        return spans

    def tokenize_sentence_spans(
        self,
        sentences: Sequence[SentenceSpan],
    ) -> tuple[tuple[TokenSpan, ...], ...]:
        """Tokenize each SentenceSpan into TokenSpans with exact absolute offsets."""
        result: List[tuple[TokenSpan, ...]] = []
        for sent in sentences:
            spans = self.tokenize_spans(
                sent.text,
                base_offset=sent.start,
                base_utf16_offset=sent.utf16_start,
            )
            result.append(spans)
        return tuple(result)
