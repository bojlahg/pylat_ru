# Completion Report — Task 0007: RussianChunker + XML Grammar Engine Core (Conformance Review Complete)

## 1. Task Summary

Task 0007 implements the native Python `RussianChunker` and the core XML Grammar Rule Engine for `pylat_ru` matching upstream Java LanguageTool `v6.8` semantics:

- **Strict Fail-Closed Schema & Structural Rule Classification**:
  - `GrammarLoader` strictly validates allowed child elements per parent context, allowed attributes per element context, and enumerated values (`default="on|off|temp_off"`, boolean flags `yes|no`, integer constraints). Any malformed integer, boolean, or unknown attribute/element raises a typed `GrammarFormatError`.
  - Preserves full structural metadata for deferred rules: `<filter class="..." args="...">`, `<unification>` / `<feature>` / `<equivalence>`, `<antipattern>`, and all `<match>` attributes (`setpos`, `regexp_match`, `regexp_replace`, `sub_type`, etc.).
  - `tools/russian_grammar_core_inventory.py` analyzes all 892 rules in `grammar.xml` and dynamically extracts regexes, syntax expansions, and phrase types directly from `RussianChunker.java` source AST.
  - Exactly classified all 892 rules into deterministic execution states:
    - `CORE_0007_RUNNABLE`: 506 rules (56.7%)
    - `DEFERRED_0008_ADVANCED_MATCHING`: 157 rules (17.6%)
    - `DEFERRED_0009_UNIFICATION`: 8 rules (0.9%)
    - `DEFERRED_0010_FILTER`: 64 rules (7.2%)
    - `MULTI_BLOCKER`: 157 rules (17.6%)
    - `UNRECOGNIZED_CONSTRUCT`: 0 rules (0.0%)
  - Generated committed reference inventory `compat/russian_grammar_core_inventory.json` with SHA-256 byte-exact regeneration tests.
  - Pinned all 20 required upstream Java/XML source files in `UPSTREAM.json` and `license_inventory.json` with recorded size, SHA-256 hash, and verified LGPL license status.

- **Native Russian Chunker (`pylat_ru.chunking`)**:
  - Implemented `TokenExpression` predicate parser, conjunction evaluator, and greedy regex sequence matching.
  - Implemented `RussianChunker` with all 21 `REGEXES1` and 3 `REGEXES2` phrase rules parsed from `RussianChunker.java`.
  - Implemented chunk tag assignment (`/B-NP`, `/I-NP`, `/B-VP`, `/I-VP`, `/B-ADJP`, `/I-ADJP`, etc.), `FILTER_TAGS` reading selection, `SYNTAX_EXPANSION`, `MayMissingYO` reading preservation, and preservation of pre-existing user chunk tags outside `FILTER_TAGS`.
  - Added 4 synthetic boundary test cases (`chunk_31_preexisting_tag`, `chunk_32_overwrite_conflict`, `chunk_33_may_missing_yo_exclusion`, `chunk_34_ambiguous_readings`).
  - Verified 100% differential parity against Java LanguageTool oracle (`tests/fixtures/oracle_russian_chunker.json`, 34 test cases) asserting all 12 serialized token fields unconditionally pre-chunker and post-chunker.

- **Core XML Grammar Engine (`pylat_ru.grammar`)**:
  - Domain models: `GrammarRule`, `Pattern`, `PatternToken`, `PatternTokenException`, `MatchReference`, `FilterConfig`, `FeatureDef`, `EquivalenceDef`, `UnificationDef`, `MessageTemplate`, `SuggestionTemplate`, `Example`, `RuleMatchResult`.
  - Precompiled pattern matching engine (`CompiledPattern`, `CompiledPatternToken`, `CompiledTokenException`) supporting:
    - Text matching (exact, case-sensitive, case-insensitive, regex with non-capturing grouping `^(?:...)$`, inflected lemma/surface matches, sentence-initial capitalization relaxation).
    - POS tag matching (literal, regex, negation).
    - Exceptions (negated POS, text regex, lemma, token-level exclusion).
    - Marker error spans (`<marker>...</marker>`).
  - Template formatter (`TemplateFormatter`) resolving `<match no="X">` references, regex transformations (`regexp_match` / `regexp_replace`), case conversions (`alllower`, `allupper`, `startlower`, `startupper`, `firstupper`, `preserve`), and Java LT-compatible capitalization adjustments (`StringTools.isAllUppercase(List<String>)`).
  - `RussianGrammarEngine` supporting full-sentence scanning, rule filtering, individual rule testing, rule enabling/disabling, dual UTF-16 code units and Python codepoint offset derivations, and fail-closed errors (`UnsupportedGrammarFeatureError`) on deferred rules.

