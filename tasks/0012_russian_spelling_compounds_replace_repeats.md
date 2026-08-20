# Task 0012 — Russian Spelling, Compounds, Replace, Coherency, Repetitions, and Final XML Filter

## Status

**ACTIVE TASK SPECIFICATION**

Task 0011 is accepted and is the exact baseline for this task.

Do not start Task 0013, Task 0014, Task 0015, or unrelated refactors while implementing this task.

---

# 1. Goal

Complete the remaining **8 ordinary Russian Java rules** and the final deferred Russian XML rule filter at the pinned LanguageTool revision:

```text
LanguageTool v6.8
commit e807fcde6a6506191e1470744d2345da28c26be6
```

Task 0012 extends the accepted Python-native pipeline from:

```text
tokenization
→ tagging
→ disambiguation
→ chunking
→ XML grammar
→ XML filters 6/7
→ 15 native Java-rule equivalents
→ LanguageTool-compatible match cleanup
```

to:

```text
tokenization
→ tagging
→ disambiguation
→ chunking
→ native spelling
→ all 23 ordinary Russian Java-rule equivalents
→ all 7 Russian XML filters
→ combined Russian LanguageTool findings
```

This task is **compatibility work**, not a redesign of Russian spelling and not a generic spell-checking exercise.

Production execution must remain fully Python-native:

```text
NO Java/JRE
NO LanguageTool server
NO Java subprocesses
NO localhost oracle calls
NO runtime LanguageTool downloads
NO external spell-check service
NO Natasha/pymorphy substitution
```

Java LanguageTool may be used only as a development/test oracle.

---

# 2. Exact accepted baseline

Repository:

```text
bojlahg/pylat_ru
branch: main
```

Accepted Task-0011 SHA:

```text
663ca3e222d694b92074f0b87da86c5e566f4bd4
```

Accepted exact-SHA GitHub Actions evidence:

```text
run ID: 32378681412
event:  push
branch: main
head:   663ca3e222d694b92074f0b87da86c5e566f4bd4

Python 3.10:
513 passed / 0 failed / 0 errors / 0 skipped

Python 3.12:
513 passed / 0 failed / 0 errors / 0 skipped
```

Pinned upstream:

```text
repository: https://github.com/languagetool-org/languagetool.git
tag:        v6.8
commit:     e807fcde6a6506191e1470744d2345da28c26be6
Morfologik: 2.1.9
```

Accepted Task-0011 accounting:

```text
ordinary relevant Java rules total               23
implemented                                       15
deferred to Task 0012                              8

generic Java rules                               10 / 10
Russian-specific Java rules                       5 / 13

language-model rules                              0 / 1
XML filters                                       6 / 7
```

Accepted grammar state before Task 0012:

```text
grammar source rules total                       892
runnable source rules                            778
deferred source rules                            114
unknown source rules                               0

grammar examples total                          2446
runnable examples                               2119
deferred examples                                327

compiled physical variants total                 907
runnable compiled variants                       772
```

Task 0012 must preserve all accepted behavior from Tasks 0001–0011.

---

# 3. Exact Task-0012 ordinary Java-rule scope

Implement exactly these 8 remaining ordinary rules:

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

Expected ordinary Java-rule accounting after successful Task 0012:

```text
ordinary relevant Java rules total               23
implemented                                      23
deferred ordinary Java rules                      0

generic                                           10 / 10
Russian-specific                                  13 / 13
```

The language-model rule remains separate:

```text
RussianConfusionProbabilityRule
```

Expected after Task 0012:

```text
language-model rules implemented                   0 / 1
status: LANGUAGE_MODEL_DEFERRED
```

Do not implement or approximate `RussianConfusionProbabilityRule` in this task.

---

# 4. Final XML filter in Task 0012

Implement the final deferred Russian XML rule filter:

```text
org.languagetool.rules.ru.RussianSuppressMisspelledSuggestionsFilter
```

It inherits its behavior from:

```text
org.languagetool.rules.AbstractSuppressMisspelledSuggestionsFilter
```

Expected filter accounting after successful Task 0012:

```text
Russian XML filters                               7 / 7
recognized deferred XML filters                   0
```

This filter belongs in Task 0012 because it depends on a real default spelling rule.

Do not fake it by:

- checking suggestions against the tagger dictionary;
- checking against a small Python set;
- calling Java at runtime;
- treating all Cyrillic strings as valid;
- using edit distance as a spelling oracle.

