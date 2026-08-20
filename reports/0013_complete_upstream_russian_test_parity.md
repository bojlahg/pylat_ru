# Task 0013 — Complete Pinned Russian Upstream Test Parity

## 1. Identity

```text
baseline SHA (Task 0012 accepted):
770c93496cc0e7646542d2ca0f618b774b650823

pinned LanguageTool:
https://github.com/languagetool-org/languagetool.git
tag    v6.8
commit e807fcde6a6506191e1470744d2345da28c26be6

trusted Java oracle build:
lt_6.8_source_build_jdk17_stefan
jar sha256 b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc
```

Production execution remains 100% Python-native: no Java/JRE, no LanguageTool
server, no Java subprocess, no localhost oracle, no runtime download, no network.
The Java oracle and the whole upstream-test tooling are development-only.

---

## 2. What this task established

Task 0012 left `upstream_tests.status = PARTIALLY_PORTED` with
`remaining_upstream_test_files_not_ported = 11`.  Task 0013 replaces file-level
prose with a mechanically derived, method- and scenario-level inventory:

```text
compat/upstream_test_inventory_0013.json     machine-readable source of truth
tools/java_test_parser.py                    fail-closed Java-lite extractor
tools/inventory_upstream_tests_0013.py       inventory generator + explicit mapping
tests/unit/test_upstream_test_inventory_0013.py   independent validation
```

The generator is fail-closed twice over: the extractor aborts on any depth-0
invocation it cannot classify, and the inventory build aborts on any executable
contract without a mapping entry and on any mapping entry that no longer
resolves to a pinned method.  `tests/unit/test_upstream_test_inventory_0013.py`
re-derives the file list, the SHA-256 of every source, and the locally declared
`@Test` method names with an **independent** regex scan, then asserts that
regenerating the inventory reproduces the committed file byte for byte.

---

## 3. Extraction methodology and counting rule

`tools/java_test_parser.py` is not a full Java parser.  It blanks comments,
blanks string/char literal *contents* for structural scanning, and only treats
declarations at class-body depth 1 as methods of the class.

Counting rule (Task 0013 §8), recorded in the inventory under `counting_rule`:

| Construct | Units |
|---|---|
| JUnit/Hamcrest assertion call at parenthesis depth 0 | 1 assertion unit |
| `throw new X(...)` fail-closed guard | 1 assertion unit |
| call to a method of the same class or a vendored superclass (incl. `new Helper(...).method(...)`) | 1 scenario unit, target inventoried |
| `for (T x : VECTOR)` over a literal-collection field | `len(unique elements) × units inside the loop` |
| invocation nested inside another invocation's arguments | 0 (it is an argument) |
| allow-listed construction / accessor / plumbing call | 0 |
| commented-out code | 0 |
| anything else at depth 0 | **extraction aborts** |

The only vector loops in the pinned Russian tree are
`RussianVerbConjugationRuleTest.wrongSentences` (19 unique `ImmutableSet`
elements) and `rightSentences` (22), giving 41 scenario units — the same 41 the
Task-0011 report recorded by hand.

---

## 4. Pinned Russian-module inventory

The pinned tree contains exactly the 18 Russian-module test files named in the
task.  No omitted executable file was found; the file list in the inventory is
re-derived from the vendored tree on every test run.

Two **discrepancies in the previous accounting** were found and corrected:

1. `compat/upstream_test_inventory.json` counted every no-argument
   `public void` method, so JUnit `@Before setUp` fixtures were listed as test
   methods for `RussianCompoundRuleTest` and `RussianDashRuleTest`, and missed
   `public final void` declarations, so `RussianSynthesizerTest#testSynthesizeString`
   and `RussianSRXSentenceTokenizerTest#testTokenize` were recorded as *zero*
   test methods.  `tools/extract_upstream_tests.py` was fixed, the inventory
   regenerated (schema `1.0.1`, `superseded_by` the 0013 inventory), and
   `tests/unit/test_test_extraction.py` now locks the corrected composition.
2. `RussianConcurrencyTest` declares no `@Test` method at all; its executable
   behaviour is the inherited `AbstractLanguageConcurrencyTest#testSpellCheckerFailure`,
   which carries `@Ignore("too slow to run every time")` and therefore never
   executes at the pin.  This is recorded explicitly rather than being counted
   as a ported file.

