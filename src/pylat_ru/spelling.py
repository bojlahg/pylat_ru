"""src/pylat_ru/spelling.py

Python-native equivalent of the LanguageTool 6.8 Morfologik spelling stack used
by the Russian language module:

``morfologik.speller.Speller`` → ``MorfologikSpeller`` → ``MorfologikMultiSpeller``
→ ``SpellingCheckRule`` → ``MorfologikSpellerRule`` →
``MorfologikRussianSpellerRule`` / ``MorfologikRussianYOSpellerRule``.

Production code here is fully self-contained: it reads the Morfologik binary
dictionaries and plain-text word lists packaged with ``pylat_ru`` and never
invokes Java, a LanguageTool server, a subprocess, or the network.
"""

from __future__ import annotations

import re
import threading
import unicodedata
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Dict, List, Optional, Sequence, Tuple

from pylat_ru.morfologik.dictionary import MorfologikDictionary
from pylat_ru.morfologik.fsa import read_fsa
from pylat_ru.morfologik.metadata import DictionaryMetadata
from pylat_ru.morfologik.speller import (
    Speller,
    build_plain_text_dictionary,
    is_letter,
    is_lower_case,
    is_upper_case,
)
from pylat_ru.tokenization.word import RussianWordTokenizer

# org.languagetool.rules.spelling.SpellingCheckRule
LANGUAGETOOL = "LanguageTool"
LANGUAGETOOLER = "LanguageTooler"
MAX_TOKEN_LENGTH = 200

# org.languagetool.rules.patterns.StringMatcher
MAX_MATCH_LENGTH = 250

# org.languagetool.rules.spelling.morfologik.MorfologikSpellerRule
MAX_FREQUENCY_FOR_SPLITTING = 21

# MessagesBundle_ru.properties
GLOBAL_SPELLING_FILE = "spelling_global.txt"

MSG_SPELLING = "Возможно найдена орфографическая ошибка."
MSG_SPELLING_SHORT = "Орфографическая ошибка"
DESC_SPELLING = "Проверка орфографии с исправлениями"

_LETTER_CATEGORIES = frozenset({"Lu", "Ll", "Lt", "Lm", "Lo"})
_PUNCT_CATEGORIES = frozenset({"Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po"})

# org.languagetool.tokenizers.WordTokenizer
_PROTOCOLS = ("http", "https", "ftp")
_NO_PROTOCOL_URL = re.compile(
    r"([a-zA-Z0-9][a-zA-Z0-9-]+\.)?([a-zA-Z0-9][a-zA-Z0-9-]+)\.([a-zA-Z0-9][a-zA-Z0-9-]+)/[\s\S]*"
)
_E_MAIL = re.compile(
    r"@?\b[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))\b"
)

# MorfologikSpellerRule uses ^(\d[\.,\d]*|\P{L}+)(.*)$ and ^([\p{C}\-\$%&]+)(.*)$.
# Python's `re` has no \p{...} classes, so both are ported as explicit scanners
# below; Java's `.` never matches these line terminators.
_JAVA_LINE_TERMINATORS = "\n\r\u0085\u2028\u2029"

_DIGITS = frozenset("0123456789")


def _java_non_letter_run(text: str) -> int:
    """Length of the leading run of non-letter characters (Java ``\\P{L}+``)."""
    length = 0
    for ch in text:
        if is_letter(ch):
            break
        length += 1
    return length


def _starts_with_numbers_bullets(word: str) -> Optional[Tuple[str, str]]:
    """Port of ``pStartsWithNumbersBullets`` (``^(\\d[\\.,\\d]*|\\P{L}+)(.*)$``).

    ``.`` does not match line terminators in Java, and neither alternative can
    match one, so a word containing ``\\n`` or ``\\r`` never matches.
    """
    if not word or any(ch in _JAVA_LINE_TERMINATORS for ch in word):
        return None
    if word[0] in _DIGITS:
        end = 1
        while end < len(word) and word[end] in ".,0123456789":
            end += 1
        return word[:end], word[end:]
    run = _java_non_letter_run(word)
    if run > 0:
        return word[:run], word[run:]
    return None


def _starts_with_numbers_bullets_exception(word: str) -> bool:
    """Port of ``pStartsWithNumbersBulletsExceptions`` (``^([\\p{C}\\-\\$%&]+)(.*)$``)."""
    if not word or any(ch in _JAVA_LINE_TERMINATORS for ch in word):
        return False
    allowed = 0
    for ch in word:
        if ch in "-$%&" or unicodedata.category(ch)[0] == "C":
            allowed += 1
        else:
            break
    return allowed > 0


def utf16_len(text: str) -> int:
    """UTF-16 code-unit length, matching Java ``String.length()``."""
    return sum(2 if ord(ch) > 0xFFFF else 1 for ch in text)


def has_no_letter(text: str) -> bool:
    """Java: ``Pattern.compile("^[^\\p{L}]+$").matcher(word).matches()``."""
    return bool(text) and not any(is_letter(ch) for ch in text)


