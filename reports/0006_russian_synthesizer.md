# Task 0006 Completion Report: Russian Synthesizer Parity

**Task Number**: 0006  
**Title**: Russian Synthesizer Parity (`tasks/0006_russian_synthesizer.md`)  
**Status**: COMPLETED (with Review Fixes)  
**Pinned Target**: LanguageTool v6.8 (`e807fcde6a6506191e1470744d2345da28c26be6`), Morfologik 2.1.9  

---

## 1. Executive Summary

Task 0006 establishes the native Python reimplementation of the complete LanguageTool Russian word form synthesis subsystem with 100% behavioral parity against pinned Java LanguageTool 6.8:

1. **`ManualSynthesizer` Overlay Parser**:
   - Parses manual synthesis mappings (`added.txt`, `removed.txt`).
   - Input format contains plain-text full forms (`fullform\tbaseform\tpostag`). Forms are stored and returned directly without suffix decoding (Java's internal `+/++` was an in-memory compression in Java's flat String array, not an input syntax).
   - Exact Java parsing semantics:
     - Line-level trim matching Java `trim()`.
     - Non-breaking spaces (`\u00A0`) raise typed `ManualSynthesizerFormatError`.
     - Supports `#separatorRegExp=` configuration directives (default `\t`), with empty or invalid regex raising `ManualSynthesizerFormatError`.
     - Comment stripping (full-line `#` comments and inline `#` comments).
     - Field splitting matching Java `Pattern.split(sep, 0)` semantics via shared `java_regex_split()` (no capturing groups in split output, trailing empty fields dropped).
     - Malformed rows (field count != 3) raise `ManualSynthesizerFormatError` with line number and source path context.
   - Nonexistent resources raise `SynthesisResourceError`.
   - Thread-safe, non-destructive form lookup grouping by `(lemma, pos_tag)`.

2. **`BaseSynthesizer` & `RussianSynthesizer` Engine**:
   - Implements abstract `Synthesizer` interface matching `org.languagetool.synthesis.Synthesizer`.
   - Combines low-level Morfologik synthesis dictionary lookups (`russian_synth.dict` + `russian_synth.info`) with manual additions (`added.txt`) and manual removals (`removed.txt`).
   - Exact lemma semantics: When `AnalyzedToken.lemma` is `None`, synthesis returns `[]` immediately without falling back to token surface.
   - Case sensitivity: Lemma lookups are strictly case-sensitive matching Morfologik FSA dictionary keys.
   - Exception filtering via `remove_exceptions()` / `is_exception()`.
   - Special number tags:
     - `_spell_number_`: returns `[get_spelled_number(token.token)]`
     - `_spell_number_:feminine`: returns `[get_spelled_number("feminine " + token.token)]`
     - `_spell_number_:Roman`: returns `[get_roman_number(token.token)]` via native integer-to-Roman converter matching `Roman.sor`.
   - Regex synthesis (`pos_tag_is_regex=True`):
     - Expands across all known tags in `tags_russian.txt` + `added.txt` in deterministic upstream order.
     - Supports trailing-empty tags such as `VB:INF:`.
     - Replicates LanguageTool's exact error message on invalid regex: `f"Error trying to synthesize POS tag {pos_tag} (posTagRegExp: true) from token {token.token}"`.
   - Fail-closed resource loading: Missing or corrupted packaged resources (`russian_synth.dict`, `russian_synth.info`, `tags_russian.txt`, `added.txt`, `removed.txt`) raise `SynthesisResourceError` without fallback to checkout data.
   - Singleton pattern: `RussianSynthesizer.get_instance()` and `RussianSynthesizer.INSTANCE()`.

3. **Packaged Runtime Resources & Real Wheel Distribution**:
   - Packaged verified byte-identical upstream assets into `src/pylat_ru/resources/ru/`:
     - `russian_synth.dict` (1,481,255 bytes, SHA-256: `299addaa9d5ccf7e95b84e48eeef5ccbd1a2137112204f56e4d5234fc6c86311`)
     - `russian_synth.info` (431 bytes, SHA-256: `916c0ff9a6101c5f36e33c109b15e9cd37da0e75b772f97bca1df8f5fcdcca3b`)
     - `tags_russian.txt` (27,195 bytes, SHA-256: `1efed64cfc852bb4619da092034dcb208acde303baeb55109718afe9cf56729a`)
     - `added.txt` (92,745 bytes, SHA-256: `4748f15da5cf97095e4d96dda3a3431028c660ff2456c30f143162616d0d8b40`)
     - `removed.txt` (3,205 bytes, SHA-256: `193c3174a137a5343b1dd7ad5a0314716c3e4023f75f57e161d6f99e2c7baff5`)
   - `test_real_installed_distribution_package_synthesis` builds a real `.whl`, verifies that all 5 resources are present in the archive, installs into an isolated directory, and executes addition, removal, and Roman lookups in an isolated subprocess.

