"""src/pylat_ru/grammar/formatter.py

Message and suggestion template formatter with MatchState resolution,
include_skipped handling, Java regex $1/$2 substitutions, POS synthesis,
CaseConversionHelper parity, and LanguageTool-compatible error capitalization.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union
import regex

from pylat_ru.analysis import AnalyzedTokenReadings
from pylat_ru.grammar.errors import GrammarError
from pylat_ru.grammar.model import (
    MatchReference,
    MessageTemplate,
    SuggestionTemplate,
)
from pylat_ru.synthesis.synthesizer import RussianSynthesizer
from pylat_ru.tagging.string_tools import (
    change_first_char_case,
    is_all_uppercase,
    is_all_uppercase_tokens,
    is_capitalized_word,
    uppercase_first_char,
)


# PatternRuleMatcher.MISTAKE marks a synthesized form that the tagger does not
# know; PatternRuleHandler.PLEASE_SPELL_ME marks a suggestion that must be
# dropped when that happens.  The suggestion text itself is never emitted, so a
# private sentinel is enough to carry the same decision through formatting.
#: Tags pinned ``MatchState.toFinalString`` treats as sentence/paragraph markers
#: while deciding whether a lemma-less reading forces the surface form.
_SENTENCE_BOUNDARY_TAGS = frozenset(("SENT_START", "SENT_END", "PARA_END"))

SPELL_SUPPRESS_MARK = "\ue000pylat_ru:mistake\ue000"


def _tagger_knows_word(word: str) -> bool:
    """``MatchState``'s tagger-based speller: unknown means no lemma and no POS tag."""
    from pylat_ru.tagging.russian import RussianTagger

    readings = RussianTagger.get_instance().tag([word])
    if not readings:
        return False
    first = readings[0].get_analyzed_token(0)
    return not (first.lemma is None and first.has_no_tag)


def _java_to_python_regex_repl(repl: str) -> str:
    """Convert Java replacement string syntax ($1, $2, \\$, \\\\) to Python regex replacement format."""
    if not repl:
        return repl
    out: List[str] = []
    i = 0
    n = len(repl)
    while i < n:
        c = repl[i]
        if c == "\\":
            if i + 1 < n:
                next_c = repl[i + 1]
                if next_c in ("$", "\\"):
                    out.append(next_c)
                    i += 2
                    continue
                else:
                    out.append("\\")
                    out.append(next_c)
                    i += 2
                    continue
            else:
                out.append("\\")
                i += 1
                continue
        elif c == "$":
            j = i + 1
            while j < n and repl[j].isdigit():
                j += 1
            if j > i + 1:
                group_num = repl[i + 1 : j]
                out.append(f"\\g<{group_num}>")
                i = j
                continue
            else:
                out.append("$")
                i += 1
                continue
        else:
            out.append(c)
            i += 1
    return "".join(out)


def convert_case(case_conv: Optional[str], s: str, sample: Optional[str] = None) -> str:
    """Apply case conversion to string s according to case_conv and sample string."""
    if not s:
        return s
    if case_conv is None or case_conv.lower() in ("none", ""):
        return s
    conv = case_conv.lower()
    if conv == "preserve":
        if sample and sample[0].isupper():
            if sample.isupper() and len(sample) > 1:
                return s.upper()
            else:
                return uppercase_first_char(s)
        return s
    elif conv == "startlower":
        if s and s[0].isupper():
            return s[0].lower() + s[1:]
        return s
    elif conv == "startupper":
        return uppercase_first_char(s)
    elif conv == "allupper":
        return s.upper()
    elif conv == "alllower":
        return s.lower()
    elif conv == "firstupper":
        lowered = s.lower()
        return uppercase_first_char(lowered)
    elif conv == "notashkeel":
        return s
    return s


