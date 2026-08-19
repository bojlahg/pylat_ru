# Task 0007 — RussianChunker + XML Grammar Engine Core

## Status

READY

## Goal

Implement the next native-Python stage of the pinned Russian LanguageTool pipeline:

1. the missing post-disambiguation `RussianChunker` prerequisite;
2. a deterministic loader/model for the complete pinned Russian `grammar.xml`;
3. the first executable **core subset** of LanguageTool pattern grammar rules;
4. exact rule/finding metadata, source spans, basic message/suggestion formatting, and Java differential parity for the subset actually claimed as supported;
5. a machine-readable classification of **all 892 pinned Russian grammar rules** into the roadmap phases that are still required.

The conceptual pipeline after this task is:

```text
text
 ↓
RussianSentenceTokenizer             ✅ 0003
 ↓
RussianWordTokenizer                 ✅ 0003
 ↓
RussianTagger                        ✅ 0004
 ↓
RussianHybridDisambiguator           ✅ 0005
 ↓
RussianChunker                       ✅ Task 0007
 ↓
Russian XML grammar loader           ✅ Task 0007
 ↓
Russian XML grammar core matcher     ✅ Task 0007, explicit core subset only
 ↓
advanced matching                    ⛔ Task 0008
unification                          ⛔ Task 0009
XML filters                          ⛔ Task 0010
Java rules                           ⛔ Task 0011
spelling/compound/replace/repetition ⛔ Task 0012
```

Task 0007 must **not** claim the entire Russian `grammar.xml` runnable. Its job is to establish a trustworthy grammar-engine foundation, execute a precisely classified core subset with pinned Java parity, and make every deferred rule explicit.

---

# Pinned compatibility target

The compatibility pin remains unchanged:

```text
LanguageTool tag:    v6.8
LanguageTool commit: e807fcde6a6506191e1470744d2345da28c26be6
Morfologik version:  2.1.9
```

Do not update the LanguageTool pin in Task 0007.

Known Task-0001 Russian `grammar.xml` baseline:

```text
size:                 1,194,903 bytes
sha256:               e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec
categories:           8
rulegroups:           297
rules:                892
examples:             2446
incorrect examples:   1083
correct examples:     1363
examples w/correction 1026
filters referenced:   6 grammar filters / 23 filter elements
```

Known structural counts from `compat/inventory.json` include:

```text
and             1
antipattern     146
exception       1275
filter          23
marker          1331
match           620
or              15
pattern         892
suggestion      806
token           3226
unification     8
unify           28
unify-ignore    12
```

Known attributes include, among others:

```text
pattern@case_sensitive
pattern@raw_pos

token@case_sensitive
token@chunk
token@inflected
token@max
token@min
token@negate
token@negate_pos
token@postag
token@postag_regexp
token@regexp
token@skip
token@spacebefore

exception@case_sensitive
exception@inflected
exception@negate
exception@negate_pos
exception@postag
exception@postag_regexp
exception@regexp
exception@scope
exception@spacebefore

match@case_conversion
match@include_skipped
match@no
match@postag
match@postag_regexp
match@postag_replace
match@regexp_match
match@regexp_replace
match@setpos

rule@default
rule@id
rule@name
rule@tags
rulegroup@default
rulegroup@id
rulegroup@name
rulegroup@tags

message@suppress_misspelled
suggestion@suppress_misspelled
```

These counts are a starting baseline only. **Phase 0 must independently regenerate and refine the inventory from the pinned files.**

---

# Why `RussianChunker` is part of Task 0007

The original roadmap omitted a separate numbered task for `RussianChunker`, but the actual pinned pipeline does not omit it:

```text
Russian.java
  createDefaultDisambiguator()
  createDefaultPostDisambiguationChunker() -> new RussianChunker()
```

and the pinned grammar uses `token@chunk` (Task-0001 inventory found 21 such tokens).

Therefore the grammar engine cannot reach full Russian parity later unless the post-disambiguation chunk state is available.

Task 0007 closes this pipeline prerequisite before grammar-rule execution.

Do not broaden this into a generic OpenRegex implementation. Port exactly the behavior required by pinned `RussianChunker.java`.

---

# Relevant pinned upstream sources

At minimum inspect and inventory the exact pinned versions of:

```text
languagetool-language-modules/ru/
  src/main/java/org/languagetool/language/Russian.java
  src/main/java/org/languagetool/chunking/RussianChunker.java
  src/main/java/org/languagetool/chunking/TokenExpressionFactory.java   (if used from core/module tree)
  src/main/resources/org/languagetool/rules/ru/grammar.xml
  src/test/java/org/languagetool/rules/ru/RussianPatternRuleTest.java

languagetool-core/src/main/java/org/languagetool/rules/patterns/
  PatternRuleLoader.java
  PatternRuleHandler.java
  AbstractPatternRule.java
  PatternRule.java
  PatternRuleMatcher.java
  AbstractPatternRulePerformer.java
  PatternToken.java
  PatternTokenMatcher.java
  Match.java
  MatchState.java
  PosToken.java
  StringMatcher.java
  Unifier.java

languagetool-core/src/main/java/org/languagetool/rules/
  Rule.java
  RuleMatch.java
  Category.java
  CategoryId.java
  RuleWithMaxFilter.java

languagetool-core/src/test/java/org/languagetool/rules/patterns/
  PatternRuleLoaderTest.java
  PatternRuleMatcherTest.java
  PatternRuleTest.java
```

The exact source list may differ after inspection. The generated Task-0007 inventory is authoritative.

If a class used by the pinned Russian core matcher lives elsewhere, add it to the source inventory with path, size, SHA-256, purpose and license status.

---

# Mandatory project constraints

Read and obey before implementation:

```text
AGENTS.md
docs/Handoff_pylat_ru.md
reports/0003_russian_sentence_word_tokenization_offsets.md
reports/0004_russian_tagger.md
reports/0005_russian_hybrid_disambiguator.md
reports/0006_russian_synthesizer.md
compat/inventory.json
compat/extracted_grammar_examples.json
compat/compatibility.json
compat/oracle_manifest.json
```