def is_url(token: str) -> bool:
    """Port of ``WordTokenizer.isUrl``."""
    for protocol in _PROTOCOLS:
        if token.startswith(protocol + "://") or token.startswith("www."):
            return True
    return bool(_NO_PROTOCOL_URL.fullmatch(token))


def is_email(token: str) -> bool:
    """Port of ``WordTokenizer.isEMail``."""
    return bool(_E_MAIL.fullmatch(token))


def is_all_uppercase(text: str) -> bool:
    """Port of ``StringTools.isAllUppercase``."""
    for ch in text:
        if is_letter(ch) and is_lower_case(ch):
            return False
    return True


def is_not_all_lowercase(text: str) -> bool:
    """Port of ``StringTools.isNotAllLowercase``."""
    for ch in text:
        if is_letter(ch) and not is_lower_case(ch):
            return True
    return False


def is_capitalized_word(text: str) -> bool:
    """Port of ``StringTools.isCapitalizedWord``."""
    if text and is_upper_case(text[0]):
        for ch in text[1:]:
            if is_letter(ch) and not is_lower_case(ch):
                return False
        return True
    return False


def is_mixed_case(text: str) -> bool:
    """Port of ``StringTools.isMixedCase``."""
    return (
        not is_all_uppercase(text)
        and not is_capitalized_word(text)
        and is_not_all_lowercase(text)
    )


def starts_with_uppercase(text: str) -> bool:
    """Port of ``StringTools.startsWithUppercase``."""
    return bool(text) and is_upper_case(text[0])


def is_punctuation_mark(text: str) -> bool:
    """Port of ``StringTools.isPunctuationMark`` (``[\\p{IsPunctuation}']``)."""
    return len(text) == 1 and (text == "'" or unicodedata.category(text) in _PUNCT_CATEGORIES)


def _change_first_char_case(text: str, to_upper: bool) -> str:
    """Port of ``StringTools.changeFirstCharCase``."""
    if not text:
        return text
    if len(text) == 1:
        return text.upper() if to_upper else text.lower()
    pos = 0
    end = len(text) - 1
    while unicodedata.category(text[pos])[0] not in {"L", "N"} and end > pos:
        pos += 1
    first = text[pos]
    changed = first.upper() if to_upper else first.lower()
    if len(changed) != 1:
        changed = first
    return text[:pos] + changed + text[pos + 1:]


def uppercase_first_char(text: str) -> str:
    """Port of ``StringTools.uppercaseFirstChar``."""
    return _change_first_char_case(text, True)


def lowercase_first_char(text: str) -> str:
    """Port of ``StringTools.lowercaseFirstChar``."""
    return _change_first_char_case(text, False)


def _word_for_speller(word: str) -> bool:
    """Java: ``^[\\p{L}\\d\\p{P}\\p{Zs}]+$`` (``\\d`` is ASCII-only in Java)."""
    if not word:
        return False
    for ch in word:
        category = unicodedata.category(ch)
        if category in _LETTER_CATEGORIES or ch in _DIGITS:
            continue
        if category in _PUNCT_CATEGORIES or category == "Zs":
            continue
        return False
    return True


def is_emoji(word: str) -> bool:
    """Port of ``StringTools.isEmoji``."""
    length = utf16_len(word)
    if length > 1 and length != len(word):
        return not _word_for_speller(word)
    return False


@dataclass(frozen=True)
class WeightedSuggestion:
    """Port of ``org.languagetool.rules.spelling.morfologik.WeightedSuggestion``."""

    word: str
    weight: int


class MorfologikSpeller:
    """Port of ``org.languagetool.rules.spelling.morfologik.MorfologikSpeller``."""

    def __init__(self, dictionary: MorfologikDictionary, max_edit_distance: int = 1) -> None:
        if max_edit_distance <= 0:
            raise ValueError(f"maxEditDistance must be > 0: {max_edit_distance}")
        self.dictionary = dictionary
        self.max_edit_distance = max_edit_distance
        self._speller = Speller(dictionary, max_edit_distance)
        self._lock = threading.RLock()

    def is_misspelled(self, word: str) -> bool:
        if not word or word == LANGUAGETOOL or word == LANGUAGETOOLER:
            return False
        with self._lock:
            return self._speller.is_misspelled(word)

    def get_frequency(self, word: str) -> int:
        with self._lock:
            frequency = self._speller.get_frequency(word)
            if frequency == 0 and word != word.lower():
                frequency = self._speller.get_frequency(word.lower())
            return frequency

    def converts_case(self) -> bool:
        return self._speller.converts_case()

    def get_suggestions(self, word: str) -> List[WeightedSuggestion]:
        suggestions: List[WeightedSuggestion] = []
        if len(word) > MAX_MATCH_LENGTH:
            return suggestions
        # Upstream rebuilds the Speller for every request because the H matrix is
        # not reset between searches.
        speller = Speller(self.dictionary, self.max_edit_distance)
        if len(word) < 50:
            for candidate in speller.find_replacement_candidates(word):
                suggestions.append(WeightedSuggestion(candidate.word, candidate.distance))
        for candidate in speller.replace_run_on_word_candidates(word):
            suggestions.append(WeightedSuggestion(candidate.word, candidate.distance))

        if self.dictionary.metadata.convert_case and is_all_uppercase(word):
            suggestions = self._normalize_case(suggestions, word, all_uppercase=True)
        elif self.dictionary.metadata.convert_case and starts_with_uppercase(word):
            suggestions = self._normalize_case(suggestions, word, all_uppercase=False)
        return suggestions

    @staticmethod
    def _normalize_case(
        suggestions: List[WeightedSuggestion], word: str, all_uppercase: bool
    ) -> List[WeightedSuggestion]:
        i = 0
        while i < len(suggestions):
            sugg = suggestions[i]
            converted = sugg.word.upper() if all_uppercase else uppercase_first_char(sugg.word)
            if converted == word or is_mixed_case(sugg.word):
                converted = sugg.word
            aux_index = -1
            for index, item in enumerate(suggestions):
                if item.word == converted:
                    aux_index = index
                    break
            if aux_index > i:
                suggestions.pop(aux_index)
            if -1 < aux_index < i:
                suggestions.pop(i)
                i -= 1
            else:
                suggestions[i] = WeightedSuggestion(converted, sugg.weight)
            i += 1
        return suggestions