- **Differential Parity and Conformance**:
  - 100% field-level parity against Java LT Oracle across 62 curated test cases in `tests/fixtures/oracle_russian_grammar_core.json`, asserting rule IDs, category metadata, descriptions, default states, match counts, UTF-16 spans, codepoint slices, messages, short messages, and suggestions.
  - 100% pass rate across all 988 examples for all 506 core-runnable rules in `grammar.xml` (525 incorrect examples detected with exact marker spans, suggested replacements, and order; 463 correct examples passed with 0 false triggers).

---

## 2. Important Files Added and Changed

### Core Implementation
- `src/pylat_ru/chunking/__init__.py`: Package init exporting `RussianChunker`, `ChunkTaggedToken`, `TokenExpression`.
- `src/pylat_ru/chunking/token_expression.py`: Token expression parser, predicate logic, and sequence matching.
- `src/pylat_ru/chunking/russian.py`: Russian phrase chunker implementing all 24 upstream rules with chunk tag preservation.
- `src/pylat_ru/grammar/__init__.py`: Grammar engine package init.
- `src/pylat_ru/grammar/errors.py`: Error hierarchy (`GrammarError`, `UnsupportedGrammarFeatureError`, `GrammarResourceError`, `GrammarFormatError`, `GrammarRuleDisabledError`).
- `src/pylat_ru/grammar/model.py`: Domain models with complete structural metadata for deferred features.
- `src/pylat_ru/grammar/classifier.py`: Structural rule classifier for all 892 rules.
- `src/pylat_ru/grammar/loader.py`: Strict fail-closed XML rule loader validating allowed children and attributes per context.
- `src/pylat_ru/grammar/matcher.py`: Precompiled token predicate and pattern matcher with refined sentence start case relaxation.
- `src/pylat_ru/grammar/formatter.py`: Message and suggestion template renderer with regex replacements and case conversion.
- `src/pylat_ru/grammar/engine.py`: `RussianGrammarEngine` execution runtime with dual UTF-16 / Python codepoint offsets.
- `src/pylat_ru/tagging/string_tools.py`: Restored exact Java `StringTools.isAllUppercase(String)` and `isAllUppercase(List<String>)`.
- `src/pylat_ru/resources/rules/ru/grammar.xml`: Pinned upstream `grammar.xml` (SHA-256 `e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec`).
- `pyproject.toml`: Added package data inclusion for `pylat_ru.resources.rules.ru`.

### Tooling & Compatibility
- `tools/russian_grammar_core_inventory.py`: Dynamic AST chunker parser and deterministic inventory generator.
- `compat/russian_grammar_core_inventory.json`: Committed grammar core inventory (892 rules).
- `compat/compatibility.json`: Reconciled oracle counts (`synthesizer_oracle_queries_total = 52`, `chunker_oracle_cases_total = 34`).
- `third_party/languagetool/UPSTREAM.json`: Updated with all 105 vendored files and SHA-256 digests.
- `third_party/languagetool/license_inventory.json`: Updated with all 105 vendored files, 0 blocked license reviews.
- `tools/differential_lt.py`: Added synthetic boundary cases and regenerated fixtures.
- `tests/fixtures/oracle_russian_chunker.json`: 34 chunker oracle test cases.
- `tests/fixtures/oracle_russian_grammar_core.json`: 62 grammar core oracle test cases.

