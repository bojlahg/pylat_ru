# Completion Report — Task 0007: RussianChunker + XML Grammar Engine Core (Final Verification Complete)

## 1. Task Summary

Task 0007 implements the native Python `RussianChunker` and the core XML Grammar Rule Engine for `pylat_ru` matching upstream Java LanguageTool `v6.8` semantics:

- **Strict Fail-Closed Schema & Structural Rule Classification**:
  - `GrammarLoader` strictly validates allowed child elements per parent context, allowed attributes per element context, and enumerated values (`default="on|off|temp_off"`, boolean flags `yes|no`, integer constraints). Any malformed integer, boolean, or unknown attribute/element raises a typed `GrammarFormatError`.
  - Removed all non-canonical attribute aliases (such as `set_postag` on `<match>`); only canonical `setpos` is permitted.
  - Fully preserves structural metadata for deferred rules into typed AST models: `PatternAnd`, `PatternOr`, `PatternUnify`, `PatternUnifyIgnore`, `PatternPhrase`, `FilterConfig`, `FeatureDef`, `EquivalenceDef`, `UnificationDef`, and complete `<match>` attributes (`setpos`, `regexp_match`, `regexp_replace`, `sub_type`, etc.).
  - `tools/russian_grammar_core_inventory.py` analyzes all 892 rules in `grammar.xml` and dynamically extracts regexes, syntax expansions, and phrase types directly from `RussianChunker.java` source using regex/source-derived parsing.
  - Exactly classified all 892 rules into deterministic execution states:
    - `CORE_0007_RUNNABLE`: 506 rules (56.7%)
    - `DEFERRED_0008_ADVANCED_MATCHING`: 157 rules (17.6%)
    - `DEFERRED_0009_UNIFICATION`: 8 rules (0.9%)
    - `DEFERRED_0010_FILTER`: 64 rules (7.2%)
    - `MULTI_BLOCKER`: 157 rules (17.6%)
    - `UNRECOGNIZED_CONSTRUCT`: 0 rules (0.0%)
  - Generated committed reference inventory `compat/russian_grammar_core_inventory.json` with SHA-256 byte-exact regeneration tests.

- **Native Russian Chunker (`pylat_ru.chunking`)**:
  - Implemented `TokenExpression` predicate parser, conjunction evaluator, and greedy regex sequence matching.
  - Implemented `RussianChunker` with all 21 `REGEXES1` and 3 `REGEXES2` phrase rules parsed from `RussianChunker.java`.
  - Exact initial chunk semantics matching pinned Java LT: `RussianChunker.getBasicChunks()` tests existing chunk tags only for `MayMissingYO` exclusion; all included tokens initialize with `["O"]`.
  - After chunking, assigning computed chunk tags back to readings replaces previous chunk tags on included tokens, while excluded tokens (such as `MayMissingYO`) retain their existing tags.
  - Added real Java differential boundary testing with pre-injected chunk tags (`chunk_31_unrelated_preexisting_tag`, `chunk_32_filter_tag_preexisting`, `chunk_33_may_missing_yo_exclusion`, `chunk_34_ambiguous_readings`).
  - Verified 100% differential parity against Java LanguageTool oracle (`tests/fixtures/oracle_russian_chunker.json`, 34 test cases) asserting all 12 serialized token fields unconditionally pre-chunker and post-chunker.

- **Core XML Grammar Engine (`pylat_ru.grammar`)**:
  - Domain models: `GrammarRule`, `Pattern`, `PatternToken`, `PatternTokenException`, `PatternAnd`, `PatternOr`, `PatternUnify`, `PatternUnifyIgnore`, `PatternPhrase`, `MatchReference`, `FilterConfig`, `FeatureDef`, `EquivalenceDef`, `UnificationDef`, `MessageTemplate`, `SuggestionTemplate`, `Example`, `RuleMatchResult`.
  - Precompiled pattern matching engine (`CompiledPattern`, `CompiledPatternToken`, `CompiledTokenException`) supporting:
    - Text matching with exact Java `PatternToken.getTestToken()` semantics: when `inflected="yes"`, matches against `lemma` only if non-null, or falls back to surface `token` if lemma is null (surface text is not tested if lemma exists and differs).
    - Sentence-initial capitalization relaxation on `test_str`.
    - POS tag matching (literal, regex, negation).
    - Exceptions (negated POS, text regex, inflected lemma exception, token-level exclusion).
    - Marker error spans (`<marker>...</marker>`).
    - Java LT `PatternRuleMatcher` comma-prepended whitespace span adjustment (when suggestions start with `,`, `fromPos` includes preceding whitespace).
  - Template formatter (`TemplateFormatter`) resolving `<match no="X">` references, regex transformations (`regexp_match` / `regexp_replace`), case conversions (`alllower`, `allupper`, `startlower`, `startupper`, `firstupper`, `preserve`), and Java LT-compatible capitalization adjustments (`StringTools.isAllUppercase(List<String>)`).
  - `RussianGrammarEngine` supporting full-sentence scanning, rule filtering, individual rule testing, rule enabling/disabling, dual UTF-16 code units and Python codepoint offset derivations, and fail-closed errors (`UnsupportedGrammarFeatureError`) on deferred rules.