class MorfologikMultiSpeller:
    """Port of ``org.languagetool.rules.spelling.morfologik.MorfologikMultiSpeller``.

    ``pylat_ru`` has no premium user dictionaries, so the user-dictionary speller
    list is always empty and ``spellers`` is ``[binary, plain-text]``.
    """

    def __init__(
        self,
        binary_dictionary: MorfologikDictionary,
        plain_text_dictionary: Optional[MorfologikDictionary],
        max_edit_distance: int,
        speller_max_weight_diff: int = -1,
    ) -> None:
        binary_speller = MorfologikSpeller(binary_dictionary, max_edit_distance)
        spellers = [binary_speller]
        self.converts_case_value = binary_speller.converts_case()
        plain_text_speller: Optional[MorfologikSpeller] = None
        if plain_text_dictionary is not None:
            plain_text_speller = MorfologikSpeller(plain_text_dictionary, max_edit_distance)
            spellers.append(plain_text_speller)
        self.spellers: Tuple[MorfologikSpeller, ...] = tuple(spellers)
        self.default_dict_spellers: Tuple[MorfologikSpeller, ...] = (
            (binary_speller, plain_text_speller) if plain_text_speller else (binary_speller,)
        )
        self.user_dict_spellers: Tuple[MorfologikSpeller, ...] = ()
        self.speller_max_weight_diff = speller_max_weight_diff
        self._default_suggestion_cache: Dict[str, List[str]] = {}

    def is_misspelled(self, word: str) -> bool:
        for speller in self.spellers:
            if not speller.is_misspelled(word):
                return False
        return True

    def get_frequency(self, word: str) -> int:
        for speller in self.spellers:
            frequency = speller.get_frequency(word)
            if frequency > 0:
                return frequency
        return 0

    def converts_case(self) -> bool:
        return self.converts_case_value

    def _suggestions_from(self, word: str, spellers: Sequence[MorfologikSpeller]) -> List[str]:
        result: List[WeightedSuggestion] = []
        seen: set = set()
        for speller in spellers:
            for suggestion in speller.get_suggestions(word):
                if suggestion.word not in seen and suggestion.word != word:
                    result.append(suggestion)
                seen.add(suggestion.word)
        result.sort(key=lambda item: item.weight)
        words: List[str] = []
        prev_weight = -1
        for suggestion in result:
            if (
                self.speller_max_weight_diff > 0
                and prev_weight > 0
                and suggestion.weight - prev_weight > self.speller_max_weight_diff
            ):
                break
            words.append(suggestion.word)
            prev_weight = suggestion.weight
        return words

    def get_suggestions(self, word: str) -> List[str]:
        return self._suggestions_from(word, self.spellers)

    def get_suggestions_from_user_dicts(self, word: str) -> List[str]:
        return self._suggestions_from(word, self.user_dict_spellers)

    def get_suggestions_from_default_dicts(self, word: str) -> List[str]:
        cached = self._default_suggestion_cache.get(word)
        if cached is not None:
            return list(cached)
        value = self._suggestions_from(word, self.default_dict_spellers)
        if len(self._default_suggestion_cache) < 2000:
            self._default_suggestion_cache[word] = list(value)
        return list(value)


def load_word_list(path) -> List[str]:
    """Port of ``CachingWordListLoader.loadWords``."""
    result: List[str] = []
    text = path.read_text(encoding="utf-8")
    for raw_line in text.split("\n"):
        line = raw_line.rstrip("\r")
        if not line or line.startswith("#"):
            continue
        result.append(line.strip().split("#", 1)[0].strip())
    return result


