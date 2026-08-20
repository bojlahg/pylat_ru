# Task 0011 — Native Russian Java Rules

## Status

**ACTIVE TASK SPECIFICATION**

Task 0010 is accepted as the baseline for this task.

Do not start Task 0012, Task 0013, or later work while implementing this task.

---

# 1. Goal

Implement the **native Python equivalents of the non-spelling Java rules enabled for Russian LanguageTool** at the pinned upstream revision:

```text
LanguageTool v6.8
commit e807fcde6a6506191e1470744d2345da28c26be6
```

Task 0011 extends the accepted Python-native Russian pipeline from:

```text
tokenization
→ tagging
→ disambiguation
→ chunking
→ XML grammar engine
→ unification
→ XML filters
→ XML findings
```

to:

```text
tokenization
→ tagging
→ disambiguation
→ chunking
→ XML grammar rules
→ native Java-rule equivalents
→ combined Russian rule findings
```

The task is **compatibility work**, not a redesign of LanguageTool rules and not a generic grammar-checking exercise.

Production execution must remain fully Python-native:

```text
NO Java/JRE
NO LanguageTool Server
NO Java subprocesses
NO localhost oracle calls
NO runtime LanguageTool downloads
```

Java LanguageTool may only be used as a **dev/test oracle**.

---

# 2. Baseline

Accepted Task-0010 branch baseline:

```text
branch: main
SHA:    e1d6288996b7deff355016d8b5a70bbd9b4a3240
```

Pinned upstream:

```text
repository: https://github.com/languagetool-org/languagetool.git
tag:        v6.8
commit:     e807fcde6a6506191e1470744d2345da28c26be6
```

Task-0010 accepted grammar state:

```text
grammar source rules total                      892
runnable source rules                           778
deferred source rules                           114
unknown source rules                              0

grammar examples total                         2446
runnable examples                              2119
deferred examples                               327
```

Task-0010 Java-rule accounting:

```text
relevant Java rules total                        23
  Russian-specific                               13
  generic                                        10

language-model rules                              1
all Java rules total                             24

implemented relevant Java rules                   0
```

Task 0011 must preserve all accepted behavior from Tasks 0001–0010.

---

# 3. Exact Task-0011 rule inventory

The pinned `Russian.java` inventory contains these 23 relevant non-language-model rules:

```text
CommaWhitespaceRule
UppercaseSentenceStartRule
MorfologikRussianSpellerRule
MultipleWhitespaceRule
SentenceWhitespaceRule
WhiteSpaceBeforeParagraphEnd
WhiteSpaceAtBeginOfParagraph
LongSentenceRule
LongParagraphRule
ParagraphRepeatBeginningRule
RussianFillerWordsRule
PunctuationMarkAtParagraphEnd2
MorfologikRussianYOSpellerRule
RussianUnpairedBracketsRule
RussianCompoundRule
RussianSimpleReplaceRule
RussianSimpleWordRepeatRule
RussianWordCoherencyRule
RussianWordRepeatRule
RussianWordRootRepeatRule
RussianVerbConjugationRule
RussianDashRule
RussianSpecificCaseRule
```

Task 0011 implements exactly the following **15 rules**.

## 3.1 Generic rules — implement all 10

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

## 3.2 Russian-specific rules — implement these 5

```text
RussianFillerWordsRule
RussianUnpairedBracketsRule
RussianVerbConjugationRule
RussianDashRule
RussianSpecificCaseRule
```

Expected Task-0011 accounting after successful completion:

```text
relevant Java rules total                        23
implemented in Task 0011                         15
remaining for Task 0012                           8

generic implemented                              10 / 10
Russian-specific implemented                      5 / 13
Russian-specific deferred to Task 0012             8 / 13
```

This 15/23 split is part of the task contract unless pinned-source reinspection proves that the accepted inventory itself is wrong. Any such discrepancy must be documented and proved from the pinned source before changing the accounting.

---

# 4. Explicit Task-0012 boundary

The following **8 rules must NOT be approximated or implemented in Task 0011**:

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

They belong to Task 0012:

```text
Spelling / compounds / replace / coherency / repetitions
```

Do not fake these rules using:

- tagger dictionary membership;
- a small Python word list;
- edit distance;
- regex-only substitutes for spelling;
- manually copied expected outputs;
- hard-coded fixture text;
- a reduced substitute dictionary;
- Java at production runtime.

Their status after Task 0011 must remain explicit, e.g.:

```text
DEFERRED_0012_SPELLING_COMPOUND_REPLACE_REPEAT
```

or an equally precise machine-readable state.