### 4.1 Per-file coverage

| File | Executable methods | Scenario units | Status |
|---|---:|---:|---|
| DateCheckFilterTest | 2 | 9 | DIRECT_PYTHON_PARITY ×2 |
| LanguageSpecificSpellcheckerTest | 1 | 1 | DIRECT_PYTHON_PARITY |
| MorfologikRussianSpellerRuleTest | 1 | 7 | ALREADY_COVERED_EQUIVALENTLY |
| MorfologikRussianYOSpellerRuleTest | 1 | 6 | ALREADY_COVERED_EQUIVALENTLY |
| RussianCompoundRuleTest | 1 | 19 | ALREADY_COVERED_EQUIVALENTLY |
| RussianConcurrencyTest | 1 (inherited, `@Ignore`d upstream) | 1 | DIRECT_PYTHON_PARITY |
| RussianDashRuleTest | 1 | 5 | DIRECT_PYTHON_PARITY |
| RussianPatternRuleTest | 3 (1 declared + 2 inherited) | 8 | DIRECT_PYTHON_PARITY ×2, NOT_APPLICABLE_WITH_PROOF ×1 |
| RussianSRXSentenceTokenizerTest | 1 | 9 | ALREADY_COVERED_EQUIVALENTLY |
| RussianSimpleReplaceRuleTest | 1 | 5 | ALREADY_COVERED_EQUIVALENTLY |
| RussianSpecificCaseRuleTest | 1 | 9 | DIRECT_PYTHON_PARITY |
| RussianSynthesizerTest | 1 | 3 | ALREADY_COVERED_EQUIVALENTLY |
| RussianTaggerTest | 2 | 5 | DIRECT_PYTHON_PARITY ×2 |
| RussianTest | 1 | 2 | DIRECT_PYTHON_PARITY |
| RussianUnpairedBracketsRuleTest | 1 | 5 | DIRECT_PYTHON_PARITY |
| RussianVerbConjugationRuleTest | 1 | 41 | DIRECT_PYTHON_PARITY |
| RussianWordCoherencyRuleTest | 3 | 8 | ALREADY_COVERED_EQUIVALENTLY ×3 |
| RussianWordRepeatRuleTest | 1 | 2 | ALREADY_COVERED_EQUIVALENTLY |
| **Total** | **24** | **145** | |

### 4.2 Full contract closure

File-level and method-level accounting alone is not enough for the three
Russian tests that delegate into core base classes (`RussianTest`,
`RussianPatternRuleTest`, `LanguageSpecificSpellcheckerTest`).  The generator
follows every delegation transitively through the vendored base classes and
inventories each reached contract:

```text
contract closure entries            91
scenario units (closure)           261
assertion units (closure)          150

DIRECT_PYTHON_PARITY                44
ALREADY_COVERED_EQUIVALENTLY        18
NOT_EXECUTABLE_HELPER               23   (zero-unit plumbing / warning-only, derived)
NOT_APPLICABLE_WITH_PROOF            5
LANGUAGE_MODEL_DEFERRED              1
BLOCKED                              0
UNMAPPED                             0
UNKNOWN                              0
```

`NOT_APPLICABLE_WITH_PROOF` entries, each with an exact pinned-source reason:

| Contract | Reason |
|---|---|
| `PatternRuleTest#testSupportsLanguage/0` | builds `FakeLanguage("yy"/"zz")` only; Russian is never involved |
| `PatternRuleTest#createToolForTesting/1` | guarded by `CHECK_WITH_SENTENCE_SPLITTING = false` |
| `WordListValidatorTest#testWordListValidity/1` | opens with `if (lang.getShortCode().equals("ru")) { return; }` |
| `WordListValidatorTest#validateWords/2` | unreachable for Russian for the same reason |
| `LanguageSpecificTest#failTest/4` | failure-message formatter, only reached after a failure |

`LANGUAGE_MODEL_DEFERRED` is used exactly once, for
`LanguageSpecificTest#testConfusionSetLoading/0`, whose loader only runs when
`getRelevantLanguageModelRules()` is non-empty — for Russian that list is
exactly `RussianConfusionProbabilityRule`.

---

## 5. Vendored upstream additions

