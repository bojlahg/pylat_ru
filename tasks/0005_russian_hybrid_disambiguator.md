# Task 0005 — Russian Hybrid Disambiguator Parity (`MultiWordChunker` + `disambiguation.xml`)

## Status

READY

## Goal

Implement the next native Python stage of the pinned LanguageTool Russian pipeline: the **Russian hybrid disambiguator**.

The required observable pipeline for this task is:

```text
sentence text
  ↓
RussianWordTokenizer                         ✅ Task 0003
  ↓
JLanguageTool-compatible raw sentence assembly
  ├─ ignored-character cleaning
  ├─ RussianTagger                           ✅ Task 0004
  ├─ whitespace tokens
  ├─ SENT_START
  ├─ SENT_END
  └─ exact token-position mapping
  ↓
MultiWordChunker(/ru/multiwords.txt)
  ↓
XmlRuleDisambiguator(/ru/disambiguation.xml)
  ↓
RussianHybridDisambiguator-compatible sentence
```

Task 0005 must reproduce the observable behavior of pinned LanguageTool `v6.8` Russian disambiguation without Java at production runtime.

This is **not** a generic statistical or neural disambiguator. It is a native implementation of the exact deterministic LanguageTool pipeline and resources pinned by this repository.

---

# Pinned compatibility target

The compatibility pin remains unchanged:

```text
LanguageTool tag:    v6.8
LanguageTool commit: e807fcde6a6506191e1470744d2345da28c26be6
Morfologik version:  2.1.9
```

Do not update the LanguageTool pin in Task 0005.

Relevant pinned Russian assets already vendored in the repository include:

```text
RussianHybridDisambiguator.java
Russian.java
NoDisambiguationRussianPartialPosTagFilter.java
RussianChunker.java                         # reference only; explicitly OUT OF SCOPE here

resource/ru/disambiguation.xml
resource/ru/multiwords.txt
```

Pinned `UPSTREAM.json` currently records at least:

```text
RussianHybridDisambiguator.java
  size:   2678
  sha256: ab89fc3b2253bdfeb643f5f432e975933e19d905e4086c996ce9fb6e5db84e4c

disambiguation.xml
  size:   47039
  sha256: 088da5e49938e7f4b1251e4de29de059822ab7e9fc299b07fbeca970b73d0f18

multiwords.txt
  size:   5289
  sha256: b802c6c9cb5a251348f0b392e4167c5e12543a44b04f3ce616e4253bc8af4e06

NoDisambiguationRussianPartialPosTagFilter.java
  size:   1851
  sha256: 19e2dce954f1241f59e63809a18aff463a7f02adff7f2324ac2cb6d1729f50e0
```

If repository metadata differs, use the **current pinned `UPSTREAM.json`** as source of truth. Do not silently change the upstream pin.

The Task 0001 compatibility inventory reported the Russian disambiguation XML baseline as:

```text
rule groups: 11
rules:       77
```

These values are an expected baseline only. Task 0005 must independently derive and verify the active XML inventory from the pinned file rather than hardcoding them.

---

# Verified upstream architecture

Pinned `Russian.java` returns:

```text
createDefaultDisambiguator()
→ RussianHybridDisambiguator.getInstance()
```

Pinned `RussianHybridDisambiguator` performs exactly:

```text
return disambiguator.disambiguate(
    chunker.disambiguate(input)
)
```

where:

```text
chunker       = MultiWordChunker.getInstance("/ru/multiwords.txt")
disambiguator = new XmlRuleDisambiguator(Russian.getInstance())
```

`XmlRuleDisambiguator(Russian)` loads:

```text
ru/disambiguation.xml
```

and **does not load `disambiguation-global.xml` by default**.

The order is mandatory:

```text
raw sentence
→ MultiWordChunker
→ XML rules in upstream rule order
```

Do not reverse these stages and do not run XML rules against a sentence that has not received multiword readings.

## Critical scope boundary: `RussianChunker` is NOT part of RussianHybridDisambiguator

Pinned `Russian.java` separately declares:

```text
createDefaultPostDisambiguationChunker()
→ new RussianChunker()
```

`JLanguageTool.getAnalyzedSentence()` applies that post-disambiguation chunker **after** the language disambiguator.

Therefore:

```text
MultiWordChunker        ✅ Task 0005
XmlRuleDisambiguator    ✅ Task 0005
RussianHybridDisambiguator ✅ Task 0005
RussianChunker          ⛔ NOT Task 0005
```

Do not mark `RussianChunker` supported merely because `MultiWordChunker` is implemented.

---

# Mandatory project constraints

Read and obey:

```text
AGENTS.md
docs/Handoff_pylat_ru.md
reports/0002_dictionary_formats_lt_russian_tagset.md
reports/0003_russian_sentence_word_tokenization_offsets.md
reports/0004_russian_tagger.md
compat/compatibility.json
compat/oracle_manifest.json
compat/russian_tagger_inventory.json
```

In particular:

- production Python must not invoke Java/JRE, LanguageTool Server, network services, or external NLP runtimes;
- Java is permitted only as a development/conformance oracle;
- exact pinned LT behavior is more important than linguistic improvements;
- do not replace deterministic LT disambiguation with pymorphy/Natasha/Stanza/spaCy/neural models;
- preserve exact raw POS strings and reading order;
- preserve whitespace and position semantics needed by downstream grammar rules;
- unknown XML elements/attributes/actions/filter classes that affect behavior must fail explicitly;
- no silent rule skipping;
- no silent regex downgrade;
- parse/compile resources once per long-lived disambiguator, not once per sentence or token;
- do not start Task 0006 automatically.

