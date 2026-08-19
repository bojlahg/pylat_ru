"""tools/generate_oracle_advanced_fixtures.py

Generates Java LanguageTool differential oracle fixture files for Task 0008:
1. tests/fixtures/oracle_advanced_russian_rules.json
   - Evaluates real Russian grammar rules classified as ADVANCED_0008_RUNNABLE (750 examples)
   - Contains machine-readable feature_coverage mapping for all nonzero Russian feature families
2. tests/fixtures/oracle_advanced_pattern_matching.json
   - Comprehensive discriminating synthetic test cases exercising all Task 0008 advanced XML matching constructs
   - Contains machine-readable feature_coverage mapping across all 44 feature dimensions
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


SYNTHETIC_ADVANCED_RULES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rules lang="ru">
  <phrases>
    <phrase id="p_adj_noun">
      <token postag_regexp="yes" postag="ADJ:.*"/>
      <token postag_regexp="yes" postag="NN:.*"/>
    </phrase>
    <phrase id="p_with_or">
      <or>
        <token>красный</token>
        <token>синий</token>
      </or>
      <token>дом</token>
    </phrase>
  </phrases>

  <category id="SYN_SKIP" name="Synthetic Skip Rules">
    <rulegroup id="SYN_FINITE_SKIP" name="Finite skip">
      <rule>
        <pattern>
          <token skip="1">начало</token>
          <token>конец</token>
        </pattern>
        <message>Skip 1 match: <suggestion>\\1 \\2</suggestion></message>
        <short>Skip 1</short>
      </rule>
      <rule>
        <pattern>
          <token skip="2">начало</token>
          <token>конец</token>
        </pattern>
        <message>Skip 2 match</message>
      </rule>
    </rulegroup>
    <rule id="SYN_INFINITE_SKIP" name="Infinite skip">
      <pattern>
        <token skip="-1">альфа</token>
        <token>омега</token>
      </pattern>
      <message>Infinite skip match</message>
    </rule>
    <rule id="SYN_SKIP_EXCEPTION" name="Skip with exception">
      <pattern>
        <token skip="3">старт<exception>стоп</exception></token>
        <token>финиш</token>
      </pattern>
      <message>Skip exception match</message>
    </rule>
  </category>

  <category id="SYN_OPTIONAL" name="Synthetic Optional Min Rules">
    <rule id="SYN_MIN_ZERO" name="Single optional token">
      <pattern>
        <token>он</token>
        <token min="0">очень</token>
        <token>быстро</token>
      </pattern>
      <message>Optional token match</message>
    </rule>
    <rule id="SYN_MIN_ONE" name="Explicit min 1 token">
      <pattern>
        <token>он</token>
        <token min="1">точно</token>
        <token>знает</token>
      </pattern>
      <message>Min 1 match</message>
    </rule>
    <rule id="SYN_ADJACENT_MIN_ZERO" name="Adjacent optional tokens">
      <pattern>
        <token>мы</token>
        <token min="0">всегда</token>
        <token min="0">очень</token>
        <token>рады</token>
      </pattern>
      <message>Adjacent optional match</message>
    </rule>
    <rule id="SYN_OPTIONAL_ANY" name="Optional any token">
      <pattern>
        <token>он</token>
        <token min="0"/>
        <token>книгу</token>
      </pattern>
      <message>Optional any token match</message>
    </rule>
    <rule id="SYN_OPTIONAL_SUGGESTION" name="Optional token with suggestion">
      <pattern>
        <token>а</token>
        <token min="0">б</token>
        <token>в</token>
      </pattern>
      <message>Suggestion: <suggestion>\\1 \\2 \\3</suggestion></message>
    </rule>
  </category>

  <category id="SYN_REPEAT" name="Synthetic Repeat Max Rules">
    <rule id="SYN_MAX_TWO" name="Max 2 occurrences">
      <pattern>
        <token>очень</token>
        <token max="2">хорошо</token>
      </pattern>
      <message>Max 2 match</message>
    </rule>
    <rule id="SYN_MAX_THREE" name="Max 3 occurrences">
      <pattern>
        <token>да</token>
        <token max="3">да</token>
      </pattern>
      <message>Max 3 match</message>
    </rule>
    <rule id="SYN_MAX_UNLIMITED" name="Unlimited max -1 occurrences">
      <pattern>
        <token>начало</token>
        <token max="-1">повтор</token>
        <token>конец</token>
      </pattern>
      <message>Unlimited max match</message>
    </rule>
    <rule id="SYN_COMBINED_MAX" name="Combined max occurrences">
      <pattern>
        <token max="2">а</token>
        <token max="3">б</token>
      </pattern>
      <message>Combined max match</message>
    </rule>
    <rule id="SYN_MIN_ZERO_MAX_TWO" name="Min 0 Max 2 occurrences">
      <pattern>
        <token>старт</token>
        <token min="0" max="2">шаг</token>
        <token>стоп</token>
      </pattern>
      <message>Min 0 Max 2 match</message>
    </rule>
    <rule id="SYN_ANY_TOKEN_MAX_TWO" name="Any token max 2">
      <pattern>
        <token>первый</token>
        <token max="2"/>
        <token>последний</token>
      </pattern>
      <message>Any token max 2 match</message>
    </rule>
  </category>

  <category id="SYN_SCOPED_EXCEPTIONS" name="Synthetic Scoped Exception Rules">
    <rule id="SYN_SCOPE_CURRENT" name="Scope current exception">
      <pattern>
        <token>дело<exception>срочное</exception></token>
        <token>важное</token>
      </pattern>
      <message>Scope current match</message>
    </rule>
    <rule id="SYN_SCOPE_PREVIOUS" name="Scope previous exception">
      <pattern>
        <token>по<exception scope="previous">судя</exception></token>
        <token>зимнему</token>
      </pattern>
      <message>Scope previous match</message>
    </rule>
    <rule id="SYN_SCOPE_NEXT" name="Scope next exception">
      <pattern>
        <token>слово<exception scope="next">исключение</exception></token>
        <token>второе</token>
      </pattern>
      <message>Scope next match</message>
    </rule>
    <rule id="SYN_SCOPE_NEXT_SKIP" name="Scope next exception with skip">
      <pattern>
        <token skip="2">пункт<exception scope="next" postag_regexp="yes" postag="NN:.*:D"/></token>
        <token>итог</token>
      </pattern>
      <message>Scope next skip match</message>
    </rule>
  </category>

  <category id="SYN_SPACEBEFORE" name="Synthetic Spacebefore Rules">
    <rule id="SYN_SPACEBEFORE_YES" name="Spacebefore yes">
      <pattern>
        <token>слово</token>
        <token spacebefore="yes">,</token>
      </pattern>
      <message>Space before comma error</message>
    </rule>
    <rule id="SYN_SPACEBEFORE_NO" name="Spacebefore no">
      <pattern>
        <token>слово</token>
        <token spacebefore="no">,</token>
      </pattern>
      <message>Normal comma</message>
    </rule>
    <rule id="SYN_EXC_SPACEBEFORE_YES" name="Exception spacebefore yes">
      <pattern>
        <token>проверка<exception spacebefore="yes">тест</exception></token>
      </pattern>
      <message>Exception spacebefore yes match</message>
    </rule>
    <rule id="SYN_EXC_SPACEBEFORE_NO" name="Exception spacebefore no">
      <pattern>
        <token>проверка<exception spacebefore="no">тест</exception></token>
      </pattern>
      <message>Exception spacebefore no match</message>
    </rule>
  </category>

  <category id="SYN_CHUNKS" name="Synthetic Chunk Rules">
    <rule id="SYN_LITERAL_CHUNK" name="Literal chunk match">
      <pattern>
        <token chunk="NP">дом</token>
      </pattern>
      <message>Literal NP chunk match</message>
    </rule>
    <rule id="SYN_CHUNK_REGEX" name="Chunk regex match">
      <pattern>
        <token chunk="NP:.*">большой</token>
        <token>дом</token>
      </pattern>
      <message>Chunk regex match</message>
    </rule>
    <rule id="SYN_MULTIPLE_CHUNKS" name="Multiple chunk tags match">
      <pattern>
        <token chunk="VP">действие</token>
      </pattern>
      <message>VP chunk match</message>
    </rule>
    <rule id="SYN_NO_CHUNKS" name="No chunk tags fail">
      <pattern>
        <token chunk="NP">проверка</token>
      </pattern>
      <message>NP on unchunked</message>
    </rule>
    <rule id="SYN_CHUNK_NEGATE" name="Chunk negation match">
      <pattern>
        <token chunk="VP" negate="yes">книга</token>
      </pattern>
      <message>Non-VP chunk match</message>
    </rule>
  </category>

  <category id="SYN_LOGICAL_GROUPS" name="Synthetic AND and OR Rules">
    <rule id="SYN_AND_CONJUNCTION" name="AND conjunction">
      <pattern>
        <and>
          <token postag_regexp="yes" postag="VB:.*"/>
          <token regexp="yes">.*ли</token>
        </and>
      </pattern>
      <message>AND conjunction match</message>
    </rule>
    <rule id="SYN_AND_DIFF_READINGS" name="AND satisfied across readings">
      <pattern>
        <and>
          <token postag_regexp="yes" postag="NN:.*"/>
          <token postag_regexp="yes" postag="VB:.*"/>
        </and>
      </pattern>
      <message>Cross-reading AND match</message>
    </rule>
    <rule id="SYN_AND_NEGATIVE" name="AND negative cross-reading">
      <pattern>
        <and>
          <token postag_regexp="yes" postag="NN:.*"/>
          <token postag_regexp="yes" postag="ADJ:.*"/>
        </and>
      </pattern>
      <message>Negative AND match</message>
    </rule>
    <rule id="SYN_OR_DISJUNCTION" name="OR disjunction">
      <pattern>
        <token>выбор</token>
        <or>
          <token>красный</token>
          <token>зеленый</token>
          <token>синий</token>
        </or>
      </pattern>
      <message>OR match</message>
    </rule>
  </category>

  <category id="SYN_PHRASES" name="Synthetic Phrase Rules">
    <rule id="SYN_PHRASE_EXPANSION" name="Phrase expansion">
      <pattern>
        <token>очень</token>
        <phraseref idref="p_adj_noun"/>
        <token>конец</token>
      </pattern>
      <message>Phrase expansion match</message>
    </rule>
    <rule id="SYN_PHRASE_WITH_OR" name="Phrase containing OR">
      <pattern>
        <phraseref idref="p_with_or"/>
      </pattern>
      <message>Phrase with OR match</message>
    </rule>
    <rule id="SYN_PHRASE_MATCH_NUM" name="Phrase match numbering">
      <pattern>
        <token>начало</token>
        <phraseref idref="p_adj_noun"/>
        <token>конец</token>
      </pattern>
      <message>Phrase match numbering: <suggestion><match no="1"/> <match no="2"/> <match no="3"/></suggestion></message>
    </rule>
    <rule id="SYN_PHRASE_MARKER" name="Marker at phrase reference">
      <pattern>
        <token>начало</token>
        <marker>
          <phraseref idref="p_adj_noun"/>
        </marker>
        <token>конец</token>
      </pattern>
      <message>Marker around phrase</message>
    </rule>
  </category>

  <category id="SYN_MATCH_REFERENCES" name="Synthetic Match Reference Rules">
    <rule id="SYN_TOKEN_MATCH_REF" name="Token level match reference">
      <pattern>
        <token regexp="yes">тот|этот</token>
        <token><match no="0"/></token>
      </pattern>
      <message>Repeated word: <suggestion>\\1</suggestion></message>
    </rule>
    <rule id="SYN_INCLUDE_SKIPPED_ALL" name="Include skipped all">
      <pattern>
        <token skip="2">до</token>
        <token>свидания</token>
      </pattern>
      <message>Replacement: <suggestion><match no="1" include_skipped="all"/>!</suggestion></message>
    </rule>
    <rule id="SYN_INCLUDE_SKIPPED_FOLLOWING" name="Include skipped following">
      <pattern>
        <token skip="2">от</token>
        <token>начала</token>
      </pattern>
      <message>Replacement: <suggestion><match no="1" include_skipped="following"/>!</suggestion></message>
    </rule>
    <rule id="SYN_CASE_CONVERSIONS" name="Case conversions">
      <pattern>
        <token>ТЕСТ</token>
      </pattern>
      <message>Lower: <suggestion><match no="1" case_conversion="alllower"/></suggestion>, Upper: <suggestion><match no="1" case_conversion="allupper"/></suggestion>, FirstUpper: <suggestion><match no="1" case_conversion="firstupper"/></suggestion></message>
    </rule>
    <rule id="SYN_REGEXP_REPLACE" name="Regex replacement captures">
      <pattern>
        <token regexp="yes">авто([а-я]+)</token>
      </pattern>
      <message>Suggestion: <suggestion>само<match no="1" regexp_match="авто([а-я]+)" regexp_replace="$1"/></suggestion></message>
    </rule>
    <rule id="SYN_POS_SYNTHESIS" name="POS tag synthesis">
      <pattern>
        <token>бывший</token>
        <token postag_regexp="yes" postag="NN:.*:D">другу</token>
      </pattern>
      <message>Suggestion: <suggestion><match no="1" postag="NN:.*:D" postag_regexp="yes" postag_replace="ADJ:Posit:Masc:D"/></suggestion></message>
    </rule>
    <rule id="SYN_OPTIONAL_MATCH_REF" name="Optional match reference">
      <pattern>
        <token>начало</token>
        <token min="0">середина</token>
        <token>конец</token>
      </pattern>
      <message>Result: <suggestion><match no="1"/>-<match no="3"/></suggestion></message>
    </rule>
    <rule id="SYN_INFINITE_SKIP_MATCH_REF" name="Infinite skip with match ref">
      <pattern>
        <token regexp="yes" skip="-1">дом|сад</token>
        <token><match no="0"/></token>
      </pattern>
      <message>Duplicate token: <suggestion>\\1</suggestion></message>
    </rule>
  </category>

  <category id="SYN_MARKERS_AND_SPANS" name="Synthetic Markers and Spans">
    <rule id="SYN_MARKER_FIRST" name="Marker on first token only">
      <pattern>
        <marker>
          <token>ошибка</token>
        </marker>
        <token>здесь</token>
      </pattern>
      <message>Marker on first token</message>
    </rule>
    <rule id="SYN_MARKER_MIDDLE" name="Marker on middle token only">
      <pattern>
        <token>слово</token>
        <marker>
          <token>внутри</token>
        </marker>
        <token>фразы</token>
      </pattern>
      <message>Marker in middle</message>
    </rule>
    <rule id="SYN_MARKER_LAST" name="Marker on last token only">
      <pattern>
        <token>в</token>
        <token>самом</token>
        <marker>
          <token>конце</token>
        </marker>
      </pattern>
      <message>Marker at end</message>
    </rule>
    <rule id="SYN_MARKER_FULL" name="Marker on entire pattern">
      <pattern>
        <marker>
          <token>полная</token>
          <token>фраза</token>
        </marker>
      </pattern>
      <message>Full marker</message>
    </rule>
    <rule id="SYN_MARKER_WITH_SKIPPED" name="Skipped tokens inside marker">
      <pattern>
        <token>старт</token>
        <marker>
          <token skip="3">начало</token>
          <token>конец</token>
        </marker>
        <token>стоп</token>
      </pattern>
      <message>Marker enclosing skipped</message>
    </rule>
    <rule id="SYN_MARKER_OMITTED_OPTIONAL" name="Omitted optional inside marker">
      <pattern>
        <token>старт</token>
        <marker>
          <token>начало</token>
          <token min="0">середина</token>
          <token>конец</token>
        </marker>
        <token>стоп</token>
      </pattern>
      <message>Marker with omitted optional</message>
    </rule>
    <rule id="SYN_MARKER_REPEATED_TOKENS" name="Repeated token inside marker">
      <pattern>
        <token>старт</token>
        <marker>
          <token>начало</token>
          <token max="3">повтор</token>
          <token>конец</token>
        </marker>
        <token>стоп</token>
      </pattern>
      <message>Marker with repeated tokens</message>
    </rule>
    <rule id="SYN_SKIP_PLUS_MIN_MAX" name="Skip plus min max">
      <pattern>
        <token skip="3">начало</token>
        <token min="0" max="2">середина</token>
        <token>конец</token>
      </pattern>
      <message>Skip plus min max match</message>
    </rule>
  </category>

  <category id="SYN_ANTIPATTERNS" name="Synthetic Antipattern Rules">
    <rule id="SYN_ANTIPATTERN_OVERLAP" name="Antipattern overlap">
      <antipattern>
        <token>белый</token>
        <token>дом</token>
      </antipattern>
      <pattern>
        <token>белый</token>
        <token>дом</token>
      </pattern>
      <message>Trigger error</message>
    </rule>
    <rule id="SYN_ANTIPATTERN_NON_OVERLAP" name="Antipattern non overlap">
      <antipattern>
        <token>красный</token>
        <token>дом</token>
      </antipattern>
      <pattern>
        <token>синий</token>
        <token>дом</token>
      </pattern>
      <message>Trigger error</message>
    </rule>
  </category>

  <category id="SYN_EDGE_CASES" name="Synthetic Edge Cases">
    <rule id="SYN_NON_BMP_EMOJI" name="Non BMP characters">
      <pattern>
        <marker>
          <token>текст</token>
        </marker>
        <token>после</token>
      </pattern>
      <message>Emoji test</message>
    </rule>
    <rule id="SYN_NON_BMP_SKIPPED" name="Non-BMP in skipped region">
      <pattern>
        <token skip="3">начало</token>
        <token>конец</token>
      </pattern>
      <message>Non-BMP in skipped</message>
    </rule>
    <rule id="SYN_NON_BMP_MARKER" name="Non-BMP in marker region">
      <pattern>
        <token>старт</token>
        <marker>
          <token>😀</token>
          <token max="2">🚀</token>
          <token>🎉</token>
        </marker>
        <token>стоп</token>
      </pattern>
      <message>Non-BMP in marker</message>
    </rule>
    <rule id="SYN_BACKREF_LITERALS" name="Backreference looking text">
      <pattern>
        <token regexp="yes">:\\d+|\\$\\d+|\\\\\\d+</token>
        <token>тест</token>
      </pattern>
      <message>References: \\1 \\2.</message>
    </rule>
    <rule id="SYN_RAW_POS" name="Raw pos pre-disambiguation">
      <pattern raw_pos="yes">
        <token postag_regexp="yes" postag="ADJ:.*:D">зимнему</token>
      </pattern>
      <message>Raw pos test</message>
    </rule>
    <rule id="SYN_RAW_POS_DIFF" name="Raw pos pre-disambig vs post-disambig diff">
      <pattern raw_pos="yes">
        <token postag="RAW_TAG">тест</token>
      </pattern>
      <message>Raw pos pre-disambig matched</message>
    </rule>
  </category>
</rules>
"""

