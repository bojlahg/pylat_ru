"""Native Python implementation of JLanguageTool raw Russian sentence assembly.

Reproduces JLanguageTool.getRawAnalyzedSentence() for Russian:
- Tokenizes with RussianWordTokenizer
- Strips Russian ignored characters [\\u00AD\\u0301\\u0300] before morphology lookup
- Tracks clean token vs source token surface
- Accumulates Java-compatible UTF-16 start positions and posFix adjustments
- Preserves whitespace tokens and whitespace-before state
- Prepends artificial SENT_START token at index 0
- Appends SENT_END reading to the last non-whitespace token
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from pylat_ru.analysis import (
    SENT_END_TAG,
    SENT_START_TAG,
    AnalyzedSentence,
    AnalyzedToken,
    AnalyzedTokenReadings,
)
from pylat_ru.tagging.russian import RussianTagger, utf16_len
from pylat_ru.tokenization.word import RussianWordTokenizer


# Russian ignored characters regex matching Russian.getIgnoredCharactersRegex()
RUSSIAN_IGNORED_CHARS_REGEX = re.compile(r"[\u00AD\u0301\u0300]")


@dataclass(frozen=True)
class CleanToken:
    """Represents an original token and its cleaned representation after removing ignored characters."""

    orig_token: str
    clean_token: str


class RussianSentenceAnalyzer:
    """Assembles JLanguageTool-compatible raw AnalyzedSentence for Russian."""

    _instance: Optional[RussianSentenceAnalyzer] = None

    def __init__(
        self,
        tagger: Optional[RussianTagger] = None,
        word_tokenizer: Optional[RussianWordTokenizer] = None,
    ) -> None:
        self.tagger = tagger or RussianTagger.get_instance()
        self.word_tokenizer = word_tokenizer or RussianWordTokenizer()

    @classmethod
    def get_instance(cls) -> RussianSentenceAnalyzer:
        """Get or create singleton RussianSentenceAnalyzer instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def analyze_raw(self, sentence: str) -> AnalyzedSentence:
        """Construct raw AnalyzedSentence matching JLanguageTool.getRawAnalyzedSentence(sentence)."""
        tokens: List[str] = list(self.word_tokenizer.tokenize(sentence))
        soft_hyphen_tokens: Dict[int, CleanToken] = {}

        # 1. Preprocess Russian ignored characters (soft hyphen U+00AD, acute U+0301, grave U+0300)
        for i, tok in enumerate(tokens):
            if RUSSIAN_IGNORED_CHARS_REGEX.search(tok):
                cleaned = RUSSIAN_IGNORED_CHARS_REGEX.sub("", tok)
                soft_hyphen_tokens[i] = CleanToken(orig_token=tok, clean_token=cleaned)
                tokens[i] = cleaned

        # 2. Tag tokens via RussianTagger
        a_tokens: List[AnalyzedTokenReadings] = self.tagger.tag(tokens)

        # 3. Create tokenArray with SENT_START at index 0
        token_array: List[AnalyzedTokenReadings] = []
        sent_start_reading = AnalyzedToken(token="", lemma=None, pos_tag=SENT_START_TAG)
        sent_start_atr = AnalyzedTokenReadings(
            readings=[sent_start_reading],
            start_pos=0,
            is_sentence_start=True,
            source_token="",
            clean_token="",
        )
        token_array.append(sent_start_atr)

        # 4. Compute initial UTF-16 start positions based on cleaned token lengths
        start_pos = 0
        for pos_tag in a_tokens:
            pos_tag.start_pos = start_pos
            token_array.append(pos_tag)
            start_pos += utf16_len(pos_tag.token)

        # 5. Apply posFix and restore source/clean token information
        num_tokens = len(a_tokens)
        pos_fix = 0
        for i in range(num_tokens):
            if i > 0:
                a_tokens[i].whitespace_before = a_tokens[i - 1].token
                a_tokens[i].start_pos = a_tokens[i].start_pos + pos_fix
                a_tokens[i].pos_fix = pos_fix
            else:
                a_tokens[i].pos_fix = pos_fix

            if i in soft_hyphen_tokens:
                ct = soft_hyphen_tokens[i]
                pos_fix += utf16_len(ct.orig_token) - utf16_len(a_tokens[i].token)
                # In Java LT, new null token with origToken surface is appended
                new_token = AnalyzedToken(token=ct.orig_token, lemma=None, pos_tag=None)
                a_tokens[i].add_reading(new_token, "softHyphenTokens")
                a_tokens[i].clean_token = ct.clean_token
                a_tokens[i].source_token = ct.orig_token

        # 6. Add SENT_END to the last non-whitespace token
        total_tokens = len(token_array)
        last_non_ws_idx = total_tokens - 1
        for i in range(total_tokens - 1):
            cand_idx = (total_tokens - 1) - i
            if not token_array[cand_idx].is_whitespace():
                last_non_ws_idx = cand_idx
                break

        if last_non_ws_idx > 0:
            token_array[last_non_ws_idx].set_sentence_end(True)

        return AnalyzedSentence(tokens=token_array)


def create_raw_analyzed_sentence(sentence: str) -> AnalyzedSentence:
    """Convenience helper to assemble raw AnalyzedSentence for Russian text."""
    return RussianSentenceAnalyzer.get_instance().analyze_raw(sentence)
