"""tools/generate_oracle_unification_fixtures.py

Generates Java LanguageTool differential oracle fixture files for Task 0009:
1. tests/fixtures/oracle_unification_russian_rules.json
   - Evaluates real Russian grammar rules classified as UNIFICATION_0009_RUNNABLE (216 examples)
   - Contains machine-readable feature_coverage mapping derived from actual rule <unify><feature> definitions
2. tests/fixtures/oracle_unification_synthetic.json
   - Comprehensive discriminating synthetic test cases exercising all Task 0009 unification constructs
   - Contains controlled-reading multi-reading disambiguation, multiple scopes, quantifiers, skips, and match references
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.differential_lt import JavaLanguageToolOracle, PINNED_LT_COMMIT, PINNED_LT_VERSION
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.model import ExecutionState, PatternUnify


def utf16_offset_to_codepoint_offset(text: str, utf16_offset: int) -> int:
    """Convert a UTF-16 code unit offset to a Unicode codepoint index."""
    u16_count = 0
    for cp_idx, char in enumerate(text):
        if u16_count >= utf16_offset:
            return cp_idx
        u16_count += 2 if ord(char) > 0xFFFF else 1
    return len(text)


def strip_injection_tags(text: str) -> str:
    """Strip ||INJECT_...|| prefix tags to get the clean sentence text."""
    clean = text
    while clean.startswith("||"):
        end_idx = clean.find("||", 2)
        if end_idx == -1:
            break
        clean = clean[end_idx + 2:]
    return clean


SYNTHETIC_UNIFICATION_RULES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rules lang="ru">
  <unification feature="number">
    <equivalence type="Sin">
      <token postag=".*:Sin(:.*)*|((ADJ|Ord|PT:(Past|Real):.*|PT_Short:Real|VB:Past):.*:(Masc|Fem|Neut)(:.*)*)|NN:.*:(Masc|Fem|Neut)" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="PL">
      <token postag=".*:PL(:.*)*|NN:.*:(Masc|Fem|Neut)" postag_regexp="yes"/>
    </equivalence>
  </unification>

  <unification feature="gender">
    <equivalence type="Masc">
      <token postag=".*:Masc(:.*)*" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="Fem">
      <token postag=".*:Fem(:.*)*" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="Neut">
      <token postag=".*:Neut(:.*)*" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="Plural">
      <token postag=".*:PL(:.*)*|NN:.*:(Masc|Fem|Neut)" postag_regexp="yes"/>
    </equivalence>
  </unification>

  <unification feature="case">
    <equivalence type="Nom">
      <token postag=".*:Nom(:.*)*|NN:.*:(Masc|Fem|Neut)" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="R">
      <token postag=".*:R(:.*)*|NN:.*:(Masc|Fem|Neut)|.*:2R(:.*)*" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="D">
      <token postag=".*:D(:.*)*|NN:.*:(Masc|Fem|Neut)" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="V">
      <token postag=".*:V(:.*)*|NN:.*:(Masc|Fem|Neut)" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="T">
      <token postag=".*:T(:.*)*|NN:.*:(Masc|Fem|Neut)" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="P">
      <token postag=".*:P(:.*)*|NN:.*:(Masc|Fem|Neut)|.*:2P(:.*)*" postag_regexp="yes"/>
    </equivalence>
  </unification>

  <unification feature="animacy">
    <equivalence type="Anim">
      <token postag=".*:(Anim|Inanimanim|Name|Patr|Fam)(:.*)*" postag_regexp="yes"/>
    </equivalence>
    <equivalence type="Inanim">
      <token postag=".*:(Inanim|Inanimanim)(:.*)*" postag_regexp="yes"/>
    </equivalence>
  </unification>

  <category id="SYN_UNI_SINGLE" name="Synthetic Single Feature Agreement">
    <rule id="SYN_UNI_NUMBER_AGREE" name="Number agreement">
      <pattern>
        <unify>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Number agree: <suggestion>\\1 \\2</suggestion></message>
    </rule>

    <rule id="SYN_UNI_GENDER_AGREE" name="Gender agreement">
      <pattern>
        <unify>
          <feature id="gender"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Gender agree: <suggestion>\\1 \\2</suggestion></message>
    </rule>

    <rule id="SYN_UNI_CASE_AGREE" name="Case agreement">
      <pattern>
        <unify>
          <feature id="case"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Case agree: <suggestion>\\1 \\2</suggestion></message>
    </rule>

    <rule id="SYN_UNI_ANIMACY_AGREE" name="Animacy agreement">
      <pattern>
        <unify>
          <feature id="animacy"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Animacy agree: <suggestion>\\1 \\2</suggestion></message>
    </rule>
  </category>

  <category id="SYN_UNI_MULTI_FEAT" name="Synthetic Multi-Feature Agreement">
    <rule id="SYN_UNI_GENDER_NUMBER" name="Gender and Number agreement">
      <pattern>
        <unify>
          <feature id="gender"/>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Gender+Number agree</message>
    </rule>

    <rule id="SYN_UNI_CASE_GENDER_NUMBER" name="Case, Gender, and Number agreement">
      <pattern>
        <unify>
          <feature id="case"/>
          <feature id="gender"/>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Full nominal agree: <suggestion>\\1 \\2</suggestion></message>
    </rule>

    <rule id="SYN_UNI_THREE_TOKENS" name="Three token unification">
      <pattern>
        <unify>
          <feature id="number"/>
          <feature id="gender"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Three tokens agree: <suggestion>\\1 \\2 \\3</suggestion></message>
    </rule>
  </category>

  <category id="SYN_UNI_TYPES" name="Synthetic Explicit Types">
    <rule id="SYN_UNI_EXPLICIT_FEMININE" name="Only feminine agreement">
      <pattern>
        <unify>
          <feature id="gender">
            <type id="Fem"/>
          </feature>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Feminine only</message>
    </rule>

    <rule id="SYN_UNI_EXPLICIT_NOM_ACC" name="Only nom or acc agreement">
      <pattern>
        <unify>
          <feature id="case">
            <type id="Nom"/>
            <type id="V"/>
          </feature>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Nom or Acc only</message>
    </rule>
  </category>

  <category id="SYN_UNI_NEGATION" name="Synthetic Negated Unification">
    <rule id="SYN_UNI_NEG_NUMBER" name="Number disagreement">
      <pattern>
        <unify negate="yes">
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Number disagree</message>
    </rule>

    <rule id="SYN_UNI_NEG_GENDER_NUMBER" name="Gender/Number disagreement">
      <pattern>
        <unify negate="yes">
          <feature id="gender"/>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Gender/Number disagree</message>
    </rule>
  </category>

  <category id="SYN_UNI_IGNORE" name="Synthetic Unify Ignore (Neutral Elements)">
    <rule id="SYN_UNI_IGNORE_COMMA" name="Unification with neutral punctuation">
      <pattern>
        <unify>
          <feature id="number"/>
          <feature id="gender"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <unify-ignore>
            <token>,</token>
          </unify-ignore>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Ignore comma agree</message>
    </rule>

    <rule id="SYN_UNI_IGNORE_ADVERB" name="Unification with neutral adverb">
      <pattern>
        <unify>
          <feature id="number"/>
          <feature id="gender"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <unify-ignore>
            <token postag_regexp="yes" postag="ADV:.*"/>
          </unify-ignore>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Ignore adverb agree</message>
    </rule>
  </category>

  <category id="SYN_UNI_ADVANCED" name="Synthetic Advanced Pattern Unify Combinations">
    <rule id="SYN_UNI_PREV_EXC" name="Unification with previous exception">
      <pattern>
        <token>старт</token>
        <unify>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*">
            <exception scope="previous">старт</exception>
          </token>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Previous exception unify</message>
    </rule>

    <rule id="SYN_UNI_NEXT_EXC" name="Unification with next exception">
      <pattern>
        <unify>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*">
            <exception scope="next">дом</exception>
          </token>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Next exception unify</message>
    </rule>

    <rule id="SYN_UNI_MAX2" name="Unification with max 2">
      <pattern>
        <unify>
          <feature id="number"/>
          <token min="1" max="2" postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Max 2 unify: <suggestion>\\1 \\2</suggestion></message>
    </rule>

    <rule id="SYN_UNI_MAX3" name="Unification with max 3">
      <pattern>
        <unify>
          <feature id="number"/>
          <token min="1" max="3" postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Max 3 unify</message>
    </rule>

    <rule id="SYN_UNI_MAX_UNBOUNDED" name="Unification with max -1">
      <pattern>
        <unify>
          <feature id="number"/>
          <token min="1" max="-1" postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Max -1 unify</message>
    </rule>

    <rule id="SYN_UNI_MIN0" name="Unification with min 0">
      <pattern>
        <unify>
          <feature id="number"/>
          <token min="0" postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Min 0 unify</message>
    </rule>

    <rule id="SYN_UNI_FINITE_SKIP" name="Unification with finite skip">
      <pattern>
        <token skip="2">старт</token>
        <unify>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Finite skip unify</message>
    </rule>

    <rule id="SYN_UNI_INFINITE_SKIP" name="Unification with infinite skip">
      <pattern>
        <token skip="-1">начало</token>
        <unify>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Infinite skip unify</message>
    </rule>

    <rule id="SYN_UNI_AND" name="Unification with AND group">
      <pattern>
        <unify>
          <feature id="number"/>
          <and>
            <token postag_regexp="yes" postag="ADJ:.*"/>
            <token regexp="yes">.*ый|.*ая|.*ое|.*ие|.*ой</token>
          </and>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>AND unify</message>
    </rule>

    <rule id="SYN_UNI_OR" name="Unification with OR group">
      <pattern>
        <unify>
          <feature id="number"/>
          <or>
            <token postag_regexp="yes" postag="ADJ:.*"/>
            <token postag_regexp="yes" postag="PT:.*"/>
          </or>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>OR unify</message>
    </rule>

    <rule id="SYN_UNI_SPACEBEFORE" name="Unification with spacebefore">
      <pattern>
        <unify>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token spacebefore="no" postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Spacebefore unify</message>
    </rule>

    <rule id="SYN_UNI_CHUNK" name="Unification with chunk">
      <pattern>
        <unify>
          <feature id="number"/>
          <token chunk="NP" postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Chunk unify</message>
    </rule>

    <rule id="SYN_UNI_ANTIPATTERN" name="Unification with antipattern">
      <antipattern>
        <token>стоп</token>
        <token postag_regexp="yes" postag="NN:.*"/>
      </antipattern>
      <pattern>
        <unify>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Antipattern unify</message>
    </rule>

    <rule id="SYN_UNI_MARKER_SPANS" name="Marker around unify">
      <pattern>
        <token>префикс</token>
        <marker>
          <unify>
            <feature id="number"/>
            <token postag_regexp="yes" postag="ADJ:.*"/>
            <token postag_regexp="yes" postag="NN:.*"/>
          </unify>
        </marker>
        <token>суффикс</token>
      </pattern>
      <message>Marker spans unify: <suggestion>\\2 \\3</suggestion></message>
    </rule>

    <rule id="SYN_UNI_MATCH_REFS" name="Match references around unify">
      <pattern>
        <token>слово1</token>
        <unify>
          <feature id="gender"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
        <token>слово4</token>
      </pattern>
      <message>Refs: <suggestion>\\1 \\2 \\3 \\4</suggestion></message>
    </rule>

    <rule id="SYN_UNI_RAW_POS_DIFF" name="Raw pos discriminating unify">
      <pattern raw_pos="yes">
        <unify>
          <feature id="gender"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Raw pos diff</message>
    </rule>

    <rule id="SYN_UNI_MULTI_SCOPES" name="Multiple unify scopes in sequence">
      <pattern>
        <unify>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
        <token>и</token>
        <unify>
          <feature id="gender"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Multiple unify scopes</message>
    </rule>

    <rule id="SYN_UNI_BASE_FILTER" name="Base pattern filters readings before unify">
      <pattern>
        <unify>
          <feature id="gender"/>
          <token postag_regexp="yes" postag="ADJ:.*:Nom"/>
          <token postag_regexp="yes" postag="NN:.*:Nom"/>
        </unify>
      </pattern>
      <message>Base filter</message>
    </rule>

    <rule id="SYN_UNI_MISSING_EQ" name="Missing equivalence value">
      <pattern>
        <unify>
          <feature id="gender"/>
          <token postag_regexp="yes" postag="NON_EQUIV_TAG"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Missing eq</message>
    </rule>
  </category>
</rules>
"""

