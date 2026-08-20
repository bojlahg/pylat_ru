"""tests/upstream/test_unifier_oracle_parity.py

Direct faithful Python translation of upstream LanguageTool UnifierTest.java.
Executes all 7 test methods testing single features, multiple features, blank type lookups,
multiple readings, sequence filtering, negation, and neutral elements.
"""

from typing import Dict, List, Optional
import pytest

from pylat_ru.analysis import AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.grammar.matcher import CompiledPatternToken
from pylat_ru.grammar.model import PatternToken
from pylat_ru.grammar.unification import (
    EquivalenceTypeLocator,
    Unifier,
    UnifierConfiguration,
)


def _make_token(token: str, pos_tag: str, lemma: str = "") -> AnalyzedToken:
    return AnalyzedToken(token=token, lemma=lemma or token, pos_tag=pos_tag)


def _prepare_pos_element(pos_string: str) -> CompiledPatternToken:
    p_token = PatternToken(postag=pos_string, postag_regexp=True)
    return CompiledPatternToken(p_token)


def _prepare_text_element(text_regex: str) -> CompiledPatternToken:
    p_token = PatternToken(text=text_regex, regexp=True, case_sensitive=True)
    return CompiledPatternToken(p_token)


def _format_unified_tokens(tokens: Optional[List[AnalyzedTokenReadings]]) -> str:
    """Format unified AnalyzedTokenReadings sequence to match Java toString()."""
    if tokens is None:
        return "null"
    parts = []
    for atr in tokens:
        readings_str = ",".join(
            f"{r.lemma}/{r.pos_tag}*" for r in atr.readings
        )
        parts.append(f"{atr.token}[{readings_str}]")
    return "[" + ", ".join(parts) + "]"