4. **Differential Oracle & Fixture Integrity**:
   - Updated `tools/differential_lt.py` with `synthesize_queries()` and `--generate-synthesizer-fixtures` CLI command, properly passing `\u0005null` sentinels for `lemma=None` cases to the Java oracle.
   - Generated and committed `tests/fixtures/oracle_russian_synthesizer_sample.json` directly from Java LanguageTool 6.8 standalone oracle (build `lt_6.8_source_build_jdk17_stefan`, JAR SHA-256: `b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc`).
   - `test_fixture_integrity` validates fixture metadata against `compat/oracle_manifest.json` (exact version, commit, build ID, and JAR SHA-256).
   - Parity suite tests all 43 queries (nouns, verbs, adjectives, irregulars, manual additions, manual removals, null lemma, case sensitivity, unknown tags/words, trailing-empty tags, and Roman numbers), achieving 100% exact match.

5. **Synthesizer Inventory Generation**:
   - `tools/russian_synthesizer_inventory.py` dynamically analyzes all upstream Java sources, FSA headers, tag sequence, overlays, material removals, and exclusions, generating `compat/russian_synthesizer_inventory.json` with byte-exact deterministic regeneration test.

---

## 2. Key Files Added and Modified

### Added Implementation Files
- `src/pylat_ru/utils.py`: Shared Java-compatible regex splitter (`java_regex_split`).
- `src/pylat_ru/synthesis/errors.py`: Synthesis exception hierarchy (`SynthesisError`, `ManualSynthesizerFormatError`, `SynthesisResourceError`).
- `src/pylat_ru/synthesis/__init__.py`: Synthesis package exports.
- `src/pylat_ru/synthesis/roman.py`: Roman numeral conversion matching `Roman.sor`.
- `src/pylat_ru/synthesis/manual.py`: `ManualSynthesizer` overlay parser.
- `src/pylat_ru/synthesis/synthesizer.py`: `Synthesizer`, `BaseSynthesizer`, and `RussianSynthesizer` implementations.
- `src/pylat_ru/resources/ru/russian_synth.dict`: Pinned binary Morfologik FSA synthesis dictionary.
- `src/pylat_ru/resources/ru/russian_synth.info`: Synthesis dictionary metadata.
- `src/pylat_ru/resources/ru/tags_russian.txt`: Canonical Russian POS tag list.
- `tools/russian_synthesizer_inventory.py`: Deterministic inventory generator.
- `compat/russian_synthesizer_inventory.json`: Committed Russian synthesizer inventory.

### Modified Files
- `src/pylat_ru/__init__.py`: Exported `RussianSynthesizer`, `Synthesizer`, `BaseSynthesizer`, `ManualSynthesizer`.
- `src/pylat_ru/tagging/word_tagger.py`: Reused shared `java_regex_split` from `pylat_ru.utils`.
- `tools/differential_lt.py`: Added `synthesize_queries()`, `SYNTHESIS_TEST_QUERIES`, `generate_synthesizer_fixtures()`, and `--generate-synthesizer-fixtures` flag.
- `compat/compatibility.json`: Updated milestone to `0006_russian_synthesizer`, overall state to `SYNTHESIZER_LAYER_ESTABLISHED`, added `russian_synthesizer` section, set `RussianSynthesizer: "SUPPORTED"`.

### Added Test Files & Fixtures
- `tasks/0006_russian_synthesizer.md`: Numbered task specification.
- `tests/upstream/test_russian_synthesizer.py`: Direct port of upstream `RussianSynthesizerTest.java`.
- `tests/test_manual_synthesizer.py`: Unit tests for `ManualSynthesizer`.
- `tests/test_synthesizer_subsystem.py`: Comprehensive synthesizer tests.
- `tests/upstream/test_russian_synthesizer_oracle_parity.py`: Exact parity and manifest integrity tests against committed oracle fixture.
- `tests/unit/test_russian_synthesizer_resources.py`: Resource hash parity, inventory byte-exact regeneration, and real wheel distribution installation test.
- `tests/fixtures/oracle_russian_synthesizer_sample.json`: Committed Java LanguageTool 6.8 synthesis oracle fixture (43 queries).

---

## 3. Test & Verification Results

Full repository test suite execution:
```bash
pytest -v
```
Output:
```text
============================ 208 passed in 20.65s =============================
```

All 208 tests passed with 0 failures, 0 skipped, and zero regressions.

---

## 4. Known Limitations & Scope Boundaries

- Number spelling for Russian (`_spell_number_` without Roman) returns the input number string unchanged because Russian has no upstream `.sor` file in LanguageTool (matches Java LT `RussianSynthesizer` behavior).
- Custom overlays (`added_custom.txt`, `removed_custom.txt`) and `do-not-synthesize.txt` are explicitly excluded from `RussianSynthesizer` matching upstream LT 6.8.
- Higher-level rule engine integration (`AdvancedSynthesizerFilter`, `match` elements with synthesis attributes) is scheduled for subsequent tasks (Task 0007 / Task 0008 / Task 0010).
- Production runtime has zero Java/JRE and zero external NLP dependencies.
