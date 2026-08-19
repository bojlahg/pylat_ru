"""Unit tests for pattern matcher backtracking and complex pattern constructs."""

from __future__ import annotations

import pytest

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.disambiguation.pattern_matcher import (
    PatternRuleMatcher,
    PatternToken,
    PatternTokenException,
)


def test_and_conjunction_multi_reading_matching():
    """Verify <and> matches a token that simultaneously has readings satisfying all child conditions."""
    # Create a token with two distinct readings: Noun Nominative and Verb
    r_noun = AnalyzedToken(token="стали", lemma="сталь", pos_tag="NN:Inan:Fem:Gen")
    r_verb = AnalyzedToken(token="стали", lemma="стать", pos_tag="VB:Perf:Past:Pl")
    tok_atr = AnalyzedTokenReadings(readings=[r_noun, r_verb], start_pos=0)

    # Sub-tokens for <and>
    p_noun = PatternToken(postag=r"^NN:.*", is_postag_regex=True)
    p_verb = PatternToken(postag=r"^VB:.*", is_postag_regex=True)
    and_pattern_tok = PatternToken(and_tokens=[p_noun, p_verb])

    assert and_pattern_tok.matches_token(tok_atr) is True

    # If we require adjective as well (which is absent), <and> must fail
    p_adj = PatternToken(postag=r"^ADJ:.*", is_postag_regex=True)
    and_pattern_tok_with_adj = PatternToken(and_tokens=[p_noun, p_verb, p_adj])
    assert and_pattern_tok_with_adj.matches_token(tok_atr) is False


def test_skip_backtracking_finds_valid_continuation():
    """Verify backtracking explores alternative matches when a candidate token fails downstream."""
    # Sequence: [A1, A2, B]
    # Pattern: [A with skip=1, B]
    # First A (A1) can match token 0. If token 1 is also A (A2), and token 2 is B:
    # A1 -> skips 1 (token 1: A2) -> token 2: B => matches!
    tok_a1 = AnalyzedTokenReadings([AnalyzedToken(token="A", pos_tag="TAG_A")], start_pos=0)
    tok_a2 = AnalyzedTokenReadings([AnalyzedToken(token="A", pos_tag="TAG_A")], start_pos=2)
    tok_b = AnalyzedTokenReadings([AnalyzedToken(token="B", pos_tag="TAG_B")], start_pos=4)

    sent = AnalyzedSentence(tokens=[tok_a1, tok_a2, tok_b])

    p_a = PatternToken(string="A", skip=1)
    p_b = PatternToken(string="B")

    matcher = PatternRuleMatcher([p_a, p_b])
    matches = matcher.find_matches(sent)

    assert len(matches) >= 1
    # Matches starting at index 0 and at index 1
    first_match = matches[0]
    assert first_match.first_match_token == 0
    assert first_match.last_match_token == 2


def test_scope_next_exception():
    """Verify exception with scope='next' suppresses match when following token matches exception."""
    tok1 = AnalyzedTokenReadings([AnalyzedToken(token="в", pos_tag="PREP")], start_pos=0)
    tok2 = AnalyzedTokenReadings([AnalyzedToken(token="том", pos_tag="PRON")], start_pos=2)
    tok3 = AnalyzedTokenReadings([AnalyzedToken(token="числе", pos_tag="NN")], start_pos=6)

    sent = AnalyzedSentence(tokens=[tok1, tok2, tok3])

    # Pattern for "в" with scope="next" exception on "том"
    exc_next = PatternTokenException(string="том", scope="next")
    p1 = PatternToken(string="в", exceptions=[exc_next])
    p2 = PatternToken(string="том")

    matcher = PatternRuleMatcher([p1, p2])
    matches = matcher.find_matches(sent)

    # Since tok2 is "том", the scope="next" exception suppresses the match
    assert len(matches) == 0
