# Task 0010 — Native XML Rule Filters: completion report

## Baseline

- LanguageTool target: `v6.8`, commit `e807fcde6a6506191e1470744d2345da28c26be6`.
- Pinned grammar: `third_party/languagetool/languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/grammar.xml`.
- Grammar size/SHA-256: `1,194,903` bytes / `e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec`.
- Accepted Task-0009 semantic baseline: `762ae1e5ce8174f12b1532d0c6212c08b72c9889`.
- Starting HEAD for Task 0010: `6f2779750442817038555445d406266454da2ca6`; initial Task-0010 implementation commit: `d14be5f`.
- Task-0009 baseline: 759 runnable and 133 deferred source rules; 1,954 runnable and 492 deferred examples.

## Raw filter inventory

The generated inventory is `compat/russian_grammar_filter_inventory.json`. It reconciles all 892 source rules and records every filter-bearing full rule ID, raw `args`, prior state/blockers, Task-0010 state, remaining blockers, examples, and overlap flags.

| Grammar filter class | Refs | Affected full rule IDs |
| --- | ---: | --- |
| `AdvancedSynthesizerFilter` | 4 | `Unify_Adj_NN_case[3]`, `Unify_PADJ_NN_case[1]`, `Unify_PADJ_NN_gender[1]`, `Unify_PADJ_NN_number[1]` |
| `DateCheckFilter` | 2 | `DATE_WEEKDAY1[1]`, `DATE_WEEKDAY1[2]` |
| `FutureDateFilter` | 2 | `INVALID_TENSE_DATE[1]`, `INVALID_TENSE_DATE[2]` |
| `INNNumberFilter` | 1 | `WRONG_INN[1]` |
| `RussianPartialPosTagFilter` | 13 | `DoubleNE[1]`, `NN_N_pril_prich[2]`, `Ne_narech2[1]`, `Ne_narech[3]`, `Ne_narech[4]`, `Ne_pril_prich1[1]`, `Ne_pril_prich[1..4]`, `Verb_INF_OR_3P[2]`, `Verb_tsa_and_ttsya[2]`, `pouchastvovat[1]` |
| `RussianSuppressMisspelledSuggestionsFilter` | 1 | `NN_N_pril_prich[1]` |

Raw totals are exactly 23 `<filter>` elements, 23 `class` attributes, 23 `args` attributes, six grammar filter classes, and 23 filter-bearing source rules. `NoDisambiguationRussianPartialPosTagFilter`, accepted in Task 0005, is the seventh project-wide XML filter class.

Exact distinct raw argument distributions (count before each value):

```text
1  AdvancedSynthesizerFilter  lemmaFrom:1 lemmaSelect:ADJ:(Posit|Sup):.*:.* postagFrom:2 postagSelect:NN:.*:(.*):.*:(.*) postagReplace:ADJ:\a1:\b1:\b2
3  AdvancedSynthesizerFilter  lemmaFrom:1 lemmaSelect:ADJ:MPR:.*:.* postagFrom:2 postagSelect:NN:.*:(.*):.*:(.*) postagReplace:ADJ:MPR:\b1:\b2
1  DateCheckFilter            year:\5 month:\4 day:\3 weekDay:\1
1  DateCheckFilter            year:\7 month:\5 day:\3 weekDay:\1
1  FutureDateFilter           year:\4 month:\3 day:\2
1  FutureDateFilter           year:\6 month:\4 day:\2
1  INNNumberFilter            inn:\3
1  RussianPartialPosTagFilter no:1 regexp:(.*[аеёиоуэюя][н])[н]([а-мо-я]{1,3}) postag_regexp:ADJ:.* two_groups_regexp:yes
1  RussianPartialPosTagFilter no:1 regexp:не(.*) postag_regexp:(ADV)
1  RussianPartialPosTagFilter no:2 regexp:(.*) postag_regexp:(ADV) prefix:не suffix:
1  RussianPartialPosTagFilter no:2 regexp:(.*) postag_regexp:(VB:.*) prefix:по suffix:
1  RussianPartialPosTagFilter no:2 regexp:(.*) postag_regexp:UNKNOWN prefix:не suffix: negate_pos:yes
1  RussianPartialPosTagFilter no:2 regexp:(.*)ься postag_regexp:UNKNOWN negate_pos:yes
2  RussianPartialPosTagFilter no:2 regexp:не(.*) postag_regexp:(ADJ:.*)|(PT:.*)
1  RussianPartialPosTagFilter no:2 regexp:не(.*) postag_regexp:(ADV)
1  RussianPartialPosTagFilter no:2 regexp:не(.*) postag_regexp:UNKNOWN negate_pos:yes
2  RussianPartialPosTagFilter no:3 regexp:(.*) postag_regexp:UNKNOWN prefix:не suffix: negate_pos:yes
1  RussianPartialPosTagFilter no:4 regexp:(.*)ься postag_regexp:UNKNOWN negate_pos:yes
1  RussianSuppressMisspelledSuggestionsFilter suppressMatch:true
```