---

# 5. First required step: re-inspect and bind the pinned source surface

Before implementation, re-inspect the exact pinned source and update the deterministic inventory.

For every Task-0012 rule record at least:

```text
registration order
registration line/location in Russian.java
constructor arguments
rule class
actual rule ID
category ID/name
default enabled/disabled state
rule-specific UserConfig
configured priority target
configured priority value
effective priority
priority binding status
source file
source SHA-256
direct resource dependencies
transitive resource dependencies
upstream tests
inherited classes whose behavior is observable
Task-0012 classification
```

Do not trust leaf class names as the whole behavior.

For inherited implementations inspect and bind the relevant pinned base classes, including as applicable:

```text
MorfologikSpellerRule
SpellingCheckRule
AbstractCompoundRule
CompoundRuleData
AbstractSimpleReplaceRule / actual pinned replace base
AbstractWordRepeatRule / actual pinned repeat bases
AbstractSuppressMisspelledSuggestionsFilter
```

If the exact inherited class hierarchy differs from these names at the pin, use the pinned hierarchy and document it.

---

# 6. Exact rule registration and priority semantics

Preserve the effective pinned Russian priority behavior.

Known Task-0012 priority entries from `Russian.java` include:

```text
RU_COMPOUNDS                         11
RUSSIAN_SIMPLE_REPLACE_RULE          10
MORFOLOGIC_RULE_RU_RU_YO              2
MORFOLOGIC_RULE_RU_RU                 1
Word_root_repeat                      -1
```

However the configured keys do not always equal actual rule IDs.

Accepted Task-0011 inventory currently establishes:

```text
RU_COMPOUNDS:
  actual ID: RU_COMPOUNDS
  effective priority: 11
  binding: BOUND

MorfologikRussianSpellerRule:
  actual ID: MORFOLOGIK_RULE_RU_RU
  configured target: MORFOLOGIC_RULE_RU_RU
  effective priority: 0
  binding: ORPHAN_OVERRIDE_ID

MorfologikRussianYOSpellerRule:
  actual ID: MORFOLOGIK_RULE_RU_RU_YO
  configured target: MORFOLOGIC_RULE_RU_RU_YO
  effective priority: 0
  binding: ORPHAN_OVERRIDE_ID

RussianSimpleReplaceRule:
  actual ID: RU_SIMPLE_REPLACE
  configured target: RUSSIAN_SIMPLE_REPLACE_RULE
  effective priority: 0
  binding: ORPHAN_OVERRIDE_ID

RussianWordRootRepeatRule:
  actual ID: RU_WORD_ROOT_REPEAT
  configured target: Word_root_repeat
  effective priority: 0
  binding: ORPHAN_OVERRIDE_ID
```

Do not "fix" upstream typo/mismatch keys.

Compatibility means preserving the pinned effective result, including upstream mistakes.

The other Task-0012 rules are expected to use base priority unless pinned source proves otherwise.

---

# 7. Default enablement

Preserve exact default state:

```text
MorfologikRussianSpellerRule          ON
MorfologikRussianYOSpellerRule        OFF
RussianCompoundRule                   ON
RussianSimpleReplaceRule              ON
RussianSimpleWordRepeatRule           ON
RussianWordCoherencyRule              ON
RussianWordRepeatRule                 OFF
RussianWordRootRepeatRule             OFF
```

Verify each state from the pinned classes and registration.

The public `LanguageToolRU` enable/disable behavior must work consistently across Tasks 0011 and 0012.

---

# 8. Native Morfologik spelling subsystem

This is the highest-risk part of Task 0012.

Do not implement spelling as:

```python
word not in dictionary
```

and do not generate suggestions using a generic Levenshtein loop over every dictionary word.

The implementation must reproduce the observable behavior of pinned LanguageTool/Morfologik.

## 8.1 Reuse existing native dictionary infrastructure

The project already has:

```text
Morfologik FSA reader
metadata parser
sequence decoder
Russian tagger dictionary support
synthesis dictionary support
```

Reuse these components where their semantics match the spelling dictionary format.

Do not introduce a second incompatible FSA implementation unless the pinned spelling format genuinely requires it.

## 8.2 Spelling resources

At minimum inspect the pinned Russian hunspell/Morfologik resources:

```text
/ru/hunspell/ru_RU.dict
/ru/hunspell/ru_RU.info
/ru/hunspell/ru_RU_yo.dict
/ru/hunspell/ru_RU_yo.info
/ru/hunspell/spelling.txt
```

Also inspect whether the inherited spelling stack reads any of:

```text
/ru/hunspell/ignore.txt
/ru/hunspell/prohibit.txt
frequency resources
replacement/conversion resources
other base-class resources
```

The leaf inventory is not sufficient proof of the transitive runtime dependency set.

Package every file actually used by the pinned runtime semantics.

Record exact upstream byte sizes and SHA-256 values.

## 8.3 `MorfologikRussianSpellerRule`

Actual rule ID:

```text
MORFOLOGIK_RULE_RU_RU
```

Pinned leaf behavior includes:

```text
dictionary: /ru/hunspell/ru_RU.dict
isLatinScript(): false
Russian-letter token filter
UserConfig integer option, default 0
```

The Russian-letter regex must be traced exactly, including:

```text
hyphen
ё/Ё
combining acute/grave variants
modifier apostrophe
Russian uppercase/lowercase
```

Default `conf_ru_Value`:

```text
0
```

Pinned meaning:

```text
0: normally ignore tokens not matching the Russian-letter pattern
1: allow checking non-Russian/Latin terms
```

Do not infer runtime validation from `RuleOption(0, 1)`.

Probe Java with at least:

```text
-1
0
1
2
```

and reproduce constructor/runtime behavior rather than imposing Python-only bounds.

## 8.4 NOSUGGEST filtering

For the ordinary Russian speller, suggestions whose lowercase replacement is one of:

```text
блоггер
дрочим
анальный
орочем
```

must be filtered exactly as pinned.

Do not confuse:

```text
"word is accepted by dictionary"
```

with:

```text
"word is allowed to appear as a suggestion"
```

They are separate observable behaviors.

## 8.5 Spell-check behavior to trace

Trace inherited behavior for:

```text
isMisspelled
ignoreWord
ignoreToken
token immunization
sentence-start behavior
URLs
emails
numbers
punctuation
hyphenated tokens
mixed scripts
case variants
all-uppercase/title-case/mixed-case words
accepted spelling additions
prohibited spellings
ignored spellings
alternative languages
user dictionary/config if reachable through current public API
suggestion generation
suggestion ordering
suggestion capitalization
replacement/conversion tables
maximum suggestion count
exact messages
short messages
category
URLs
match spans
multiple errors per sentence
```

Only implement behavior proven relevant to the registered Russian rule and current `LanguageToolRU` surface.

Do not create speculative multilingual infrastructure.

---

# 9. `MorfologikRussianYOSpellerRule`

Actual ID:

```text
MORFOLOGIK_RULE_RU_RU_YO
```

Dictionary:

```text
/ru/hunspell/ru_RU_yo.dict
```

Default:

```text
OFF
```

Description and message behavior must match pinned Java.

It shares the Russian-letter/config behavior with the ordinary Russian speller, but uses its own dictionary and suggestion filtering.

Its do-not-suggest set includes:

```text
блоггер
елка
дрочим
анальный
орочем
```

Test ordinary `е`/`ё` distinctions using Java oracle results.

Do not assume that every `е` can or should be suggested as `ё`.

Preserve exact dictionary-driven behavior.

---

# 10. Suggestion engine parity

For spelling findings, parity is not achieved merely by identifying the same misspelled token.

Compare the full observable suggestion surface:

```text
suggestion text
suggestion order
case
deduplication
NOSUGGEST suppression
empty suggestion list
multiple suggestion count
```

The native implementation must use a search/generation approach compatible with pinned Morfologik semantics.

Performance requirement:

```text
NO O(dictionary_size) full scan per token
```

The large spelling dictionaries must be queried through an indexed/native FSA-compatible algorithm.

If upstream uses edit-distance automata, replacement pairs, frequency ordering, case conversion, or equivalent machinery, port the relevant observable semantics.

Do not substitute an arbitrary Python spellchecker library.

---

# 11. `RussianCompoundRule`

Actual ID:

```text
RU_COMPOUNDS
```

Priority:

```text
11
```

Resource:

```text
/ru/compounds.txt
```

Pinned leaf class extends `AbstractCompoundRule`, sets:

```text
sentenceStartsWithUpperCase = true
```

and provides three message forms:

```text
must be hyphenated
must be joined
may be hyphenated or joined
```

Trace the actual pinned semantics of:

```text
CompoundRuleData
resource line syntax/markers
two-token vs multi-token compounds
space → hyphen suggestion
space → joined suggestion
either-form suggestion
case conversion
sentence-start uppercase handling
punctuation boundaries
token boundaries
multiple findings
UserConfig if used by inherited class
```

Do not reuse `RussianDashRule` canonicalization logic. That rule solves a different problem.

---

# 12. `RussianSimpleReplaceRule`

Actual ID:

```text
RU_SIMPLE_REPLACE
```

Resource:

```text
/ru/replace.txt
```

Effective priority at the pin:

```text
0
```

because the Russian priority override uses a different ID.

Trace the inherited replace-rule implementation and exact file format.

Preserve:

```text
single-word replacements
multi-word replacements if supported
case sensitivity
case adaptation
tokenization
message
short message
suggestions and order
multiple alternatives
span
multiple findings
punctuation adjacency
start/end of text behavior
```

Do not turn `replace.txt` into a naive `str.replace()` map.

---

# 13. Repetition and coherency rules

Implement exact pinned behavior for:

```text
RussianSimpleWordRepeatRule
RussianWordCoherencyRule
RussianWordRepeatRule
RussianWordRootRepeatRule
```

## 13.1 `RussianSimpleWordRepeatRule`

Actual ID:

```text
WORD_REPEAT_RULE
```

Default:

```text
ON
```

No dedicated upstream test is currently recorded in the accepted inventory.

Therefore:

- inspect inherited/base implementation;
- create controlled Java oracle coverage;
- document absence of a dedicated pinned Russian test if still true.

Test at least:

```text
immediate repeated word
case variants
punctuation between repeats
sentence boundary
paragraph boundary
quoted text
repetition that should be ignored
multiple repeats
exact span/message/suggestions
```

## 13.2 `RussianWordCoherencyRule`

Actual ID:

```text
RU_WORD_COHERENCY
```

Resource:

```text
/ru/coherency.txt
```

Default:

```text
ON
```

Port exact resource syntax, matching window/state, case behavior, and finding semantics.

Use the pinned `RussianWordCoherencyRuleTest.java` as primary evidence.

## 13.3 `RussianWordRepeatRule`

Actual ID:

```text
RU_WORD_REPEAT
```

Default:

```text
OFF
```

Use the pinned `RussianWordRepeatRuleTest.java`.

Trace:

```text
distance/window
normalization
ignored words
punctuation behavior
sentence/paragraph boundaries
message/span
multiple matches
```

Do not collapse it into `RussianSimpleWordRepeatRule`.

## 13.4 `RussianWordRootRepeatRule`

Actual ID:

```text
RU_WORD_ROOT_REPEAT
```

Resource:

```text
/ru/wordrootrep.txt
```

Default:

```text
OFF
```

Effective priority:

```text
0
```

because `Word_root_repeat = -1` does not bind the actual rule ID at the pin.

No dedicated upstream test is currently recorded in the accepted inventory.

Use controlled Java oracle cases to prove:

```text
resource syntax
root/group matching semantics
distance/window
case normalization
word/token boundaries
punctuation
sentence boundaries
false-positive exclusions
multiple findings
exact output
```

---

# 14. `RussianSuppressMisspelledSuggestionsFilter`

Implement the exact inherited observable behavior.

Required argument:

```text
suppressMatch
```

Optional argument, exact spelling/case from pinned source:

```text
SuppressPostag
```

Behavior:

1. obtain the language's **default spelling rule**;
2. tokenize each replacement using the Russian word tokenizer;
3. a replacement is misspelled if **any token** is misspelled by the default spelling rule;
4. discard misspelled replacements;
5. if `SuppressPostag` is provided:
   - tag replacement strings using the language tagger;
   - also discard replacements matching that POS regex;
6. `suppressMatch` defaults operationally to suppression unless explicitly equal to `false` ignoring case;
7. if no replacements remain and suppression is active:
   - suppress the entire rule match;
8. otherwise:
   - return the rule match with the filtered replacement list.

The production filter must use the native Task-0012 default speller.

Do not call Java.

## 14.1 Required filter cases

Cover with Java oracle evidence:

```text
all suggestions valid
one valid + one misspelled
all misspelled + suppressMatch=true
all misspelled + suppressMatch=false
SuppressPostag removes one candidate
SuppressPostag removes all candidates
mixed valid/misspelled/POS-suppressed candidates
multi-token suggestion where one token is misspelled
case-sensitive argument spelling behavior
non-BMP prefix preserving offsets
```