- **Differential Parity and Conformance**:
  - 100% field-level parity against Java LT Oracle across 62 curated test cases in `tests/fixtures/oracle_russian_grammar_core.json`, asserting rule IDs, category metadata, descriptions, default states, match counts, UTF-16 spans, codepoint slices, messages, short messages, and suggestions.
  - 100% exact parity on `tests/fixtures/oracle_pattern_token_inflected.json` (6 synthetic oracle cases independently proving surface match / lemma diff, lemma match / surface diff, lemma null surface fallback, and inflected exception exclusion/inclusion).
  - 100% exact parity across all 988 examples for all 506 core-runnable rules in `grammar.xml`:
    - 525 incorrect examples detected with exact `(from_pos, to_pos)` marker spans (0 span diffs), exact replacement strings and ordering without silent NBSP or whitespace stripping (0 suggestion diffs);
    - 463 correct examples passed with 0 false triggers.

---

## 2. Pinned Upstream Files & Hashes

| File | Size (Bytes) | SHA-256 Digest |
|---|---|---|
| `grammar.xml` | 1,194,903 | `e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec` |
| `RussianChunker.java` | 14,544 | `df0035c002e5453cbe970cbef3880ae19cb9aaab24d98d669bf746c2a70b27d1` |
| `PatternRule.java` | 8,809 | `c320373a9ae9fcf91f51fd6547ed1619f23d4c516a117e6beaccf5482a4817f3` |
| `PatternRuleMatcher.java` | 22,434 | `70eae73add129bd4852185c202676ad378ccce22ea8cd1097f8b2d738edb6613` |
| `PatternRuleLoader.java` | 3,248 | `778eae3a362b3aa6bd595ac233e27bd74605c4e91c9460e6d94a0f3d43a4ed3a` |
| `PatternToken.java` | 26,728 | `11b69892b0738e38e90eb7653b3474982db98762d9d98d138e8360e70bcf8fbb` |

---

## 3. Important Files Added and Changed

### Core Implementation
- `src/pylat_ru/chunking/__init__.py`: Package init exporting `RussianChunker`, `ChunkTaggedToken`, `TokenExpression`.
- `src/pylat_ru/chunking/token_expression.py`: Token expression parser, predicate logic, and sequence matching.
- `src/pylat_ru/chunking/russian.py`: Russian phrase chunker with exact `["O"]` basic chunk initialization and tag replacement.
- `src/pylat_ru/grammar/__init__.py`: Grammar engine package init.
- `src/pylat_ru/grammar/errors.py`: Error hierarchy (`GrammarError`, `UnsupportedGrammarFeatureError`, `GrammarResourceError`, `GrammarFormatError`, `GrammarRuleDisabledError`).
- `src/pylat_ru/grammar/model.py`: Domain models with complete typed structural metadata for deferred features (`PatternAnd`, `PatternOr`, `PatternUnify`, `PatternUnifyIgnore`, `PatternPhrase`).
- `src/pylat_ru/grammar/classifier.py`: Structural rule classifier for all 892 rules.
- `src/pylat_ru/grammar/loader.py`: Strict fail-closed XML rule loader validating allowed children/attributes per context and parsing typed structural nodes.
- `src/pylat_ru/grammar/matcher.py`: Precompiled token predicate and pattern matcher with exact `getTestToken` inflected semantics.
- `src/pylat_ru/grammar/formatter.py`: Message and suggestion template renderer with regex replacements and case conversion.
- `src/pylat_ru/grammar/engine.py`: `RussianGrammarEngine` execution runtime with comma-adjusted spans and dual UTF-16 / Python codepoint offsets.
- `src/pylat_ru/tagging/string_tools.py`: Restored exact Java `StringTools.isAllUppercase(String)` and `isAllUppercase(List<String>)`.
- `src/pylat_ru/resources/rules/ru/grammar.xml`: Pinned upstream `grammar.xml` (SHA-256 `e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec`).
- `pyproject.toml`: Added package data inclusion for `pylat_ru.resources.rules.ru`.