Task 0011 must not claim:

```text
all Russian Java rules implemented
```

because that statement would be false.

---

# 5. Language-model rule is NOT Task 0011

Pinned inventory also contains:

```text
RussianConfusionProbabilityRule
```

This is accounted separately as a language-model rule:

```text
language_model_rules_total = 1
```

It is not one of the 23 ordinary relevant Java rules and is not part of Task 0011.

Do not silently mark it implemented.

Do not pull in an unrelated neural/runtime dependency merely to make the metric green.

Preserve an explicit deferred compatibility status for it until a later task deliberately addresses that surface.

---

# 6. First step: reconstruct exact pinned registration semantics

Before implementing rule logic, inspect the pinned `Russian.java` and prove the exact Russian registration surface.

Create/update a deterministic inventory containing at least:

```text
rule class
source file
source SHA-256
Russian.java registration location/order
constructor arguments
rule ID
category ID/name
default enabled/disabled state
rule-specific configuration
priority override, if any
Task-0011 / Task-0012 / LM classification
upstream test sources
resource dependencies
```

The inventory must be generated or mechanically verifiable from the pinned source wherever practical.

Do not rely on class names alone.

For each Task-0011 rule, trace inherited behavior used by the pinned implementation. If a Russian rule subclasses or configures a generic LanguageTool base class, the Python implementation must reproduce the **observable pinned behavior**, not merely the few lines in the leaf class.

---

# 7. Priority overrides

Pinned Russian priority overrides include:

```text
RU_DASH_RULE                          12
RU_COMPOUNDS                         11
RUSSIAN_SIMPLE_REPLACE_RULE          10
RUSSIAN_SPECIFIC_CASE                 9
MORFOLOGIC_RULE_RU_RU_YO              2
MORFOLOGIC_RULE_RU_RU                 1
Word_root_repeat                      -1
PUNCT_DPT_2                           -2
TOO_LONG_PARAGRAPH                   -15
```

Task 0011 directly touches at least:

```text
RU_DASH_RULE              12
RUSSIAN_SPECIFIC_CASE      9
PUNCT_DPT_2               -2
TOO_LONG_PARAGRAPH       -15
```

Implement the rule-priority representation required for parity.

Do not hard-code priority only inside tests.

The combined Russian rule pipeline must expose deterministic ordering/conflict behavior consistent with the pinned Russian registration and priority semantics.

Task-0012 priority entries must remain represented but deferred until their rules are implemented.

---

# 8. Native rule interface

Introduce or extend a native rule abstraction only as much as required by the pinned Russian rule set.

A native rule must be able to receive the correct accepted pipeline representation and emit findings carrying the compatibility-visible fields required by the rule:

```text
rule_id
category_id
category_name, where represented
message
short_message
offset
length
replacements / suggestions
URL, when the pinned rule provides one
source
priority / ordering metadata where required
```

Do not build a speculative multilingual plugin system.

Do not force all rules into an abstraction that loses distinctions required by LanguageTool.

The implementation may use shared helpers for recurring behavior such as:

```text
whitespace scanning
sentence-start checks
paragraph boundaries
bracket pairing
token/POS traversal
finding construction
UTF-16/codepoint conversion
```

but shared helpers must preserve per-rule semantics.

---

# 9. Required rule behavior

For every Task-0011 rule, port the behavior of the pinned implementation, including applicable:

- exact rule ID;
- category;
- message;
- short message;
- suggestion list and order;
- offsets and lengths;
- multiple findings in one input;
- punctuation handling;
- whitespace type handling;
- sentence boundaries;
- paragraph boundaries;
- token/POS conditions;
- exclusions and exceptions;
- ignored characters;
- capitalization behavior;
- maximum-length thresholds;
- default enabled/disabled behavior;
- priority;
- URLs or metadata;
- behavior at start/end of text.

Do not reduce a rule to "find roughly the same problem".

Parity means the observable finding is compatible.

---

# 10. Generic rule requirements

## 10.1 `CommaWhitespaceRule`

Reproduce pinned behavior around comma spacing, including positive and negative cases, multiple commas, punctuation adjacency, line/paragraph boundaries, and exact match spans.

## 10.2 `UppercaseSentenceStartRule`

Use the accepted Russian sentence/token pipeline.

Do not implement a second sentence tokenizer inside the rule.

Verify pinned exclusions and sentence-start conditions rather than using a naive:

```python
sentence[0].islower()
```

## 10.3 `MultipleWhitespaceRule`

Handle the exact whitespace set and exclusions used by the pinned rule.