Overlap inventory: four filter + unification rules, three filter + spelling/suppression rules, and twelve filter rules using other advanced constructs.

## Upstream provenance

All entries below are byte-exact from the pinned commit and recorded as `VERIFIED_LGPL` in `third_party/languagetool/license_inventory.json`.

| Upstream path | Bytes | SHA-256 | Purpose |
| --- | ---: | --- | --- |
| `languagetool-core/.../AbstractAdvancedSynthesizerFilter.java` | 8,645 | `ebae258c5b034f3af3a67a563cf254fa32d934065a6808a9750a2df4e754d387` | synthesis/filter semantics |
| `languagetool-core/.../AbstractDateCheckFilter.java` | 7,013 | `c18a7cbfc48369f89905d964d2757d50c6cff79911202ff46e9f16b8641446c0` | weekday/date mutation semantics |
| `languagetool-core/.../AbstractFutureDateFilter.java` | 4,157 | `be48708586932a31d4bb9ce546bd4410b235c7ebbc8b2d3c7fbcb358c159c2df` | future-date semantics |
| `languagetool-core/.../AbstractSuppressMisspelledSuggestionsFilter.java` | 3,336 | `9a93332483a1ec33cd1eb0245b951598991e96b0b271670c824f2562b42c2739` | Task-0012 dependency audit |
| `languagetool-core/.../PartialPosTagFilter.java` | 5,324 | `fdd3f4fa34e02f03f2f291527c1b382d4b55c0a0b9b8533d592ef605dd6fce1f` | partial-token POS semantics |
| `languagetool-core/.../patterns/RuleFilter.java` | 6,004 | `9d35d67c2ed47ce9f9bb332af4306fdb62fd56e28bca132c9aa6bdbe92697e8b` | base helpers and positions |
| `languagetool-core/.../patterns/RuleFilterEvaluator.java` | 3,771 | `8c6313c12533e28873bf42d6c8b4d9a6025aea32fa67c63c5885064dad30ac58` | argument resolution |
| `languagetool-core/.../patterns/RuleFilterEvaluatorTest.java` | 3,323 | `45ee3705fb0fdeac3398581ab5d9599c4e80bca75a47661c1d99f51388680cc3` | translated evaluator assertions |
| `languagetool-language-modules/ru/.../DateCheckFilterTest.java` | 2,067 | `995d5a5c44fa80394ddee6278e279d0a04dec1047522fae3cba5e0401a657e22` | translated Russian date assertions |

## Implementation semantics

The engine creates and formats a provisional `RuleMatchResult`, resolves `filter@args` against the physical matched token slice and `tokenPositions`, then executes the native filter. A filter can reject, preserve, or replace the provisional match. Filters that construct a fresh Java `RuleMatch` (`AdvancedSynthesizerFilter` and the modifying `DateCheckFilter` branch) reset the full-pattern span to the finding span and copy only the fields upstream copies.