_ANTI_PATTERN_CACHE: Dict[int, "SpellerAntiPatternIndex"] = {}
_DICTIONARY_CACHE: Dict[str, MorfologikDictionary] = {}
_PLAIN_TEXT_CACHE: Dict[str, MorfologikDictionary] = {}
_WORD_LIST_CACHE: Dict[str, List[str]] = {}
_RESOURCE_LOCK = threading.RLock()


def _hunspell_resource(name: str):
    return files("pylat_ru.resources.ru.hunspell").joinpath(name)


def _resource_root(name: str):
    return files("pylat_ru.resources").joinpath(name)


def _cached_word_list(name: str) -> List[str]:
    with _RESOURCE_LOCK:
        cached = _WORD_LIST_CACHE.get(name)
        if cached is None:
            path = _resource_root(name) if "/" not in name and name == GLOBAL_SPELLING_FILE else _hunspell_resource(name)
            cached = load_word_list(path)
            _WORD_LIST_CACHE[name] = cached
        return cached


class SpellerAntiPatternIndex:
    """Ignore-spelling antipatterns created by ``SpellingCheckRule.addIgnoreWords``.

    Any accepted-spelling line that the language word tokenizer splits into more
    than one token becomes an ``IGNORE_SPELLING`` disambiguation antipattern of
    case-sensitive, non-inflected pattern tokens.  Matching those directly on the
    whitespace-free token list is equivalent to running the pinned pattern rules
    and avoids materializing ~27k rule objects per speller.
    """

    def __init__(self, lines: Sequence[str], tokenizer: RussianWordTokenizer) -> None:
        self.single_tokens: List[str] = []
        self.phrases: Dict[str, List[Tuple[str, ...]]] = {}
        self.max_length = 0
        for line in lines:
            tokens = list(tokenizer.tokenize(line))
            if len(tokens) > 1:
                pattern = tuple(token for token in tokens if token.strip())
                if not pattern:
                    continue
                self.phrases.setdefault(pattern[0], []).append(pattern)
                self.max_length = max(self.max_length, len(pattern))
            else:
                self.single_tokens.append(line)

    def apply(self, tokens: Sequence["SpellerToken"]) -> None:
        """Mark every token covered by a matching antipattern as ignored by the speller."""
        if not self.phrases:
            return
        surface = [token.token for token in tokens]
        total = len(surface)
        for index in range(total):
            candidates = self.phrases.get(surface[index])
            if not candidates:
                continue
            for pattern in candidates:
                end = index + len(pattern)
                if end > total:
                    continue
                if all(surface[index + offset] == pattern[offset] for offset in range(len(pattern))):
                    for offset in range(len(pattern)):
                        tokens[index + offset].is_ignore_spelling = True


def _cached_anti_patterns(
    lines: Sequence[str], tokenizer: RussianWordTokenizer
) -> "SpellerAntiPatternIndex":
    """Both Russian speller rules load the same accepted-spelling lines."""
    with _RESOURCE_LOCK:
        key = len(lines)
        cached = _ANTI_PATTERN_CACHE.get(key)
        if cached is None:
            cached = SpellerAntiPatternIndex(lines, tokenizer)
            _ANTI_PATTERN_CACHE[key] = cached
        return cached


def load_binary_dictionary(name: str) -> MorfologikDictionary:
    """Load and cache a packaged Morfologik speller dictionary by base name."""
    with _RESOURCE_LOCK:
        cached = _DICTIONARY_CACHE.get(name)
        if cached is not None:
            return cached
        metadata = DictionaryMetadata.from_text(
            _hunspell_resource(name + ".info").read_text(encoding="utf-8"),
            source_name=name + ".info",
        )
        fsa = read_fsa(_hunspell_resource(name + ".dict").read_bytes())
        dictionary = MorfologikDictionary(fsa=fsa, metadata=metadata)
        _DICTIONARY_CACHE[name] = dictionary
        return dictionary


def _plain_text_dictionary(name: str, lines: Sequence[str]) -> Optional[MorfologikDictionary]:
    """Build (and cache) the runtime dictionary LT creates from ``spelling.txt``."""
    with _RESOURCE_LOCK:
        cached = _PLAIN_TEXT_CACHE.get(name)
        if cached is not None:
            return cached
        encoded = [line.encode("utf-8") for line in lines if line]
        if not encoded:
            return None
        dictionary = build_plain_text_dictionary(
            encoded, load_binary_dictionary(name).metadata
        )
        _PLAIN_TEXT_CACHE[name] = dictionary
        return dictionary


@dataclass
class SpellerToken:
    """The token view ``MorfologikSpellerRule`` needs from an analyzed sentence."""

    token: str
    clean_token: str
    start_pos: int
    is_sentence_start: bool = False
    is_immunized: bool = False
    is_ignore_spelling: bool = False
    is_whitespace_before: bool = False

    @property
    def end_pos(self) -> int:
        return self.start_pos + utf16_len(self.token)


