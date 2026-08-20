# Task 0013 — Complete Pinned Russian Upstream Test Parity

## Status

**ACTIVE TASK SPECIFICATION**

Task 0012 is accepted as the exact baseline for this task.

Do not start Task 0014, Task 0015, release work, differential-corpus expansion, or unrelated refactors while implementing this task.

---

# 1. Goal

Establish **complete, mechanically auditable parity with the pinned upstream Russian LanguageTool test suite** at:

```text
LanguageTool v6.8
commit e807fcde6a6506191e1470744d2345da28c26be6
```

Task 0013 is primarily a **test-completeness and compatibility-proof task**.

The implementation is already expected to contain:

```text
Russian tokenization
Russian tagging
Russian disambiguation
Russian chunking
Russian synthesis
all 892 Russian XML grammar source rules
all 7 Russian XML filters
all 23 ordinary relevant Java-rule equivalents
native Morfologik spelling
LanguageTool-compatible match cleanup
```

Task 0013 must prove that the native Python implementation reproduces every relevant observable behavior exercised by the pinned Russian upstream tests.

Production execution must remain:

```text
100% Python-native
NO Java/JRE
NO LanguageTool server
NO Java subprocesses
NO localhost oracle
NO runtime downloads
NO network dependency
```

Java LanguageTool may be used only as a development/test oracle.

---

# 2. Exact accepted baseline

Repository:

```text
bojlahg/pylat_ru
branch: main
```

Accepted Task-0012 SHA:

```text
770c93496cc0e7646542d2ca0f618b774b650823
```

Task-0012 implementation commit:

```text
3032ddadff315c8546ecba13abc5528f9623e379
```

Accepted Task-0012 GitHub Actions run:

```text
run ID: 32409044294
event:  push
branch: main
head:   770c93496cc0e7646542d2ca0f618b774b650823
```

Accepted CI result:

```text
Python 3.10:
760 passed / 0 failed / 0 errors / 0 skipped

Python 3.12:
760 passed / 0 failed / 0 errors / 0 skipped
```

Pinned upstream:

```text
repository: https://github.com/languagetool-org/languagetool.git
tag:        v6.8
commit:     e807fcde6a6506191e1470744d2345da28c26be6
```

Accepted functional accounting:

```text
ordinary relevant Java rules              23 / 23
generic relevant Java rules               10 / 10
Russian-specific Java rules               13 / 13
Russian XML filters                         7 / 7

Russian XML source rules                  892 / 892 runnable
Russian XML examples                     2446 / 2446 runnable
compiled physical variants                907 / 907 runnable

language-model rules                        0 / 1
RussianConfusionProbabilityRule = LANGUAGE_MODEL_DEFERRED
```

Task 0013 must preserve all accepted behavior from Tasks 0001–0012.

---

# 3. Why this task exists

Current compatibility metadata still reports:

```text
upstream_tests.status = PARTIALLY_PORTED
upstream_test_files_total = 18
remaining_upstream_test_files_not_ported = 11
```

Earlier tasks translated or oracle-covered selected tests and assertions needed to prove individual subsystems.

That is not the same thing as proving:

```text
every relevant pinned Russian upstream test file
every relevant @Test method
every meaningful assertion/scenario
```

Task 0013 closes that gap.

Do not merely change:

```text
PARTIALLY_PORTED
```

to:

```text
PORTED
```

The transition must be mechanically proved.

---

# 4. Exact pinned Russian-module test-file inventory

The accepted pinned inventory contains exactly these **18 Russian-module test files**:

```text
1.  languagetool-language-modules/ru/src/test/java/org/languagetool/RussianConcurrencyTest.java

2.  languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/DateCheckFilterTest.java
3.  languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/LanguageSpecificSpellcheckerTest.java
4.  languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/MorfologikRussianSpellerRuleTest.java
5.  languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/MorfologikRussianYOSpellerRuleTest.java
6.  languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/RussianCompoundRuleTest.java
7.  languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/RussianDashRuleTest.java
8.  languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/RussianPatternRuleTest.java
9.  languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/RussianSimpleReplaceRuleTest.java
10. languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/RussianSpecificCaseRuleTest.java
11. languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/RussianTest.java
12. languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/RussianUnpairedBracketsRuleTest.java
13. languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/RussianVerbConjugationRuleTest.java
14. languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/RussianWordCoherencyRuleTest.java
15. languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/RussianWordRepeatRuleTest.java

16. languagetool-language-modules/ru/src/test/java/org/languagetool/synthesis/ru/RussianSynthesizerTest.java
17. languagetool-language-modules/ru/src/test/java/org/languagetool/tagging/ru/RussianTaggerTest.java
18. languagetool-language-modules/ru/src/test/java/org/languagetool/tokenizers/ru/RussianSRXSentenceTokenizerTest.java
```

This exact set is the primary Task-0013 source inventory.

If pinned-tree reinspection finds another executable Russian-module test file omitted by the current accepted inventory:

- do not ignore it;
- fix the inventory;
- document the discrepancy;
- include it in Task 0013.

If a listed file contains no executable `@Test` method because it is a helper/base test class, classify that explicitly rather than pretending it was "ported".

---

# 5. Core/generic upstream tests already used by earlier tasks

Earlier tasks also relied on generic/core LanguageTool test sources for behavior inherited by Russian, for example:

```text
CommaWhitespaceRuleTest
UppercaseSentenceStartRuleTest
MultipleWhitespaceRuleTest
SentenceWhitespaceRuleTest
LongSentenceRuleTest
LongParagraphRuleTest
PunctuationMarkAtParagraphEnd2Test
generic filter/base-rule tests where applicable
```

Task 0013 must **reconcile** these sources in the machine-readable test inventory.

However, the completion gate is not:

```text
port every test in the entire multilingual LanguageTool repository
```

Instead:

1. all 18 pinned Russian-module test files must be fully accounted;
2. every core/generic test source explicitly used as compatibility evidence by Tasks 0001–0012 must be accounted;
3. any additional inherited test source required to understand a Russian test method must be referenced and classified;
4. no unrelated multilingual test corpus needs to be imported.

---

# 6. Create a canonical upstream test inventory

Create:

```text
compat/upstream_test_inventory_0013.json
```

Generate it deterministically from pinned vendored/upstream source wherever practical.

For every test source record:

```text
source_path
source_sha256
module
Java test class
test file classification
@Test method names
parameterized-test methods if any
helper methods that materially define assertions
number of executable test methods
number of assertion/scenario units
Python translation file(s)
Python test function(s)
oracle fixture/case IDs where used
status
reason if not directly translated
```

Allowed per-method statuses:

```text
DIRECT_PYTHON_PARITY
ORACLE_PARITY
ALREADY_COVERED_EQUIVALENTLY
NOT_EXECUTABLE_HELPER
LANGUAGE_MODEL_DEFERRED
NOT_APPLICABLE_WITH_PROOF
BLOCKED
```

Do not use vague states such as:

```text
PARTIAL
MOSTLY_DONE
COVERED
```

without an exact mapping.

---

# 7. Method-level accounting is mandatory

File-level accounting alone is insufficient.

For each executable upstream test method, record:

```text
Java source file
Java method name
test semantics
individual assertion/scenario count
Python test mapping
oracle-case mapping, if any
status
```

Example shape:

```json
{
  "source": ".../RussianCompoundRuleTest.java",
  "method": "testRule",
  "scenario_count": 17,
  "status": "DIRECT_PYTHON_PARITY",
  "python_tests": [
    "tests/upstream/test_...py::..."
  ],
  "oracle_cases": [
    "compound_..."
  ]
}
```

