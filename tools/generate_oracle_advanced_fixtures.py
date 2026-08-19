"""tools/generate_oracle_advanced_fixtures.py

Generates Java LanguageTool differential oracle fixture files for Task 0008:
1. tests/fixtures/oracle_advanced_russian_rules.json
   - Evaluates real Russian grammar rules classified as ADVANCED_0008_RUNNABLE (750 examples)
2. tests/fixtures/oracle_advanced_pattern_matching.json
   - >= 100 discriminating synthetic test cases exercising advanced XML matching constructs
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.differential_lt import JavaLanguageToolOracle, PINNED_LT_COMMIT, PINNED_LT_VERSION
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.model import ExecutionState

SYNTHETIC_ADVANCED_RULES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rules lang="ru">
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
  </category>

  <category id="SYN_CHUNKS" name="Synthetic Chunk Rules">
    <rule id="SYN_CHUNK_REGEX" name="Chunk regex match">
      <pattern>
        <token chunk="NP:.*">большой</token>
        <token>дом</token>
      </pattern>
      <message>Chunk regex match</message>
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
  </category>
</rules>
"""

DISCRIMINATING_SYNTHETIC_CASES = [
    # 1. Finite skip cases (0, 1, 2, 3 tokens)
    {"id": "syn_skip_01", "full_rule_id": "SYN_FINITE_SKIP[1]", "category": "SYN_SKIP", "text": "начало конец"},
    {"id": "syn_skip_02", "full_rule_id": "SYN_FINITE_SKIP[1]", "category": "SYN_SKIP", "text": "начало шаг конец"},
    {"id": "syn_skip_03", "full_rule_id": "SYN_FINITE_SKIP[1]", "category": "SYN_SKIP", "text": "начало один два конец"},
    {"id": "syn_skip_04", "full_rule_id": "SYN_FINITE_SKIP[2]", "category": "SYN_SKIP", "text": "начало конец"},
    {"id": "syn_skip_05", "full_rule_id": "SYN_FINITE_SKIP[2]", "category": "SYN_SKIP", "text": "начало шаг конец"},
    {"id": "syn_skip_06", "full_rule_id": "SYN_FINITE_SKIP[2]", "category": "SYN_SKIP", "text": "начало один два конец"},
    {"id": "syn_skip_07", "full_rule_id": "SYN_FINITE_SKIP[2]", "category": "SYN_SKIP", "text": "начало один два три конец"},

    # 2. Infinite skip cases
    {"id": "syn_inf_skip_01", "full_rule_id": "SYN_INFINITE_SKIP", "category": "SYN_SKIP", "text": "альфа омега"},
    {"id": "syn_inf_skip_02", "full_rule_id": "SYN_INFINITE_SKIP", "category": "SYN_SKIP", "text": "альфа бета гамма дельта омега"},
    {"id": "syn_inf_skip_03", "full_rule_id": "SYN_INFINITE_SKIP", "category": "SYN_SKIP", "text": "альфа первый второй третий четвертый пятый омега"},
    {"id": "syn_inf_skip_04", "full_rule_id": "SYN_INFINITE_SKIP", "category": "SYN_SKIP", "text": "альфа омега и еще альфа тестовое слово омега"},

    # 3. Skip boundary and exception failure cases
    {"id": "syn_skip_exc_01", "full_rule_id": "SYN_SKIP_EXCEPTION", "category": "SYN_SKIP", "text": "старт финиш"},
    {"id": "syn_skip_exc_02", "full_rule_id": "SYN_SKIP_EXCEPTION", "category": "SYN_SKIP", "text": "старт один финиш"},
    {"id": "syn_skip_exc_03", "full_rule_id": "SYN_SKIP_EXCEPTION", "category": "SYN_SKIP", "text": "старт один два три финиш"},
    {"id": "syn_skip_exc_04", "full_rule_id": "SYN_SKIP_EXCEPTION", "category": "SYN_SKIP", "text": "старт один стоп финиш"},
    {"id": "syn_skip_exc_05", "full_rule_id": "SYN_SKIP_EXCEPTION", "category": "SYN_SKIP", "text": "старт стоп финиш"},
    {"id": "syn_skip_exc_06", "full_rule_id": "SYN_SKIP_EXCEPTION", "category": "SYN_SKIP", "text": "старт один два три четыре финиш"},

    # 4. Optional token (min=0) present and absent
    {"id": "syn_min0_01", "full_rule_id": "SYN_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "он очень быстро"},
    {"id": "syn_min0_02", "full_rule_id": "SYN_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "он быстро"},
    {"id": "syn_min0_03", "full_rule_id": "SYN_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "он медленно"},
    {"id": "syn_min0_04", "full_rule_id": "SYN_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "он очень медленно"},

    # 5. Adjacent optional tokens (all combinations)
    {"id": "syn_adj_min0_01", "full_rule_id": "SYN_ADJACENT_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "мы рады"},
    {"id": "syn_adj_min0_02", "full_rule_id": "SYN_ADJACENT_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "мы всегда рады"},
    {"id": "syn_adj_min0_03", "full_rule_id": "SYN_ADJACENT_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "мы очень рады"},
    {"id": "syn_adj_min0_04", "full_rule_id": "SYN_ADJACENT_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "мы всегда очень рады"},
    {"id": "syn_adj_min0_05", "full_rule_id": "SYN_ADJACENT_MIN_ZERO", "category": "SYN_OPTIONAL", "text": "мы грустны"},

    # 6. Optional any-token
    {"id": "syn_opt_any_01", "full_rule_id": "SYN_OPTIONAL_ANY", "category": "SYN_OPTIONAL", "text": "он книгу"},
    {"id": "syn_opt_any_02", "full_rule_id": "SYN_OPTIONAL_ANY", "category": "SYN_OPTIONAL", "text": "он читал книгу"},
    {"id": "syn_opt_any_03", "full_rule_id": "SYN_OPTIONAL_ANY", "category": "SYN_OPTIONAL", "text": "он интересную книгу"},
    {"id": "syn_opt_any_04", "full_rule_id": "SYN_OPTIONAL_ANY", "category": "SYN_OPTIONAL", "text": "он журнал"},

    # 7. Optional token with suggestion
    {"id": "syn_opt_sug_01", "full_rule_id": "SYN_OPTIONAL_SUGGESTION", "category": "SYN_OPTIONAL", "text": "а б в"},
    {"id": "syn_opt_sug_02", "full_rule_id": "SYN_OPTIONAL_SUGGESTION", "category": "SYN_OPTIONAL", "text": "а в"},
    {"id": "syn_opt_sug_03", "full_rule_id": "SYN_OPTIONAL_SUGGESTION", "category": "SYN_OPTIONAL", "text": "а г"},

    # 8. Repeat max=2 occurrences
    {"id": "syn_max2_01", "full_rule_id": "SYN_MAX_TWO", "category": "SYN_REPEAT", "text": "очень хорошо"},
    {"id": "syn_max2_02", "full_rule_id": "SYN_MAX_TWO", "category": "SYN_REPEAT", "text": "очень хорошо хорошо"},
    {"id": "syn_max2_03", "full_rule_id": "SYN_MAX_TWO", "category": "SYN_REPEAT", "text": "очень хорошо хорошо хорошо"},
    {"id": "syn_max2_04", "full_rule_id": "SYN_MAX_TWO", "category": "SYN_REPEAT", "text": "очень плохо"},

    # 9. Repeat max=3 occurrences
    {"id": "syn_max3_01", "full_rule_id": "SYN_MAX_THREE", "category": "SYN_REPEAT", "text": "да да"},
    {"id": "syn_max3_02", "full_rule_id": "SYN_MAX_THREE", "category": "SYN_REPEAT", "text": "да да да"},
    {"id": "syn_max3_03", "full_rule_id": "SYN_MAX_THREE", "category": "SYN_REPEAT", "text": "да да да да"},
    {"id": "syn_max3_04", "full_rule_id": "SYN_MAX_THREE", "category": "SYN_REPEAT", "text": "да да да да да"},
    {"id": "syn_max3_05", "full_rule_id": "SYN_MAX_THREE", "category": "SYN_REPEAT", "text": "да нет"},

    # 10. Unlimited repeat max=-1
    {"id": "syn_max_unlim_01", "full_rule_id": "SYN_MAX_UNLIMITED", "category": "SYN_REPEAT", "text": "начало повтор конец"},
    {"id": "syn_max_unlim_02", "full_rule_id": "SYN_MAX_UNLIMITED", "category": "SYN_REPEAT", "text": "начало повтор повтор конец"},
    {"id": "syn_max_unlim_03", "full_rule_id": "SYN_MAX_UNLIMITED", "category": "SYN_REPEAT", "text": "начало повтор повтор повтор повтор повтор конец"},
    {"id": "syn_max_unlim_04", "full_rule_id": "SYN_MAX_UNLIMITED", "category": "SYN_REPEAT", "text": "начало конец"},

    # 11. Combined multiple max occurrences
    {"id": "syn_comb_max_01", "full_rule_id": "SYN_COMBINED_MAX", "category": "SYN_REPEAT", "text": "а б"},
    {"id": "syn_comb_max_02", "full_rule_id": "SYN_COMBINED_MAX", "category": "SYN_REPEAT", "text": "а а б"},
    {"id": "syn_comb_max_03", "full_rule_id": "SYN_COMBINED_MAX", "category": "SYN_REPEAT", "text": "а б б"},
    {"id": "syn_comb_max_04", "full_rule_id": "SYN_COMBINED_MAX", "category": "SYN_REPEAT", "text": "а а б б б"},
    {"id": "syn_comb_max_05", "full_rule_id": "SYN_COMBINED_MAX", "category": "SYN_REPEAT", "text": "а а а б б б"},

    # 12. Min 0 Max 2 occurrences
    {"id": "syn_min0_max2_01", "full_rule_id": "SYN_MIN_ZERO_MAX_TWO", "category": "SYN_REPEAT", "text": "старт стоп"},
    {"id": "syn_min0_max2_02", "full_rule_id": "SYN_MIN_ZERO_MAX_TWO", "category": "SYN_REPEAT", "text": "старт шаг стоп"},
    {"id": "syn_min0_max2_03", "full_rule_id": "SYN_MIN_ZERO_MAX_TWO", "category": "SYN_REPEAT", "text": "старт шаг шаг стоп"},
    {"id": "syn_min0_max2_04", "full_rule_id": "SYN_MIN_ZERO_MAX_TWO", "category": "SYN_REPEAT", "text": "старт бег стоп"},

    # 13. Any token max 2 occurrences
    {"id": "syn_any_max2_01", "full_rule_id": "SYN_ANY_TOKEN_MAX_TWO", "category": "SYN_REPEAT", "text": "первый один последний"},
    {"id": "syn_any_max2_02", "full_rule_id": "SYN_ANY_TOKEN_MAX_TWO", "category": "SYN_REPEAT", "text": "первый один два последний"},
    {"id": "syn_any_max2_03", "full_rule_id": "SYN_ANY_TOKEN_MAX_TWO", "category": "SYN_REPEAT", "text": "первый последний"},

    # 14. Scope previous exception
    {"id": "syn_sc_prev_01", "full_rule_id": "SYN_SCOPE_PREVIOUS", "category": "SYN_SCOPED_EXCEPTIONS", "text": "мы по зимнему"},
    {"id": "syn_sc_prev_02", "full_rule_id": "SYN_SCOPE_PREVIOUS", "category": "SYN_SCOPED_EXCEPTIONS", "text": "судя по зимнему"},
    {"id": "syn_sc_prev_03", "full_rule_id": "SYN_SCOPE_PREVIOUS", "category": "SYN_SCOPED_EXCEPTIONS", "text": "они по зимнему"},

    # 15. Scope next exception
    {"id": "syn_sc_next_01", "full_rule_id": "SYN_SCOPE_NEXT", "category": "SYN_SCOPED_EXCEPTIONS", "text": "слово обычное второе"},
    {"id": "syn_sc_next_02", "full_rule_id": "SYN_SCOPE_NEXT", "category": "SYN_SCOPED_EXCEPTIONS", "text": "слово исключение второе"},
    {"id": "syn_sc_next_03", "full_rule_id": "SYN_SCOPE_NEXT", "category": "SYN_SCOPED_EXCEPTIONS", "text": "слово исключение третье"},

    # 16. Scope next exception with skip
    {"id": "syn_sc_next_skip_01", "full_rule_id": "SYN_SCOPE_NEXT_SKIP", "category": "SYN_SCOPED_EXCEPTIONS", "text": "пункт один итог"},
    {"id": "syn_sc_next_skip_02", "full_rule_id": "SYN_SCOPE_NEXT_SKIP", "category": "SYN_SCOPED_EXCEPTIONS", "text": "пункт другу итог"},
    {"id": "syn_sc_next_skip_03", "full_rule_id": "SYN_SCOPE_NEXT_SKIP", "category": "SYN_SCOPED_EXCEPTIONS", "text": "пункт один два итог"},

    # 17. Spacebefore yes vs no
    {"id": "syn_spb_yes_01", "full_rule_id": "SYN_SPACEBEFORE_YES", "category": "SYN_SPACEBEFORE", "text": "слово ,"},
    {"id": "syn_spb_yes_02", "full_rule_id": "SYN_SPACEBEFORE_YES", "category": "SYN_SPACEBEFORE", "text": "слово,"},
    {"id": "syn_spb_no_01", "full_rule_id": "SYN_SPACEBEFORE_NO", "category": "SYN_SPACEBEFORE", "text": "слово,"},
    {"id": "syn_spb_no_02", "full_rule_id": "SYN_SPACEBEFORE_NO", "category": "SYN_SPACEBEFORE", "text": "слово ,"},

    # 18. Chunks regex and negation
    {"id": "syn_chunk_01", "full_rule_id": "SYN_CHUNK_REGEX", "category": "SYN_CHUNKS", "text": "большой дом"},
    {"id": "syn_chunk_02", "full_rule_id": "SYN_CHUNK_REGEX", "category": "SYN_CHUNKS", "text": "синий дом"},
    {"id": "syn_chunk_03", "full_rule_id": "SYN_CHUNK_NEGATE", "category": "SYN_CHUNKS", "text": "книга"},

    # 19. AND conjunction
    {"id": "syn_and_01", "full_rule_id": "SYN_AND_CONJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "они читали"},
    {"id": "syn_and_02", "full_rule_id": "SYN_AND_CONJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "они писали"},
    {"id": "syn_and_03", "full_rule_id": "SYN_AND_CONJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "были книги"},
    {"id": "syn_and_04", "full_rule_id": "SYN_AND_CONJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "он читал"},

    # 20. OR disjunction
    {"id": "syn_or_01", "full_rule_id": "SYN_OR_DISJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "выбор красный"},
    {"id": "syn_or_02", "full_rule_id": "SYN_OR_DISJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "выбор зеленый"},
    {"id": "syn_or_03", "full_rule_id": "SYN_OR_DISJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "выбор синий"},
    {"id": "syn_or_04", "full_rule_id": "SYN_OR_DISJUNCTION", "category": "SYN_LOGICAL_GROUPS", "text": "выбор желтый"},

    # 21. Token match reference (repetition)
    {"id": "syn_tok_match_01", "full_rule_id": "SYN_TOKEN_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "тот тот"},
    {"id": "syn_tok_match_02", "full_rule_id": "SYN_TOKEN_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "этот этот"},
    {"id": "syn_tok_match_03", "full_rule_id": "SYN_TOKEN_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "тот этот"},
    {"id": "syn_tok_match_04", "full_rule_id": "SYN_TOKEN_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "этот тот"},

    # 22. Include skipped all and following
    {"id": "syn_inc_sk_01", "full_rule_id": "SYN_INCLUDE_SKIPPED_ALL", "category": "SYN_MATCH_REFERENCES", "text": "до свидания"},
    {"id": "syn_inc_sk_02", "full_rule_id": "SYN_INCLUDE_SKIPPED_ALL", "category": "SYN_MATCH_REFERENCES", "text": "до скорого свидания"},
    {"id": "syn_inc_sk_03", "full_rule_id": "SYN_INCLUDE_SKIPPED_ALL", "category": "SYN_MATCH_REFERENCES", "text": "до самого скорого свидания"},
    {"id": "syn_inc_sk_04", "full_rule_id": "SYN_INCLUDE_SKIPPED_FOLLOWING", "category": "SYN_MATCH_REFERENCES", "text": "от начала"},
    {"id": "syn_inc_sk_05", "full_rule_id": "SYN_INCLUDE_SKIPPED_FOLLOWING", "category": "SYN_MATCH_REFERENCES", "text": "от самого начала"},

    # 23. Case conversions
    {"id": "syn_case_01", "full_rule_id": "SYN_CASE_CONVERSIONS", "category": "SYN_MATCH_REFERENCES", "text": "ТЕСТ"},
    {"id": "syn_case_02", "full_rule_id": "SYN_CASE_CONVERSIONS", "category": "SYN_MATCH_REFERENCES", "text": "тест"},

    # 24. Regexp replacement captures
    {"id": "syn_reg_repl_01", "full_rule_id": "SYN_REGEXP_REPLACE", "category": "SYN_MATCH_REFERENCES", "text": "автомобиль"},
    {"id": "syn_reg_repl_02", "full_rule_id": "SYN_REGEXP_REPLACE", "category": "SYN_MATCH_REFERENCES", "text": "автобус"},
    {"id": "syn_reg_repl_03", "full_rule_id": "SYN_REGEXP_REPLACE", "category": "SYN_MATCH_REFERENCES", "text": "велосипед"},

    # 25. POS synthesis
    {"id": "syn_pos_synth_01", "full_rule_id": "SYN_POS_SYNTHESIS", "category": "SYN_MATCH_REFERENCES", "text": "бывший другу"},
    {"id": "syn_pos_synth_02", "full_rule_id": "SYN_POS_SYNTHESIS", "category": "SYN_MATCH_REFERENCES", "text": "бывший брату"},
    {"id": "syn_pos_synth_03", "full_rule_id": "SYN_POS_SYNTHESIS", "category": "SYN_MATCH_REFERENCES", "text": "бывший враг"},

    # 26. Optional match reference
    {"id": "syn_opt_ref_01", "full_rule_id": "SYN_OPTIONAL_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "начало середина конец"},
    {"id": "syn_opt_ref_02", "full_rule_id": "SYN_OPTIONAL_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "начало конец"},

    # 27. Infinite skip with match ref
    {"id": "syn_inf_sk_ref_01", "full_rule_id": "SYN_INFINITE_SKIP_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "дом посреди улицы дом"},
    {"id": "syn_inf_sk_ref_02", "full_rule_id": "SYN_INFINITE_SKIP_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "сад посреди улицы сад"},
    {"id": "syn_inf_sk_ref_03", "full_rule_id": "SYN_INFINITE_SKIP_MATCH_REF", "category": "SYN_MATCH_REFERENCES", "text": "дом посреди улицы сад"},

    # 28. Markers: first, middle, last, full
    {"id": "syn_mark_01", "full_rule_id": "SYN_MARKER_FIRST", "category": "SYN_MARKERS_AND_SPANS", "text": "ошибка здесь"},
    {"id": "syn_mark_02", "full_rule_id": "SYN_MARKER_FIRST", "category": "SYN_MARKERS_AND_SPANS", "text": "тут ошибка здесь"},
    {"id": "syn_mark_03", "full_rule_id": "SYN_MARKER_MIDDLE", "category": "SYN_MARKERS_AND_SPANS", "text": "слово внутри фразы"},
    {"id": "syn_mark_04", "full_rule_id": "SYN_MARKER_MIDDLE", "category": "SYN_MARKERS_AND_SPANS", "text": "наше слово внутри фразы"},
    {"id": "syn_mark_05", "full_rule_id": "SYN_MARKER_LAST", "category": "SYN_MARKERS_AND_SPANS", "text": "в самом конце"},
    {"id": "syn_mark_06", "full_rule_id": "SYN_MARKER_LAST", "category": "SYN_MARKERS_AND_SPANS", "text": "они в самом конце"},
    {"id": "syn_mark_07", "full_rule_id": "SYN_MARKER_FULL", "category": "SYN_MARKERS_AND_SPANS", "text": "полная фраза"},
    {"id": "syn_mark_08", "full_rule_id": "SYN_MARKER_FULL", "category": "SYN_MARKERS_AND_SPANS", "text": "вот полная фраза тут"},

    # 29. Antipattern overlap and non-overlap
    {"id": "syn_anti_01", "full_rule_id": "SYN_ANTIPATTERN_OVERLAP", "category": "SYN_ANTIPATTERNS", "text": "белый дом"},
    {"id": "syn_anti_02", "full_rule_id": "SYN_ANTIPATTERN_NON_OVERLAP", "category": "SYN_ANTIPATTERNS", "text": "синий дом"},
    {"id": "syn_anti_03", "full_rule_id": "SYN_ANTIPATTERN_NON_OVERLAP", "category": "SYN_ANTIPATTERNS", "text": "красный дом"},

    # 30. Non-BMP emoji before, inside skip, inside marker
    {"id": "syn_emoji_01", "full_rule_id": "SYN_NON_BMP_EMOJI", "category": "SYN_EDGE_CASES", "text": "🌟 🚀 текст после 👍"},
    {"id": "syn_emoji_02", "full_rule_id": "SYN_NON_BMP_EMOJI", "category": "SYN_EDGE_CASES", "text": "текст после"},
    {"id": "syn_emoji_03", "full_rule_id": "SYN_NON_BMP_EMOJI", "category": "SYN_EDGE_CASES", "text": "просто 🚀 текст до"},

    # 31. Backreference looking sequences (:42, \42, $1)
    {"id": "syn_backref_01", "full_rule_id": "SYN_BACKREF_LITERALS", "category": "SYN_EDGE_CASES", "text": ":42 тест"},
    {"id": "syn_backref_02", "full_rule_id": "SYN_BACKREF_LITERALS", "category": "SYN_EDGE_CASES", "text": "\\42 тест"},
    {"id": "syn_backref_03", "full_rule_id": "SYN_BACKREF_LITERALS", "category": "SYN_EDGE_CASES", "text": "$1 тест"},
    {"id": "syn_backref_04", "full_rule_id": "SYN_BACKREF_LITERALS", "category": "SYN_EDGE_CASES", "text": "$2 тест"},

    # 32. Raw pos
    {"id": "syn_raw_pos_01", "full_rule_id": "SYN_RAW_POS", "category": "SYN_EDGE_CASES", "text": "по зимнему"},
    {"id": "syn_raw_pos_02", "full_rule_id": "SYN_RAW_POS", "category": "SYN_EDGE_CASES", "text": "по летнему"},
]


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
        case["oracle_result"] = out

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
        "cases": russian_rule_cases,
    }

    russian_fixture_path = fixtures_dir / "oracle_advanced_russian_rules.json"
    with open(russian_fixture_path, "w", encoding="utf-8") as f:
        json.dump(russian_fixture_data, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(russian_rule_cases)} cases to {russian_fixture_path}")

    # 2. Generate oracle_advanced_pattern_matching.json (>= 100 discriminating synthetic cases)
    print(f"Querying Java Oracle for {len(DISCRIMINATING_SYNTHETIC_CASES)} discriminating synthetic pattern cases...")
    syn_oracle_outputs = oracle.check_synthetic_pattern_rules(SYNTHETIC_ADVANCED_RULES_XML, DISCRIMINATING_SYNTHETIC_CASES)

    synthetic_cases = []
    for case, out in zip(DISCRIMINATING_SYNTHETIC_CASES, syn_oracle_outputs):
        c_dict = dict(case)
        c_dict["oracle_result"] = out
        synthetic_cases.append(c_dict)

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
        "cases": synthetic_cases,
    }

    synthetic_fixture_path = fixtures_dir / "oracle_advanced_pattern_matching.json"
    with open(synthetic_fixture_path, "w", encoding="utf-8") as f:
        json.dump(synthetic_fixture_data, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(synthetic_cases)} synthetic cases to {synthetic_fixture_path}")


if __name__ == "__main__":
    generate_advanced_fixtures()