---

# Scope

## In scope

1. Minimal `AnalyzedSentence`-compatible Python data model needed by LT pattern matching.
2. JLanguageTool-compatible **raw sentence assembly** for Russian.
3. Exact handling of Russian ignored characters relevant to raw analysis.
4. `SENT_START` and `SENT_END` semantics.
5. Whitespace tokens and non-whitespace-to-original index mapping.
6. `MultiWordChunker` behavior required by pinned `multiwords.txt`.
7. Native parser for pinned `disambiguation.xml`.
8. Native pattern matcher for the XML features actually used by pinned Russian disambiguation rules.
9. Active disambiguation actions actually used by pinned Russian XML.
10. Antipattern behavior used by pinned XML.
11. The pinned Russian `NoDisambiguationRussianPartialPosTagFilter` behavior.
12. `IGNORE_SPELLING` token state because pinned disambiguation XML uses it.
13. Full `RussianHybridDisambiguator` stage ordering.
14. Development-only fail-closed Java oracle fixtures for raw/multiword/final disambiguation output.
15. Deterministic feature/resource inventory.
16. Package-safe runtime copies of `multiwords.txt` and `disambiguation.xml`.
17. Wheel/install smoke verification including the new resources.

## Explicitly out of scope

Do **not** implement in Task 0005:

- `RussianChunker` post-disambiguation chunker;
- `RussianSynthesizer` as a public synthesis stage;
- grammar.xml checking;
- spelling rules;
- compound/replacement/coherency/repetition Java rules;
- generic XML grammar rule messages/suggestions;
- `LanguageToolRU.check()`;
- `disambiguation-global.xml`;
- unused disambiguator action families merely because core LT supports them;
- full multilingual PatternRule compatibility;
- speculative optimization frameworks.

Small reusable pattern primitives are allowed when they are faithful translations needed by the pinned Russian XML and will be useful later for grammar.xml.

---

# Phase 0 — Inventory before implementation

Before writing the matcher, deterministically inspect the **actual pinned active XML** and produce a feature inventory.

Create a tool such as:

```text
tools/russian_disambiguation_inventory.py
```

and a committed artifact:

```text
compat/russian_disambiguation_inventory.json
```

The inventory must derive, not hardcode, at least:

```text
pinned LT tag/commit
RussianHybridDisambiguator.java path/hash/size
disambiguation.xml path/hash/size
multiwords.txt path/hash/size
NoDisambiguationRussianPartialPosTagFilter.java path/hash/size

active rule count
active rulegroup count
rule IDs/full IDs/source order
active example counts by type

XML element names actually used
all token attributes actually used
all exception attributes/scopes actually used
all pattern attributes actually used
all disambig actions actually used
default-action count
all <match> attributes actually used
all <wd> attributes actually used
all skip values actually used
and/or/unification feature usage
antipattern count
marker usage count
filter class names and argument-key inventory
regexp usage counts
postag regexp usage counts
inflected usage counts
negate/negate_pos usage counts
case_sensitive usage counts

multiwords parsed-entry count
multiwords distinct phrase count
duplicate phrase behavior
multiwords POS-tag inventory
maximum phrase token count
whether single-token/no-space entries exist
```

The inspected pinned v6.8 file is expected to use at least these action families:

```text
ADD
REMOVE
REPLACE        # including default <disambig> behavior
IGNORE_SPELLING
```

and the filter class:

```text
org.languagetool.rules.ru.NoDisambiguationRussianPartialPosTagFilter
```

The pinned XML also visibly uses constructs including:

```text
rule / rulegroup
pattern
marker
antipattern
token
and
exception
wd
match
filter

regexp
postag
postag_regexp
case_sensitive
inflected
negate
negate_pos
skip
exception scope="next"
```

The inventory is authoritative. If additional active behavior is found, either implement it exactly in Task 0005 or stop with an explicit compatibility blocker. Never silently ignore it because it was omitted from this prose list.

The committed inventory must have deterministic complete regeneration tests, byte-for-byte after canonical serialization.

---

# 1. Raw analyzed-sentence assembly

Task 0004 intentionally implemented direct `RussianTagger` parity but did not assemble the full LT sentence object required by disambiguation.

Task 0005 must add this boundary.

A sensible public/internal API may look conceptually like:

```python
raw = RussianSentenceAnalyzer().analyze_raw(sentence_text)
result = RussianHybridDisambiguator().disambiguate(raw)
```

Exact names may improve.

## 1.1 Word tokenization

Use the Task 0003 Russian word tokenizer. Preserve every token required to reconstruct the sentence, including whitespace tokens.

Do not perform the `TestTools` shortcut that removes whitespace before tagging; the real `JLanguageTool.getRawAnalyzedSentence()` pipeline retains whitespace tokens in the analyzed sentence.

## 1.2 Russian ignored-character preprocessing

Pinned `Russian.getIgnoredCharactersRegex()` is:

```text
[\u00AD\u0301\u0300]
```

Thus before tagging, full JLanguageTool raw analysis removes:

```text
U+00AD SOFT HYPHEN
U+0301 COMBINING ACUTE ACCENT
U+0300 COMBINING GRAVE ACCENT
```

from affected word-token strings.

This happens **before** `RussianTagger.tag(tokens)` in `JLanguageTool.getRawAnalyzedSentence()`.

