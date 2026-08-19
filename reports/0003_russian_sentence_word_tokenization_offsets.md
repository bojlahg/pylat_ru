# Task Completion Report: Task 0003 — Russian Sentence + Word Tokenization with Exact Offsets

## 1. Executive Summary

Task 0003 has implemented the complete pure Python tokenization and span offset subsystem for LanguageTool's Russian pipeline:
- **`RussianSentenceTokenizer`**: Implements SRX 2.0 segmentation faithfully following `net.loomchild.segment 2.0.3` semantics for both `ru_two` (default) and `ru_one` (single-line paragraph) modes with 100% rule coverage, dynamic `<languagemap>` resolution, and exact `cut_matchers()`/`move_matchers()` control flow.
- **`RussianWordTokenizer`**: Implements LanguageTool's `RussianWordTokenizer` + `WordTokenizer` character-based splitting, Russian special sentinels (`б/у`, `б/н`, dot-space sentinels), `fullmatch` email checking matching Java `Matcher.matches()`, and inherited URL/email rejoining.
- **Exact Offsets & Span Representation**: `TextSpan`, `SentenceSpan`, and `TokenSpan` provide both Python code-point offsets and Java UTF-16 code unit offsets with $O(N)$ conversion and strict cumulative derivation (no substring searches).
- **Source Text Reconstruction Guarantee**: Every sentence and word tokenization operation strictly guarantees:
  $$\text{original\_text} == \sum \text{sentence.text} == \sum \text{token.text}$$
  with zero normalization, zero trimming, and exact character preservation.

All operations execute in native Python with **zero Java/JRE, zero daemon/server, and zero third-party NLP tokenizers** (no Natasha, pymorphy, or razdel).

---

## 2. Upstream Pin & Provenance Details

- **LanguageTool Target**: Tag `v6.8` (commit `e807fcde6a6506191e1470744d2345da28c26be6`).
- **`segment.srx` Hash (SHA-256)**: `746cd57ee0be4a962875d4d3855f29cb1c3ab5daca5641de25d599ea055d64da` (size: 213,633 bytes). Verified strictly prior to generating artifacts.
- **SRX Reference Engine**: `net.loomchild.segment` version `2.0.3`.
- **SRX Cascade Header**: `cascade="yes"`, `segmentsubflows="yes"`.

---

## 3. Review Findings & Implemented Fixes

1. **Strict SRX Metadata & Rule Field Type Validation**:
   - Runtime loader `load_russian_srx_rule_manager()` strictly checks exact expected metadata values (`EXPECTED_LT_COMMIT = "e807fcde6a6506191e1470744d2345da28c26be6"`, `EXPECTED_LT_TAG = "v6.8"`, `EXPECTED_LOOMCHILD_VERSION = "2.0.3"`, `EXPECTED_SOURCE_SHA256 = "746cd57ee0be4a962875d4d3855f29cb1c3ab5daca5641de25d599ea055d64da"`).
   - Strict type-checking on all rule fields (rejecting non-str `group`, non-int/bool `rule_index`, non-str `beforebreak`/`afterbreak`) without unsafe type coercion.
   - Added negative tests `test_strict_srx_metadata_exact_values` and `test_strict_srx_rule_field_types`.
2. **Verifiably Pinned Java Development Oracle**:
   - Implemented `validate_oracle()` in `tools/differential_lt.py` that checks Java availability, validates JAR presence, runs a Java probe verifying `org.languagetool.JLanguageTool.VERSION == "6.8"`, and computes JAR SHA-256.
   - Explicitly refuses fixture generation when oracle identity cannot be proven.
3. **Exact Loomchild 2.0.3 `SrxTextIterator` Alignment**:
   - Reimplemented `SRXSegmenter` with explicit `_init_matchers()`, `_get_min_matcher()`, `_is_exception()`, `_cut_matchers()`, and `_move_matchers()` methods matching `net.loomchild.segment.srx.SrxTextIterator` line-by-line.
   - Ensured `while matcher.break_pos <= end` loop semantics after every candidate boundary.
   - Added synthetic tests `test_synthetic_overlapping_and_same_boundary_rules` verifying multi-rule and overlapping boundary behavior.
4. **Byte-Exact Regeneration Pytest**:
   - Updated `test_srx_inventory_and_rules_complete_regeneration` to compare raw serialized string contents (`read_text()`) against committed `compat/russian_srx_inventory.json` and `src/pylat_ru/resources/russian_srx_rules.json`.
5. **Dynamic `<languagemap>` Resolution**:
   - Dynamic evaluation of all `<languagemap>` entries in XML document order against `languagepattern` matching target code (`ru_two`, `ru_one`), respecting `cascade="yes"`.
6. **Loomchild `segment 2.0.3` Lookbehind Finitization**:
   - Implemented `finitize(pattern, max_length=100)` with `remove_block_quotes()`.
7. **`RussianWordTokenizer.is_email()` Fullmatch Semantics**:
   - Fixed `is_email()` to use `fullmatch()` matching Java `Matcher.matches()`.
8. **Tightly Bounded `regex` Dependency**:
   - Updated `pyproject.toml` to `dependencies = ["regex>=2024.5.15,<=2026.7.19"]`. Documented Apache-2.0 / PSF license in `docs/russian_tokenization.md`.

---

## 4. SRX Inventory & Rule Mapping Breakdown

