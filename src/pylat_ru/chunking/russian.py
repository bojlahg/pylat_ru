"""src/pylat_ru/chunking/russian.py

Native Python reimplementation of pinned LanguageTool RussianChunker.
Performs rule-based chunking on Russian AnalyzedSentence tokens after disambiguation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Set

from pylat_ru.analysis import AnalyzedSentence, AnalyzedTokenReadings
from pylat_ru.chunking.token_expression import ChunkTaggedToken, TokenExpression


@dataclass
class RegularExpressionWithPhraseType:
    expression: TokenExpression
    phrase_type: str
    overwrite: bool


class RussianChunker:
    """Rule-based Russian phrase chunker matching pinned LanguageTool RussianChunker."""

    FILTER_TAGS: Set[str] = {
        "PP",
        "NPP",
        "NPS",
        "MayMissingYO",
        "VP",
        "SBAR",
        "ADJP",
        "DPT",
    }

    SYNTAX_EXPANSION = {
        "<NP>": "<chunk=B-NP> <chunk=I-NP>*",
        "<VP>": "<chunk=B-VP> <chunk=I-VP>*",
        "<ADJP>": "<chunk=B-ADJP> <chunk=I-ADJP>*",
        "<DPT>": "<chunk=B-DPT> <chunk=I-DPT>*",
    }

    def __init__(self) -> None:
        self.regexes1 = self._init_regexes1()
        self.regexes2 = self._init_regexes2()

    def _build(self, expr: str, phrase_type: str, overwrite: bool = False) -> RegularExpressionWithPhraseType:
        expanded_expr = expr
        for k, v in self.SYNTAX_EXPANSION.items():
            expanded_expr = expanded_expr.replace(k, v)
        token_expr = TokenExpression(expanded_expr, case_sensitive=False)
        return RegularExpressionWithPhraseType(token_expr, phrase_type, overwrite)

    def _init_regexes1(self) -> List[RegularExpressionWithPhraseType]:
        return [
            # Иванов Иван Иванович
            self._build("<posre='NN:(Name|Fam|Patr):.*'> <posre='NN:(Name|Fam|Patr):.*'>+ ", "NP", True),
            # Иванов И.И.
            self._build("<posre='NN:Fam:.*'> <regexCS=[А-ЯЁ]> <.> <regexCS=[А-ЯЁ]> <.> ", "NP", True),
            # И.И. Иванов
            self._build("<regexCS=[А-ЯЁ]> <.> <regexCS=[А-ЯЁ]> <.> <posre='NN:Fam:.*'> ", "NP", True),
            # verb+verb
            self._build("<posre='VB:.*:.*' & !posre='NN:.*'>* ", "VP", False),
            self._build("<если>", "SBAR"),
            self._build("<поэтому>", "SBAR"),
            # noun phrase
            self._build("<posre='ADJ:Posit:.*:.*'> <posre='NN:(Anim|Inanim):.*' & !posre='NN:(Anim|Inanim):.*:(R|D|T|P)'> ", "NP", True),
            self._build("<posre='ADJ:Posit:.*:.*'> <posre='NN:(Anim|Inanim):.*' & !posre='NN:(Anim|Inanim):.*:(R|D|T|P)'> <posre='NN:(Anim|Inanim):.*'> ", "NP", True),
            # adj -> participle phrase
            self._build("<posre='ADJ:Posit:.*:.*'> <posre='NN:(Anim|Inanim):.*' & !posre='NN:(Anim|Inanim):.*:(Nom|V)'> <posre='NN:(Anim|Inanim):.*:(Nom|V)' & !posre='NN:(Anim|Inanim):.*:(R|D|T|P)'> ", "ADJP", True),
            # adverbial participle
            self._build("<posre='DPT:.*:.*' & !pos='PREP'> ", "DPT"),
            self._build("<posre='DPT:.*:.*' & !pos='PREP'> <posre='NN:.*:.*:(R|D|T|P)' > ", "DPT", True),
            self._build("<posre='DPT:.*:.*' & !pos='PREP'> <posre='PREP'> <posre='NN:.*:.*:(R|D|T|P)' > ", "DPT", True),
            # participle
            self._build("<posre='PT:.*:.*'> ", "ADJP"),
            self._build("<posre='PT:.*:.*'> <pos='ADV' > ", "ADJP", True),
            self._build("<posre='PT:.*:.*'> <posre='NN:.*:.*:(R|D|T|P)' > ", "ADJP", True),
            self._build("<posre='PT:.*:.*'> <posre='PREP'> <posre='NN:.*:.*:(R|D|T|P|V)' > ", "ADJP", True),
            self._build("<posre='PT:.*:.*'> <posre='PREP'> <posre='ADJ:.*:.*:(R|D|T|P|V)' > <posre='NN:.*:.*:(R|D|T|P|V)' > ", "ADJP", True),
            self._build("<posre='PT:.*:.*'> <posre='NN:(Anim|Inanim):.*' & !posre='NN:(Anim|Inanim):.*:(Nom|V)'> <posre='NN:(Anim|Inanim):.*:(Nom|V)' & !posre='NN:(Anim|Inanim):.*:(R|D|T|P)'> ", "ADJP", True),
            self._build("<posre='PT:.*:.*'> <posre='PNN:.*' & !posre='PNN:.*:Nom:.*'> <posre='NN:(Anim|Inanim):.*:(Nom|V)' & !posre='NN:(Anim|Inanim):.*:(R|D|T|P)'> ", "ADJP", True),
            self._build("<posre='PT:.*:.*'> <posre='ADJ:.*:.*' > ", "ADJP", False),
            self._build("<тов>", "NP"),
        ]

    def _init_regexes2(self) -> List[RegularExpressionWithPhraseType]:
        return [
            # ===== plural and singular noun phrases, based on OpenNLP chunker output ===============
            # "Маша и Миша":
            self._build("<posre=NN:Name:.*> <и> <posre=NN:Name:.*>", "NPP", True),
            self._build("<posre=NN:Name:.*> <или> <posre=NN:Name:.*>", "NPP", True),
            # не + VB
            self._build("<не> <posre='VB:.*:.*' & !posre='NN:.*'>* ", "VP", False),
        ]

    def add_chunk_tags(self, token_readings: Sequence[AnalyzedTokenReadings]) -> None:
        """Assign chunk tags in-place to the provided token readings."""
        chunk_tagged_tokens = self.get_basic_chunks(token_readings)
        for regex in self.regexes2:
            self._apply(regex, chunk_tagged_tokens)
        self._assign_chunks_to_readings(chunk_tagged_tokens)

    def chunk(self, sentence: AnalyzedSentence) -> AnalyzedSentence:
        """Add chunk tags to sentence and return it."""
        self.add_chunk_tags(sentence.tokens)
        return sentence

    def get_basic_chunks(self, token_readings: Sequence[AnalyzedTokenReadings]) -> List[ChunkTaggedToken]:
        """Filter out whitespace/MayMissingYO and apply REGEXES1."""
        chunk_tagged_tokens: List[ChunkTaggedToken] = []
        for tr in token_readings:
            if not tr.is_whitespace() and "MayMissingYO" not in tr.chunk_tags:
                chunk_tagged_tokens.append(
                    ChunkTaggedToken(
                        token=tr.token,
                        chunk_tags=["O"],
                        readings=tr,
                    )
                )

        for regex in self.regexes1:
            self._apply(regex, chunk_tagged_tokens)

        return chunk_tagged_tokens

    def _apply(self, regex: RegularExpressionWithPhraseType, tokens: List[ChunkTaggedToken]) -> None:
        matches = regex.expression.find_all(tokens)
        for start_idx, end_idx in matches:
            for i in range(start_idx, end_idx):
                tok = tokens[i]
                new_chunk_tags = list(tok.chunk_tags)

                if regex.overwrite:
                    new_chunk_tags = [ct for ct in new_chunk_tags if ct not in self.FILTER_TAGS]

                new_tag = self._get_chunk_tag(regex.phrase_type, is_first=(i == start_idx))
                if new_tag not in new_chunk_tags:
                    new_chunk_tags.append(new_tag)
                    if "O" in new_chunk_tags:
                        new_chunk_tags.remove("O")

                tok.chunk_tags = new_chunk_tags

    def _get_chunk_tag(self, phrase_type: str, is_first: bool) -> str:
        if phrase_type == "NP":
            return "B-NP" if is_first else "I-NP"
        elif phrase_type == "NPP":
            return "B-NP-plural" if is_first else "I-NP-plural"
        elif phrase_type == "VP":
            return "B-VP" if is_first else "I-VP"
        elif phrase_type == "ADJP":
            return "B-ADJP" if is_first else "I-ADJP"
        elif phrase_type == "DPT":
            return "B-DPT" if is_first else "I-DPT"
        else:
            return phrase_type

    def _assign_chunks_to_readings(self, chunk_tagged_tokens: List[ChunkTaggedToken]) -> None:
        for tagged_token in chunk_tagged_tokens:
            if tagged_token.readings is not None:
                tagged_token.readings.chunk_tags = list(tagged_token.chunk_tags)