Requirements remain:

- Python-only production runtime;
- no Java/JRE/server/network dependency in package/runtime API;
- Java allowed only in explicit development/conformance tooling;
- exact pinned LT semantics are the target;
- original upstream `grammar.xml` is data, not something to manually translate into 892 Python rules;
- unknown active XML behavior is never silently ignored;
- recognized-but-deferred behavior is explicitly classified and must not execute as if supported;
- rules/resources are parsed/compiled once per long-lived engine, not per sentence;
- no Natasha/pymorphy/other NLP substitute;
- no speculative multilingual framework;
- do not begin Task 0008 automatically.

---

# Scope

## In scope

1. Exact native port of pinned `RussianChunker` behavior needed by the Russian pipeline.
2. Package-safe exact copy of pinned Russian `grammar.xml`.
3. Deterministic Task-0007 grammar inventory/classification.
4. Full structural parsing of the pinned Russian `grammar.xml` into a Python model.
5. Exact rule/category/rulegroup/source-order/full-ID metadata.
6. Explicit feature/blocker classification for all 892 rules.
7. Core token matching for the supported Task-0007 feature subset.
8. Current-token exceptions for the supported core subset.
9. Marker-based finding spans for core rules.
10. Basic message/short-message/suggestion templates used by core rules.
11. Basic `<match no="...">` substitution for core rules where no advanced `<match>` attributes are active.
12. Exact source offsets, including Java UTF-16 parity and Python codepoint spans.
13. Rule default/enabled metadata and rulegroup inheritance required by pinned XML.
14. Core-rule execution against fully analyzed/chunked Russian sentences.
15. Java differential fixtures for chunker and grammar core.
16. Execution of all `grammar.xml` examples belonging to the Task-0007 core-runnable subset.
17. Real installed-wheel grammar-resource and core-rule smoke tests.
18. Honest compatibility/report updates.

## Explicitly out of scope

Task 0007 must not implement:

- full `skip` matching;
- `min`/`max` optional/repeated pattern semantics;
- antipattern matching;
- advanced `<and>` / `<or>` pattern containers unless Phase 0 proves a trivial case is unavoidable for core classification;
- `spacebefore` matching;
- `pattern@raw_pos` / pre-disambiguation grammar matching;
- complex `<match>` transformations (`regexp_match`, `regexp_replace`, POS synthesis, `postag_replace`, `include_skipped`, `setpos`, case-conversion machinery beyond the proven basic core formatter);
- unification (`unification`, `feature`, `equivalence`, `unify`, `unify-ignore`);
- any grammar XML filter implementation;
- `AdvancedSynthesizerFilter`;
- `RussianPartialPosTagFilter`;
- date/INN/future-date/suppress-misspelled filters;
- spelling-rule integration;
- Russian Java grammar rules;
- replace/coherency/compound/repetition engines;
- full public `LanguageToolRU.check()`;
- complete 2446-example parity claim;
- Task 0008 work.

These features must be classified as deferred, not silently approximated.

---

# Core principle: load all rules, execute only proven rules

The Task-0007 loader must understand enough structure to inventory every rule in the pinned file.

The executable engine must then classify each rule using an explicit feature set.

A rule is `CORE_0007_RUNNABLE` only if **every behaviorally active feature it needs is implemented and proven in Task 0007**.

Any other rule remains loaded as metadata but has explicit blocker records.

Suggested conceptual states:

```text
CORE_0007_RUNNABLE
DEFERRED_0008_ADVANCED_MATCHING
DEFERRED_0009_UNIFICATION
DEFERRED_0010_FILTER
DEFERRED_0012_SPELLING_OR_SUPPRESSION
BLOCKED_UNSUPPORTED_OR_UNKNOWN
```

A rule may have more than one blocker. Preserve a list, for example:

```json
{
  "full_rule_id": "EXAMPLE[2]",
  "execution_state": "DEFERRED",
  "blockers": [
    {"feature": "token@skip", "target_task": "0008"},
    {"feature": "filter:...AdvancedSynthesizerFilter", "target_task": "0010"}
  ]
}
```

Do not use one opaque boolean like `supported=false` when the exact reason is knowable.

Attempting to execute a deferred rule explicitly must raise a typed project compatibility error describing the rule ID and blockers.

There may be an explicit `core_only=True` batch mode that executes only `CORE_0007_RUNNABLE` rules. It must expose/report the skipped/deferred counts and must never masquerade as a full grammar check.

---

# Phase 0 — Deterministic grammar-core inventory

Create:

```text
tools/russian_grammar_core_inventory.py
compat/russian_grammar_core_inventory.json
```

The inventory must be generated from pinned files/source, not hand-written.

At minimum record:

## Pinned files/sources

For each relevant source/resource:

```text
path
size
sha256
license/provenance status
purpose
```

Include at least:

```text
grammar.xml
RussianChunker.java
Russian.java
PatternRuleLoader.java
PatternRuleHandler.java
AbstractPatternRule.java
PatternRule.java
PatternRuleMatcher.java
AbstractPatternRulePerformer.java
PatternToken.java
PatternTokenMatcher.java
Match.java
MatchState.java
RuleMatch.java
RussianPatternRuleTest.java
PatternRuleLoaderTest.java
PatternRuleMatcherTest.java
PatternRuleTest.java
```

## Complete grammar structure

Re-derive:

```text
category count
rulegroup count
rule count
direct rule count
grouped rule count
example counts by type
examples with correction
all XML element counts
all XML attribute counts
all distinct attribute values where finite/reasonable
all filter classes + counts
all rule/default values
all rulegroup/default values
all rule/rulegroup tags values
all exception scope values
all token skip/min/max values
all chunk values
all match attribute combinations
all regex-bearing locations
all unification features/equivalences
```

## Full IDs and exact source order

For every rule record:

```text
source_order_index
category id/name
rulegroup id/name or null
rule id/subId if present
resolved Java-compatible full rule ID
rule name
rule default state
inherited group default state
rule tags
group tags
XML source path
examples count
incorrect/correct counts
feature set
execution state
blocker list
```