Nine pinned core test-support sources were vendored so the extractor and the
tests bind to bytes rather than to prose:

```text
languagetool-core/src/test/java/org/languagetool/TestTools.java
languagetool-core/src/test/java/org/languagetool/LanguageSpecificTest.java
languagetool-core/src/test/java/org/languagetool/language/AbstractLanguageConcurrencyTest.java
languagetool-core/src/test/java/org/languagetool/rules/AbstractCompoundRuleTest.java
languagetool-core/src/test/java/org/languagetool/rules/WordListValidatorTest.java
languagetool-core/src/test/java/org/languagetool/rules/spelling/SpellcheckerTest.java
languagetool-core/src/test/java/org/languagetool/rules/patterns/AbstractPatternRuleTest.java
languagetool-core/src/test/java/org/languagetool/rules/patterns/RuleIdValidator.java
languagetool-core/src/test/java/org/languagetool/tagging/disambiguation/rules/DisambiguationRuleTest.java
```

`third_party/languagetool/UPSTREAM.json`, `license_inventory.json` and
`LICENSES.md` were updated: **164** vendored files, **164** `VERIFIED_LGPL`,
**0** `BLOCKED_LICENSE_REVIEW`.

---

## 6. Generic/core evidence reconciliation (§25)

13 core test sources are reconciled in the inventory under
`generic_core_evidence_sources`, with source hash, size, class, `@Test` method
list, the Russian behaviour that depends on them, and the mapping.

Seven of them were claimed per-rule as Russian evidence in
`compat/russian_java_rules_inventory.json`.  All seven execute against
`TestTools.getDemoLanguage()` or `new FakeLanguage()`, so their literal
expectations are Demo-language outcomes, not a Russian contract.  Every one of
their pinned scenario inputs was therefore replayed through the trusted Java
oracle **with the Russian language** and is asserted field for field:

```text
tests/fixtures/oracle_upstream_tests_0013.json     146 cases
tools/generate_upstream_tests_fixtures_0013.py     generator (dev-only)
tests/upstream/test_upstream_tests_0013_oracle_parity.py

CommaWhitespaceRuleTest              45
MultipleWhitespaceRuleTest           17
SentenceWhitespaceRuleTest            7
UppercaseSentenceStartRuleTest       23
LongSentenceRuleTest                 24   (pinned maxWords 40 and 6)
LongParagraphRuleTest                 8   (pinned maxWords 6)
PunctuationMarkAtParagraphEnd2Test   22
```

The remaining six sources are:

* `PatternRuleLoaderTest`, `PatternRuleMatcherTest`, `RuleFilterEvaluatorTest`,
  `UnifierTest` — already translated by Tasks 0007–0010
  (`ALREADY_COVERED_EQUIVALENTLY`);
* `PatternRuleTest` — decomposed into its eleven Russian sub-contracts by this
  task (`DIRECT_PYTHON_PARITY`);
* `GenericUnpairedBracketsRuleTest` — vendored but never claimed as Russian
  evidence; its `setUpRule` builds `new GenericUnpairedBracketsRule(messages,
  Arrays.asList("»"), Arrays.asList("«"))` on `new FakeLanguage()`, a symbol set
  `RussianUnpairedBracketsRule` does not use (`NOT_APPLICABLE_WITH_PROOF`).

---

## 7. Compatibility bugs the faithful tests exposed, and the fixes

Three real production defects were found by executing the upstream contracts
faithfully.  All three are fixed in production code, not papered over.

### 7.1 Shared unifier state across threads (`src/pylat_ru/grammar/matcher.py`)

The concurrency port failed immediately with `IndexError: list index out of
range` inside `Unifier._check_next`.  Upstream builds a fresh
`PatternRuleMatcher` — and therefore a fresh `Unifier` — for every rule match
attempt; `pylat_ru` caches compiled rule variants and created the unifier once
per variant, so two threads shared per-attempt state.

Fix: the unifier is now created lazily **per thread**, and a whole match attempt
over one sentence is serialised per variant by an `RLock`, because the compiled
tokens also carry the dynamic `<match>` reference state that upstream keeps in a
per-attempt `PatternTokenMatcher`.  Exactly one pinned Russian antipattern uses a
token-level `<match>` reference (`Multiple_missing_commas_VB[1]`), and its
incorrect example is part of the shared-instance concurrency corpus.

