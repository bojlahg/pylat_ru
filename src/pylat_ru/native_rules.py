"""Python-native equivalents of the Java rules registered by Russian LT 6.8.

This module intentionally models only the Task-0011 registration surface.  It
does not contain spelling, compound-spelling, replacement, coherency, or word
repetition substitutes (those remain the explicit Task-0012 boundary).
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence

from pylat_ru.analysis import AnalyzedSentence, AnalyzedTokenReadings
from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.tokenization.offsets import TokenSpan, Utf16CodePointMapper, tokens_to_spans
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
    source: str = "java_rule_0011"


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


def _resource_lines(name: str) -> tuple[str, ...]:
    path = files("pylat_ru.resources.ru").joinpath(name)
    return tuple(path.read_text(encoding="utf-8").splitlines())


def _is_word(token: str) -> bool:
    return bool(token) and unicodedata.category(token[0])[0] in {"L", "N"}


def _is_non_word(token: str) -> bool:
    return bool(token) and not any(unicodedata.category(ch)[0] in {"L", "N"} for ch in token)


class NativeRule:
    rule_id = ""
    category_id = ""
    category_name = ""
    description = ""
    default_off = False
    priority = 0
    tags: tuple[str, ...] = ()

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

    @staticmethod
    def _ws(token: str) -> bool:
        return token != "\u200b" and (token.isspace() or token == "\u00a0")

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        tokens = context.token_spans
        out: list[NativeRuleFinding] = []
        if tokens and tokens[0].text == ",":
            out.append(self.finding(context, tokens[0].start, tokens[0].end, "Поставьте пробел после запятой, а не перед ней.", (", ",)))
        for i, cur in enumerate(tokens):
            if i == 0:
                continue
            prev = tokens[i - 1]
            prev2 = tokens[i - 2] if i >= 2 else None
            token, ptoken = cur.text, prev.text
            pp = prev2.text if prev2 else ""
            msg = None
            repl = None
            start = prev.start
            suggestions: tuple[str, ...] = ()
            if self._ws(token) and ptoken == "(":
                msg, repl = "Не ставьте пробел после открывающейся скобки.", "("
            elif self._ws(token) and ptoken in "'\"’”“«»" and pp == " ":
                msg = "Не ставьте пробел у символа кавычек."
                start = prev2.start if prev2 else prev.start
                suggestions = (ptoken + " ", " " + ptoken)
            elif not self._ws(token) and ptoken == "," and token not in "'\"’”“«»- ," and not any(c.isdigit() for c in pp + token) and pp != ",":
                msg, repl = "Поставьте пробел после запятой.", ", " + token
            elif self._ws(ptoken):
                if token == ")":
                    msg, repl = "Не ставьте пробел до закрывающейся скобки.", ")"
                elif token == "," and not (i + 1 < len(tokens) and tokens[i + 1].text == ","):
                    msg = "Поставьте пробел после запятой, а не перед ней."
                    repl = ", " if i + 1 < len(tokens) and not self._ws(tokens[i + 1].text) else ","
                elif token == ".":
                    if pp == ".":
                        continue
                    nxt = tokens[i + 1].text if i + 1 < len(tokens) else ""
                    nxt2 = tokens[i + 2].text if i + 2 < len(tokens) else ""
                    domain = bool(re.fullmatch(r"(?i)(com|org|net|int|edu|gov|mil|[a-z]{2})", nxt))
                    ext = bool(re.fullmatch(r"(?i)([a-z]{3,4}|ai|mp[34])(-.+)?", nxt))
                    if not domain and not ext and not (nxt and (nxt[0].isdigit() or nxt[0] == ".")) and not (nxt == "/" and re.fullmatch(r"[a-zA-Z]+", nxt2)):
                        msg, repl = "Не ставьте пробел перед точкой в конце предложения.", "."
            if msg:
                if not suggestions:
                    suggestions = (repl or "",)
                out.append(self.finding(context, start, cur.end, msg, suggestions))
        return out


class UppercaseSentenceStartRule(NativeRule):
    rule_id = "UPPERCASE_SENTENCE_START"
    category_id = "CASING"
    category_name = "Заглавные буквы"
    description = "Предложение должно начинаться с заглавной буквы"
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
                if replacement != token and not re.fullmatch(r"[a-z][A-Z].*", token):
                    out.append(self.finding(context, candidate.start, candidate.end, "Это предложение не начинается с заглавной буквы.", (replacement,), "Заглавные буквы"))
            previous_last = last
        return out


class MultipleWhitespaceRule(NativeRule):
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
        t = context.token_spans
        i = 0
        while i < len(t):
            if self._first(t[i].text):
                first = i
                i += 1
                while i < len(t) and self._removable(t[i].text):
                    i += 1
                if i - 1 > first:
                    out.append(self.finding(context, t[first].start, t[i - 1].end, "Повтор пробела", (t[first].text,)))
                continue
            if t[i].text in {"\n", "\r", "\r\n"}:
                i += 1
                while i < len(t) and self._removable(t[i].text):
                    i += 1
                continue
            i += 1
        return out


class SentenceWhitespaceRule(NativeRule):
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


def _paragraph_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start = 0
    for m in re.finditer(r"(?:\r?\n){2,}", text):
        ranges.append((start, m.start()))
        start = m.end()
    ranges.append((start, len(text)))
    return ranges


class WhiteSpaceBeforeParagraphEnd(NativeRule):
    rule_id = "WHITESPACE_PARAGRAPH"
    category_id = "STYLE"
    category_name = "Стиль"
    description = "Пробел в конце абзаца"
    default_off = True
    priority = -50

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out = []
        for start, end in _paragraph_ranges(context.text):
            m = re.search(r"[^\S\r\n]+$", context.text[start:end])
            if m:
                # The pinned token loop reports only the final removable token
                # immediately before the paragraph line-break sequence.
                b = start + m.end()
                a = b - 1
                out.append(self.finding(context, a, b, "Удалите пробел в конце абзаца"))
        return out


class WhiteSpaceAtBeginOfParagraph(NativeRule):
    rule_id = "WHITESPACE_PARAGRAPH_BEGIN"
    category_id = "STYLE"
    category_name = "Стиль"
    description = "Пробел в начале абзаца"
    default_off = True
    priority = -50

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out = []
        for start, end in _paragraph_ranges(context.text):
            m = re.match(r"[^\S\r\n]+", context.text[start:end])
            if not m:
                continue
            rest_start = start + m.end()
            spans = tokens_to_spans(RussianWordTokenizer().tokenize(context.text[rest_start:end]), base_offset=rest_start, mapper=context.mapper)
            first = next((span for span in spans if not span.text.isspace()), None)
            if first:
                out.append(self.finding(context, start, first.end, "Удалите пробел в начале абзаца", (first.text,)))
        return out


class LongSentenceRule(NativeRule):
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
                elif quote == -1 and _is_word(token):
                    if first is None:
                        first = span
                    if count == self.max_words:
                        last = next((s for s in reversed(spans) if _is_word(s.text)), span)
                        idx = spans.index(last)
                        if idx + 1 < len(spans) and spans[idx + 1].text in ".?!":
                            last = spans[idx + 1]
                        out.append(self.finding(context, first.start, last.end, f"Предложение длиной {self.max_words} слов от позиции маркера необходимо проверить. Более короткие предложения лучше воспринимаются читателями."))
                        break
                    count += 1
        return out


class LongParagraphRule(NativeRule):
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


class ParagraphRepeatBeginningRule(NativeRule):
    rule_id = "PARAGRAPH_REPEAT_BEGINNING_RULE"
    category_id = "STYLE"
    category_name = "Стиль"
    description = "Повтор начала абзаца"
    default_off = True
    priority = -50
    _quotes = re.compile(r"[’'\"„“”»«‚‘›‹()\[\]]")

    def _first(self, context: NativeRuleContext, start: int, end: int) -> TokenSpan | None:
        spans = tokens_to_spans(RussianWordTokenizer().tokenize(context.text[start:end]), base_offset=start, mapper=context.mapper)
        visible = [s for s in spans if not s.text.isspace()]
        if not visible:
            return None
        idx = 1 if self._quotes.fullmatch(visible[0].text) and len(visible) > 1 else 0
        return visible[idx] if visible[idx].text and visible[idx].text[0].isalpha() else None

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out = []
        ranges = _paragraph_ranges(context.text)
        for left, right in zip(ranges, ranges[1:]):
            a, b = self._first(context, *left), self._first(context, *right)
            if a and b and a.text == b.text:
                msg = "Повтор начала последнего абзаца"
                # Pinned ParagraphRepeatBeginningRule reuses the prior
                # sentence-local end offset for the next paragraph, exposing
                # this one-codepoint-short second span after the line break.
                out.extend((self.finding(context, a.start, a.end, msg), self.finding(context, b.start, max(b.start, b.end - 1), msg)))
        return out


class RussianFillerWordsRule(NativeRule):
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
    rule_id = "PUNCTUATION_PARAGRAPH_END2"
    category_id = "PUNCTUATION"
    category_name = "Пунктуация"
    description = "В конце абзаца отсутствует знак пунктуации"
    default_off = True
    # Russian.java contains an orphan priority key PUNCT_DPT_2; it does not
    # match this pinned rule ID, so the effective priority is the base value.

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        out = []
        for start, end in _paragraph_ranges(context.text):
            spans = [s for s in tokens_to_spans(RussianWordTokenizer().tokenize(context.text[start:end]), base_offset=start, mapper=context.mapper) if not s.text.isspace()]
            words = [s for s in spans if not _is_non_word(s.text)]
            if len(words) > 10 and spans:
                last = spans[-1]
                if last.text not in {":", ".", "?", "!", "…"} and not _is_non_word(last.text):
                    out.append(self.finding(context, last.start, last.end, "Добавьте знак пунктуации в конце абзаца.", (last.text + ".",)))
        return out


class RussianUnpairedBracketsRule(NativeRule):
    rule_id = "RU_UNPAIRED_BRACKETS"
    category_id = "PUNCTUATION"
    category_name = "Пунктуация"
    description = "Непарные скобки или апострофы"
    starts = ("(", "{", "„", "\"", "'", "“")
    ends = (")", "}", "“", "\"", "'", "”")

    def match(self, context: NativeRuleContext) -> list[NativeRuleFinding]:
        stack: list[tuple[str, TokenSpan, bool]] = []
        symmetric = {'\"', "'"}
        visible = [s for s in context.token_spans if not s.text.isspace()]
        for idx, span in enumerate(visible):
            token = span.text
            if token not in self.starts and token not in self.ends:
                continue
            prev = visible[idx - 1] if idx else None
            prev2 = visible[idx - 2] if idx >= 2 else None
            nxt = visible[idx + 1] if idx + 1 < len(visible) else None
            if token in "()" and prev and (
                (prev.text in {":", ";"} and prev.end == span.start)
                or (prev2 and prev2.text in {":", ";"} and prev.text == "-" and prev2.end == prev.start)
            ):
                continue
            if token in symmetric:
                preceded = idx == 0 or (prev is not None and prev.end < span.start) or (prev is not None and ((_is_non_word(prev.text) and prev.text != ".") or prev.text in self.starts))
                followed = nxt is None or span.end < nxt.start or (nxt is not None and (_is_non_word(nxt.text) or nxt.text in self.ends or nxt.text.startswith("-") or nxt.text == "s"))
                if stack and stack[-1][0] == token and followed:
                    stack.pop()
                elif preceded:
                    stack.append((token, span, True))
                continue
            if token in self.starts:
                stack.append((token, span, True))
                continue
            j = self.ends.index(token)
            expected = self.starts[j]
            prev_text = prev.text if prev else ""
            if token == ")" and re.fullmatch(r"(?i)(\d{1,2}[а-яa-z']*|[а-яa-z]{1,2}|[ivxlcdm]+)\.?", prev_text):
                continue
            if stack and stack[-1][0] == expected:
                stack.pop()
            else:
                stack.append((token, span, False))
        out = []
        for symbol, span, opening in stack:
            if opening:
                sentence_index = next((index for index, unit in enumerate(context.sentences) if unit.start <= span.start < unit.end), len(context.sentences) - 1)
                sentence_text = context.sentences[sentence_index].text.rstrip() if context.sentences else ""
                if sentence_index == len(context.sentences) - 1 and not sentence_text.endswith((".", "?", "!")):
                    continue
            other = self.ends[self.starts.index(symbol)] if opening else self.starts[self.ends.index(symbol)]
            out.append(self.finding(context, span.start, span.end, f"Непарный символ: «{other}» скорей всего пропущен"))
        return out


class RussianVerbConjugationRule(NativeRule):
    rule_id = "RU_VERB_CONJUGATION"
    category_id = "GRAMMAR"
    category_name = "Грамматика"
    description = "Согласование личных местоимений с глаголами"
    pronoun = re.compile(r"PNN:(.*):Nom:(.*)")
    future = re.compile(r"VB:(Fut|Real):(.*):(.*):(.*):(.*)")
    past = re.compile(r"VB:Past:(.*):(.*):(.*)")

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


class RussianJavaRulesEngine:
    """Execute the exact Task-0011 native-rule registration for Russian."""

    def __init__(self, rule_config: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        config = dict(rule_config or {})
        known = {cls.rule_id for cls in TASK_0011_RULE_CLASSES}
        unknown = set(config) - known
        if unknown:
            raise KeyError(f"Unknown Task-0011 rule configuration: {sorted(unknown)}")
        self.rules = tuple(cls(i, config.get(cls.rule_id)) for i, cls in enumerate(TASK_0011_RULE_CLASSES))
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
        token_spans = tokens_to_spans(self._word_tokenizer.tokenize(text), mapper=mapper)
        return NativeRuleContext(text, tuple(units), mapper, token_spans)

    def check_context(self, context: NativeRuleContext, include_disabled: bool = False) -> list[NativeRuleFinding]:
        findings = []
        for rule in self.rules:
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