| Configuration | Dynamically Resolved Rule Groups | Total Rules | Break Rules (`break="yes"`) | Exception Rules (`break="no"`) |
| :--- | :--- | :--- | :--- | :--- |
| **`ru_two`** (default) | `GeneralImportant` $\to$ `ByTwoLineBreaks` $\to$ `Russian` $\to$ `Default` | **45** | **12** | **33** |
| **`ru_one`** (single-line) | `GeneralImportant` $\to$ `ByLineBreak` $\to$ `Russian` $\to$ `Default` | **44** | **11** | **33** |

### Group Counts:
- `GeneralImportant`: 7 rules (0 break, 7 exception) — URL/email protection, abbreviations (`A.aegypti`, `.NET`, `FRITZ!Box`).
- `ByTwoLineBreaks`: 2 rules (2 break, 0 exception) — `\r?\n\s*\r?\n[\t]*` and `[.!?]\u00A0\r?\n`.
- `ByLineBreak`: 1 rule (1 break, 0 exception) — `\r?\n`.
- `Russian`: 30 rules (4 break, 26 exception) — Russian abbreviations (`млрд.`, `г.`, `гг.`, `тыс.`, `руб.`, `шт.`, `т.к.`, initials, etc.).
- `Default`: 6 rules (6 break, 0 exception) — Generic fallback break rules.

**Effective Russian SRX Regex Compilation Status**: 100% (0 errors, 0 unsupported rules, 0 skipped rules).

---

## 5. Architecture & Key Modules

```text
src/pylat_ru/
  tokenization/
    __init__.py          # Public tokenization exports
    errors.py            # TokenizationError, SRXFormatError, SRXRuleCompilationError, etc.
    offsets.py           # TextSpan, SentenceSpan, TokenSpan, Utf16CodePointMapper
    srx.py               # SRXRule, SRXRuleManager, SRXRuleMatcher, SRXSegmenter, finitize
    sentence.py          # RussianSentenceTokenizer
    word.py              # RussianWordTokenizer, join_emails, join_urls
  resources/
    russian_srx_rules.json  # Embedded deterministic runtime SRX rules artifact
```

---

## 6. Verification & Test Suite Summary

The complete pytest suite passes with **93 passed tests in 2.35s**:

```text
tests/unit/test_differential_boundary.py ................ 4 passed
tests/unit/test_foundation.py ........................... 4 passed
tests/unit/test_inventory.py ............................ 12 passed
tests/unit/test_license_inventory.py .................... 2 passed
tests/unit/test_morfologik_dictionary.py ................ 4 passed
tests/unit/test_morfologik_fsa.py ....................... 8 passed
tests/unit/test_morfologik_metadata.py .................. 7 passed
tests/unit/test_morfologik_sequence_encoder.py .......... 4 passed
tests/unit/test_offsets.py .............................. 5 passed
tests/unit/test_russian_sentence_tokenizer.py ........... 4 passed
tests/unit/test_russian_tagset.py ....................... 5 passed
tests/unit/test_russian_word_tokenizer.py ............... 5 passed
tests/unit/test_srx_rules.py ............................ 11 passed
tests/unit/test_test_extraction.py ...................... 6 passed
tests/unit/test_upstream_diff.py ........................ 5 passed
tests/upstream/test_russian_dictionary_lookup.py ........ 2 passed
tests/upstream/test_russian_sentence_tokenizer_parity.py  2 passed
tests/upstream/test_russian_synth_dictionary_lookup.py .. 2 passed
tests/upstream/test_russian_word_tokenizer_parity.py .... 1 passed
======================================================== 93 passed in 2.35s
```

---

## 7. Performance Sanity Measurements

Measured on standard single-threaded Python runtime:
- **Sentence Tokenizer Initialization**: **0.13 ms** (rules compiled and cached).
- **Word Tokenizer Initialization**: **0.00 ms**.
- **Sentence Tokenization (37.6 KB / 400 sentences)**: **12.78 ms** (~2.81 MB/s throughput).
- **Word Tokenization (37.6 KB / 7,775 tokens)**: **3.70 ms** (~9.68 MB/s throughput).
- **Sentence Spans with UTF-16 Mapping (37.6 KB)**: **14.83 ms**.
- **Nested Word Spans (37.6 KB)**: **11.53 ms**.
- **UTF-16 Mapper Build (37.6 KB)**: **1.45 ms**.

---

## 8. Compatibility Status Update

Updated `compat/compatibility.json`:
- `task_milestone`: `"0003_russian_sentence_word_tokenization_offsets"`
- `overall_state`: `"TOKENIZATION_LAYER_ESTABLISHED"`
- `tokenization_and_offsets`:
  - `russian_srx_inventory`: `SUPPORTED`
  - `RussianSentenceTokenizer`: `SUPPORTED`
  - `RussianSentenceTokenizer_ru_two`: `SUPPORTED`
  - `RussianSentenceTokenizer_ru_one`: `SUPPORTED`
  - `RussianWordTokenizer`: `SUPPORTED`
  - `token_spans_codepoint_offsets`: `SUPPORTED`
  - `token_spans_utf16_offsets`: `SUPPORTED`
- Downstream layers (`RussianTagger`, `RussianDisambiguator`, `RussianSynthesizer`, `RussianChunker`, `XMLRuleEngine`) remain explicitly marked `NOT_YET_IMPLEMENTED`.