Do not emit `UNKNOWN`, empty IDs, or invented IDs.

Where Java's full-ID construction is non-obvious, use the pinned Java oracle to derive it.

## Feature-classification matrix

Automatically derive per rule booleans/counts for at least:

```text
has_marker
has_exception
has_scoped_exception
has_and
has_or
has_antipattern
has_skip
has_min_max
has_inflected
has_negate
has_negate_pos
has_postag
has_postag_regexp
has_text_regexp
has_case_sensitive
has_chunk
has_spacebefore
has_raw_pos
has_filter
filter_classes[]
has_unification
has_unify
has_unify_ignore
has_basic_match
has_complex_match
match_attribute_sets[]
has_message_suppress_misspelled
has_suggestion_suppress_misspelled
```

Then derive exact totals for:

```text
CORE_0007_RUNNABLE
rules requiring 0008
rules requiring 0009
rules requiring 0010
rules requiring 0012/suppression
rules with multiple blockers
unknown/unclassified rules
```

**Unknown/unclassified must be zero before Task 0007 is accepted.**

Unknown does not mean implemented. It means every pinned rule must have a known disposition.

## Regex inventory

For all regexes relevant to core-runnable rules, derive:

```text
location
rule ID
raw pattern
case sensitivity
Java Pattern flags/semantics required
whether Python `regex` can compile it directly
whether translation is required
```

Do not assume Python `re` is equivalent to Java Pattern.

The project already depends on the third-party Python `regex` package for earlier compatibility work; reuse it where appropriate rather than creating a second regex abstraction accidentally.

## Chunker inventory

Extract from pinned `RussianChunker.java`:

```text
FILTER_TAGS
SYNTAX_EXPANSION
PhraseType values
REGEXES1 in exact order
REGEXES2 in exact order
expression text
phrase type
overwrite flag
all expression operators actually used
all matcher predicates actually used
all quantifiers actually used
```

Do not manually claim a generic OpenRegex feature that the pinned class never uses.

The inventory must have a byte-exact deterministic regeneration test.

---

# Phase 1 — Native `RussianChunker`

Implement the pinned Russian post-disambiguation chunker under an appropriate package, for example:

```text
src/pylat_ru/chunking/
  __init__.py
  russian.py
  token_expression.py
```

The exact structure may differ.

## Input/output boundary

Input:

```text
AnalyzedSentence after RussianHybridDisambiguator
```

Output:

```text
same logical analyzed sentence/token readings
with chunk tags matching pinned RussianChunker
```

Do not destroy existing chunk tags unrelated to an overwrite operation.

## Required pinned behavior

Reproduce at least the behavior proven by the actual class:

- ignore whitespace tokens when building chunker matching input;
- tokens carrying `MayMissingYO` are excluded from chunk matching as pinned Java does;
- initial included token chunk state begins with `O` for matching;
- apply `REGEXES1` in exact declared order;
- apply `REGEXES2` in exact declared order after `REGEXES1`;
- preserve exact match-overlap behavior from the underlying Java/OpenRegex calls;
- apply every match returned by each expression in exact order;
- implement `overwrite` exactly;
- when overwriting, remove only tags in pinned `FILTER_TAGS`;
- do not remove unrelated chunk tags;
- never append a duplicate chunk tag;
- when a real chunk tag is added, remove `O`;
- exact B/I naming for NP/NPP/VP/ADJP/DPT;
- exact direct phrase tag naming for other phrase types;
- assign final chunk-tag lists back to the corresponding original `AnalyzedTokenReadings` objects/tokens;
- preserve token/readings/order/offset/whitespace/sentence metadata.

## OpenRegex boundary

Do not add Java/OpenRegex to production.

A small Python evaluator is acceptable if it implements the exact syntax/semantics required by the extracted pinned expressions.

The Phase-0 inventory must prove which of these are actually needed, such as:

```text
<string=value> / <literal>
<regex=...>
<regexCS=...>
<chunk=...>
<pos=...>
<posre=...> / <posregex=...>
logical AND
negated condition
*
+
sequence matching
```

Do not implement or advertise unused OpenRegex syntax merely for completeness.

Unknown expression syntax in the pinned source/data must fail inventory/compatibility validation, not be skipped.

## Chunker differential oracle

Extend `tools/differential_lt.py` and commit:

```text
tests/fixtures/oracle_russian_chunker.json
```

Use the already trusted Task-0005/0006 Java oracle build and `oracle_build_id` binding.

The Java oracle must isolate the exact boundary:

```text
raw sentence
→ RussianHybridDisambiguator
→ snapshot post-hybrid
→ RussianChunker.addChunkTags
→ snapshot post-chunker
```

Do not use only `JLanguageTool.getAnalyzedSentence()` without separately capturing/preparing the pre-chunker boundary, because that would hide where a mismatch originates.

Capture for each token at least:

```text
token
start_pos_utf16
pos_fix
whitespace/sentence markers
readings in exact order
chunk_tags in exact order
ignored spelling state
clean/source-token metadata where applicable
```

Corpus requirements:

- every distinct pinned chunker expression should be exercised if a compact real/synthetic input can be derived;
- otherwise inventory it as unexercised with an explicit reason;
- include person/name NPs;
- initials/name patterns;
- verb phrases;
- SBAR literals;
- adjective+noun phrases;
- participle/adverbial-participle cases;
- plural NP joining patterns;
- overwrite conflicts;
- existing unrelated chunk-tag preservation;
- `MayMissingYO` exclusion;
- whitespace preservation;
- ambiguous multi-reading tokens.

Target at least 25 differential chunker cases, preferably more if required to cover every expression class.

---

# Phase 2 — Package `grammar.xml`

Add a package-runtime exact copy of pinned Russian grammar data, for example:

```text
src/pylat_ru/resources/rules/ru/grammar.xml
```

Requirements:

- byte-for-byte pinned `grammar.xml`;
- size/hash validated against pinned upstream metadata;
- present in built wheel;
- runtime never depends on `third_party/...` checkout path;
- corrupt packaged XML fails explicitly;
- no silent fallback to vendored checkout after package corruption;
- no network/XInclude/external-resource fetching during production parsing;
- parser must not interpret arbitrary external entities;
- parser/load is cached for long-lived engine use.

Do not modify or normalize upstream XML formatting/content merely to make Python parsing easier.

---

# Phase 3 — Grammar XML model and fail-closed loader

Implement a dedicated grammar package, for example:

```text
src/pylat_ru/grammar/
  __init__.py
  errors.py
  model.py
  loader.py
  classifier.py
  matcher.py
  formatter.py
  engine.py
```

Exact file names may differ.

## Suggested typed errors

```text
GrammarError
GrammarResourceError
GrammarXmlFormatError
GrammarUnsupportedFeatureError
GrammarDeferredFeatureError
GrammarRegexError
GrammarExecutionError
```

Callers must be able to distinguish malformed resources from a valid no-match result.

## Model requirements

Represent without losing source order or raw strings:

```text
GrammarDocument
GrammarCategory
GrammarRuleGroup
GrammarRule
GrammarPattern
GrammarPatternToken
GrammarException
GrammarMarker span membership
GrammarMessageTemplate
GrammarSuggestionTemplate
GrammarMatchReference
GrammarExample
GrammarFilterReference (metadata only in 0007)
GrammarUnificationReference (metadata only in 0007)
```

The exact types may differ, but do not reduce the loader to anonymous dicts that make later parity work unmaintainable.

Preserve at least:

```text
raw rule/group IDs
resolved full ID
category metadata
source order
rule/group default values
rule/group tags
name
pattern case-sensitive state
all raw token/exception/match attributes
message/short-message mixed text
suggestions in source order
URL
examples and correction strings
filter class/args as deferred metadata
unification metadata as deferred metadata
```

## Full structural parsing vs executable support

The loader must **recognize and retain/classify** every behaviorally active element/attribute in pinned Russian `grammar.xml`.

It does not need to execute Task-0008/0009/0010 features yet.

Rules that contain those features must be marked deferred.

Unknown element/attribute/value not present in the known pinned inventory must raise an explicit compatibility error if encountered at runtime.

Never do this:

```python
for child in element:
    if child.tag == "known":
        ...
    # everything else silently disappears
```

Validate allowed child elements per parent context, not only globally.

A globally known tag in a semantically unsupported location must fail.

## IDs and inheritance

Reproduce pinned Java `PatternRuleLoader` observable semantics for:

- direct rule IDs;
- rulegroup IDs;
- child rule/subrule IDs;
- resolved full IDs;
- source order;
- inherited group metadata;
- `default` values;
- `tags` metadata;
- category association.

Use Java fixture proof for edge cases rather than copying Task-0005 ID logic by assumption.

---

# Phase 4 — Core-runnable rule definition

After Phase 0, define the exact Task-0007 executable feature set in code and inventory.

The expected core capability should include rules using only the following **after Java verification**:

## Pattern sequence

- ordinary sequential pattern tokens;
- no `skip`;
- no `min/max` other than the implicit exactly-one default;
- no antipattern;
- no unification;
- no filter;
- no advanced AND/OR groups;
- no raw/pre-disambiguation POS mode;
- no unsupported `spacebefore` behavior.

## Token conditions

- literal text matching;
- `regexp` text matching;
- `case_sensitive`;
- exact POS tag;
- POS regexp;
- `inflected` lemma matching;
- text `negate`;
- POS `negate_pos`;
- POS-only tokens;
- text-only tokens;
- combined text+POS conditions;
- sentinel POS conditions (`SENT_START`, `SENT_END`) if they appear in core-classifiable rules;
- special `UNKNOWN` POS behavior if used by core rules.

Each bullet is conditional on exact pinned Java semantics being implemented and proven. If Phase 0 discovers an unexpected complication, classify affected rules deferred instead of approximating.

## Basic exceptions

Task 0007 should support only exception forms whose semantics are proven by the implemented core matcher.

Expected minimum:

- current-token exception without `scope`;
- text/regexp exception;
- POS/POS-regexp exception;
- exception `inflected`;
- exception `negate` / `negate_pos` if present in otherwise-core rules;
- exception case-sensitivity inheritance/override.

Scoped `next`/`previous`, `spacebefore`, grouped exceptions or other advanced behavior may be deferred to 0008 unless the pinned core classification requires them.

## Marker

Implement basic `<marker>` membership and use it for the error span.

If no marker exists, use the full matched pattern span as pinned Java does.

Do not confuse marker span with full pattern span; both are needed for formatter/match references and later filters.

---

# Phase 5 — Core token-matching semantics

Do not simply reuse the Task-0005 disambiguation matcher and declare parity.

Reuse low-level concepts/code where genuinely identical, but verify grammar behavior against:

```text
PatternToken
PatternTokenMatcher
AbstractPatternRulePerformer
PatternRuleMatcher
```

Key semantics to prove include:

## Matching input

Pinned `PatternRuleMatcher` normally uses:

```text
sentence.getTokensWithoutWhitespace()
```

and only uses pre-disambiguation tokens for `raw_pos` rules.

Task 0007 core rules must therefore match the post-disambiguation + post-chunker non-whitespace token sequence while retaining mapping back to full source tokens/spans.

`raw_pos` rules are deferred to 0008.

## Reading semantics

Prove whether combined token text/POS predicates must match:

- the same `AnalyzedToken` reading;
- any reading independently;
- all readings for special cases.

Do not infer this from the Task-0005 `<and>` implementation.

Add synthetic ambiguous-reading cases that distinguish the alternatives and compare with Java.

## Regex semantics

- Java regex uses full-match behavior where `Matcher.matches()` is used;
- case-insensitive behavior must match pinned Unicode behavior;
- raw XML regex text must be preserved;
- invalid regex raises typed error at load/compile time with rule ID/source context;
- no substring-search substitute unless Java source proves it.

## Inflected semantics

Prove and implement exact lemma-vs-surface handling, including:

- multiple readings;
- null lemma;
- case sensitivity;
- regexp + inflected combinations if present in core rules.

## Negation

Text negation and POS negation are distinct.

Prove combined text/POS negation truth tables with synthetic Java-oracle cases.

## Sentinels and offsets

Preserve `SENT_START`/`SENT_END` behavior from accepted analyzed-sentence model.

Never make sentinel token text contribute bogus source length.

---

# Phase 6 — Core message, short message and suggestions

The Task-0007 engine must create useful RuleMatch-compatible findings for core rules.

Implement the **basic formatter subset only** and classify rules requiring advanced formatting as deferred.

## Required basic template support

Expected minimum after Phase-0 proof:

```text
plain text in <message>
plain text in <short>
<suggestion>...</suggestion>
multiple suggestions in source order
basic <match no="N"> reference to a matched token
basic match reference inside message and suggestion
XML mixed text/tails preservation
```

A basic `<match>` is Task-0007-runnable only when it uses the proven basic attribute set, expected to be:

```text
no
```

Any rule using additional active `<match>` transformation attributes must be deferred to 0008 or 0010 as appropriate:

```text
case_conversion
include_skipped
postag
postag_regexp
postag_replace
regexp_match
regexp_replace
setpos
```

Do not parse those attributes and then pretend they have no effect.

## Suggestion markup

The final finding should not expose raw XML `<suggestion>` tags as user text.

Prove Java formatting for the core subset and capture separately:

```text
message
short_message
ordered replacements/suggestions
```

Preserve duplicate suggestions if Java preserves them.

Do not sort suggestions.

## Case adjustment

Pinned `PatternRuleMatcher` performs automatic suggestion case handling in some situations.

Task 0007 must either:

1. implement and prove the basic case-adjustment behavior needed by core-runnable rules; or
2. classify every rule requiring that behavior as deferred.

Do not silently emit lowercase replacements where Java emits uppercase, or vice versa.

## Suppress-misspelled behavior

Rules/messages/suggestions using `suppress_misspelled` require spelling-layer/filter interactions that are not established yet.

Classify them explicitly as deferred unless Java/source analysis proves an isolated grammar-core behavior can be implemented without Task 0012.

Do not fake spelling decisions.

---

# Phase 7 — Finding model and offsets

Create an internal finding representation suitable for later public API integration.

Suggested observable fields:

```text
rule_id
full_rule_id
sub_id/group info if applicable
category_id
category_name
rule_name
message
short_message
replacements: ordered list[str]
source: "grammar.xml"
rule_source_order

sentence-local:
  from_utf16
  to_utf16
  from_codepoint
  to_codepoint

full-pattern span:
  pattern_from_utf16
  pattern_to_utf16
  pattern_from_codepoint
  pattern_to_codepoint
```

If document-level checking is implemented internally, also preserve document-adjusted offsets separately.

Do not conflate UTF-16 Java offsets with Python codepoint offsets.

Add emoji/non-BMP differential cases.

Marker span and full pattern span must both remain available because later filters and formatting depend on them.

---

# Phase 8 — Internal grammar engine API

Do not expose premature full `LanguageToolRU.check()`.

An internal API may resemble:

```python
engine = RussianGrammarEngine()

engine.rules
engine.core_rules
engine.deferred_rules

engine.check_sentence(analyzed_sentence, core_only=True)
engine.check_text_core(text)
engine.check_rule(text, full_rule_id)
```

Exact naming is flexible.

Required semantics:

- grammar/chunker resources loaded once;
- compiled regexes/rule model cached;
- source-order rule execution;
- output matches preserved in deterministic Java-compatible order for the tested boundary;
- explicit rule execution can force a default-off core rule for testing;
- ordinary core batch mode respects pinned default-enabled metadata;
- trying to execute a deferred rule by ID raises `GrammarDeferredFeatureError` or equivalent;
- requesting an unknown rule ID is distinguishable from a deferred known rule;
- no Java involvement at runtime.

Do not implement whole-document overlap suppression/priority arbitration unless required for the selected Java oracle boundary. That belongs to later full checker integration.

---

# Phase 9 — Java grammar-core oracle

Extend the existing trusted Java oracle instead of inventing expected output in Python.

Commit:

```text
tests/fixtures/oracle_russian_grammar_core.json
```

The fixture must be bound to exact:

```text
pinned_lt_version
pinned_lt_commit
oracle_build_id
oracle_jar_sha256
```

and tests must resolve those fields through `compat/oracle_manifest.json`, as Tasks 0005/0006 do.

## Oracle boundary

The Java harness must be able to run a **specific Russian pattern rule** against a text/sentence, independently enough that unrelated Java rules do not contaminate expected output.

Acceptable approaches include a pinned `PatternRuleLoader`/pattern-rule harness or a `JLanguageTool` harness that explicitly isolates/enables the target pattern rule.

Do not merely run all LT rules and hope a target ID is unique in the output.

For each oracle case capture at least:

```text
input text
target full rule ID
rule source order/category/default metadata
matched/not matched
match count
for each match:
  from/to UTF-16
  full pattern from/to if observable
  message
  short message
  suggestions in exact order
```

When Java exposes only part of this directly, document which fields are oracle-proven and which are internal derivations.

## Corpus selection

Use the Phase-0 classifier to select cases systematically.

Minimum requirements:

- at least 60 Java differential grammar-core cases;
- at least one core rule from every category that has a core-runnable rule;
- literal token match;
- case-insensitive and case-sensitive cases;
- text regexp;
- POS exact;
- POS regexp;
- inflected;
- negate;
- negate_pos;
- combined text+POS;
- current-token exception;
- marker subset span;
- no-marker full span;
- basic `<match no>` in message;
- basic `<match no>` in suggestion;
- multiple suggestions if a core-runnable rule contains them;
- correct/non-matching pair;
- SENT_START/SENT_END if core-runnable;
- ambiguous readings;
- emoji/non-BMP before the match for UTF-16/codepoint offset proof;
- default-off rule metadata if any core-runnable default-off rule exists.

