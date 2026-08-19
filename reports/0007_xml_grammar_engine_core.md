# Completion Report — Task 0007: RussianChunker + XML Grammar Engine Core

## 1. Task Summary

Task 0007 implements the native Python `RussianChunker` and the core XML Grammar Rule Engine for `pylat_ru` matching upstream Java LanguageTool `v6.8` semantics:

- **Structural Rule Classification & Inventory**:
  - Implemented `tools/russian_grammar_core_inventory.py` analyzing all 892 rules in `grammar.xml`.
  - Exactly classified all 892 rules into deterministic execution states:
    - `CORE_0007_RUNNABLE`: 506 rules (56.7%)
    - `DEFERRED_0008_ADVANCED_SYNTAX`: 157 rules (17.6%)
    - `DEFERRED_0009_UNIFICATION`: 8 rules (0.9%)
    - `DEFERRED_0010_FILTERS`: 64 rules (7.2%)
    - `MULTI_BLOCKER`: 157 rules (17.6%)
    - `UNRECOGNIZED_CONSTRUCT`: 0 rules (0.0%)
  - Generated committed reference inventory `compat/russian_grammar_core_inventory.json` with SHA-256 byte-exact regeneration tests.

- **Native Russian Chunker (`pylat_ru.chunking`)**:
  - Implemented `TokenExpression` predicate parser, conjunction evaluator, and greedy regex sequence matching.
  - Implemented `RussianChunker` with all 21 `REGEXES1` and 3 `REGEXES2` rules from `org.languagetool.chunking.RussianChunker`.
  - Implemented chunk tag assignment (`/B-NP`, `/I-NP`, `/B-VP`, `/I-VP`, `/B-ADJP`, `/I-ADJP`, etc.), `FILTER_TAGS` reading selection, `SYNTAX_EXPANSION`, and `MayMissingYO` reading preservation.
  - Verified 100% differential parity against Java LanguageTool oracle (`tests/fixtures/oracle_russian_chunker.json`, 30 test cases).

- **Core XML Grammar Engine (`pylat_ru.grammar`)**:
  - Domain models: `GrammarRule`, `Pattern`, `PatternToken`, `PatternTokenException`, `MessageTemplate`, `SuggestionTemplate`, `Example`, `RuleMatchResult`.
  - Precompiled pattern matching engine (`CompiledPattern`, `CompiledPatternToken`, `CompiledTokenException`) supporting:
    - Text matching (exact, case-sensitive, case-insensitive, regex with non-capturing grouping `^(?:...)$`, inflected lemma/surface matches, sentence-initial capitalization relaxation).
    - POS tag matching (literal, regex, negation).
    - Exceptions (negated POS, text regex, lemma, token-level exclusion).
    - Marker error spans (`<marker>...</marker>`).
  - Template formatter (`TemplateFormatter`) resolving `<match no="X">` and `\1`, `\2`, ... token backreferences and Java LT-compatible capitalization adjustments.
  - `RussianGrammarEngine` supporting full-sentence scanning, rule filtering, individual rule testing, rule enabling/disabling, UTF-16 code unit offset calculations, and fail-closed errors (`UnsupportedGrammarFeatureError`) on deferred rules.

- **Differential Parity and Conformance**:
  - 100% parity against Java LT Oracle across 62 curated test cases in `tests/fixtures/oracle_russian_grammar_core.json`.
  - 100% pass rate across all 988 examples for all 506 core-runnable rules in `grammar.xml` (525 incorrect examples detected with 0 misses, 463 correct examples passed with 0 false triggers).

---

## 2. Important Files Added and Changed

### Core Implementation
- `src/pylat_ru/chunking/__init__.py`: Package init exporting `RussianChunker`, `ChunkTaggedToken`, `TokenExpression`.
- `src/pylat_ru/chunking/token_expression.py`: Token expression parser, predicate logic, and sequence matching.
- `src/pylat_ru/chunking/russian.py`: Russian phrase chunker implementing all 24 upstream rules.
- `src/pylat_ru/grammar/__init__.py`: Grammar engine package init.
- `src/pylat_ru/grammar/errors.py`: Error hierarchy (`GrammarError`, `UnsupportedGrammarFeatureError`, `GrammarResourceError`, `GrammarFormatError`, `GrammarRuleDisabledError`).
- `src/pylat_ru/grammar/model.py`: Domain models and data structures.
- `src/pylat_ru/grammar/classifier.py`: Structural rule classifier for all 892 rules.
- `src/pylat_ru/grammar/loader.py`: XML rule loader parsing `grammar.xml`.
- `src/pylat_ru/grammar/matcher.py`: Precompiled token predicate and pattern matcher.
- `src/pylat_ru/grammar/formatter.py`: Message and suggestion template renderer.
- `src/pylat_ru/grammar/engine.py`: `RussianGrammarEngine` execution runtime.
- `src/pylat_ru/resources/rules/ru/grammar.xml`: Paged upstream `grammar.xml` (SHA-256 `e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec`).
- `src/pylat_ru/resources/rules/__init__.py`, `src/pylat_ru/resources/rules/ru/__init__.py`: Resource package markers.
- `pyproject.toml`: Added package data inclusion for `pylat_ru.resources.rules.ru`.