After tagging, LT restores source-surface information through the equivalent of `CleanToken`/additional null reading/position-fix metadata.

This is different from calling `RussianTagger.tag_word()` directly, where Task 0004 correctly exposed RussianTagger's own normalization behavior.

The full sentence layer must therefore distinguish:

```text
source token surface
clean token used for morphology
current analyzed-token surface
source/code-point span
Java-compatible UTF-16 start position
position fix caused by removed ignored characters
```

Do not collapse these concepts into one string or one offset.

### Required parity proof

Include at least:

- combining acute inside a Russian word;
- combining grave;
- soft hyphen;
- emoji before/after affected tokens;
- whitespace around affected tokens.

Compare the raw Java analyzed sentence, not merely Python slicing.

## 1.3 `SENT_START`

Raw LT sentence assembly prepends one artificial reading container:

```text
token:   ""
pos_tag: "SENT_START"
lemma:   None
start:   0
```

It remains present in `getTokensWithoutWhitespace()`.

Pattern matching must be able to match/exclude it by POS tag.

## 1.4 `SENT_END`

LT does not create a separate visible word token for sentence end. It adds a `SENT_END` reading to the **last non-whitespace token**.

Preserve this behavior, including the original token's existing readings.

A disambiguation action that replaces/removes ordinary readings must not accidentally destroy the special sentence-end state. Port the relevant preservation semantics of `AnalyzedTokenReadings` transformations.

## 1.5 Whitespace tokens and mapping

Implement an `AnalyzedSentence`-equivalent that preserves:

```text
full tokens including whitespace + SENT_START
non-whitespace tokens including SENT_START / SENT_END-bearing token
mapping: non-whitespace position -> full-token position
pre-disambiguation view/snapshot needed downstream
```

Conceptually expose equivalents of:

```text
getTokens()
getTokensWithoutWhitespace()
getOriginalPosition(nonWhitespaceIndex)
getText()
```

Exact API naming may be Pythonic.

The mapping must be deterministic and parity-tested with:

- single spaces;
- multiple spaces;
- tabs;
- line breaks;
- punctuation adjacent to words.

Do not reconstruct positions by searching token strings after the fact.

---

# 2. Extend the analyzed-token/readings data model safely

Task 0004 introduced immutable morphology objects. Extend them only as necessary for the LT disambiguation surface.

At minimum the readings container must be able to represent/preserve:

```text
readings
token surface
start_pos_utf16
chunk tags
whitespace status
linebreak status
whitespace-before state
sentence-start state
sentence-end state
clean token / position fix where relevant
ignored-by-speller state
immunized state if needed by actual active features
historical/source annotation if implemented for debugging
```

The implementation may remain immutable and return modified copies rather than reproduce Java mutation internally. Observable results must match LT.

### Reading mutation semantics

Implement helpers equivalent to the relevant LT operations, with explicit tests:

```text
addReading
removeReading
replace readings while preserving token metadata
setSentEnd
ignoreSpelling
```

Important LT behavior:

- adding a reading appends without general deduplication;
- removing a reading removes matching readings;
- if removal would leave zero readings, LT creates a single null reading for the token;
- `SENT_END`/paragraph/chunk/ignored-spelling metadata is preserved across replacement constructors as upstream does;
- special sentinel readings must not be casually discarded by morphology filtering.

Do not mutate shared tuple/list instances across sentence snapshots.

---

# 3. MultiWordChunker parity

Implement the behavior used by:

```java
MultiWordChunker.getInstance("/ru/multiwords.txt")
```

For Russian this uses default settings:

```text
allowFirstCapitalized = false
allowAllUppercase     = false
allowTitlecase        = false
defaultTag            = null
```

Therefore case variants must **not** be invented automatically. The Russian resource already contains explicit variants where desired.

## 3.1 Resource parsing

Port the relevant `MultiWordChunker.loadWords()` semantics for the pinned resource:

- UTF-8;
- default separator is tab;
- `#separatorRegExp=` support if the inventory shows/permits it;
- trim lines as upstream does;
- ignore empty/comment lines;
- strip inline comments;
- require the expected phrase/tag structure;
- preserve deterministic resource order/overwrite behavior;
- malformed resources fail explicitly with source/line context.

Do not accidentally reuse `ManualTagger` semantics where upstream `MultiWordChunker` differs.

## 3.2 Matching semantics

Port the Russian-relevant behavior of pinned `MultiWordChunker`, including:

- maximum multiword traversal bound equivalent to `MAX_TOKENS_IN_MULTIWORD = 20`;
- whitespace-aware matching;
- handling of multiple whitespace tokens as upstream does;
- phrase matching in full analyzed token sequence;
- deterministic selection when prefixes/longer entries overlap;
- no automatic Russian case folding beyond the configured settings;
- no removal of existing morphology for the Russian default configuration.

## 3.3 Added readings

For a multi-token phrase such as a phrase tagged `ADV`, reproduce LT's boundary readings:

```text
first token: <ADV>
last token:  </ADV>
lemma:       original multiword phrase
```

with existing morphology preserved and the new reading appended according to LT behavior.

For any actual single-token/no-space entries in the pinned inventory, reproduce their upstream handling as well.

### Mandatory real-resource proofs

Use at least several pinned phrases spanning phrase lengths and tags, for example candidates from the actual resource such as:

```text
в будущем
до свидания
во что бы ни стало
откуда ни возьмись
затаив дыхание
```

Use the inventory and Java oracle to select exact cases; do not assume examples above cover every resource behavior.

---

