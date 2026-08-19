# Completion Report — Task 0008: Advanced XML Pattern Matching

## 1. Task Summary

Task 0008 implements advanced LanguageTool XML pattern matching constructs for `pylat_ru` matching upstream Java LanguageTool `v6.8` semantics:

- **Logical Token Groupings (`<and>` / `<or>`)**:
  - Implemented `<and>`: requires all enclosed `<token>` elements to match simultaneously on the same candidate token (conjunction).
  - Implemented `<or>`: matches if any enclosed `<token>` branch matches (disjunction). In rule compilation, `<or>` groups expand recursively into Cartesian product compiled rule variants (`expand_rule_into_variants`), exactly matching Java LanguageTool's `PatternRuleLoader` rule expansion.
  - Supported token-level exceptions inside `<and>` and `<or>` blocks with negated POS, inflected matching, and scope checks.

- **Quantifiers & Variable-Length Matching (`skip="N"`, `min="0"`, `max="M"`)**:
  - Implemented `min="0"` optional tokens and optional phrases with branch back-tracking during sentence scanning. Strict validation restricts `min` to values in `{0, 1}` (`0 <= min <= 127` inside `<unify>`).
  - Implemented `max="M"` (`1 <= max <= 127`, `max="-1"` unbounded) for repeated token matching via `_skip_max_tokens` using `sys.maxsize`.
  - Implemented `skip="N"` (including `skip="-1"` unbounded sentence skipping): greedy/lazy forward skipping of up to `N` intermediate tokens with per-token exception constraints (`<exception>` on skipped tokens) preventing skip traversal across boundary tokens.
  - Implemented `RuleWithMaxFilter` / subsumption match deduplication (`filter_subsumed_rule_matches`), ensuring longer and earlier matches supersede subsumed variants matching Java LT's `RuleWithMaxFilter`.

- **Structured `<match>` Reference Resolution & Synthesizer Integration (`MatchState`)**:
  - Implemented `resolve_match_reference_forms` supporting:
    - Target token index mapping taking into account variable-length element positions (`rep_token_pos = sum(token_positions[:token_k + 1]) - 1`).
    - Multi-token `<phrase>` / `<phraseref>` match reference concatenation according to token lengths matching Java LT `PatternRuleMatcher`.
    - `include_skipped="all"` and `include_skipped="following"` extracting skipped whitespace and surface tokens between matched pattern elements.
    - Regex capture and replacement (`regexp_match` and `regexp_replace`) on surface token text and POS tag strings.
    - Synthesizer integration: synthesizing inflected forms from `target_at` or static lemma (`ref.lemma`), target POS regex transformations (`postag_replace`), and regex-based POS matching.
    - Case conversion (`alllower`, `allupper`, `startlower`, `startupper`, `firstupper`, `preserve`, `none`).

- **Multi-Form Suggestion Formatting & Expansion**:
  - Implemented Cartesian product expansion for multi-candidate synthesis results inside `<suggestion>...</suggestion>` tags matching Java LT's `formatMultipleSynthesis`.
  - Extracted formatted suggestions directly from embedded `<suggestion>` elements in messages, preserving case and structure alignment.
  - Capitalized suggestions conditionally when the error begins at the sentence start (`is_sentence_start and first_token.isupper()`).

- **Differential Parity and Conformance**:
  - Evaluated and verified 100% field-level parity across **891 test cases**:
    - `tests/fixtures/oracle_advanced_russian_rules.json` (750 real Russian rule cases across 229 advanced rules in `grammar.xml`).
    - `tests/fixtures/oracle_advanced_pattern_matching.json` (141 discriminating synthetic test cases covering all 44 feature dimensions of skip, min, max, markers, chunking, AND/OR groups, phrase expansions, and match references).
  - All 891 cases match Java LanguageTool `v6.8` with **0 errors, 0 diffs, and 100% exact parity** across rule IDs, category metadata, descriptions, default states, match counts, UTF-16 spans, codepoint offsets, pattern spans, messages, and suggestions.

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

### 3.1 Strict Structural Loading for Deferred Rules (`pylat_ru.grammar.loader`)
- Removed `try...except GrammarFormatError: pattern = Pattern()` fallback in `GrammarLoader`.
- Propagated `is_unify: bool` context: only elements inside `<unify>` accept `0 <= min <= 127`. All other standard token nodes strictly enforce `min in (0, 1)`.
- All 892 rules in `grammar.xml` (including deferred 0009 unification, 0010 filter, and 0012 suppression rules) retain full typed pattern structures without discarding XML contents.
- Malformed XML and undefined attributes fail closed immediately.