### Tooling & Compatibility
- `tools/russian_grammar_core_inventory.py`: Dynamic regex/source-derived chunker parser and deterministic inventory generator.
- `compat/russian_grammar_core_inventory.json`: Committed grammar core inventory (892 rules).
- `compat/compatibility.json`: Reconciled oracle counts and upstream test metrics with explicit separate units.
- `third_party/languagetool/UPSTREAM.json`: Updated with all 105 vendored files and SHA-256 digests.
- `third_party/languagetool/license_inventory.json`: Updated with all 105 vendored files, 0 blocked license reviews.
- `tools/differential_lt.py`: Added injected chunk protocol, `evaluate_pattern_tokens`, and fixture generators.
- `tests/fixtures/oracle_russian_chunker.json`: 34 chunker oracle test cases with pre-injected boundary tags.
- `tests/fixtures/oracle_russian_grammar_core.json`: 62 grammar core oracle test cases.
- `tests/fixtures/oracle_pattern_token_inflected.json`: 6 pattern token inflected semantics oracle test cases.

### Tests
- `tests/unit/test_grammar_inventory.py`: Deterministic inventory regeneration and invariant tests.
- `tests/unit/test_russian_chunker.py`: Unit tests for chunker components and regex expressions.
- `tests/unit/test_grammar_engine_core.py`: Unit tests for loader fail-closed validation, matcher, formatter, engine, emoji/non-BMP offsets.
- `tests/unit/test_real_wheel_grammar.py`: Automated wheel packaging, resource inspection, and isolated subprocess execution test.
- `tests/upstream/test_russian_chunker_oracle_parity.py`: 100% oracle differential test for chunker (34 cases, 12 token fields unconditionally asserted pre and post chunker).
- `tests/upstream/test_russian_grammar_oracle_parity.py`: 100% oracle differential test for grammar core (62 cases, 100% field-level parity).
- `tests/upstream/test_pattern_token_oracle_parity.py`: 100% oracle differential test for PatternToken inflected semantics (6 cases).
- `tests/upstream/test_russian_grammar_examples.py`: Executable XML examples test suite for all 506 core-runnable rules (988 examples, 100% trigger, exact marker spans, and exact suggestion parity).
- `tests/upstream/test_upstream_pattern_rules.py`: Ported tests from `PatternRuleLoaderTest`, `PatternRuleMatcherTest`, `PatternRuleTest`, `RussianPatternRuleTest` with inflected exact semantics.

---

## 4. Test & Verification Results

All 248 test cases across the entire project test suite passed cleanly with 0 skips and 0 failures:

```
============================ 248 passed in 33.57s =============================
```

Detailed test suite breakdown:
- `tests/unit/test_grammar_inventory.py`: 2 passed
- `tests/unit/test_russian_chunker.py`: 5 passed
- `tests/unit/test_grammar_engine_core.py`: 10 passed
- `tests/unit/test_real_wheel_grammar.py`: 1 passed
- `tests/upstream/test_russian_chunker_oracle_parity.py`: 4 passed (34 oracle cases)
- `tests/upstream/test_russian_grammar_oracle_parity.py`: 3 passed (62 oracle cases)
- `tests/upstream/test_pattern_token_oracle_parity.py`: 2 passed (6 oracle cases)
- `tests/upstream/test_russian_grammar_examples.py`: 3 passed (988 examples across 506 rules)
- `tests/upstream/test_upstream_pattern_rules.py`: 8 passed
- Existing tests (tokenization, tagset, dictionary, tagger, disambiguator, synthesizer, SRX, licenses): 210 passed

### Upstream Test Accounting (Explicit Units)
- `upstream_test_files_total`: 18
- `task_0007_source_test_files_translated`: 4 (`PatternRuleLoaderTest`, `PatternRuleMatcherTest`, `PatternRuleTest`, `RussianPatternRuleTest`)
- `task_0007_python_tests_passed`: 8
- `remaining_upstream_test_files_not_ported`: 14