Prefer real `grammar.xml` examples. Add synthetic inputs only to isolate semantics not adequately covered by real examples.

---

# Phase 10 — Grammar example conformance for core subset

`RussianPatternRuleTest` delegates to LanguageTool's `PatternRuleTest`, so embedded `grammar.xml` examples are a major upstream test asset.

Task 0007 must execute **all examples associated with `CORE_0007_RUNNABLE` rules**.

For each target rule:

```text
incorrect example:
  target rule must produce the expected target-rule match according to pinned example semantics

correct example:
  target rule must not produce a target-rule match
```

Where an example contains `<marker>` or correction metadata, preserve and validate all semantics that belong to the Task-0007 formatter subset.

Do not count examples belonging to deferred rules as failed or passed. Count them explicitly as `NOT_YET_RUNNABLE` with blocker/task classification.

Update machine-readable metrics:

```text
core_examples_total
core_examples_passed
core_examples_failed
deferred_examples_total
examples_by_target_task
```

Acceptance requires:

```text
core_examples_failed == 0
```

Do not claim `2446/2446` until later tasks actually support the remaining features.

---

# Phase 11 — Upstream core test ports

Port/translate the relevant subset of upstream tests rather than relying only on custom tests.

At minimum inspect and inventory assertions from:

```text
PatternRuleLoaderTest.java
PatternRuleMatcherTest.java
PatternRuleTest.java
RussianPatternRuleTest.java
```

Create Python tests for the Task-0007 feature surface.

Do not mechanically port tests for 0008/0009/0010 features and then skip them. Record them as deferred in the test inventory.

Synthetic tests are still required for semantic boundaries that the Russian upstream examples do not distinguish clearly.

---

# Phase 12 — Package/wheel proof

Build a real wheel and install it into an isolated target directory as in Tasks 0004/0006.

Verify explicitly inside the wheel:

```text
Russian grammar.xml
all pre-existing runtime morphology/disambiguation/synthesis resources required by the smoke path
```

Run an isolated subprocess with repository `src/` and `third_party/` unavailable.

The smoke must prove at least:

```text
import pylat_ru
construct RussianChunker / RussianGrammarEngine
analyze a Russian sentence
chunk it
load grammar.xml from installed package
execute one real CORE_0007_RUNNABLE rule
obtain exact expected rule ID/span/message/suggestion behavior
```

Do not use `PYTHONPATH=src` and call that an installed-package test.

---

# Phase 13 — Compatibility accounting

Update `compat/compatibility.json` honestly.

At minimum:

## Pipeline

```text
RussianChunker: SUPPORTED
XMLRuleEngine: PARTIAL_CORE_0007
```

Do not mark `XMLRuleEngine: SUPPORTED` globally.

## XML constructs

Replace the old coarse counts with a generated feature table where possible:

```text
feature
usage_count
rules_affected
status
implemented_in_task
deferred_to_task
notes
```

Expected statuses include:

```text
SUPPORTED_CORE
DEFERRED_0008
DEFERRED_0009
DEFERRED_0010
DEFERRED_0012
```

## Rules

Record:

```text
grammar_rules_total = 892
core_0007_runnable_rules
advanced_0008_rules
unification_0009_rules
filter_0010_rules
spelling/suppression-deferred rules
multi-blocker rules
unknown/unclassified = 0
```

Do not force these buckets to sum naïvely if blockers overlap; provide both primary classification and blocker counts.

## Examples

Record exact Task-0007 core example coverage and deferred counts.

## Carry-over consistency

Reconcile stale summary metrics with the accepted previous tasks.

In particular, Task 0006 ended with 52 committed synthesizer oracle queries, so do not retain an obsolete `synthesizer_oracle_queries_total: 34` merely because an older compatibility file said so.

Any other stale count discovered during Task 0007 should be corrected from canonical current artifacts, with the correction documented in the report.

---

# Required tests

At minimum create/extend tests covering these groups.

## Inventory

- deterministic byte-exact grammar-core inventory regeneration;
- exact grammar.xml size/hash;
- no unknown/unclassified rules;
- every rule has non-empty resolved full ID;
- rule full IDs/source order deterministic;
- blocker classification deterministic;
- current compatibility counts derived from inventory, not duplicated magic constants.

## Chunker

- exact Java differential fixture parity;
- every extracted expression/operator accounted for;
- REGEXES1/REGEXES2 order;
- overwrite semantics;
- `O` removal;
- FILTER_TAGS behavior;
- existing unrelated chunk preservation;
- MayMissingYO exclusion;
- whitespace preservation;
- exact chunk ordering;
- metadata/readings unchanged except chunks.

## XML loader

- complete pinned grammar.xml parses;
- all 892 rules loaded;
- 297 rulegroups;
- 8 categories;
- examples preserved;
- malformed XML typed failure;
- unknown element failure;
- unknown attribute failure;
- known element in invalid parent failure;
- unsupported feature creates explicit deferred rule, never silent runnable rule;
- corrupt packaged grammar fails without checkout fallback.

## Core matching

- literal text;
- regexp text;
- case sensitivity;
- POS exact;
- POS regexp;
- inflected;
- null lemma behavior;
- text negation;
- POS negation;
- combined predicates;
- current exception;
- marker span;
- no-marker span;
- ambiguous readings;
- SENT_START/SENT_END if active;
- Java-regex incompatibility failure rather than silent semantic drift.

## Formatter/findings

- plain message;
- short message;
- one suggestion;
- multiple suggestions;
- basic `<match no>`;
- match inside suggestion;
- marker source span;
- full pattern span;
- UTF-16 offsets;
- Python codepoint offsets;
- emoji before match;
- suggestion order;
- basic case-adjustment parity or explicit rule deferral.

## Rule state

- source-order execution;
- group/default inheritance;
- explicit force-run for target-rule tests;
- ordinary core batch respects default state;
- deferred rule execution raises typed error;
- unknown rule ID distinct from deferred rule ID.

## Upstream examples