# 4. Native `disambiguation.xml` loader

Implement a deterministic parser for the pinned Russian disambiguation XML.

Prefer Python standard-library XML parsing unless a dependency is demonstrably needed. Do not introduce a heavyweight XML stack merely to read a 47 KB pinned resource.

The loader must:

- preserve active rule source order;
- preserve rulegroup/subrule order;
- preserve IDs/names/full IDs needed for diagnostics;
- parse marker boundaries;
- parse antipatterns;
- parse token/and/exception structures;
- parse disambig action/default action;
- parse `wd` and `match` constructs actually used;
- parse the exact filter class/args actually used;
- compile regexes once at load time;
- reject malformed XML and behaviorally unsupported constructs explicitly;
- never ignore an unknown active tag/attribute/action/filter with a warning-only path.

Comments and examples are not runtime rules, but inventory/test tooling should account for them deterministically.

Do not load `disambiguation-global.xml`.

---

# 5. Pattern matching semantics required by Russian disambiguation

Implement only the pattern-language subset required by the pinned active Russian XML, but implement that subset **exactly**.

A shared internal package such as:

```text
src/pylat_ru/patterns/
```

is acceptable if it remains focused and reusable for later grammar.xml work.

## 5.1 Non-whitespace pattern domain

XML pattern matching operates on `AnalyzedSentence.getTokensWithoutWhitespace()`.

This sequence excludes ordinary whitespace but includes artificial/special sentence markers as LT does.

Every action must then map matched non-whitespace positions back to the full token array through `getOriginalPosition()`-equivalent mapping before modifying output.

## 5.2 Token string matching

Reproduce `PatternToken` / `StringMatcher` semantics required by the Russian file:

- default string matching is case-insensitive;
- `case_sensitive="yes"` is exact case;
- `regexp="yes"` uses Java `Matcher.matches()` semantics, i.e. whole-string matching;
- enforce the same conceptual full-match behavior in Python (`fullmatch`, not prefix `match`/search);
- literal patterns are compared as entire strings;
- regexes are validated at load time;
- do not ASCII-downcast Cyrillic case behavior.

If Java/Python regex syntax differs for any actual pinned expression, add a targeted compatibility translation and differential test. Do not silently reinterpret it.

## 5.3 POS matching

- exact `postag` means exact raw LT POS string;
- `postag_regexp="yes"` uses whole-string regex matching;
- null/unknown POS behavior must match `PatternToken`;
- `negate_pos="yes"` semantics must be distinct from token-text negation;
- special tags such as `SENT_START` and `SENT_END` are matchable.

## 5.4 `inflected="yes"`

Pinned `PatternToken` tests a reading's lemma when `inflected=yes`; when the reading has no lemma it falls back to the token surface.

Do not synthesize inflected forms here and do not require Task 0006 synthesizer just to support this attribute.

## 5.5 Reading ambiguity

A surface token has multiple readings.

A pattern token matches when the LT pattern semantics are satisfied by the token's reading set. Do not prematurely disambiguate or choose the first reading.

### Critical `<and>` behavior

Russian XML frequently uses forms conceptually like:

```xml
<and>
  <token postag="...:Nom"/>
  <token postag="...:V"/>
</and>
```

This intentionally detects a **single surface token that has both possible readings**.

Each `<and>` child condition may therefore be satisfied by a different reading of the same `AnalyzedTokenReadings` container.

Do not require one impossible reading to have two different POS tags simultaneously.

Add a dedicated synthetic regression test for this.

## 5.6 Exceptions

Implement the exception semantics actually present in the pinned file, including current-token and `scope="next"` behavior if confirmed by the inventory.

Preserve combinations of:

```text
text / regexp
postag / postag_regexp
inflected
negation
scope
```

An exception suppresses the token/pattern match according to upstream semantics; it is not a separate disambiguation action.

## 5.7 `skip`

The pinned Russian XML visibly uses positive skip and negative/unbounded skip forms.

Implement the actual skip values found by the inventory, including exact behavior for:

```text
skip="1"
skip="-1"
```

if confirmed active.

Do not reinterpret `skip=-1` as Python slice syntax. Port LT matching semantics.

Add synthetic tests where multiple candidate paths exist so greedy/backtracking differences become observable.

## 5.8 Markers

`<marker>` selects which part of a matched pattern the disambiguation action targets.

Implement start/end corrections exactly enough to match pinned rules, including patterns where marker covers one token inside a longer pattern.

Do not simply apply every action to the first pattern token.

## 5.9 Antipatterns

Pinned Russian XML contains active antipatterns.

Port the disambiguation suppression behavior:

- match the rule normally;
- evaluate the rule/rulegroup antipatterns;
- suppress an action when an antipattern match overlaps the relevant rule match according to upstream overlap semantics;
- preserve rulegroup vs rule-local antipattern scope.

Add both positive and suppressed Java-oracle cases.

---

# 6. Disambiguation actions required by pinned Russian XML

Derive the final action set from inventory and implement all active actions. The inspected v6.8 resource is expected to require the following.

## 6.1 `REMOVE`

Support both forms used by LT:

```xml
<disambig action="remove" postag="..."/>
```

and exact reading removal with `wd`:

```xml
<disambig action="remove">
  <wd lemma="..." pos="...">...</wd>
</disambig>
```

Requirements:

- POS regexp matching follows Java full-match semantics;
- remove all readings selected by the action;
- preserve unaffected reading order;
- exact `wd` removal compares the required token/lemma/POS semantics as upstream does;
- if no ordinary readings remain, preserve LT's null-reading fallback;
- preserve `SENT_END` and other container metadata as upstream transformations do.

