# Task 0011 — Native Russian Java Rules: review-fix report

## Baseline and status

- Current evidence-integrity review-fix baseline: `main` at `f133bc575f3f0084dd40b5ab093ddf0b5ba75685`.
- Overlap review-fix baseline: `86ad892fb1bc3c8c895cf5282ff20cd5a47494e7`.
- Earlier broad review-fix baseline: `ce6f145bdb52d1d462bab0d400515ca87aa04bbe`.
- Original Task-0011 implementation parent: `875dcd0c2aa78deecaf8fb9be574030cf559e4d5`.
- LanguageTool target: `v6.8`, commit `e807fcde6a6506191e1470744d2345da28c26be6`.
- Trusted oracle: `lt_6.8_source_build_jdk17_stefan`, JAR SHA-256 `b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc`.
- Earlier broad review-fix implementation commit: `95527bf3ff932fd1716fa9667e93e5fb1186713a`; the current overlap fix is delivered by the final commit containing this report.
- Production remains Python-native and does not invoke Java, an LT server, localhost services, or runtime downloads.

Rule accounting is unchanged and exact: 15/23 ordinary relevant Java rules are implemented (generic 10/10, Russian-specific 5/13); all eight Task-0012 rules remain deferred; the language-model rule remains deferred 0/1. `RussianSuppressMisspelledSuggestionsFilter` remains outside Task 0011. Task 0012 was not started.

## Review defects and fixes

### CI skip mismatch

The prior report incorrectly claimed `416 passed / 0 skipped`; GitHub run `32366269081` actually produced `415 passed / 1 skipped` in both jobs. The skipped live-Java generator test was removed from ordinary pytest semantics, not deleted: the live generator remains an explicit development command, while ordinary pytest now verifies the deterministic committed synthesizer fixture-to-generator-query contract without Java. Final local result is `513 passed / 0 failed / 0 errors / 0 skipped`.

### Semantic-signature duplicate hole

The semantic signature excludes testcase ID, stored signature, coverage bookkeeping, finding counts, and expected Java output. It includes execution mode, target rule/class, input text, explicit enablement/disablement, rule configuration, and any additional raw-rule oracle queries. Integrity tests assert `len(signatures) == len(set(signatures))` across all three fixtures. Result: 137/137 unique semantic signatures.

### Coverage metadata integrity

A corpus-wide audit found four labels that contradicted trusted Java results: `comma_ellipsis` falsely claimed `multi_finding`; `long_paragraph_above_final` falsely claimed a positive exact-span finding inside the pinned `maxWords + 5` guard band; `uppercase_enumeration` was labeled negative despite one Java match; and `filler_quote_adjacent` was labeled negative despite the pinned `minPercent=0` behavior producing one match. Generator definitions now describe all four honestly; the two misleading IDs were renamed to `long_paragraph_guard_band_final_without_separator` and `filler_zero_quote_adjacent`. The independent true positive `long_paragraph_final_no_separator` remains and has one Java finding.

Both generator and committed-fixture tests now fail closed when positive and negative coexist, a positive has no findings, a negative has findings, or `multi_finding`/`multiple_findings` has fewer than two findings. Regeneration proved that all 137 semantic-signature values are unchanged because only IDs/coverage bookkeeping changed, not oracle inputs/configuration or Java expected results.

### Inherited and configurable behavior

- `RussianUnpairedBracketsRule` now carries the observable inherited `GenericUnpairedBracketsRule` conditions used by Russian: nested/mismatched symbols, symmetric quotes, cross-sentence/paragraph state, smiley and URL exceptions, RU/Latin/numeric enumeration forms, exact symbol spans, and multiple-match order.
- `CommaWhitespaceRule` was corrected for leading commas and ellipsis behavior. Oracle coverage now includes both quote-spacing sides, exact suggestion order, parentheses, NBSP, decimal/thousands forms, extensions, control characters, and exact spans.
- `LongParagraphRule` now implements the pinned `maxWords + 5` guard and `paraHasLinebreaks` behavior for completed internal-linebreak/checklist sentences, including multiple and unterminated final paragraphs.
- `LongSentenceRule` now preserves the pinned segment state around `:`, `;`, and newline, including the inherited start-span behavior, quote/bracket/dash exclusion, quoted sentence-ending exclusion, punctuation counting, and exact spans.
- `RussianDashRule` now accepts only the four whole-compound trie variants generated upstream; mixed en/em or spacing variants are not independently canonicalized.
- Full-tool parity uses a development-only `JLanguageTool.check(text)` probe with exactly the eight Task-0012 rules disabled. The former global priority/length greedy selection was removed. A separate Python-native component now ports the pinned sequence `SameRuleGroupFilter` → identity Russian language-dependent filter → `CleanOverlappingFilter` → identity Russian post-overlap filter. It preserves stable position traversal, Russian/base/rule priority, picky penalty, punctuation-only preference, correction-all metadata, duplicate adjacent suggestions, longest-span tie, and last-match tie.
- Pinned `PICKY` probes prove that raw execution simultaneously emits `TOO_LONG_SENTENCE` plus an internal `COMMA_PARENTHESIS_WHITESPACE` or XML finding, while final cleanup retains the inner non-picky finding. Controlled oracle cases also cover equal-priority nested and same-length overlaps, adjacent non-overlap, and different Russian priorities. The comma case additionally proves `SameRuleGroupFilter`: direct rule execution emits both overlapping comma-spacing matches, while the pre-clean combined surface retains the first same-ID match.
- Premium/hidePremium infrastructure is proven non-applicable: the implemented Russian XML/Task-0011 surface contains no premium rule, and none of the implemented rule IDs is in pinned `ERRORS_THAT_CAN_BE_CORRECTED_ALL_AT_ONCE`; the flag is nevertheless modeled and the applicable branch is translated in focused tests.
- `RussianDashRule` explicitly clears inherited `Tag.picky` in pinned Russian source; its Python metadata now does likewise. This is required for `RU_DASH_RULE` priority 12 to beat the overlapping XML `Tire_and_spaces` match.
- A minimal public `rule_config` surface reaches native rules through `LanguageToolRU`/`RussianJavaRulesEngine`: LongSentence `maxWords` default 50, LongParagraph default 220, and FillerWords `minPercent` default 8 plus `excludeDirectSpeech`. Pinned Java proved that RuleOption ranges 5–100, 5–300, and 0–100 are UI metadata, not constructor validation: Java and Python both accept LongSentence 4/101, LongParagraph 4/301, and FillerWords -1/101 with identical behavior. The prior Python `ValueError` difference was removed.