- `RuleFilterEvaluator` preserves Java whitespace splitting, first-colon parsing, 1-based backreferences, skip correction, explicit bounds failures, duplicate-backreference failure, and literal duplicate overwrite.
- `AdvancedSynthesizerFilter` uses the engine's current native `RussianSynthesizer`, first matching ATR reading with first-reading fallback, marker/numeric positions, composite `\aN`/`\bN` tags, Java casing/template order, template-result deduplication, and raw no-placeholder forms (including duplicates). Russian `adaptSuggestion` is the inherited identity behavior. Filter instances are match-local so contextual synthesizers cannot leak across engines.
- `DateCheckFilter` and `FutureDateFilter` distinguish Java-equivalent illegal-argument and runtime failures. `DateCheckFilter` rejects invalid strict dates. `FutureDateFilter` preserves Java `Calendar.after` behavior for pending invalid future fields, while required/malformed arguments propagate where upstream does. `SystemClock` provides isolated production-current and controlled-test behavior.
- `INNNumberFilter` ports the pinned 10/12-digit checksum algorithms and ASCII digit semantics.
- `RussianPartialPosTagFilter` runs the native tagger and the accepted single-token Russian disambiguator, including presence-based `negate_pos` and exact one/two-group behavior.
- `RussianSuppressMisspelledSuggestionsFilter` is recognized but remains non-executable. It fails closed with an explicit Task-0012 spelling dependency; no dictionary-membership or heuristic approximation was added.

The isolated wheel proof runs `Unify_PADJ_NN_case[1]`, `Ne_narech[3]`, `WRONG_INN[1]`, and the previously accepted `Unify_Mult_Adj[1]`, while blocking sockets and subprocess creation.

## State transitions

| Task-0009 state | Task-0009 | Task-0010 state | Task-0010 | Transition |
| --- | ---: | --- | ---: | --- |
| `CORE_0007_RUNNABLE` | 506 | `CORE_0007_RUNNABLE` | 506 | unchanged |
| `ADVANCED_0008_RUNNABLE` | 229 | `ADVANCED_0008_RUNNABLE` | 229 | unchanged |
| `UNIFICATION_0009_RUNNABLE` | 24 | `UNIFICATION_0009_RUNNABLE` | 24 | unchanged |
| `DEFERRED_0010_FILTER` | 20 | `FILTER_0010_RUNNABLE` | 19 | promoted |
| `DEFERRED_0010_FILTER` | included above | `DEFERRED_0012_SPELLING_OR_SUPPRESSION` | +1 | spelling filter remains deferred |
| `DEFERRED_0012_SPELLING_OR_SUPPRESSION` | 110 | same state | 110 | unchanged |
| `MULTI_BLOCKER` | 3 | `DEFERRED_0012_SPELLING_OR_SUPPRESSION` | +3 | filter blocker removed |

Final arithmetic: 778 runnable + 114 deferred = 892; `DEFERRED_0010_FILTER = 0`, `MULTI_BLOCKER = 0`, `UNKNOWN = 0`.

Examples: 2,119 runnable (910 incorrect, 1,209 correct) and 327 deferred (129 incorrect, 198 correct), totaling 2,446.

## Oracle provenance and results

- Oracle build: `lt_6.8_source_build_jdk17_stefan`.
- JAR SHA-256: `b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc`.
- Live generator: `python tools/generate_oracle_filters_fixtures.py`; completed successfully against the trusted Java oracle.
- Synthetic fixture: 178 genuinely distinct low-level cases across 84 feature dimensions; 166 ordinary results and 12 exact-class Java exception results. Canonical semantic SHA-256 signatures cover operation/filter, arguments, controlled ATR, token positions, marker state, and provisional match state; generation and tests reject duplicates.
- Real Russian fixture: all 165 embedded examples for all 19 promoted rules; 32 positive and 133 zero-match oracle results.
- Controlled omitted-year fixture date: `2026-08-20`; production still uses the runtime current year.
- Real-rule compared fields: finding count/order, rule ID, full rule ID, category ID/name, rule description, default-off state, marker and full-pattern UTF-16 spans, message, short message, suggestions/order, and URL. Python codepoint spans and source slices for marker and full-pattern spans are derived from Java UTF-16 offsets and asserted independently.
- Low-level compared fields: resolved arguments, selected numeric/marker/backreference position, reject/preserve/modify decision, returned offsets/message/short message/suggestions/URL, and exact Java exception class plus mapped Python exception category.
- Coverage fails closed: normal features require a Java `RESULT`; an exception counts only for an explicitly exception-named feature with a pinned class/category. Pattern non-matches and unrelated missing-argument failures are absent from this fixture.
- `compat/oracle_manifest.json` binds both fixtures to the trusted build with byte size and SHA-256.