Test spaces, tabs, line boundaries, Unicode whitespace cases actually supported by upstream, and consecutive matches.

## 10.4 `SentenceWhitespaceRule`

Preserve the pinned distinction between whitespace problems associated with sentence boundaries and generic repeated whitespace.

## 10.5 `WhiteSpaceBeforeParagraphEnd`

Use real paragraph boundaries and exact spans.

Do not treat every newline as equivalent unless the pinned implementation does.

## 10.6 `WhiteSpaceAtBeginOfParagraph`

Match the pinned paragraph-start semantics and exclusions.

## 10.7 `LongSentenceRule`

Derive the exact Russian constructor/configuration from pinned `Russian.java`.

Preserve:

```text
threshold
counting unit
sentence segmentation dependency
default state
message/category
```

Do not guess the threshold.

## 10.8 `LongParagraphRule`

Derive exact threshold/configuration from the pinned registration.

Preserve priority:

```text
TOO_LONG_PARAGRAPH = -15
```

## 10.9 `ParagraphRepeatBeginningRule`

Port the actual repeated-paragraph-beginning algorithm and normalization rules.

Do not replace it with a simple `startswith()` comparison unless that is proven equivalent to the pinned implementation.

## 10.10 `PunctuationMarkAtParagraphEnd2`

Port exact punctuation-at-paragraph-end behavior, exceptions, message/span semantics, and priority:

```text
PUNCT_DPT_2 = -2
```

---

# 11. Russian-specific rule requirements

## 11.1 `RussianFillerWordsRule`

Trace the pinned class and any inherited/resource-backed filler-word configuration.

Preserve:

```text
exact word/phrase inventory
matching/token semantics
case behavior
message/category
span
suggestions, if any
```

Do not create a hand-written "common filler words" list from general Russian knowledge.

## 11.2 `RussianUnpairedBracketsRule`

Port the pinned Russian bracket-pair inventory and pairing behavior.

Test at least:

```text
balanced pair
missing opener
missing closer
nested pairs
mixed bracket types
quotes/brackets where relevant
multiple errors
paragraph/sentence boundaries
```

Use the exact upstream tests as primary evidence.

## 11.3 `RussianVerbConjugationRule`

This rule must use the accepted LT-compatible Russian analyses from the existing native pipeline.

Do not substitute pymorphy/Natasha or invent a new morphology layer.

Port exact POS/lemma/feature conditions, exclusions, finding spans, messages, and suggestions.

This is a morphology-sensitive rule and therefore requires oracle evidence beyond a couple of happy-path strings.

## 11.4 `RussianDashRule`

Port exact Russian dash/hyphen logic and its upstream exceptions.

Preserve:

```text
rule ID
replacement form(s)
span
message
priority RU_DASH_RULE = 12
```

Do not normalize all hyphens/dashes globally before the rule, because that can destroy observable offsets and rule semantics.

## 11.5 `RussianSpecificCaseRule`

Port exact resource/code behavior and priority:

```text
RUSSIAN_SPECIFIC_CASE = 9
```

Trace every pinned data dependency.

Do not recreate its cases from memory or a manually curated shortlist.

---

# 12. Upstream tests

Pinned Russian-module inventory already includes these directly relevant Task-0011 test files:

```text
RussianDashRuleTest.java
RussianSpecificCaseRuleTest.java
RussianUnpairedBracketsRuleTest.java
RussianVerbConjugationRuleTest.java
RussianTest.java
```

Also inspect the pinned upstream tree for tests covering:

```text
RussianFillerWordsRule
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

Some generic tests may live outside the Russian language module.

Task 0011 must inventory the exact upstream test source files/methods/assertions used as evidence.

Translate relevant upstream assertions into Python where practical.

Do not report "upstream parity" based only on newly invented local tests.

If a pinned class has no dedicated upstream test, state that explicitly and provide controlled oracle coverage instead.

---

# 13. Java oracle fixtures

Create deterministic Task-0011 oracle evidence against the trusted pinned Java LT build.

Recommended split:

```text
tests/fixtures/oracle_java_rules_0011_synthetic.json
tests/fixtures/oracle_java_rules_0011_russian.json
```

Names may differ if the repository has a stronger established convention, but the distinction must remain clear.

## 13.1 Synthetic fixture

Cover the behavior dimensions of all 15 Task-0011 rules.

Each case must identify at least:

```text
case id
rule class
rule ID
input text
enabled/default configuration if relevant
expected Java result(s)
finding count
finding order
UTF-16 spans
message
short message
suggestions
category
URL if present
feature/coverage labels
```

Where Python codepoint offsets are derived from Java UTF-16 offsets, test the conversion using non-BMP characters in representative cases.

Coverage must not consist of duplicate semantic cases with different IDs.

Create deterministic semantic signatures or equivalent integrity checks.

## 13.2 Real Russian fixture

Use real pinned upstream test cases and additional real Russian inputs exercising the exact registered rule configuration.

Do not use only English examples for generic rules merely because their base classes are generic. The target is the Russian LT pipeline.

## 13.3 Fixture provenance

Bind fixtures in:

```text
compat/oracle_manifest.json
```

with at least:

```text
path
byte size
SHA-256
case count
oracle build ID
pinned LT commit
```

Write fixture bytes deterministically with explicit LF newlines.

Do not repeat the CRLF-vs-LF mistake fixed in Task 0010. Humanity has already paid for that lesson once.

---

# 14. Oracle integrity tests

Add tests that independently verify the oracle evidence.

At minimum:

1. recompute fixture byte size and SHA-256 from raw bytes;
2. verify pinned upstream commit;
3. verify trusted oracle build identity;
4. ensure case IDs are unique;
5. recompute semantic signatures rather than trusting stored signatures;
6. ensure every declared coverage dimension has at least one case;
7. ensure all 15 Task-0011 rules have positive and negative coverage;
8. ensure expected results are produced by Java oracle evidence, not hand-entered Python expectations;
9. verify expected rule IDs and result counts;
10. include multi-finding cases where the pinned rule permits them.

The production test suite must consume committed fixtures and must not require Java.

---

# 15. Differential parity assertions

For oracle-backed Task-0011 tests, compare all observable fields supplied by the pinned Java result.

At minimum where applicable:

```text
rule class / registered rule identity
rule_id
category
default enabled state
finding count
finding order
UTF-16 from/to
Python codepoint from/to
source slices
message
short_message
suggestions and suggestion order
URL
priority/order metadata where externally relevant
```

A test that only asserts:

```text
len(matches) == 1
```

is not adequate parity evidence.

---

# 16. Pipeline integration

Task 0011 must not leave the new rules as isolated classes that are never called.

Integrate the 15 rules into the native Russian rule engine according to pinned `Russian.java` registration semantics.

The engine must be able to execute:

```text
XML grammar rules
+
Task-0011 native Java-rule equivalents
```

without Java.

Preserve deterministic result ordering.

If LanguageTool performs deduplication, overlap handling, priority selection, or rule disabling at a layer not yet represented in Python, implement only the exact portion required to reproduce Task-0011 observable behavior and document it.

Do not silently discard conflicting findings just to match a fixture.

---

# 17. Rule enablement and defaults

Inventory and preserve which rules are:

```text
enabled by default
disabled by default
configurable by threshold/options
```

The Python engine must not execute a default-off rule merely because its class exists.

Likewise, a default-on rule must not require a special test-only flag.

Tests must prove the default Russian configuration and explicit enablement behavior where the pinned API distinguishes them.

---

# 18. Offsets

All new findings must preserve the project's accepted offset contract.

Internally track both where required:

```text
Python codepoint offsets
Java/LT UTF-16 offsets for oracle comparison
```

Test:

- Cyrillic;
- combining accents used by Russian text;
- ignored LT characters where relevant;
- non-BMP characters before a match;
- multiple matches after non-BMP characters.

Never "fix" an offset mismatch by slicing the expected string until it looks right.

---

# 19. Resources and licensing

Any newly vendored upstream source/resource required by these rules must be:

1. taken from the pinned commit only;
2. recorded in `third_party/languagetool/UPSTREAM.json`;
3. hashed;
4. added to licensing/provenance inventory;
5. packaged only if required at production runtime.

If provenance/license is unclear:

```text
BLOCKED_LICENSE_REVIEW
```

Do not silently copy an asset.

Do not vendor Java binaries into production package data.

---

# 20. Compatibility reporting

Update:

```text
compat/compatibility.json
```

and add/update a dedicated Task-0011 inventory if useful, for example:

```text
compat/russian_java_rules_inventory.json
```

Expected post-Task-0011 metrics, subject only to proven pinned-source reconciliation:

```text
java_rules.status                         PARTIALLY_IMPLEMENTED

relevant_rules:
  implemented                            15
  total                                  23

russian_specific:
  implemented                             5
  total                                  13

generic:
  implemented                            10
  total                                  10

deferred_to_0012                          8

language_model_rules:
  implemented                             0
  total                                   1