## 6.2 `ADD`

Support new interpretations from `<wd>`.

Upstream behavior to preserve:

- absent/empty `wd` token uses the matched token surface;
- absent lemma falls back to the effective token surface;
- exact POS string is added;
- reading is appended without generic deduplication;
- action applies to marker-selected token(s), not arbitrary pattern positions.

Real pinned cases include noun normalization additions, pronoun additions, abbreviations and imperative-hyphen handling.

## 6.3 Default `REPLACE`

When `<disambig>` has no `action`, upstream defaults to `REPLACE`.

The Russian file uses forms such as:

```xml
<disambig postag="NumD_D"/>
```

and:

```xml
<disambig>
  <match no="2" postag="ADV"/>
</disambig>
```

Implement the exact replacement semantics required by these active forms.

For direct POS replacement, preserve upstream lemma-selection fallback rather than inventing a new lemma.

For `<match no="...">`, implement the actual pinned `Match` behavior needed by Russian rules and prove it against Java oracle output.

Do not implement every `Match` transformation feature in LanguageTool unless inventory shows it is needed.

## 6.4 `IGNORE_SPELLING`

Pinned Russian disambiguation uses:

```xml
<disambig action="ignore_spelling"/>
```

This does not remove morphology. It marks the selected token as ignored by spelling rules.

Extend `AnalyzedTokenReadings` state to represent this exactly and preserve it across subsequent disambiguation transformations.

This flag will be consumed by later spelling-rule tasks, so silently dropping it is not acceptable.

## 6.5 Unsupported action families

Core LanguageTool also supports action types such as:

```text
FILTER
FILTERALL
UNIFY
IMMUNIZE
ADDCHUNK
```

Do not implement them merely for completeness if the pinned active Russian XML does not use them.

However, loader startup must fail with an explicit `UnsupportedDisambiguationFeatureError` (or equivalent) if an unsupported active action appears.

---

# 7. Pinned Russian partial-POS filter

The active Russian XML uses exactly the Java filter class:

```text
org.languagetool.rules.ru.NoDisambiguationRussianPartialPosTagFilter
```

Do not dynamically import arbitrary Java class names.

Implement an explicit registry:

```text
Java class name → Python compatibility implementation
```

Unknown filter class → explicit compatibility error.

## Required behavior

Port the relevant `PartialPosTagFilter` semantics:

Required arguments are conceptually:

```text
no
regexp
postag_regexp
```

and support any additional argument keys actually found by the pinned inventory.

The filter:

1. selects the specified matched token position (`no`, 1-based);
2. applies the configured regex to the token using whole-string matching;
3. validates expected capture-group count;
4. extracts capture group 1 (and group 2 only if the actual configured mode requires it);
5. applies optional prefix/suffix if present in actual inventory;
6. tags the extracted partial token using the **Task 0004 RussianTagger directly, without the disambiguator**;
7. keeps/rejects the rule match depending on whether partial-token POS readings satisfy `postag_regexp` and optional negation semantics.

This is why the class is named `NoDisambiguationRussianPartialPosTagFilter`: do not recursively call the new RussianHybridDisambiguator from inside it.

### Filter argument parsing

Port the relevant pinned `RuleFilterEvaluator` argument semantics rather than blindly splitting on every space/colon. Regex values contain punctuation and grouping syntax.

Add regression cases from real rules such as the `-ка`, `-то`, `пол-`, `обер-`, `экс-` families.

---

# 8. Rule execution order

Pinned `XmlRuleDisambiguator` processes its selected rule set sequentially:

```text
for rule in rulesForSentence(sentence):
    sentence = rule.replace(sentence)
```

Later rules can therefore see morphology/state produced by earlier rules.

Preserve **source rule order**.

`RuleSet.textHinted(...)` is an optimization for candidate-rule selection, not permission to reorder behavior.

For Task 0005 it is acceptable to evaluate all 77 active Russian rules in source order if:

- semantic parity is exact;
- resources/regexes are precompiled once;
- performance sanity is acceptable.

Do not invent text-hint optimization before correctness is proven.

---

# 9. Package-safe resources

Runtime disambiguation must work from an installed wheel with no Git checkout and no `third_party/` access.

Package byte-identical pinned copies under the existing resource tree, for example:

```text
src/pylat_ru/resources/ru/
  ... Task 0004 resources ...
  multiwords.txt
  disambiguation.xml
```

Extend deterministic resource sync/hash verification so the package copies are proven byte-identical to pinned upstream.

Extend the real wheel/install smoke test from Task 0004 to verify that both new resources are physically present in the wheel and usable after isolated installation.

Do not fetch these resources from the network at runtime.

---

# 10. Java oracle boundary

Extend the existing fail-closed `tools/differential_lt.py` oracle support.

Create a committed deterministic fixture, for example:

```text
tests/fixtures/oracle_russian_disambiguation.json
```

The oracle must remain bound to the trusted LanguageTool 6.8 JAR SHA from `compat/oracle_manifest.json`.

## Critical oracle rule

Do **not** use only:

```java
JLanguageTool.getAnalyzedSentence(...)
```

as the Task 0005 oracle, because that method also invokes Russian's **post-disambiguation `RussianChunker`**, which is out of scope.

The Java oracle must be able to observe the Task 0005 boundary directly, conceptually:

```text
raw = JLanguageTool.getRawAnalyzedSentence(sentence)

multiword = MultiWordChunker.getInstance("/ru/multiwords.txt")
             .disambiguate(raw)

final = RussianHybridDisambiguator.getInstance()
          .disambiguate(freshRawSentence)
```

Use fresh/raw copies as needed to avoid Java's mutable token containers contaminating stage comparisons.

## Fixture should record enough observable state

For each token/stage, record as applicable:

```text
full token sequence, including whitespace and SENT_START
non-whitespace mapping
surface token
clean token where relevant
start_pos_utf16
readings in exact order:
  token
  lemma
  raw pos_tag
chunk tags
is_whitespace
is_linebreak
is_sentence_start
is_sentence_end
ignored_by_speller
position-fix metadata if relevant
```

At minimum preserve separate expected snapshots for:

```text
raw tagged sentence
post-MultiWordChunker sentence
post-RussianHybridDisambiguator sentence
```

when practical. If the fixture format uses deltas for compactness, it must remain deterministic and independently reproducible from the Java oracle.

## Required oracle case coverage

Use at least 30 carefully selected sentence cases, or an equivalent larger generated set, covering every active behavior class discovered by the inventory:

- ambiguous noun case removal;
- adjective/participle ambiguity;
- `ADD`;
- exact `wd` `REMOVE`;
- default `REPLACE`;
- `<match no>` replacement;
- `IGNORE_SPELLING`;
- filter pass/fail;
- antipattern suppression;
- marker inside longer pattern;
- positive skip;
- negative/unbounded skip if active;
- `inflected=yes`;
- `case_sensitive=yes`;
- `negate` / `negate_pos` if active;
- `scope=next` exception;
- `SENT_START` / `SENT_END` conditions;
- multiword two-token and longer phrases;
- multiple whitespace around multiword candidates;
- punctuation;
- accented/ignored-character source offsets;
- unknown words.

Prefer real XML examples and real Russian phrases from the pinned resources. Do not create an oracle fixture from the Python implementation itself.

---

# 11. Suggested implementation layout

One reasonable structure is:

```text
src/pylat_ru/
  analysis.py                       # extend AnalyzedTokenReadings + AnalyzedSentence
  sentence_analysis.py              # raw LT-compatible sentence assembly
  disambiguation/
    __init__.py
    errors.py
    multiword.py                    # MultiWordChunker
    model.py                        # parsed disambiguation rule structures
    loader.py                       # disambiguation.xml loader
    matcher.py                      # required pattern matcher
    actions.py                      # add/remove/replace/ignore-spelling
    filters.py                      # NoDisambiguationRussianPartialPosTagFilter
    russian.py                      # RussianHybridDisambiguator
```

Exact file names may differ. Keep boundaries clear enough that later grammar.xml work can reuse pattern primitives without coupling grammar findings/messages to disambiguation actions.

---

# 12. Error model / fail-closed behavior

Add project-specific errors as appropriate, for example:

```text
DisambiguationError
DisambiguationResourceError
DisambiguationXMLFormatError
UnsupportedDisambiguationFeatureError
PatternCompatibilityError
MultiWordFormatError
DisambiguationFilterError
```

Fail explicitly on:

- missing `disambiguation.xml`;
- missing `multiwords.txt`;
- package-resource hash mismatch in validation tooling;
- malformed XML;
- duplicate/impossible rule metadata that upstream would reject;
- malformed regexp;
- unsupported active element/attribute/action;
- unknown filter class;
- malformed filter arguments;
- invalid capture-group count;
- invalid marker/reference index;
- impossible `<wd>` count for the action/matched range;
- invalid `skip` value;
- malformed multiword entry;
- internal non-whitespace/full-token mapping corruption.

Unknown **text tokens** remain normal. Broken **resources or unsupported rule features** are compatibility errors.

Never convert a parser/matcher compatibility problem into "rule did not match".

---

# 13. Tests

Create focused tests under suitable files, for example:

```text
tests/unit/test_analyzed_sentence.py
tests/unit/test_raw_sentence_analysis.py
tests/unit/test_multiword_chunker.py
tests/unit/test_disambiguation_inventory.py
tests/unit/test_disambiguation_loader.py
tests/unit/test_disambiguation_pattern_matcher.py
tests/unit/test_disambiguation_actions.py
tests/unit/test_russian_partial_pos_filter.py
tests/unit/test_russian_hybrid_disambiguator.py

tests/upstream/test_russian_disambiguation_parity.py

tests/fixtures/oracle_russian_disambiguation.json
```

Exact split may improve.

## Mandatory synthetic unit coverage

1. `AnalyzedSentence` full/non-whitespace mapping.
2. SENT_START insertion.
3. SENT_END added to last non-whitespace token.
4. whitespace/tabs/linebreak preservation.
5. ignored-character cleaning and position fix.
6. add-reading order.
7. remove-reading null fallback.
8. metadata preservation across reading replacement.
9. multiword two-token boundaries `<TAG>` / `</TAG>`.
10. multiword longer phrase.
11. multiword casing behavior with default Russian settings.
12. malformed multiword resource.
13. literal token matching.
14. case-insensitive/default and case-sensitive token matching.
15. token regexp whole-string semantics.
16. exact/regexp POS matching.
17. `inflected=yes` lemma matching.
18. text negation.
19. POS negation if active.
20. `<and>` conditions satisfied by different readings of the same token.
21. current-token exception.
22. scope-next exception.
23. skip positive.
24. skip -1/unbounded if active.
25. marker targeting.
26. antipattern suppression.
27. ADD.
28. REMOVE by POS regexp.
29. REMOVE exact `wd`.
30. default REPLACE by POS.
31. `<match>` replacement.
32. IGNORE_SPELLING state.
33. filter capture/retag/pass/fail.
34. unknown filter/action/attribute fails explicitly.
35. sequential rule order where rule B depends on rule A output.

