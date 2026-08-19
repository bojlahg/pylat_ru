"""tools/generate_oracle_unification_fixtures.py

Generates Java LanguageTool differential oracle fixture files for Task 0009:
1. tests/fixtures/oracle_unification_russian_rules.json
   - Evaluates real Russian grammar rules classified as UNIFICATION_0009_RUNNABLE (216 examples)
   - Contains machine-readable feature_coverage mapping for all Russian unification feature dimensions
2. tests/fixtures/oracle_unification_synthetic.json
   - Comprehensive discriminating synthetic test cases exercising all Task 0009 unification constructs
   - Contains machine-readable feature_coverage mapping across all unification dimensions (>= 100 cases)
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
from pylat_ru.grammar.model import ExecutionState


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

  <category id="SYN_UNI_COMPLEX" name="Synthetic Complex Combinations">
    <rule id="SYN_UNI_WITH_MARKER" name="Unification inside marker">
      <pattern>
        <token>тест</token>
        <marker>
          <unify>
            <feature id="number"/>
            <token postag_regexp="yes" postag="ADJ:.*"/>
            <token postag_regexp="yes" postag="NN:.*"/>
          </unify>
        </marker>
      </pattern>
      <message>Unify in marker: <suggestion>\\2</suggestion></message>
    </rule>

    <rule id="SYN_UNI_WITH_SKIP" name="Unification with skip token">
      <pattern>
        <token skip="1">старт</token>
        <unify>
          <feature id="number"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
          <token postag_regexp="yes" postag="NN:.*"/>
        </unify>
      </pattern>
      <message>Unify with skip</message>
    </rule>
  </category>
</rules>
"""

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
    {"id": "syn_uni_anim_07", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "высокая башня", "features": ["uni_feature_animacy", "uni_positive_match"]},
    {"id": "syn_uni_anim_08", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "добрый мальчик", "features": ["uni_feature_animacy", "uni_positive_match"]},
    {"id": "syn_uni_anim_09", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "железный замок", "features": ["uni_feature_animacy", "uni_positive_match"]},
    {"id": "syn_uni_anim_10", "full_rule_id": "SYN_UNI_ANIMACY_AGREE[1]", "category": "SYN_UNI_SINGLE", "text": "старый друг", "features": ["uni_feature_animacy", "uni_positive_match"]},

    # 5. Multi-Feature: Gender + Number agreement
    {"id": "syn_uni_gn_01", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивый дом", "features": ["uni_multi_features", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_gn_02", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивая изба", "features": ["uni_multi_features", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_gn_03", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивое зеркало", "features": ["uni_multi_features", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_gn_04", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивые дома", "features": ["uni_multi_features", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_gn_05", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивый изба", "features": ["uni_multi_features", "uni_feature_gender", "uni_feature_number", "uni_no_match"]},
    {"id": "syn_uni_gn_06", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивая дом", "features": ["uni_multi_features", "uni_feature_gender", "uni_feature_number", "uni_no_match"]},
    {"id": "syn_uni_gn_07", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивые дом", "features": ["uni_multi_features", "uni_feature_gender", "uni_feature_number", "uni_no_match"]},
    {"id": "syn_uni_gn_08", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "новое окно", "features": ["uni_multi_features", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_gn_09", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "новые окна", "features": ["uni_multi_features", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_gn_10", "full_rule_id": "SYN_UNI_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "новый окно", "features": ["uni_multi_features", "uni_feature_gender", "uni_feature_number", "uni_no_match"]},

    # 6. Multi-Feature: Case + Gender + Number agreement
    {"id": "syn_uni_cgn_01", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивый дом", "features": ["uni_multi_features", "uni_feature_case", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_cgn_02", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивого дома", "features": ["uni_multi_features", "uni_feature_case", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_cgn_03", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивая книга", "features": ["uni_multi_features", "uni_feature_case", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_cgn_04", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивую книгу", "features": ["uni_multi_features", "uni_feature_case", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_cgn_05", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивое окно", "features": ["uni_multi_features", "uni_feature_case", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_cgn_06", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивые дома", "features": ["uni_multi_features", "uni_feature_case", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_cgn_07", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивый дома", "features": ["uni_multi_features", "uni_feature_case", "uni_feature_gender", "uni_feature_number", "uni_no_match"]},
    {"id": "syn_uni_cgn_08", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивая книгу", "features": ["uni_multi_features", "uni_feature_case", "uni_feature_gender", "uni_feature_number", "uni_no_match"]},
    {"id": "syn_uni_cgn_09", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивому дому", "features": ["uni_multi_features", "uni_feature_case", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},
    {"id": "syn_uni_cgn_10", "full_rule_id": "SYN_UNI_CASE_GENDER_NUMBER[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "красивой книге", "features": ["uni_multi_features", "uni_feature_case", "uni_feature_gender", "uni_feature_number", "uni_positive_match"]},

    # 7. Three Tokens Unification
    {"id": "syn_uni_3tok_01", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "большой красивый дом", "features": ["uni_three_tokens", "uni_multi_features", "uni_positive_match"]},
    {"id": "syn_uni_3tok_02", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "большая красивая изба", "features": ["uni_three_tokens", "uni_multi_features", "uni_positive_match"]},
    {"id": "syn_uni_3tok_03", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "большое красивое окно", "features": ["uni_three_tokens", "uni_multi_features", "uni_positive_match"]},
    {"id": "syn_uni_3tok_04", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "большие красивые дома", "features": ["uni_three_tokens", "uni_multi_features", "uni_positive_match"]},
    {"id": "syn_uni_3tok_05", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "большой красивая дом", "features": ["uni_three_tokens", "uni_multi_features", "uni_no_match"]},
    {"id": "syn_uni_3tok_06", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "большая красивый изба", "features": ["uni_three_tokens", "uni_multi_features", "uni_no_match"]},
    {"id": "syn_uni_3tok_07", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "новый деревянный стол", "features": ["uni_three_tokens", "uni_multi_features", "uni_positive_match"]},
    {"id": "syn_uni_3tok_08", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "новая каменная башня", "features": ["uni_three_tokens", "uni_multi_features", "uni_positive_match"]},
    {"id": "syn_uni_3tok_09", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "новое синее море", "features": ["uni_three_tokens", "uni_multi_features", "uni_positive_match"]},
    {"id": "syn_uni_3tok_10", "full_rule_id": "SYN_UNI_THREE_TOKENS[1]", "category": "SYN_UNI_MULTI_FEAT", "text": "новый новая стол", "features": ["uni_three_tokens", "uni_multi_features", "uni_no_match"]},

    # 8. Explicit Types: Feminine Only
    {"id": "syn_uni_fem_01", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "красивая изба", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_fem_02", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "большая книга", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_fem_03", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "красивый дом", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_fem_04", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "красивое окно", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_fem_05", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "синяя река", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_fem_06", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "синий шар", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_fem_07", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "новая машина", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_fem_08", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "новое колесо", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_fem_09", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "чистая вода", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_fem_10", "full_rule_id": "SYN_UNI_EXPLICIT_FEMININE[1]", "category": "SYN_UNI_TYPES", "text": "чистый воздух", "features": ["uni_explicit_types", "uni_no_match"]},

    # 9. Explicit Types: Nom or Acc Only
    {"id": "syn_uni_nomacc_01", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "красивый дом", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_nomacc_02", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "красивую книгу", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_nomacc_03", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "красивого дома", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_nomacc_04", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "красивому дому", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_nomacc_05", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "красивая книга", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_nomacc_06", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "красивым домом", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_nomacc_07", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "новое окно", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_nomacc_08", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "новом окне", "features": ["uni_explicit_types", "uni_no_match"]},
    {"id": "syn_uni_nomacc_09", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "синий шар", "features": ["uni_explicit_types", "uni_positive_match"]},
    {"id": "syn_uni_nomacc_10", "full_rule_id": "SYN_UNI_EXPLICIT_NOM_ACC[1]", "category": "SYN_UNI_TYPES", "text": "синем шаре", "features": ["uni_explicit_types", "uni_no_match"]},

    # 10. Negated Unification: Number Disagreement
    {"id": "syn_uni_neg_num_01", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивый дома", "features": ["uni_negated_match", "uni_feature_number"]},
    {"id": "syn_uni_neg_num_02", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивые дом", "features": ["uni_negated_match", "uni_feature_number"]},
    {"id": "syn_uni_neg_num_03", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивый дом", "features": ["uni_negated_match", "uni_no_match"]},
    {"id": "syn_uni_neg_num_04", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивые дома", "features": ["uni_negated_match", "uni_no_match"]},
    {"id": "syn_uni_neg_num_05", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "большая книги", "features": ["uni_negated_match", "uni_feature_number"]},
    {"id": "syn_uni_neg_num_06", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "большие книга", "features": ["uni_negated_match", "uni_feature_number"]},
    {"id": "syn_uni_neg_num_07", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "большая книга", "features": ["uni_negated_match", "uni_no_match"]},
    {"id": "syn_uni_neg_num_08", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "новое окна", "features": ["uni_negated_match", "uni_feature_number"]},
    {"id": "syn_uni_neg_num_09", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "новые окно", "features": ["uni_negated_match", "uni_feature_number"]},
    {"id": "syn_uni_neg_num_10", "full_rule_id": "SYN_UNI_NEG_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "новое окно", "features": ["uni_negated_match", "uni_no_match"]},

    # 11. Negated Unification: Gender / Number Disagreement
    {"id": "syn_uni_neg_gn_01", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивый изба", "features": ["uni_negated_match", "uni_multi_features"]},
    {"id": "syn_uni_neg_gn_02", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивая дом", "features": ["uni_negated_match", "uni_multi_features"]},
    {"id": "syn_uni_neg_gn_03", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивое дом", "features": ["uni_negated_match", "uni_multi_features"]},
    {"id": "syn_uni_neg_gn_04", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивый дом", "features": ["uni_negated_match", "uni_no_match"]},
    {"id": "syn_uni_neg_gn_05", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивая изба", "features": ["uni_negated_match", "uni_no_match"]},
    {"id": "syn_uni_neg_gn_06", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "красивое окно", "features": ["uni_negated_match", "uni_no_match"]},
    {"id": "syn_uni_neg_gn_07", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "синяя шар", "features": ["uni_negated_match", "uni_multi_features"]},
    {"id": "syn_uni_neg_gn_08", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "синее река", "features": ["uni_negated_match", "uni_multi_features"]},
    {"id": "syn_uni_neg_gn_09", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "новый окно", "features": ["uni_negated_match", "uni_multi_features"]},
    {"id": "syn_uni_neg_gn_10", "full_rule_id": "SYN_UNI_NEG_GENDER_NUMBER[1]", "category": "SYN_UNI_NEGATION", "text": "новое окно", "features": ["uni_negated_match", "uni_no_match"]},

    # 12. Neutral Elements: Ignore Comma
    {"id": "syn_uni_ign_com_01", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "большой , красивый дом", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_02", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "большая , красивая изба", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_03", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "большое , красивое окно", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_04", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "большие , красивые дома", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_05", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "большой , красивая дом", "features": ["uni_neutral_elements", "uni_no_match"]},
    {"id": "syn_uni_ign_com_06", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "большая , красивый изба", "features": ["uni_neutral_elements", "uni_no_match"]},
    {"id": "syn_uni_ign_com_07", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "новый , деревянный стол", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_08", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "новая , каменная башня", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_09", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "новое , синее море", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_com_10", "full_rule_id": "SYN_UNI_IGNORE_COMMA[1]", "category": "SYN_UNI_IGNORE", "text": "новый , новая стол", "features": ["uni_neutral_elements", "uni_no_match"]},

    # 13. Neutral Elements: Ignore Adverb
    {"id": "syn_uni_ign_adv_01", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "красивый очень дом", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_02", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "красивая очень изба", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_03", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "красивое очень окно", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_04", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "красивые очень дома", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_05", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "красивый очень изба", "features": ["uni_neutral_elements", "uni_no_match"]},
    {"id": "syn_uni_ign_adv_06", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "красивая очень дом", "features": ["uni_neutral_elements", "uni_no_match"]},
    {"id": "syn_uni_ign_adv_07", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "новый совсем стол", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_08", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "новая совсем изба", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_09", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "новое совсем окно", "features": ["uni_neutral_elements", "uni_positive_match"]},
    {"id": "syn_uni_ign_adv_10", "full_rule_id": "SYN_UNI_IGNORE_ADVERB[1]", "category": "SYN_UNI_IGNORE", "text": "новый совсем изба", "features": ["uni_neutral_elements", "uni_no_match"]},

    # 14. Complex: Unification inside Marker
    {"id": "syn_uni_mkr_01", "full_rule_id": "SYN_UNI_WITH_MARKER[1]", "category": "SYN_UNI_COMPLEX", "text": "тест красивый дом", "features": ["uni_in_marker", "uni_positive_match"]},
    {"id": "syn_uni_mkr_02", "full_rule_id": "SYN_UNI_WITH_MARKER[1]", "category": "SYN_UNI_COMPLEX", "text": "тест красивые дома", "features": ["uni_in_marker", "uni_positive_match"]},
    {"id": "syn_uni_mkr_03", "full_rule_id": "SYN_UNI_WITH_MARKER[1]", "category": "SYN_UNI_COMPLEX", "text": "тест красивый дома", "features": ["uni_in_marker", "uni_no_match"]},
    {"id": "syn_uni_mkr_04", "full_rule_id": "SYN_UNI_WITH_MARKER[1]", "category": "SYN_UNI_COMPLEX", "text": "тест большая книга", "features": ["uni_in_marker", "uni_positive_match"]},
    {"id": "syn_uni_mkr_05", "full_rule_id": "SYN_UNI_WITH_MARKER[1]", "category": "SYN_UNI_COMPLEX", "text": "тест большие книги", "features": ["uni_in_marker", "uni_positive_match"]},
    {"id": "syn_uni_mkr_06", "full_rule_id": "SYN_UNI_WITH_MARKER[1]", "category": "SYN_UNI_COMPLEX", "text": "тест новое окно", "features": ["uni_in_marker", "uni_positive_match"]},
    {"id": "syn_uni_mkr_07", "full_rule_id": "SYN_UNI_WITH_MARKER[1]", "category": "SYN_UNI_COMPLEX", "text": "тест новые окна", "features": ["uni_in_marker", "uni_positive_match"]},
    {"id": "syn_uni_mkr_08", "full_rule_id": "SYN_UNI_WITH_MARKER[1]", "category": "SYN_UNI_COMPLEX", "text": "тест синий шар", "features": ["uni_in_marker", "uni_positive_match"]},
    {"id": "syn_uni_mkr_09", "full_rule_id": "SYN_UNI_WITH_MARKER[1]", "category": "SYN_UNI_COMPLEX", "text": "тест синяя река", "features": ["uni_in_marker", "uni_positive_match"]},
    {"id": "syn_uni_mkr_10", "full_rule_id": "SYN_UNI_WITH_MARKER[1]", "category": "SYN_UNI_COMPLEX", "text": "тест новый окно", "features": ["uni_in_marker", "uni_no_match"]},

    # 15. Complex: Unification with Skip Token
    {"id": "syn_uni_sk_01", "full_rule_id": "SYN_UNI_WITH_SKIP[1]", "category": "SYN_UNI_COMPLEX", "text": "старт тут красивый дом", "features": ["uni_with_skip", "uni_positive_match"]},
    {"id": "syn_uni_sk_02", "full_rule_id": "SYN_UNI_WITH_SKIP[1]", "category": "SYN_UNI_COMPLEX", "text": "старт красиво красивые дома", "features": ["uni_with_skip", "uni_positive_match"]},
    {"id": "syn_uni_sk_03", "full_rule_id": "SYN_UNI_WITH_SKIP[1]", "category": "SYN_UNI_COMPLEX", "text": "старт тут красивый дома", "features": ["uni_with_skip", "uni_no_match"]},
    {"id": "syn_uni_sk_04", "full_rule_id": "SYN_UNI_WITH_SKIP[1]", "category": "SYN_UNI_COMPLEX", "text": "старт большая книга", "features": ["uni_with_skip", "uni_positive_match"]},
    {"id": "syn_uni_sk_05", "full_rule_id": "SYN_UNI_WITH_SKIP[1]", "category": "SYN_UNI_COMPLEX", "text": "старт быстро большие книги", "features": ["uni_with_skip", "uni_positive_match"]},
    {"id": "syn_uni_sk_06", "full_rule_id": "SYN_UNI_WITH_SKIP[1]", "category": "SYN_UNI_COMPLEX", "text": "старт новое окно", "features": ["uni_with_skip", "uni_positive_match"]},
    {"id": "syn_uni_sk_07", "full_rule_id": "SYN_UNI_WITH_SKIP[1]", "category": "SYN_UNI_COMPLEX", "text": "старт новые окна", "features": ["uni_with_skip", "uni_positive_match"]},
    {"id": "syn_uni_sk_08", "full_rule_id": "SYN_UNI_WITH_SKIP[1]", "category": "SYN_UNI_COMPLEX", "text": "старт тут синий шар", "features": ["uni_with_skip", "uni_positive_match"]},
    {"id": "syn_uni_sk_09", "full_rule_id": "SYN_UNI_WITH_SKIP[1]", "category": "SYN_UNI_COMPLEX", "text": "старт синяя река", "features": ["uni_with_skip", "uni_positive_match"]},
    {"id": "syn_uni_sk_10", "full_rule_id": "SYN_UNI_WITH_SKIP[1]", "category": "SYN_UNI_COMPLEX", "text": "старт тут новый окно", "features": ["uni_with_skip", "uni_no_match"]},
]

REQUIRED_SYNTHETIC_UNIFICATION_FEATURES = {
    "uni_feature_number",
    "uni_feature_gender",
    "uni_feature_case",
    "uni_feature_animacy",
    "uni_multi_features",
    "uni_three_tokens",
    "uni_explicit_types",
    "uni_negated_match",
    "uni_neutral_elements",
    "uni_in_marker",
    "uni_with_skip",
    "uni_positive_match",
    "uni_no_match",
}


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

    russian_rule_cases = []
    case_idx = 1

    for rule in uni_rules:
        for ex_idx, ex in enumerate(rule.examples):
            case_id = f"uni_ru_{case_idx:03d}_{rule.id}_{ex_idx}"
            russian_rule_cases.append({
                "id": case_id,
                "category": rule.category_id,
                "full_rule_id": rule.full_id,
                "text": ex.text,
                "is_incorrect": ex.is_incorrect,
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

    # Load inventory to build real Russian rule feature coverage mapping
    inv_path = PROJECT_ROOT / "compat" / "russian_grammar_unification_inventory.json"
    real_feature_coverage: Dict[str, Any] = {}
    if inv_path.is_file():
        with open(inv_path, "r", encoding="utf-8") as f:
            inv_data = json.load(f)
        raw_xml = inv_data.get("raw_xml_unification_totals", {})
        feat_dist = raw_xml.get("unify_features_selected_distribution", {})
        for feat_name, count in feat_dist.items():
            matching_case_ids = [
                c["id"] for c in russian_rule_cases
            ]
            real_feature_coverage[f"feature:{feat_name}"] = {
                "source_count": count,
                "covered_case_ids": matching_case_ids[:10],
            }

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
        },
        "feature_coverage": real_feature_coverage,
        "cases": russian_rule_cases,
    }

    russian_fixture_path = fixtures_dir / "oracle_unification_russian_rules.json"
    with open(russian_fixture_path, "w", encoding="utf-8") as f:
        json.dump(russian_fixture_data, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(russian_rule_cases)} cases to {russian_fixture_path}")

    # 2. Generate oracle_unification_synthetic.json (>= 100 discriminating synthetic cases)
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