Use real Russian `grammar.xml` rules using this filter wherever available, not only synthetic mocks.

---

# 15. Default spelling rule integration

After Task 0012:

```text
Russian.getDefaultSpellingRule()
```

observable behavior must be represented by the native equivalent:

```text
MorfologikRussianSpellerRule
```

The Python `LanguageToolRU` pipeline must expose a stable internal/default-speller dependency used by:

```text
RussianSuppressMisspelledSuggestionsFilter
combined rule execution
public check()
```

Do not instantiate unrelated independent spellers per suggestion unless pinned behavior requires fresh state.

Avoid shared mutable state leaks across checks.

---

# 16. Promote Task-0012-deferred XML grammar rules

Current accepted compatibility accounting says:

```text
grammar deferred source rules total               114
grammar deferred_0012 source rules total          114
deferred examples total                           327
```

Task 0012 must re-run the structural inventory after implementing:

```text
RussianSuppressMisspelledSuggestionsFilter
+
native default spelling
```

First prove whether **all 114 source rules and 327 examples are deferred solely because of Task-0012 spelling/filter dependencies**.

If proven:

```text
grammar source rules total                        892
runnable source rules                             892
deferred source rules                               0

grammar examples total                           2446
runnable examples                                2446
deferred examples                                   0

compiled physical variants total                  907
runnable compiled variants                        907
```

become required Task-0012 acceptance counts.

If pinned reinspection proves another legitimate blocker:

- do not fake 892/892;
- identify every remaining blocker exactly;
- update deterministic accounting;
- report the exact rule IDs/examples;
- Task 0012 is BLOCKED until the discrepancy is either implemented within scope or explicitly proven outside scope.

No unexplained deferred rule may remain.

---

# 17. Full combined Russian rule pipeline

Extend the accepted Task-0011 combined execution surface to all 23 ordinary rules.

Preserve the accepted cleanup sequence and semantics:

```text
SameRuleGroupFilter
→ Russian language-dependent match filter
→ CleanOverlappingFilter
→ Russian post-overlap filter
```

Do not regress:

```text
priority handling
Tag.picky
UTF-16 span comparison
longest-span tie
last-match tie
duplicate adjacent suggestion behavior
punctuation-only correction preference
```

Add Task-0012 interactions to combined oracle coverage, especially:

```text
RU_COMPOUNDS priority 11 vs overlapping XML/other rule
spelling vs XML grammar overlap
simple-replace vs spelling
word-repeat vs spelling
default-off YO vs ordinary speller
default-off repetition rules
filter-suppressed XML match vs surviving spelling finding
```

Expected full-tool Java oracle runs should disable only:

```text
RussianConfusionProbabilityRule
```

or the exact language-model surface required to make the ordinary-rule comparison deterministic.

Do not continue disabling the eight Task-0012 rules after they are implemented.

---

# 18. Public configuration surface

Extend the existing `rule_config` mechanism only where pinned Task-0012 rules use `UserConfig`.

At minimum cover the spelling `conf_ru_Value`.

Inspect inherited `AbstractCompoundRule`/spelling classes for additional reachable config.

Requirements:

- use actual rule IDs in Python public config;
- reproduce Java constructor/runtime behavior;
- distinguish UI `RuleOption` bounds from runtime validation;
- query Java for out-of-range values rather than guessing;
- unknown configuration keys fail explicitly;
- config does not silently affect unrelated rules.

---

# 19. Upstream test inventory and translation

Inspect exact pinned tests for Task 0012.

Known direct tests include:

```text
MorfologikRussianSpellerRuleTest.java
MorfologikRussianYOSpellerRuleTest.java
RussianCompoundRuleTest.java
RussianSimpleReplaceRuleTest.java
RussianWordCoherencyRuleTest.java
RussianWordRepeatRuleTest.java
```

Current accepted inventory records no dedicated Russian test for:

```text
RussianSimpleWordRepeatRule
RussianWordRootRepeatRule
```

Confirm this against the pinned tree.

Also inspect relevant inherited/base tests for:

```text
MorfologikSpellerRule
SpellingCheckRule
AbstractCompoundRule
simple replace base
word repeat bases
AbstractSuppressMisspelledSuggestionsFilter
```

Report separately:

```text
upstream test files inventoried
@Test methods inspected
assertion/scenario count inspected
direct assertions translated
oracle-only controlled scenarios
rules without dedicated upstream tests
```

Do not claim "upstream test parity" based only on locally invented strings.

---

# 20. Trusted Java oracle extensions

Create deterministic Task-0012 evidence from the trusted pinned build:

```text
lt_6.8_source_build_jdk17_stefan
```

Recommended fixtures:

```text
tests/fixtures/oracle_java_rules_0012_spelling.json
tests/fixtures/oracle_java_rules_0012_rules.json
tests/fixtures/oracle_java_rules_0012_combined.json
```

A separate filter fixture is acceptable if it makes integrity clearer.

## 20.1 Spelling oracle

Must support at least:

```text
single-rule check
direct isMisspelled-style query where required
exact suggestions
exact suggestion order
config values
default state
```

## 20.2 Rule oracle

Cover the six non-spelling Task-0012 rule classes.

Each class needs:

```text
positive cases
negative cases
edge/boundary cases
multiple findings where possible
exact observable findings
```

## 20.3 Combined oracle

Run actual pinned:

```text
JLanguageTool.check(text)
```

with the Task-0012 ordinary rule surface active according to pinned defaults.

Compare ordered final findings.

Where cleanup is important, store raw/pre-overlap evidence just as Task 0011 does.

---

# 21. Required spelling oracle dimensions

The spelling corpus must cover, based on pinned behavior:

```text
correct Cyrillic word
misspelled Cyrillic word
multiple misspellings
sentence-start capitalization
title case
ALL CAPS
mixed case
ё vs е
combining acute
combining grave
modifier apostrophe
hyphenated form
digits
punctuation
non-Russian/Latin token with config=0
non-Russian/Latin token with config=1
mixed-script token
URLs/emails if handled by inherited ignore logic
dictionary spelling additions
ignore/prohibit resources if used
NOSUGGEST filtering
no-suggestion result
several suggestions and exact order
non-BMP character before an error
```

Do not mark a coverage label positive or negative before observing the Java result.

Use the accepted Task-0011 fail-closed coverage metadata rules.

---

# 22. Oracle fixture integrity

Continue the Task-0011 evidence discipline.

Semantic signatures must depend on the **query semantics**, not bookkeeping:

```text
execution mode
rule class
rule ID
input text
config
explicit enable/disable state
direct/raw query mode
other parameters that alter Java execution
```

Semantic signatures must not depend on:

```text
case ID
coverage labels
expected Java result
stored finding count
stored signature
```

Integrity tests must assert:

```text
case IDs unique
semantic signatures unique
positive => finding_count > 0
negative => finding_count == 0
positive and negative cannot coexist
multi_finding => finding_count > 1
finding_count == len(expected)
all expected rule IDs consistent with query mode
LF-only deterministic bytes
manifest size/hash exact
pinned commit exact
trusted oracle build exact
```

For spelling-specific direct queries, add equivalent consistency assertions.

Do not hand-edit expected Java output.

---

# 23. Observable finding parity

For every Task-0012 Java-rule finding compare all applicable fields:

```text
rule ID
category ID
category name
message
short message
suggestions
suggestion order
URL
UTF-16 from/to
Python codepoint from/to
source slice
priority/effective ordering
default-enabled state
source marker
```

For spelling, also prove:

```text
isMisspelled decision
suggestion filtering
suggestion ordering
```

Do not reduce parity to "same number of findings".

---

# 24. Resource integrity and provenance

Vendor/package every Task-0012 runtime resource actually required.

At minimum investigate:

```text
ru_RU.dict
ru_RU.info
ru_RU_yo.dict
ru_RU_yo.info
spelling.txt
compounds.txt
replace.txt
coherency.txt
wordrootrep.txt
```

Plus any transitive spelling resources discovered in the pinned base classes.

For each runtime resource:

```text
record upstream path
record pinned SHA/commit
record byte size
record SHA-256
preserve exact bytes where possible
verify runtime packaged copy against vendored source
verify wheel contains it
record license/provenance
```

Do not regenerate an equivalent-but-different dictionary unless the pinned runtime itself requires a build step and the output is proven byte/semantic equivalent.

---

# 25. Wheel isolation proof

Extend the real installed-wheel test.

Build and install the actual wheel into an isolated directory/environment.

Remove repository source paths.

Remove or invalidate:

```text
JAVA_HOME
Java executable assumptions
LanguageTool checkout assumptions
```

Block/deny:

```text
subprocess execution
socket/network access
runtime downloads
localhost services
```

From the installed wheel verify at least:

```text
ordinary Russian spelling error + exact suggestion surface
correct spelling no finding
YO speller when explicitly enabled
RU_COMPOUNDS
RU_SIMPLE_REPLACE
one repetition/coherency rule
XML grammar rule using RussianSuppressMisspelledSuggestionsFilter
existing Task-0011 Java rule
existing XML grammar rule
```

Production must remain self-contained.

---

# 26. Performance and memory requirements

The spelling implementation must not introduce pathological behavior.

At minimum add deterministic performance sanity coverage for:

```text
repeated spelling checks
long paragraph with many correct words
multiple misspellings
suggestion generation
```

Requirements:

```text
dictionary/FSA loaded once or cached safely
no full dictionary scan per checked token
no unbounded cache growth
no subprocess/network fallback
thread-safe or immutable shared resource state
```

Do not optimize by changing observable suggestion semantics.

Correctness wins over micro-optimization, but obvious O(N dictionary) per token is not acceptable.

---

# 27. Grammar/example parity after filter promotion

After promotion, run the full pinned Russian grammar example suite.

If all 114 deferred source rules become runnable, require:

```text
source rule parity: 892 / 892
example parity:    2446 / 2446
```

For every incorrect example:

```text
trigger behavior must match pinned Java
full observable finding parity where the existing framework compares it
```

For every correct example:

```text
no false positive relative to pinned Java
```

Do not simply remove the defer marker and count the rule as runnable.

Execution must be proven.

---

# 28. Update deterministic compatibility accounting

Update:

```text
compat/compatibility.json
compat/russian_java_rules_inventory.json
compat/oracle_manifest.json
```

Expected successful state, if the deferred XML blocker proof confirms current accounting:

```text
task_milestone: 0012_...

ordinary relevant Java rules:
  23 / 23 implemented

Russian-specific:
  13 / 13 implemented

generic:
  10 / 10 implemented

XML filters:
  7 / 7 implemented

Task-0012 deferred ordinary Java rules:
  0

grammar source rules:
  892 total
  892 runnable
  0 deferred

grammar examples:
  2446 total
  2446 runnable
  0 deferred

compiled variants:
  907 total
  907 runnable

language-model:
  0 / 1
  RussianConfusionProbabilityRule = LANGUAGE_MODEL_DEFERRED
```

If exact source reinspection changes one of these expected counts, document and prove why.

No unexplained `UNKNOWN`, `PARTIAL`, or stale Task-0012 deferred status may remain.

---

# 29. Regression requirements

Do not weaken or delete existing accepted tests to make Task 0012 pass.

All Task-0011 evidence must remain green, including:

```text
126 single-rule cases
11 combined cases
137 unique Task-0011 semantic signatures
match cleanup parity
config parity
wheel isolation
zero-skip gate
```

Task 0012 may extend shared infrastructure, but any regression in prior accepted behavior is a task failure.

---

# 30. Required focused tests

Add focused tests for at least:

```text
Task-0012 inventory/accounting
Morfologik spelling dictionary lookup
isMisspelled behavior
suggestion generation/order
NOSUGGEST filtering
speller UserConfig
YO speller default-off/explicit enable
compound behavior
replace behavior
simple word repeat
coherency
word repeat
word-root repeat
SuppressMisspelledSuggestionsFilter
filter + default speller
Task-0012 oracle fixture integrity
Task-0012 single-rule parity
Task-0012 combined parity
deferred XML promotion accounting
full grammar examples
resource hashes
wheel isolation
```

All focused tests:

```text
failed  = 0
errors  = 0
skipped = 0
```

No `xfail` as a substitute for completion.

---

# 31. Full regression

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

The pass count is expected to exceed the Task-0011 baseline of 513.

Do not hard-code a target count merely to make reporting pretty.

---

# 32. CI requirements

Commit and push the final Task-0012 implementation to `main`.

GitHub Actions must run on the exact final SHA.

Required matrix:

```text
Python 3.10
Python 3.12
```

For both jobs verify from logs:

```text
git rev-parse HEAD == GITHUB_SHA == FINAL_SHA
```

And:

```text
<passed> passed / 0 failed / 0 errors / 0 skipped
```

The workflow conclusion must be:

```text
success
```