## Mandatory real-resource/upstream coverage

- full deterministic XML inventory regeneration;
- expected 77 active rules / 11 rulegroups, if independently confirmed from current pin;
- real `multiwords.txt` phrases;
- real rules from each action family;
- real antipattern behavior;
- real `NoDisambiguationRussianPartialPosTagFilter` rules;
- exact Java oracle parity for the curated fixture;
- complete previous Task 0001–0004 test suite remains green;
- Java absent → normal Python runtime/tests remain functional except explicit oracle-generation tests/tools;
- isolated installed-wheel use of both new runtime resources.

---

# 14. Regex parity

Task 0003 already introduced the bounded `regex` dependency for SRX parity.

For disambiguation patterns:

- first determine whether standard `re` is sufficient for every pinned active pattern;
- if the existing `regex` package is required, reuse the already pinned/bounded dependency rather than adding another regex engine;
- use a small compatibility adapter so Java `Matcher.matches()` semantics are explicit;
- test Unicode Cyrillic case-insensitive behavior;
- test patterns with groups/alternation/classes used by real XML;
- inventory any Java regex construct requiring translation.

Do not transform regex strings heuristically without source-driven tests.

---

# 15. Performance and lifecycle

Correctness is primary, but the implementation must not make obviously pathological lifecycle choices.

Requirements:

- parse `disambiguation.xml` once per disambiguator/resource cache, not per sentence;
- parse `multiwords.txt` once;
- compile regexes once;
- reuse Task 0004 `RussianTagger` resources;
- do not spawn subprocesses in production;
- no full-dictionary expansion;
- no repeated wheel/resource hash verification on every token.

Report representative measurements for:

```text
disambiguator initialization
single representative sentence
batch of representative Russian sentences
```

No arbitrary performance gate is required unless a regression is obviously severe. Record the environment and methodology honestly.

---

# 16. Licensing and provenance

The project remains LGPL-2.1-or-later and uses pinned LanguageTool resources/source as compatibility references.

If any upstream Java implementation is copied/adapted materially rather than independently reimplemented from behavior:

- preserve attribution in source comments;
- update provenance/license inventory if new third-party reference files are vendored;
- record exact upstream path/commit;
- do not copy unrelated dependencies such as fastutil/Apache Commons implementations into production merely because core LT uses them.

Implement equivalent data structures with Python built-ins where semantics are straightforward.

If provenance/license status is unclear, mark it `BLOCKED_LICENSE_REVIEW` rather than guessing.

---

# 17. Compatibility matrix update

On successful completion update `compat/compatibility.json` honestly.

Expected direction:

```text
RussianSentenceTokenizer      SUPPORTED
RussianWordTokenizer          SUPPORTED
RussianTagger                 SUPPORTED
RussianDisambiguator          SUPPORTED
RussianChunker                NOT_YET_IMPLEMENTED
RussianSynthesizer            NOT_YET_IMPLEMENTED
XMLRuleEngine                 NOT_YET_IMPLEMENTED
```

Add useful Task 0005 sub-statuses, e.g.:

```text
raw_sentence_assembly
analyzed_sentence_mapping
ignored_character_positions
multiword_chunker
disambiguation_xml_loader
disambiguation_pattern_matcher
disambiguation_actions
antipatterns
partial_pos_filter
ignore_spelling_state
java_disambiguation_oracle
runtime_resource_packaging
```

Do not mark generic grammar XML or post-disambiguation `RussianChunker` as supported.

---

# 18. Completion report

Create:

```text
reports/0005_russian_hybrid_disambiguator.md
```

Include at minimum:

- exact upstream pin/references;
- independently derived XML feature inventory;
- active rule/rulegroup/action/filter counts;
- multiword resource counts/statistics;
- raw sentence assembly behavior;
- ignored-character/offset semantics;
- `AnalyzedSentence` mapping model;
- MultiWordChunker behavior and real phrase proofs;
- XML loader/matcher architecture;
- implemented XML feature matrix;
- explicit unsupported feature matrix;
- action semantics implemented;
- filter implementation;
- antipattern behavior;
- Java oracle fixture generation command/provenance;
- oracle case/token counts and exact parity result;
- wheel/package-resource proof;
- performance sanity results;
- full test command and exact count;
- known limitations/differences;
- what remains for the next task.

If any active pinned Russian disambiguation feature is unsupported or any required oracle case fails, do **not** mark `RussianDisambiguator` fully supported.

---

# Acceptance criteria

Task 0005 is complete only when all of the following are true:

1. Production Russian disambiguation is Python-native and invokes no Java/server/network.
2. The LT pin remains `v6.8` / `e807fcde6a6506191e1470744d2345da28c26be6`.
3. The active pinned `disambiguation.xml` feature inventory is generated from source, not hardcoded.
4. Full deterministic inventory regeneration is byte-for-byte tested.
5. The inventory independently confirms the active rule/rulegroup counts and feature set.
6. Raw sentence analysis preserves whitespace tokens.
7. Raw sentence analysis prepends `SENT_START` exactly.
8. `SENT_END` is attached to the last non-whitespace token with LT-compatible semantics.
9. Non-whitespace-to-full-token mapping matches LT behavior.
10. Sentence text reconstruction remains exact for ordinary text.
11. Russian ignored characters U+00AD/U+0301/U+0300 are handled at the full-pipeline boundary compatibly with JLanguageTool.
12. Source-surface vs clean-token vs morphology-token state is not silently conflated.
13. UTF-16 internal positions match the Java oracle on ignored-character and non-BMP cases.
14. Reading mutation helpers preserve special metadata and deterministic order.
15. Removing the last ordinary reading yields LT-compatible null-reading behavior.
16. Pinned `multiwords.txt` is parsed and packaged.
17. MultiWordChunker executes before XML disambiguation.
18. Russian MultiWordChunker default casing settings are reproduced.
19. Multiword boundary readings/lemmas match the Java oracle.
20. Multiword whitespace behavior is parity-tested.
21. Pinned `disambiguation.xml` is parsed and packaged.
22. Rule and rulegroup source order is preserved.
23. Unknown active XML behavior fails explicitly instead of being skipped.
24. Literal token matching parity is proven.
25. Regex token matching uses whole-string Java-compatible semantics.
26. POS exact/regexp matching parity is proven.
27. `inflected=yes` uses lemma-or-token semantics compatible with `PatternToken`.
28. Ambiguous reading-set matching is preserved.
29. `<and>` can match distinct readings of the same surface token as upstream requires.
30. Exceptions used by pinned XML are implemented.
31. `scope="next"` behavior is implemented if confirmed active.
32. Active positive/negative skip values are implemented exactly.
33. Marker targeting is implemented.
34. Active antipattern behavior is implemented.
35. `ADD` action parity is proven.
36. `REMOVE` by POS parity is proven.
37. exact `wd` removal parity is proven.
38. default `REPLACE` parity is proven.
39. active `<match>` replacement parity is proven.
40. `IGNORE_SPELLING` state is represented and parity-tested.
41. `NoDisambiguationRussianPartialPosTagFilter` is implemented without recursive disambiguation.
42. Unknown filter classes fail explicitly.
43. Filter argument/capture/POS matching behavior is parity-tested on real Russian rules.
44. Rules execute sequentially so later rules see earlier modifications.
45. `disambiguation-global.xml` is not loaded.
46. `RussianChunker` is not implemented or marked supported by this task.
47. The Java oracle observes the Task 0005 boundary directly and does not accidentally include post-disambiguation RussianChunker output.
48. Oracle fixture metadata includes the verified LT JAR SHA and upstream pin.
49. The curated oracle corpus covers every active action/filter/pattern feature family.
50. Exact final disambiguated readings and relevant token flags match Java oracle for all committed cases.
51. `multiwords.txt` and `disambiguation.xml` package copies are hash-verified against pinned upstream.
52. A real built/installed wheel contains and successfully uses the new resources without repository `third_party/` access.
53. No semantic substitute NLP dependency is introduced.
54. Resources/regexes are cached rather than reparsed per token/sentence.
55. Existing Task 0001–0004 tests remain green.
56. Full Task 0005 tests pass.
57. Completion report is written and does not hide unsupported behavior.
58. Diff/status is reviewed for accidental caches, JARs, build outputs, wheels or unrelated files.
59. Task 0005 changes are committed intentionally.
60. The completed commit is pushed to `origin` immediately.
61. The remote commit is verified visible.
62. Task 0006 is not started automatically.

---

# Expected final state after Task 0005

```text
raw text
  ↓
RussianSentenceTokenizer                         ✅
  ↓
RussianWordTokenizer                             ✅
  ↓
RussianTagger                                    ✅
  ↓
Raw AnalyzedSentence assembly                    ✅
  ├─ whitespace mapping                         ✅
  ├─ SENT_START / SENT_END                      ✅
  └─ ignored-character position handling        ✅
  ↓
RussianHybridDisambiguator                       ✅
  ├─ MultiWordChunker                           ✅
  ├─ multiwords.txt                             ✅
  ├─ XmlRuleDisambiguator                       ✅
  ├─ disambiguation.xml                         ✅
  ├─ antipatterns / marker / skip               ✅
  ├─ ADD / REMOVE / REPLACE                     ✅
  ├─ IGNORE_SPELLING                            ✅
  └─ NoDisambiguationRussianPartialPosTagFilter ✅
  ↓
RussianChunker (post-disambiguation)              ⛔ later task
  ↓
RussianSynthesizer                                ⛔ later task
  ↓
Russian grammar/rule engine                       ⛔ later tasks
```

The key result is not merely that one ambiguous noun loses one POS tag. The result must be that downstream LanguageTool Russian rules receive the **same disambiguated analyzed-sentence surface** they would receive immediately after pinned `RussianHybridDisambiguator`, including multiword boundary readings, exact morphology order, sentence markers, whitespace mapping, ignored-spelling state, XML rule ordering, marker targeting, exceptions, antipatterns and source-compatible positions.

---

# Completion workflow

Follow `AGENTS.md` exactly:

```text
implement Task 0005 only
→ focused tests while developing
→ full Task 0001–0005 test suite
→ deterministic artifact regeneration/checks
→ real wheel/install resource smoke test
→ reports/0005_russian_hybrid_disambiguator.md
→ git diff/status review
→ one intentional Task 0005 commit (plus later review-fix commit only if needed)
→ push current branch to origin
→ verify remote commit is visible
→ stop
```

Do not start Task 0006.