All listed review areas required either implementation changes or combined-pipeline changes; no area is being claimed as `NO CODE CHANGE REQUIRED AFTER ORACLE CONFIRMATION` in aggregate.

## Oracle fixtures and integrity

Fixtures were regenerated only by `python -m tools.generate_java_rules_fixtures_0011` through the trusted pinned Java oracle and written as deterministic LF bytes.

| Fixture | Cases | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| `oracle_java_rules_0011_synthetic.json` | 114 | 141,499 | `8d6202657139a1538cfd7c6c0efcc1675e3a0a021a5f0e7e24f64f7ad0bb4a42` |
| `oracle_java_rules_0011_russian.json` | 12 | 11,396 | `b7d216d5a06b32f72b826647d75705adc31e465877f998c4a63663dde7ba6531` |
| `oracle_java_rules_0011_combined.json` | 11 | 40,398 | `edf539f4e1d4c30f72239c76e2df4a1f20555e427e48ec3ed4e85a1178fc4680` |

Single-rule parity is 126/126 and combined-pipeline parity is 11/11. Combined cases also bind the Java pre-overlap result and selected direct-rule raw queries. All surfaces compare ordered rule ID, category ID/name, UTF-16 and Python codepoint spans, source slice, message, short message, suggestions and order, and URL. IDs, build identity, counts, raw sizes/hashes, LF bytes, stored/recomputed signatures, and signature uniqueness are independently checked and bound by `compat/oracle_manifest.json`.

## Upstream test translation

- Upstream test files inventoried: 12.
- Upstream `@Test` methods inspected: 13.
- Direct upstream assertion scenarios represented in oracle fixtures: 27.
- `RussianVerbConjugationRuleTest` sentence assertions translated: 41/41.
- Distinct selected applicable upstream assertion scenarios translated/directly represented: 65/65 (three verb scenarios are also oracle-backed and counted once).
- Additional controlled oracle cases beyond those direct upstream scenarios: 99 single-rule cases plus 11 combined-pipeline cases.

The inspected surface includes `CommaWhitespaceRuleTest`, `GenericUnpairedBracketsRuleTest`, `RussianUnpairedBracketsRuleTest`, `LongParagraphRuleTest`, `LongSentenceRuleTest`, `RussianVerbConjugationRuleTest`, `RussianDashRuleTest`, `RussianSpecificCaseRuleTest`, `UppercaseSentenceStartRuleTest`, `MultipleWhitespaceRuleTest`, `SentenceWhitespaceRuleTest`, and `PunctuationMarkAtParagraphEnd2Test`. No pinned dedicated behavior test exists for `RussianFillerWordsRule`, `WhiteSpaceBeforeParagraphEnd`, `WhiteSpaceAtBeginOfParagraph`, or `ParagraphRepeatBeginningRule`; those use controlled oracle cases.

## Tests and wheel proof

Full pre-report regression:

```text
python -m pytest -q
513 passed in 87.08s
failed=0; errors=0; skipped=0
```

The required focused oracle/integrity/config/combined/filter set plus wheel isolation passed 153/153 with zero skips. The real-wheel proof was rerun in the full suite and passed. It builds and installs the wheel into an isolated directory, removes repository source paths and `JAVA_HOME`, and blocks sockets/subprocess use in production execution. It executes representative Task-0011 generic whitespace, explicit default-off paragraph whitespace, dash-resource, morphology-sensitive verb, XML grammar, and filter findings.

CI now verifies `git rev-parse HEAD == GITHUB_SHA` and parses the generated JUnit XML after pytest. Each matrix job prints and enforces `failures=0`, `errors=0`, and `skipped=0`; a green job can no longer hide a skip as run `32366269081` did.

Accepted XML grammar counts remain 778 runnable / 114 deferred source rules and 2,119 runnable / 327 deferred examples.

## Compatibility and known differences

Updated machine-readable files are `compat/compatibility.json`, `compat/oracle_manifest.json`, and `compat/russian_java_rules_inventory.json`. The inventory records the three UserConfig surfaces and preserves pinned priority-ID mismatches (`RUSSIAN_SPECIFIC_CASE` vs `RU_SPECIFIC_CASE`, `PUNCT_DPT_2` vs `PUNCTUATION_PARAGRAPH_END2`) as upstream facts.

Known Java-oracle differences: none in the committed Task-0011 surface. Russian pre/post language-dependent match filters are identity at the pin; premium hiding and the correction-all ID set do not apply to implemented Russian rules.

## Git and final CI

- The final SHA and exact-SHA Actions run for the commit containing code, fixtures, compatibility data, tests, and this report are recorded in the final task handoff after the commit and CI run exist.

`FINAL = SUBJECT TO EXACT-SHA CI FOR REPORT/GATE COMMIT`