def resolve_match_reference_forms(
    ref: MatchReference,
    tokens: Sequence[AnalyzedTokenReadings],
    token_positions: Sequence[int],
    first_match_token: int,
    element_lengths: Optional[Sequence[int]] = None,
    synthesizer: Optional[RussianSynthesizer] = None,
    check_spelling: bool = False,
) -> List[str]:
    """Resolve a single MatchReference into a list of candidate replacement strings.

    With ``check_spelling`` the match behaves like a ``Match`` inside a
    ``suppress_misspelled`` suggestion: forms that cannot be synthesized or that
    the tagger does not recognize are returned as :data:`SPELL_SUPPRESS_MARK`.
    """
    token_k = ref.no - 1  # 0-indexed token position matching Java LT PatternRuleMatcher
    if token_k < 0:
        return [""]

    if element_lengths is not None:
        token_lens: Dict[int, int] = {}
        cur_t = 0
        for el_len in element_lengths:
            token_lens[cur_t] = el_len
            for offset in range(1, el_len):
                token_lens[cur_t + offset] = 1
            cur_t += el_len
        elem_len = token_lens.get(token_k, 1)
        if elem_len > 1:
            # Multi-token phrase element - concatenate phrase tokens matching Java LT
            phrase_word_lists: List[List[str]] = []
            for p_i in range(elem_len):
                cur_tok_k = token_k + p_i
                if cur_tok_k < len(token_positions):
                    rep_pos = sum(token_positions[: cur_tok_k + 1]) - 1
                    act_idx = first_match_token + rep_pos
                    if 0 <= act_idx < len(tokens):
                        p_atr = tokens[act_idx]
                        p_raw = p_atr.token or ""
                        p_word = convert_case(ref.case_conversion, p_raw, sample=p_raw)
                        phrase_word_lists.append([p_word])
            if phrase_word_lists:
                combos = [""]
                for w_list in phrase_word_lists:
                    combos = [
                        (prefix + " " + w if prefix else w)
                        for prefix in combos
                        for w in w_list
                    ]
                return combos

    if token_k >= len(token_positions):
        return [f"\\{ref.no}"]

    # Check if element was optional and skipped
    if token_positions[token_k] == 0:
        return [""]

    rep_token_pos = sum(token_positions[:token_k + 1]) - 1
    actual_token_idx = first_match_token + rep_token_pos

    if actual_token_idx < 0 or actual_token_idx >= len(tokens):
        return [f"\\{ref.no}"]

    target_atr = tokens[actual_token_idx]
    target_at = target_atr.readings[0] if target_atr.readings else None
    raw_word = target_atr.token or ""

    # Check skipped tokens if include_skipped is requested
    skipped_text = ""
    include_skipped = (ref.include_skipped or "").lower()

    if include_skipped in ("following", "all"):
        next_k = token_k + 1
        if next_k < len(token_positions):
            skipped_count = token_positions[next_k] - 1
            if skipped_count > 0:
                skipped_parts = []
                for s_i in range(1, skipped_count + 1):
                    if actual_token_idx + s_i < len(tokens):
                        s_atr = tokens[actual_token_idx + s_i]
                        has_ws = bool(getattr(s_atr, "is_whitespace_before", False) or getattr(s_atr, "whitespace_before", False))
                        if has_ws and not (s_i == 1 and include_skipped == "following"):
                            skipped_parts.append(" ")
                        skipped_parts.append(s_atr.token or "")
                skipped_text = "".join(skipped_parts)

    # 1. Regex transformation on surface word
    if ref.regexp_match is not None and ref.regexp_replace is not None:
        try:
            py_repl = _java_to_python_regex_repl(ref.regexp_replace)
            raw_word = regex.sub(ref.regexp_match, py_repl, raw_word)
        except Exception as e:
            raise GrammarError(f"Malformed regular expression or replacement in <match>: {e}") from e

    # 2. POS synthesis / modification -- MatchState.getTargetPosTag
    synth = synthesizer or RussianSynthesizer.get_instance()
    target_pos = ref.postag
    if target_pos and ref.postag_regexp:
        # Java uses Matcher.matches(), i.e. only a full match of the postag regex
        # against a reading's POS tag contributes to the target tag.
        pos_tags = [
            rd.pos_tag
            for rd in target_atr.readings
            if rd.pos_tag and regex.fullmatch(ref.postag, rd.pos_tag)
        ]
        target_pos = synth.get_target_pos_tag(pos_tags, target_pos)
        if ref.postag_replace is not None:
            if not pos_tags:
                pos_tags = [target_pos]
            py_pos_repl = _java_to_python_regex_repl(ref.postag_replace)
            replaced_tags = []
            for tag in pos_tags:
                try:
                    tag = regex.sub(ref.postag, py_pos_repl, tag)
                except Exception as e:
                    raise GrammarError(
                        f"Malformed regular expression or replacement in postag_replace: {e}"
                    ) from e
                if ref.setpos == "yes":
                    tag = synth.get_pos_tag_correction(tag)
                replaced_tags.append(tag)
            target_pos = "|".join(replaced_tags)

    words = [raw_word]
    synthesis_failed = False
    if target_pos and synth:
        if ref.postag_regexp and ref.lemma is None:
            # MatchState collects the forms of every reading in a TreeSet, but only
            # after a pre-pass over the lemma-less readings.  A reading with neither
            # lemma nor POS tag -- which is what a token carrying a combining mark
            # keeps alongside its tagged reading -- sets ``oneForm`` and contributes
            # the surface token itself, and synthesis is then skipped altogether.
            forms: set = set()
            one_form = False
            for rd in target_atr.readings:
                if rd.lemma is not None:
                    continue
                if rd.pos_tag is None:
                    forms.add(target_atr.token or "")
                    one_form = True
                elif rd.pos_tag in _SENTENCE_BOUNDARY_TAGS:
                    if not one_form:
                        forms.add(target_atr.token or "")
                    one_form = True
                else:
                    one_form = False
            if not one_form:
                for rd in target_atr.readings:
                    produced = synth.synthesize(rd, target_pos, pos_tag_is_regex=True)
                    if produced:
                        forms.update(produced)
            if forms:
                words = sorted(forms)
            else:
                # MatchState uses "(" + token + ")" here, which the
                # suppress_misspelled filter always removes.
                synthesis_failed = True
        else:
            tok_input = ref.lemma if ref.lemma is not None else (target_at if target_at is not None else raw_word)
            synth_forms = synth.synthesize(tok_input, target_pos, pos_tag_is_regex=ref.postag_regexp)
            if synth_forms:
                # MatchState.toFinalString collects every synthesized form in a
                # TreeSet in both of its branches, so upstream output is
                # deduplicated and sorted.  A token whose readings all map to the
                # same target tag otherwise yields the same form several times.
                words = sorted(set(synth_forms))
            elif ref.lemma:
                words = [ref.lemma]
            else:
                synthesis_failed = True
    elif ref.lemma:
        words = [ref.lemma]

    # 3. Handle include_skipped and case conversion
    if ref.regexp_match is not None and ref.regexp_replace is not None:
        sample_str = raw_word
    else:
        sample_str = target_atr.token or ""
    out_forms = []
    for w in words:
        if include_skipped == "following":
            w = skipped_text
        elif include_skipped == "all" and skipped_text:
            w = w + skipped_text
        w = convert_case(ref.case_conversion, w, sample=sample_str)
        out_forms.append(w)

    if not out_forms:
        out_forms = [raw_word]
    if check_spelling:
        if synthesis_failed:
            return [SPELL_SUPPRESS_MARK for _ in out_forms]
        out_forms = [w if _tagger_knows_word(w) else SPELL_SUPPRESS_MARK for w in out_forms]
    return out_forms