@dataclass
class SpellingMatch:
    """A single spelling finding with UTF-16 offsets inside the analyzed sentence."""

    from_pos: int
    to_pos: int
    suggestions: List[str] = field(default_factory=list)
    message: str = MSG_SPELLING
    short_message: str = MSG_SPELLING_SHORT


class RussianSpellerRuleBase:
    """Shared Russian implementation of ``MorfologikSpellerRule`` + ``SpellingCheckRule``.

    The two registered Russian spelling rules differ only by dictionary, rule id,
    description, default state, and NOSUGGEST filter set.
    """

    rule_id = ""
    dictionary_file = ""
    description = DESC_SPELLING
    default_off = False
    lc_do_not_suggest_words: frozenset = frozenset()

    # MorfologikRussianSpellerRule.RUSSIAN_LETTERS (identical in the YO rule)
    RUSSIAN_LETTERS = re.compile(
        "[-а-яё"
        "о́а́е́у́и́"
        "ы́э́ю́я́"
        "о̀а̀ѐу̀ѝ"
        "ы̀э̀ю̀я̀"
        "ʼА-ЯЁ]*"
    )

    def __init__(self, conf_ru_value: int = 0) -> None:
        self.conf_ru_value = conf_ru_value
        self._speller1: Optional[MorfologikMultiSpeller] = None
        self._speller2: Optional[MorfologikMultiSpeller] = None
        self._speller3: Optional[MorfologikMultiSpeller] = None
        self._converts_case = False
        self._words_to_be_ignored: set = set()
        self._words_to_be_prohibited: set = set()
        self._word_tokenizer = RussianWordTokenizer()
        self._anti_patterns: Optional[SpellerAntiPatternIndex] = None
        self._init_lock = threading.RLock()
        self._initialized = False

    # ---------------------------------------------------------------- init

    def _init(self) -> None:
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            binary_dictionary = load_binary_dictionary(self.dictionary_file)

            ignore_words = _cached_word_list("ignore.txt")
            spelling_words = _cached_word_list("spelling.txt")
            # getAdditionalSpellingFileNames(): ru/hunspell/spelling_custom.txt is
            # absent at the pin, spelling_global.txt ships in languagetool-core.
            global_words = _cached_word_list(GLOBAL_SPELLING_FILE)
            prohibited = _cached_word_list("prohibit.txt")

            # SpellingCheckRule#init: ignore.txt, spelling.txt and the additional
            # spelling files all feed wordsToBeIgnored, but a line the tokenizer
            # splits becomes an ignore-spelling antipattern instead.
            self._anti_patterns = _cached_anti_patterns(
                ignore_words + spelling_words + global_words, self._word_tokenizer
            )
            self._words_to_be_ignored.update(self._anti_patterns.single_tokens)
            self._words_to_be_prohibited.update(prohibited)

            plain = _plain_text_dictionary(
                self.dictionary_file, spelling_words + global_words
            )
            self._speller1 = MorfologikMultiSpeller(binary_dictionary, plain, 1)
            self._speller2 = MorfologikMultiSpeller(binary_dictionary, plain, 2)
            self._speller3 = MorfologikMultiSpeller(binary_dictionary, plain, 3)
            self._converts_case = self._speller1.converts_case()
            self._initialized = True

    @property
    def speller1(self) -> MorfologikMultiSpeller:
        self._init()
        assert self._speller1 is not None
        return self._speller1

    @property
    def speller2(self) -> MorfologikMultiSpeller:
        self._init()
        assert self._speller2 is not None
        return self._speller2

    @property
    def speller3(self) -> MorfologikMultiSpeller:
        self._init()
        assert self._speller3 is not None
        return self._speller3

    # ------------------------------------------------------- spelling checks

    def is_misspelled(self, word: str) -> bool:
        """``MorfologikSpellerRule.isMisspelled(String)`` (checkCompound is off for Russian)."""
        return self.speller1.is_misspelled(word)

    def is_prohibited(self, word: str) -> bool:
        self._init()
        return word in self._words_to_be_prohibited

    def is_in_ignored_set(self, word: str) -> bool:
        self._init()
        return word in self._words_to_be_ignored

    def is_ignored_no_case(self, word: str) -> bool:
        self._init()
        return self.is_in_ignored_set(word) or (
            not is_mixed_case(word) and self._converts_case and self.is_in_ignored_set(word.lower())
        )

    def ignore_word(self, word: str) -> bool:
        """``SpellingCheckRule.ignoreWord`` + ``MorfologikSpellerRule.ignoreWord``."""
        self._init()
        if self._ignore_word_base(word):
            return True
        return is_emoji(word)

    def _ignore_word_base(self, word: str) -> bool:
        if len(word) > MAX_TOKEN_LENGTH:
            return True
        # isLatinScript() is false for Russian, so the plain \p{L} test applies.
        if has_no_letter(word):
            return True
        if word.endswith(".") and not self.is_in_ignored_set(word):
            return self.is_ignored_no_case(word[:-1])
        return self.is_ignored_no_case(word)

    def ignore_token(self, tokens: Sequence[SpellerToken], idx: int) -> bool:
        """``MorfologikRussianSpellerRule.ignoreToken``."""
        word = tokens[idx].token
        if self.conf_ru_value != 1 and not self.RUSSIAN_LETTERS.fullmatch(word):
            return True
        return self.ignore_word(word)

    def _can_be_ignored(self, tokens: Sequence[SpellerToken], idx: int) -> bool:
        token = tokens[idx]
        return (
            token.is_sentence_start
            or token.is_immunized
            or token.is_ignore_spelling
            or is_url(token.token)
            or is_email(token.token)
            or self.ignore_token(tokens, idx)
        )

    # ------------------------------------------------------------ suggestions

    def filter_no_suggest_words(self, suggestions: List[str]) -> List[str]:
        """``MorfologikRussian(YO)SpellerRule.filterNoSuggestWords``."""
        return [s for s in suggestions if s.lower() not in self.lc_do_not_suggest_words]

    def filter_suggestions(self, suggestions: List[str]) -> List[str]:
        """``SpellingCheckRule.filterSuggestions``.

        The English possessive branch requires an ``NNP`` tag, which the Russian
        tagset never produces, so only prohibition, dedup, and NOSUGGEST apply.
        """
        remaining = [s for s in suggestions if not self.is_prohibited(s)]
        deduped: List[str] = []
        for item in remaining:
            if item not in deduped:
                deduped.append(item)
        return self.filter_no_suggest_words(deduped)

    def calc_speller_suggestions(self, word: str) -> List[str]:
        """``MorfologikSpellerRule.calcSpellerSuggestions``.

        ``getOnlySuggestions``/``getAdditionalSuggestions``/``orderSuggestions``
        and ``addHyphenSuggestions`` are all no-ops in the pinned base classes,
        and Russian has no user dictionary, so only the default dictionaries and
        the curated LanguageTool top suggestions contribute.
        """
        default_suggestions = list(self.speller1.get_suggestions_from_default_dicts(word))
        only_case_differs = bool(
            default_suggestions and word.lower() == default_suggestions[0].lower()
        )
        if len(word) >= 3 and (only_case_differs or not default_suggestions):
            default_suggestions.extend(self.speller2.get_suggestions_from_default_dicts(word))
            if len(word) >= 5 and not default_suggestions:
                default_suggestions.extend(self.speller3.get_suggestions_from_default_dicts(word))
        top_suggestions = self._additional_top_suggestions(word, default_suggestions)
        default_suggestions[0:0] = top_suggestions
        if not default_suggestions:
            return []
        return self.filter_suggestions(default_suggestions)

    @staticmethod
    def _additional_top_suggestions(word: str, suggestions: Sequence[str]) -> List[str]:
        """``SpellingCheckRule.getAdditionalTopSuggestions``."""
        more: List[str] = []
        if word in ("Languagetool", "languagetool") and LANGUAGETOOL not in suggestions:
            more.append(LANGUAGETOOL)
        if word in ("Languagetooler", "languagetooler") and LANGUAGETOOLER not in suggestions:
            more.append(LANGUAGETOOLER)
        return more

    # ----------------------------------------------------------------- match

    def match(self, tokens: Sequence[SpellerToken]) -> List[SpellingMatch]:
        """``MorfologikSpellerRule.match`` for the Russian registration surface."""
        self._init()
        # Rule.getSentenceWithImmunization: apply this rule's own antipatterns.
        if self._anti_patterns is not None:
            self._anti_patterns.apply(tokens)
        matches: List[SpellingMatch] = []
        is_first_word = True
        for idx, token in enumerate(tokens):
            if self._can_be_ignored(tokens, idx):
                if idx > 0 and is_first_word and not is_punctuation_mark(token.token):
                    is_first_word = False
                continue
            start_pos = token.start_pos
            word = token.clean_token
            new_rule_idx = len(matches)
            # tokenizingPattern() is null for the Russian speller rules.
            matches.extend(self._get_rule_matches(word, start_pos, matches, idx, tokens))
            if len(matches) > new_rule_idx:
                hidden_char_offset = utf16_len(token.token) - utf16_len(word)
                if hidden_char_offset > 0:
                    for match in matches[new_rule_idx:]:
                        if token.end_pos < match.to_pos:
                            continue
                        match.to_pos += hidden_char_offset
            if is_first_word and matches and idx < len(tokens) - 1:
                match = matches[0]
                new_replacements: List[str] = []
                for replacement in match.suggestions:
                    if replacement == replacement.lower():
                        capitalized = uppercase_first_char(replacement)
                        if capitalized not in new_replacements:
                            new_replacements.append(capitalized)
                    elif replacement not in new_replacements:
                        new_replacements.append(replacement)
                match.suggestions = new_replacements
            if idx > 0 and is_first_word and not is_punctuation_mark(token.token):
                is_first_word = False
        return matches

    def _create_wrong_split_match(
        self,
        matches_so_far: List[SpellingMatch],
        pos: int,
        covered_word: str,
        suggestion1: str,
        suggestion2: str,
        prev_pos: int,
    ) -> SpellingMatch:
        """``SpellingCheckRule.createWrongSplitMatch`` (mutates the running list)."""
        if matches_so_far and matches_so_far[-1].from_pos == prev_pos:
            matches_so_far.pop()
        return SpellingMatch(
            from_pos=prev_pos,
            to_pos=pos + utf16_len(covered_word),
            suggestions=[(suggestion1 + " " + suggestion2).strip()],
        )

    def _get_rule_matches(
        self,
        word: str,
        start_pos: int,
        matches_so_far: List[SpellingMatch],
        idx: int,
        tokens: Sequence[SpellerToken],
    ) -> List[SpellingMatch]:
        """``MorfologikSpellerRule.getRuleMatches``."""
        speller1 = self.speller1
        result: List[SpellingMatch] = []
        rule_match: Optional[SpellingMatch] = None

        if not speller1.is_misspelled(word) and not self.is_prohibited(word):
            return result
        # ignorePotentiallyMisspelledWord is false in the pinned base class.
        if matches_so_far and matches_so_far[-1].to_pos > start_pos:
            return result

        before_suggestion = ""
        after_suggestion = ""

        # Check for split word with previous word
        if idx > 0 and tokens[idx].is_whitespace_before:
            prev_word = tokens[idx - 1].token
            if (
                prev_word
                and not any(ch in _DIGITS for ch in prev_word)
                and speller1.get_frequency(prev_word) < MAX_FREQUENCY_FOR_SPLITTING
            ):
                prev_start_pos = tokens[idx - 1].start_pos
                sugg1a = prev_word[: len(prev_word) - 1]
                sugg1b = prev_word[len(prev_word) - 1:] + word
                if (
                    len(sugg1a) > 1
                    and len(sugg1b) > 2
                    and not speller1.is_misspelled(sugg1a)
                    and not speller1.is_misspelled(sugg1b)
                    and speller1.get_frequency(sugg1a) + speller1.get_frequency(sugg1b)
                    > speller1.get_frequency(prev_word)
                ):
                    rule_match = self._create_wrong_split_match(
                        matches_so_far, start_pos, word, sugg1a, sugg1b, prev_start_pos
                    )
                    before_suggestion = prev_word + " "
                sugg2a = prev_word + word[0]
                sugg2b = word[1:]
                if (
                    len(sugg2b) > 2
                    and not speller1.is_misspelled(sugg2a)
                    and not speller1.is_misspelled(sugg2b)
                ):
                    if rule_match is None:
                        if speller1.get_frequency(sugg2a) + speller1.get_frequency(
                            sugg2b
                        ) > speller1.get_frequency(prev_word):
                            rule_match = self._create_wrong_split_match(
                                matches_so_far, start_pos, word, sugg2a, sugg2b, prev_start_pos
                            )
                            before_suggestion = prev_word + " "
                    else:
                        _add_suggestion(rule_match, (sugg2a + " " + sugg2b).strip())
                joined = prev_word + word
                if word == word.lower() and not speller1.is_misspelled(joined):
                    if rule_match is None:
                        if speller1.get_frequency(joined) >= speller1.get_frequency(prev_word):
                            rule_match = SpellingMatch(
                                from_pos=prev_start_pos,
                                to_pos=start_pos + utf16_len(word),
                                suggestions=[joined],
                            )
                            before_suggestion = prev_word + " "
                    else:
                        _add_suggestion(rule_match, joined)
                if rule_match is not None and speller1.is_misspelled(prev_word):
                    result.append(rule_match)
                    return result

        # Check for split word with next word
        if rule_match is None and idx < len(tokens) - 1 and tokens[idx + 1].is_whitespace_before:
            next_word = tokens[idx + 1].token
            if (
                next_word
                and not any(ch in _DIGITS for ch in next_word)
                and speller1.get_frequency(next_word) < MAX_FREQUENCY_FOR_SPLITTING
            ):
                next_start_pos = tokens[idx + 1].start_pos
                sugg1a = word[: len(word) - 1]
                sugg1b = word[len(word) - 1:] + next_word
                if (
                    len(sugg1a) > 1
                    and len(sugg1b) > 2
                    and not speller1.is_misspelled(sugg1a)
                    and not speller1.is_misspelled(sugg1b)
                    and speller1.get_frequency(sugg1a) + speller1.get_frequency(sugg1b)
                    > speller1.get_frequency(next_word)
                ):
                    rule_match = self._create_wrong_split_match(
                        matches_so_far, next_start_pos, next_word, sugg1a, sugg1b, start_pos
                    )
                    after_suggestion = " " + next_word
                sugg2a = word + next_word[0]
                sugg2b = next_word[1:]
                if (
                    len(sugg2b) > 2
                    and not speller1.is_misspelled(sugg2a)
                    and not speller1.is_misspelled(sugg2b)
                ):
                    if rule_match is None:
                        if speller1.get_frequency(sugg2a) + speller1.get_frequency(
                            sugg2b
                        ) > speller1.get_frequency(next_word):
                            rule_match = self._create_wrong_split_match(
                                matches_so_far, next_start_pos, next_word, sugg2a, sugg2b, start_pos
                            )
                            after_suggestion = " " + next_word
                    else:
                        _add_suggestion(rule_match, (sugg2a + " " + sugg2b).strip())
                joined = word + next_word
                if next_word == next_word.lower() and not speller1.is_misspelled(joined):
                    if rule_match is None:
                        if speller1.get_frequency(joined) >= speller1.get_frequency(next_word):
                            rule_match = SpellingMatch(
                                from_pos=start_pos,
                                to_pos=next_start_pos + utf16_len(next_word),
                                suggestions=[joined],
                            )
                            after_suggestion = " " + next_word
                    else:
                        _add_suggestion(rule_match, joined)
                if rule_match is not None and speller1.is_misspelled(next_word):
                    result.append(rule_match)
                    return result

        prevent_further_suggestions = False
        if rule_match is None:
            rule_match = SpellingMatch(
                from_pos=start_pos, to_pos=start_pos + utf16_len(word)
            )

        # Word starting with numbers or bullets
        clean_word = word
        split = _starts_with_numbers_bullets(word)
        if split is not None and not _starts_with_numbers_bullets_exception(word):
            first_part, second_part = split
            second_part_tokens = self._word_tokenizer.tokenize(second_part)
            multitoken_is_misspelled = any(
                speller1.is_misspelled(part) for part in second_part_tokens
            )
            if (
                not multitoken_is_misspelled or self.is_ignored_no_case(second_part)
            ) and not self.is_prohibited(second_part):
                _add_suggestion(rule_match, first_part + " " + second_part)
                prevent_further_suggestions = True
            else:
                before_suggestion = first_part + " "
                clean_word = second_part

        if not prevent_further_suggestions:
            previous = list(rule_match.suggestions)
            from_speller = self.calc_speller_suggestions(clean_word)
            joined_suggestions = [
                before_suggestion + item + after_suggestion for item in from_speller
            ]
            rule_match.suggestions = previous + joined_suggestions

        result.append(rule_match)
        return result