### Oracle Provenance & Environment
- Oracle Build ID: `lt_6.8_source_build_jdk17_stefan`
- Oracle JAR SHA-256: `b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc`
- Total Grammar & Chunker Oracle Cases: 102 cases
- Python Version: `3.10.11`
- Target Branch: `main`

### Automated Real-Wheel Package Test
- `tests/unit/test_real_wheel_grammar.py` builds the `.whl` package, verifies `grammar.xml` inside the archive, installs into an isolated temporary directory, and executes the complete `raw -> tag -> disambiguate -> chunk -> grammar check` pipeline in a clean subprocess with `PYTHONPATH` isolated from repo source.

---

## 5. Compatibility & Upstream Parity Inventory

- Pinned Upstream Version: LanguageTool `v6.8` (commit `e807fcde6a6506191e1470744d2345da28c26be6`).
- Total XML Rules: 892 across 8 categories and 297 rulegroups
  - Core Runnable (Task 0007): 506 (56.7%)
  - Deferred to Advanced Matching (Task 0008): 157 (17.6%)
  - Deferred to Unification (Task 0009): 8 (0.9%)
  - Deferred to Java Filters (Task 0010): 64 (7.2%)
  - Multi-blocker Deferred: 157 (17.6%)
  - Unrecognized / Silent: 0 (0.0%)
- Examples: 988 core runnable examples / 1458 deferred examples (2446 total)

---

## 6. Known Limitations & Blocked Items

- Advanced matching constructs (`<and>`, `<or>`, `<phrase>`, `skip="..."`, `min/max`, `scope="next"`, `scope="previous"`, `spacebefore`) are cleanly deferred to Task 0008.
- Feature unification (`<unification>`, `<unify>`, `<feature>`, `<equivalence>`) is cleanly deferred to Task 0009.
- Custom Java rule filters (`filter class="..."`, `AdvancedSynthesizerFilter`, `DateCheckFilter`, `RussianPartialPosTagFilter`, etc.) are cleanly deferred to Task 0010.
- All deferred rules raise `UnsupportedGrammarFeatureError` fail-closed when directly invoked, with zero silent partial execution.

---

## 7. License & Provenance Findings

- Pinned upstream `grammar.xml` provenance: `languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/grammar.xml` at commit `e807fcde6a6506191e1470744d2345da28c26be6` (LGPL 2.1+).
- SHA-256 hash verified: `e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec`.
- All 105 vendored upstream files have verified LGPL licensing in `license_inventory.json` with 0 items in `BLOCKED_LICENSE_REVIEW`.

---

## 8. Detailed Blocker Breakdown & Git Completion

### 8.1 Canonical Inventory Blocker Counts by Feature and Task

From canonical inventory `compat/russian_grammar_core_inventory.json` across all 892 rules:

#### Classification by Primary Target Task
- `CORE_0007_RUNNABLE`: 506 rules (56.7%)
- `DEFERRED_0008_ADVANCED_MATCHING`: 157 rules (17.6%)
- `DEFERRED_0009_UNIFICATION`: 8 rules (0.9%)
- `DEFERRED_0010_FILTER`: 64 rules (7.2%)
- `MULTI_BLOCKER`: 157 rules (17.6%)
- `UNRECOGNIZED_CONSTRUCT`: 0 rules (0.0%)
- **Total Deferred Rules**: 386 rules (43.3%)

#### Blocker Occurrences by Specific Feature
- `filter` (Java filter class): 178 rules
- `skip` (`skip="N"` attribute): 144 rules
- `unification` (`<unify>`, `<unification>`, `<feature>`): 85 rules
- `or` (`<or>` construct): 44 rules
- `and` (`<and>` construct): 40 rules
- `phrase` (`<phrase>` construct): 30 rules
- `exception_scope` (`scope="previous|next"`): 28 rules
- `token_match` (`<token><match .../></token>`): 24 rules
- `min_max` (`min="N"`, `max="N"` token repetition): 10 rules
- `spacebefore` (`spacebefore="yes|no"`): 6 rules

### 8.2 Git Completion

- **Implementation/Review-Fix Commit SHA**: `067477885c14ccdad876f0fb9d4ca062ec3597eb`
- **Push Target Branch**: `origin/main`
- **Remote Verification**: Commit verified present on `origin/main` (clean remote sync).
