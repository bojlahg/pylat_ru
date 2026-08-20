# Task 0011 — Native Russian Java Rules: review-fix report

## Baseline and status

- Review-fix baseline: `main` at `ce6f145bdb52d1d462bab0d400515ca87aa04bbe`.
- Original Task-0011 implementation parent: `875dcd0c2aa78deecaf8fb9be574030cf559e4d5`.
- LanguageTool target: `v6.8`, commit `e807fcde6a6506191e1470744d2345da28c26be6`.
- Trusted oracle: `lt_6.8_source_build_jdk17_stefan`, JAR SHA-256 `b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc`.
- Review-fix implementation commit: `PENDING_REVIEW_FIX_COMMIT`.
- Production remains Python-native and does not invoke Java, an LT server, localhost services, or runtime downloads.

Rule accounting is unchanged and exact: 15/23 ordinary relevant Java rules are implemented (generic 10/10, Russian-specific 5/13); all eight Task-0012 rules remain deferred; the language-model rule remains deferred 0/1. `RussianSuppressMisspelledSuggestionsFilter` remains outside Task 0011. Task 0012 was not started.

## Review defects and fixes

### CI skip mismatch

The prior report incorrectly claimed `416 passed / 0 skipped`; GitHub run `32366269081` actually produced `415 passed / 1 skipped` in both jobs. The skipped live-Java generator test was removed from ordinary pytest semantics, not deleted: the live generator remains an explicit development command, while ordinary pytest now verifies the deterministic committed synthesizer fixture-to-generator-query contract without Java. Final local result is `498 passed / 0 failed / 0 errors / 0 skipped`.

### Semantic-signature duplicate hole

The semantic signature now excludes testcase ID, stored signature, coverage bookkeeping, finding counts, and expected Java output. It includes execution mode, target rule/class, input text, explicit enablement/disablement, and rule configuration. Integrity tests assert `len(signatures) == len(set(signatures))` across all three fixtures. The strengthened test found two real bookkeeping duplicates; both duplicate queries were removed without removing behavioral coverage. Result: 126/126 unique semantic signatures.

### Inherited and configurable behavior

- `RussianUnpairedBracketsRule` now carries the observable inherited `GenericUnpairedBracketsRule` conditions used by Russian: nested/mismatched symbols, symmetric quotes, cross-sentence/paragraph state, smiley and URL exceptions, RU/Latin/numeric enumeration forms, exact symbol spans, and multiple-match order.
- `CommaWhitespaceRule` was corrected for leading commas and ellipsis behavior. Oracle coverage now includes both quote-spacing sides, exact suggestion order, parentheses, NBSP, decimal/thousands forms, extensions, control characters, and exact spans.
- `LongParagraphRule` now implements the pinned `maxWords + 5` guard and `paraHasLinebreaks` behavior for completed internal-linebreak/checklist sentences, including multiple and unterminated final paragraphs.
- `LongSentenceRule` now preserves the pinned segment state around `:`, `;`, and newline, including the inherited start-span behavior, quote/bracket/dash exclusion, quoted sentence-ending exclusion, punctuation counting, and exact spans.
- `RussianDashRule` now accepts only the four whole-compound trie variants generated upstream; mixed en/em or spacing variants are not independently canonicalized.
- Full-tool parity now uses a development-only `JLanguageTool.check(text)` probe with exactly the eight Task-0012 rules disabled. The Python public pipeline applies the pinned overlap/priority cleanup separately from direct single-rule execution and matches ordered full observable fields.
- A minimal public `rule_config` surface reaches native rules through `LanguageToolRU`/`RussianJavaRulesEngine`: LongSentence `maxWords` default 50/range 5–100, LongParagraph default 220/range 5–300, and FillerWords `minPercent` default 8/range 0–100 plus `excludeDirectSpeech`. Boundary, custom percentage, zero-percent, and quote adjacency/spacing behavior are Java-oracle backed. The non-obvious pinned behavior at `minPercent=0` is preserved literally.

All listed review areas required either implementation changes or combined-pipeline changes; no area is being claimed as `NO CODE CHANGE REQUIRED AFTER ORACLE CONFIRMATION` in aggregate.

## Oracle fixtures and integrity