def _add_suggestion(match: SpellingMatch, suggestion: str) -> None:
    """``RuleMatch.addSuggestedReplacement``."""
    if suggestion not in match.suggestions:
        match.suggestions.append(suggestion)


class RussianSpeller(RussianSpellerRuleBase):
    """Native equivalent of ``MorfologikRussianSpellerRule`` (``MORFOLOGIK_RULE_RU_RU``)."""

    rule_id = "MORFOLOGIK_RULE_RU_RU"
    dictionary_file = "ru_RU"
    description = DESC_SPELLING
    default_off = False
    lc_do_not_suggest_words = frozenset({"блоггер", "дрочим", "анальный", "орочем"})


class RussianYoSpeller(RussianSpellerRuleBase):
    """Native equivalent of ``MorfologikRussianYOSpellerRule`` (``MORFOLOGIK_RULE_RU_RU_YO``)."""

    rule_id = "MORFOLOGIK_RULE_RU_RU_YO"
    dictionary_file = "ru_RU_yo"
    description = "Проверка орфографии. Только «Ё» (экспериментальное правило)."
    default_off = True
    lc_do_not_suggest_words = frozenset({"блоггер", "елка", "дрочим", "анальный", "орочем"})


_DEFAULT_SPELLER_LOCK = threading.RLock()
_DEFAULT_SPELLER: Optional[RussianSpeller] = None


