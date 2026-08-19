# Completion Report — Task 0008: Advanced XML Pattern Matching

## 1. Task Summary

Task 0008 implements advanced LanguageTool XML pattern matching constructs for `pylat_ru` matching upstream Java LanguageTool `v6.8` semantics:

- **Logical Token Groupings (`<and>` / `<or>`)**:
  - Implemented `<and>`: requires all enclosed `<token>` elements to match simultaneously on the same candidate token (conjunction).
  - Implemented `<or>`: matches if any enclosed `<token>` branch matches (disjunction). In rule compilation, `<or>` groups at the pattern root expand into Cartesian product compiled rule variants (`expand_rule_into_variants`), exactly matching Java LanguageTool's `PatternRuleLoader` rule expansion.
  - Supported token-level exceptions inside `<and>` and `<or>` blocks with negated POS and inflected matching.

- **Quantifiers & Variable-Length Matching (`skip="N"`, `min="0"`)**:
  - Implemented `min="0"` optional tokens and optional phrases with branch back-tracking during sentence scanning.
  - Implemented `skip="N"` (including `skip="-1"` unbounded sentence skipping): greedy/lazy forward skipping of up to `N` intermediate tokens with per-token exception constraints (`<exception>` on skipped tokens) preventing skip traversal across boundary tokens.
  - Implemented `RuleWithMaxFilter` / subsumption match deduplication (`filter_subsumed_rule_matches`), ensuring longer and earlier matches supersede subsumed variants matching Java LT's `RuleWithMaxFilter`.

- **Structured `<match>` Reference Resolution & Synthesizer Integration (`MatchState`)**:
  - Implemented `resolve_match_reference_forms` supporting:
    - Target token index mapping taking into account variable-length element positions (`rep_token_pos = sum(token_positions[:token_k + 1]) - 1`).
    - `include_skipped="all"` and `include_skipped="following"` extracting skipped whitespace and surface tokens between matched pattern elements.
    - Regex capture and replacement (`regexp_match` and `regexp_replace`) on surface token text and POS tag strings.
    - Synthesizer integration: synthesizing inflected forms from `target_at` or static lemma (`ref.lemma`), target POS regex transformations (`postag_replace`), and regex-based POS matching.
    - Case conversion (`alllower`, `allupper`, `startlower`, `startupper`, `firstupper`, `preserve`, `none`).

- **Multi-Form Suggestion Formatting & Expansion**:
  - Implemented Cartesian product expansion for multi-candidate synthesis results inside `<suggestion>...</suggestion>` tags matching Java LT's `formatMultipleSynthesis`.
  - Extracted formatted suggestions directly from embedded `<suggestion>` elements in messages, preserving case and structure alignment.
  - Capitalized suggestions conditionally when the error begins at the sentence start (`is_sentence_start and first_token.isupper()`).

- **Differential Parity and Conformance**:
  - Evaluated and verified 100% field-level parity across **874 test cases**:
    - `tests/fixtures/oracle_advanced_russian_rules.json` (750 real Russian rule cases across 229 advanced rules in `grammar.xml`).
    - `tests/fixtures/oracle_advanced_pattern_matching.json` (124 discriminating synthetic test cases covering all 27 dimensional combinations of skip, min, max, markers, chunking, AND/OR groups, and match references).
  - All 874 cases match Java LanguageTool `v6.8` with **0 errors, 0 diffs, and 100% exact parity** across rule IDs, category metadata, descriptions, default states, match counts, UTF-16 spans, codepoint offsets, messages, and suggestions.

---

## 2. Pinned Upstream Files & Hashes

| File | Size (Bytes) | SHA-256 Digest |
|---|---|---|
| `grammar.xml` | 1,194,903 | `e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec` |
| `PatternRule.java` | 8,809 | `c320373a9ae9fcf91f51fd6547ed1619f23d4c516a117e6beaccf5482a4817f3` |
| `PatternRuleMatcher.java` | 22,434 | `70eae73add129bd4852185c202676ad378ccce22ea8cd1097f8b2d738edb6613` |
| `MatchState.java` | 15,219 | `cb46d7e007802877a164b73b5d38f8cf0b396bfe61fe343881e18d6ee3be895b` |
| `Match.java` | 6,610 | `47343e8bb8d0859c26425c27bf4958fa134d193309a6331fa9230559ebfeaa7b` |
| `RuleMatch.java` | 16,913 | `2da701c9a72173e3bfaf08018e6900fdfbbfebf32b84c8a2b535ff203a11df6b` |

---

## 3. Implementation & Conformance Review Fixes

