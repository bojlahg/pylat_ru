# Handoff — `pylat_ru`

## 1. Project purpose

`pylat_ru` is a standalone Python library whose goal is to reimplement the Russian LanguageTool pipeline in native Python so that Russian checking does not require Java/JRE, LanguageTool Server, Natasha, pymorphy, or another external NLP runtime.

This is **not** a Python wrapper around LanguageTool and not an HTTP client.

Target pipeline:

```text
text
 ↓
RussianSentenceTokenizer
 ↓
RussianWordTokenizer
 ↓
RussianTagger
 ↓
RussianDisambiguator
 ↓
RussianChunker
 ↓
RussianRuleEngine
 ├─ grammar.xml
 ├─ XML filters → Python
 ├─ Java rules → Python
 ├─ spelling
 ├─ compounds
 ├─ replace/coherency
 └─ repetitions
 ↓
RussianSynthesizer
 ↓
findings
 ├─ rule_id
 ├─ category
 ├─ message
 ├─ offset
 ├─ length
 └─ suggestions
```

The main goal is **maximum compatibility with Russian LanguageTool at one pinned upstream revision**.

Repository/package/import name:

```text
repository: pylat_ru
package:    pylat_ru
import:     import pylat_ru
```

README must state:

> `pylat_ru` is an independent project and is not affiliated with or endorsed by LanguageTool.

## 2. Hard architecture decisions

### No Natasha / pymorphy replacement

Russian LanguageTool rules are written against LT's own tokenizer, morphological dictionary, tagset, disambiguator and synthesizer. Replacing that pipeline with Natasha/pymorphy would make parity failures originate in different morphology instead of the rule engine.

Goal: reproducible Python-native LT-compatible behavior, not merely similar Russian checking.

### No Java in production

Production API must not:

- start JRE;
- invoke LT CLI;
- talk to LT Server/localhost;
- use Java subprocesses;
- download LanguageTool during `check()`.

A separate dev/test oracle may use the official pinned Java LanguageTool only for differential/conformance testing. Production import must work without Java.

### Russian only for now

Do not build a speculative multilingual framework. Generalize only where naturally useful. A second real language can justify a later abstraction.

## 3. Upstream data strategy

Whenever practical, execute the original upstream Russian resources instead of manually rewriting thousands of rules into Python.

Important Russian rule files include, subject to verification against the pinned revision:

```text
rules/ru/
  grammar.xml
  wordrootrep.txt
  replace.txt
  coherency.txt
  bitext.xml
```

Important Russian linguistic resources include, again subject to exact pinned inventory:

```text
resource/ru/
  added.txt
  added_custom.txt
  removed.txt
  removed_custom.txt
  common_words.txt
  compounds.txt
  confusion_sets.txt
  multiwords.txt
  specific_case.txt
  disambiguation.xml
  tags_russian.txt
  tagset.txt
  russian.dict
  russian.info
  russian_synth.dict
  russian_synth.info
  russian_manual_add.txt
  hunspell/...
```

The task handoff lists are leads, **not final source-of-truth**. Task 0001 must derive the actual compatibility surface from the pinned LanguageTool revision.

## 4. Morphology/tagger/synthesis requirements

### `russian.dict`

Python must read/use native LT Russian morphological/tagger data and expose analyses equivalent in semantics to LT:

```text
surface
lemma
LT POS tag
morphological features
```

A token may have multiple analyses. Output must preserve LT tag semantics because `grammar.xml` matches those POS strings.

### `tags_russian.txt` / `tagset.txt`

Use as source-of-truth for LT Russian POS/tag semantics. Document tag grammar, create typed representations, and later test round-trip/matching behavior.

### `disambiguation.xml`

Implement Python-native Russian disambiguation. Actual supported constructs/actions must be derived from pinned upstream inventory, not guessed. Unknown constructs cannot be silently ignored.

### `russian_synth.dict`

