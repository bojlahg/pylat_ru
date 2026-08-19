"""tests/unit/test_unification.py

Unit tests for Unifier, UnifierConfiguration, EquivalenceTypeLocator,
and fail-closed XML schema validation for unification elements.
"""

import pytest
import xml.etree.ElementTree as ET

from pylat_ru.analysis import AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.grammar.errors import GrammarFormatError
from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.matcher import CompiledPatternToken
from pylat_ru.grammar.model import PatternToken
from pylat_ru.grammar.unification import (
    EquivalenceTypeLocator,
    Unifier,
    UnifierConfiguration,
)


def _make_token(token: str, pos: str, lemma: str = "") -> AnalyzedToken:
    return AnalyzedToken(token=token, pos_tag=pos, lemma=lemma or token)


def _prepare_pos_element(pos_regex: str) -> CompiledPatternToken:
    p_tok = PatternToken(postag=pos_regex, postag_regexp=True)
    return CompiledPatternToken(p_tok)


def test_equivalence_type_locator_equality_and_repr():
    """Test EquivalenceTypeLocator equality, hashing, and representation."""
    loc1 = EquivalenceTypeLocator("gender", "feminine")
    loc2 = EquivalenceTypeLocator("gender", "feminine")
    loc3 = EquivalenceTypeLocator("gender", "masculine")
    loc4 = EquivalenceTypeLocator("number", "feminine")

    assert loc1 == loc2
    assert hash(loc1) == hash(loc2)
    assert loc1 != loc3
    assert loc1 != loc4
    assert repr(loc1) == "EquivalenceTypeLocator(feature='gender', type='feminine')"


def test_unifier_configuration_first_definition_wins():
    """Test UnifierConfiguration duplicate registration first-definition-wins policy."""
    config = UnifierConfiguration()
    elem1 = _prepare_pos_element(".*:m")
    elem2 = _prepare_pos_element(".*:masc")

    config.set_equivalence("gender", "masculine", elem1)
    config.set_equivalence("gender", "masculine", elem2)

    assert len(config.equivalence_types) == 1
    stored = config.equivalence_types[EquivalenceTypeLocator("gender", "masculine")]
    assert stored is elem1
    assert config.equivalence_features == {"gender": ["masculine"]}


def test_unifier_configuration_multiple_features_and_types():
    """Test registering multiple features and equivalence types."""
    config = UnifierConfiguration()
    config.set_equivalence("number", "singular", _prepare_pos_element(".*:sg:.*"))
    config.set_equivalence("number", "plural", _prepare_pos_element(".*:pl:.*"))
    config.set_equivalence("gender", "feminine", _prepare_pos_element(".*:f"))
    config.set_equivalence("gender", "masculine", _prepare_pos_element(".*:m"))

    assert len(config.equivalence_types) == 4
    feats = config.equivalence_features
    assert feats["number"] == ["singular", "plural"]
    assert feats["gender"] == ["feminine", "masculine"]

    unifier = config.create_unifier()
    assert isinstance(unifier, Unifier)
    assert len(unifier.equivalence_types) == 4


def test_unifier_reset_isolation():
    """Test Unifier reset completely restores initial match state."""
    config = UnifierConfiguration()
    config.set_equivalence("number", "singular", _prepare_pos_element(".*:sg:.*"))
    config.set_equivalence("number", "plural", _prepare_pos_element(".*:pl:.*"))
    unifier = config.create_unifier()

    tok1 = _make_token("дом", "NN:sg:m")
    tok2 = _make_token("большой", "ADJ:sg:m")
    equiv = {"number": None}

    unifier.is_unified(tok1, equiv, last_reading=True)
    unifier.is_unified(tok2, equiv, last_reading=True)
    assert unifier.in_unification is True
    assert len(unifier.tok_sequence) == 2

    unifier.reset()
    assert unifier.in_unification is False
    assert len(unifier.tok_sequence) == 0
    assert len(unifier.equivalences_matched) == 0
    assert unifier.tok_cnt == 0
    assert unifier.all_feats_in is False


def test_unification_fail_closed_on_malformed_xml():
    """Test GrammarLoader fails closed on invalid unification elements and attributes."""
    loader = GrammarLoader()

    # Invalid attribute on <unification>
    bad_xml_1 = """<rules lang="ru">
      <unification feature="case" invalid_attr="foo">
        <equivalence type="nom"><token postag=".*:nom"/></equivalence>
      </unification>
      <category id="TEST" name="Test"><rule id="R1" name="R1"><pattern><token>a</token></pattern><message>m</message></rule></category>
    </rules>"""
    with pytest.raises(GrammarFormatError, match="invalid_attr"):
        loader.load_from_string(bad_xml_1)

    # Invalid child under <unification>
    bad_xml_2 = """<rules lang="ru">
      <unification feature="case">
        <unknown_child/>
      </unification>
      <category id="TEST" name="Test"><rule id="R1" name="R1"><pattern><token>a</token></pattern><message>m</message></rule></category>
    </rules>"""
    with pytest.raises(GrammarFormatError, match="unknown_child"):
        loader.load_from_string(bad_xml_2)

    # Invalid attribute on <unify>
    bad_xml_3 = """<rules lang="ru">
      <category id="TEST" name="Test">
        <rule id="R1" name="R1">
          <pattern>
            <unify bogus_attr="yes">
              <feature id="case"/>
              <token postag=".*"/>
            </unify>
          </pattern>
          <message>m</message>
        </rule>
      </category>
    </rules>"""
    with pytest.raises(GrammarFormatError, match="bogus_attr"):
        loader.load_from_string(bad_xml_3)

    # Invalid attribute on <unify-ignore>
    bad_xml_4 = """<rules lang="ru">
      <category id="TEST" name="Test">
        <rule id="R1" name="R1">
          <pattern>
            <unify>
              <feature id="case"/>
              <token postag=".*"/>
              <unify-ignore extra="bad">
                <token postag=".*"/>
              </unify-ignore>
            </unify>
          </pattern>
          <message>m</message>
        </rule>
      </category>
    </rules>"""
    with pytest.raises(GrammarFormatError, match="extra"):
        loader.load_from_string(bad_xml_4)

    # Invalid child under <type>
    bad_xml_5 = """<rules lang="ru">
      <category id="TEST" name="Test">
        <rule id="R1" name="R1">
          <pattern>
            <unify>
              <feature id="case">
                <type id="nom"><bad_nested/></type>
              </feature>
              <token postag=".*"/>
            </unify>
          </pattern>
          <message>m</message>
        </rule>
      </category>
    </rules>"""
    with pytest.raises(GrammarFormatError, match="bad_nested"):
        loader.load_from_string(bad_xml_5)