Fixtures were regenerated only by `python -m tools.generate_java_rules_fixtures_0011` through the trusted pinned Java oracle and written as deterministic LF bytes.

| Fixture | Cases | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| `oracle_java_rules_0011_synthetic.json` | 108 | 129,214 | `5a4767184df81babd476c1ad7f175d6b91a659be1d52c7ee1085d945cc57dcc7` |
| `oracle_java_rules_0011_russian.json` | 12 | 11,396 | `0b0224312f6b2dc273bce8716061f5e8c68d09e91b34329471ca8b8e3465886e` |
| `oracle_java_rules_0011_combined.json` | 6 | 11,591 | `ab7b95eb8207a775cf31bd040dc5477350b3f9c2dc3451ef768754785b84e1f4` |

Single-rule parity is 120/120 and combined-pipeline parity is 6/6. Both compare ordered rule ID, category ID/name, UTF-16 and Python codepoint spans, source slice, message, short message, suggestions and order, and URL. IDs, build identity, counts, raw sizes/hashes, LF bytes, stored/recomputed signatures, and signature uniqueness are independently checked and bound by `compat/oracle_manifest.json`.

## Upstream test translation

- Upstream test files inventoried: 12.
- Upstream `@Test` methods inspected: 13.
- Direct upstream assertion scenarios represented in oracle fixtures: 27.
- `RussianVerbConjugationRuleTest` sentence assertions translated: 41/41.
- Distinct selected applicable upstream assertion scenarios translated/directly represented: 65/65 (three verb scenarios are also oracle-backed and counted once).
- Additional controlled oracle cases beyond those direct upstream scenarios: 93 single-rule cases plus 6 combined-pipeline cases.

The inspected surface includes `CommaWhitespaceRuleTest`, `GenericUnpairedBracketsRuleTest`, `RussianUnpairedBracketsRuleTest`, `LongParagraphRuleTest`, `LongSentenceRuleTest`, `RussianVerbConjugationRuleTest`, `RussianDashRuleTest`, `RussianSpecificCaseRuleTest`, `UppercaseSentenceStartRuleTest`, `MultipleWhitespaceRuleTest`, `SentenceWhitespaceRuleTest`, and `PunctuationMarkAtParagraphEnd2Test`. No pinned dedicated behavior test exists for `RussianFillerWordsRule`, `WhiteSpaceBeforeParagraphEnd`, `WhiteSpaceAtBeginOfParagraph`, or `ParagraphRepeatBeginningRule`; those use controlled oracle cases.

## Tests and wheel proof

Full pre-report regression:

```text
python -m pytest -q
498 passed in 76.53s
failed=0; errors=0; skipped=0
```

The final focused oracle/integrity/config/combined/wheel set passed 138/138. The real-wheel proof was then rerun in the full suite and passed. It builds and installs the wheel into an isolated directory, removes repository source paths and `JAVA_HOME`, and blocks sockets/subprocess use in production execution. It executes representative Task-0011 generic whitespace, explicit default-off paragraph whitespace, dash-resource, morphology-sensitive verb, XML grammar, and filter findings.

Accepted XML grammar counts remain 778 runnable / 114 deferred source rules and 2,119 runnable / 327 deferred examples.

## Compatibility and known differences

Updated machine-readable files are `compat/compatibility.json`, `compat/oracle_manifest.json`, and `compat/russian_java_rules_inventory.json`. The inventory records the three UserConfig surfaces and preserves pinned priority-ID mismatches (`RUSSIAN_SPECIFIC_CASE` vs `RU_SPECIFIC_CASE`, `PUNCT_DPT_2` vs `PUNCTUATION_PARAGRAPH_END2`) as upstream facts.

Known unexplained Java-oracle differences: none in the committed Task-0011 fixtures.

## Git and final CI

- Review-fix implementation commit: `PENDING_REVIEW_FIX_COMMIT`.
- Final `main`: `PENDING_FINAL_SHA`.
- Exact-SHA Actions run: `PENDING_FINAL_CI`.
- Python 3.10: `PENDING_FINAL_CI`.
- Python 3.12: `PENDING_FINAL_CI`.

`FINAL = PENDING EXACT-SHA CI`