Needed for lemma + target LT POS/morphology → correct word form, including suggestion generation and filters.

### compounds/spelling

Port relevant Russian compound and spelling behavior using upstream resources. A Python-native helper library is acceptable only if it reproduces required semantics and passes parity tests; it must not quietly substitute a different language model.

## 5. Java logic that requires functional ports

Not all Russian behavior lives in XML. `Russian.java` enables Russian-specific and generic rules. Examples seen during initial investigation include:

```text
MorfologikRussianSpellerRule
MorfologikRussianYOSpellerRule
RussianCompoundRule
RussianSimpleReplaceRule
RussianSimpleWordRepeatRule
RussianWordCoherencyRule
RussianWordRepeatRule
RussianWordRootRepeatRule
RussianVerbConjugationRule
RussianDashRule
RussianSpecificCaseRule
RussianFillerWordsRule
RussianUnpairedBracketsRule
```

Relevant generic rules may include whitespace, sentence start, long sentence/paragraph and repetition rules.

**Exact list must be extracted from pinned upstream `Russian.java`/registration logic.**

## 6. XML engine

Implement the complete subset actually used by pinned Russian LanguageTool, not an arbitrary hand-picked subset.

Expected examples include:

```text
token text
regexp
case_sensitive
postag
postag_regexp
inflected
min/max/skip
exception / scope
negate_pos
marker
match / regexp_match / regexp_replace
include_skipped
suggestion
antipattern
unify / unify-ignore / feature / negate
filter
```

Actual inventory wins.

Project rule:

> unknown XML element/attribute = explicit unsupported compatibility error, never silent ignore.

## 7. Java-specific XML filters

`grammar.xml` can call Java filter classes. Initial examples include `DateCheckFilter`, `FutureDateFilter`, `INNNumberFilter`, `AdvancedSynthesizerFilter`, and Russian spelling-suggestion filters.

Required workflow:

1. extract full `<filter class="...">` set automatically;
2. locate pinned upstream implementation;
3. create Python equivalent in later tasks;
4. port relevant upstream tests;
5. compare findings/spans/suggestions.

Unknown filters must remain explicit compatibility gaps.

## 8. Upstream tests are the primary asset

Do not invent a small bespoke test suite instead of upstream conformance.

Use/translate:

- Russian JUnit tests;
- `grammar.xml` examples;
- disambiguation tests;
- spelling tests;
- rule-specific tests.

`RussianPatternRuleTest` effectively executes examples embedded in `grammar.xml`, making them a major ready-made test corpus.

Conformance should eventually compare:

```text
rule_id
category
finding existence/count
offset
length
message
suggestions
default enabled/disabled behavior
```

An optional differential oracle runs the same text through official pinned Java LT RU and `pylat_ru`, then emits structured diffs.

## 9. Compatibility reporting

Project completion cannot be declared with prose like "Russian LanguageTool port implemented".

Maintain machine-readable status covering at least:

```text
upstream revision
Russian rule count
XML constructs: supported / unsupported / partial
filters: implemented / total
Java rules: implemented / total
upstream tests: pass / fail / skipped
grammar.xml examples: pass / fail
finding parity
span parity
suggestion parity
known differences
```

Metrics must reflect reality, including zeros/not-yet-implemented states.

## 10. Upstream pinning and drift

Never use floating `master`/`main` as the compatibility target.

Maintain:

```text
third_party/languagetool/
  UPSTREAM.json
  LICENSES.md
```

`UPSTREAM.json` should record repository, exact commit SHA, retrieval date, resource paths and SHA-256 hashes for every vendored upstream file.

Provide a drift detector capable of reporting:

- added/removed/changed rules/resources;
- new XML elements/attributes;
- filter changes;
- Russian enabled-rule-set changes;
- dictionary changes;
- test inventory changes.

No automatic upstream upgrades. Updating the pin is a controlled operation followed by conformance testing.

## 11. Licensing

