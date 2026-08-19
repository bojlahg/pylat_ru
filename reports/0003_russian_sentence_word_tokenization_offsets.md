# Task Completion Report: Task 0003 — Russian Sentence + Word Tokenization with Exact Offsets

## 1. Executive Summary

Task 0003 has implemented the complete pure Python tokenization and span offset subsystem for LanguageTool's Russian pipeline:
- **`RussianSentenceTokenizer`**: Implements SRX 2.0 segmentation following `net.loomchild.segment 2.0.3` semantics for both `ru_two` (default) and `ru_one` (single-line paragraph) modes with 100% rule coverage and dynamic `<languagemap>` resolution.
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

1. **Dynamic `<languagemap>` Resolution**:
   - Replaced hard-coded group lists with dynamic evaluation of all `<languagemap>` entries in XML document order against `languagepattern` matching target code (`ru_two`, `ru_one`), respecting `cascade="yes"`.
   - Added unit test `test_dynamic_languagemap_cascade_resolution` proving dynamic resolution on custom/synthetic mappings.
2. **Strict Source Hash Verification**:
   - Added SHA-256 check against `746cd57ee0be4a962875d4d3855f29cb1c3ab5daca5641de25d599ea055d64da` in `tools/russian_srx_inventory.py`. Added test `test_srx_source_hash_mismatch_raises_error`.
3. **Java `Matcher.find()` Advance Semantics**:
   - Fixed `SRXRuleMatcher.find()` to advance from `before_match.end()` after a non-empty match, and advance by 1 code point only after a zero-width match (`^`, `\b`).
   - Added `test_srx_rule_matcher_advancement_and_zero_width` verifying non-empty and zero-width pattern searches.
4. **Loomchild `segment 2.0.3` Lookbehind Finitization**:
   - Implemented `finitize(pattern, max_length=100)` with `remove_block_quotes()`:
     - `\Q...\E` $\to$ `\a\b\c...`
     - unescaped `*` $\to$ `{0,100}`
     - unescaped `+` $\to$ `{1,100}`
     - unescaped `{n,}` $\to$ `{n,100}`
   - Added `test_remove_block_quotes_and_finitize` testing Russian beforebreak exception patterns with unbounded quantifiers.
5. **Strict Runtime SRX Resource Validation**:
   - Added strict validation of top-level keys (`metadata`, `configurations`, `groups`), metadata fields (`languagetool_commit`, `languagetool_tag`, `loomchild_version`, `source_sha256`), rule objects (`group`, `rule_index`, `break`, `beforebreak`, `afterbreak`), and break values (`"yes"` or `"no"`). Raises `SRXFormatError` on any violation.
   - Added `test_strict_srx_runtime_resource_validation`.
6. **Development-Only Pinned-LT v6.8 Oracle Generator**:
   - Added `--generate-tokenization-fixtures` in `tools/differential_lt.py` which compiles and runs lightweight Java harnesses against `org.languagetool.language.Russian` in `LanguageTool-6.8/languagetool-commandline.jar`.
7. **Full-Content Regeneration Pytest**:
   - Added `test_srx_inventory_and_rules_complete_regeneration` asserting exact structural and byte equality of regenerated `compat/russian_srx_inventory.json` and `src/pylat_ru/resources/russian_srx_rules.json` against committed files.
8. **`RussianWordTokenizer.is_email()` Fullmatch Semantics**:
   - Fixed `is_email()` to use `fullmatch()` matching Java `Matcher.matches()`.
   - Added positive and negative regression tests in `test_url_and_email_detection_helpers`.
9. **Tightly Bounded `regex` Dependency**:
   - Updated `pyproject.toml` to `dependencies = ["regex>=2024.5.15,<=2026.7.19"]`. Documented Apache-2.0 / PSF license and Java-vs-Python regex semantics in `docs/russian_tokenization.md`.

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

The complete pytest suite passes with **91 passed tests in 2.61s**:

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
tests/unit/test_srx_rules.py ............................ 9 passed
tests/unit/test_test_extraction.py ...................... 6 passed
tests/unit/test_upstream_diff.py ........................ 5 passed
tests/upstream/test_russian_dictionary_lookup.py ........ 2 passed
tests/upstream/test_russian_sentence_tokenizer_parity.py  2 passed
tests/upstream/test_russian_synth_dictionary_lookup.py .. 2 passed
tests/upstream/test_russian_word_tokenizer_parity.py .... 1 passed
======================================================== 91 passed in 2.61s
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