### 7.2 Whole-text instead of per-sentence tokenization (`src/pylat_ru/native_rules.py`)

`NativeRuleContext.token_spans` tokenised the whole text at once, while upstream
tokenises every `AnalyzedSentence` from its own text.  The two differ whenever
the `RussianWordTokenizer` placeholder pass spans a sentence boundary: for
`"I live in .Los Angeles"` the whole-text pass yields the single token `.Los`,
while upstream splits the text into `"I live in ."` + `"Los Angeles"` and yields
`.` on its own — a match Java reports and `pylat_ru` missed.

Fix: the context now carries `sentence_token_spans` (per sentence, absolute
offsets) and `token_spans` is their concatenation.

### 7.3 `CommaWhitespaceRule` divergences (`src/pylat_ru/native_rules.py`)

The Task-0011 oracle corpus never reached several branches.  Compared against
the pinned `CommaWhitespaceRule.java`:

| Divergence | Pinned behaviour |
|---|---|
| office field codes ``/`` treated as ordinary text | `isWhitespaceToken` counts them as whitespace, and `prevWhite` excludes them |
| `FILE_EXTENSION` matched case-insensitively | pinned regex is `([a-z]{3,4}\|[A-Z]{3,4}\|ai\|mp[34]\|MP[34])(-.+)?` — all-lower or all-upper, never mixed, so `.Los` is *not* a file extension |
| a `pp == "."` short-circuit that upstream does not have | upstream only suppresses on `isDigitOrDot(next)` or a `./cmd` next-token pair |
| missing `marked.equals(suggestionText)` skip | upstream skips a match whose marked text already equals its single suggestion |
| rule looped over the whole text | upstream is `Rule.match(AnalyzedSentence)` — state is rebuilt per sentence and starts on the empty `SENT_START` token |
| soft-hyphen-only token not whitespace | `AnalyzedTokenReadings.isWhitespace` is computed from the token after upstream's soft-hyphen cleanup, so `"­"` is whitespace while `getToken()` still returns it |

`StringTools.isWhitespace`, `String.trim()` and `isFieldCode` are now ported
explicitly, and the whole rule is a direct port of the pinned loop.  All 45
`CommaWhitespaceRuleTest` scenarios now match the Java oracle under Russian, and
every Task-0011/0012 fixture still passes unchanged.

### 7.4 Rule example pairs added to the native rules

`LanguageSpecificTest#testJavaRules` asserts that every non-pattern rule's
incorrect example produces exactly one match and every correct example none.
The native rules carried no examples, so `NativeRule` now exposes
`incorrect_examples` / `correct_examples` holding the pinned `Example.wrong()` /
`Example.fixed()` literals for the 12 rules that declare them
(2 from `Russian.java`, 10 from the Russian rule classes).  All 24 example
checks pass.

No stored Task-0011 or Task-0012 oracle fixture was regenerated or changed.

---

## 8. New Python test modules

```text
tests/upstream/test_upstream_russian_rule_tests_0013.py        55 tests
tests/upstream/test_upstream_pattern_rule_contract_0013.py     14 tests
tests/upstream/test_upstream_language_contract_0013.py          9 tests
tests/upstream/test_upstream_tests_0013_oracle_parity.py      148 tests
tests/unit/test_upstream_test_inventory_0013.py                12 tests
tests/unit/test_production_dependency_audit_0013.py             4 tests
```

`tests/upstream/test_java_rules_0012_upstream_tests.py` was strengthened: the
compound-rule scenarios now assert the exact suggestion list and order that
`AbstractCompoundRuleTest#check` asserts, instead of mere membership.

Notable contracts newly executed:

* `RussianTaggerTest#testTagger` — exact `TestTools.myAssert` reading strings
  (sorted `token/[lemma]POS`, `null` rendered as Java renders it), not a
  semantic subset check;
* `RussianTest#testLanguage` — the demo text yields exactly
  `DOUBLE_PUNCTUATION, UPPERCASE_SENTENCE_START, MORFOLOGIK_RULE_RU_RU,
  DATE_WEEKDAY1`, in that order;
* `PatternRuleTest` sub-contracts — rule-id shape and uniqueness, category-id
  shape, `<unify-ignore>` placement, synthesis back-reference arity, message
  quality, every rule having an incorrect example with marker markup, and that
  applying any suggestion to a bad example never re-triggers the rule
  (953 suggestion re-checks);