### 3.2 Distinct Synthetic Feature Matrix & Machine-Readable Coverage
- Expanded synthetic pattern XML and test corpus to **141 discriminating test cases** covering all 44 feature dimensions:
  - `exception@spacebefore` yes/no, literal chunk, chunk regex, multiple chunks, no chunks.
  - AND across readings, negative AND cross-reading, OR branch expansion.
  - `<phrase>` and `<phraseref>` expansion, phrase with internal OR, match numbering through phrases, marker around phrase references.
  - Skip + min/max interaction, skipped tokens inside marker, omitted optional tokens inside marker, repeated tokens inside marker.
  - Non-BMP UTF-16 surrogates in skipped and marker regions.
  - `raw_pos="yes"` pre- vs post-disambiguation token stream divergence.
- Added machine-readable `REQUIRED_SYNTHETIC_FEATURE_FAMILIES` coverage assertion verifying that `required - covered == empty set` and each family has non-empty associated case IDs.

### 3.3 Coverage-Driven Real Russian Oracle Corpus
- Derived feature usage from `compat/russian_grammar_advanced_inventory.json` across 750 real Russian rule cases.
- Produced machine-readable `feature_coverage` mapping `feature -> representative rules -> covered case IDs` for all 12 non-zero Russian advanced feature families.
- Added test asserting 100% coverage of `REQUIRED_RUSSIAN_FEATURE_FAMILIES`.

### 3.4 Exact Codepoint & Full Pattern Span Parity
- Independently derived `expected_from_codepoint`, `expected_to_codepoint`, `expected_pattern_from_codepoint`, and `expected_pattern_to_codepoint` from UTF-16 offsets.
- Asserted exact equality against `act_m.from_pos`, `act_m.to_pos`, `act_m.pattern_from_pos`, `act_m.pattern_to_pos`.
- Asserted exact text slice equality (`text[from_pos:to_pos]` and `text[pattern_from_pos:pattern_to_pos]` matching Java UTF-16 slices) across both synthetic and real-rule fixtures.

### 3.5 Mutable Token-Reference State Isolation (`pylat_ru.grammar.matcher`)
- Unconditionally cleared dynamic reference fields (`dynamic_text`, `dynamic_postag`, `dynamic_text_regex`, `dynamic_postag_regex`) in `resolve_reference()` before any early return.
- Added `reset_dynamic_state()` to `CompiledRuleVariant` invoked before each match attempt, preventing stale dynamic references across candidate token positions or sentence lengths.

### 3.6 Exception Scopes & Methods in Matcher
- Implemented `matches_next_exception(self, next_atr: AnalyzedTokenReadings)` iterating across all readings.
- Retained `matches_scope_next(self, next_at: AnalyzedToken, next_atr: AnalyzedTokenReadings)` for single reading evaluations.

### 3.7 Phrase Reference Semantics & Match Formatting
- Supported `<phrases>` container root tag and `<phraseref idref="..."/>` references in `GrammarLoader`.
- Aligned phrase match reference formatting in `TemplateFormatter`: multi-token phrases concatenated with spaces matching Java LT `PatternRuleMatcher.concatMatches`.
- Validated undefined phrase references fail closed at expansion time.

---

## 4. Tests and Verification

### 4.1 Pytest Test Suite Results
All 293 tests in the project suite passed with 0 failures, 0 errors, and 0 skips:
- `tests/unit/test_advanced_grammar_matcher.py`: 34 unit tests covering all Task 0008 advanced features, upstream `PatternRuleMatcherTest` ports, `min`/`max` boundary validation, deferred rule structural preservation, dynamic state isolation, and phrase semantics.
- `tests/upstream/test_advanced_pattern_oracle_parity.py`: 4 tests verifying manifest integrity, 100% synthetic feature coverage, case count (>=100), and 100% field/span/slice parity across 141 discriminating synthetic oracle cases.
- `tests/upstream/test_advanced_russian_rule_oracle_parity.py`: 4 tests verifying manifest integrity, 100% real Russian feature coverage, case count (>=700), and 100% field/span/slice parity across 750 real Russian rule cases from `grammar.xml`.
- `tests/unit/test_real_wheel_grammar.py`: 1 test verifying real wheel build, wheel archive contents inspection, clean isolated installation, and end-to-end execution of both Core 0007 and Advanced 0008 rules in a clean subprocess without `src/` on `sys.path`.
- Full project test suite (Tasks 0001–0008): **293 passed in 42.89s**.

### 4.2 Compatibility Status
- Total grammar rules in `grammar.xml`: 892
- `CORE_0007_RUNNABLE`: 506 source rules (56.7%)
- `ADVANCED_0008_RUNNABLE`: 229 source rules (25.7%)
- **Total runnable source rules**: **735 rules (82.4%)**
- **Total compiled rule variants**: **747 variants**
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