### Tests
- `tests/unit/test_grammar_inventory.py`: Deterministic inventory regeneration and invariant tests.
- `tests/unit/test_russian_chunker.py`: Unit tests for chunker components and regex expressions.
- `tests/unit/test_grammar_engine_core.py`: Unit tests for loader fail-closed validation, matcher, formatter, engine, emoji/non-BMP offsets.
- `tests/unit/test_real_wheel_grammar.py`: Automated wheel packaging, resource inspection, and isolated subprocess execution test.
- `tests/upstream/test_russian_chunker_oracle_parity.py`: 100% oracle differential test for chunker (34 cases, 12 token fields unconditionally asserted).
- `tests/upstream/test_russian_grammar_oracle_parity.py`: 100% oracle differential test for grammar core (62 cases, 100% field-level parity).
- `tests/upstream/test_russian_grammar_examples.py`: Executable XML examples test suite for all 506 core-runnable rules (988 examples, 100% trigger and full example parity).
- `tests/upstream/test_upstream_pattern_rules.py`: Ported tests from `PatternRuleLoaderTest`, `PatternRuleMatcherTest`, `PatternRuleTest`, `RussianPatternRuleTest`.

---

## 3. Test & Verification Results

All 244 test cases across the entire project test suite passed cleanly:

```
============================ 244 passed in 31.62s =============================
```

Detailed test suite breakdown:
- `tests/unit/test_grammar_inventory.py`: 2 passed
- `tests/unit/test_russian_chunker.py`: 5 passed
- `tests/unit/test_grammar_engine_core.py`: 9 passed
- `tests/unit/test_real_wheel_grammar.py`: 1 passed
- `tests/upstream/test_russian_chunker_oracle_parity.py`: 4 passed (34 oracle cases)
- `tests/upstream/test_russian_grammar_oracle_parity.py`: 3 passed (62 oracle cases)
- `tests/upstream/test_russian_grammar_examples.py`: 3 passed (988 examples across 506 rules)
- `tests/upstream/test_upstream_pattern_rules.py`: 7 passed
- Existing tests (tokenization, tagset, dictionary, tagger, disambiguator, synthesizer, SRX, licenses): 210 passed

### Automated Real-Wheel Package Test
- `tests/unit/test_real_wheel_grammar.py` builds the `.whl` package, verifies `grammar.xml` inside the archive, installs into an isolated temporary directory, and executes the complete `raw -> tag -> disambiguate -> chunk -> grammar check` pipeline in a clean subprocess with `PYTHONPATH` isolated from repo source.

---

## 4. Compatibility & Upstream Parity Inventory

- Pinned Upstream Version: LanguageTool `v6.8` (commit `e807fcde6a6506191e1470744d2345da28c26be6`).
- Total XML Rules: 892
  - Core Runnable (Task 0007): 506 (56.7%)
  - Deferred to Advanced Matching (Task 0008): 157 (17.6%)
  - Deferred to Unification (Task 0009): 8 (0.9%)
  - Deferred to Java Filters (Task 0010): 64 (7.2%)
  - Multi-blocker Deferred: 157 (17.6%)
  - Unrecognized / Silent: 0 (0.0%)

---

## 5. Known Limitations & Blocked Items

- Advanced matching constructs (`<and>`, `<or>`, `<phrase>`, `skip="..."`, `min/max`, `scope="next"`, `scope="previous"`, `spacebefore`) are cleanly deferred to Task 0008.
- Feature unification (`<unification>`, `<unify>`, `<feature>`, `<equivalence>`) is cleanly deferred to Task 0009.
- Custom Java rule filters (`filter class="..."`, `AdvancedSynthesizerFilter`, `DateCheckFilter`, `RussianPartialPosTagFilter`, etc.) are cleanly deferred to Task 0010.
- All deferred rules raise `UnsupportedGrammarFeatureError` fail-closed when directly invoked, with zero silent partial execution.

---

## 6. License & Provenance Findings

- Pinned upstream `grammar.xml` provenance: `languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/grammar.xml` at commit `e807fcde6a6506191e1470744d2345da28c26be6` (LGPL 2.1+).
- SHA-256 hash verified: `e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec`.
- All 105 vendored upstream files have verified LGPL licensing in `license_inventory.json` with 0 items in `BLOCKED_LICENSE_REVIEW`.