* `LanguageSpecificTest#testCoherencyBaseformIsOtherForm` — 337 synthesised
  forms of the 34 `coherency.txt` keys, asserted both in the faithful (vacuous,
  because upstream enables the non-existent `EN_WORD_COHERENCY`) and in the
  strengthened `RU_WORD_COHERENCY` reading.

---

## 9. Concurrency

`AbstractLanguageConcurrencyTest#testSpellCheckerFailure` is `@Ignore`d
upstream, so it contributes no executed assertion at the pin.  The Python port
executes on every run and is stronger in sharing model, weaker in stress level:

```text
upstream (never executed):  availableProcessors()*10 threads x 100 runs, fresh instance per run
port (always executed):     12 threads x 3 runs, fresh instance per run
                          + 12 threads x 3 runs x 6 texts on ONE shared instance
```

The reduction is documented because a Python pipeline construction costs ~0.3 s,
so the upstream stress level would take roughly 40 minutes per run.  The port
adds what upstream does not test: a shared-instance model, singleton identity
before/after (`RussianTagger`, `RussianHybridDisambiguator`,
`RussianSynthesizer`, `RussianGrammarEngine`), byte-identical result
fingerprints against a sequential baseline, and unchanged sequential results
after the concurrent load.  The corpus deliberately exercises feature
unification and the one antipattern with a token-level `<match>` reference.

```text
concurrency: PASS
state isolation: PASS
```

---

## 10. Preserved evidence

```text
Russian XML grammar source rules      892 / 892 runnable, 0 deferred
Russian XML embedded examples        2446 / 2446 runnable, 0 deferred
compiled physical variants            907 / 907 runnable

Task 0011 oracle                      137 / 137 cases green (126 single-rule + 11 combined)
Task 0012 oracle                      151 / 151 cases green (59 spelling + 67 rules + 10 filter + 15 combined)
Task 0013 oracle                      146 / 146 cases green
oracle semantic signatures            unique, derived from query semantics only
oracle manifest                       binding added for the 0013 fixture

ordinary relevant Java rules           23 / 23
generic relevant Java rules            10 / 10
Russian-specific Java rules            13 / 13
Russian XML filters                     7 / 7
language-model rules                    0 / 1  (RussianConfusionProbabilityRule = LANGUAGE_MODEL_DEFERRED)
```

Tagger-dictionary audit (`tools/audit_tagger_dictionary_0013.py`, recorded in
the inventory and asserted by the inventory test):

```text
entries                 7,176,385
entries without a tag           0
```

---

## 11. Wheel isolation and production dependency audit

```text
wheel isolation (tests/unit/test_real_wheel_grammar.py)          PASS
production dependency audit (tests/unit/test_production_dependency_audit_0013.py)  PASS
```

The audit asserts that no module under `src/pylat_ru/` imports `pytest`,
`tools`, `unittest`, a Java bridge, `subprocess`, `socket` or an HTTP client;
that no production source references the vendored Java *test* tree, the oracle
jar, the oracle manifest, `.oracle_cache`, a `java -cp` invocation or the
upstream-test inventory; that the Task-0013 tooling lives only under `tools/`,
`tests/` and `compat/`; and that the built wheel ships no `.java`, `.jar`,
`third_party/`, `tools/` or `oracle_*` entry while still shipping
`grammar.xml`.

Two resource loaders (`disambiguation/multiwords.py`, `disambiguation/xml_loader.py`)
keep a documented last-resort development fallback to the vendored upstream
*main* resource directory.  It is never a runtime dependency — the wheel
isolation test executes the full pipeline from an installed wheel with the
repository removed from `sys.path` — and it does not touch the Java test tree,
so it is explicitly out of scope of the §36 prohibition.

---

## 12. Upstream Java test-module execution (§38)

Not performed.  `mvn` is not available in this environment and the trusted
oracle build is a distributed jar, not a pinned source checkout, so the pinned
`languagetool-language-modules/ru` Maven/JUnit module could not be executed
here.  Rather than invent a passing result, this is recorded as a limitation.

