"""Hybrid chunker-disambiguator for Russian matching LanguageTool RussianHybridDisambiguator."""

from __future__ import annotations

from typing import Optional

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.disambiguation.multiwords import MultiWordChunker
from pylat_ru.disambiguation.xml_loader import XmlRuleDisambiguator
from pylat_ru.tagging.russian import RussianTagger
from pylat_ru.tokenization.word import RussianWordTokenizer


class RussianHybridDisambiguator:
    """Hybrid chunker-disambiguator for Russian.

    Port of org.languagetool.tagging.disambiguation.ru.RussianHybridDisambiguator.
    Combines:
    1. MultiWordChunker (/ru/multiwords.txt)
    2. XmlRuleDisambiguator (/ru/disambiguation.xml)
    """

    _instance: Optional[RussianHybridDisambiguator] = None

    def __init__(
        self,
        multiwords_chunker: Optional[MultiWordChunker] = None,
        xml_disambiguator: Optional[XmlRuleDisambiguator] = None,
        tagger: Optional[RussianTagger] = None,
        word_tokenizer: Optional[RussianWordTokenizer] = None,
    ) -> None:
        self.tagger = tagger or RussianTagger.get_instance()
        self.word_tokenizer = word_tokenizer or RussianWordTokenizer()
        self.chunker = multiwords_chunker or MultiWordChunker.get_instance("ru/multiwords.txt")
        self.disambiguator = xml_disambiguator or XmlRuleDisambiguator("ru/disambiguation.xml", tagger=self.tagger)

    @classmethod
    def get_instance(cls) -> RussianHybridDisambiguator:
        """Get or create singleton RussianHybridDisambiguator instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_analyzed_sentence(self, sentence_text: str) -> AnalyzedSentence:
        """Helper to tokenize, tag, and assemble raw AnalyzedSentence ready for disambiguation."""
        tokens = self.word_tokenizer.tokenize(sentence_text)
        tagged_readings = self.tagger.tag(tokens)

        # Create SENT_START pseudo-token at index 0
        sent_start = AnalyzedTokenReadings.create_sentence_start_token(start_pos=0)

        # Set character start positions for each token
        current_pos = 0
        positioned_readings: list[AnalyzedTokenReadings] = []
        for tr in tagged_readings:
            r = AnalyzedTokenReadings(tr, start_pos=current_pos)
            positioned_readings.append(r)
            current_pos += len(r.token)

        all_tokens = [sent_start] + positioned_readings
        return AnalyzedSentence(tokens=all_tokens)

    def disambiguate(self, sentence: AnalyzedSentence) -> AnalyzedSentence:
        """Execute complete Russian disambiguation pipeline: MultiWordChunker -> XmlRuleDisambiguator."""
        chunked = self.chunker.disambiguate(sentence)
        return self.disambiguator.disambiguate(chunked)

    def disambiguate_text(self, sentence_text: str) -> AnalyzedSentence:
        """Tokenize, tag, and disambiguate a sentence string."""
        raw_sentence = self.create_analyzed_sentence(sentence_text)
        return self.disambiguate(raw_sentence)
