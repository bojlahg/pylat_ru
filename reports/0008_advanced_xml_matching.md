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
  - Evaluated and verified 100% field-level parity across **870 test cases**:
    - `tests/fixtures/oracle_advanced_russian_rules.json` (750 real Russian rule cases across 229 advanced rules in `grammar.xml`).
    - `tests/fixtures/oracle_advanced_pattern_matching.json` (120 test cases covering `<and>`, `<or>`, `skip`, `min="0"`, `include_skipped`, regex replacement, POS synthesis, and multi-suggestion expansion).
  - All 870 cases match Java LanguageTool `v6.8` with **0 errors, 0 diffs, and 100% exact parity** across rule IDs, category metadata, descriptions, default states, match counts, UTF-16 spans, codepoint offsets, messages, and suggestions.

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

## 3. Implementation Details

### 3.1 Advanced Matcher (`pylat_ru.grammar.matcher`)
- Expanded `CompiledRuleVariant` to hold precomputed element lengths, skip constraints, and optional token tracking.
- `expand_rule_into_variants`: recursively expands `<or>` elements at the root of patterns into multiple variant branches.
- `_match_sequence_recursive`: backtracking sequence matcher supporting:
  - Exact token match against surface text, lemma, POS tag, and chunk tags.
  - Logical conjunction `<and>`: evaluating multiple predicate tokens on a single sentence token.
  - Logical disjunction `<or>`: trying each child branch.
  - Zero-or-one quantifier `min="0"`: exploring both the branch matching the token and the branch skipping the token (recording `token_positions[k] = 0`).
  - Skipping `skip="N"`: scanning forward up to `N` tokens while verifying that skipped tokens do not trigger pattern `<exception>` elements.
- `filter_subsumed_rule_matches`: removes duplicate matches and matches strictly contained within a larger match of the same rule.

### 3.2 Advanced Formatter (`pylat_ru.grammar.formatter`)
- `resolve_match_reference_forms`: computes actual token index in sentence via `rep_token_pos = sum(token_positions[:k+1]) - 1`.
- `include_skipped`: extracts whitespace and text between `actual_token_idx` and `actual_token_idx + skipped_count`.
- `regexp_match` / `regexp_replace`: converts Java regex replacement tokens (`$1`, `$2`) to Python regex replacement tokens (`\g<1>`, `\g<2>`).
- Synthesizer integration: performs regex replacement on POS tags (`postag_replace`), resolves target lemma from static `<match>lemma</match>` or dynamic token readings, and synthesizes all candidate inflected forms using `RussianSynthesizer`.
- Cartesian suggestion expansion: `_build_sug_block` and `format_suggestions_list` perform Cartesian product of multi-candidate match references inside `<suggestion>` blocks.

### 3.3 Grammar Engine (`pylat_ru.grammar.engine`)
- `check_rule` and `check_sentence`:
  - Executes all runnable core (0007) and advanced (0008) rules over `AnalyzedSentence` input.
  - Evaluates rule antipatterns before pattern execution.
  - Derives UTF-16 code unit and Unicode codepoint offsets for marker spans and full pattern matches.
  - Extracts suggestions from formatted message templates, applying initial-capitalization adjustment when errors occur at sentence start.

---

## 4. Tests and Verification

### 4.1 Pytest Test Suite Results
All test suites passed with 0 failures, 0 errors, and 0 skips:
- `tests/unit/test_advanced_grammar_matcher.py`: 7 unit tests verifying `<and>`, `<or>`, `skip`, `min="0"`, `include_skipped`, regex replacement, and POS tag synthesis.
- `tests/upstream/test_advanced_pattern_oracle_parity.py`: 2 tests verifying exact parity across 120 oracle cases for advanced XML pattern matching constructs.
- `tests/upstream/test_advanced_russian_rule_oracle_parity.py`: 2 tests verifying exact parity across 750 real Russian rule cases from `grammar.xml`.
- `tests/unit/test_real_wheel_grammar.py`: 1 test verifying real wheel build, wheel archive contents inspection, clean isolated installation, and end-to-end execution of both Core 0007 and Advanced 0008 rules in a clean subprocess without `src/` on `sys.path`.
- Full project test suite (Tasks 0001–0008): **All tests passed**.

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