The repository already carries the infrastructure that could run it — the
manual `Oracle Conformance` workflow (`.github/workflows/oracle-conformance.yml`)
fetches the exact pinned commit, installs Maven 3.9.12 and JDK 17 and builds the
standalone oracle with `mvn clean package -DskipTests`.  Running the upstream
Russian module's own JUnit suite there is a `workflow_dispatch` operation that
was not triggered as part of this task.

The Java-side evidence that *was* produced is stronger for the purpose at hand:
every pinned scenario input of the seven core evidence sources, and every
Task-0011/0012 oracle query, was executed by the trusted pinned build with the
Russian language, and `pylat_ru` reproduces those results field for field.

---

## 13. Files added / changed

Added:

```text
compat/upstream_test_inventory_0013.json
reports/0013_complete_upstream_russian_test_parity.md
tests/fixtures/oracle_upstream_tests_0013.json
tests/unit/test_production_dependency_audit_0013.py
tests/unit/test_upstream_test_inventory_0013.py
tests/upstream/test_upstream_language_contract_0013.py
tests/upstream/test_upstream_pattern_rule_contract_0013.py
tests/upstream/test_upstream_russian_rule_tests_0013.py
tests/upstream/test_upstream_tests_0013_oracle_parity.py
tools/audit_tagger_dictionary_0013.py
tools/generate_upstream_tests_fixtures_0013.py
tools/inventory_upstream_tests_0013.py
tools/java_test_parser.py
third_party/languagetool/languagetool-core/src/test/java/... (9 vendored sources)
```

Changed:

```text
compat/compatibility.json                       upstream_tests block rewritten
compat/oracle_manifest.json                     0013 fixture binding
compat/upstream_test_inventory.json             corrected + superseded_by
src/pylat_ru/grammar/matcher.py                 thread-safe unifier / match state
src/pylat_ru/native_rules.py                    per-sentence spans, CommaWhitespaceRule port, rule examples
tests/unit/test_inventory.py                    164 vendored files
tests/unit/test_license_inventory.py            164 vendored files
tests/unit/test_test_extraction.py              corrected @Test composition
tests/upstream/test_java_rules_0012_upstream_tests.py   exact compound suggestions
third_party/languagetool/LICENSES.md            164 / 164
third_party/languagetool/UPSTREAM.json          164 vendored files
third_party/languagetool/license_inventory.json 164 items
tools/extract_upstream_tests.py                 @Test-only method scan
```

---

## 14. Known differences

```text
known_differences = []
```

No ordinary (non language-model) behavioural difference from pinned Russian
LanguageTool remains after this task.  The three divergences found (§7) were
fixed in production code rather than documented away.

Language-model deferral stays separate accounting:

```text
language-model rules: 0 / 1
RussianConfusionProbabilityRule = LANGUAGE_MODEL_DEFERRED
```

---

## 15. Test results

```text
python -m pytest -q
1002 passed / 0 failed / 0 errors / 0 skipped
```

No skip, no xfail, no conditional "Java unavailable" escape hatch in any
committed Python test.  Java-dependent fixture generation
(`tools/generate_upstream_tests_fixtures_0013.py`,
`tools/audit_tagger_dictionary_0013.py`) is an explicit dev command and never
runs during pytest.

### Exact-SHA GitHub Actions verification

Implementation commit:

```text
run ID:    32420629192
run URL:   https://github.com/bojlahg/pylat_ru/actions/runs/32420629192
event:     push
head_sha:  d055cbed9a725bd8482a6ba67e83c10cfff62440
conclusion: success

Python 3.10  conclusion: success
Python 3.12  conclusion: success
```

Both jobs ran every step successfully, including:

* `Verify exact checkout SHA`, which asserts `git rev-parse HEAD == GITHUB_SHA`;
* `Enforce zero failures, errors, and skips`, which parses the pytest JUnit
  report and fails the job unless `failures == 0 and errors == 0 and skipped == 0`.

The per-job *passed* count is not reproduced here: job logs and the uploaded
`pytest-results.xml` artifacts require repository credentials, and none are
available in this environment.  The machine-enforced part of the gate
(`0 failed / 0 errors / 0 skipped`) is green on both jobs; the local run on the
same commit reports `1002 passed`.

This report was added by a docs-only follow-up commit; its own exact-SHA
Actions run is recorded in the task handoff.
