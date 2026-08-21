"""Python-native equivalents of the Java rules registered by Russian LT 6.8.

``RUSSIAN_RULE_CLASSES`` reproduces the exact 23-entry registration order of
``Russian.getRelevantRules()``: the fifteen rules implemented by Task 0011 plus
the eight spelling, compound, replacement, repetition and coherency rules
implemented by Task 0012.  ``RussianConfusionProbabilityRule`` is a language-model
rule registered separately upstream and remains out of scope.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from importlib.resources import files
import re
import unicodedata
from typing import Any, Iterable, Mapping, Optional, Sequence

from pylat_ru.analysis import AnalyzedSentence, AnalyzedTokenReadings
from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.tokenization.offsets import TokenSpan, Utf16CodePointMapper, tokens_to_spans
from pylat_ru.spelling import (
    DESC_SPELLING,
    RussianSpeller,
    RussianSpellerRuleBase,
    RussianYoSpeller,
    SpellerToken,
    is_all_uppercase,
    is_capitalized_word,
    is_emoji,
    is_punctuation_mark,
    starts_with_uppercase,
    uppercase_first_char,
    utf16_len,
)
from pylat_ru.tokenization.sentence import RussianSentenceTokenizer
from pylat_ru.tokenization.word import RussianWordTokenizer


@dataclass(frozen=True)
class NativeRuleFinding:
    rule_class: str
    rule_id: str
    category_id: str
    category_name: str
    description: str
    message: str
    short_message: str
    suggestions: tuple[str, ...]
    from_pos: int
    to_pos: int
    from_pos_utf16: int
    to_pos_utf16: int
    priority: int
    registration_order: int
    tags: tuple[str, ...] = ()
    original_error: str = ""
    url: str | None = None
    source: str = "java_rule"


@dataclass(frozen=True)
class SentenceUnit:
    text: str
    start: int
    end: int
    analyzed: AnalyzedSentence


@dataclass(frozen=True)
class NativeRuleContext:
    text: str
    sentences: tuple[SentenceUnit, ...]
    mapper: Utf16CodePointMapper
    token_spans: tuple[TokenSpan, ...]
    sentence_token_spans: tuple[tuple[TokenSpan, ...], ...] = ()


def _resource_lines(name: str) -> tuple[str, ...]:
    path = files("pylat_ru.resources.ru").joinpath(name)
    return tuple(path.read_text(encoding="utf-8").splitlines())


def _is_word(token: str) -> bool:
    return bool(token) and unicodedata.category(token[0])[0] in {"L", "N"}


def _is_long_sentence_word(token: str) -> bool:
    """Pinned ``LongSentenceRule.isWordCount`` first-character semantics.

    ``StringTools.isNotWordCharacter`` treats a leading digit as non-word here,
    unlike several other generic rules that intentionally count numeric tokens.
    Keep this predicate local to LongSentenceRule instead of changing their surface.
    """
    return bool(token) and unicodedata.category(token[0]).startswith("L")


#: Pinned ``AnalyzedTokenReadings.NON_WORD_REGEX``, copied verbatim from the
#: constant pool of ``org/languagetool/AnalyzedTokenReadings.class`` in the trusted
#: jar.  It is a single-character class, and ``isNonWord()`` uses ``matches()``, so
#: only a token that is exactly one of these characters is a non-word.  Braces and
#: other punctuation outside the class deliberately count as words.
_NON_WORD_REGEX = re.compile(
    '[.?!…:;,~’\'"„“”»«‚‘›‹()\\[\\]\\-–—*×∗·+÷/=]'
)


def _is_non_word(token: str) -> bool:
    """Pinned ``AnalyzedTokenReadings.isNonWord()``."""
    return _NON_WORD_REGEX.fullmatch(token) is not None


class NativeRule:
    rule_id = ""
    category_id = ""
    category_name = ""
    description = ""
    default_off = False
    priority = 0
    tags: tuple[str, ...] = ()
    # Upstream ``Rule.getIncorrectExamples()`` / ``Rule.getCorrectExamples()``.
    # The strings are the pinned LanguageTool 6.8 ``Example.wrong()`` /
    # ``Example.fixed()`` literals, ``<marker>`` markup included.
    incorrect_examples: tuple[str, ...] = ()
    correct_examples: tuple[str, ...] = ()

    #: True when the pinned rule extends ``TextLevelRule`` rather than ``Rule``.
    #: ``JLanguageTool`` runs the text-level rules over the whole text and collects
    #: their matches *before* the per-sentence ones, which decides who wins a
    #: same-span overlap where both rules have equal priority and length.
    text_level = False

    def __init__(self, registration_order: int, config: Mapping[str, Any] | None = None) -> None:
        self.registration_order = registration_order
        self.config = dict(config or {})

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        raise NotImplementedError

    def finding(
        self,
        context: NativeRuleContext,
        start: int,
        end: int,
        message: str,
        suggestions: Sequence[str] = (),
        short_message: str = "",
        url: str | None = None,
    ) -> NativeRuleFinding:
        return NativeRuleFinding(
            rule_class=type(self).__name__,
            rule_id=self.rule_id,
            category_id=self.category_id,
            category_name=self.category_name,
            description=self.description,
            message=message,
            short_message=short_message,
            suggestions=tuple(suggestions),
            from_pos=start,
            to_pos=end,
            from_pos_utf16=context.mapper.codepoint_to_utf16(start),
            to_pos_utf16=context.mapper.codepoint_to_utf16(end),
            priority=self.priority,
            registration_order=self.registration_order,
            tags=self.tags,
            original_error=context.text[start:end],
            url=url,
        )


class CommaWhitespaceRule(NativeRule):
    rule_id = "COMMA_PARENTHESIS_WHITESPACE"
    category_id = "TYPOGRAPHY"
    category_name = "Типографика"
    description = "Пробелы перед запятой или до и после скобок"
    # pinned upstream examples: org/languagetool/language/Russian.java
    incorrect_examples = (
        "Не род<marker> ,</marker> а ум поставлю в воеводы.",
    )
    correct_examples = (
        "Не род<marker>,</marker> а ум поставлю в воеводы.",
    )

    # Upstream CommaWhitespaceRule.FILE_EXTENSION - deliberately case sensitive:
    # an all-lowercase or an all-uppercase 3-4 letter run, never mixed case.
    _file_extension = re.compile(r"([a-z]{3,4}|[A-Z]{3,4}|ai|mp[34]|MP[34])(-.+)?")
    _domain = re.compile(r"(?i)(com|org|net|int|edu|gov|mil|[a-z]{2})")

    @staticmethod
    def _is_field_code(token: str) -> bool:
        """Upstream ``AnalyzedTokenReadings.isFieldCode`` (office field codes)."""
        return token in ("\u0001", "\u0002")

    @staticmethod
    def _java_trim(token: str) -> str:
        """``String.trim()``: strips code points <= U+0020 only."""
        start, end = 0, len(token)
        while start < end and ord(token[start]) <= 0x20:
            start += 1
        while end > start and ord(token[end - 1]) <= 0x20:
            end -= 1
        return token[start:end]

    @classmethod
    def _string_tools_is_whitespace(cls, token: str) -> bool:
        """Upstream ``StringTools.isWhitespace``."""
        if token in ("\u0001", "\u0002"):
            return False
        if token == "\ufeff":
            return True
        trimmed = cls._java_trim(token)
        if not trimmed:
            return True
        if len(trimmed) == 1:
            if token in ("\u200b", "\u00a0", "\u202f"):
                return True
            return trimmed.isspace()
        return False

    @classmethod
    def _ws(cls, token: str) -> bool:
        """Upstream ``CommaWhitespaceRule.isWhitespaceToken``.

        ``AnalyzedTokenReadings.isWhitespace`` is computed from the token after
        upstream's soft-hyphen cleanup, so a token made only of soft hyphens
        counts as whitespace while ``getToken()`` still returns the original.
        The empty SENT_START token is whitespace for the same reason.
        """
        cleaned = token.replace("\u00ad", "")
        is_whitespace = cls._string_tools_is_whitespace(cleaned)
        return (
            is_whitespace or token == "\u00a0" or cls._is_field_code(token)
        ) and token != "\u200b"

    @staticmethod
    def _is_digit_or_dot(token: str) -> bool:
        """Upstream ``CommaWhitespaceRule.isDigitOrDot`` - first character only."""
        return bool(token) and (token[0] == "." or token[0].isdigit())

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out: list[NativeRuleFinding] = []
        # Upstream implements Rule.match(AnalyzedSentence): the loop state is
        # rebuilt for every sentence and starts on the empty SENT_START token.
        for unit, spans in zip(context.sentences, context.sentence_token_spans):
            out.extend(self._match_sentence(context, unit, spans))
        return out

    def _match_sentence(
        self,
        context: NativeRuleContext,
        unit: SentenceUnit,
        spans: Sequence[TokenSpan],
    ) -> list[NativeRuleFinding]:
        out: list[NativeRuleFinding] = []
        # (token text, start offset) including the leading SENT_START token.
        tokens: list[tuple[str, int, int]] = [("", unit.start, unit.start)]
        tokens.extend((span.text, span.start, span.end) for span in spans)
        prev_white = False
        for i in range(len(tokens)):
            token, _, token_end = tokens[i]
            is_whitespace = self._ws(token)
            if i == 0:
                prev_white = is_whitespace and not self._is_field_code(token)
                continue
            ptoken, prev_start, _ = tokens[i - 1]
            pp, pp_start = (tokens[i - 2][0], tokens[i - 2][1]) if i >= 2 else ("", unit.start)
            msg = None
            repl = None
            start = prev_start
            suggestions: tuple[str, ...] = ()
            two_suggestions = False
            if is_whitespace and ptoken == "(":
                msg, repl = "Не ставьте пробел после открывающейся скобки.", "("
            elif is_whitespace and ptoken in "'\"’”“«»" and pp == " ":
                msg = "Не ставьте пробел у символа кавычек."
                repl = ptoken
                two_suggestions = True
                start = pp_start
                suggestions = (ptoken + " ", " " + ptoken)
            elif not is_whitespace and ptoken == "," and token not in "'\"’”“«»- ," and not any(c.isdigit() for c in pp + token) and pp != ",":
                msg, repl = "Поставьте пробел после запятой.", ", " + token
            elif prev_white:
                if token == ")":
                    msg, repl = "Не ставьте пробел до закрывающейся скобки.", ")"
                elif token == "," and not (i + 1 < len(tokens) and tokens[i + 1][0] == ","):
                    msg = "Поставьте пробел после запятой, а не перед ней."
                    repl = ", " if i + 1 < len(tokens) and not self._ws(tokens[i + 1][0]) else ","
                elif token == ".":
                    nxt = tokens[i + 1][0] if i + 1 < len(tokens) else ""
                    nxt2 = tokens[i + 2][0] if i + 2 < len(tokens) else ""
                    if not self._domain.fullmatch(nxt) and not self._file_extension.fullmatch(nxt):
                        msg, repl = "Не ставьте пробел перед точкой в конце предложения.", "."
                        if self._is_digit_or_dot(nxt):
                            msg = None  # figures such as ".5" and ellipsis
                        elif nxt == "/" and re.fullmatch(r"[a-zA-Z]+", nxt2):
                            msg = None  # commands like "./validate.sh"
            if msg is not None and not two_suggestions and token_end < unit.end:
                # Upstream skips the match when the marked text already equals
                # the single suggested replacement.
                if context.text[start:token_end] == repl:
                    msg = None
            if msg:
                if not suggestions:
                    suggestions = (repl or "",)
                out.append(self.finding(context, start, token_end, msg, suggestions))
            prev_white = is_whitespace and not self._is_field_code(token)
        return out


class UppercaseSentenceStartRule(NativeRule):
    text_level = True
    rule_id = "UPPERCASE_SENTENCE_START"
    category_id = "CASING"
    category_name = "Заглавные буквы"
    description = "Предложение должно начинаться с заглавной буквы"
    # pinned upstream examples: org/languagetool/language/Russian.java
    incorrect_examples = (
        "Закончилось лето. <marker>дети</marker> снова сели за школьные парты.",
    )
    correct_examples = (
        "Закончилось лето. <marker>Дети</marker> снова сели за школьные парты.",
    )

    _quotes = frozenset("\"'„»«“‘¡¿")
    _exceptions = {"n", "w", "x86", "ⓒ", "ø", "cc", "pH", "heylogin"}

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        if len(context.sentences) == 1:
            visible = [t for t in context.token_spans if not t.text.isspace()]
            if len(visible) == 1:
                return []
        out: list[NativeRuleFinding] = []
        previous_last = ""
        for unit in context.sentences:
            spans = tokens_to_spans(RussianWordTokenizer().tokenize(unit.text), base_offset=unit.start, mapper=context.mapper)
            visible = [s for s in spans if not s.text.isspace()]
            if not visible:
                continue
            candidate_idx = 1 if visible[0].text in self._quotes and len(visible) > 1 else 0
            candidate = visible[candidate_idx]
            token = candidate.text
            last = visible[-1].text
            prevent = previous_last in {",", ";"} or any(ch.isdigit() for ch in token)
            if previous_last and previous_last not in ".?!…" and last not in ".?!…":
                prevent = True
            if re.fullmatch(r"(?i)[a-z]|[ivxlcdm]+", token) and candidate_idx + 1 < len(visible) and visible[candidate_idx + 1].text in {".", ")"}:
                prevent = True
            if re.match(r"(?i)https?://|\w+@\w+", token):
                prevent = True
            if token and token[0].islower() and token not in self._exceptions and not prevent:
                replacement = token[0].upper() + token[1:]
                # Pinned ONLY_LOWERCASE_START plus StringTools.isCamelCase, which is
                # `matches("[a-z]+[A-Z][A-Za-z]+")`: a camel-cased product name such as
                # "languageTool" is deliberately left alone.
                if (
                    replacement != token
                    and not re.fullmatch(r"[a-z][A-Z].*", token)
                    and not re.fullmatch(r"[a-z]+[A-Z][A-Za-z]+", token)
                ):
                    out.append(self.finding(context, candidate.start, candidate.end, "Это предложение не начинается с заглавной буквы.", (replacement,), "Заглавные буквы"))
            previous_last = last
        return out


class MultipleWhitespaceRule(NativeRule):
    text_level = True
    rule_id = "WHITESPACE_RULE"
    category_id = "TYPOGRAPHY"
    category_name = "Типографика"
    description = "Повтор пробела"

    @staticmethod
    def _first(token: str) -> bool:
        return token.isspace() and token not in {"\n", "\r", "\r\n"} and not any(c in token for c in "\u200b\ufeff\u2060")

    @staticmethod
    def _removable(token: str) -> bool:
        return MultipleWhitespaceRule._first(token) and token != "\t"

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out: list[NativeRuleFinding] = []
        # The pinned rule walks each sentence's own token array, so a run of spaces
        # split across a sentence boundary is never joined into one repetition.
        for spans in context.sentence_token_spans:
            i = 0
            while i < len(spans):
                if self._first(spans[i].text):
                    first = i
                    i += 1
                    while i < len(spans) and self._removable(spans[i].text):
                        i += 1
                    if i - 1 > first:
                        out.append(
                            self.finding(
                                context,
                                spans[first].start,
                                spans[i - 1].end,
                                "Повтор пробела",
                                (spans[first].text,),
                            )
                        )
                    continue
                if spans[i].text in {"\n", "\r", "\r\n"}:
                    i += 1
                    while i < len(spans) and self._removable(spans[i].text):
                        i += 1
                    continue
                i += 1
        return out


class SentenceWhitespaceRule(NativeRule):
    text_level = True
    rule_id = "SENTENCE_WHITESPACE"
    category_id = "TYPOGRAPHY"
    category_name = "Типографика"
    description = "Отсутствуют пробелы между предложениями"

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out: list[NativeRuleFinding] = []
        for prev, cur in zip(context.sentences, context.sentences[1:]):
            if prev.text and not (len(prev.text[-1]) == 1 and prev.text[-1].replace("\u00a0", " ").strip() == ""):
                spans = tokens_to_spans(RussianWordTokenizer().tokenize(cur.text), base_offset=cur.start, mapper=context.mapper)
                first = next((s for s in spans if not s.text.isspace()), None)
                if first:
                    out.append(self.finding(context, cur.start, cur.start + len(first.text), "Добавьте пробел между предложениями.", (" " + first.text,)))
        return out


#: Tokens the pinned ``AnalyzedTokenReadings.isLinebreak()`` recognises.
_LINEBREAKS = frozenset(("\n", "\r", "\r\n"))

#: Zero-width space, excluded from deletable whitespace by the pinned paragraph rules
#: so office-suite fields (page number, page count) survive.
_ZERO_WIDTH_SPACE = "\u200b"


@dataclass(frozen=True)
class _SentenceStart:
    """Stand-in for the pinned zero-width SENT_START token at array index 0.

    Reproducing it keeps every index in the ported paragraph rules identical to the
    pinned ``sentence.getTokens()`` arithmetic.
    """

    start: int
    end: int
    text: str = ""


def _java_sentence_tokens(context: NativeRuleContext, index: int) -> list[Any]:
    """One sentence's tokens with the pinned SENT_START sentinel at index 0."""
    unit = context.sentences[index]
    return [_SentenceStart(unit.start, unit.start), *context.sentence_token_spans[index]]