### Tooling & Compatibility
- `tools/russian_grammar_core_inventory.py`: Deterministic inventory generator.
- `compat/russian_grammar_core_inventory.json`: Committed grammar core inventory (892 rules).
- `compat/compatibility.json`: Updated status to `0007_xml_grammar_engine_core`.
- `tools/differential_lt.py`: Added `chunk_sentences`, `check_pattern_rules`, `--generate-chunker-fixtures`, and `--generate-grammar-core-fixtures`.
- `tests/fixtures/oracle_russian_chunker.json`: 30 chunker oracle test cases.
- `tests/fixtures/oracle_russian_grammar_core.json`: 62 grammar core oracle test cases.

### Tests
- `tests/unit/test_grammar_inventory.py`: Deterministic inventory regeneration and invariant tests.
- `tests/unit/test_russian_chunker.py`: Unit tests for chunker components and regex expressions.
- `tests/unit/test_grammar_engine_core.py`: Unit tests for loader, matcher, formatter, engine, exceptions.
- `tests/upstream/test_russian_chunker_oracle_parity.py`: 100% oracle differential test for chunker (30 cases).
- `tests/upstream/test_russian_grammar_oracle_parity.py`: 100% oracle differential test for grammar core (62 cases).
- `tests/upstream/test_russian_grammar_examples.py`: Executable XML examples test suite for all 506 core-runnable rules (988 examples, 0 failures).

---

## 3. Test & Verification Results

All 230 test cases across the entire project test suite passed:

```
============================ 230 passed in 25.13s =============================
```

Summary of test suite:
- `tests/unit/test_grammar_inventory.py`: 2 passed
- `tests/unit/test_russian_chunker.py`: 5 passed
- `tests/unit/test_grammar_engine_core.py`: 7 passed
- `tests/upstream/test_russian_chunker_oracle_parity.py`: 2 passed (30 oracle cases)
- `tests/upstream/test_russian_grammar_oracle_parity.py`: 2 passed (62 oracle cases)
- `tests/upstream/test_russian_grammar_examples.py`: 2 passed (988 examples across 506 rules)
- Existing tests (tokenization, tagset, dictionary, tagger, disambiguator, synthesizer): 210 passed

### Isolated Wheel Package Smoke Test
- Built clean wheel distribution: `dist/pylat_ru-0.1.0a0-py3-none-any.whl` (3.13 MB).
- Extracted and executed end-to-end grammar pipeline smoke test in isolated Python process without Java runtime: Passed with zero errors.

---

## 4. Compatibility & Upstream Parity Inventory

- Pinned Upstream Version: LanguageTool `v6.8` (commit `e807fcde6a6506191e1470744d2345da28c26be6`).
- Total XML Rules: 892
  - Core Runnable (Task 0007): 506 (56.7%)
  - Deferred to Advanced Syntax (Task 0008): 157 (17.6%)
  - Deferred to Unification (Task 0009): 8 (0.9%)
  - Deferred to Java Filters (Task 0010): 64 (7.2%)
  - Multi-blocker Deferred: 157 (17.6%)
  - Unrecognized / Silent: 0 (0.0%)

---

## 5. Known Limitations & Blocked Items

- Advanced syntax constructs (`<and>`, `<or>`, `<phrase>`, `skip="..."`, `min/max`, `scope="next"`, `scope="previous"`, `spacebefore`) are cleanly deferred to Task 0008.
- Feature unification (`<unification>`, `<unify>`, `<feature>`, `<equivalence>`) is cleanly deferred to Task 0009.
- Custom Java rule filters (`filter class="..."`, `AdvancedSynthesizerFilter`, `DateCheckFilter`, `RussianPartialPosTagFilter`, etc.) are cleanly deferred to Task 0010.
- All deferred rules raise `UnsupportedGrammarFeatureError` fail-closed when directly invoked, with zero silent partial execution.

---

## 6. License & Provenance Findings

- Pinned upstream `grammar.xml` provenance: `languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/grammar.xml` at commit `e807fcde6a6506191e1470744d2345da28c26be6` (LGPL 2.1+).
- SHA-256 hash verified: `e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec`.