```

Do not change the accepted XML grammar runnable/deferred counts merely because Java rules were added:

```text
grammar runnable source rules            778
grammar deferred source rules            114
grammar runnable examples               2119
grammar deferred examples                327
```

unless a genuine bug in the accepted inventory is independently proved.

Do not turn unresolved states into `SUPPORTED` by wording.

---

# 21. Production no-Java proof

Keep or extend the isolated wheel test.

Build/install the wheel into an environment where Java and the source tree are unavailable, then execute representative Task-0011 rules.

The proof must exercise at least:

```text
one generic whitespace rule
one paragraph/sentence rule
RussianDashRule or RussianSpecificCaseRule
one morphology-sensitive Russian rule
```

The installed wheel must not:

- invoke `java`;
- require `JAVA_HOME`;
- access the dev oracle;
- read resources outside installed package data;
- depend on the repository checkout.

---

# 22. Required focused tests

At minimum run focused suites covering:

```text
Task-0011 inventory
generic native rules
Russian-specific native rules
upstream-translated assertions
oracle fixture integrity
oracle parity
combined XML + Java-rule engine
offset parity
default enablement
priority/order behavior
wheel isolation
```

All previous Task 0001–0010 focused suites must remain passing.

---

# 23. Full regression

Run:

```text
python -m pytest -q
```

Requirements:

```text
failed  = 0
errors  = 0
skipped = 0
```

If a previously passing test fails, fix the regression.

Do not:

```text
skip
xfail
delete assertion
weaken comparison
remove oracle case
change expected Java output by hand
```

merely to make CI green.

---

# 24. GitHub CI

After the task is complete:

```text
focused tests
→ full pytest
→ completion report
→ git diff review
→ commit
→ push main
→ verify remote SHA
→ exact-SHA GitHub Actions verification
```

Required CI:

```text
Python 3.10 — success
Python 3.12 — success
```

Verify the workflow run belongs to the exact pushed Task-0011 SHA.

Do not claim completion based on:

- parent SHA;
- a different PR merge SHA;
- local pytest only;
- a manually rerun unrelated commit.

Never force-push or rewrite published history.

---

# 25. Completion report

Create:

```text
reports/0011_russian_java_rules.md
```

The report must contain at least:

```text
baseline SHA
final implementation SHA
pinned LT commit
exact 23-rule inventory
exact 15-rule Task-0011 implemented set
exact 8-rule Task-0012 deferred set
language-model rule status
source/resource hashes
upstream test inventory
translated test counts
oracle build identity
fixture paths/hashes/counts
per-rule oracle coverage
parity result summary
priority/default-enablement verification
wheel isolation result
focused test results
full pytest result
GitHub CI Python 3.10 result
GitHub CI Python 3.12 result
known differences
```

If there are unexplained differences:

```text
FINAL = BLOCKED / REVIEW-FIX
```

Do not describe them as harmless without evidence.

---

# 26. Definition of Done

Task 0011 is complete only when all of the following are true:

1. exact pinned `Russian.java` registration surface is revalidated;
2. all 10 Task-0011 generic rules have native Python implementations;
3. all 5 Task-0011 Russian-specific rules have native Python implementations;
4. the 8 Task-0012 rules remain explicitly deferred, not approximated;
5. `RussianConfusionProbabilityRule` remains explicitly accounted for;
6. exact IDs/categories/messages/spans/suggestions are preserved where applicable;
7. default enablement is compatible;
8. relevant Russian priority overrides are represented;
9. the 15 rules are integrated into the native Russian rule engine;
10. upstream tests are inventoried and relevant assertions translated;
11. Java oracle fixtures are deterministic and provenance-bound;
12. parity assertions compare full observable findings, not only counts;
13. UTF-16/codepoint offset parity is tested;
14. committed fixture integrity is independently verified;
15. production wheel executes representative rules without Java;
16. Tasks 0001–0010 remain passing;
17. full pytest has zero failures/errors/skips;
18. exact pushed SHA is verified on remote;
19. GitHub Actions Python 3.10 is green for that SHA;
20. GitHub Actions Python 3.12 is green for that SHA;
21. `reports/0011_russian_java_rules.md` matches reality;
22. no known compatibility gap is silently marked supported.

---

# 27. Expected stopping point

After successful Task 0011, stop.

Do **not** automatically start Task 0012.

Expected next task:

```text
Task 0012 — Spelling / compounds / replace / coherency / repetitions
```

Task 0012 will own these remaining 8 relevant Java rules:

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

and the spelling-dependent:

```text
RussianSuppressMisspelledSuggestionsFilter
```

That boundary must remain intact.