- all examples belonging to core-runnable rules execute;
- zero failures in that subset;
- deferred examples counted explicitly by blocker phase.

## Packaging

- wheel contains grammar.xml;
- isolated installed-wheel core rule smoke passes;
- no Java/JRE at production runtime;
- no `third_party` runtime dependency.

---

# Performance expectations

Parity first, but avoid obviously pathological architecture.

Requirements:

- parse grammar.xml once per long-lived grammar engine;
- compile regexes once;
- create immutable or effectively immutable rule definitions after load;
- do not deep-copy all 892 rule objects per sentence;
- do not reload dictionaries/chunker resources per rule;
- preserve source-order rule list;
- allow direct full-ID lookup without O(892) scans if trivial to index;
- do not pre-expand the whole grammar into millions of token variants.

No optimization may change observable Java parity.

---

# Compatibility / fail-closed rules

Task 0007 is especially vulnerable to fake progress by silently skipping XML.

The following are forbidden:

```text
except Exception: pass
unknown child: continue
unsupported attr: ignore
filter present: run rule without filter
unification present: run rule without unification
advanced match present: substitute token text anyway
antipattern present: ignore antipattern
skip/min/max present: treat as sequential exactly-one token
chunk present: ignore chunk predicate
```

The correct behavior for a recognized future feature is:

```text
load metadata
classify rule deferred
report exact blocker
refuse direct execution
```

The correct behavior for an unknown/unclassified feature is:

```text
raise compatibility error
```

---

# Java oracle integrity

All new Task-0007 Java fixtures must use the established trusted-oracle mechanism.

Required metadata:

```text
pinned_lt_version
pinned_lt_commit
oracle_build_id
oracle_jar_sha256
```

Tests must resolve `oracle_build_id` against `compat/oracle_manifest.json` and require exact version/commit/SHA equality.

Do not add a second loose SHA allow-list.

Do not silently regenerate fixtures with a different local JAR.

Fixture generation must fail closed when the configured JAR does not match the selected trusted build record.

---

# Completion artifacts

Task 0007 must produce at least:

```text
tasks/0007_xml_grammar_engine_core.md                # this file
reports/0007_xml_grammar_engine_core.md

tools/russian_grammar_core_inventory.py
compat/russian_grammar_core_inventory.json

tests/fixtures/oracle_russian_chunker.json
tests/fixtures/oracle_russian_grammar_core.json

src/pylat_ru/chunking/...
src/pylat_ru/grammar/...
src/pylat_ru/resources/rules/ru/grammar.xml
```

Exact implementation filenames may differ, but equivalent artifacts are required.

---

# Completion report requirements

Create:

```text
reports/0007_xml_grammar_engine_core.md
```

Include at minimum:

## Pin/provenance

- LT version/tag/commit;
- grammar.xml size/SHA;
- RussianChunker.java size/SHA;
- core pattern-engine source hashes used for compatibility analysis;
- oracle build ID/SHA.

## Grammar inventory

- 892 total rule proof;
- category/rulegroup counts;
- exact core-runnable count;
- exact primary/deferred classification counts;
- blocker counts by feature/task;
- zero unknown/unclassified proof;
- exact core/deferred example counts.

## Chunker

- expression counts/order;
- operator/predicate subset implemented;
- oracle case count;
- exact chunker parity result.

## Grammar engine

- supported core token features;
- supported exception subset;
- formatter subset;
- finding fields/offset semantics;
- default-rule semantics;
- Java grammar oracle case count and parity.

## Examples/tests

- core grammar examples passed/failed;
- deferred examples count;
- upstream translated test count;
- complete repository pytest total;
- no required hidden skips.

## Packaging

- wheel proof and packaged grammar resource verification.

## Known limitations

List every deliberately deferred feature family and target task.

## Git completion

Record:

```text
implementation commit SHA
push target branch
remote verification result
```

Do not claim Task 0007 complete before the pushed commit is visible remotely.

---

# Acceptance criteria

Task 0007 is accepted only if all of the following are true.