The exact schema may differ, but the evidence must support deterministic completeness checks.

---

# 8. Define "assertion/scenario unit" consistently

JUnit tests often express behavior through:

```text
assertEquals
assertTrue
assertFalse
assertNull
assertNotNull
assertThrows
helper methods such as assertGood/assertBad
loops over test vectors
parameterized cases
arrays/lists of expected values
```

Task 0013 must not inflate or undercount evidence by counting only textual `assert` tokens.

Create a documented counting rule.

At minimum:

- one explicit assertion call = one assertion unit unless it validates a structured result intentionally;
- each table-driven input/expected pair = one scenario unit;
- each `assertGood("...")` / `assertBad("...")` call = one scenario unit;
- each loop item in a static test vector = one scenario unit;
- helper implementation itself is not counted repeatedly as a scenario;
- comments do not count;
- setup/constructor calls do not count.

Store enough source-location information to reproduce counts.

---

# 9. Source binding and drift detection

For every upstream test file used by Task 0013:

```text
verify pinned LT SHA
verify file SHA-256
verify file byte size
verify expected Java class
```

Tests must fail closed if:

```text
source file missing
hash changed
method disappeared
new method appeared
assertion/scenario count changed
mapping is missing
duplicate mapping occurs
```

The inventory must be regenerated deterministically.

Do not hand-maintain an unverifiable spreadsheet disguised as JSON.

---

# 10. Translate behavior, not Java syntax

For each upstream test method, reproduce the observable contract in Python.

Do not mechanically translate:

```java
new Russian(...)
new JLanguageTool(...)
```

if the equivalent accepted Python public surface is:

```python
LanguageToolRU(...)
```

The Python test should validate the same behavior at the appropriate layer.

Use the lowest layer that still preserves the upstream test's actual contract.

Examples:

```text
tokenizer upstream test
→ Python tokenizer directly

tagger upstream test
→ Python RussianTagger directly

synthesizer upstream test
→ Python RussianSynthesizer directly

specific Java rule test
→ RussianJavaRulesEngine.check_rule()

whole-language registration test
→ LanguageToolRU / inventory/public registration

pattern-rule integration test
→ native XML grammar pipeline

concurrency test
→ concurrent use of the public/native equivalent
```

---

# 11. Full observable parity for result-producing tests

Where an upstream test checks a rule or pipeline result, compare every observable field that the Java test or pinned Java behavior exposes and that the current native model supports:

```text
rule ID
full rule ID where applicable
category
message
short message
suggestions
suggestion order
from/to offsets
UTF-16 offsets
Python codepoint offsets
source slice
URL
default state
priority where relevant
```

Do not reduce a rich upstream assertion to:

```python
assert len(matches) == 1
```

when the upstream test validates more.

---

# 12. Use Java oracle only where appropriate

Direct Python translations are preferred when the expected value is explicitly encoded in the pinned upstream test.

Use the trusted Java oracle when:

```text
the upstream test depends on helper behavior not conveniently represented in Python
the assertion is indirect
ordering depends on Java collection/runtime semantics
the expected match surface is not explicitly written in the test
the public pipeline behavior is the real contract
```

Trusted oracle identity remains:

```text
pinned LT commit:
e807fcde6a6506191e1470744d2345da28c26be6

build ID:
lt_6.8_source_build_jdk17_stefan
```

Java oracle remains development-only.

---

# 13. Oracle evidence added in Task 0013

If new oracle fixtures are needed, use a dedicated namespace, for example:

```text
tests/fixtures/oracle_upstream_tests_0013.json
```

or split by subsystem if large:

```text
oracle_upstream_language_0013.json
oracle_upstream_rules_0013.json
oracle_upstream_pipeline_0013.json
```

Every case must map back to:

```text
upstream source file
upstream test method
upstream assertion/scenario unit
```

Do not add generic random corpus cases in this task.

That belongs to Task 0014.

---

