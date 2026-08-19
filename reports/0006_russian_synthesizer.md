# Task 0006 Completion Report: Russian Synthesizer Parity

**Task Number**: 0006  
**Title**: Russian Synthesizer Parity (`tasks/0006_russian_synthesizer.md`)  
**Status**: COMPLETED  
**Pinned Target**: LanguageTool v6.8 (`e807fcde6a6506191e1470744d2345da28c26be6`), Morfologik 2.1.9  

---

## 1. Executive Summary

Task 0006 establishes the native Python reimplementation of the complete LanguageTool Russian word form synthesis subsystem:

1. **`ManualSynthesizer` Overlay Parser**:
   - Parses manual synthesis mappings (`added.txt`, `removed.txt`).
   - Supports `#separatorRegExp=` configuration directives (default `\t`).
   - Supports comments (`#` lines and inline `#` comments stripped from right).
   - Form suffix decoding: `++` strips 1 char from lemma before appending suffix; `+` appends suffix to lemma; otherwise literal full form.
   - Collects unique POS tags in `possible_tags`.
   - Thread-safe, non-destructive form lookup grouping by `(lemma, pos_tag)`.

2. **`BaseSynthesizer` & `RussianSynthesizer` Engine**:
   - Implements abstract `Synthesizer` interface matching `org.languagetool.synthesis.Synthesizer`.
   - Combines low-level Morfologik synthesis dictionary lookups (`russian_synth.dict` + `russian_synth.info`) with manual additions (`added.txt`) and manual removals (`removed.txt`).
   - Exception filtering via `remove_exceptions()` / `is_exception()`.
   - Special number tags:
     - `_spell_number_`: returns `[get_spelled_number(token.token)]`
     - `_spell_number_:feminine`: returns `[get_spelled_number("feminine " + token.token)]`
     - `_spell_number_:Roman`: returns `[get_roman_number(token.token)]` via native integer-to-Roman converter matching `Roman.sor`.
   - Regex synthesis (`pos_tag_is_regex=True`):
     - Expands across all known tags in `tags_russian.txt` + `added.txt` in deterministic upstream order.
     - Replicates LanguageTool's exact error message on invalid regex: `f"Error trying to synthesize POS tag {pos_tag} (posTagRegExp: true) from token {token.token}"`.
   - Predicate synthesis (`synthesize_for_pos_tags`).
   - Tag utility methods: `get_pos_tag_correction` and `get_target_pos_tag`.
   - Singleton pattern: `RussianSynthesizer.get_instance()` and `RussianSynthesizer.INSTANCE()`.
   - Thread-safe lazy initialization of possible tags.

3. **Packaged Runtime Resources & Real Wheel Distribution**:
   - Packaged verified byte-identical upstream assets into `src/pylat_ru/resources/ru/`:
     - `russian_synth.dict` (1,481,255 bytes, SHA-256: `299addaa9d5ccf7e95b84e48eeef5ccbd1a2137112204f56e4d5234fc6c86311`)
     - `russian_synth.info` (431 bytes, SHA-256: `916c0ff9a6101c5f36e33c109b15e9cd37da0e75b772f97bca1df8f5fcdcca3b`)
     - `tags_russian.txt` (27,195 bytes, SHA-256: `1efed64cfc852bb4619da092034dcb208acde303baeb55109718afe9cf56729a`)
   - `test_real_installed_distribution_package_synthesis` builds a real `.whl`, verifies that all resources are packaged, installs into an isolated site-packages directory, and verifies synthesis lookups in a subprocess with clean `sys.path` (no `src/` or `third_party/`).

4. **Differential Oracle & Fixture Parity**:
   - Updated `tools/differential_lt.py` with `synthesize_queries()` and `--generate-synthesizer-fixtures` CLI command.
   - Generated and committed `tests/fixtures/oracle_russian_synthesizer_sample.json` directly from Java LanguageTool 6.8 standalone oracle (build `lt_6.8_source_build_jdk17_stefan`).
   - `test_oracle_synthesizer_fixture_parity` asserts 100% exact parity across all 34 oracle queries covering nouns, verbs, adjectives, irregulars, manual additions, manual removals, regex expansions, and Roman numerals.

---

## 2. Key Files Added and Modified

### Added Implementation Files
- `src/pylat_ru/synthesis/__init__.py`: Synthesis package exports.
- `src/pylat_ru/synthesis/roman.py`: Roman numeral conversion matching `Roman.sor`.
- `src/pylat_ru/synthesis/manual.py`: `ManualSynthesizer` overlay parser.
- `src/pylat_ru/synthesis/synthesizer.py`: `Synthesizer`, `BaseSynthesizer`, and `RussianSynthesizer` implementations.
- `src/pylat_ru/resources/ru/russian_synth.dict`: Pinned binary Morfologik FSA synthesis dictionary.
- `src/pylat_ru/resources/ru/russian_synth.info`: Synthesis dictionary metadata.
- `src/pylat_ru/resources/ru/tags_russian.txt`: Canonical Russian POS tag list.

### Modified Files
- `src/pylat_ru/__init__.py`: Exported `RussianSynthesizer`, `Synthesizer`, `BaseSynthesizer`, `ManualSynthesizer`.
- `tools/differential_lt.py`: Added `synthesize_queries()`, `SYNTHESIS_TEST_QUERIES`, `generate_synthesizer_fixtures()`, and `--generate-synthesizer-fixtures` flag.
- `compat/compatibility.json`: Updated milestone to `0006_russian_synthesizer`, overall state to `SYNTHESIZER_LAYER_ESTABLISHED`, added `russian_synthesizer` section, set `RussianSynthesizer: "SUPPORTED"`.

### Added Test Files & Fixtures
- `tasks/0006_russian_synthesizer.md`: Numbered task specification.
- `tests/upstream/test_russian_synthesizer.py`: Direct port of upstream `RussianSynthesizerTest.java`.
- `tests/test_manual_synthesizer.py`: Unit tests for `ManualSynthesizer`.
- `tests/test_synthesizer_subsystem.py`: Comprehensive synthesizer tests.
- `tests/upstream/test_russian_synthesizer_oracle_parity.py`: Exact parity against committed oracle fixture.
- `tests/unit/test_russian_synthesizer_resources.py`: Resource hash parity and real wheel distribution installation test.
- `tests/fixtures/oracle_russian_synthesizer_sample.json`: Committed Java LanguageTool 6.8 synthesis oracle fixture.

---

## 3. Test & Verification Results

Full repository test suite execution:
```bash
pytest -v
```
Output:
```text
============================ 202 passed in 21.02s =============================
```

All 202 tests passed with 0 failures, 0 skipped, and zero regressions.

---

## 4. Known Limitations & Scope Boundaries

- Number spelling for Russian (`_spell_number_` without Roman) returns the input number string unchanged because Russian has no upstream `.sor` file in LanguageTool (matches Java LT `RussianSynthesizer` behavior).
- Higher-level rule engine integration (`AdvancedSynthesizerFilter`, `match` elements with synthesis attributes) is scheduled for subsequent tasks (Task 0007 / Task 0008 / Task 0010).
- Production runtime has zero Java/JRE and zero external NLP dependencies.