Do not create a documentation-only commit after the verified SHA merely to write the CI run ID into a report.

The final handoff may record the CI run ID outside the repository.

---

# 33. Required report

Create:

```text
reports/0012_russian_spelling_compounds_replace_repeats.md
```

The report must include:

```text
baseline SHA
final implementation SHA
pinned LT SHA
rule inventory/accounting
effective priority table
default-state table
spelling architecture
transitive resource list + hashes
spelling config semantics
NOSUGGEST behavior
YO behavior
compound behavior
replace behavior
repeat/coherency behavior
final XML filter behavior
XML promotion accounting
upstream tests inspected/translated
oracle fixture counts
semantic-signature counts
grammar/example parity
wheel isolation result
full pytest result
known differences
language-model deferred status
```

Do not claim parity for an untested surface.

---

# 34. Licensing/provenance

Update licensing/provenance records for all newly vendored:

```text
Java source
test source
dictionary resources
text resources
Morfologik-derived behavior/data
```

Preserve LGPL/source attribution requirements already established by the project.

Do not silently copy third-party spell resources without provenance.

---

# 35. Definition of Done

Task 0012 is complete only if all of the following are true:

1. Exactly 8 remaining ordinary Java rules are implemented natively.
2. Ordinary relevant Java rules are 23/23.
3. Russian-specific Java rules are 13/13.
4. Generic Java rules remain 10/10.
5. `RussianSuppressMisspelledSuggestionsFilter` is implemented.
6. Russian XML filters are 7/7.
7. Default Russian native speller is available to XML filters.
8. Spelling uses pinned-compatible Morfologik semantics, not a toy substitute.
9. Suggestion order/filtering is Java-oracle verified.
10. YO speller semantics/default-off state are verified.
11. `RU_COMPOUNDS` preserves effective priority 11.
12. Orphan priority-key mismatches remain faithfully represented.
13. All six non-spelling Task-0012 rules have positive/negative oracle coverage.
14. Rules without dedicated upstream tests are explicitly identified and oracle-covered.
15. Task-0012 oracle semantic queries are unique.
16. Coverage metadata is fail-closed and consistent with Java results.
17. All required resources are packaged and hash-bound.
18. Real installed wheel executes spelling and final XML filter with no Java/network/subprocess fallback.
19. The 114 Task-0012-deferred XML source rules are fully reconciled.
20. If current blocker accounting is confirmed, grammar rules are 892/892 runnable.
21. If current blocker accounting is confirmed, examples are 2446/2446 runnable.
22. If current blocker accounting is confirmed, compiled variants are 907/907 runnable.
23. All prior Task-0011 oracle/combined tests remain green.
24. Full pytest has 0 failed, 0 errors, 0 skipped.
25. Exact final SHA CI passes on Python 3.10 and 3.12.
26. `RussianConfusionProbabilityRule` remains explicitly deferred 0/1.
27. No Task 0013 work is started.

---

# 36. Final handoff format

The final response after implementation must contain concrete values:

```text
Task 0012 final verification

baseline:
663ca3e222d694b92074f0b87da86c5e566f4bd4

final main SHA:
<SHA>

implementation commit:
<SHA>

Pinned LT:
e807fcde6a6506191e1470744d2345da28c26be6

Ordinary Java rules:
23 / 23

Russian-specific:
13 / 13

Generic:
10 / 10

Task-0012 rules:
8 / 8

XML filters:
7 / 7

RussianSuppressMisspelledSuggestionsFilter:
PASS/FAIL

Default native speller:
PASS/FAIL

Spelling oracle:
<count>/<count>

Other Task-0012 single-rule oracle:
<count>/<count>

Combined oracle:
<count>/<count>

Semantic signatures:
<count>/<count> unique

Upstream test files inspected:
<count>

Upstream scenarios/assertions represented:
<count>

Grammar source rules:
<runnable>/<total>
<deferred> deferred

Grammar examples:
<runnable>/<total>
<deferred> deferred

Compiled variants:
<runnable>/<total>

Wheel isolation:
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

Language-model rule:
0 / 1
RussianConfusionProbabilityRule = LANGUAGE_MODEL_DEFERRED

Known differences:
<none or exact list>

FINAL:
READY FOR REVIEW
```

If any required parity surface is not complete:

```text
FINAL:
BLOCKED
```

with the exact blocker and evidence.

After this response, stop.

Do not start Task 0013.