# 14. Oracle semantic-signature integrity

Preserve the evidence rules established in Tasks 0011–0012.

Semantic signatures must be computed only from query semantics, e.g.:

```text
execution mode
target subsystem/rule
input
configuration
enabled/disabled rules
parameters that affect Java execution
```

Do not include:

```text
case ID
expected output
coverage label
stored finding count
source bookkeeping
stored signature
```

Assert:

```text
IDs unique
semantic signatures unique
manifest hashes exact
LF deterministic
pinned commit exact
oracle build exact
```

---

# 15. `RussianConcurrencyTest.java`

Port the actual upstream concurrency contract.

Do not replace it with:

```python
"call the function twice"
```

Inspect:

```text
thread count
shared-vs-separate LanguageTool instances
input corpus
iteration count
expected determinism
exception behavior
mutable singleton/resource interactions
```

The Python test must exercise the closest native equivalent.

Required outcome:

```text
no race exception
no state contamination
deterministic result
no mutation of shared dictionaries/resources
```

Do not weaken the upstream stress level without documented justification.

---

# 16. `DateCheckFilterTest.java`

Port every executable method/scenario.

Use deterministic dates/arguments from the pinned test.

Do not depend on the current wall clock unless upstream does.

Verify:

```text
weekday/month mapping
valid/invalid date behavior
argument parsing
match suppression/retention
```

Keep Task-0010 filter behavior green.

---

# 17. `LanguageSpecificSpellcheckerTest.java`

Inspect whether this file is:

```text
an executable test
a subclass of a generic spelling test harness
a helper/base integration test
```

Account for its inherited executable behavior, not just locally declared `@Test` methods.

If it inherits generic tests, record the inherited tests that actually execute for Russian.

Map them to:

```text
native default speller
LanguageToolRU public pipeline
spelling resource behavior
```

This is a common place for fake "file ported" accounting. Do not do that.

---

# 18. Morfologik spelling tests

Complete parity for:

```text
MorfologikRussianSpellerRuleTest.java
MorfologikRussianYOSpellerRuleTest.java
```

Task 0012 already has strong oracle coverage, but Task 0013 must map **every pinned upstream method/scenario**.

Verify where applicable:

```text
correct/misspelled verdict
exact suggestions
suggestion order
case behavior
hyphens
ё/е
dictionary additions
NOSUGGEST behavior
default-off YO rule
configuration
```

Do not count Task-0012 oracle cases as upstream-test coverage unless they are explicitly mapped to the upstream scenario.

---

# 19. Rule tests

Fully account and translate:

```text
RussianCompoundRuleTest.java
RussianDashRuleTest.java
RussianSimpleReplaceRuleTest.java
RussianSpecificCaseRuleTest.java
RussianUnpairedBracketsRuleTest.java
RussianVerbConjugationRuleTest.java
RussianWordCoherencyRuleTest.java
RussianWordRepeatRuleTest.java
```

For each:

- map every executable method;
- map every explicit/vectorized scenario;
- preserve exact positive and negative semantics;
- preserve output fields checked upstream;
- add oracle only where direct translation cannot prove the contract.

Task-0011/0012 selected cases do not automatically satisfy full method-level parity.

---

# 20. `RussianPatternRuleTest.java`

Determine exactly what the pinned test validates:

```text
grammar.xml loadability
pattern-rule examples
rule IDs
full Russian pattern-rule harness behavior
```

Port the actual contract.

The project already executes all:

```text
892 source rules
2446 embedded XML examples
907 compiled variants
```

Reuse that infrastructure rather than creating a second grammar harness.

If the upstream test delegates to a generic framework, trace and account for the inherited assertions that actually execute for Russian.

---

# 21. `RussianTest.java`

Port all whole-language assertions.

Verify exact registered components and metadata exercised upstream, including as applicable:

```text
language short code
countries/variants
tagger
synthesizer
disambiguator
chunker
word tokenizer
sentence tokenizer
relevant rules
default spelling rule
rule priorities
language-model rules
ignored characters
```

Do not broaden this into unsupported LanguageTool API emulation.

Implement only what the pinned Russian test contract requires.

---

# 22. `RussianSynthesizerTest.java`

Map every upstream synthesis case.

Use the native packaged Morfologik synthesis dictionary.

Compare exact:

```text
input lemma
POS tag / regex mode
forms
form order
empty result
case behavior
special-number behavior if upstream test reaches it
```

Keep existing 52 synthesizer oracle queries green.

---

# 23. `RussianTaggerTest.java`

Map every upstream tagging case.

Compare exact ordered readings as appropriate:

```text
surface token
lemma
POS tag
reading count
reading order where observable
normalization
case fallback
unknown-token behavior
accent handling
ё handling
manual additions/removals
```

Do not replace exact tag parity with a semantic subset check.

---

# 24. `RussianSRXSentenceTokenizerTest.java`

Map every upstream tokenizer scenario.

Compare exact sentence segmentation and reconstruction.

Cover all pinned cases involving, as applicable:

```text
abbreviations
initials
numbers
quotes
parentheses
ellipsis
newlines
URLs/emails
Russian abbreviations
non-BMP characters
single-line behavior if exercised
```

Do not normalize whitespace before comparison unless upstream does.

---

# 25. Generic/core tests used as inherited evidence

Create a second inventory section for non-Russian-module sources explicitly relied upon by prior tasks.

At minimum reconcile the sources already named in:

```text
compat/russian_java_rules_inventory.json
reports/000x...
reports/0010...
reports/0011...
reports/0012...
```

For each such source:

```text
source hash
method names
which Russian behavior depends on it
whether direct Python tests already map it
whether additional translation is required
```

Do not require 100% of unrelated generic-core test files.

Require 100% of the specific core test methods claimed as compatibility evidence.

---

# 26. Existing test reuse is encouraged, but mapping must be exact

Do not duplicate tests just to increase counts.

An existing Python test may satisfy an upstream assertion if it genuinely checks the same contract.

Record the mapping.

One Python test may satisfy multiple upstream scenarios only when the test makes all those checks explicitly.

One upstream scenario may map to:

```text
direct Python test
+
oracle parity test
```

if both are materially useful.

Avoid meaningless N:N mappings.

---

# 27. No silent exclusions

Every executable upstream method/scenario must end in one of:

```text
DIRECT_PYTHON_PARITY
ORACLE_PARITY
ALREADY_COVERED_EQUIVALENTLY
LANGUAGE_MODEL_DEFERRED
NOT_APPLICABLE_WITH_PROOF
BLOCKED
```

Acceptance requires:

```text
BLOCKED = 0
unmapped = 0
unknown = 0
```

`NOT_APPLICABLE_WITH_PROOF` must contain an exact reason tied to pinned source.

`LANGUAGE_MODEL_DEFERRED` may only be used for behavior that truly requires:

```text
RussianConfusionProbabilityRule
```

or its language-model dependency.

Do not use the LM bucket as a garbage chute.

---

# 28. Language-model boundary

Task 0013 does **not** implement:

```text
RussianConfusionProbabilityRule
```

Expected accounting remains:

```text
language-model rules:
0 / 1

RussianConfusionProbabilityRule:
LANGUAGE_MODEL_DEFERRED
```

If an upstream Russian test file/method directly exercises this rule:

- inventory it;
- classify it exactly as `LANGUAGE_MODEL_DEFERRED`;
- prove why it cannot be part of ordinary native parity yet;
- do not count it as ordinary upstream-test failure.

If no pinned test exercises it, record that fact.

---

# 29. Assertions that reveal a real compatibility bug

Task 0013 is not read-only QA.

If a faithful upstream test exposes a Python behavioral mismatch:

1. fix the implementation;
2. add a regression test;
3. preserve the upstream mapping;
4. add Java-oracle evidence when useful;
5. update compatibility metadata.

Do not:

```text
weaken the translated assertion
edit the expected result
mark the method not applicable
skip/xfail it
```

just to make the suite green.

---

# 30. Upstream-test inventory validation tests

Add dedicated tests, e.g.:

```text
tests/unit/test_upstream_test_inventory_0013.py
```

They must independently verify:

```text
pinned LT commit
18 Russian-module source files exactly, unless pinned reinspection proves otherwise
source hashes
source byte sizes
Java class names
executable method inventory
method names
scenario counts
status enum
Python mapping references
oracle mapping references
no duplicate source/method identity
no unmapped executable method
no BLOCKED
no UNKNOWN
no unexplained exclusions
```

Validate that every referenced Python test node/file actually exists.

Where practical, validate test function names mechanically.

---

# 31. Coverage matrix

Create a human-readable and machine-readable coverage summary.

Machine-readable source of truth:

```text
compat/upstream_test_inventory_0013.json
```

Report should summarize per file:

```text
file
methods
scenario/assertion units
direct Python
oracle
equivalent existing
LM-deferred
not-applicable
blocked
```

Expected acceptance:

```text
18/18 Russian-module files accounted

100% executable ordinary/non-LM methods mapped
100% ordinary/non-LM scenario units mapped

BLOCKED = 0
UNKNOWN = 0
UNMAPPED = 0
```

Do not predeclare the exact method/scenario total before mechanically deriving it.

---

# 32. Preserve full Russian XML parity

Task 0013 must keep:

```text
892 / 892 source rules runnable
2446 / 2446 examples runnable
907 / 907 compiled variants runnable
```

Run all existing XML example tests.

Do not regress:

```text
trigger parity
correct-example false-positive parity
marker spans
suggestion order
filters
unification
advanced matching
suppress-misspelled behavior
```

---

# 33. Preserve Task-0011 and Task-0012 oracle evidence

All accepted oracle evidence remains mandatory.

At minimum preserve:

```text
Task 0011:
126 single-rule cases
11 combined-pipeline cases
137 total

Task 0012:
59 spelling cases
67 other rule cases
10 filter cases
15 combined cases
151 total
```

Existing semantic-signature integrity must remain green.

Do not regenerate old fixtures with changed semantics unless a newly found pinned-compatibility bug proves they were wrong.

If an old fixture must change:

- document exactly why;
- prove new Java output;
- update manifest;
- make the change reviewable.

---

# 34. Concurrency and state isolation

Because the pinned suite contains `RussianConcurrencyTest`, explicitly test that shared native components remain safe:

```text
RussianTagger singleton
RussianHybridDisambiguator singleton
RussianSynthesizer singleton
Morfologik dictionary caches
speller caches
grammar-engine caches
resource loaders
rule engines
```

No mutable per-check state may leak between concurrent calls.

If public `LanguageToolRU` instances themselves are not documented thread-safe, reproduce the exact upstream test's sharing model and document the compatibility boundary.

---

# 35. Wheel isolation regression

Keep the real installed-wheel proof green.

Task 0013 must not accidentally make upstream-test support a production dependency on:

```text
Java
vendored Java source
pytest
oracle fixtures
Git checkout
network
development-only files
```

The wheel should contain runtime resources, not the entire upstream test tree unless explicitly intended.

Run existing wheel isolation tests unchanged or stronger.

---

# 36. Production dependency audit

After adding test-parity infrastructure, verify that production imports do not reach:

```text
tools/
tests/
third_party/languagetool test sources
Java oracle code
pytest
development parsers used only to inventory Java tests
```

Test-only tooling must stay test/dev-only.

---

# 37. Deterministic test extraction tool

Add a small deterministic extractor, for example:

```text
tools/inventory_upstream_tests_0013.py
```

It should parse enough Java test structure to inventory:

```text
class
@Test methods
parameterized executable methods where used
common assertion/helper invocations
static/vector test scenarios where mechanically identifiable
```

It does not need to be a full Java parser if a smaller deterministic approach is robust for the 18 pinned files.

Fail closed on unsupported syntax that would make counts ambiguous.

Do not silently undercount.

---

# 38. Upstream Java test execution as secondary evidence

Where practical, record a trusted execution of the pinned upstream Russian Maven/JUnit suite itself.

This is **development evidence**, not a production dependency.

If the environment can execute the exact pinned Russian test module, record:

```text
command
pinned checkout SHA
JDK version
test classes
passed/failed/skipped
```

This does not replace Python translations.

It proves the source test suite itself is green at the pin and helps detect mistaken test extraction.

If running the entire upstream module requires unrelated infrastructure unavailable in the trusted oracle build, document the limitation rather than inventing a passing result.

---

# 39. Full Python test suite

Run:

```text
python -m pytest -q
```

Required:

```text
failed  = 0
errors  = 0
skipped = 0
```

No:

```text
skip
xfail
conditional "Java unavailable" escape hatch
```

in ordinary committed Python tests.

Java-dependent fixture generation remains an explicit dev command and must not run during normal pytest.

---

# 40. CI exact-SHA requirement

Commit and push final Task-0013 implementation to `main`.

GitHub Actions must run on the exact final SHA.

Required matrix:

```text
Python 3.10
Python 3.12
```

For each job:

```text
git rev-parse HEAD == GITHUB_SHA == FINAL_SHA
```

and:

```text
<passed> passed / 0 failed / 0 errors / 0 skipped
```

Both jobs:

```text
conclusion = success
```

The final head must not change after the verified CI run.

If a later docs-only correction commit is made, run CI again on that new final SHA.

---

# 41. Update compatibility metadata

Update:

```text
compat/compatibility.json
compat/upstream_test_inventory_0013.json
compat/oracle_manifest.json
```

as applicable.

Expected successful test-status transition:

```text
upstream_tests.status:
PARTIALLY_PORTED
→ COMPLETE_PINNED_RUSSIAN_TEST_PARITY
```

Record exact values:

```text
Russian-module test files total
Russian-module files accounted
executable methods total
ordinary/non-LM methods mapped
scenario/assertion units total
ordinary/non-LM units mapped
direct Python mappings
oracle mappings
already-covered mappings
LM-deferred mappings
not-applicable mappings
blocked
unmapped
```

Do not preserve stale fields such as:

```text
remaining_upstream_test_files_not_ported = 11
```

after completion.

---

# 42. Known differences

Task 0012 currently records:

```text
known_differences = []
```

Do not automatically preserve that statement.

After complete upstream-test parity:

- if no ordinary/native mismatch remains, keep `[]`;
- if an intentional compatibility difference is discovered, record it precisely;
- if a difference violates the pinned tests, fix it rather than documenting it away.

Language-model deferral remains separate accounting, not an ordinary `known_difference`.

---

# 43. Required report

Create:

```text
reports/0013_complete_upstream_russian_test_parity.md
```

Include:

```text
baseline SHA
final SHA
pinned LT SHA

18-file pinned inventory result
test extraction methodology
total executable method count
total scenario/assertion-unit count

per-file coverage table
direct Python mapping count
oracle mapping count
already-covered count
LM-deferred count
not-applicable count
blocked/unmapped count

bugs exposed by upstream tests
implementation fixes made
old oracle fixtures changed, if any

892/892 grammar status
2446/2446 example status
907/907 variant status

Task0011 oracle regression result
Task0012 oracle regression result

concurrency result
wheel isolation result
production dependency audit

full pytest result
exact-SHA Actions run
known differences
LM rule status
```

Do not report only file counts.

Method/scenario completeness is the point of Task 0013.

---

# 44. Definition of Done