def _is_whitespace_token(text: str) -> bool:
    """Pinned ``AnalyzedTokenReadings.isWhitespace()``: the trimmed token is empty."""
    return text.strip() == ""


def _paragraph_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start = 0
    for m in re.finditer(r"(?:\r?\n){2,}", text):
        ranges.append((start, m.start()))
        start = m.end()
    ranges.append((start, len(text)))
    return ranges


class WhiteSpaceBeforeParagraphEnd(NativeRule):
    text_level = True
    rule_id = "WHITESPACE_PARAGRAPH"
    category_id = "STYLE"
    category_name = "Стиль"
    description = "Пробел в конце абзаца"
    default_off = True
    priority = -50

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        """Port of pinned ``WhiteSpaceBeforeParagraphEnd.match(List<AnalyzedSentence>)``.

        The pinned rule walks back over the trailing line breaks, then back over the
        trailing whitespace, and reports the span from the last non-whitespace token
        through the end of the line-break run, suggesting that token on its own.
        """
        out: list[NativeRuleFinding] = []
        for index in range(len(context.sentences)):
            if not _is_paragraph_end(context.sentences, index):
                continue
            tokens = _java_sentence_tokens(context, index)
            last_break = len(tokens) - 1
            while last_break > 0 and tokens[last_break].text in _LINEBREAKS:
                last_break -= 1
            last_white = last_break
            while (
                last_white > 0
                and _is_whitespace_token(tokens[last_white].text)
                and tokens[last_white].text != _ZERO_WIDTH_SPACE
            ):
                last_white -= 1
            if last_white >= last_break:
                continue
            if _is_whitespace_token(tokens[last_white].text):
                from_pos = tokens[last_white + 1].start
                suggestion = ""
            else:
                from_pos = tokens[last_white].start
                suggestion = tokens[last_white].text if last_white > 0 else ""
            out.append(
                self.finding(
                    context,
                    from_pos,
                    tokens[last_break].end,
                    "Удалите пробел в конце абзаца",
                    # Pinned setSuggestedReplacement("") leaves the match with no
                    # suggestion at all rather than one empty replacement.
                    (suggestion,) if suggestion else (),
                )
            )
        return out


class WhiteSpaceAtBeginOfParagraph(NativeRule):
    rule_id = "WHITESPACE_PARAGRAPH_BEGIN"
    category_id = "STYLE"
    category_name = "Стиль"
    description = "Пробел в начале абзаца"
    default_off = True
    priority = -50

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        """Port of pinned ``WhiteSpaceAtBeginOfParagraph.match(AnalyzedSentence)``.

        The pinned rule is sentence level, not paragraph level: every sentence whose
        own token array starts with deletable whitespace is reported, which is why a
        sentence that merely follows another on the same line still matches.
        """
        out: list[NativeRuleFinding] = []
        for index in range(len(context.sentences)):
            tokens = _java_sentence_tokens(context, index)
            position = 1
            while position < len(tokens) and self._is_whitespace_del(
                tokens[position].text
            ):
                position += 1
            if (
                position > 1
                and position < len(tokens)
                and tokens[position].text not in _LINEBREAKS
            ):
                out.append(
                    self.finding(
                        context,
                        tokens[1].start,
                        tokens[position].end,
                        "Удалите пробел в начале абзаца",
                        (tokens[position].text,),
                    )
                )
        return out

    @staticmethod
    def _is_whitespace_del(text: str) -> bool:
        """Pinned ``isWhitespaceDel``: whitespace that may actually be deleted."""
        return (
            _is_whitespace_token(text)
            and text != _ZERO_WIDTH_SPACE
            and text not in _LINEBREAKS
        )


class LongSentenceRule(NativeRule):
    text_level = True
    rule_id = "TOO_LONG_SENTENCE"
    category_id = "STYLE"
    category_name = "Стиль"
    description = "Удобочитаемость: предложение длиной 50 слов"
    max_words = 50
    priority = -101
    tags = ("picky",)

    def __init__(self, registration_order: int, config: Mapping[str, Any] | None = None) -> None:
        super().__init__(registration_order, config)
        self.max_words = int(self.config.get("maxWords", 50))

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out = []
        opening = ["\"", "“", "„", "«", "(", "[", "{", "—"]
        closing = ["\"", "”", "“", "»", ")", "]", "}", "—"]
        for unit in context.sentences:
            if re.search(r"[?!.][\"“”„»«]", unit.text, re.S):
                continue
            spans = tokens_to_spans(RussianWordTokenizer().tokenize(unit.text), base_offset=unit.start, mapper=context.mapper)
            count = 0
            quote = -1
            first = None
            for span in spans:
                token = span.text
                if token in {":", ";", "\n", "\r\n", "\n\r"}:
                    count = 0
                    continue
                if quote == -1 and token in opening:
                    quote = opening.index(token)
                elif quote > -1 and token in closing and closing.index(token) == quote:
                    quote = -1
                elif quote == -1 and _is_long_sentence_word(token):
                    if first is None:
                        first = span
                    if count == self.max_words:
                        last = next(
                            (s for s in reversed(spans) if _is_long_sentence_word(s.text)),
                            span,
                        )
                        idx = spans.index(last)
                        if idx + 1 < len(spans) and spans[idx + 1].text in ".?!":
                            last = spans[idx + 1]
                        out.append(self.finding(context, first.start, last.end, f"Предложение длиной {self.max_words} слов от позиции маркера необходимо проверить. Более короткие предложения лучше воспринимаются читателями."))
                        break
                    count += 1
        return out