1. LT pin remains exactly `e807fcde6a6506191e1470744d2345da28c26be6` / v6.8.
2. Production runtime remains Java-free.
3. Pinned RussianChunker source is inventoried with SHA/provenance.
4. Pinned grammar.xml is inventoried with exact SHA/provenance.
5. grammar.xml packaged runtime copy is byte-identical to pinned upstream.
6. Installed wheel contains grammar.xml.
7. RussianChunker is implemented natively in Python.
8. RussianChunker does not require Java/OpenRegex at runtime.
9. Chunker inventory extracts exact REGEXES1 order.
10. Chunker inventory extracts exact REGEXES2 order.
11. Chunker inventory extracts exact phrase types.
12. Chunker inventory extracts exact overwrite flags.
13. Chunker inventory extracts exact expression syntax surface used.
14. Unknown chunk-expression syntax fails explicitly.
15. Chunker ignores whitespace as pinned Java does.
16. Chunker handles MayMissingYO exclusion exactly.
17. Chunker preserves unrelated existing chunks.
18. Chunker overwrite removes only pinned FILTER_TAGS.
19. Chunker removes `O` when a real tag is added.
20. Chunk-tag order matches Java oracle.
21. Post-chunker token/readings metadata is otherwise preserved.
22. Chunker Java fixture uses trusted oracle build binding.
23. Chunker fixture captures isolated post-hybrid and post-chunker boundaries.
24. Chunker differential corpus covers every expression class.
25. Chunker differential parity is exact on committed fixture.
26. Complete grammar-core inventory is generated deterministically.
27. Inventory regenerates byte-for-byte.
28. All 8 grammar categories are loaded.
29. All 297 rulegroups are loaded.
30. All 892 rules are loaded.
31. All 2446 examples remain represented in inventory/model.
32. Every rule has deterministic source order.
33. Every rule has a non-empty resolved full ID.
34. Java full-ID semantics are independently verified.
35. Rule/group default metadata is preserved.
36. Rule/group tags metadata is preserved.
37. Category association is preserved.
38. Every active XML element in pinned grammar has a known disposition.
39. Every active XML attribute in pinned grammar has a known disposition.
40. Unknown/unclassified rule count is zero.
41. Deferred rules carry explicit blocker lists.
42. Deferred blockers name target roadmap tasks.
43. Direct execution of deferred rule raises typed error.
44. Unknown rule ID is distinguishable from deferred rule ID.
45. Loader validates allowed child elements per parent context.
46. Loader validates supported/known attributes per element context.
47. Malformed XML raises typed format/resource error.
48. Corrupt packaged grammar does not fall back silently to third_party.
49. Production grammar parsing performs no network fetch.
50. Core matching uses post-disambiguation/post-chunker non-whitespace tokens.
51. `raw_pos` rules are not falsely executed as normal core rules.
52. Literal text core matching matches Java.
53. Text-regexp core matching matches Java.
54. Core case sensitivity matches Java.
55. Exact POS matching matches Java.
56. POS-regexp matching matches Java.
57. Inflected/lemma matching matches Java for proven core cases.
58. Null-lemma edge behavior is proven.
59. Text negation matches Java.
60. POS negation matches Java.
61. Combined text/POS reading semantics are proven with ambiguous readings.
62. Current-token core exceptions match Java.
63. Advanced/scoped exception behavior is deferred if not implemented.
64. Marker-based finding span matches Java.
65. No-marker finding span matches Java.
66. Full pattern span is retained separately from marker span.
67. SENT_START/SENT_END core behavior is correct if used.
68. UTF-16 offsets match Java.
69. Codepoint offsets map to exact Python source substrings.
70. Non-BMP/emoji offset regression passes.
71. Plain message formatting matches Java for core subset.
72. Short-message formatting matches Java for core subset.
73. Basic suggestions match Java in exact order.
74. Basic `<match no>` substitution matches Java.
75. Complex match transforms are not silently approximated.
76. Basic case-adjustment is either proven or affected rules are deferred.
77. suppress-misspelled rules are not falsely treated as fully supported.
78. Core rule execution preserves grammar source order.
79. Ordinary core batch mode respects default metadata.
80. Target-rule test mode can execute explicitly selected core rule.
81. Java grammar fixture uses exact trusted build ID/SHA binding.
82. Java grammar oracle isolates target pattern rules from unrelated Java rules.
83. At least 60 meaningful grammar-core differential cases are committed.
84. Every supported core feature class has Java differential coverage.
85. Grammar-core fixture parity is exact.
86. Every example belonging to a core-runnable rule is executed.
87. Core incorrect examples pass target-rule expectations.
88. Core correct examples do not trigger target rule.
89. Core example failures equal zero.
90. Deferred examples are counted, not skipped invisibly.
91. Relevant PatternRuleLoader/Matcher upstream tests are inventoried.
92. Relevant Task-0007 upstream semantics are translated into Python tests.
93. Full Task 0001–0007 pytest suite passes.
94. No required Task-0007 parity test is skipped.
95. Real wheel is built in tests.
96. Isolated installed-wheel grammar smoke passes.
97. Installed-wheel smoke does not import repo `src/` or `third_party/`.
98. `compat/compatibility.json` marks RussianChunker supported.
99. `compat/compatibility.json` marks XML engine only partial/core, not fully supported.
100. Compatibility records exact core/deferred rule counts.
101. Compatibility records exact core/deferred example counts.
102. Compatibility stale Task-0006 oracle count is reconciled to current canonical fixture count.
103. No XML filter is claimed implemented by Task 0007.
104. No unification is claimed implemented by Task 0007.
105. No advanced matching feature is claimed implemented unless explicitly proven.
106. No Java rule is implemented accidentally as part of this task.
107. Completion report records all exact counts and known limitations honestly.
108. Completion report records oracle build ID/SHA.
109. Completion report records full test totals.
110. Completion diff contains no unrelated changes.
111. Task completion is committed.
112. Current branch is pushed to origin.
113. Remote completion commit is verified.
114. Task 0008 is not started automatically.

---

# Suggested implementation sequence

```text
1. Read AGENTS/handoff/accepted reports
2. Reconcile current compatibility baseline
3. Build Task-0007 grammar + chunker inventory
4. Classify all 892 rules and prove zero unknown dispositions
5. Port RussianChunker exact pinned subset
6. Build chunker Java oracle + fixture parity
7. Package exact grammar.xml
8. Implement fail-closed grammar loader/model
9. Implement rule IDs/default/tags/category inheritance
10. Implement core token matcher
11. Implement core current-token exceptions + marker spans
12. Implement basic formatter/suggestions
13. Implement internal core engine + deferred-rule guardrails
14. Extend trusted Java grammar oracle
15. Generate committed grammar-core fixture
16. Run exact grammar differential tests
17. Execute all core-runnable grammar examples
18. Port relevant upstream pattern loader/matcher tests
19. Build/install real wheel and run isolated grammar smoke
20. Regenerate compatibility artifacts
21. Run complete 0001–0007 suite
22. Write completion report
23. git diff/status review
24. commit
25. push current branch to origin
26. verify remote commit
27. stop; do not start 0008
```

---

# Final scope boundary

At the end of Task 0007 the project must be able to truthfully say:

```text
Russian tokenization                 ✅
Russian morphology/tagging           ✅
Russian disambiguation               ✅
Russian post-disambiguation chunker  ✅
Russian synthesis                    ✅
Russian grammar.xml structural load  ✅ all 892 rules classified
Russian grammar core execution       ✅ exact, measured subset
Advanced pattern matching            ⛔ 0008
Unification                          ⛔ 0009
XML filters                          ⛔ 0010
Java rules                           ⛔ 0011
Spelling/compound/etc.               ⛔ 0012
Full 2446-example parity             ⛔ later
```

The key result is **not** "some grammar rules now work".

The result is:

```text
every pinned Russian grammar rule is known,
every unsupported feature is explicitly accounted for,
and the rules claimed as CORE_0007_RUNNABLE behave like pinned Java LanguageTool.
```

That gives Task 0008 a measurable input instead of another archaeological expedition through a 1.2 MB XML file.