Committed-fixture parity is part of normal pytest. Live Java generation is development-only and neither Java nor oracle assets are imported by production code.

## Upstream test translation accounting

| Java source method | Source assertions | Python test function | Translated | Deferred |
| --- | ---: | --- | ---: | ---: |
| `RuleFilterEvaluatorTest.testGetResolvedArguments` | 3 | `test_rule_filter_evaluator_resolved_arguments` | 3 | 0 |
| `RuleFilterEvaluatorTest.testGetResolvedArgumentsWithColon` | 2 | `test_rule_filter_evaluator_value_with_colon` | 2 | 0 |
| `RuleFilterEvaluatorTest.testDuplicateKey` | 1 | `test_rule_filter_evaluator_duplicate_backreference_key` | 1 | 0 |
| `RuleFilterEvaluatorTest.testNoBackReference` | 1 | `test_rule_filter_evaluator_without_backreference` | 1 | 0 |
| `RuleFilterEvaluatorTest.testTooLargeBackRef` | 1 | `test_rule_filter_evaluator_too_large_backreference` | 1 | 0 |
| `DateCheckFilterTest.testGetDayOfWeek` | 4 | `test_date_check_filter_upstream_weekday_mapping` | 4 | 0 |
| `DateCheckFilterTest.testMonth` | 5 | `test_date_check_filter_upstream_month_mapping` | 5 | 0 |

Totals: two Java source files, seven source methods, 17 active source assertions, seven direct Python translation functions, 17 translated assertions, zero deferred active assertions. Additional evaluator edge cases cover malformed args, zero/negative bounds, and literal duplicate overwrite.

## Tests and proofs

Final verification commands/results:

```text
python tools/generate_oracle_filters_fixtures.py
  19 rules / 165 real cases; 178 distinct low-level synthetic cases; exit 0

python tools/russian_grammar_filter_inventory.py
  23 filter-bearing rules; exit 0

python -m pytest tests/upstream/test_filters_oracle_parity.py -q
  5 passed

python -m pytest tests/upstream/test_russian_grammar_examples.py::test_grammar_all_runnable_0010_trigger_parity -q
  1 passed; all 2,119 runnable examples; failed=0, errors=0, skipped=0

python -m pytest tests/unit/test_real_wheel_grammar.py -q
  1 passed; failed=0, errors=0, skipped=0

python -m pytest -q
  361 passed, 0 failed, 0 errors, 0 skipped; 69.32 s
```

The full run used CPython 3.10.11 on Windows and included the isolated real-wheel build/install/execution proof. Normal fixture-only tests and the live-oracle generation are reported separately above.

## Compatibility totals

- XML filters: 6/7 project-wide classes implemented; five executable Task-0010 grammar classes, one accepted Task-0005 disambiguation class, one recognized Task-0012-deferred grammar class.
- Grammar filter references/classes: 23 / 6.
- `FILTER_0010_RUNNABLE`: 19 rules.
- Runnable/deferred source rules: 778 / 114.
- Runnable/deferred examples: 2,119 / 327.
- Oracle cases: 178 synthetic + 165 real.
- Unknown filter classes: 0.
- Wheel production isolation: passed.

## Known limitations

- Task 0011 Russian/shared Java rules are not implemented by this task.
- Task 0012 spelling, spelling-dependent suggestion suppression, compounds, replace, and repetition layers remain deferred.
- `RussianSuppressMisspelledSuggestionsFilter` is not claimed as production-supported before Task 0012.

## Git and CI completion

- Initial Task-0010 implementation commit: `d14be5f` on `main`.
- Conformance review-fix implementation commit: `85a3451da293d8c58ecb0fd5436cd7af71a0708c`.
- Final oracle-evidence correction started from `d4189f0aad3fea6a41be6d7c31fdcd5fb4b1c4fb`.
- The first final-correction CI run exposed a cross-platform fixture-binding defect: Windows-generated CRLF bytes were hashed before Git's required LF normalization. The generator now writes explicit LF, the manifest binds the canonical Git bytes, and the complete local suite was rerun afterward.
- Push target for the final correction: `origin/main`, without force or history rewrite. The exact pushed SHA and exact-SHA CI result are part of the final handoff verification.
- Manual Oracle Conformance workflow: not invoked; live local trusted-oracle generation completed successfully as documented above.