def test_unification_case():
    """Test character case unification directly ported from UnifierTest.testUnificationCase()."""
    unifier_config = UnifierConfiguration()
    el_lower = _prepare_text_element(r"\p{Ll}+")
    el_upper = _prepare_text_element(r"\p{Lu}\p{Ll}+")
    el_all_upper = _prepare_text_element(r"\p{Lu}+$")

    unifier_config.set_equivalence("case-sensitivity", "lowercase", el_lower)
    unifier_config.set_equivalence("case-sensitivity", "uppercase", el_upper)
    unifier_config.set_equivalence("case-sensitivity", "alluppercase", el_all_upper)

    lower1 = _make_token("lower", "JJR", "lower")
    lower2 = _make_token("lowercase", "JJ", "lowercase")
    upper1 = _make_token("Uppercase", "JJ", "Uppercase")
    upper2 = _make_token("John", "NNP", "John")
    upper_all1 = _make_token("JOHN", "NNP", "John")
    upper_all2 = _make_token("JAMES", "NNP", "James")

    uni = unifier_config.createUnifier()

    equiv: Dict[str, Optional[List[str]]] = {"case-sensitivity": ["lowercase"]}

    satisfied = uni.is_satisfied(lower1, equiv)
    satisfied &= uni.is_satisfied(lower2, equiv)
    uni.start_unify()
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is True
    uni.reset()

    satisfied = uni.is_satisfied(upper2, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(lower2, equiv)
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is False
    uni.reset()

    satisfied = uni.is_satisfied(upper1, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(lower1, equiv)
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is False
    uni.reset()

    satisfied = uni.is_satisfied(upper2, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(upper1, equiv)
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is False
    uni.reset()

    equiv = {"case-sensitivity": ["uppercase"]}
    satisfied = uni.is_satisfied(upper2, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(upper1, equiv)
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is True
    uni.reset()

    equiv = {"case-sensitivity": ["alluppercase"]}
    satisfied = uni.is_satisfied(upper2, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(upper1, equiv)
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is False
    uni.reset()

    satisfied = uni.is_satisfied(upper_all2, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(upper_all1, equiv)
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is True


def test_unification_number():
    """Test grammatical number unification ported from UnifierTest.testUnificationNumber()."""
    unifier_config = UnifierConfiguration()
    unifier_config.set_equivalence("number", "singular", _prepare_pos_element(r".*[\.:]sg:.*"))
    unifier_config.set_equivalence("number", "plural", _prepare_pos_element(r".*[\.:]pl:.*"))

    uni = unifier_config.createUnifier()

    sing1 = _make_token("mały", "adj:sg:blahblah", "mały")
    sing2 = _make_token("człowiek", "subst:sg:blahblah", "człowiek")

    equiv: Dict[str, Optional[List[str]]] = {"number": ["singular"]}

    satisfied = uni.is_satisfied(sing1, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(sing2, equiv)
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is True
    uni.reset()

    # for multiple readings - OR for interpretations, AND for tokens
    sing1a = _make_token("mały", "adj:pl:blahblah", "mały")
    satisfied = uni.is_satisfied(sing1, equiv)
    satisfied |= uni.is_satisfied(sing1a, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(sing2, equiv)
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is True
    uni.reset()

    # check if any of the equivalences is there
    equiv = {"number": ["singular", "plural"]}
    sing1a = _make_token("mały", "adj:pl:blahblah", "mały")
    satisfied = uni.is_satisfied(sing1, equiv)
    satisfied |= uni.is_satisfied(sing1a, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(sing2, equiv)
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is True
    uni.reset()

    # test all possible feature equivalences by leaving type blank (None)
    sing1a = _make_token("mały", "adj:pl:blahblah", "mały")
    equiv = {"number": None}
    satisfied = uni.is_satisfied(sing1, equiv)
    satisfied |= uni.is_satisfied(sing1a, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(sing2, equiv)
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is True
    uni.reset()

    # test non-agreeing tokens with blank types
    satisfied = uni.is_satisfied(sing1a, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(sing2, equiv)
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is False
    uni.reset()


def test_unification_number_gender():
    """Test number & gender unification ported from UnifierTest.testUnificationNumberGender()."""
    unifier_config = UnifierConfiguration()
    unifier_config.set_equivalence("number", "singular", _prepare_pos_element(r".*[\.:]sg:.*"))
    unifier_config.set_equivalence("number", "plural", _prepare_pos_element(r".*[\.:]pl:.*"))
    unifier_config.set_equivalence("gender", "feminine", _prepare_pos_element(r".*[\.:]f"))
    unifier_config.set_equivalence("gender", "masculine", _prepare_pos_element(r".*[\.:]m"))

    uni = unifier_config.createUnifier()

    sing1 = _make_token("mały", "adj:sg:blahblah:m", "mały")
    sing1a = _make_token("mała", "adj:sg:blahblah:f", "mały")
    sing1b = _make_token("małe", "adj:pl:blahblah:m", "mały")
    sing2 = _make_token("człowiek", "subst:sg:blahblah:m", "człowiek")

    equiv = {"number": None, "gender": None}

    satisfied = uni.is_satisfied(sing1, equiv)
    satisfied |= uni.is_satisfied(sing1a, equiv)
    satisfied |= uni.is_satisfied(sing1b, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(sing2, equiv)
    uni.start_next_token()
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is True
    assert _format_unified_tokens(uni.get_unified_tokens()) == (
        "[mały[mały/adj:sg:blahblah:m*], człowiek[człowiek/subst:sg:blahblah:m*]]"
    )
    uni.reset()


def test_multiple_feats():
    """Test multiple features unification ported from UnifierTest.testMultipleFeats()."""
    unifier_config = UnifierConfiguration()
    unifier_config.set_equivalence("number", "singular", _prepare_pos_element(r".*[\.:]sg:.*"))
    unifier_config.set_equivalence("number", "plural", _prepare_pos_element(r".*[\.:]pl:.*"))
    unifier_config.set_equivalence("gender", "feminine", _prepare_pos_element(r".*[\.:]f([\.:].*)?"))
    unifier_config.set_equivalence("gender", "masculine", _prepare_pos_element(r".*[\.:]m([\.:].*)?"))
    unifier_config.set_equivalence("gender", "neutral", _prepare_pos_element(r".*[\.:]n([\.:].*)?"))

    uni = unifier_config.createUnifier()

    sing1 = _make_token("mały", "adj:sg:blahblah:m", "mały")
    sing1a = _make_token("mały", "adj:pl:blahblah:f", "mały")
    sing1b = _make_token("mały", "adj:pl:blahblah:f", "mały")
    sing2 = _make_token("zgarbiony", "adj:pl:blahblah:f", "zgarbiony")
    sing3 = _make_token("człowiek", "subst:sg:blahblah:m", "człowiek")

    equiv = {"number": None, "gender": None}

    satisfied = uni.is_satisfied(sing1, equiv)
    satisfied |= uni.is_satisfied(sing1a, equiv)
    satisfied |= uni.is_satisfied(sing1b, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(sing2, equiv)
    uni.start_next_token()
    satisfied &= uni.is_satisfied(sing3, equiv)
    uni.start_next_token()
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is False
    uni.reset()

    # simplified interface
    uni.is_unified(sing1, equiv, False)
    uni.is_unified(sing1a, equiv, False)
    uni.is_unified(sing1b, equiv, True)
    uni.is_unified(sing2, equiv, True)
    assert uni.is_unified(sing3, equiv, True) is False
    uni.reset()

    sing1a = _make_token("osobiste", "adj:pl:nom.acc.voc:f.n.m2.m3:pos:aff", "osobisty")
    sing1b = _make_token("osobiste", "adj:sg:nom.acc.voc:n:pos:aff", "osobisty")
    sing2 = _make_token("godło", "subst:sg:nom.acc.voc:n", "godło")

    uni.is_unified(sing1a, equiv, False)
    uni.is_unified(sing1b, equiv, True)
    assert uni.is_unified(sing2, equiv, True) is True
    assert _format_unified_tokens(uni.get_final_unified()) == (
        "[osobiste[osobisty/adj:sg:nom.acc.voc:n:pos:aff*], godło[godło/subst:sg:nom.acc.voc:n*]]"
    )
    uni.reset()

    # last reading doesn't match at all
    sing1a = _make_token("osobiste", "adj:pl:nom.acc.voc:f.n.m2.m3:pos:aff", "osobisty")
    sing1b = _make_token("osobiste", "adj:sg:nom.acc.voc:n:pos:aff", "osobisty")
    sing2a = _make_token("godło", "subst:sg:nom.acc.voc:n", "godło")
    sing2b = _make_token("godło", "indecl", "godło")

    uni.is_unified(sing1a, equiv, False)
    uni.is_unified(sing1b, equiv, True)
    uni.is_unified(sing2a, equiv, False)
    assert uni.is_unified(sing2b, equiv, True) is True
    assert _format_unified_tokens(uni.get_final_unified()) == (
        "[osobiste[osobisty/adj:sg:nom.acc.voc:n:pos:aff*], godło[godło/subst:sg:nom.acc.voc:n*]]"
    )
    uni.reset()

    # check if two features are left out correctly (both match)
    plur1 = _make_token("zgarbieni", "adj:pl:foobar:m", "zgarbiony")
    plur2 = _make_token("zgarbieni", "adj:pl:blabla:m", "zgarbiony")
    plur3 = _make_token("ludzie", "subst:pl:blabla:m", "człowiek")
    plur4 = _make_token("ludzie", "subst:pl:pampam:m", "człowiek")

    uni.is_unified(plur1, equiv, False)
    uni.is_unified(plur2, equiv, True)
    uni.is_unified(plur3, equiv, False)
    assert uni.is_unified(plur4, equiv, True) is True
    assert _format_unified_tokens(uni.get_final_unified()) == (
        "[zgarbieni[zgarbiony/adj:pl:foobar:m*,zgarbiony/adj:pl:blabla:m*], "
        "ludzie[człowiek/subst:pl:blabla:m*,człowiek/subst:pl:pampam:m*]]"
    )
    uni.reset()

    # sequence of many tokens
    case1a = _make_token("xx", "abc:sg:f", "xx")
    case1b = _make_token("xx", "cde:pl:f", "xx")

    case2a = _make_token("yy", "abc:pl:f", "yy")
    case2b = _make_token("yy", "cde:as:f", "yy")
    case2c = _make_token("yy", "cde:pl:c", "yy")
    case2d = _make_token("yy", "abc:sg:f", "yy")
    case2e = _make_token("yy", "efg:aa:e", "yy")

    uni.is_unified(case1a, equiv, False)
    uni.is_unified(case1b, equiv, True)

    uni.is_unified(case2a, equiv, False)
    uni.is_unified(case2b, equiv, False)
    uni.is_unified(case2c, equiv, False)
    uni.is_unified(case2d, equiv, False)
    assert uni.is_unified(case2e, equiv, True) is True
    assert _format_unified_tokens(uni.get_final_unified()) == (
        "[xx[xx/abc:sg:f*,xx/cde:pl:f*], yy[yy/abc:pl:f*,yy/abc:sg:f*]]"
    )
    uni.reset()

    token_complex1_1 = _make_token("xx", "abc:sg:f", "xx1")
    token_complex1_2 = _make_token("xx", "cde:pl:f", "xx2")
    token_complex2_1 = _make_token("yy", "abc:sg:f", "yy1")
    token_complex2_2 = _make_token("yy", "cde:pl:f", "yy2")
    token_complex3 = _make_token("zz", "cde:sg:f", "zz")

    uni.is_unified(token_complex1_1, equiv, False)
    uni.is_unified(token_complex1_2, equiv, True)
    uni.is_unified(token_complex2_1, equiv, False)
    uni.is_unified(token_complex2_2, equiv, True)

    assert _format_unified_tokens(uni.get_final_unified()) == (
        "[xx[xx1/abc:sg:f*,xx2/cde:pl:f*], yy[yy1/abc:sg:f*,yy2/cde:pl:f*]]"
    )

    assert uni.is_unified(token_complex3, equiv, True) is True
    assert _format_unified_tokens(uni.get_final_unified()) == (
        "[xx[xx1/abc:sg:f*], yy[yy1/abc:sg:f*], zz[zz/cde:sg:f*]]"
    )


def test_multiple_feats_with_multiple_types():
    """Test multiple features with multi-predicate types from UnifierTest.testMultipleFeatsWithMultipleTypes()."""
    unifier_config = UnifierConfiguration()
    unifier_config.set_equivalence("number", "singular", _prepare_pos_element(r".*[\.:]sg:.*"))
    unifier_config.set_equivalence("number", "plural", _prepare_pos_element(r".*[\.:]pl:.*"))

    unifier_config.set_equivalence("gender", "feminine", _prepare_pos_element(r".*[\.:]f([\.:].*)?"))
    unifier_config.set_equivalence("gender", "masculine", _prepare_pos_element(r".*[\.:]m1([\.:].*)?"))
    unifier_config.set_equivalence("gender", "masculine", _prepare_pos_element(r".*[\.:]m2([\.:].*)?"))
    unifier_config.set_equivalence("gender", "masculine", _prepare_pos_element(r".*[\.:]m3([\.:].*)?"))
    unifier_config.set_equivalence("gender", "neutral1", _prepare_pos_element(r".*[\.:]n1(?:[\.:].*)?"))
    unifier_config.set_equivalence("gender", "neutral2", _prepare_pos_element(r".*[\.:]n2(?:[\.:].*)?"))

    unifier_config.set_equivalence("case", "nominativus", _prepare_pos_element(r".*[\.:]nom[\.:]?.*"))
    unifier_config.set_equivalence("case", "accusativus", _prepare_pos_element(r".*[\.:]acc[\.:]?.*"))
    unifier_config.set_equivalence("case", "dativus", _prepare_pos_element(r".*[\.:]dat[\.:]?.*"))
    unifier_config.set_equivalence("case", "vocativus", _prepare_pos_element(r".*[\.:]voc[\.:]?.*"))

    uni = unifier_config.createUnifier()

    sing1 = _make_token("niezgorsze", "adj:sg:acc:n1.n2:pos", "niezgorszy")
    sing1a = _make_token("niezgorsze", "adj:pl:acc:m2.m3.f.n1.n2.p2.p3:pos", "niezgorszy")
    sing1b = _make_token("niezgorsze", "adj:pl:nom.voc:m2.m3.f.n1.n2.p2.p3:pos", "niezgorszy")
    sing1c = _make_token("niezgorsze", "adj:sg:nom.voc:n1.n2:pos", "niezgorszy")
    sing2 = _make_token("lekarstwo", "subst:sg:acc:n2", "lekarstwo")
    sing2b = _make_token("lekarstwo", "subst:sg:nom:n2", "lekarstwo")
    sing2c = _make_token("lekarstwo", "subst:sg:voc:n2", "lekarstwo")

    equiv = {"number": None, "gender": None, "case": None}

    uni.is_unified(sing1, equiv, False)
    uni.is_unified(sing1a, equiv, False)
    uni.is_unified(sing1b, equiv, False)
    uni.is_unified(sing1c, equiv, True)
    uni.is_unified(sing2, equiv, False)
    uni.is_unified(sing2b, equiv, False)
    assert uni.is_unified(sing2c, equiv, True) is True
    assert _format_unified_tokens(uni.get_unified_tokens()) == (
        "[niezgorsze[niezgorszy/adj:sg:acc:n1.n2:pos*,niezgorszy/adj:sg:nom.voc:n1.n2:pos*], "
        "lekarstwo[lekarstwo/subst:sg:acc:n2*,lekarstwo/subst:sg:nom:n2*,lekarstwo/subst:sg:voc:n2*]]"
    )
    uni.reset()

    # different order
    uni.is_unified(sing1a, equiv, False)
    uni.is_unified(sing1, equiv, False)
    uni.is_unified(sing1c, equiv, False)
    uni.is_unified(sing1b, equiv, True)
    uni.is_unified(sing2b, equiv, False)
    uni.is_unified(sing2c, equiv, False)
    assert uni.is_unified(sing2, equiv, True) is True
    assert _format_unified_tokens(uni.get_unified_tokens()) == (
        "[niezgorsze[niezgorszy/adj:sg:acc:n1.n2:pos*,niezgorszy/adj:sg:nom.voc:n1.n2:pos*], "
        "lekarstwo[lekarstwo/subst:sg:nom:n2*,lekarstwo/subst:sg:voc:n2*,lekarstwo/subst:sg:acc:n2*]]"
    )
    uni.reset()


def test_negation():
    """Test unification negation ported directly from UnifierTest.testNegation()."""
    unifier_config = UnifierConfiguration()
    unifier_config.set_equivalence("number", "singular", _prepare_pos_element(r".*[\.:]sg:.*"))
    unifier_config.set_equivalence("number", "plural", _prepare_pos_element(r".*[\.:]pl:.*"))
    unifier_config.set_equivalence("gender", "feminine", _prepare_pos_element(r".*:f"))
    unifier_config.set_equivalence("gender", "masculine", _prepare_pos_element(r".*:m"))

    uni = unifier_config.createUnifier()

    sing_masc = _make_token("parvus", "adj:sg:blahblah:m", "parvus")
    plur_masc = _make_token("parvi", "adj:sg:blahblah:m", "parvus")
    plur_fem = _make_token("parvae", "adj:pl:blahblah:f", "parvus")
    sing_fem = _make_token("parva", "adj:sg:blahblah:f", "parvus")

    det_sing_fem = _make_token("una", "det:sg:blahblah:f", "unus")
    det_plur_fem = _make_token("unae", "det:pl:blahblah:f", "unus")
    det_sing_masc = _make_token("unus", "det:sg:blahblah:m", "unus")
    det_plur_masc = _make_token("uni", "det:sg:blahblah:m", "unus")

    subst_sing_fem = _make_token("discrepatio", "subst:sg:blahblah:f", "discrepatio")
    subst_plur_fem = _make_token("discrepationes", "subst:sg:blahblah:f", "discrepatio")
    subst_sing_masc = _make_token("homo", "sg:sg:blahblah:m", "homo")
    subst_plur_masc = _make_token("homines", "sg:sg:blahblah:m", "homo")

    equiv = {"number": None, "gender": None}

    satisfied = uni.is_satisfied(det_sing_masc, equiv)
    uni.start_unify()
    satisfied &= uni.is_satisfied(sing_masc, equiv)
    uni.start_next_token()
    satisfied &= uni.is_satisfied(subst_sing_masc, equiv)
    uni.start_next_token()
    satisfied &= uni.get_final_unification_value(equiv)
    assert satisfied is True
    uni.reset()

    uni.is_unified(det_sing_masc, equiv, True)
    uni.is_unified(sing_masc, equiv, True)
    assert uni.is_unified(subst_sing_masc, equiv, True) is True
    uni.reset()

    # test negation
    uni.is_unified(det_sing_masc, equiv, True)
    uni.is_unified(sing_masc, equiv, True)
    assert (not uni.is_unified(subst_sing_masc, equiv, True)) is False
    uni.reset()

    uni.is_unified(det_sing_fem, equiv, True)
    uni.is_unified(sing_masc, equiv, True)
    assert (not uni.is_unified(subst_sing_masc, equiv, True)) is True
    uni.reset()

    uni.is_unified(det_sing_masc, equiv, True)
    uni.is_unified(sing_fem, equiv, True)
    assert (not uni.is_unified(subst_sing_masc, equiv, True)) is True
    uni.reset()

    uni.is_unified(det_sing_masc, equiv, True)
    uni.is_unified(sing_masc, equiv, True)
    assert (not uni.is_unified(subst_sing_fem, equiv, True)) is True
    uni.reset()

    uni.is_unified(det_sing_masc, equiv, True)
    uni.is_unified(plur_masc, equiv, True)
    assert (not uni.is_unified(subst_sing_fem, equiv, True)) is True
    uni.reset()

    uni.is_unified(det_sing_masc, equiv, True)
    uni.is_unified(plur_fem, equiv, True)
    assert (not uni.is_unified(subst_sing_fem, equiv, True)) is True
    uni.reset()

    uni.is_unified(det_plur_fem, equiv, True)
    uni.is_unified(plur_fem, equiv, True)
    assert (not uni.is_unified(subst_sing_fem, equiv, True)) is True
    uni.reset()

    uni.is_unified(det_sing_fem, equiv, True)
    uni.is_unified(plur_fem, equiv, True)
    assert (not uni.is_unified(subst_plur_fem, equiv, True)) is True
    uni.reset()

    uni.is_unified(det_sing_fem, equiv, True)
    uni.is_unified(plur_fem, equiv, True)
    assert (not uni.is_unified(subst_plur_masc, equiv, True)) is True
    uni.reset()

    uni.is_unified(det_plur_masc, equiv, True)
    uni.is_unified(plur_fem, equiv, True)
    assert (not uni.is_unified(subst_plur_masc, equiv, True)) is True
    uni.reset()


def test_add_neutral_element():
    """Test neutral elements (<unify-ignore>) from UnifierTest.testAddNeutralElement()."""
    unifier_config = UnifierConfiguration()
    unifier_config.set_equivalence("number", "singular", _prepare_pos_element(r".*[\.:]sg:.*"))
    unifier_config.set_equivalence("number", "plural", _prepare_pos_element(r".*[\.:]pl:.*"))
    unifier_config.set_equivalence("gender", "feminine", _prepare_pos_element(r".*[\.:]f([\.:].*)?"))
    unifier_config.set_equivalence("gender", "masculine", _prepare_pos_element(r".*[\.:]m([\.:].*)?"))
    unifier_config.set_equivalence("gender", "neutral", _prepare_pos_element(r".*[\.:]n([\.:].*)?"))

    uni = unifier_config.createUnifier()

    equiv = {"number": None, "gender": None}

    sing1a = _make_token("osobiste", "adj:pl:nom.acc.voc:f.n.m2.m3:pos:aff", "osobisty")
    sing1b = _make_token("osobiste", "adj:sg:nom.acc.voc:n:pos:aff", "osobisty")
    sing2 = _make_token("godło", "subst:sg:nom.acc.voc:n", "godło")
    comma = _make_token(",", "comma", ",")

    atr_sing1 = AnalyzedTokenReadings([sing1a, sing1b], start_pos=0, chunk_tags=["NP"], whitespace_before="")
    atr_comma = AnalyzedTokenReadings([comma], start_pos=8, chunk_tags=["PUNCT"], whitespace_before=" ")
    atr_sing2 = AnalyzedTokenReadings([sing2], start_pos=10, chunk_tags=["NP"], whitespace_before=" ")

    uni.is_unified(sing1a, equiv, False, orig_atr=atr_sing1)
    uni.is_unified(sing1b, equiv, True, orig_atr=atr_sing1)
    uni.add_neutral_element(atr_comma)
    assert uni.is_unified(sing2, equiv, True, orig_atr=atr_sing2) is True
    
    final_unified = uni.get_final_unified()
    assert _format_unified_tokens(final_unified) == (
        "[osobiste[osobisty/adj:sg:nom.acc.voc:n:pos:aff*], ,[,/comma*], godło[godło/subst:sg:nom.acc.voc:n*]]"
    )
    assert final_unified is not None
    assert len(final_unified) == 3
    # Check preservation of token text, start_pos, chunk_tags, and whitespace_before
    assert final_unified[0].token == "osobiste"
    assert final_unified[0].start_pos == 0
    assert final_unified[0].chunk_tags == ["NP"]
    assert final_unified[0].whitespace_before == ""
    assert [r.pos_tag for r in final_unified[0].readings] == ["adj:sg:nom.acc.voc:n:pos:aff"]

    assert final_unified[1].token == ","
    assert final_unified[1].start_pos == 8
    assert final_unified[1].chunk_tags == ["PUNCT"]
    assert final_unified[1].whitespace_before == " "

    assert final_unified[2].token == "godło"
    assert final_unified[2].start_pos == 10
    assert final_unified[2].chunk_tags == ["NP"]
    assert final_unified[2].whitespace_before == " "
    uni.reset()