REQUIRED_SYNTHETIC_UNIFICATION_FEATURES = {
    "uni_feature_number",
    "uni_feature_gender",
    "uni_feature_case",
    "uni_feature_animacy",
    "uni_multi_feature",
    "uni_explicit_types",
    "uni_negation",
    "uni_neutral_elements",
    "multiple_unify_scopes",
    "success_then_fail_candidate",
    "fail_then_success_candidate",
    "repeated_calls_isolation",
    "finite_skip_unify",
    "infinite_skip_unify",
    "min_zero_unify",
    "max_quantifiers_unify",
    "and_group_unify",
    "or_group_unify",
    "previous_exception_unify",
    "next_exception_unify",
    "spacebefore_unify",
    "chunk_unify",
    "raw_pos_unify",
    "antipattern_unify",
    "marker_spans_unify",
    "match_references_unify",
    "controlled_multi_reading_filtering",
    "controlled_base_pattern_reading_filtering",
    "controlled_rejected_reading_isolation",
    "controlled_equivalence_intersection",
    "controlled_missing_equivalence_value",
    "controlled_positive_unification",
    "controlled_negated_unification",
    "controlled_neutral_unify_ignore",
    "uni_positive_match",
    "uni_no_match",
}

DISCRIMINATING_SYNTHETIC_UNIFICATION_CASES = [
    # 1. Single Feature: Number agreement
    {"id": "syn_uni_num_01", "full_rule_id": "SYN_UNI_NUMBER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивый дом", "features": ["uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_num_02", "full_rule_id": "SYN_UNI_NUMBER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивые дома", "features": ["uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_num_03", "full_rule_id": "SYN_UNI_NUMBER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивый дома", "features": ["uni_feature_number", "uni_no_match"]},
    {"id": "syn_uni_num_04", "full_rule_id": "SYN_UNI_NUMBER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивые дом", "features": ["uni_feature_number", "uni_no_match"]},
    {"id": "syn_uni_num_05", "full_rule_id": "SYN_UNI_NUMBER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "большая книга", "features": ["uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_num_06", "full_rule_id": "SYN_UNI_NUMBER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "большие книги", "features": ["uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_num_07", "full_rule_id": "SYN_UNI_NUMBER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "новое окно", "features": ["uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_num_08", "full_rule_id": "SYN_UNI_NUMBER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "новые окна", "features": ["uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_num_09", "full_rule_id": "SYN_UNI_NUMBER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "новое окна", "features": ["uni_feature_number", "uni_no_match"]},
    {"id": "syn_uni_num_10", "full_rule_id": "SYN_UNI_NUMBER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "старый стол", "features": ["uni_feature_number", "uni_positive_match"]},

    # 2. Single Feature: Gender agreement
    {"id": "syn_uni_gen_01", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивый дом", "features": ["uni_feature_gender", "uni_positive_match"]},
    {"id": "syn_uni_gen_02", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивая книга", "features": ["uni_feature_gender", "uni_positive_match"]},
    {"id": "syn_uni_gen_03", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивое окно", "features": ["uni_feature_gender", "uni_positive_match"]},
    {"id": "syn_uni_gen_04", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивый книга", "features": ["uni_feature_gender", "uni_no_match"]},
    {"id": "syn_uni_gen_05", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивая дом", "features": ["uni_feature_gender", "uni_no_match"]},
    {"id": "syn_uni_gen_06", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивое дом", "features": ["uni_feature_gender", "uni_no_match"]},
    {"id": "syn_uni_gen_07", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "синий шар", "features": ["uni_feature_gender", "uni_positive_match"]},
    {"id": "syn_uni_gen_08", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "синяя река", "features": ["uni_feature_gender", "uni_positive_match"]},
    {"id": "syn_uni_gen_09", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "синее море", "features": ["uni_feature_gender", "uni_positive_match"]},
    {"id": "syn_uni_gen_10", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "синий река", "features": ["uni_feature_gender", "uni_no_match"]},

    # 3. Single Feature: Case agreement
    {"id": "syn_uni_case_01", "full_rule_id": "SYN_UNI_CASE_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивый дом", "features": ["uni_feature_case", "uni_positive_match"]},
    {"id": "syn_uni_case_02", "full_rule_id": "SYN_UNI_CASE_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивого дома", "features": ["uni_feature_case", "uni_positive_match"]},
    {"id": "syn_uni_case_03", "full_rule_id": "SYN_UNI_CASE_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивому дому", "features": ["uni_feature_case", "uni_positive_match"]},
    {"id": "syn_uni_case_04", "full_rule_id": "SYN_UNI_CASE_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивым домом", "features": ["uni_feature_case", "uni_positive_match"]},
    {"id": "syn_uni_case_05", "full_rule_id": "SYN_UNI_CASE_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивом доме", "features": ["uni_feature_case", "uni_positive_match"]},
    {"id": "syn_uni_case_06", "full_rule_id": "SYN_UNI_CASE_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивый дому", "features": ["uni_feature_case", "uni_no_match"]},
    {"id": "syn_uni_case_07", "full_rule_id": "SYN_UNI_CASE_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивая книга", "features": ["uni_feature_case", "uni_positive_match"]},
    {"id": "syn_uni_case_08", "full_rule_id": "SYN_UNI_CASE_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивой книги", "features": ["uni_feature_case", "uni_positive_match"]},
    {"id": "syn_uni_case_09", "full_rule_id": "SYN_UNI_CASE_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивую книгу", "features": ["uni_feature_case", "uni_positive_match"]},
    {"id": "syn_uni_case_10", "full_rule_id": "SYN_UNI_CASE_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивая книги", "features": ["uni_feature_case", "uni_no_match"]},

    # 4. Single Feature: Animacy agreement
    {"id": "syn_uni_anim_01", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "живой кот", "features": ["uni_feature_animacy", "uni_positive_match"]},
    {"id": "syn_uni_anim_02", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "деревянный стол", "features": ["uni_feature_animacy", "uni_positive_match"]},
    {"id": "syn_uni_anim_03", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "умный человек", "features": ["uni_feature_animacy", "uni_positive_match"]},
    {"id": "syn_uni_anim_04", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "быстрый конь", "features": ["uni_feature_animacy", "uni_positive_match"]},
    {"id": "syn_uni_anim_05", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "каменный мост", "features": ["uni_feature_animacy", "uni_positive_match"]},
    {"id": "syn_uni_anim_06", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "верная собака", "features": ["uni_feature_animacy", "uni_positive_match"]},
    {"id": "syn_uni_anim_07", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "железная дверь", "features": ["uni_feature_animacy", "uni_positive_match"]},
    {"id": "syn_uni_anim_08", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "сильный медведь", "features": ["uni_feature_animacy", "uni_positive_match"]},
    {"id": "syn_uni_anim_09", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "чистая вода", "features": ["uni_feature_animacy", "uni_positive_match"]},
    {"id": "syn_uni_anim_10", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "добрый учитель", "features": ["uni_feature_animacy", "uni_positive_match"]},

    # 5. Multi-Feature: Gender and Number
    {"id": "syn_uni_gn_01", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивый дом", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_gn_02", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивая книга", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_gn_03", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивое окно", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_gn_04", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивые дома", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_gn_05", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивый книга", "features": ["uni_multi_feature", "uni_no_match"]},
    {"id": "syn_uni_gn_06", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивая дома", "features": ["uni_multi_feature", "uni_no_match"]},
    {"id": "syn_uni_gn_07", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивые дом", "features": ["uni_multi_feature", "uni_no_match"]},
    {"id": "syn_uni_gn_08", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "большой город", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_gn_09", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "большая река", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_gn_10", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "большие реки", "features": ["uni_multi_feature", "uni_positive_match"]},

    # 6. Multi-Feature: Case, Gender, and Number
    {"id": "syn_uni_cgn_01", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивый дом", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_cgn_02", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивого дома", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_cgn_03", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивой книги", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_cgn_04", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивому дому", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_cgn_05", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивой книге", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_cgn_06", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивым домом", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_cgn_07", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивой книгой", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_cgn_08", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивом доме", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_cgn_09", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивый дома", "features": ["uni_multi_feature", "uni_no_match"]},
    {"id": "syn_uni_cgn_10", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивая дому", "features": ["uni_multi_feature", "uni_no_match"]},

    # 7. Multi-Token: Three tokens agreement
    {"id": "syn_uni_3tok_01", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "новый красивый дом", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_3tok_02", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "новая красивая книга", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_3tok_03", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "новое красивое окно", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_3tok_04", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "новые красивые дома", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_3tok_05", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "большой красивая дом", "features": ["uni_multi_feature", "uni_no_match", "controlled_multi_reading_filtering"]},
    {"id": "syn_uni_3tok_06", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "новый красивая книга", "features": ["uni_multi_feature", "uni_no_match"]},
    {"id": "syn_uni_3tok_07", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "старый добрый друг", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_3tok_08", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "старая добрая подруга", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_3tok_09", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "старые добрые друзья", "features": ["uni_multi_feature", "uni_positive_match"]},
    {"id": "syn_uni_3tok_10", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "старый добрая друг", "features": ["uni_multi_feature", "uni_no_match"]},

    # 8. Explicit Types: Feminine only
    {"id": "syn_uni_fem_01", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "красивая книга", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_fem_02", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "синяя река", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_fem_03", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "большая река", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_fem_04", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "красивый дом", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_fem_05", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "красивое окно", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_fem_06", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "старая машина", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_fem_07", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "чистая вода", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_fem_08", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "новый стол", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_fem_09", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "зеленая трава", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_fem_010", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "зеленое поле", "features": ["uni_explicit_types", "uni_no_match"]},

    # 9. Explicit Types: Nom or Acc only
    {"id": "syn_uni_nomacc_01", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "красивый дом", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_nomacc_02", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "красивая книга", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_nomacc_03", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "красивую книгу", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_nomacc_04", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "красивого дома", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_nomacc_05", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "красивому дому", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_nomacc_06", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "красивым домом", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_nomacc_07", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "новое окно", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_nomacc_08", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "новому окну", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_nomacc_09", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "чистый лист", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_nomacc_10", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "чистым листом", "features": ["uni_explicit_types", "uni_no_match"]},

    # 10. Negated Unification: Number disagreement
    {"id": "syn_uni_neg_num_01", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивые дом", "features": ["uni_negation", "uni_positive_match"]},
    {"id": "syn_uni_neg_num_02", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "новые окно", "features": ["uni_negation", "uni_positive_match"]},
    {"id": "syn_uni_neg_num_03", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивый дом", "features": ["uni_negation", "uni_no_match"]},
    {"id": "syn_uni_neg_num_04", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивые дома", "features": ["uni_negation", "uni_no_match"]},
    {"id": "syn_uni_neg_num_05", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "большие книга", "features": ["uni_negation", "uni_positive_match"]},
    {"id": "syn_uni_neg_num_06", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "новое окно", "features": ["uni_negation", "uni_no_match"]},
    {"id": "syn_uni_neg_num_07", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "старые стол", "features": ["uni_negation", "uni_positive_match"]},
    {"id": "syn_uni_neg_num_08", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "чистые вода", "features": ["uni_negation", "uni_positive_match"]},
    {"id": "syn_uni_neg_num_09", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "чистая вода", "features": ["uni_negation", "uni_no_match"]},
    {"id": "syn_uni_neg_num_10", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "большая книга", "features": ["uni_negation", "uni_no_match"]},

    # 11. Negated Unification: Gender/Number disagreement
    {"id": "syn_uni_neg_gn_01", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивый книга", "features": ["uni_negation", "uni_positive_match"]},
    {"id": "syn_uni_neg_gn_02", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивая дом", "features": ["uni_negation", "uni_positive_match"]},
    {"id": "syn_uni_neg_gn_03", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивое дом", "features": ["uni_negation", "uni_positive_match"]},
    {"id": "syn_uni_neg_gn_04", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивый дом", "features": ["uni_negation", "uni_no_match"]},
    {"id": "syn_uni_neg_gn_05", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивая книга", "features": ["uni_negation", "uni_no_match"]},
    {"id": "syn_uni_neg_gn_06", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивое окно", "features": ["uni_negation", "uni_no_match"]},
    {"id": "syn_uni_neg_gn_07", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "синий река", "features": ["uni_negation", "uni_positive_match"]},
    {"id": "syn_uni_neg_gn_08", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "синяя шар", "features": ["uni_negation", "uni_positive_match"]},
    {"id": "syn_uni_neg_gn_09", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "синее море", "features": ["uni_negation", "uni_no_match"]},
    {"id": "syn_uni_neg_gn_10", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "синий шар", "features": ["uni_negation", "uni_no_match"]},

    # 12. Neutral Elements: Ignore comma
    {"id": "syn_uni_ign_com_01", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "новый , красивый дом", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_02", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "новая , красивая книга", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_03", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "новое , красивое окно", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_04", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "новые , красивые дома", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_05", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "большой , красивая дом", "features": ["uni_neutral_elements", "uni_no_match", "controlled_multi_reading_filtering"]},
    {"id": "syn_uni_ign_com_06", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "новый , красивая книга", "features": ["uni_neutral_elements", "uni_no_match"]},
    {"id": "syn_uni_ign_com_07", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "старый , добрый друг", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_08", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "старая , добрая подруга", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_09", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "старые , добрые друзья", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_10", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "старый , добрая друг", "features": ["uni_neutral_elements", "uni_no_match"]},

    # 13. Neutral Elements: Ignore adverb
    {"id": "syn_uni_ign_adv_01", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "очень красивый дом", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_02", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "очень красивая книга", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_03", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "очень красивое окно", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_04", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "очень красивые дома", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_05", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "очень красивый книга", "features": ["uni_neutral_elements", "uni_no_match"]},
    {"id": "syn_uni_ign_adv_06", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "очень красивая дом", "features": ["uni_neutral_elements", "uni_no_match"]},
    {"id": "syn_uni_ign_adv_07", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "весьма интересный факт", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_08", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "весьма интересная мысль", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_09", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "весьма интересное дело", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_10", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "весьма интересный мысль", "features": ["uni_neutral_elements", "uni_no_match"]},

    # 14. Advanced Unify: Previous & Next Exceptions
    {"id": "syn_uni_prev_exc_01", "full_rule_id": "SYN_UNI_PREV_EXC[1]", "category": "SYN_UNI_ADVANCED", "text": "старт красивый дом", "features": ["previous_exception_unify", "uni_no_match"]},
    {"id": "syn_uni_prev_exc_02", "full_rule_id": "SYN_UNI_PREV_EXC[1]", "category": "SYN_UNI_ADVANCED", "text": "начало красивый дом", "features": ["previous_exception_unify", "uni_no_match"]},
    {"id": "syn_uni_next_exc_01", "full_rule_id": "SYN_UNI_NEXT_EXC[1]", "category": "SYN_UNI_ADVANCED", "text": "красивый дом", "features": ["next_exception_unify", "uni_no_match"]},
    {"id": "syn_uni_next_exc_02", "full_rule_id": "SYN_UNI_NEXT_EXC[1]", "category": "SYN_UNI_ADVANCED", "text": "красивая книга", "features": ["next_exception_unify", "uni_positive_match"]},

    # 15. Advanced Unify: Quantifiers (min=0, max=2, max=3, max=-1)
    {"id": "syn_uni_min0_01", "full_rule_id": "SYN_UNI_MIN0[1]", "category": "SYN_UNI_ADVANCED", "text": "красивый дом", "features": ["min_zero_unify", "uni_positive_match"]},
    {"id": "syn_uni_min0_02", "full_rule_id": "SYN_UNI_MIN0[1]", "category": "SYN_UNI_ADVANCED", "text": "дом", "features": ["min_zero_unify", "uni_positive_match"]},
    {"id": "syn_uni_max2_01", "full_rule_id": "SYN_UNI_MAX2[1]", "category": "SYN_UNI_ADVANCED", "text": "красивый дом", "features": ["max_quantifiers_unify", "uni_positive_match"]},
    {"id": "syn_uni_max2_02", "full_rule_id": "SYN_UNI_MAX2[1]", "category": "SYN_UNI_ADVANCED", "text": "новый красивый дом", "features": ["max_quantifiers_unify", "uni_positive_match"]},
    {"id": "syn_uni_max3_01", "full_rule_id": "SYN_UNI_MAX3[1]", "category": "SYN_UNI_ADVANCED", "text": "новый красивый большой дом", "features": ["max_quantifiers_unify", "uni_positive_match"]},
    {"id": "syn_uni_max3_02", "full_rule_id": "SYN_UNI_MAX3[1]", "category": "SYN_UNI_ADVANCED", "text": "новый красивый большая дом", "features": ["max_quantifiers_unify", "uni_no_match"]},
    {"id": "syn_uni_max_unb_01", "full_rule_id": "SYN_UNI_MAX_UNBOUNDED[1]", "category": "SYN_UNI_ADVANCED", "text": "новый красивый большой старый дом", "features": ["max_quantifiers_unify", "uni_positive_match"]},

    # 16. Advanced Unify: Finite & Infinite Skip
    {"id": "syn_uni_fskip_01", "full_rule_id": "SYN_UNI_FINITE_SKIP[1]", "category": "SYN_UNI_ADVANCED", "text": "старт один два красивый дом", "features": ["finite_skip_unify", "uni_positive_match"]},
    {"id": "syn_uni_fskip_02", "full_rule_id": "SYN_UNI_FINITE_SKIP[1]", "category": "SYN_UNI_ADVANCED", "text": "старт один два три красивый дом", "features": ["finite_skip_unify", "uni_no_match"]},
    {"id": "syn_uni_infskip_01", "full_rule_id": "SYN_UNI_INFINITE_SKIP[1]", "category": "SYN_UNI_ADVANCED", "text": "начало один два три четыре красивый дом", "features": ["infinite_skip_unify", "uni_positive_match"]},
    {"id": "syn_uni_infskip_02", "full_rule_id": "SYN_UNI_INFINITE_SKIP[1]", "category": "SYN_UNI_ADVANCED", "text": "начало один два три четыре красивые дом", "features": ["infinite_skip_unify", "uni_no_match"]},

    # 17. Advanced Unify: Logical AND & OR groups
    {"id": "syn_uni_and_01", "full_rule_id": "SYN_UNI_AND[1]", "category": "SYN_UNI_ADVANCED", "text": "красивый дом", "features": ["and_group_unify", "uni_positive_match"]},
    {"id": "syn_uni_and_02", "full_rule_id": "SYN_UNI_AND[1]", "category": "SYN_UNI_ADVANCED", "text": "красивые дом", "features": ["and_group_unify", "uni_no_match"]},
    {"id": "syn_uni_or_01", "full_rule_id": "SYN_UNI_OR[1]", "category": "SYN_UNI_ADVANCED", "text": "красивый дом", "features": ["or_group_unify", "uni_positive_match"]},
    {"id": "syn_uni_or_02", "full_rule_id": "SYN_UNI_OR[1]", "category": "SYN_UNI_ADVANCED", "text": "построенный дом", "features": ["or_group_unify", "uni_positive_match"]},
    {"id": "syn_uni_or_03", "full_rule_id": "SYN_UNI_OR[1]", "category": "SYN_UNI_ADVANCED", "text": "построенные дом", "features": ["or_group_unify", "uni_no_match"]},

    # 18. Advanced Unify: Spacebefore, Chunk, Antipattern, Marker Spans, Match References
    {"id": "syn_uni_sp_01", "full_rule_id": "SYN_UNI_SPACEBEFORE[1]", "category": "SYN_UNI_ADVANCED", "text": "красивыйдом", "features": ["spacebefore_unify", "uni_positive_match"]},
    {"id": "syn_uni_sp_02", "full_rule_id": "SYN_UNI_SPACEBEFORE[1]", "category": "SYN_UNI_ADVANCED", "text": "красивый дом", "features": ["spacebefore_unify", "uni_no_match"]},
    {"id": "syn_uni_chk_01", "full_rule_id": "SYN_UNI_CHUNK[1]", "category": "SYN_UNI_ADVANCED", "text": "||INJECT_CHUNKS:1=NP||красивый дом", "features": ["chunk_unify", "uni_positive_match"]},
    {"id": "syn_uni_chk_02", "full_rule_id": "SYN_UNI_CHUNK[1]", "category": "SYN_UNI_ADVANCED", "text": "||INJECT_CHUNKS:1=VP||красивый дом", "features": ["chunk_unify", "uni_no_match"]},
    {"id": "syn_uni_ap_01", "full_rule_id": "SYN_UNI_ANTIPATTERN[1]", "category": "SYN_UNI_ADVANCED", "text": "красивый дом", "features": ["antipattern_unify", "uni_positive_match"]},
    {"id": "syn_uni_ap_02", "full_rule_id": "SYN_UNI_ANTIPATTERN[1]", "category": "SYN_UNI_ADVANCED", "text": "стоп красивый дом", "features": ["antipattern_unify", "uni_no_match"]},
    {"id": "syn_uni_mark_01", "full_rule_id": "SYN_UNI_MARKER_SPANS[1]", "category": "SYN_UNI_ADVANCED", "text": "префикс красивый дом суффикс", "features": ["marker_spans_unify", "uni_positive_match"]},
    {"id": "syn_uni_mref_01", "full_rule_id": "SYN_UNI_MATCH_REFS[1]", "category": "SYN_UNI_ADVANCED", "text": "слово1 красивый дом слово4", "features": ["match_references_unify", "uni_positive_match"]},
    {"id": "syn_uni_mult_scopes_01", "full_rule_id": "SYN_UNI_MULTI_SCOPES[1]", "category": "SYN_UNI_ADVANCED", "text": "новый дом и новая книга", "features": ["multiple_unify_scopes", "uni_positive_match"]},
    {"id": "syn_uni_mult_scopes_02", "full_rule_id": "SYN_UNI_MULTI_SCOPES[1]", "category": "SYN_UNI_ADVANCED", "text": "красивые дом и новая книга", "features": ["multiple_unify_scopes", "uni_no_match"]},

    # 19. Discriminating Raw POS Proof (Controlled Pre/Post Disambiguation)
    {"id": "syn_uni_raw_pos_01", "full_rule_id": "SYN_UNI_RAW_POS_DIFF[1]", "category": "SYN_UNI_ADVANCED", "text": "||INJECT_PRE_DISAMBIG:1=слово/слово/ADJ:Masc:Sin:Nom|| ||INJECT_READINGS:1=слово/слово/VB:Past:Fem||слово дом", "features": ["raw_pos_unify", "uni_positive_match"]},
    {"id": "syn_uni_raw_pos_02", "full_rule_id": "SYN_UNI_RAW_POS_DIFF[1]", "category": "SYN_UNI_ADVANCED", "text": "||INJECT_PRE_DISAMBIG:1=слово/слово/ADJ:Fem:Sin:Nom|| ||INJECT_READINGS:1=слово/слово/ADJ:Masc:Sin:Nom||слово дом", "features": ["raw_pos_unify", "uni_no_match"]},

    # 20. Real Controlled ATR Injections (Multi-Reading, Base Filtering, Rejected Isolation, Intersections, Missing Values)
    {"id": "syn_uni_ctrl_mult_rd", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "||INJECT_READINGS:1=слово/слово/ADJ:Masc:Sin:Nom,слово/слово/ADJ:Fem:Sin:Nom|| ||INJECT_READINGS:2=дом/дом/NN:Masc:Sin:Nom||слово дом", "features": ["controlled_multi_reading_filtering", "uni_positive_match"]},
    {"id": "syn_uni_ctrl_base_filter", "full_rule_id": "SYN_UNI_BASE_FILTER[1]", "category": "SYN_UNI_ADVANCED", "text": "||INJECT_READINGS:1=слово/слово/ADJ:Fem:Sin:Nom,слово/слово/ADJ:Masc:Sin:Gen|| ||INJECT_READINGS:2=дом/дом/NN:Masc:Sin:Nom||слово дом", "features": ["controlled_base_pattern_reading_filtering", "uni_no_match"]},
    {"id": "syn_uni_ctrl_rej_iso", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "||INJECT_READINGS:1=слово/слово/ADJ:Fem:Sin:Nom,слово/слово/NN:Masc:Sin:Nom|| ||INJECT_READINGS:2=дом/дом/NN:Masc:Sin:Nom||слово дом", "features": ["controlled_rejected_reading_isolation", "uni_no_match"]},
    {"id": "syn_uni_ctrl_eq_inter", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "||INJECT_READINGS:1=слово/слово/ADJ:Masc:Sin:Nom,слово/слово/ADJ:Fem:Sin:Nom|| ||INJECT_READINGS:2=книга/книга/NN:Fem:Sin:Nom||слово книга", "features": ["controlled_equivalence_intersection", "uni_positive_match"]},
    {"id": "syn_uni_ctrl_miss_val", "full_rule_id": "SYN_UNI_MISSING_EQ[1]", "category": "SYN_UNI_ADVANCED", "text": "||INJECT_READINGS:1=слово/слово/NON_EQUIV_TAG|| ||INJECT_READINGS:2=дом/дом/NN:Masc:Sin:Nom||слово дом", "features": ["controlled_missing_equivalence_value", "uni_no_match"]},
    {"id": "syn_uni_ctrl_pos_unify", "full_rule_id": "SYN_UNI_GENDER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "||INJECT_READINGS:1=слово/слово/ADJ:Masc:Sin:Nom|| ||INJECT_READINGS:2=дом/дом/NN:Masc:Sin:Nom||слово дом", "features": ["controlled_positive_unification", "uni_positive_match"]},
    {"id": "syn_uni_ctrl_neg_unify", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "||INJECT_READINGS:1=слово/слово/ADJ:Fem:Sin:Nom|| ||INJECT_READINGS:2=дом/дом/NN:Masc:Sin:Nom||слово дом", "features": ["controlled_negated_unification", "uni_positive_match"]},
    {"id": "syn_uni_ctrl_neutral", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "||INJECT_READINGS:1=слово1/слово1/ADJ:Masc:Sin:Nom|| ||INJECT_READINGS:2=запятая/запятая/,|| ||INJECT_READINGS:3=слово2/слово2/ADJ:Masc:Sin:Nom|| ||INJECT_READINGS:4=дом/дом/NN:Masc:Sin:Nom||слово1 , слово2 дом", "features": ["controlled_neutral_unify_ignore", "uni_positive_match"]},

    # 21. Candidate transitions and repeated calls isolation
    {"id": "syn_uni_cand_succ_fail", "full_rule_id": "SYN_UNI_NUMBER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивый дом красивые дом", "features": ["success_then_fail_candidate", "repeated_calls_isolation", "uni_positive_match"]},
    {"id": "syn_uni_cand_fail_succ", "full_rule_id": "SYN_UNI_NUMBER_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "красивые дом красивый дом", "features": ["fail_then_success_candidate", "repeated_calls_isolation", "uni_positive_match"]},
]


def generate_unification_fixtures():
    oracle = JavaLanguageToolOracle()
    if not oracle.is_java_available():
        print("ERROR: Java is not available!")
        sys.exit(1)

    val = oracle.validate_oracle()
    oracle_sha = val["jar_sha256"]
    oracle_build_id = val["oracle_build_id"]

    fixtures_dir = PROJECT_ROOT / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate oracle_unification_russian_rules.json from real rule examples
    engine = RussianGrammarEngine.get_instance()
    uni_rules = [r for r in engine.get_all_rules() if r.execution_state == ExecutionState.UNIFICATION_0009_RUNNABLE]

    print(f"Loaded {len(uni_rules)} UNIFICATION_0009_RUNNABLE rules.")
    assert len(uni_rules) == 24, f"Expected 24 unification rules, found {len(uni_rules)}"

    russian_rule_cases = []
    case_idx = 1

    # Map each rule's feature IDs directly from its actual <unify><feature id="..."> elements
    rule_features_map: Dict[str, List[str]] = {}
    for rule in uni_rules:
        r_feats: List[str] = []
        for elem in (rule.pattern.elements or rule.pattern.tokens or []):
            if isinstance(elem, PatternUnify):
                for f in elem.features:
                    if f.name not in r_feats:
                        r_feats.append(f.name)
        rule_features_map[rule.full_id] = r_feats

        for ex_idx, ex in enumerate(rule.examples):
            case_id = f"uni_ru_{case_idx:03d}_{rule.id}_{ex_idx}"
            russian_rule_cases.append({
                "id": case_id,
                "category": rule.category_id,
                "full_rule_id": rule.full_id,
                "text": ex.text,
                "is_incorrect": ex.is_incorrect,
                "rule_features": r_feats,
            })
            case_idx += 1

    print(f"Querying Java Oracle for {len(russian_rule_cases)} real Russian rule cases...")
    oracle_inputs = [{"full_rule_id": c["full_rule_id"], "text": c["text"]} for c in russian_rule_cases]
    oracle_outputs = oracle.check_pattern_rules(oracle_inputs)

    for case, out in zip(russian_rule_cases, oracle_outputs):
        case_text = case["text"]
        for m in out.get("matches", []):
            m["expected_from_codepoint"] = utf16_offset_to_codepoint_offset(case_text, m["from_utf16"])
            m["expected_to_codepoint"] = utf16_offset_to_codepoint_offset(case_text, m["to_utf16"])
            m["expected_pattern_from_codepoint"] = utf16_offset_to_codepoint_offset(case_text, m["pattern_from_utf16"])
            m["expected_pattern_to_codepoint"] = utf16_offset_to_codepoint_offset(case_text, m["pattern_to_utf16"])
        case["oracle_result"] = out

    # Build genuine feature coverage mapping directly from each rule's actual feature usage
    real_feature_coverage: Dict[str, Any] = {}
    for case in russian_rule_cases:
        for feat in case.get("rule_features", []):
            feat_key = f"feature:{feat}"
            if feat_key not in real_feature_coverage:
                real_feature_coverage[feat_key] = {
                    "feature_name": feat,
                    "covered_rule_ids": [],
                    "covered_case_ids": [],
                }
            if case["full_rule_id"] not in real_feature_coverage[feat_key]["covered_rule_ids"]:
                real_feature_coverage[feat_key]["covered_rule_ids"].append(case["full_rule_id"])
            real_feature_coverage[feat_key]["covered_case_ids"].append(case["id"])

    russian_fixture_data = {
        "schema_version": "1.0.0",
        "description": "Committed LanguageTool 6.8 Java Oracle Russian Unification Rules Fixture",
        "metadata": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": oracle_build_id,
            "oracle_jar_sha256": oracle_sha,
            "generator_operation": "tools/generate_oracle_unification_fixtures.py",
            "corpus_version": "1.0.0",
            "cases_count": len(russian_rule_cases),
            "promoted_rules_count": len(uni_rules),
            "promoted_full_rule_ids": [r.full_id for r in uni_rules],
        },
        "feature_coverage": real_feature_coverage,
        "cases": russian_rule_cases,
    }

    russian_fixture_path = fixtures_dir / "oracle_unification_russian_rules.json"
    with open(russian_fixture_path, "w", encoding="utf-8") as f:
        json.dump(russian_fixture_data, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(russian_rule_cases)} cases to {russian_fixture_path}")

    # 2. Generate oracle_unification_synthetic.json (discriminating synthetic cases)
    print(f"Querying Java Oracle for {len(DISCRIMINATING_SYNTHETIC_UNIFICATION_CASES)} discriminating synthetic unification cases...")
    syn_oracle_outputs = oracle.check_synthetic_pattern_rules(SYNTHETIC_UNIFICATION_RULES_XML, DISCRIMINATING_SYNTHETIC_UNIFICATION_CASES)

    synthetic_feature_coverage: Dict[str, List[str]] = {f: [] for f in REQUIRED_SYNTHETIC_UNIFICATION_FEATURES}

    synthetic_cases = []
    for case, out in zip(DISCRIMINATING_SYNTHETIC_UNIFICATION_CASES, syn_oracle_outputs):
        c_dict = dict(case)
        raw_text = c_dict["text"]
        clean_text = strip_injection_tags(raw_text)

        for m in out.get("matches", []):
            m["expected_from_codepoint"] = utf16_offset_to_codepoint_offset(clean_text, m["from_utf16"])
            m["expected_to_codepoint"] = utf16_offset_to_codepoint_offset(clean_text, m["to_utf16"])
            m["expected_pattern_from_codepoint"] = utf16_offset_to_codepoint_offset(clean_text, m["pattern_from_utf16"])
            m["expected_pattern_to_codepoint"] = utf16_offset_to_codepoint_offset(clean_text, m["pattern_to_utf16"])

        c_dict["oracle_result"] = out
        synthetic_cases.append(c_dict)

        for feat in c_dict.get("features", []):
            if feat in synthetic_feature_coverage:
                synthetic_feature_coverage[feat].append(c_dict["id"])

    # Verify that all required synthetic feature families have at least one case
    uncovered = {k for k, v in synthetic_feature_coverage.items() if len(v) == 0}
    if uncovered:
        raise ValueError(f"Uncovered synthetic feature families: {uncovered}")

    synthetic_fixture_data = {
        "schema_version": "1.0.0",
        "description": "Committed LanguageTool 6.8 Java Oracle Unification Pattern Matching Synthetic Fixture",
        "synthetic_rules_xml": SYNTHETIC_UNIFICATION_RULES_XML,
        "metadata": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": oracle_build_id,
            "oracle_jar_sha256": oracle_sha,
            "generator_operation": "tools/generate_oracle_unification_fixtures.py",
            "corpus_version": "1.0.0",
            "cases_count": len(synthetic_cases),
        },
        "feature_coverage": synthetic_feature_coverage,
        "cases": synthetic_cases,
    }

    synthetic_fixture_path = fixtures_dir / "oracle_unification_synthetic.json"
    with open(synthetic_fixture_path, "w", encoding="utf-8") as f:
        json.dump(synthetic_fixture_data, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(synthetic_cases)} synthetic cases to {synthetic_fixture_path}")


if __name__ == "__main__":
    generate_unification_fixtures()