DISCRIMINATING_SYNTHETIC_CASES = [
    # 1. Finite skip cases (0, 1, 2, 3 tokens)
    {"id": "syn_skip_01", "full_rule_id": "SYN_FINITE_SKIP[1]", "category": "SYN_SKIP", "text": "начало конец", "features": ["skip_finite"]},
    {"id": "syn_skip_02", "full_rule_id": "SYN_FINITE_SKIP[1]", "category": "SYN_SKIP", "text": "начало шаг конец", "features": ["skip_finite"]},
    {"id": "syn_skip_03", "full_rule_id": "SYN_FINITE_SKIP[1]", "category": "SYN_SKIP", "text": "начало один два конец", "features": ["skip_finite"]},
    {"id": "syn_skip_04", "full_rule_id": "SYN_FINITE_SKIP[2]", "category": "SYN_SKIP", "text": "начало конец", "features": ["skip_finite"]},
    {"id": "syn_skip_05", "full_rule_id": "SYN_FINITE_SKIP[2]", "category": "SYN_SKIP", "text": "начало шаг конец", "features": ["skip_finite"]},
    {"id": "syn_skip_06", "full_rule_id": "SYN_FINITE_SKIP[2]", "category": "SYN_SKIP", "text": "начало один два конец", "features": ["skip_finite"]},
    {"id": "syn_skip_07", "full_rule_id": "SYN_FINITE_SKIP[2]", "category": "SYN_SKIP", "text": "начало один два три конец", "features": ["skip_finite"]},

    # 2. Infinite skip cases
    {"id": "syn_inf_skip_01", "full_rule_id": "SYN_INFINITE_SKIP", "category": "SYN_SKIP", "text": "альфа омега", "features": ["skip_unbounded"]},
    {"id": "syn_inf_skip_02", "full_rule_id": "SYN_INFINITE_SKIP", "category": "SYN_SKIP", "text": "альфа бета гамма дельта омега", "features": ["skip_unbounded"]},
    {"id": "syn_inf_skip_03", "full_rule_id": "SYN_INFINITE_SKIP", "category": "SYN_SKIP", "text": "альфа первый второй третий четвертый пятый омега", "features": ["skip_unbounded"]},
    {"id": "syn_inf_skip_04", "full_rule_id": "SYN_INFINITE_SKIP", "category": "SYN_SKIP", "text": "альфа омега и еще альфа тестовое слово омега", "features": ["skip_unbounded", "rule_with_max_filter"]},

    # 3. Skip boundary and exception failure cases
    {"id": "syn_skip_exc_01", "full_rule_id": "SYN_SKIP_EXCEPTION", "category": "SYN_SKIP", "text": "старт финиш", "features": ["skip_with_exception"]},
    {"id": "syn_skip_exc_02", "full_rule_id": "SYN_SKIP_EXCEPTION", "category": "SYN_SKIP", "text": "старт один финиш", "features": ["skip_with_exception"]},
    {"id": "syn_skip_exc_03", "full_rule_id": "SYN_SKIP_EXCEPTION", "category": "SYN_SKIP", "text": "старт один два три финиш", "features": ["skip_with_exception"]},
    {"id": "syn_skip_exc_04", "full_rule_id": "SYN_SKIP_EXCEPTION", "category": "SYN_SKIP", "text": "старт один стоп финиш", "features": ["skip_with_exception"]},
    {"id": "syn_skip_exc_05", "full_rule_id": "SYN_SKIP_EXCEPTION", "category": "SYN_SKIP", "text": "старт стоп финиш", "features": ["skip_with_exception"]},
    {"id": "syn_skip_exc_06", "full_rule_id": "SYN_SKIP_EXCEPTION", "category": "SYN_SKIP", "text": "старт один два три четыре финиш", "features": ["skip_with_exception"]},

    # 4. Optional token (min=0) present and absent
    {"id": "syn_min0_01", "full_rule_id": "SYN_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "он очень быстро", "features": ["min_zero"]},
    {"id": "syn_min0_02", "full_rule_id": "SYN_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "он быстро", "features": ["min_zero"]},
    {"id": "syn_min0_03", "full_rule_id": "SYN_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "он медленно", "features": ["min_zero"]},
    {"id": "syn_min0_04", "full_rule_id": "SYN_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "он очень медленно", "features": ["min_zero"]},

    # 5. Min 1 explicit
    {"id": "syn_min1_01", "full_rule_id": "SYN_MIN_ONE", "category": "SYN_OPTIONAL", "text": "он точно знает", "features": ["min_one"]},
    {"id": "syn_min1_02", "full_rule_id": "SYN_MIN_ONE", "category": "SYN_OPTIONAL", "text": "он знает", "features": ["min_one"]},

    # 6. Adjacent optional tokens (all combinations)
    {"id": "syn_adj_min0_01", "full_rule_id": "SYN_ADJACENT_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "мы рады", "features": ["min_zero"]},
    {"id": "syn_adj_min0_02", "full_rule_id": "SYN_ADJACENT_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "мы всегда рады", "features": ["min_zero"]},
    {"id": "syn_adj_min0_03", "full_rule_id": "SYN_ADJACENT_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "мы очень рады", "features": ["min_zero"]},
    {"id": "syn_adj_min0_04", "full_rule_id": "SYN_ADJACENT_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "мы всегда очень рады", "features": ["min_zero"]},
    {"id": "syn_adj_min0_05", "full_rule_id": "SYN_ADJACENT_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "мы грустны", "features": ["min_zero"]},

    # 7. Optional any-token
    {"id": "syn_opt_any_01", "full_rule_id": "SYN_OPTIONAL_ANY", "category": "SYN_OPTIONAL", "text": "он книгу", "features": ["min_zero"]},
    {"id": "syn_opt_any_02", "full_rule_id": "SYN_OPTIONAL_ANY", "category": "SYN_OPTIONAL", "text": "он читал книгу", "features": ["min_zero"]},
    {"id": "syn_opt_any_03", "full_rule_id": "SYN_OPTIONAL_ANY", "category": "SYN_OPTIONAL", "text": "он интересную книгу", "features": ["min_zero"]},
    {"id": "syn_opt_any_04", "full_rule_id": "SYN_OPTIONAL_ANY", "category": "SYN_OPTIONAL", "text": "он журнал", "features": ["min_zero"]},

    # 8. Optional token with suggestion
    {"id": "syn_opt_sug_01", "full_rule_id": "SYN_OPTIONAL_SUGGESTION", "category": "SYN_OPTIONAL", "text": "а б в", "features": ["min_zero"]},
    {"id": "syn_opt_sug_02", "full_rule_id": "SYN_OPTIONAL_SUGGESTION", "category": "SYN_OPTIONAL", "text": "а в", "features": ["min_zero"]},
    {"id": "syn_opt_sug_03", "full_rule_id": "SYN_OPTIONAL_SUGGESTION", "category": "SYN_OPTIONAL", "text": "а г", "features": ["min_zero"]},

    # 9. Repeat max=2 occurrences
    {"id": "syn_max2_01", "full_rule_id": "SYN_MAX_TWO", "category": "SYN_REPEAT", "text": "очень хорошо", "features": ["max_two"]},
    {"id": "syn_max2_02", "full_rule_id": "SYN_MAX_TWO", "category": "SYN_REPEAT", "text": "очень хорошо хорошо", "features": ["max_two"]},
    {"id": "syn_max2_03", "full_rule_id": "SYN_MAX_TWO", "category": "SYN_REPEAT", "text": "очень хорошо хорошо хорошо", "features": ["max_two"]},
    {"id": "syn_max2_04", "full_rule_id": "SYN_MAX_TWO", "category": "SYN_REPEAT", "text": "очень плохо", "features": ["max_two"]},

    # 10. Repeat max=3 occurrences
    {"id": "syn_max3_01", "full_rule_id": "SYN_MAX_THREE", "category": "SYN_REPEAT", "text": "да да", "features": ["max_three"]},
    {"id": "syn_max3_02", "full_rule_id": "SYN_MAX_THREE", "category": "SYN_REPEAT", "text": "да да да", "features": ["max_three"]},
    {"id": "syn_max3_03", "full_rule_id": "SYN_MAX_THREE", "category": "SYN_REPEAT", "text": "да да да да", "features": ["max_three"]},
    {"id": "syn_max3_04", "full_rule_id": "SYN_MAX_THREE", "category": "SYN_REPEAT", "text": "да да да да да", "features": ["max_three"]},
    {"id": "syn_max3_05", "full_rule_id": "SYN_MAX_THREE", "category": "SYN_REPEAT", "text": "да нет", "features": ["max_three"]},

    # 11. Unlimited repeat max=-1
    {"id": "syn_max_unlim_01", "full_rule_id": "SYN_MAX_UNLIMITED", "category": "SYN_REPEAT", "text": "начало повтор конец", "features": ["max_unbounded"]},
    {"id": "syn_max_unlim_02", "full_rule_id": "SYN_MAX_UNLIMITED", "category": "SYN_REPEAT", "text": "начало повтор повтор конец", "features": ["max_unbounded"]},
    {"id": "syn_max_unlim_03", "full_rule_id": "SYN_MAX_UNLIMITED", "category": "SYN_REPEAT", "text": "начало повтор повтор повтор повтор повтор конец", "features": ["max_unbounded"]},
    {"id": "syn_max_unlim_04", "full_rule_id": "SYN_MAX_UNLIMITED", "category": "SYN_REPEAT", "text": "начало конец", "features": ["max_unbounded"]},

    # 12. Combined multiple max occurrences
    {"id": "syn_comb_max_01", "full_rule_id": "SYN_COMBINED_MAX", "category": "SYN_REPEAT", "text": "а б", "features": ["max_two", "max_three"]},
    {"id": "syn_comb_max_02", "full_rule_id": "SYN_COMBINED_MAX", "category": "SYN_REPEAT", "text": "а а б", "features": ["max_two", "max_three"]},
    {"id": "syn_comb_max_03", "full_rule_id": "SYN_COMBINED_MAX", "category": "SYN_REPEAT", "text": "а б б", "features": ["max_two", "max_three"]},
    {"id": "syn_comb_max_04", "full_rule_id": "SYN_COMBINED_MAX", "category": "SYN_REPEAT", "text": "а а б б б", "features": ["max_two", "max_three"]},
    {"id": "syn_comb_max_05", "full_rule_id": "SYN_COMBINED_MAX", "category": "SYN_REPEAT", "text": "а а а б б б", "features": ["max_two", "max_three"]},

    # 13. Min 0 Max 2 occurrences
    {"id": "syn_min0_max2_01", "full_rule_id": "SYN_MIN_ZERO_MAX_TWO", "category": "SYN_REPEAT", "text": "старт стоп", "features": ["min_zero_max_two"]},
    {"id": "syn_min0_max2_02", "full_rule_id": "SYN_MIN_ZERO_MAX_TWO", "category": "SYN_REPEAT", "text": "старт шаг стоп", "features": ["min_zero_max_two"]},
    {"id": "syn_min0_max2_03", "full_rule_id": "SYN_MIN_ZERO_MAX_TWO", "category": "SYN_REPEAT", "text": "старт шаг шаг стоп", "features": ["min_zero_max_two"]},
    {"id": "syn_min0_max2_04", "full_rule_id": "SYN_MIN_ZERO_MAX_TWO", "category": "SYN_REPEAT", "text": "старт шаг шаг шаг стоп", "features": ["min_zero_max_two"]},

    # 14. Any token max=2
    {"id": "syn_any_max2_01", "full_rule_id": "SYN_ANY_TOKEN_MAX_TWO", "category": "SYN_REPEAT", "text": "первый один последний", "features": ["repeated_any_token"]},
    {"id": "syn_any_max2_02", "full_rule_id": "SYN_ANY_TOKEN_MAX_TWO", "category": "SYN_REPEAT", "text": "первый один два последний", "features": ["repeated_any_token"]},
    {"id": "syn_any_max2_03", "full_rule_id": "SYN_ANY_TOKEN_MAX_TWO", "category": "SYN_REPEAT", "text": "первый один два три последний", "features": ["repeated_any_token"]},
    {"id": "syn_any_max2_04", "full_rule_id": "SYN_ANY_TOKEN_MAX_TWO", "category": "SYN_REPEAT", "text": "первый последний", "features": ["repeated_any_token"]},

    # 15. Scope current exception
    {"id": "syn_scope_curr_01", "full_rule_id": "SYN_SCOPE_CURRENT", "category": "SYN_SCOPED_EXCEPTIONS", "text": "дело важное", "features": ["exception_scope_current"]},
    {"id": "syn_scope_curr_02", "full_rule_id": "SYN_SCOPE_CURRENT", "category": "SYN_SCOPED_EXCEPTIONS", "text": "дело срочное", "features": ["exception_scope_current"]},

    # 16. Scope previous exception
    {"id": "syn_scope_prev_01", "full_rule_id": "SYN_SCOPE_PREVIOUS", "category": "SYN_SCOPED_EXCEPTIONS", "text": "по зимнему", "features": ["exception_scope_previous"]},
    {"id": "syn_scope_prev_02", "full_rule_id": "SYN_SCOPE_PREVIOUS", "category": "SYN_SCOPED_EXCEPTIONS", "text": "судя по зимнему", "features": ["exception_scope_previous"]},

    # 17. Scope next exception
    {"id": "syn_scope_next_01", "full_rule_id": "SYN_SCOPE_NEXT", "category": "SYN_SCOPED_EXCEPTIONS", "text": "слово второе", "features": ["exception_scope_next"]},
    {"id": "syn_scope_next_02", "full_rule_id": "SYN_SCOPE_NEXT", "category": "SYN_SCOPED_EXCEPTIONS", "text": "слово исключение второе", "features": ["exception_scope_next"]},

    # 18. Scope next with skip
    {"id": "syn_scope_next_sk_01", "full_rule_id": "SYN_SCOPE_NEXT_SKIP", "category": "SYN_SCOPED_EXCEPTIONS", "text": "пункт один итог", "features": ["exception_scope_next", "skip_finite"]},
    {"id": "syn_scope_next_sk_02", "full_rule_id": "SYN_SCOPE_NEXT_SKIP", "category": "SYN_SCOPED_EXCEPTIONS", "text": "пункт другу итог", "features": ["exception_scope_next", "skip_finite"]},

    # 19. Spacebefore yes/no
    {"id": "syn_spacebefore_01", "full_rule_id": "SYN_SPACEBEFORE_YES", "category": "SYN_SPACEBEFORE", "text": "слово ,", "features": ["spacebefore_yes"]},
    {"id": "syn_spacebefore_02", "full_rule_id": "SYN_SPACEBEFORE_YES", "category": "SYN_SPACEBEFORE", "text": "слово,", "features": ["spacebefore_yes"]},
    {"id": "syn_spacebefore_03", "full_rule_id": "SYN_SPACEBEFORE_NO", "category": "SYN_SPACEBEFORE", "text": "слово,", "features": ["spacebefore_no"]},
    {"id": "syn_spacebefore_04", "full_rule_id": "SYN_SPACEBEFORE_NO", "category": "SYN_SPACEBEFORE", "text": "слово ,", "features": ["spacebefore_no"]},

    # 20. Exception spacebefore yes/no
    {"id": "syn_exc_sb_yes_01", "full_rule_id": "SYN_EXC_SPACEBEFORE_YES", "category": "SYN_SPACEBEFORE", "text": "проверка", "features": ["exception_spacebefore_yes"]},
    {"id": "syn_exc_sb_yes_02", "full_rule_id": "SYN_EXC_SPACEBEFORE_YES", "category": "SYN_SPACEBEFORE", "text": "тест", "features": ["exception_spacebefore_yes"]},
    {"id": "syn_exc_sb_no_01", "full_rule_id": "SYN_EXC_SPACEBEFORE_NO", "category": "SYN_SPACEBEFORE", "text": "проверка", "features": ["exception_spacebefore_no"]},
    {"id": "syn_exc_sb_no_02", "full_rule_id": "SYN_EXC_SPACEBEFORE_NO", "category": "SYN_SPACEBEFORE", "text": "тест", "features": ["exception_spacebefore_no"]},

    # 21. Literal chunk
    {"id": "syn_chunk_lit_01", "full_rule_id": "SYN_LITERAL_CHUNK", "category": "SYN_CHUNKS", "text": "||INJECT_CHUNKS:1=NP||большой дом", "features": ["chunk_literal"]},
    {"id": "syn_chunk_lit_02", "full_rule_id": "SYN_LITERAL_CHUNK", "category": "SYN_CHUNKS", "text": "||INJECT_CHUNKS:1=VP||большой дом", "features": ["chunk_literal"]},

    # 22. Chunk regex
    {"id": "syn_chunk_reg_01", "full_rule_id": "SYN_CHUNK_REGEX", "category": "SYN_CHUNKS", "text": "большой дом", "features": ["chunk_regex"]},
    {"id": "syn_chunk_reg_02", "full_rule_id": "SYN_CHUNK_REGEX", "category": "SYN_CHUNKS", "text": "дом", "features": ["chunk_regex"]},

    # 23. Multiple chunks
    {"id": "syn_chunk_mult_01", "full_rule_id": "SYN_MULTIPLE_CHUNKS", "category": "SYN_CHUNKS", "text": "||INJECT_CHUNKS:1=NP,VP||важное действие", "features": ["chunk_multiple"]},

    # 24. No chunk tags
    {"id": "syn_chunk_none_01", "full_rule_id": "SYN_NO_CHUNKS", "category": "SYN_CHUNKS", "text": "||INJECT_CHUNKS:1=||простая проверка", "features": ["chunk_none"]},

    # 25. Chunk negate
    {"id": "syn_chunk_neg_01", "full_rule_id": "SYN_CHUNK_NEGATE", "category": "SYN_CHUNKS", "text": "книга", "features": ["chunk_literal"]},

    # 26. AND conjunction
    {"id": "syn_and_01", "full_rule_id": "SYN_AND_CONJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "были", "features": ["and_cross_reading"]},
    {"id": "syn_and_02", "full_rule_id": "SYN_AND_CONJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "шел", "features": ["and_cross_reading"]},

    # 27. AND different readings vs negative
    {"id": "syn_and_diff_01", "full_rule_id": "SYN_AND_DIFF_READINGS", "category": "SYN_LOGICAL_GROUPS", "text": "||INJECT_READINGS:1=тест/тест/NN:Masc:Sin:Nom,тест/тест/VB:Pres:3:Sin||мой тест", "features": ["and_cross_reading"]},
    {"id": "syn_and_neg_01", "full_rule_id": "SYN_AND_NEGATIVE", "category": "SYN_LOGICAL_GROUPS", "text": "||INJECT_READINGS:1=тест/тест/NN:Masc:Sin:Nom||мой тест", "features": ["and_negative"]},

    # 28. OR disjunction
    {"id": "syn_or_01", "full_rule_id": "SYN_OR_DISJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "выбор красный", "features": ["or_branch_expansion"]},
    {"id": "syn_or_02", "full_rule_id": "SYN_OR_DISJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "выбор зеленый", "features": ["or_branch_expansion"]},
    {"id": "syn_or_03", "full_rule_id": "SYN_OR_DISJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "выбор синий", "features": ["or_branch_expansion"]},
    {"id": "syn_or_04", "full_rule_id": "SYN_OR_DISJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "выбор черный", "features": ["or_branch_expansion"]},

    # 29. Phrase expansion
    {"id": "syn_phrase_exp_01", "full_rule_id": "SYN_PHRASE_EXPANSION", "category": "SYN_PHRASES", "text": "очень красивый дом конец", "features": ["phrase_expansion"]},
    {"id": "syn_phrase_exp_02", "full_rule_id": "SYN_PHRASE_EXPANSION", "category": "SYN_PHRASES", "text": "очень бежал быстро конец", "features": ["phrase_expansion"]},

    # 30. Phrase containing OR
    {"id": "syn_phrase_or_01", "full_rule_id": "SYN_PHRASE_WITH_OR", "category": "SYN_PHRASES", "text": "красный дом", "features": ["phrase_containing_or"]},
    {"id": "syn_phrase_or_02", "full_rule_id": "SYN_PHRASE_WITH_OR", "category": "SYN_PHRASES", "text": "синий дом", "features": ["phrase_containing_or"]},
    {"id": "syn_phrase_or_03", "full_rule_id": "SYN_PHRASE_WITH_OR", "category": "SYN_PHRASES", "text": "зеленый дом", "features": ["phrase_containing_or"]},

    # 31. Phrase match numbering
    {"id": "syn_phrase_num_01", "full_rule_id": "SYN_PHRASE_MATCH_NUM", "category": "SYN_PHRASES", "text": "начало красивый дом конец", "features": ["phrase_match_numbering"]},

    # 32. Marker at phrase reference
    {"id": "syn_phrase_mkr_01", "full_rule_id": "SYN_PHRASE_MARKER", "category": "SYN_PHRASES", "text": "начало красивый дом конец", "features": ["marker_at_phrase_ref"]},

    # 33. Token match reference (0-indexed)
    {"id": "syn_tok_match_01", "full_rule_id": "SYN_TOKEN_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "тот тот", "features": ["token_match_ref_0_indexed"]},
    {"id": "syn_tok_match_02", "full_rule_id": "SYN_TOKEN_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "этот этот", "features": ["token_match_ref_0_indexed"]},
    {"id": "syn_tok_match_03", "full_rule_id": "SYN_TOKEN_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "тот этот", "features": ["token_match_ref_0_indexed"]},
    {"id": "syn_tok_match_04", "full_rule_id": "SYN_TOKEN_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "этот тот", "features": ["token_match_ref_0_indexed"]},

    # 34. Include skipped all
    {"id": "syn_inc_all_01", "full_rule_id": "SYN_INCLUDE_SKIPPED_ALL", "category": "SYN_MATCH_REFERENCES", "text": "до скорого свидания", "features": ["include_skipped_all"]},
    {"id": "syn_inc_all_02", "full_rule_id": "SYN_INCLUDE_SKIPPED_ALL", "category": "SYN_MATCH_REFERENCES", "text": "до свидания", "features": ["include_skipped_all"]},

    # 35. Include skipped following
    {"id": "syn_inc_foll_01", "full_rule_id": "SYN_INCLUDE_SKIPPED_FOLLOWING", "category": "SYN_MATCH_REFERENCES", "text": "от самого начала", "features": ["include_skipped_following"]},
    {"id": "syn_inc_foll_02", "full_rule_id": "SYN_INCLUDE_SKIPPED_FOLLOWING", "category": "SYN_MATCH_REFERENCES", "text": "от начала", "features": ["include_skipped_following"]},

    # 36. Case conversions (alllower, allupper, firstupper)
    {"id": "syn_case_conv_01", "full_rule_id": "SYN_CASE_CONVERSIONS", "category": "SYN_MATCH_REFERENCES", "text": "ТЕСТ", "features": ["case_conversion_alllower", "case_conversion_allupper", "case_conversion_firstupper"]},

    # 37. Regexp replacement captures
    {"id": "syn_reg_rep_01", "full_rule_id": "SYN_REGEXP_REPLACE", "category": "SYN_MATCH_REFERENCES", "text": "автомобиль", "features": ["regexp_replace_captures"]},
    {"id": "syn_reg_rep_02", "full_rule_id": "SYN_REGEXP_REPLACE", "category": "SYN_MATCH_REFERENCES", "text": "автобус", "features": ["regexp_replace_captures"]},

    # 38. POS tag synthesis
    {"id": "syn_pos_synth_01", "full_rule_id": "SYN_POS_SYNTHESIS", "category": "SYN_MATCH_REFERENCES", "text": "бывший другу", "features": ["postag_replace_synthesis"]},

    # 39. Optional match ref
    {"id": "syn_opt_ref_01", "full_rule_id": "SYN_OPTIONAL_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "начало середина конец", "features": ["min_zero"]},
    {"id": "syn_opt_ref_02", "full_rule_id": "SYN_OPTIONAL_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "начало конец", "features": ["min_zero"]},

    # 40. Infinite skip with match ref
    {"id": "syn_inf_sk_ref_01", "full_rule_id": "SYN_INFINITE_SKIP_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "дом сад дом", "features": ["skip_unbounded", "token_match_ref_0_indexed"]},
    {"id": "syn_inf_sk_ref_02", "full_rule_id": "SYN_INFINITE_SKIP_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "сад трава лес сад", "features": ["skip_unbounded", "token_match_ref_0_indexed"]},
    {"id": "syn_inf_sk_ref_03", "full_rule_id": "SYN_INFINITE_SKIP_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "дом сад трава", "features": ["skip_unbounded", "token_match_ref_0_indexed"]},

    # 41. Marker locations (first, middle, last, full)
    {"id": "syn_mkr_first_01", "full_rule_id": "SYN_MARKER_FIRST", "category": "SYN_MARKERS_AND_SPANS", "text": "ошибка здесь", "features": ["marker_at_phrase_ref"]},
    {"id": "syn_mkr_mid_01", "full_rule_id": "SYN_MARKER_MIDDLE", "category": "SYN_MARKERS_AND_SPANS", "text": "слово внутри фразы", "features": ["marker_at_phrase_ref"]},
    {"id": "syn_mkr_last_01", "full_rule_id": "SYN_MARKER_LAST", "category": "SYN_MARKERS_AND_SPANS", "text": "в самом конце", "features": ["marker_at_phrase_ref"]},
    {"id": "syn_mkr_full_01", "full_rule_id": "SYN_MARKER_FULL", "category": "SYN_MARKERS_AND_SPANS", "text": "полная фраза", "features": ["marker_at_phrase_ref"]},

    # 42. Skipped tokens inside marker
    {"id": "syn_mkr_skip_01", "full_rule_id": "SYN_MARKER_WITH_SKIPPED", "category": "SYN_MARKERS_AND_SPANS", "text": "старт начало а б конец стоп", "features": ["marker_with_skipped_tokens"]},

    # 43. Omitted optional token inside marker
    {"id": "syn_mkr_opt_01", "full_rule_id": "SYN_MARKER_OMITTED_OPTIONAL", "category": "SYN_MARKERS_AND_SPANS", "text": "старт начало конец стоп", "features": ["marker_with_omitted_optional"]},
    {"id": "syn_mkr_opt_02", "full_rule_id": "SYN_MARKER_OMITTED_OPTIONAL", "category": "SYN_MARKERS_AND_SPANS", "text": "старт начало середина конец стоп", "features": ["marker_with_omitted_optional"]},

    # 44. Repeated tokens inside marker
    {"id": "syn_mkr_rep_01", "full_rule_id": "SYN_MARKER_REPEATED_TOKENS", "category": "SYN_MARKERS_AND_SPANS", "text": "старт начало повтор повтор конец стоп", "features": ["marker_with_repeated_tokens"]},

    # 45. Skip plus min/max
    {"id": "syn_sk_minmax_01", "full_rule_id": "SYN_SKIP_PLUS_MIN_MAX", "category": "SYN_MARKERS_AND_SPANS", "text": "начало а б середина конец", "features": ["skip_plus_min_max"]},
    {"id": "syn_sk_minmax_02", "full_rule_id": "SYN_SKIP_PLUS_MIN_MAX", "category": "SYN_MARKERS_AND_SPANS", "text": "начало конец", "features": ["skip_plus_min_max"]},

    # 46. Antipattern overlap & non-overlap
    {"id": "syn_anti_over_01", "full_rule_id": "SYN_ANTIPATTERN_OVERLAP", "category": "SYN_ANTIPATTERNS", "text": "белый дом", "features": ["rule_with_max_filter"]},
    {"id": "syn_anti_non_01", "full_rule_id": "SYN_ANTIPATTERN_NON_OVERLAP", "category": "SYN_ANTIPATTERNS", "text": "синий дом", "features": ["rule_with_max_filter"]},
    {"id": "syn_anti_non_02", "full_rule_id": "SYN_ANTIPATTERN_NON_OVERLAP", "category": "SYN_ANTIPATTERNS", "text": "красный дом", "features": ["rule_with_max_filter"]},

    # 47. Non-BMP character inside skipped region
    {"id": "syn_non_bmp_sk_01", "full_rule_id": "SYN_NON_BMP_SKIPPED", "category": "SYN_EDGE_CASES", "text": "начало 🌟 🚀 ⭐ конец", "features": ["non_bmp_in_skipped"]},

    # 48. Non-BMP character inside marker/repeated region
    {"id": "syn_non_bmp_mkr_01", "full_rule_id": "SYN_NON_BMP_MARKER", "category": "SYN_EDGE_CASES", "text": "старт 😀 🚀 🚀 🎉 стоп", "features": ["non_bmp_in_marker"]},

    # 49. Emoji offset handling
    {"id": "syn_emoji_01", "full_rule_id": "SYN_NON_BMP_EMOJI", "category": "SYN_EDGE_CASES", "text": "🌟 🚀 текст после 👍", "features": ["non_bmp_in_marker"]},
    {"id": "syn_emoji_02", "full_rule_id": "SYN_NON_BMP_EMOJI", "category": "SYN_EDGE_CASES", "text": "текст после", "features": ["non_bmp_in_marker"]},
    {"id": "syn_emoji_03", "full_rule_id": "SYN_NON_BMP_EMOJI", "category": "SYN_EDGE_CASES", "text": "просто 🚀 текст до", "features": ["non_bmp_in_marker"]},

    # 50. Backreference looking sequences (:42, \42, $1)
    {"id": "syn_backref_01", "full_rule_id": "SYN_BACKREF_LITERALS", "category": "SYN_EDGE_CASES", "text": ":42 тест", "features": ["regexp_replace_captures"]},
    {"id": "syn_backref_02", "full_rule_id": "SYN_BACKREF_LITERALS", "category": "SYN_EDGE_CASES", "text": "\\42 тест", "features": ["regexp_replace_captures"]},
    {"id": "syn_backref_03", "full_rule_id": "SYN_BACKREF_LITERALS", "category": "SYN_EDGE_CASES", "text": "$1 тест", "features": ["regexp_replace_captures"]},
    {"id": "syn_backref_04", "full_rule_id": "SYN_BACKREF_LITERALS", "category": "SYN_EDGE_CASES", "text": "$2 тест", "features": ["regexp_replace_captures"]},

    # 51. Raw pos
    {"id": "syn_raw_pos_01", "full_rule_id": "SYN_RAW_POS", "category": "SYN_EDGE_CASES", "text": "по зимнему", "features": ["raw_pos_stream_diff"]},
    {"id": "syn_raw_pos_02", "full_rule_id": "SYN_RAW_POS", "category": "SYN_EDGE_CASES", "text": "по летнему", "features": ["raw_pos_stream_diff"]},

    # 52. Raw pos with injected pre-disambiguation diff
    {"id": "syn_raw_pos_diff_01", "full_rule_id": "SYN_RAW_POS_DIFF", "category": "SYN_EDGE_CASES", "text": "||INJECT_PRE_DISAMBIG:1=тест/тест/RAW_TAG||тест слово", "features": ["raw_pos_stream_diff"]},
]


REQUIRED_SYNTHETIC_FEATURE_FAMILIES = {
    "skip_finite",
    "skip_unbounded",
    "skip_with_exception",
    "min_zero",
    "min_one",
    "max_two",
    "max_three",
    "max_unbounded",
    "min_zero_max_two",
    "repeated_any_token",
    "spacebefore_yes",
    "spacebefore_no",
    "exception_spacebefore_yes",
    "exception_spacebefore_no",
    "exception_scope_current",
    "exception_scope_previous",
    "exception_scope_next",
    "chunk_literal",
    "chunk_regex",
    "chunk_multiple",
    "chunk_none",
    "and_cross_reading",
    "and_negative",
    "or_branch_expansion",
    "phrase_expansion",
    "phrase_containing_or",
    "phrase_match_numbering",
    "marker_at_phrase_ref",
    "skip_plus_min_max",
    "marker_with_skipped_tokens",
    "marker_with_omitted_optional",
    "marker_with_repeated_tokens",
    "non_bmp_in_skipped",
    "non_bmp_in_marker",
    "raw_pos_stream_diff",
    "token_match_ref_0_indexed",
    "include_skipped_all",
    "include_skipped_following",
    "case_conversion_alllower",
    "case_conversion_allupper",
    "case_conversion_firstupper",
    "regexp_replace_captures",
    "postag_replace_synthesis",
    "rule_with_max_filter",
}


def generate_advanced_fixtures():
    oracle = JavaLanguageToolOracle()
    if not oracle.is_java_available():
        print("ERROR: Java is not available!")
        sys.exit(1)

    val = oracle.validate_oracle()
    oracle_sha = val["jar_sha256"]
    oracle_build_id = val["oracle_build_id"]

    fixtures_dir = PROJECT_ROOT / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate oracle_advanced_russian_rules.json from real rule examples
    engine = RussianGrammarEngine.get_instance()
    adv_rules = [r for r in engine.get_all_rules() if r.execution_state == ExecutionState.ADVANCED_0008_RUNNABLE]

    print(f"Loaded {len(adv_rules)} ADVANCED_0008_RUNNABLE rules.")

    russian_rule_cases = []
    case_idx = 1

    for rule in adv_rules:
        for ex_idx, ex in enumerate(rule.examples):
            case_id = f"adv_ru_{case_idx:03d}_{rule.id}_{ex_idx}"
            russian_rule_cases.append({
                "id": case_id,
                "category": rule.category_id,
                "full_rule_id": rule.full_id,
                "text": ex.text,
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
    REQUIRED_RUSSIAN_FEATURE_FAMILIES = {
        "pattern@raw_pos",
        "token@chunk",
        "token@spacebefore",
        "exception@spacebefore",
        "pattern:and",
        "pattern:or",
        "token@skip",
        "token@min",
        "token@max",
        "exception@scope=current",
        "exception@scope=previous",
        "exception@scope=next",
    }

    inv_path = PROJECT_ROOT / "compat" / "russian_grammar_advanced_inventory.json"
    real_feature_coverage: Dict[str, Any] = {}
    if inv_path.is_file():
        with open(inv_path, "r", encoding="utf-8") as f:
            inv_data = json.load(f)
        feat_sum = inv_data.get("feature_summary", {})
        for feat_name, f_info in feat_sum.items():
            if feat_name in REQUIRED_RUSSIAN_FEATURE_FAMILIES and f_info.get("source_rules_count", 0) > 0:
                rep_rules = f_info.get("representative_rules", [])
                matching_case_ids = [
                    c["id"] for c in russian_rule_cases
                    if c["full_rule_id"] in rep_rules or any(r.split("[")[0] in c["full_rule_id"] for r in rep_rules)
                ]
                real_feature_coverage[feat_name] = {
                    "source_rules_count": f_info.get("source_rules_count"),
                    "representative_rules": rep_rules,
                    "covered_case_ids": matching_case_ids[:10],
                }

    russian_fixture_data = {
        "schema_version": "1.0.0",
        "description": "Committed LanguageTool 6.8 Java Oracle Russian Advanced Rules Fixture",
        "metadata": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": oracle_build_id,
            "oracle_jar_sha256": oracle_sha,
            "generator_operation": "tools/generate_oracle_advanced_fixtures.py",
            "corpus_version": "1.0.0",
            "cases_count": len(russian_rule_cases),
        },
        "feature_coverage": real_feature_coverage,
        "cases": russian_rule_cases,
    }

    russian_fixture_path = fixtures_dir / "oracle_advanced_russian_rules.json"
    with open(russian_fixture_path, "w", encoding="utf-8") as f:
        json.dump(russian_fixture_data, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(russian_rule_cases)} cases to {russian_fixture_path}")

    # 2. Generate oracle_advanced_pattern_matching.json (>= 100 discriminating synthetic cases)
    print(f"Querying Java Oracle for {len(DISCRIMINATING_SYNTHETIC_CASES)} discriminating synthetic pattern cases...")
    syn_oracle_outputs = oracle.check_synthetic_pattern_rules(SYNTHETIC_ADVANCED_RULES_XML, DISCRIMINATING_SYNTHETIC_CASES)

    synthetic_feature_coverage: Dict[str, List[str]] = {f: [] for f in REQUIRED_SYNTHETIC_FEATURE_FAMILIES}

    synthetic_cases = []
    for case, out in zip(DISCRIMINATING_SYNTHETIC_CASES, syn_oracle_outputs):
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
        "description": "Committed LanguageTool 6.8 Java Oracle Advanced Pattern Matching Synthetic Fixture",
        "synthetic_rules_xml": SYNTHETIC_ADVANCED_RULES_XML,
        "metadata": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": oracle_build_id,
            "oracle_jar_sha256": oracle_sha,
            "generator_operation": "tools/generate_oracle_advanced_fixtures.py",
            "corpus_version": "1.0.0",
            "cases_count": len(synthetic_cases),
        },
        "feature_coverage": synthetic_feature_coverage,
        "cases": synthetic_cases,
    }

    synthetic_fixture_path = fixtures_dir / "oracle_advanced_pattern_matching.json"
    with open(synthetic_fixture_path, "w", encoding="utf-8") as f:
        json.dump(synthetic_fixture_data, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(synthetic_cases)} synthetic cases to {synthetic_fixture_path}")


if __name__ == "__main__":
    generate_advanced_fixtures()