def get_default_spelling_rule() -> RussianSpeller:
    """Equivalent of ``Russian.getDefaultSpellingRule()``.

    Upstream constructs ``MorfologikRussianSpellerRule`` with a null ``UserConfig``,
    so the default speller always uses ``conf_ru_Value = 0`` and never sees user
    configuration.  Its dictionaries and word lists are immutable and shared, so
    one process-wide instance is safe and avoids reloading 1.8 MB per check.
    """
    global _DEFAULT_SPELLER
    with _DEFAULT_SPELLER_LOCK:
        if _DEFAULT_SPELLER is None:
            _DEFAULT_SPELLER = RussianSpeller(conf_ru_value=0)
        return _DEFAULT_SPELLER


__all__ = [
    "MorfologikMultiSpeller",
    "MorfologikSpeller",
    "RussianSpeller",
    "RussianSpellerRuleBase",
    "RussianYoSpeller",
    "SpellerToken",
    "SpellingMatch",
    "WeightedSuggestion",
    "get_default_spelling_rule",
    "is_all_uppercase",
    "is_capitalized_word",
    "is_email",
    "is_emoji",
    "is_mixed_case",
    "is_punctuation_mark",
    "is_url",
    "load_binary_dictionary",
    "lowercase_first_char",
    "starts_with_uppercase",
    "uppercase_first_char",
    "utf16_len",
]