class LongParagraphRule(NativeRule):
    text_level = True
    rule_id = "TOO_LONG_PARAGRAPH"
    category_id = "STYLE"
    category_name = "Стиль"
    description = "Удобочитаемость: абзац длиной 220 слов"
    default_off = True
    priority = -15
    tags = ("picky",)

    def __init__(self, registration_order: int, config: Mapping[str, Any] | None = None) -> None:
        super().__init__(registration_order, config)
        self.max_words = int(self.config.get("maxWords", 220))

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out = []
        for start, end in _paragraph_ranges(context.text):
            spans = tokens_to_spans(RussianWordTokenizer().tokenize(context.text[start:end]), base_offset=start, mapper=context.mapper)
            words = [s for s in spans if _is_word(s.text)]
            has_internal_linebreak = "\n" in context.text[start:end].rstrip("\r\n") or "\r" in context.text[start:end].rstrip("\r\n")
            over_limit = len(words) > self.max_words + 5
            if over_limit and not has_internal_linebreak and len(words) >= self.max_words:
                out.append(self.finding(context, words[self.max_words - 2].start, words[self.max_words - 1].end, f"Абзац длиной {self.max_words} слов, разбейте его на части."))
        return out


def _is_paragraph_end(units: Sequence[SentenceUnit], index: int) -> bool:
    """Port of pinned ``org.languagetool.tools.Tools.isParagraphEnd``.

    The Russian sentence tokenizer reports ``singleLineBreaksMarksPara() == false``,
    so only doubled line breaks — or a following sentence that itself starts with a
    line break — end a paragraph.
    """
    if index >= len(units) - 1:
        return True
    text = units[index].text
    if text.endswith("\n\n") or text.endswith("\n\r\n\r") or text.endswith("\r\n\r\n"):
        return True
    following = units[index + 1].text
    return following.startswith("\n") or following.startswith("\r\n")


class ParagraphRepeatBeginningRule(NativeRule):
    text_level = True
    rule_id = "PARAGRAPH_REPEAT_BEGINNING_RULE"
    category_id = "STYLE"
    category_name = "Стиль"
    description = "Повтор начала абзаца"
    default_off = True
    priority = -50
    _quotes = re.compile(r"[’\'\"„“”»«‚‘›‹()\[\]]")

    @staticmethod
    def _visible_tokens(context: NativeRuleContext, index: int) -> list[TokenSpan]:
        """Non-whitespace tokens of one sentence.

        Element 0 corresponds to pinned ``getTokensWithoutWhitespace()[1]``, because
        the pinned array carries the zero-width SENT_START token at index 0.
        """
        return [span for span in context.sentence_token_spans[index] if not span.text.isspace()]

    def _num_char_equal_beginning(
        self, last: Sequence[TokenSpan], following: Sequence[TokenSpan], last_base: int
    ) -> int:
        """Port of pinned ``numCharEqualBeginning``.

        Returns the **sentence-local** end offset of the matching token in the *last*
        sentence, or 0.  The article branch of the pinned method tests ``DT`` part-of-
        speech tags, which the Russian tagset never emits, so it can never be taken.
        """
        if not last or not following:
            return 0
        index = 0
        last_token, next_token = last[index].text, following[index].text
        if self._quotes.fullmatch(last_token) and last_token == next_token:
            if len(last) <= index + 1 or len(following) <= index + 1:
                return 0
            index += 1
            last_token, next_token = last[index].text, following[index].text
        if not last_token or not last_token[0].isalpha():
            return 0
        if last_token == next_token:
            return last[index].end - last_base
        return 0

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        units = context.sentences
        if not units:
            return []
        out: list[NativeRuleFinding] = []
        last_index = 0
        for index in range(len(units) - 1):
            if not _is_paragraph_end(units, index):
                continue
            last_tokens = self._visible_tokens(context, last_index)
            next_tokens = self._visible_tokens(context, index + 1)
            last_base = units[last_index].start
            next_base = units[index + 1].start
            end_pos = self._num_char_equal_beginning(last_tokens, next_tokens, last_base)
            if end_pos > 0:
                start = last_tokens[0].start
                if start < last_base + end_pos:
                    msg = "Повтор начала последнего абзаца"
                    out.append(self.finding(context, start, last_base + end_pos, msg))
                    # The pinned rule reuses the *last* sentence's local end offset
                    # against the *next* sentence's base, so the second span is only
                    # as long as the first sentence's leading token.
                    #
                    # That second RuleMatch is built without the guard the first one
                    # has, so when the two offsets coincide -- a repeated paragraph
                    # whose first token is a single character -- pinned LanguageTool
                    # 6.8 throws ``IllegalArgumentException: fromPos must be less than
                    # toPos`` and abandons the whole check.  An empty span is not a
                    # reportable match, so it is skipped here instead; Task 0014
                    # records the resulting difference explicitly.
                    if next_tokens[0].start < next_base + end_pos:
                        out.append(
                            self.finding(
                                context, next_tokens[0].start, next_base + end_pos, msg
                            )
                        )
            last_index = index + 1
        return out


class RussianFillerWordsRule(NativeRule):
    text_level = True
    rule_id = "FILLER_WORDS_RU"
    category_id = "CREATIVE_WRITING"
    category_name = "Стилистические подсказки для творческого письма"
    description = "Слова-паразиты"
    default_off = True
    filler_words = frozenset(("ах", "аа", "ааа", "аааа", "ау", "бу", "вау", "ох", "однако", "эээ", "э", "эй", "эх", "ух-ты", "ух"))

    def __init__(self, registration_order: int, config: Mapping[str, Any] | None = None) -> None:
        super().__init__(registration_order, config)
        self.min_percent = int(self.config.get("minPercent", 8))
        self.exclude_direct_speech = bool(self.config.get("excludeDirectSpeech", True))

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        candidates: list[TokenSpan] = []
        word_count = 0
        direct = False
        for span in context.token_spans:
            if self.exclude_direct_speech and span.text in "\"“„»«" and not direct and span.end < len(context.text) and not context.text[span.end].isspace():
                direct = True
            elif self.exclude_direct_speech and span.text in "\"“”»«" and direct and span.start > 0 and not context.text[span.start - 1].isspace():
                direct = False
            elif (not direct or self.min_percent == 0) and _is_word(span.text):
                word_count += 1
                if span.text in self.filler_words:
                    candidates.append(span)
        if word_count and len(candidates) * 100.0 / word_count > self.min_percent:
            return [self.finding(context, s.start, s.end, "Это — слово-паразит. Удалите его, если это возможно.") for s in candidates]
        return []


class PunctuationMarkAtParagraphEnd2(NativeRule):
    text_level = True
    rule_id = "PUNCTUATION_PARAGRAPH_END2"
    category_id = "PUNCTUATION"
    category_name = "Пунктуация"
    description = "В конце абзаца отсутствует знак пунктуации"
    default_off = True
    # Russian.java contains an orphan priority key PUNCT_DPT_2; it does not
    # match this pinned rule ID, so the effective priority is the base value.

    #: Pinned ``TOKEN_THRESHOLD``.
    token_threshold = 10

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        """Port of pinned ``PunctuationMarkAtParagraphEnd2.match(List<AnalyzedSentence>)``.

        The word count accumulates across the sentences of a paragraph and is reset
        only at a paragraph end, so the threshold applies to the paragraph rather than
        to any single sentence.
        """
        out: list[NativeRuleFinding] = []
        token_count = 0
        for index in range(len(context.sentences)):
            tokens = _java_sentence_tokens(context, index)
            for token in tokens:
                if not _is_non_word(token.text) and not _is_whitespace_token(token.text):
                    token_count += 1
            last_non_space = next(
                (t for t in reversed(tokens) if not _is_whitespace_token(t.text)), None
            )
            is_paragraph_end = _is_paragraph_end(context.sentences, index)
            if (
                is_paragraph_end
                and token_count > self.token_threshold
                and last_non_space is not None
                and last_non_space.text not in {":", ".", "?", "!", "…"}
                and not _is_non_word(last_non_space.text)
            ):
                out.append(
                    self.finding(
                        context,
                        last_non_space.start,
                        last_non_space.end,
                        "Добавьте знак пунктуации в конце абзаца.",
                        (last_non_space.text + ".",),
                    )
                )
            if is_paragraph_end:
                token_count = 0
        return out


#: ``java.util.regex`` ``\p{Punct}`` is the ASCII punctuation block, not a Unicode
#: property, so the pinned character classes are spelled out here rather than
#: approximated with a Unicode class.
_ASCII_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"

#: Pinned ``GenericUnpairedBracketsRule.PUNCTUATION`` = ``[\p{Punct}…–—]``.
_PUNCTUATION = frozenset(_ASCII_PUNCT + "…–—")

#: Pinned ``PUNCTUATION_NO_DOT`` = ``[ldmnstLDMNST]'|[–—\p{Punct}&&[^.]]``.
_PUNCTUATION_NO_DOT_CHARS = frozenset(_ASCII_PUNCT.replace(".", "") + "–—")
_PUNCTUATION_NO_DOT_APOSTROPHE = frozenset("ldmnstLDMNST")

_URL_TOKEN = re.compile(r"https?://.+")
_LIST_MARKER_CONTEXT = re.compile(r"\n[a-zA-Z]\)")
_LIST_MARKER_CONTEXT_AT_START = re.compile(r"[a-zA-Z]\)")

#: Pinned ``RussianUnpairedBracketsRule.NUMERALS_RU``.  The leading inline ``(?i)``
#: makes the whole Java pattern case-insensitive, and ``Matcher.matches()`` anchors it,
#: which is why the trailing ``$`` is dropped here.
_NUMERALS_RU = re.compile(
    r"\d{1,2}?[а-я]*|[а-я]|[А-Я]|[а-я][а-я]|[А-Я][А-Я]|\d{1,2}?[a-zA-Z']*"
    r"|(?i:M*(D?C{0,3}|C[DM])(L?X{0,3}|X[LC])(V?I{0,3}|I[VX]))"
)


@dataclass
class _SymbolLocator:
    """Port of the pinned ``SymbolLocator``/``Symbol`` pair."""

    symbol: str
    opening: bool
    index: int
    start_pos: int
    sentence_index: int


def _index_of(values: Sequence[str], value: str) -> int:
    """``List.indexOf`` semantics: -1 rather than an exception."""
    try:
        return list(values).index(value)
    except ValueError:
        return -1


