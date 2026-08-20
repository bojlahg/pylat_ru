"""src/pylat_ru/grammar/unification.py

Native Python implementation of LanguageTool feature unification engine.
Faithfully reproduces Unifier, UnifierConfiguration, and EquivalenceTypeLocator
semantics from pinned Java LanguageTool v6.8.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from pylat_ru.analysis import AnalyzedToken, AnalyzedTokenReadings


@dataclass(frozen=True)
class EquivalenceTypeLocator:
    """Composite key identifying a feature and equivalence type."""

    feature: str
    type: str

    def __repr__(self) -> str:
        return f"EquivalenceTypeLocator(feature={self.feature!r}, type={self.type!r})"


class UnifierConfiguration:
    """Immutable configuration storing global and category-level feature equivalences.

    Matches Java UnifierConfiguration first-definition-wins policy for duplicate
    (feature, type) pairs.
    """

    def __init__(self) -> None:
        self._equivalence_types: Dict[EquivalenceTypeLocator, Any] = {}
        self._equivalence_features: Dict[str, List[str]] = {}

    @property
    def equivalence_types(self) -> Dict[EquivalenceTypeLocator, Any]:
        """Read-only view of equivalence types mapping locator to compiled PatternToken predicate."""
        return dict(self._equivalence_types)

    @property
    def equivalence_features(self) -> Dict[str, List[str]]:
        """Read-only view of configured feature types mapping feature ID to list of type names."""
        return {k: list(v) for k, v in self._equivalence_features.items()}

    def set_equivalence(self, feature: str, type_name: str, elem: Any) -> None:
        """Register an equivalence type predicate. First definition wins."""
        locator = EquivalenceTypeLocator(feature, type_name)
        if locator in self._equivalence_types:
            return

        self._equivalence_types[locator] = elem
        if feature not in self._equivalence_features:
            self._equivalence_features[feature] = []
        self._equivalence_features[feature].append(type_name)

    def create_unifier(self) -> Unifier:
        """Create a fresh Unifier instance with this configuration."""
        return Unifier(
            equivalence_types=self._equivalence_types,
            equivalence_features=self._equivalence_features,
        )

    # Upstream Java alias
    createUnifier = create_unifier


class Unifier:
    """Per-match-attempt unifier state tracking feature agreement across tokens."""

    UNIFY_IGNORE: str = "unify-ignore"

    def __init__(
        self,
        equivalence_types: Dict[EquivalenceTypeLocator, Any],
        equivalence_features: Dict[str, List[str]],
    ) -> None:
        self.equivalence_types = dict(equivalence_types)
        self.equivalence_features = {k: list(v) for k, v in equivalence_features.items()}

        self.tok_sequence: List[AnalyzedTokenReadings] = []
        self.tok_sequence_equivalences: List[List[Dict[str, Set[str]]]] = []
        self.equivalences_matched: List[Dict[str, Set[str]]] = []

        self.all_feats_in: bool = False
        self.tok_cnt: int = 0
        self.readings_counter: int = 1

        self.features_found: List[bool] = []
        self.tmp_features_found: List[bool] = []
        self.equivalences_to_be_kept: Dict[str, Set[str]] = {}
        self.unification_feats: Optional[Dict[str, List[str]]] = None

        self.in_unification: bool = False
        self.uni_matched: bool = False
        self.uni_all_matched: bool = False

    def reset(self) -> None:
        """Reset unifier state after matching candidate or unify block."""
        self.equivalences_matched.clear()
        self.all_feats_in = False
        self.tok_cnt = 0
        self.features_found.clear()
        self.tmp_features_found.clear()
        self.tok_sequence.clear()
        self.tok_sequence_equivalences.clear()
        self.readings_counter = 1
        self.uni_matched = False
        self.uni_all_matched = False
        self.in_unification = False
        self.equivalences_to_be_kept.clear()
        self.unification_feats = None

    def is_satisfied(
        self,
        a_token: AnalyzedToken,
        u_features: Dict[str, List[str]],
        orig_atr: Optional[AnalyzedTokenReadings] = None,
    ) -> bool:
        """Check whether token satisfies feature definitions."""
        if self.all_feats_in and not self.equivalences_matched:
            return False
        if u_features is None:
            raise RuntimeError("isSatisfied called without features being set")

        self.unification_feats = u_features
        if self.all_feats_in:
            return self._check_next(a_token, u_features, orig_atr=orig_atr)
        else:
            unified = True
            token_equiv_map: Dict[str, Set[str]] = {}

            for feat_key, types in u_features.items():
                if not types:
                    types = self.equivalence_features.get(feat_key, [])
                for type_name in types:
                    test_elem = self.equivalence_types.get(EquivalenceTypeLocator(feat_key, type_name))
                    if test_elem is None:
                        return False
                    if test_elem.matches_reading(a_token, AnalyzedTokenReadings(a_token, 0)):
                        token_equiv_map.setdefault(feat_key, set()).add(type_name)

                unified = feat_key in token_equiv_map
                if not unified:
                    break

            if unified:
                if self.tok_cnt == 0 or len(self.tok_sequence) == 0:
                    if orig_atr is not None:
                        new_atr = AnalyzedTokenReadings(
                            readings=[a_token],
                            start_pos=orig_atr.start_pos,
                            chunk_tags=list(orig_atr.chunk_tags),
                            is_sentence_start=orig_atr.is_sentence_start,
                            is_sentence_end=orig_atr.is_sentence_end,
                            is_paragraph_end=orig_atr.is_paragraph_end,
                            is_immunized=orig_atr.is_immunized,
                            is_ignore_spelling=orig_atr.is_ignore_spelling,
                            whitespace_before=orig_atr.whitespace_before,
                            pos_fix=orig_atr.pos_fix,
                        )
                        self.tok_sequence.append(new_atr)
                    else:
                        self.tok_sequence.append(AnalyzedTokenReadings(a_token, 0))
                    self.tok_sequence_equivalences.append([token_equiv_map])
                else:
                    self.tok_sequence[0].add_reading(a_token)
                    self.tok_sequence_equivalences[0].append(token_equiv_map)
                self.equivalences_matched.append(token_equiv_map)
                self.tok_cnt += 1

            return unified

    def _check_next(
        self,
        a_token: AnalyzedToken,
        u_features: Dict[str, List[str]],
        orig_atr: Optional[AnalyzedTokenReadings] = None,
    ) -> bool:
        """Check compatibility of next token against interpretations from token 0."""
        any_feat_unified = False
        token_features_found = list(self.tmp_features_found)
        equivalences_matched_here: Dict[str, Set[str]] = {}

        if self.all_feats_in:
            for i in range(self.tok_cnt):
                all_feats_unified = True
                for feat_key, types in u_features.items():
                    feat_unified = False
                    if not types:
                        types = self.equivalence_features.get(feat_key, [])
                    for type_name in types:
                        matched_set = self.equivalences_matched[i].get(feat_key)
                        if matched_set is not None and type_name in matched_set:
                            test_elem = self.equivalence_types.get(EquivalenceTypeLocator(feat_key, type_name))
                            if test_elem is not None:
                                matched = test_elem.matches_reading(a_token, AnalyzedTokenReadings(a_token, 0))
                                feat_unified = feat_unified or matched
                                if matched:
                                    self.equivalences_to_be_kept.setdefault(feat_key, set()).add(type_name)
                                    equivalences_matched_here.setdefault(feat_key, set()).add(type_name)

                    all_feats_unified = all_feats_unified and feat_unified

                if i < len(token_features_found):
                    token_features_found[i] = token_features_found[i] or all_feats_unified
                any_feat_unified = any_feat_unified or all_feats_unified

            if any_feat_unified:
                equiv_copy = {k: set(v) for k, v in equivalences_matched_here.items()}
                if len(self.tok_sequence) == self.readings_counter:
                    if orig_atr is not None:
                        new_atr = AnalyzedTokenReadings(
                            readings=[a_token],
                            start_pos=orig_atr.start_pos,
                            chunk_tags=list(orig_atr.chunk_tags),
                            is_sentence_start=orig_atr.is_sentence_start,
                            is_sentence_end=orig_atr.is_sentence_end,
                            is_paragraph_end=orig_atr.is_paragraph_end,
                            is_immunized=orig_atr.is_immunized,
                            is_ignore_spelling=orig_atr.is_ignore_spelling,
                            whitespace_before=orig_atr.whitespace_before,
                            pos_fix=orig_atr.pos_fix,
                        )
                        self.tok_sequence.append(new_atr)
                    else:
                        self.tok_sequence.append(AnalyzedTokenReadings(a_token, 0))
                    self.tok_sequence_equivalences.append([equiv_copy])
                else:
                    if self.readings_counter < len(self.tok_sequence):
                        self.tok_sequence[self.readings_counter].add_reading(a_token)
                        self.tok_sequence_equivalences[self.readings_counter].append(equiv_copy)
                    else:
                        any_feat_unified = False

                self.tmp_features_found = token_features_found

        return any_feat_unified

    def start_next_token(self) -> None:
        """Advance to next token in sequence and intersect surviving equivalences."""
        self.features_found = list(self.tmp_features_found)
        self.readings_counter += 1

        for j in range(len(self.tok_sequence)):
            for i in range(len(self.tok_sequence_equivalences[j])):
                for feat_key in self.equivalence_features:
                    if feat_key != self.UNIFY_IGNORE:
                        if feat_key in self.tok_sequence_equivalences[j][i]:
                            if feat_key in self.equivalences_to_be_kept:
                                self.tok_sequence_equivalences[j][i][feat_key].intersection_update(
                                    self.equivalences_to_be_kept[feat_key]
                                )
                            else:
                                self.tok_sequence_equivalences[j][i].pop(feat_key, None)
                        else:
                            self.tok_sequence_equivalences[j][i].pop(feat_key, None)

        self.equivalences_to_be_kept.clear()

    def start_unify(self) -> None:
        """Start testing subsequent tokens against the interpretations found in token 0."""
        self.all_feats_in = True
        self.features_found = [False] * self.tok_cnt
        self.tmp_features_found = list(self.features_found)

    def get_final_unification_value(self, u_features: Dict[str, List[str]]) -> bool:
        """Check if all tokens in sequence have at least one interpretation sharing all required features."""
        tok_unified = 0
        feats_to_check = self.unification_feats if self.unification_feats is not None else u_features

        for j in range(len(self.tok_sequence)):
            unified_tokens_found = False
            for i in range(len(self.tok_sequence_equivalences[j])):
                if self.UNIFY_IGNORE in self.tok_sequence_equivalences[j][i]:
                    if i == 0:
                        tok_unified += 1
                    unified_tokens_found = True
                    continue
                else:
                    feat_unified = 0
                    for feat_key in u_features:
                        s = self.tok_sequence_equivalences[j][i].get(feat_key)
                        if s is not None and len(s) == 0:
                            feat_unified = 0
                        else:
                            feat_unified += 1

                        if feat_unified == len(feats_to_check) and tok_unified <= j:
                            tok_unified += 1
                            unified_tokens_found = True
                            break

            if not unified_tokens_found:
                return False

        return tok_unified == len(self.tok_sequence)

    def is_unified(
        self,
        match_token: AnalyzedToken,
        u_features: Dict[str, List[str]],
        last_reading: bool,
        is_matched: bool = True,
        orig_atr: Optional[AnalyzedTokenReadings] = None,
    ) -> bool:
        """Main lifecycle entry point testing whether sequence of tokens shares features."""
        if self.in_unification:
            if is_matched:
                self.uni_matched |= self.is_satisfied(match_token, u_features, orig_atr=orig_atr)
            self.uni_all_matched = self.uni_matched

            if last_reading:
                self.start_next_token()
                self.uni_matched = False

            return self.uni_all_matched and self.get_final_unification_value(u_features)
        else:
            if is_matched:
                self.is_satisfied(match_token, u_features, orig_atr=orig_atr)

        if last_reading:
            self.in_unification = True
            self.uni_matched = False
            self.start_unify()

        return True

    def add_neutral_element(self, analyzed_token_readings: AnalyzedTokenReadings) -> None:
        """Add neutral element (<unify-ignore>) that participates in pattern but does not constrain unification."""
        self.tok_sequence.append(analyzed_token_readings)
        num_readings = len(analyzed_token_readings.readings) if analyzed_token_readings.readings else 1
        tok_equivs: List[Dict[str, Set[str]]] = []
        for _ in range(num_readings):
            tok_equivs.append({self.UNIFY_IGNORE: set()})
        self.tok_sequence_equivalences.append(tok_equivs)
        self.readings_counter += 1

    def get_unified_tokens(self) -> Optional[List[AnalyzedTokenReadings]]:
        """Get sequence of filtered AnalyzedTokenReadings containing only compatible readings."""
        if not self.tok_sequence:
            return None

        u_tokens: List[AnalyzedTokenReadings] = []
        feats_to_check = self.unification_feats if self.unification_feats is not None else {}

        for j in range(len(self.tok_sequence)):
            unified_tokens_found = False
            orig_atr = self.tok_sequence[j]

            for i in range(len(self.tok_sequence_equivalences[j])):
                equiv_map = self.tok_sequence_equivalences[j][i]
                if self.UNIFY_IGNORE in equiv_map:
                    at = orig_atr.readings[i] if (orig_atr.readings and i < len(orig_atr.readings)) else AnalyzedToken(orig_atr.token)
                    self._add_token_to_sequence(u_tokens, at, j, orig_atr)
                    unified_tokens_found = True
                else:
                    feat_unified = 0
                    for feat_key in feats_to_check:
                        s = equiv_map.get(feat_key)
                        if s is not None and len(s) == 0:
                            feat_unified = 0
                        else:
                            feat_unified += 1

                    if feat_unified == len(feats_to_check):
                        at = orig_atr.readings[i] if (orig_atr.readings and i < len(orig_atr.readings)) else AnalyzedToken(orig_atr.token)
                        self._add_token_to_sequence(u_tokens, at, j, orig_atr)
                        unified_tokens_found = True

            if not unified_tokens_found:
                return None

        return u_tokens

    def _add_token_to_sequence(
        self,
        token_sequence: List[AnalyzedTokenReadings],
        token: AnalyzedToken,
        pos: int,
        orig_atr: Optional[AnalyzedTokenReadings] = None,
    ) -> None:
        if len(token_sequence) <= pos or not token_sequence:
            if orig_atr is not None:
                tmp_atr = AnalyzedTokenReadings(
                    readings=[token],
                    start_pos=orig_atr.start_pos,
                    chunk_tags=list(orig_atr.chunk_tags),
                    is_sentence_start=orig_atr.is_sentence_start,
                    is_sentence_end=orig_atr.is_sentence_end,
                    is_paragraph_end=orig_atr.is_paragraph_end,
                    is_immunized=orig_atr.is_immunized,
                    is_ignore_spelling=orig_atr.is_ignore_spelling,
                    whitespace_before=orig_atr.whitespace_before,
                    pos_fix=orig_atr.pos_fix,
                    clean_token=orig_atr.clean_token,
                    source_token=orig_atr.source_token,
                )
            else:
                tmp_atr = AnalyzedTokenReadings(token, 0)
            token_sequence.append(tmp_atr)
        else:
            token_sequence[pos].add_reading(token)

    def get_final_unified(self) -> Optional[List[AnalyzedTokenReadings]]:
        """Get final filtered tokens if currently in unification."""
        if self.in_unification:
            return self.get_unified_tokens()
        return None

    # Upstream Java method aliases
    isSatisfied = is_satisfied
    startUnify = start_unify
    startNextToken = start_next_token
    getFinalUnificationValue = get_final_unification_value
    getUnifiedTokens = get_unified_tokens
    getFinalUnified = get_final_unified
    addNeutralElement = add_neutral_element
    isUnified = is_unified