def resolve_match_reference(
    ref: MatchReference,
    tokens: Sequence[AnalyzedTokenReadings],
    token_positions: Sequence[int],
    first_match_token: int,
    element_lengths: Optional[Sequence[int]] = None,
    synthesizer: Optional[RussianSynthesizer] = None,
) -> str:
    """Resolve a single MatchReference into a single formatted replacement string."""
    forms = resolve_match_reference_forms(
        ref=ref,
        tokens=tokens,
        token_positions=token_positions,
        first_match_token=first_match_token,
        element_lengths=element_lengths,
        synthesizer=synthesizer,
    )
    return forms[0] if forms else ""


class TemplateFormatter:
    """Renders structured message and suggestion templates using MatchState context."""

    @staticmethod
    def format_message(
        template: MessageTemplate,
        tokens: Sequence[AnalyzedTokenReadings],
        token_positions: Optional[Sequence[int]] = None,
        first_match_token: int = 0,
        element_lengths: Optional[Sequence[int]] = None,
        synthesizer: Optional[RussianSynthesizer] = None,
        suggestion_suppress_flags: Sequence[bool] = (),
    ) -> str:
        """Format rule message replacing <match no="X"> references and expanding multi-form suggestions.

        ``suggestion_suppress_flags`` carries the per-``<suggestion>``
        ``suppress_misspelled`` state in document order; together with the
        message-level flag it reproduces ``removeSuppressMisspelled``, which
        deletes every suggestion whose synthesized form is misspelled.
        """
        positions = list(token_positions) if token_positions is not None else [1] * len(tokens)
        suggestion_index = 0

        def _suppresses(index: int) -> bool:
            if template.suppress_misspelled:
                return True
            return index < len(suggestion_suppress_flags) and suggestion_suppress_flags[index]

        def _build_sug_block(acc: List[List[str]], suppress: bool) -> Optional[str]:
            expanded = [""]
            for form_list in acc:
                expanded = [prefix + f for prefix in expanded for f in form_list]
            cleaned = [regex.sub(r" {2,}", " ", s) for s in expanded]
            if suppress:
                cleaned = [item for item in cleaned if SPELL_SUPPRESS_MARK not in item]
                if not cleaned:
                    return None
            else:
                cleaned = [item.replace(SPELL_SUPPRESS_MARK, "") for item in cleaned]
            return "</suggestion>, <suggestion>".join(cleaned)

        # Parse message template elements into chunks (outside suggestions vs inside suggestions)
        # to support Cartesian expansion matching Java LT formatMultipleSynthesis
        in_suggestion = False
        sug_accumulator: List[List[str]] = []
        message_chunks: List[str] = []

        for elem in template.elements:
            if isinstance(elem, str):
                if "<suggestion>" in elem:
                    # Flush any prior text before <suggestion>
                    before_sug, after_sug = elem.split("<suggestion>", 1)
                    if before_sug:
                        message_chunks.append(before_sug)
                    message_chunks.append("<suggestion>")
                    in_suggestion = True
                    if "</suggestion>" in after_sug:
                        inside, after_end = after_sug.split("</suggestion>", 1)
                        if inside:
                            sug_accumulator.append([inside])
                        sug_block = _build_sug_block(sug_accumulator, _suppresses(suggestion_index))
                        suggestion_index += 1
                        # Replace leading '<suggestion>' from message_chunks
                        if message_chunks and message_chunks[-1] == "<suggestion>":
                            message_chunks.pop()
                        if sug_block is not None:
                            message_chunks.append(f"<suggestion>{sug_block}</suggestion>")
                        in_suggestion = False
                        sug_accumulator = []
                        if after_end:
                            message_chunks.append(after_end)
                    elif after_sug:
                        sug_accumulator.append([after_sug])
                elif "</suggestion>" in elem:
                    inside, after_end = elem.split("</suggestion>", 1)
                    if inside:
                        sug_accumulator.append([inside])
                    sug_block = _build_sug_block(sug_accumulator, _suppresses(suggestion_index))
                    suggestion_index += 1
                    if message_chunks and message_chunks[-1] == "<suggestion>":
                        message_chunks.pop()
                    if sug_block is not None:
                        message_chunks.append(f"<suggestion>{sug_block}</suggestion>")
                    in_suggestion = False
                    sug_accumulator = []
                    if after_end:
                        message_chunks.append(after_end)
                else:
                    if in_suggestion:
                        sug_accumulator.append([elem])
                    else:
                        message_chunks.append(elem)
            elif isinstance(elem, MatchReference):
                forms = resolve_match_reference_forms(
                    ref=elem,
                    tokens=tokens,
                    token_positions=positions,
                    first_match_token=first_match_token,
                    element_lengths=element_lengths,
                    synthesizer=synthesizer,
                    check_spelling=in_suggestion and _suppresses(suggestion_index),
                )
                if in_suggestion:
                    sug_accumulator.append(forms)
                else:
                    message_chunks.append(forms[0] if forms else "")

        if in_suggestion and sug_accumulator:
            sug_block = _build_sug_block(sug_accumulator, _suppresses(suggestion_index))
            suggestion_index += 1
            if message_chunks and message_chunks[-1] == "<suggestion>":
                message_chunks.pop()
            if sug_block is not None:
                message_chunks.append(f"<suggestion>{sug_block}</suggestion>")

        # Pinned PatternRuleMatcher only deletes the PLEASE_SPELL_ME and MISTAKE
        # markers from the message; it never collapses the whitespace a removed
        # <suggestion> block leaves behind, so neither does this.
        return "".join(message_chunks)

    @staticmethod
    def format_suggestions_list(
        template: SuggestionTemplate,
        tokens: Sequence[AnalyzedTokenReadings],
        token_positions: Optional[Any] = None,
        first_match_token: int = 0,
        error_tokens: Optional[Sequence[AnalyzedTokenReadings]] = None,
        element_lengths: Optional[Sequence[int]] = None,
        synthesizer: Optional[RussianSynthesizer] = None,
    ) -> List[str]:
        """Format suggestion template into a list of candidate strings with Cartesian expansion."""
        if token_positions is not None and len(token_positions) > 0 and not isinstance(token_positions[0], int):
            error_tokens = token_positions
            positions = [1] * len(tokens)
        elif token_positions is not None:
            positions = list(token_positions)
        else:
            positions = [1] * len(tokens)

        accum: List[List[str]] = []
        for elem in template.elements:
            if isinstance(elem, str):
                accum.append([elem])
            elif isinstance(elem, MatchReference):
                forms = resolve_match_reference_forms(
                    ref=elem,
                    tokens=tokens,
                    token_positions=positions,
                    first_match_token=first_match_token,
                    element_lengths=element_lengths,
                    synthesizer=synthesizer,
                )
                accum.append(forms)

        expanded = [""]
        for form_list in accum:
            expanded = [prefix + f for prefix in expanded for f in form_list]
        cleaned = [regex.sub(r" {2,}", " ", s) for s in expanded]

        is_first_match_upper = False
        if error_tokens and error_tokens[0].token:
            is_first_match_upper = error_tokens[0].token[0].isupper()
        elif 0 <= first_match_token < len(tokens):
            first_tok = tokens[first_match_token].token or ""
            if first_tok and first_tok[0].isupper():
                is_first_match_upper = True

        if is_first_match_upper:
            cleaned = [uppercase_first_char(s) for s in cleaned]

        return cleaned

    @staticmethod
    def format_suggestion(
        template: SuggestionTemplate,
        tokens: Sequence[AnalyzedTokenReadings],
        token_positions: Optional[Any] = None,
        first_match_token: int = 0,
        error_tokens: Optional[Sequence[AnalyzedTokenReadings]] = None,
        element_lengths: Optional[Sequence[int]] = None,
        synthesizer: Optional[RussianSynthesizer] = None,
    ) -> str:
        """Format suggestion replacement string."""
        res_list = TemplateFormatter.format_suggestions_list(
            template=template,
            tokens=tokens,
            token_positions=token_positions,
            first_match_token=first_match_token,
            error_tokens=error_tokens,
            element_lengths=element_lengths,
            synthesizer=synthesizer,
        )
        return res_list[0] if res_list else ""