class RussianUnpairedBracketsRule(NativeRule):
    text_level = True
    """Faithful port of pinned ``RussianUnpairedBracketsRule``.

    The pinned rule is ``GenericUnpairedBracketsRule`` parameterised with the Russian
    symbol lists and numeral pattern.  Task 0014 replaced an earlier approximation that
    diverged on three observable points: the numeral exception ignored the pinned
    ``!(stack.peek() == "(")`` guard, symmetric symbols were popped instead of always
    being pushed when preceded by whitespace, and the pinned
    ``ruleMatchStack``/``createMatch`` cancellation pass was missing entirely.
    """

    rule_id = "RU_UNPAIRED_BRACKETS"
    category_id = "PUNCTUATION"
    category_name = "Пунктуация"
    description = "Непарные скобки или апострофы"
    starts = ("(", "{", "„", "\"", "'", "“")
    ends = (")", "}", "“", "\"", "'", "”")
    # pinned upstream examples: org/languagetool/rules/ru/RussianUnpairedBracketsRule.java
    incorrect_examples = (
        "Самоотверженный поступок Оленина <marker>(</marker>подарок Лукашке коня вызывает лишь удивление и усиливает недоверие к нему станичников.",
    )
    correct_examples = (
        "Самоотверженный поступок Оленина <marker>(</marker>подарок Лукашке коня) вызывает лишь удивление и усиливает недоверие к нему станичников.",
    )

    def _is_no_exception(
        self, tokens: Sequence[Any], index: int
    ) -> bool:
        """Port of ``isNoException``: smiley and URL exceptions."""
        token = tokens[index].token
        if index > 0:
            previous = tokens[index - 1].token
            if _URL_TOKEN.fullmatch(previous) and "(" in previous:
                return False
        if index >= 2:
            previous_previous = tokens[index - 2].token
            previous = tokens[index - 1].token
            if previous_previous in (":", ";") and previous == "-" and token in (")", "("):
                return False
        if index >= 1:
            previous = tokens[index - 1].token
            if (
                previous in (":", ";")
                and not tokens[index].whitespace_before
                and token in (")", "(")
            ):
                return False
        return True

    def _preceded_by_whitespace(self, tokens: Sequence[Any], index: int, j: int) -> bool:
        """Port of ``getPrecededByWhitespace``; only symmetric symbols are constrained."""
        if self.starts[j] != self.ends[j]:
            return True
        previous = tokens[index - 1]
        previous_token = previous.token
        return bool(
            previous.is_sentence_start
            or tokens[index].whitespace_before
            or (
                len(previous_token) == 2
                and previous_token[0] in _PUNCTUATION_NO_DOT_APOSTROPHE
                and previous_token[1] == "'"
            )
            or (len(previous_token) == 1 and previous_token in _PUNCTUATION_NO_DOT_CHARS)
            or previous_token in self.starts
        )

    def _special_case(self, tokens: Sequence[Any], index: int, j: int) -> bool:
        """Port of ``getSpecialCase``; only symmetric symbols are constrained."""
        if not (index < len(tokens) - 1 and self.starts[j] == self.ends[j]):
            return True
        following = tokens[index + 1].token
        return bool(
            tokens[index + 1].whitespace_before
            or (len(following) == 1 and following in _PUNCTUATION)
            or following in self.ends
            or (index >= 1 and tokens[index - 1].token.endswith("-"))
            or following.startswith("-")
            or following == "s"
        )

    def _numeral_exception(
        self, tokens: Sequence[Any], index: int, j: int, stack: Sequence[_SymbolLocator]
    ) -> bool:
        """Port of the pinned numbered-list exception for ``)``.

        Both branches carry ``!(stack.peek() == "(")``: an enumerator such as ``(а)``
        that actually closes an open parenthesis is paired normally rather than skipped.
        """
        if self.ends[j] != ")":
            return False
        top_is_open_paren = bool(stack) and stack[-1].symbol == "("
        if top_is_open_paren:
            return False
        if (
            index > 2
            and (
                tokens[index - 3].has_pos_tag("SENT_START")
                or tokens[index - 2].whitespace_before
            )
            and tokens[index - 1].token == "."
            and _NUMERALS_RU.fullmatch(tokens[index - 2].token)
        ):
            return True
        return bool(index > 1 and _NUMERALS_RU.fullmatch(tokens[index - 1].token))

    def _fill_symbol_stack(
        self,
        base: int,
        tokens: Sequence[Any],
        index: int,
        j: int,
        stack: list[_SymbolLocator],
        sentence_index: int,
    ) -> bool:
        """Port of ``fillSymbolStack``.  Returns True when the symbol was consumed."""
        token = tokens[index].token
        if token != self.starts[j] and token != self.ends[j]:
            return False
        start_pos = base + tokens[index].start_pos
        preceded = self._preceded_by_whitespace(tokens, index, j)
        special = self._special_case(tokens, index, j)
        if not self._is_no_exception(tokens, index):
            return False

        if preceded and token == self.starts[j]:
            stack.append(
                _SymbolLocator(self.starts[j], True, index, start_pos, sentence_index)
            )
            return True

        if (special or tokens[index].is_sentence_end) and token == self.ends[j]:
            if self._numeral_exception(tokens, index, j, stack):
                return False
            if not stack:
                stack.append(
                    _SymbolLocator(self.ends[j], False, index, start_pos, sentence_index)
                )
                return True
            if stack[-1].symbol == self.starts[j]:
                stack.pop()
                return True
            # Every Russian end symbol is unique within the end-symbol list, so the
            # pinned ``isEndSymbolUnique`` branch always pushes here.
            stack.append(
                _SymbolLocator(self.ends[j], False, index, start_pos, sentence_index)
            )
            return True
        return False

    def _corresponding_symbol(self, symbol: str) -> str:
        index = _index_of(self.starts, symbol)
        if index >= 0:
            return self.ends[index]
        return self.starts[_index_of(self.ends, symbol)]

    def _create_match(
        self,
        context: NativeRuleContext,
        matches: list[NativeRuleFinding],
        match_stack: list[_SymbolLocator],
        locator: _SymbolLocator,
    ) -> NativeRuleFinding | None:
        """Port of ``createMatch``, including its cancellation of an earlier match."""
        if match_stack:
            index = _index_of(self.ends, locator.symbol)
            if index >= 0:
                previous = match_stack[-1]
                if previous.symbol == self.starts[index]:
                    if len(matches) > previous.index:
                        del matches[previous.index]
                        match_stack.pop()
                        return None

        # The pinned method pushes before the context guards below, so a suppressed
        # match still participates in later cancellation.
        match_stack.append(
            _SymbolLocator(
                locator.symbol, locator.opening, len(matches), locator.start_pos, locator.sentence_index
            )
        )
        other = self._corresponding_symbol(locator.symbol)
        text = context.text
        start_pos = locator.start_pos
        end_pos = start_pos + len(locator.symbol)
        if end_pos < len(text):
            if start_pos >= 2:
                if _LIST_MARKER_CONTEXT.fullmatch(text[start_pos - 2 : end_pos]):
                    return None
            elif start_pos >= 1:
                if _LIST_MARKER_CONTEXT_AT_START.fullmatch(text[start_pos - 1 : end_pos]):
                    return None
        return self.finding(
            context,
            start_pos,
            end_pos,
            f"Непарный символ: «{other}» скорей всего пропущен",
        )

    @staticmethod
    def _ends_like_real_sentence(text: str) -> bool:
        stripped = text.strip()
        return stripped.endswith((".", "?", "!"))

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        stack: list[_SymbolLocator] = []
        match_stack: list[_SymbolLocator] = []
        matches: list[NativeRuleFinding] = []

        for sentence_index, unit in enumerate(context.sentences):
            tokens = unit.analyzed.non_blank_tokens
            for index in range(1, len(tokens)):
                for j in range(len(self.starts)):
                    if self._fill_symbol_stack(
                        unit.start, tokens, index, j, stack, sentence_index
                    ):
                        break

        # If the stack is odd and symmetric, only the middle symbol is reported.
        is_symmetric = False
        size = len(stack)
        if size > 2 and size % 2 == 1:
            is_symmetric = True
            for position in range(size // 2):
                if _index_of(self.starts, stack[position].symbol) != _index_of(
                    self.ends, stack[size - 1].symbol
                ):
                    is_symmetric = False
                    break

        if is_symmetric:
            found = self._create_match(context, matches, match_stack, stack[size // 2])
            if found is not None:
                matches.append(found)
            return matches

        sentence_count = len(context.sentences)
        for locator in stack:
            found = self._create_match(context, matches, match_stack, locator)
            if found is None:
                continue
            sentence_text = context.sentences[locator.sentence_index].text
            if (
                not locator.opening
                or self._ends_like_real_sentence(sentence_text)
                or sentence_count - 1 > locator.sentence_index
            ):
                matches.append(found)
        return matches


class RussianVerbConjugationRule(NativeRule):
    rule_id = "RU_VERB_CONJUGATION"
    category_id = "GRAMMAR"
    category_name = "Грамматика"
    description = "Согласование личных местоимений с глаголами"
    pronoun = re.compile(r"PNN:(.*):Nom:(.*)")
    future = re.compile(r"VB:(Fut|Real):(.*):(.*):(.*):(.*)")
    past = re.compile(r"VB:Past:(.*):(.*):(.*)")
    # pinned upstream examples: org/languagetool/rules/ru/RussianVerbConjugationRule.java
    incorrect_examples = (
        "<marker>Я идёт</marker>.",
    )
    correct_examples = (
        "<marker>Я иду</marker>.",
    )

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out = []
        for unit in context.sentences:
            tokens = unit.analyzed.get_tokens_without_whitespace()
            for i in range(1, len(tokens) - 1):
                previous = tokens[i - 1].readings[0]
                current = tokens[i].readings[0]
                tag = current.pos_tag or ""
                pm = self.pronoun.search(tag)
                if not pm or previous.token == "и":
                    continue
                nxt = tokens[i + 1].readings[0]
                next2 = tokens[i + 2].readings[0].token if i < len(tokens) - 2 else ""
                if not nxt.pos_tag or (next2 == "быть" and nxt.token == "может") or nxt.token == "целую":
                    continue
                wrong = False
                vm = self.future.search(nxt.pos_tag)
                if vm:
                    pron_gender_num, pron_person = pm.group(1), pm.group(2)
                    verb_num, verb_person = vm.group(4), vm.group(5)
                    wrong = pron_person != verb_person or (pron_gender_num in {"Masc", "Fem", "Neut"} and verb_num == "PL") or (pron_gender_num not in {"Masc", "Fem", "Neut"} and pron_gender_num != verb_num)
                else:
                    vm = self.past.search(nxt.pos_tag)
                    if vm:
                        verb_gender_num = vm.group(3)
                        wrong = (pm.group(1) == "Sin" and verb_gender_num in {"PL", "Neut"}) or (pm.group(1) != "Sin" and pm.group(1) != verb_gender_num)
                if wrong:
                    local_mapper = Utf16CodePointMapper(unit.text)
                    a = unit.start + local_mapper.utf16_to_codepoint(tokens[i].start_pos)
                    b = unit.start + local_mapper.utf16_to_codepoint(tokens[i + 1].start_pos + len(tokens[i + 1].token.encode("utf-16-le")) // 2)
                    out.append(self.finding(context, a, b, "Неверное спряжение глагола или неверное местоимение", (), "Неверное спряжение глагола"))
        return out


class RussianDashRule(NativeRule):
    rule_id = "RU_DASH_RULE"
    category_id = "TYPOGRAPHY"
    category_name = "Типографика"
    description = "Тире вместо дефиса («из — за» вместо «из-за»)."
    priority = 12
    _compounds: frozenset[str] | None = None
    _max_compound_len = 0

    @classmethod
    def compounds(cls) -> frozenset[str]:
        if cls._compounds is None:
            values: set[str] = set()
            for line in _resource_lines("compounds.txt"):
                if not line or line.startswith("#") or line.endswith(("+", "?")):
                    continue
                if line.endswith(("*", "$")):
                    line = line[:-1]
                values.add(line)
            cls._compounds = frozenset(values)
            cls._max_compound_len = max(map(len, values))
        return cls._compounds

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        compounds = self.compounds()
        hits: list[tuple[int, int]] = []
        # All canonical resource entries are <=30 characters and contain no
        # spaces.  Enumerating bounded windows around actual dash characters
        # preserves AbstractDashRule's boundary behavior without constructing
        # 105k expanded Python strings or scanning every entry per check.
        for dash_pos, char in enumerate(context.text):
            if char not in "–—":
                continue
            low = max(0, dash_pos - self._max_compound_len - 2)
            high = min(len(context.text), dash_pos + self._max_compound_len + 3)
            for start in range(low, dash_pos + 1):
                if start > 0 and "\u0400" <= context.text[start - 1] <= "\u04ff":
                    continue
                for end in range(dash_pos + 1, high + 1):
                    if end < len(context.text) and "\u0400" <= context.text[end] <= "\u04ff":
                        continue
                    covered = context.text[start:end]
                    canonical = re.sub(r" ?[–—] ?", "-", covered)
                    variants = {
                        canonical.replace("-", "–"),
                        canonical.replace("-", "—"),
                        canonical.replace("-", " – "),
                        canonical.replace("-", " — "),
                    }
                    if canonical in compounds and covered in variants:
                        hits.append((start, end))
        seen = set()
        out = []
        for start, end in sorted(hits, key=lambda h: (h[0], -(h[1] - h[0]))):
            if start in seen:
                continue
            seen.add(start)
            replacement = re.sub(r" ?[–—] ?", "-", context.text[start:end])
            out.append(self.finding(context, start, end, "Использовано тире вместо дефиса.", (replacement,)))
        return out


class RussianSpecificCaseRule(NativeRule):
    rule_id = "RU_SPECIFIC_CASE"
    category_id = "CASING"
    category_name = "Заглавные буквы"
    description = "Написание специальных наименований в верхнем или нижнем регистре"
    # Russian.java contains an orphan priority key RUSSIAN_SPECIFIC_CASE; it
    # does not match this pinned rule ID, so the effective priority is 0.
    # pinned upstream examples: org/languagetool/rules/ru/RussianSpecificCaseRule.java
    incorrect_examples = (
        "Река <marker>рытый банк</marker> находится в Прикаспийской низменности.",
    )
    correct_examples = (
        "Река <marker>Рытый Банк</marker> находится в Прикаспийской низменности",
    )

    _phrases = tuple(line.strip() for line in _resource_lines("specific_case.txt") if line.strip() and not line.startswith("#"))
    _proper = {p.lower(): p for p in _phrases}
    _max_len = max(len(p.split()) for p in _phrases)

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out = []
        spans = [s for s in context.token_spans if not s.text.isspace()]
        for i in range(len(spans)):
            parts = []
            for j in range(i, min(len(spans), i + self._max_len)):
                parts.append(spans[j].text)
                phrase = " ".join(parts)
                proper = self._proper.get(phrase.lower())
                if proper and not phrase.isupper() and phrase != proper:
                    if i == 0 and proper[0].islower():
                        continue
                    all_upper = all(word and word[0].isupper() for word in proper.split())
                    msg = "Для специальных наименований используйте начальную заглавную букву." if all_upper else "Для специальных наименований используйте предложенное написание заглавных и строчных букв."
                    out.append(self.finding(context, spans[i].start, spans[j].end, msg, (proper,)))
        return out


# ---------------------------------------------------------------------------
# Task 0012 — the eight remaining ordinary Russian Java rules
# ---------------------------------------------------------------------------


def _java_string_hash(text: str) -> int:
    """Java ``String.hashCode()`` (32-bit signed)."""
    value = 0
    for ch in text:
        value = (value * 31 + ord(ch)) & 0xFFFFFFFF
    if value >= 0x80000000:
        value -= 0x100000000
    return value


def _java_hash_spread(hash_value: int) -> int:
    """Java ``HashMap.hash()``: ``h ^ (h >>> 16)``."""
    h = hash_value & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFFFFFF


def java_hash_set_order(items: Sequence[Optional[str]]) -> list[Optional[str]]:
    """Iteration order of a ``java.util.HashSet<String>`` filled with ``items``.

    ``AbstractWordCoherencyRule`` iterates a ``Collectors.toSet()`` result, so the
    first matching base form -- and therefore which match is reported -- depends
    on Java's bucket order rather than reading order.  Buckets are masked with
    ``capacity - 1``, and resizing preserves relative order inside a bucket, so
    a stable sort on the final bucket index reproduces it exactly.
    """
    unique: list[Optional[str]] = []
    seen: set[Optional[str]] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    capacity = 16
    while len(unique) > int(capacity * 0.75):
        capacity *= 2
    mask = capacity - 1
    return sorted(
        unique,
        key=lambda item: 0 if item is None else (_java_hash_spread(_java_string_hash(item)) & mask),
    )


def _uncapitalize(text: str) -> str:
    """``org.apache.commons.lang3.StringUtils.uncapitalize``."""
    if not text:
        return text
    lowered = text[0].lower()
    if len(lowered) != 1:
        return text
    return lowered + text[1:]


def _sentence_tokens(unit: SentenceUnit) -> list[AnalyzedTokenReadings]:
    return list(unit.analyzed.get_tokens_without_whitespace())


class _SentenceOffsets:
    """Translate per-sentence UTF-16 token offsets into absolute code-point offsets."""

    def __init__(self, unit: SentenceUnit) -> None:
        self.unit = unit
        self.mapper = Utf16CodePointMapper(unit.text)

    def absolute(self, utf16_pos: int) -> int:
        return self.unit.start + self.mapper.utf16_to_codepoint(utf16_pos)

    def local(self, utf16_pos: int) -> int:
        return self.mapper.utf16_to_codepoint(utf16_pos)


def _end_pos(token: AnalyzedTokenReadings) -> int:
    """Java ``AnalyzedTokenReadings.getEndPos()`` (UTF-16 units)."""
    return token.start_pos + utf16_len(token.token)


class _SpellerRuleBase(NativeRule):
    """Shared registration wrapper around the native Morfologik speller."""

    speller_class: type[RussianSpellerRuleBase] = RussianSpeller
    category_id = "TYPOS"
    category_name = "Проверка орфографии"

    def __init__(self, registration_order: int, config: Mapping[str, Any] | None = None) -> None:
        super().__init__(registration_order, config)
        unknown = set(self.config) - {"conf_ru_Value"}
        if unknown:
            raise KeyError(f"Unknown configuration keys for {self.rule_id}: {sorted(unknown)}")
        value = self.config.get("conf_ru_Value", 0)
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{self.rule_id} conf_ru_Value must be an int, got {value!r}")
        self.speller = self.speller_class(conf_ru_value=value)

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out: list[NativeRuleFinding] = []
        for unit in context.sentences:
            offsets = _SentenceOffsets(unit)
            tokens = [
                SpellerToken(
                    token=token.token,
                    clean_token=token.get_analyzed_token(0).token or "",
                    start_pos=token.start_pos,
                    is_sentence_start=token.is_sentence_start,
                    is_immunized=token.is_immunized,
                    is_ignore_spelling=token.is_ignore_spelling,
                    is_whitespace_before=bool(getattr(token, "is_whitespace_before", False)),
                )
                for token in _sentence_tokens(unit)
            ]
            for match in self.speller.match(tokens):
                out.append(
                    self.finding(
                        context,
                        offsets.absolute(match.from_pos),
                        offsets.absolute(match.to_pos),
                        match.message,
                        tuple(match.suggestions),
                        match.short_message,
                    )
                )
        return out


class MorfologikRussianSpellerRule(_SpellerRuleBase):
    rule_id = "MORFOLOGIK_RULE_RU_RU"
    description = DESC_SPELLING
    speller_class = RussianSpeller
    # Russian.java configures MORFOLOGIC_RULE_RU_RU (a typo), which never binds
    # the actual rule id, so the effective priority stays at the base value.
    priority = 0
    # pinned upstream examples: org/languagetool/rules/ru/MorfologikRussianSpellerRule.java
    incorrect_examples = (
        "Все счастливые семьи похожи друг на друга, <marker>каждя</marker> несчастливая семья несчастлива по-своему.",
    )
    correct_examples = (
        "Все счастливые семьи похожи друг на друга, <marker>каждая</marker> несчастливая семья несчастлива по-своему.",
    )


class MorfologikRussianYOSpellerRule(_SpellerRuleBase):
    rule_id = "MORFOLOGIK_RULE_RU_RU_YO"
    description = "Проверка орфографии. Только «Ё» (экспериментальное правило)."
    speller_class = RussianYoSpeller
    default_off = True
    # Russian.java configures MORFOLOGIC_RULE_RU_RU_YO (a typo) -> orphan key.
    priority = 0
    # pinned upstream examples: org/languagetool/rules/ru/MorfologikRussianYOSpellerRule.java
    incorrect_examples = (
        "Все счастливые семьи похожи друг на друга, <marker>каждя</marker> несчастливая семья несчастлива по-своему.",
    )
    correct_examples = (
        "Все счастливые семьи похожи друг на друга, <marker>каждая</marker> несчастливая семья несчастлива по-своему.",
    )


@dataclass(frozen=True)
class _CompoundRuleData:
    incorrect_compounds: frozenset[str]
    joined_suggestion: frozenset[str]
    joined_lower_case_suggestion: frozenset[str]
    dash_suggestion: frozenset[str]
    has_digit_patterns: bool


_COMPOUND_MAX_TERMS = 5
_COMPOUND_COMMENT = re.compile(r"#.*$")
_COMPOUND_DASHES = re.compile(r"--+")
_COMPOUND_WHITESPACE = re.compile(r"\s+")


def _load_compound_rule_data(name: str) -> _CompoundRuleData:
    """Port of ``org.languagetool.rules.CompoundRuleData`` (no ``LineExpander``)."""
    incorrect: set[str] = set()
    joined: set[str] = set()
    joined_lower: set[str] = set()
    dash: set[str] = set()
    has_digits = False
    for raw_line in _resource_lines(name):
        if raw_line == "" or raw_line.startswith("#"):
            continue
        line = _COMPOUND_COMMENT.sub("", raw_line, count=1).strip()
        exp_line = line.replace("-", " ")
        parts = exp_line.split(" ")
        if len(parts) == 1:
            raise ValueError(f"Not a compound in file {name}: {exp_line}")
        if len(parts) > _COMPOUND_MAX_TERMS:
            raise ValueError(f"Too many compound parts in file {name}: {exp_line}")
        if exp_line.lower() in incorrect:
            raise ValueError(f"Duplicated word in file {name}: {exp_line}")
        if exp_line.endswith("+"):
            exp_line = exp_line[:-1]
            joined.add(exp_line)
        elif exp_line.endswith("*"):
            exp_line = exp_line[:-1]
            dash.add(exp_line)
        elif exp_line.endswith("?"):
            exp_line = exp_line[:-1]
            joined.add(exp_line)
            joined_lower.add(exp_line)
        elif exp_line.endswith("$"):
            exp_line = exp_line[:-1]
            joined.add(exp_line)
            dash.add(exp_line)
            joined_lower.add(exp_line)
        else:
            joined.add(exp_line)
            dash.add(exp_line)
        incorrect.add(exp_line)
        if "\\d" in exp_line:
            has_digits = True
    return _CompoundRuleData(
        incorrect_compounds=frozenset(incorrect),
        joined_suggestion=frozenset(joined),
        joined_lower_case_suggestion=frozenset(joined_lower),
        dash_suggestion=frozenset(dash),
        has_digit_patterns=has_digits,
    )


class _SyntheticToken:
    """The empty padding token ``AbstractCompoundRule`` appends past the sentence end."""

    __slots__ = ("start_pos",)

    def __init__(self, start_pos: int) -> None:
        self.start_pos = start_pos

    @property
    def token(self) -> str:
        return ""

    @property
    def is_immunized(self) -> bool:
        return False

    @property
    def is_whitespace_before(self) -> bool:
        return False

    @property
    def is_sentence_start(self) -> bool:
        return False


class RussianCompoundRule(NativeRule):
    rule_id = "RU_COMPOUNDS"
    category_id = "MISC"
    category_name = "Общие правила"
    description = "Правописание через дефис"
    priority = 11

    WITH_HYPHEN_MESSAGE = "Эти слова должны быть написаны через дефис."
    WITHOUT_HYPHEN_MESSAGE = "Эти слова должны быть написаны слитно."
    WITH_OR_WITHOUT_HYPHEN_MESSAGE = "Эти слова могут быть написаны через дефис или слитно."
    # pinned upstream examples: org/languagetool/rules/ru/RussianCompoundRule.java
    incorrect_examples = (
        "Собрание состоится в <marker>конференц зале</marker>.",
    )
    correct_examples = (
        "Собрание состоится в <marker>конференц-зале</marker>.",
    )

    _data: _CompoundRuleData | None = None

    @classmethod
    def data(cls) -> _CompoundRuleData:
        if cls._data is None:
            cls._data = _load_compound_rule_data("compounds.txt")
        return cls._data

    @staticmethod
    def _normalize(text: str) -> str:
        value = text.strip()
        value = value.replace(" - ", " ")
        value = value.replace("-", " ")
        return _COMPOUND_WHITESPACE.sub(" ", value)

    @staticmethod
    def _is_not_all_uppercase(text: str) -> bool:
        for part in text.split(" "):
            if part != "-" and is_all_uppercase(part):
                return False
        return True

    @staticmethod
    def _merge_compound(text: str, uncapitalize_mid_words: bool) -> str:
        parts = text.replace("-", " ").split(" ")
        out = []
        for index, part in enumerate(parts):
            if index == 0:
                out.append(part)
            else:
                out.append(_uncapitalize(part) if uncapitalize_mid_words else part)
        return "".join(out)

    def _string_to_token_map(
        self, prev_tokens: Sequence[Any]
    ) -> tuple[list[str], list[str], dict[str, Any]]:
        strings_to_check: list[str] = []
        orig_strings_to_check: list[str] = []
        string_to_token: dict[str, Any] = {}
        builder = ""
        is_first_sent_start = False
        for j, atr in enumerate(prev_tokens):
            if atr.is_whitespace_before:
                builder += " "
            builder += atr.token
            if j == 0:
                is_first_sent_start = atr.is_sentence_start
            if j >= 1 or (j == 0 and not is_first_sent_start):
                string_to_check = self._normalize(builder)
                # RussianCompoundRule sets sentenceStartsWithUpperCase = true
                if is_first_sent_start:
                    string_to_check = _uncapitalize(string_to_check)
                strings_to_check.append(string_to_check)
                orig_strings_to_check.append(builder.strip())
                if string_to_check not in string_to_token:
                    string_to_token[string_to_check] = atr
        return strings_to_check, orig_strings_to_check, string_to_token

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        data = self.data()
        out: list[NativeRuleFinding] = []
        for unit in context.sentences:
            offsets = _SentenceOffsets(unit)
            tokens = _sentence_tokens(unit)
            prev_rule_match: tuple[int, int] | None = None
            prev_tokens: deque = deque()
            for i in range(len(tokens) + _COMPOUND_MAX_TERMS):
                if i >= len(tokens):
                    token: Any = _SyntheticToken(prev_tokens[0].start_pos)
                else:
                    token = tokens[i]
                if i == 0:
                    if len(prev_tokens) == _COMPOUND_MAX_TERMS:
                        prev_tokens.popleft()
                    prev_tokens.append(token)
                    continue
                if token.is_immunized:
                    continue

                first_match_token = prev_tokens[0]
                strings, orig_strings, string_to_token = self._string_to_token_map(prev_tokens)
                for k in range(len(strings) - 1, -1, -1):
                    string_to_check = strings[k]
                    orig_string_to_check = orig_strings[k]
                    if string_to_check not in data.incorrect_compounds:
                        continue
                    atr = string_to_token[string_to_check]
                    message = None
                    replacement: list[str] = []
                    if string_to_check in data.dash_suggestion and " " not in orig_string_to_check:
                        break  # already joined
                    if string_to_check in data.dash_suggestion:
                        replacement.append(orig_string_to_check.replace(" ", "-"))
                        message = self.WITH_HYPHEN_MESSAGE
                    if (
                        self._is_not_all_uppercase(orig_string_to_check)
                        and string_to_check in data.joined_suggestion
                    ):
                        replacement.append(
                            self._merge_compound(
                                orig_string_to_check,
                                any(s in string_to_check for s in data.joined_lower_case_suggestion),
                            )
                        )
                        message = self.WITHOUT_HYPHEN_MESSAGE
                    parts = string_to_check.split(" ")
                    if parts and len(parts[0]) == 1:
                        replacement = [orig_string_to_check.replace(" ", "-")]
                        message = self.WITH_HYPHEN_MESSAGE
                    elif not replacement or len(replacement) == 2:
                        message = self.WITH_OR_WITHOUT_HYPHEN_MESSAGE
                    original = unit.text[
                        offsets.local(first_match_token.start_pos):offsets.local(_end_pos(atr))
                    ]
                    replacement = [
                        _COMPOUND_DASHES.sub("-", item)
                        for item in replacement
                        if _COMPOUND_DASHES.sub("-", item) != original
                    ]
                    if not replacement:
                        break
                    start_pos = first_match_token.start_pos
                    end_pos = _end_pos(atr)
                    if prev_rule_match is not None and prev_rule_match[0] == start_pos:
                        prev_rule_match = (start_pos, end_pos)
                        break
                    prev_rule_match = (start_pos, end_pos)
                    out.append(
                        self.finding(
                            context,
                            offsets.absolute(start_pos),
                            offsets.absolute(end_pos),
                            message or "",
                            tuple(replacement),
                        )
                    )
                    break
                if len(prev_tokens) == _COMPOUND_MAX_TERMS:
                    prev_tokens.popleft()
                prev_tokens.append(token)
        return out


@dataclass(frozen=True)
class _SuggestionWithMessage:
    suggestion: str
    message: str | None


_MAX_TOKENS_IN_MULTIWORD = 20


class RussianSimpleReplaceRule(NativeRule):
    rule_id = "RU_SIMPLE_REPLACE"
    category_id = "MISC"
    category_name = "Общие правила"
    description = "Поиск просторечий и ошибочных фраз"
    short = "Ошибка?"
    message_template = "«$match» — просторечие, исправление: $suggestions"
    suggestions_separator = ", "
    # Russian.java configures RUSSIAN_SIMPLE_REPLACE_RULE, not RU_SIMPLE_REPLACE.
    priority = 0
    # pinned upstream examples: org/languagetool/rules/ru/RussianSimpleReplaceRule.java
    incorrect_examples = (
        "<marker>Экспрессо</marker> – крепкий кофе, приготовленный из хорошо обжаренных и тонко помолотых кофейных зёрен.",
    )
    correct_examples = (
        "<marker>Эспрессо</marker> – крепкий кофе, приготовленный из хорошо обжаренных и тонко помолотых кофейных зёрен.",
    )

    _maps: tuple[dict[str, int], dict[str, int], dict[str, _SuggestionWithMessage], dict[str, _SuggestionWithMessage]] | None = None

    @classmethod
    def maps(cls):
        if cls._maps is None:
            cls._maps = _load_simple_replace("replace.txt")
        return cls._maps

    @staticmethod
    def _is_punctuation_start(word: str) -> bool:
        """``AbstractSimpleReplaceRule2.isPunctuationStart``."""
        if any(ch.isdigit() and unicodedata.category(ch) == "Nd" for ch in word):
            return True
        if is_punctuation_mark(word):
            return True
        # StringTools.isNotWordCharacter: a single non-letter character
        return len(word) == 1 and unicodedata.category(word)[0] != "L"

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        m_start_space, m_start_no_space, m_full_space, m_full_no_space = self.maps()
        out: list[NativeRuleFinding] = []
        for unit in context.sentences:
            offsets = _SentenceOffsets(unit)
            tokens = _sentence_tokens(unit)
            matches: list[tuple[int, int, str, tuple[str, ...]]] = []
            sent_start = 1
            while sent_start < len(tokens) and self._is_punctuation_start(tokens[sent_start].token):
                sent_start += 1
            for start_index in range(sent_start, len(tokens)):
                tok = tokens[start_index].token
                if len(tok) < 1:
                    continue
                k = start_index + 1
                while k < len(tokens) and not tokens[k].is_whitespace_before:
                    tok += tokens[k].token
                    k += 1
                tok = tok.lower()
                if tok in m_start_space:
                    key_builder = ""
                    max_token_len = m_start_space[tok]
                    end_index = start_index
                    while (
                        end_index < len(tokens)
                        and end_index - start_index < _MAX_TOKENS_IN_MULTIWORD
                    ):
                        if end_index > start_index and tokens[end_index].is_whitespace_before:
                            key_builder += " "
                        key_builder += tokens[end_index].token
                        original_str = key_builder
                        number_of_spaces = original_str.count(" ")
                        if number_of_spaces + 1 > max_token_len:
                            break
                        if number_of_spaces > 0:
                            entry = m_full_space.get(original_str.lower())
                            self._create_match(
                                matches, entry, start_index, end_index, original_str, tokens, sent_start
                            )
                        end_index += 1
                if tok[:1] in m_start_no_space:
                    end_index = start_index
                    key_builder = ""
                    while (
                        end_index < len(tokens)
                        and end_index - start_index < _MAX_TOKENS_IN_MULTIWORD
                    ):
                        if end_index > start_index and tokens[end_index].is_whitespace_before:
                            break
                        key_builder += tokens[end_index].token
                        original_str = key_builder
                        entry = m_full_no_space.get(original_str.lower())
                        self._create_match(
                            matches, entry, start_index, end_index, original_str, tokens, sent_start
                        )
                        end_index += 1
            for from_pos, to_pos, message, suggestions in matches:
                out.append(
                    self.finding(
                        context,
                        offsets.absolute(from_pos),
                        offsets.absolute(to_pos),
                        message,
                        suggestions,
                        self.short,
                    )
                )
        return out

    def _create_match(
        self,
        matches: list[tuple[int, int, str, tuple[str, ...]]],
        entry: _SuggestionWithMessage | None,
        start_index: int,
        end_index: int,
        original_str: str,
        tokens: Sequence[AnalyzedTokenReadings],
        sent_start: int,
    ) -> None:
        if entry is None:
            return
        replacements = entry.suggestion.split("|")
        from_pos = tokens[start_index].start_pos
        to_pos = _end_pos(tokens[end_index])
        if matches:
            last = matches[-1]
            if last[0] <= from_pos and last[1] >= to_pos:
                return
        # StringTools.isCamelCase is ASCII-only and never matches Russian.
        all_uppercase = is_all_uppercase(original_str)
        capitalized = is_capitalized_word(original_str.split(" ")[0])
        final_replacements: list[str] = []
        for repl in replacements:
            final_repl = repl
            if sent_start == start_index or capitalized:
                final_repl = uppercase_first_char(repl)
            if all_uppercase:
                final_repl = repl.upper()
            if (
                repl != original_str
                and final_repl != original_str
                and final_repl not in final_replacements
            ):
                final_replacements.append(final_repl)
            if final_repl == original_str:
                final_replacements.clear()
                break
        if not final_replacements:
            return
        message = entry.message
        if message is not None and (
            message.startswith("http://") or message.startswith("https://")
        ):
            message = None
        if message is None:
            msg_suggestions = ""
            for index, repl in enumerate(replacements):
                if index > 0:
                    msg_suggestions += (
                        self.suggestions_separator if index == len(replacements) - 1 else ", "
                    )
                msg_suggestions += "<suggestion>" + repl + "</suggestion>"
            message = self.message_template.replace("$match", original_str, 1).replace(
                "$suggestions", msg_suggestions, 1
            )
        if matches:
            last = matches[-1]
            if last[0] >= from_pos and last[1] <= to_pos:
                matches.pop()
        matches.append((from_pos, to_pos, message, tuple(final_replacements)))


def _load_simple_replace(name: str):
    """Port of ``AbstractSimpleReplaceRule2.fillMaps`` for a case-insensitive rule."""
    m_start_space: dict[str, int] = {}
    m_start_no_space: dict[str, int] = {}
    m_full_space: dict[str, _SuggestionWithMessage] = {}
    m_full_no_space: dict[str, _SuggestionWithMessage] = {}
    path = files("pylat_ru.resources.rules.ru").joinpath(name)
    for raw_line in path.read_text(encoding="utf-8").split("\n"):
        line = raw_line.rstrip("\r").strip()
        if not line or line.startswith("#"):
            continue
        if "  " in line:
            raise ValueError(
                f"More than one consecutive space in {name} - use a tab character as "
                f"a delimiter for the message: {line}"
            )
        line = line.split("#", 1)[0].strip()
        parts = line.split("\t")
        conf_pair = parts[0]
        if len(parts) == 1:
            message = None
        elif len(parts) == 2:
            message = parts[1]
        else:
            raise ValueError(f"Format error in file {name}. Line: {line}")
        conf_pair_parts = conf_pair.split("=")
        if len(conf_pair_parts) < 2:
            raise ValueError(
                f"Format error in file {name}. Missing suggestion after character '='. Line: {line}"
            )
        suggestion = conf_pair_parts[1]
        for wrong_form in conf_pair_parts[0].split("|"):
            search_key = wrong_form.lower()
            if search_key == suggestion:
                raise ValueError(
                    f"Format error in file {name}. Found same word on left and right side "
                    f"of '='. Line: {line}"
                )
            entry = _SuggestionWithMessage(suggestion, message)
            if wrong_form.find(" ") <= 0:
                first_char = search_key[:1]
                if first_char in m_start_no_space:
                    if m_start_no_space[first_char] < len(search_key):
                        m_start_no_space[first_char] = len(search_key)
                else:
                    m_start_no_space[first_char] = len(search_key)
                m_full_no_space[search_key] = entry
            else:
                key_tokens = search_key.split(" ")
                first_token = key_tokens[0]
                if first_token in m_start_space:
                    if m_start_space[first_token] < len(key_tokens):
                        m_start_space[first_token] = len(key_tokens)
                else:
                    m_start_space[first_token] = len(key_tokens)
                m_full_space[search_key] = entry
    return m_start_space, m_start_no_space, m_full_space, m_full_no_space


_SIMPLE_REPEAT_PATTERN = re.compile("[a-zA-Zа-яёА-ЯЁ]")
_WORD_REPEAT_IGNORED_NAMES = (
    "Phi", "Li", "Xiao", "Duran", "Wagga", "Abdullah", "Nwe", "Pago", "Cao",
)


def _is_numeric_space(text: str) -> bool:
    """``org.apache.commons.lang3.StringUtils.isNumericSpace``."""
    for ch in text:
        if ch != " " and unicodedata.category(ch) != "Nd":
            return False
    return True


class RussianSimpleWordRepeatRule(NativeRule):
    rule_id = "WORD_REPEAT_RULE"
    category_id = "MISC"
    category_name = "Общие правила"
    description = "Повтор слов (например: «он он»)"
    message = "Возможная опечатка: повтор слова"
    short_message = "Повтор слова"

    @staticmethod
    def _is_word(token: str) -> bool:
        if is_emoji(token):
            return False
        if _is_numeric_space(token):
            return False
        if len(token) == 1 and unicodedata.category(token)[0] != "L":
            return False
        return True

    @staticmethod
    def _word_repetition_of(word: str, tokens: Sequence[AnalyzedTokenReadings], position: int) -> bool:
        return (
            position > 0
            and tokens[position - 1].token == word
            and tokens[position].token == word
        )

    def _ignore(self, tokens: Sequence[AnalyzedTokenReadings], position: int) -> bool:
        for word in ("-", "и", "по"):
            if self._word_repetition_of(word, tokens, position):
                return True
        if tokens[position - 1].token == "ПО" and tokens[position].token == "по":
            return True
        if tokens[position - 1].token == "по" and tokens[position].token == "ПО":
            return True
        if self._word_repetition_of("что", tokens, position):
            return True
        if (
            _SIMPLE_REPEAT_PATTERN.fullmatch(tokens[position].token)
            and position > 1
            and _SIMPLE_REPEAT_PATTERN.fullmatch(tokens[position - 1].token)
        ):
            return True
        for name in _WORD_REPEAT_IGNORED_NAMES:
            if self._word_repetition_of(name, tokens, position):
                return True
        return False

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out: list[NativeRuleFinding] = []
        for unit in context.sentences:
            offsets = _SentenceOffsets(unit)
            tokens = _sentence_tokens(unit)
            prev_token = ""
            for i in range(1, len(tokens)):
                token = tokens[i].token
                if tokens[i].is_immunized:
                    prev_token = ""
                    continue
                if (
                    self._is_word(token)
                    and prev_token.lower() == token.lower()
                    and prev_token != ""
                    and not self._ignore(tokens, i)
                ):
                    prev_pos = tokens[i - 1].start_pos
                    pos = tokens[i].start_pos
                    out.append(
                        self.finding(
                            context,
                            offsets.absolute(prev_pos),
                            offsets.absolute(pos + utf16_len(prev_token)),
                            self.message,
                            (prev_token,),
                            self.short_message,
                        )
                    )
                prev_token = token
        return out


def _load_word_coherency_data(name: str) -> dict[str, tuple[str, ...]]:
    """Port of ``org.languagetool.rules.WordCoherencyDataLoader``."""
    mapping: dict[str, list[str]] = {}
    path = files("pylat_ru.resources.rules.ru").joinpath(name)
    for raw_line in path.read_text(encoding="utf-8").split("\n"):
        line = raw_line.rstrip("\r")
        if not line or line[0] == "#":
            continue
        parts = line.split(";")
        if len(parts) != 2:
            raise ValueError(f"Format error in file {name}, line: {line}")
        for left, right in ((parts[0], parts[1]), (parts[1], parts[0])):
            bucket = mapping.setdefault(left, [])
            if right not in bucket:
                bucket.append(right)
    return {key: tuple(value) for key, value in mapping.items()}


class _WordCoherencyRuleBase(NativeRule):
    text_level = True
    """Port of ``org.languagetool.rules.AbstractWordCoherencyRule`` (a TextLevelRule)."""

    resource_name = ""
    _word_map: dict[str, tuple[str, ...]] | None = None

    @classmethod
    def word_map(cls) -> dict[str, tuple[str, ...]]:
        if cls._word_map is None:
            cls._word_map = _load_word_coherency_data(cls.resource_name)
        return cls._word_map

    def build_message(self, word1: str, word2: str) -> str:
        raise NotImplementedError

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        word_map = self.word_map()
        should_not_appear_word: dict[str, str] = {}
        out: list[NativeRuleFinding] = []
        for unit in context.sentences:
            offsets = _SentenceOffsets(unit)
            for tmp_token in _sentence_tokens(unit):
                token = tmp_token.token
                readings = tmp_token.get_readings()
                if not readings:
                    continue
                baseforms = java_hash_set_order([reading.lemma for reading in readings])
                for baseform in baseforms:
                    if baseform is not None:
                        token = baseform
                    from_pos = offsets.absolute(tmp_token.start_pos)
                    to_pos = offsets.absolute(_end_pos(tmp_token))
                    if token in should_not_appear_word:
                        other_spelling = should_not_appear_word[token]
                        message = self.build_message(token, other_spelling)
                        marked = unit.text[
                            offsets.local(tmp_token.start_pos):offsets.local(_end_pos(tmp_token))
                        ]
                        # Pinned createReplacement is
                        # ``marked.replaceFirst("(?i)" + token, otherSpelling)``, and
                        # Java's ``(?i)`` folds ASCII only without ``UNICODE_CASE``.
                        # A Cyrillic word whose surface differs from its lemma only by
                        # capitalisation is therefore left untouched, and the
                        # ``equalsIgnoreCase`` guard below then drops the match.
                        replacement = re.sub(
                            re.escape(token),
                            other_spelling,
                            marked,
                            count=1,
                            flags=re.IGNORECASE | re.ASCII,
                        )
                        if starts_with_uppercase(tmp_token.token):
                            replacement = uppercase_first_char(replacement)
                        if marked.lower() != replacement.lower():
                            out.append(
                                self.finding(context, from_pos, to_pos, message, (replacement,))
                            )
                        break
                    if token in word_map:
                        for should_not_appear in word_map[token]:
                            should_not_appear_word[should_not_appear] = token
        return out


class RussianWordCoherencyRule(_WordCoherencyRuleBase):
    rule_id = "RU_WORD_COHERENCY"
    category_id = "MISC"
    category_name = "Общие правила"
    description = (
        "Единообразное написание слов с более чем одним допустимым написанием"
    )
    resource_name = "coherency.txt"
    # pinned upstream examples: org/languagetool/rules/ru/RussianWordCoherencyRule.java
    incorrect_examples = (
        "Понятие «оффлайн» тоже имеет английские корни и связано со словом «offline», что означает «вне сети». Принтер перешёл в состояние <marker>офлайн</marker>.",
    )
    correct_examples = (
        "Понятие «оффлайн» тоже имеет английские корни и связано со словом «offline», что означает «вне сети». Принтер перешёл в состояние <marker>оффлайн</marker>.",
    )

    _word_map = None

    def build_message(self, word1: str, word2: str) -> str:
        return f"«{word1}» и «{word2}» не следует использовать одновременно"


class RussianWordRootRepeatRule(_WordCoherencyRuleBase):
    rule_id = "RU_WORD_ROOT_REPEAT"
    category_id = "MISC"
    category_name = "Общие правила"
    description = "Повтор однокоренных слов"
    resource_name = "wordrootrep.txt"
    default_off = True
    # Russian.java configures Word_root_repeat = -1, which never binds RU_WORD_ROOT_REPEAT.
    priority = 0
    # pinned upstream examples: org/languagetool/rules/ru/RussianWordRootRepeatRule.java
    incorrect_examples = (
        "Абрикос рос в саду. У меня на столе стоит <marker>абрикосный</marker> сок.",
    )
    correct_examples = (
        "Абрикос рос в саду. У меня на столе стоит сок из <marker>абрикосов</marker>.",
    )

    _word_map = None

    def build_message(self, word1: str, word2: str) -> str:
        return (
            f"«{word1}» и «{word2}» – однокоренные слова, "
            "их не стоит использовать одновременно"
        )


_ADVANCED_REPEAT_EXC_WORDS = frozenset({
    "не", "ни", "а", "их", "на", "в", "по", "минута", "друг", "час", "секунда",
    "ПАО", "ООО", "табл", "рис",
})
_ADVANCED_REPEAT_EXC_POS = re.compile(
    r"INTERJECTION|PRDC|PREP|CONJ|PARTICLE|ABR|NumC:.*|Num:.*"
)
_ADVANCED_REPEAT_EXC_NONWORDS = re.compile(
    r"&quot|&gt|&lt|&amp|[0-9].*|"
    r"M*(D?C{0,3}|C[DM])(L?X{0,3}|X[LC])(V?I{0,3}|I[VX])$"
)
_SENTENCE_END_TAGNAME = "SENT_END"


class RussianWordRepeatRule(NativeRule):
    """Port of ``RussianWordRepeatRule`` on ``AdvancedWordRepeatRule``."""

    rule_id = "RU_WORD_REPEAT"
    category_id = "MISC"
    category_name = "Общие правила"
    description = "Повтор слов в предложении"
    message = "Повтор слов в предложении"
    short_message = "Повтор слов в предложении"
    default_off = True
    # pinned upstream examples: org/languagetool/rules/ru/RussianWordRepeatRule.java
    incorrect_examples = (
        "Всё смешалось в <marker>доме доме</marker> Облонских.",
    )
    correct_examples = (
        "Всё смешалось в <marker>доме</marker> Облонских.",
    )

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out: list[NativeRuleFinding] = []
        for unit in context.sentences:
            offsets = _SentenceOffsets(unit)
            tokens = _sentence_tokens(unit)
            repetition = False
            inflected_words: set[str] = set()
            cur_token = 0
            for i in range(1, len(tokens)):
                token = tokens[i].token
                is_word = True
                has_lemma = True
                if len(token) < 2:
                    is_word = False
                for analyzed_token in tokens[i].get_readings():
                    pos_tag = analyzed_token.pos_tag
                    if pos_tag is not None:
                        if pos_tag == "":
                            is_word = False
                            break
                        lemma = analyzed_token.lemma
                        if lemma is None:
                            has_lemma = False
                            break
                        if lemma in _ADVANCED_REPEAT_EXC_WORDS:
                            is_word = False
                            break
                        if _ADVANCED_REPEAT_EXC_POS.fullmatch(pos_tag):
                            is_word = False
                            break
                    else:
                        has_lemma = False
                if is_word and _ADVANCED_REPEAT_EXC_NONWORDS.fullmatch(tokens[i].token):
                    is_word = False

                prev_lemma = ""
                if is_word:
                    not_sent_end = False
                    for analyzed_token in tokens[i].get_readings():
                        pos = analyzed_token.pos_tag
                        if pos is not None:
                            not_sent_end = not_sent_end or (_SENTENCE_END_TAGNAME == pos)
                        if has_lemma:
                            cur_lemma = analyzed_token.lemma
                            if prev_lemma != cur_lemma and not not_sent_end:
                                if cur_lemma in inflected_words and cur_token != i:
                                    repetition = True
                                else:
                                    inflected_words.add(analyzed_token.lemma)
                                    cur_token = i
                            prev_lemma = cur_lemma
                        else:
                            if tokens[i].token in inflected_words and not not_sent_end:
                                repetition = True
                            else:
                                inflected_words.add(tokens[i].token)
                if repetition:
                    pos = tokens[i].start_pos
                    out.append(
                        self.finding(
                            context,
                            offsets.absolute(pos),
                            offsets.absolute(pos + utf16_len(token)),
                            self.message,
                            (),
                            self.short_message,
                        )
                    )
                    repetition = False
        return out


TASK_0011_RULE_CLASSES = (
    CommaWhitespaceRule,
    UppercaseSentenceStartRule,
    MultipleWhitespaceRule,
    SentenceWhitespaceRule,
    WhiteSpaceBeforeParagraphEnd,
    WhiteSpaceAtBeginOfParagraph,
    LongSentenceRule,
    LongParagraphRule,
    ParagraphRepeatBeginningRule,
    RussianFillerWordsRule,
    PunctuationMarkAtParagraphEnd2,
    RussianUnpairedBracketsRule,
    RussianVerbConjugationRule,
    RussianDashRule,
    RussianSpecificCaseRule,
)

TASK_0012_RULE_CLASSES = (
    MorfologikRussianSpellerRule,
    MorfologikRussianYOSpellerRule,
    RussianCompoundRule,
    RussianSimpleReplaceRule,
    RussianSimpleWordRepeatRule,
    RussianWordCoherencyRule,
    RussianWordRepeatRule,
    RussianWordRootRepeatRule,
)

# Exact registration order of Russian.getRelevantRules() at the pinned revision.
RUSSIAN_RULE_CLASSES = (
    CommaWhitespaceRule,
    UppercaseSentenceStartRule,
    MorfologikRussianSpellerRule,
    MultipleWhitespaceRule,
    SentenceWhitespaceRule,
    WhiteSpaceBeforeParagraphEnd,
    WhiteSpaceAtBeginOfParagraph,
    LongSentenceRule,
    LongParagraphRule,
    ParagraphRepeatBeginningRule,
    RussianFillerWordsRule,
    PunctuationMarkAtParagraphEnd2,
    MorfologikRussianYOSpellerRule,
    RussianUnpairedBracketsRule,
    RussianCompoundRule,
    RussianSimpleReplaceRule,
    RussianSimpleWordRepeatRule,
    RussianWordCoherencyRule,
    RussianWordRepeatRule,
    RussianWordRootRepeatRule,
    RussianVerbConjugationRule,
    RussianDashRule,
    RussianSpecificCaseRule,
)


class RussianJavaRulesEngine:
    """Execute the exact Task-0011 native-rule registration for Russian."""

    def __init__(self, rule_config: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        config = dict(rule_config or {})
        known = {cls.rule_id for cls in RUSSIAN_RULE_CLASSES}
        unknown = set(config) - known
        if unknown:
            raise KeyError(f"Unknown Russian rule configuration: {sorted(unknown)}")
        self.rules = tuple(cls(i, config.get(cls.rule_id)) for i, cls in enumerate(RUSSIAN_RULE_CLASSES))
        self._rules = {rule.rule_id: rule for rule in self.rules}
        self._enabled_overrides: set[str] = set()
        self._disabled_overrides: set[str] = set()
        self._sentence_tokenizer = RussianSentenceTokenizer()
        self._word_tokenizer = RussianWordTokenizer()
        self._disambiguator = RussianHybridDisambiguator.get_instance()
        self._chunker = RussianChunker()

    def get_rule(self, rule_id: str) -> NativeRule | None:
        return self._rules.get(rule_id)

    def enable_rule(self, rule_id: str) -> None:
        if rule_id not in self._rules:
            raise KeyError(rule_id)
        self._enabled_overrides.add(rule_id)
        self._disabled_overrides.discard(rule_id)

    def disable_rule(self, rule_id: str) -> None:
        if rule_id not in self._rules:
            raise KeyError(rule_id)
        self._disabled_overrides.add(rule_id)
        self._enabled_overrides.discard(rule_id)

    def is_rule_enabled(self, rule_id: str) -> bool:
        rule = self._rules[rule_id]
        if rule_id in self._enabled_overrides:
            return True
        if rule_id in self._disabled_overrides:
            return False
        return not rule.default_off

    def analyze(self, text: str) -> NativeRuleContext:
        mapper = Utf16CodePointMapper(text)
        units = []
        for span in self._sentence_tokenizer.tokenize_spans(text):
            analyzed = self._disambiguator.disambiguate_text(span.text)
            analyzed.text = span.text
            self._chunker.chunk(analyzed)
            units.append(SentenceUnit(span.text, span.start, span.end, analyzed))
        # Upstream tokenises every AnalyzedSentence from its own text, so the
        # word tokenizer never sees the sentence boundary.  Tokenising the whole
        # text at once would merge tokens across that boundary (for example
        # ". Los" at the end of one sentence and the start of the next).
        per_sentence: list[tuple[TokenSpan, ...]] = []
        for unit in units:
            per_sentence.append(
                tokens_to_spans(
                    self._word_tokenizer.tokenize(unit.text),
                    base_offset=unit.start,
                    mapper=mapper,
                )
            )
        token_spans = tuple(span for spans in per_sentence for span in spans)
        return NativeRuleContext(text, tuple(units), mapper, token_spans, tuple(per_sentence))

    def check_context(self, context: NativeRuleContext, include_disabled: bool = False) -> list[NativeRuleFinding]:
        """Run the enabled rules, text-level ones first.

        ``JLanguageTool`` executes ``TextLevelRule`` instances over the whole text and
        ``Rule`` instances per sentence, and the text-level matches reach the filter
        chain first.  ``SameRuleGroupFilter`` sorts stably by start position, so for two
        matches on the same span that order is what ``CleanOverlappingFilter`` breaks
        the tie with.
        """
        findings = []
        for text_level in (True, False):
            for rule in self.rules:
                if rule.text_level is not text_level:
                    continue
                if not include_disabled and not self.is_rule_enabled(rule.rule_id):
                    continue
                findings.extend(rule.match(context))
        return findings

    def check(self, text: str, include_disabled: bool = False) -> list[NativeRuleFinding]:
        if not text:
            return []
        findings = self.check_context(self.analyze(text), include_disabled=include_disabled)
        return sorted(findings, key=lambda f: (f.from_pos, -f.priority, f.registration_order, f.to_pos))

    def check_rule(self, text: str, rule_id: str) -> list[NativeRuleFinding]:
        rule = self._rules.get(rule_id)
        if rule is None:
            raise KeyError(rule_id)
        context = self.analyze(text)
        return rule.match(context)