### 3.1 Advanced Matcher (`pylat_ru.grammar.matcher`)
- Fixed `max="-1"` runtime by importing `sys` and using `sys.maxsize` for unbounded repeats.
- Added greedy repeat matcher `_skip_max_tokens` supporting `max=2`, `max=3`, `max=-1` and any-token repetitions.
- Ported complete upstream test semantics from `PatternRuleMatcherTest.java`:
  - `testZeroMinOccurrences`, `testTwoZeroMinOccurrences`, `testZeroMinOccurrences2..4`
  - `testZeroMinOccurrencesWithEmptyElement`, `testZeroMinOccurrencesWithSuggestion`
  - `testZeroMinTwoMaxOccurrences`, `testTwoMaxOccurrencesWithAnyToken`, `testThreeMaxOccurrencesWithAnyToken`
  - `testZeroMinTwoMaxOccurrencesWithAnyToken`, `testTwoMaxOccurrences`, `testThreeMaxOccurrences`
  - `testOptionalWithoutExplicitMarker`, `testOptionalWithExplicitMarker`
  - `testOptionalAnyTokenWithExplicitMarker`, `testOptionalAnyTokenWithExplicitMarker2`
  - `testUnlimitedMaxOccurrences`, `testMaxTwoAndThreeOccurrences`
  - `testInfiniteSkip`, `testInfiniteSkipWithMatchReference`, `testNoMatchReferenceRecursion`
- Implemented exact Java `RuleWithMaxFilter` algorithm sorting by `fromPos` and discarding included matches sharing the same rule ID.
- Corrected token-level `<match no="..."/>` reference resolution to 0-indexed relative to `firstMatchToken` (`target_idx = firstMatchToken + ref_no`).
- Handled `<phrase>` Cartesian expansion preserving individual branch lengths (`opt_len`).

### 3.2 Loader & XML Validation (`pylat_ru.grammar.loader`)
- Enforced strict fail-closed validation for `min` attribute: only `min=0` and `min=1` are permitted (`min in (0, 1)`). `min=2..127`, `min=-1`, and non-integers are rejected with `GrammarFormatError`.
- Enforced strict fail-closed validation for `max` attribute: `max=-1` and `1 <= max <= 127` are permitted. `max=0`, `max < -1`, `max > 127`, and non-integers are rejected.
- Validated attribute boundaries in dedicated unit tests.

### 3.3 Advanced Formatter (`pylat_ru.grammar.formatter`)
- Removed silent `except Exception: pass` paths; non-trivial regex/synthesis failures fail closed with explicit `GrammarError`.
- `resolve_match_reference_forms`: computes actual token index in sentence via `rep_token_pos = sum(token_positions[:k+1]) - 1`.
- Synthesizer integration: performs regex replacement on POS tags (`postag_replace`), resolves target lemma from static `<match>lemma</match>` or dynamic token readings, and synthesizes candidate inflected forms using `RussianSynthesizer`.
- Respected explicit case conversions (`case_conversion="alllower"`, `allupper`, `firstupper`) in suggestions and message formatting without erroneous sentence-start auto-capitalization overrides.

---

## 4. Tests and Verification

### 4.1 Pytest Test Suite Results
All 288 tests in the project suite passed with 0 failures, 0 errors, and 0 skips:
- `tests/unit/test_advanced_grammar_matcher.py`: 31 unit tests covering all Task 0008 advanced features, upstream `PatternRuleMatcherTest` ports, and `min`/`max` boundary validation.
- `tests/upstream/test_advanced_pattern_oracle_parity.py`: 3 tests verifying manifest integrity, case count (>=100), and 100% field parity across 124 discriminating synthetic oracle cases.
- `tests/upstream/test_advanced_russian_rule_oracle_parity.py`: 3 tests verifying manifest integrity, case count (>=700), and 100% field parity across 750 real Russian rule cases from `grammar.xml`.
- `tests/unit/test_real_wheel_grammar.py`: 1 test verifying real wheel build, wheel archive contents inspection, clean isolated installation, and end-to-end execution of both Core 0007 and Advanced 0008 rules in a clean subprocess without `src/` on `sys.path`.
- Full project test suite (Tasks 0001–0008): **288 passed in 41.72s**.

### 4.2 Compatibility Status
- Total grammar rules in `grammar.xml`: 892
- `CORE_0007_RUNNABLE`: 506 rules (56.7%)
- `ADVANCED_0008_RUNNABLE`: 229 rules (25.7%)
- **Total runnable rules**: **735 rules (82.4%)**
- Total runnable examples: 1,738
- Remaining deferred rules: 157 rules (17.6%)
  - `DEFERRED_0012_SPELLING_OR_SUPPRESSION`: 110 rules
  - `DEFERRED_0009_UNIFICATION`: 24 rules
  - `DEFERRED_0010_FILTER`: 16 rules
  - `MULTI_BLOCKER`: 7 rules

---

## 5. Compliance & Licensing

- Pinned upstream commit: `e807fcde6a6506191e1470744d2345da28c26be6` (`v6.8`).
- License: GNU LGPL v2.1 or later.
- Zero external runtime NLP dependencies (no Java, no Natasha, no pymorphy).