Task 0013 is complete only if all are true:

1. The exact pinned Russian-module test-file inventory is mechanically verified.
2. All 18 currently inventoried Russian test files are accounted, unless pinned-source proof changes the count.
3. Every executable test method has an explicit mapping/status.
4. Every ordinary/non-LM executable method is covered.
5. Every ordinary/non-LM assertion/scenario unit is covered.
6. Inherited executable behavior from helper/base test classes is accounted where relevant.
7. Core/generic test sources previously claimed as Russian compatibility evidence are reconciled.
8. `BLOCKED = 0`.
9. `UNKNOWN = 0`.
10. `UNMAPPED = 0`.
11. No test is hidden behind skip/xfail.
12. Any incompatibility exposed by faithful upstream tests is fixed in production code.
13. All source hashes are pinned and validated.
14. Oracle mappings are source-method traceable.
15. Oracle semantic signatures remain unique and evidence-based.
16. Task0011 fixtures/tests remain green.
17. Task0012 fixtures/tests remain green.
18. Russian XML rules remain 892/892 runnable.
19. Russian XML examples remain 2446/2446 runnable.
20. Compiled variants remain 907/907 runnable.
21. Concurrency parity is proven.
22. Wheel isolation remains PASS.
23. Production has no Java/test/oracle runtime dependency.
24. Full pytest has 0 failed/errors/skipped.
25. Exact final SHA CI passes on Python 3.10 and 3.12.
26. `upstream_tests.status = COMPLETE_PINNED_RUSSIAN_TEST_PARITY`.
27. `RussianConfusionProbabilityRule` remains explicitly `LANGUAGE_MODEL_DEFERRED`.
28. Task 0014 work is not started.

---

# 45. Final handoff format

The executor's final response must contain concrete values:

```text
Task 0013 final verification

baseline:
770c93496cc0e7646542d2ca0f618b774b650823

final main SHA:
<SHA>

implementation commit:
<SHA>

Pinned LT:
e807fcde6a6506191e1470744d2345da28c26be6

Pinned Russian-module test files:
<accounted>/<total>

Executable upstream methods:
<mapped>/<total>

Ordinary/non-LM methods:
<mapped>/<total>

Scenario/assertion units:
<mapped>/<total>

Direct Python parity mappings:
<count>

Oracle parity mappings:
<count>

Already-covered equivalent mappings:
<count>

LM-deferred:
<count>

Not-applicable-with-proof:
<count>

Blocked:
0

Unmapped:
0

Unknown:
0

Generic/core evidence sources reconciled:
<count>/<count>

Task0011 oracle:
137/137

Task0012 oracle:
151/151

Task0013 new oracle:
<count>/<count>

Grammar source rules:
892/892
0 deferred

Grammar examples:
2446/2446
0 deferred

Compiled variants:
907/907

Concurrency:
PASS/FAIL

Wheel isolation:
PASS/FAIL

Production dependency audit:
PASS/FAIL

Full pytest:
<passed> passed
0 failed
0 errors
0 skipped

Actions run ID:
<id>

Actions run URL:
<url>

Actions head_sha:
<SHA>

Python 3.10:
<passed> passed / 0 failed / 0 errors / 0 skipped
checkout SHA: <SHA>

Python 3.12:
<passed> passed / 0 failed / 0 errors / 0 skipped
checkout SHA: <SHA>

upstream_tests.status:
COMPLETE_PINNED_RUSSIAN_TEST_PARITY

Language-model rule:
0/1
RussianConfusionProbabilityRule = LANGUAGE_MODEL_DEFERRED

Known differences:
<none or exact list>

FINAL:
READY FOR REVIEW
```

If any ordinary/non-LM upstream method/scenario remains unmapped or failing:

```text
FINAL:
BLOCKED
```

with exact source file, method, scenario, expected pinned behavior, and blocker.

After this response, stop.

Do not start Task 0014.
