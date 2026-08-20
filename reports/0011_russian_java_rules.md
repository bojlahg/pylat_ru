# Task 0011 — Native Russian Java Rules: completion report

## Baseline and result

- Accepted baseline: `main` at `e1d6288996b7deff355016d8b5a70bbd9b4a3240`.
- LanguageTool target: `v6.8`, commit `e807fcde6a6506191e1470744d2345da28c26be6`.
- Implementation commit: `875dcd0c2aa78deecaf8fb9be574030cf559e4d5`.
- Production remains Python-native: no Java/JRE, LT server, Java subprocess, localhost oracle, or runtime download.
- State: 15 of 23 ordinary relevant Java rules implemented; eight remain explicitly Task-0012-deferred; the one language-model rule remains deferred.

## Exact rule accounting

Implemented generic rules (10/10):

```text
CommaWhitespaceRule
UppercaseSentenceStartRule
MultipleWhitespaceRule
SentenceWhitespaceRule
WhiteSpaceBeforeParagraphEnd
WhiteSpaceAtBeginOfParagraph
LongSentenceRule
LongParagraphRule
ParagraphRepeatBeginningRule
PunctuationMarkAtParagraphEnd2
```

Implemented Russian-specific rules (5/13):

```text
RussianFillerWordsRule
RussianUnpairedBracketsRule
RussianVerbConjugationRule
RussianDashRule
RussianSpecificCaseRule
```

Explicitly deferred to Task 0012 (8/23 ordinary relevant rules):

```text
MorfologikRussianSpellerRule
MorfologikRussianYOSpellerRule
RussianCompoundRule
RussianSimpleReplaceRule
RussianSimpleWordRepeatRule
RussianWordCoherencyRule
RussianWordRepeatRule
RussianWordRootRepeatRule
```

`RussianConfusionProbabilityRule` / `CONFUSION_RULE` is separately recorded as `LANGUAGE_MODEL_DEFERRED` (0/1). No spelling or language-model approximation was added.

The mechanically generated [registration inventory](../compat/russian_java_rules_inventory.json) records all 23 ordinary rules plus the LM rule with registration order/line, constructor arguments, IDs, categories, default state, source paths and SHA-256, resource dependencies, test sources, classification, and priority binding.

## Implementation

- `src/pylat_ru/native_rules.py` adds the narrowly scoped native rule/finding interface, full-text analysis context, 15 registered rules, default enablement, UTF-16/codepoint offsets, priority metadata, and deterministic ordering.
- `LanguageToolRU.check()` now runs the accepted tokenizer/tagger/disambiguator/chunker once, combines XML grammar results with Task-0011 native results, adjusts sentence offsets to full-text offsets, and returns deterministic public findings.
- `RussianVerbConjugationRule` uses the accepted LT-compatible Russian readings and preserves the pinned first-reading/POS conditions and exceptions.
- `RussianDashRule` uses the complete pinned `compounds.txt`; runtime matching stores the 26,464 canonical eligible entries and searches bounded windows around actual dash characters instead of expanding 105,852 variants or scanning every entry per text.
- `RussianSpecificCaseRule` uses the complete pinned `specific_case.txt`.
- Default-off rules are not run unless explicitly enabled: `WHITESPACE_PARAGRAPH`, `WHITESPACE_PARAGRAPH_BEGIN`, `TOO_LONG_PARAGRAPH`, `PARAGRAPH_REPEAT_BEGINNING_RULE`, `FILLER_WORDS_RU`, and `PUNCTUATION_PARAGRAPH_END2`.
- The wheel packages both required runtime resources; the production code uses `importlib.resources` only.

## Priority reconciliation

The pinned `Russian.java` contains priority keys which do not all equal the pinned rule IDs. The inventory records configured and effective priority separately instead of silently binding mismatched strings.

Effective Task-0011 bindings are:

```text
RU_DASH_RULE             12
TOO_LONG_PARAGRAPH      -15
```

Pinned orphan override keys directly affecting Task 0011 are:

```text
configured RUSSIAN_SPECIFIC_CASE = 9   vs registered RU_SPECIFIC_CASE
configured PUNCT_DPT_2 = -2            vs registered PUNCTUATION_PARAGRAPH_END2
```

Thus both registered rules inherit base priority `0` in pinned v6.8. Deferred rules expose four additional orphan keys (`MORFOLOGIC_RULE_RU_RU`, `MORFOLOGIC_RULE_RU_RU_YO`, `RUSSIAN_SIMPLE_REPLACE_RULE`, and `Word_root_repeat`) and two bound keys (`RU_COMPOUNDS`, plus the Task-0011 keys above). This is a proved upstream inconsistency, not an unexplained Python difference.

## Provenance and licensing

Twenty-two newly required generic base/source test files were copied byte-exactly from the pinned checkout into `third_party/languagetool`, taking the vendored/licensed inventory from 118 to 140 files. All 140 are `VERIFIED_LGPL`; `BLOCKED_LICENSE_REVIEW = 0`. Complete hashes are in `third_party/languagetool/UPSTREAM.json` and `third_party/languagetool/license_inventory.json`.

Key runtime resources:

| Resource | Bytes | SHA-256 |
| --- | ---: | --- |
| `compounds.txt` | 899,551 | `71b4217689cf83c07eb88b4f4b5c9c5e482171a053b48fa93e1cd1c14e8e720a` |
| `specific_case.txt` | 915 | `c35d08b0909b45acf242621961e2dbf0148792b70e4696be40248ad952c50966` |
| pinned `Russian.java` | 8,757 | `e42c7b3ee2aaf1e76deea246beb16d3f08df64fd65943495f1e3d0ad017cfaa6` |

Integrity tests prove that both packaged resource copies equal the pinned bytes.

## Upstream tests and oracle evidence

Inventoried generic test sources:

```text
CommaWhitespaceRuleTest.java
GenericUnpairedBracketsRuleTest.java
LongParagraphRuleTest.java
LongSentenceRuleTest.java
MultipleWhitespaceRuleTest.java
PunctuationMarkAtParagraphEnd2Test.java
SentenceWhitespaceRuleTest.java
UppercaseSentenceStartRuleTest.java
```

Inventoried Russian evidence includes `RussianDashRuleTest.java`, `RussianSpecificCaseRuleTest.java`, `RussianUnpairedBracketsRuleTest.java`, `RussianVerbConjugationRuleTest.java`, and registered examples in `Russian.java`. No pinned dedicated behavior test exists for `RussianFillerWordsRule`, `WhiteSpaceBeforeParagraphEnd`, `WhiteSpaceAtBeginOfParagraph`, or `ParagraphRepeatBeginningRule`; those surfaces receive controlled single-rule oracle cases.

Translated tests contain six focused Python functions, including 32 verb-conjugation good/bad assertions and direct dash/specific-case/bracket/default/priority/integration/offset assertions. The differential suite adds 45 parameterized full-field cases.

Oracle identity:

```text
build id: lt_6.8_source_build_jdk17_stefan
JAR SHA-256: b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc
pinned commit: e807fcde6a6506191e1470744d2345da28c26be6
```

Fixtures:

| Fixture | Cases | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| `tests/fixtures/oracle_java_rules_0011_synthetic.json` | 30 | 28,863 | `f02a6511541f6c7bd1248dc8dab5413e347bcdade9fdab198bbcf38d73b8a2ae` |
| `tests/fixtures/oracle_java_rules_0011_russian.json` | 15 | 14,062 | `6ba061a425a6a55a06284d476f486e32765f9f86cf1cf4f24265aaf27b5108ee` |

Every rule has positive and negative coverage. Coverage includes multi-finding inputs, Russian registered/upstream examples, thresholds, default-off rules, paragraph/sentence boundaries, resources, morphology, and non-BMP offsets. Fixtures were emitted by `tools/generate_java_rules_fixtures_0011.py` through the verified Java probe, with explicit LF bytes and semantic signatures.

Parity compares rule class/ID, category ID/name, finding count/order, Java UTF-16 spans, Python codepoint spans, source slices, message, short message, suggestions/order, and URL. Result: 45/45 exact cases, 100% full observable-field parity.

## Tests and wheel proof

Focused verification:

```text
python -m pytest -q \
  tests/upstream/test_java_rules_0011_oracle_parity.py \
  tests/unit/test_java_rules_0011.py \
  tests/unit/test_java_rules_0011_inventory.py \
  tests/unit/test_real_wheel_grammar.py \
  tests/unit/test_license_inventory.py \
  tests/unit/test_foundation.py

62 passed; failed=0; errors=0; skipped=0
```

The real-wheel test builds and installs the distribution into an isolated target, removes repository source paths, removes `JAVA_HOME`, and blocks sockets and subprocess calls. It executes a generic whitespace rule, an explicitly enabled paragraph rule, `RU_DASH_RULE`, and morphology-sensitive `RU_VERB_CONJUGATION`, as well as the accepted XML grammar/filter proofs. Result: passed.

Full regression (final pre-commit run):

```text
python -m pytest -q
416 passed; failed=0; errors=0; skipped=0
```

The accepted grammar counts remain unchanged: 778 runnable / 114 deferred source rules and 2,119 runnable / 327 deferred examples.

## Known differences and stopping point

- There are no unexplained oracle differences in the committed Task-0011 evidence.
- The priority ID mismatches above are preserved and explicitly reported as pinned upstream behavior.
- The eight Task-0012 rules and spelling-dependent suppression filter remain deferred and unapproximated.
- Task 0012 was not started.

## Git and CI verification

- Implementation commit: `875dcd0c2aa78deecaf8fb9be574030cf559e4d5`.
- Push target: `origin/main` without force or history rewrite.
- Exact remote implementation SHA: `875dcd0c2aa78deecaf8fb9be574030cf559e4d5` (verified with `git ls-remote origin refs/heads/main`).
- Exact-SHA CI run: [CI #32366269081](https://github.com/bojlahg/pylat_ru/actions/runs/32366269081).
- GitHub Actions Python 3.10: `success`, job `96416331112`, completed `2026-08-20T11:57:52Z`.
- GitHub Actions Python 3.12: `success`, job `96416331386`, completed `2026-08-20T11:57:34Z`.

`FINAL = COMPLETE`