Working project license: `LGPL-2.1-or-later`, subject to concrete license inventory.

Initial upstream investigation indicates Russian dictionary material and Hunspell Russian resources identify LGPL licensing, but **do not assume every file in the tree has the same license**.

Before mass vendoring, maintain inventory fields equivalent to:

```text
path
upstream origin
copyright
license
included?
status
notes
```

If provenance/license is unclear:

```text
BLOCKED_LICENSE_REVIEW
```

Do not guess and do not silently copy.

## 12. Public API target

Eventually the minimal API should resemble:

```python
from pylat_ru import LanguageToolRU

tool = LanguageToolRU()
matches = tool.check("Текст для проверки.")
```

Conceptual finding fields:

```text
rule_id
category_id
message
short_message
offset
length
replacements
context
context_offset
source
```

Do not expand public API prematurely before core parity.

## 13. Performance principle

Parity first, profiling second.

Architecturally avoid obvious waste:

- dictionaries loaded once per long-lived instance/runtime;
- regex/rules compiled once;
- XML not reparsed for each `check()`;
- avoid millions of heavyweight Python objects for dictionary entries if a compact representation works.

## 14. Out of scope

Do not put TextQA concerns into this library:

```text
AI detector
neural GEC models
SAGE/Qwen/Gemma/RuCoLA
humanizer
character voice
continuity
browser UI
benchmark UI
```

`pylat_ru` is a rule-based Russian linguistic QA library; TextQA may consume it later as a normal Python dependency.

## 15. Recommended roadmap

```text
0001 Project Foundation + Upstream Inventory + Licensing + Tests
0002 Dictionary formats + LT Russian tagset
0003 Russian tokenization
0004 Russian tagger
0005 Russian disambiguator
0006 Russian synthesizer
0007 XML grammar engine core
0008 Advanced matching
0009 Unification
0010 XML filters
0011 Russian Java rules
0012 Spelling / compounds / replace / repetitions
0013 Complete upstream Russian test parity
0014 Differential corpus
0015 Packaging / performance / release
```

Task 0001 intentionally does **not** implement the grammar engine. It first establishes exactly what pinned Russian LanguageTool does, which assets it uses, which tests exist, and which licenses/provenance apply.

## 16. Task workflow

Use:

```text
tasks/
reports/
```

Each numbered task follows:

```text
implement
→ focused tests
→ completion report
→ git diff review
→ commit
→ push current branch to origin
→ verify remote commit
```

Push the completed task commit automatically after a successful commit. If push fails, report the exact error and do not claim the task is complete. Never force-push or rewrite published history. Do not automatically start the next numbered task.

## 17. Definition of Done for the overall project

`pylat_ru` is a full Russian Python LanguageTool-compatible port only when:

1. production requires no Java/JRE;
2. production uses no LT server;
3. Natasha/pymorphy are not semantic replacements for LT Russian pipeline;
4. tokenizer preserves correct source offsets;
5. tagger reproduces LT-compatible analyses;
6. Russian disambiguation works;
7. Russian synthesis works;
8. all XML constructs used by pinned Russian `grammar.xml` are supported;
9. all Russian XML filters are ported;
10. all enabled Russian-specific Java rules are ported;
11. all relevant shared rules are ported;
12. spelling/compound/repetition layers work;
13. relevant upstream Russian tests pass;
14. `grammar.xml` examples pass;
15. no rules/features are silently skipped;
16. differential testing has no substantial unexplained discrepancies;
17. every vendored upstream asset has verified license/provenance;
18. compatibility report is reproducible;
19. API behaves like a normal Python library;
20. TextQA can consume it without knowing implementation details.

## 18. Key principle

Do not optimize the goal down to:

```text
make a good Russian grammar checker
```

Keep the goal:

```text
make a Python-native Russian LanguageTool-compatible implementation
```

That compatibility is what provides a large existing rule base, upstream tests, comparable behavior, controlled updates, and an objective definition of progress.