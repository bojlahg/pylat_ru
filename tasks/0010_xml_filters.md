# Task 0010 — Native XML Rule Filters

## Status

**ACTIVE TASK SPECIFICATION**

Do not start Task 0011 or Task 0012 while implementing this task.

---

# 1. Goal

Implement the **native Python grammar-rule filter layer** required by the pinned Russian LanguageTool `grammar.xml`, preserving the observable behavior of LanguageTool `v6.8` at commit:

```text
e807fcde6a6506191e1470744d2345da28c26be6
```

Task 0010 extends the accepted Task-0009 XML grammar engine from:

```text
pattern match
→ unification
→ formatted RuleMatch
```

to the pinned LanguageTool flow:

```text
pattern match
→ unification
→ marker / full-pattern span calculation
→ message / short-message / suggestion formatting
→ provisional RuleMatch
→ XML RuleFilter argument resolution
→ concrete native filter
→ keep / reject / modify RuleMatch
→ final Python finding
```

This is an **exact compatibility task**, not a generic plugin/filter framework exercise.

The result must execute every Russian grammar filter whose complete pinned behavior can be implemented using components already accepted through Task 0009, while explicitly keeping spelling-dependent behavior deferred to Task 0012.

---

# 2. Baseline

Task 0009 is accepted.

Accepted semantic closure commit:

```text
762ae1e5ce8174f12b1532d0c6212c08b72c9889
```

Repository CI/provenance fixes after Task 0009 are also part of the working baseline. At specification time current `main` is:

```text
6f2779750442817038555445d406266454da2ca6
```

Do not revert or rewrite those CI/provenance fixes.

Pinned grammar source:

```text
third_party/languagetool/
  languagetool-language-modules/ru/src/main/resources/
  org/languagetool/rules/ru/grammar.xml
```

Canonical SHA-256:

```text
e9bfa390cc417b07a72a762b14097451892355172d65dbe80e979251da2647ec
```

Accepted Task-0009 source-rule state:

```text
CORE_0007_RUNNABLE                         506
ADVANCED_0008_RUNNABLE                     229
UNIFICATION_0009_RUNNABLE                   24
DEFERRED_0010_FILTER                        20
DEFERRED_0012_SPELLING_OR_SUPPRESSION      110
MULTI_BLOCKER                                3
UNKNOWN                                      0
-----------------------------------------------
TOTAL                                      892

runnable                                  759
deferred                                  133
```

Accepted Task-0009 examples:

```text
all examples        2446
runnable            1954
  incorrect          878
  correct           1076
deferred             492
  incorrect          161
  correct             331
```

All 0001–0009 accepted behavior must remain passing.

---

# 3. Exact Russian filter inventory at the Task-0009 baseline

The pinned Russian grammar contains exactly:

```text
<filter> elements       23
filter@class attrs      23
filter@args attrs       23
```

Grammar filter class references:

```text
org.languagetool.rules.ru.AdvancedSynthesizerFilter                 4
org.languagetool.rules.ru.DateCheckFilter                           2
org.languagetool.rules.ru.FutureDateFilter                          2
org.languagetool.rules.ru.INNNumberFilter                           1
org.languagetool.rules.ru.RussianPartialPosTagFilter               13
org.languagetool.rules.ru.RussianSuppressMisspelledSuggestionsFilter 1
---------------------------------------------------------------------
TOTAL                                                               23
```

These 23 references belong to 23 filter-bearing source rules:

- 20 currently `DEFERRED_0010_FILTER`;
- 3 currently `MULTI_BLOCKER` because they have both a filter blocker and a Task-0012 spelling/suppression blocker.

The project-wide `xml_filters_total = 7` additionally includes:

```text
NoDisambiguationRussianPartialPosTagFilter
```

used by `disambiguation.xml`.

That filter was already implemented and accepted in Task 0005. Task 0010 must preserve it, not reimplement/reclassify the accepted disambiguation subsystem.

Create a deterministic Task-0010 inventory that proves these counts directly from the pinned XML and reconciles them with source-rule IDs, examples, filter classes, exact `args`, existing blockers, and resulting Task-0010 states.

---

# 4. Important scope boundary: spelling-dependent filter remains Task 0012

`RussianSuppressMisspelledSuggestionsFilter` is a thin Russian subclass of pinned:

```text
AbstractSuppressMisspelledSuggestionsFilter
```

The generic implementation calls:

```text
language.getDefaultSpellingRule()
```

and uses the real spelling checker to determine whether generated suggestions are misspelled.

A native exact Russian spelling checker is intentionally scheduled for Task 0012.

Therefore Task 0010 MUST NOT approximate this behavior using:

- tagger dictionary membership;
- `RussianTagger` unknown-token status;
- a Python word list;
- edit distance;
- regex heuristics;
- the synthesis dictionary;
- a hard-coded allow/deny list;
- Java/LanguageTool at production runtime.

For Task 0010:

1. parse and recognize `RussianSuppressMisspelledSuggestionsFilter` exactly;
2. inventory its exact XML args and affected rule;
3. preserve its source structure and provenance;
4. classify its rule as `DEFERRED_0012_SPELLING_OR_SUPPRESSION` with an explicit blocker explaining the native spelling dependency;
5. do not execute that rule publicly in Task 0010;
6. include differential/audit fixtures as useful to document future Task-0012 behavior, but do not claim production support.

This is intentional scope control, not an implementation failure.

---

# 5. Expected Task-0010 state transition

Subject to exact inventory reconciliation, Task 0010 must produce:

```text
CORE_0007_RUNNABLE                         506
ADVANCED_0008_RUNNABLE                     229
UNIFICATION_0009_RUNNABLE                   24
FILTER_0010_RUNNABLE                        19
DEFERRED_0010_FILTER                         0
DEFERRED_0012_SPELLING_OR_SUPPRESSION      114
MULTI_BLOCKER                                0
UNKNOWN                                      0
-----------------------------------------------
TOTAL                                      892

runnable                                  778
deferred                                  114
```

Explanation:

- 19 of the 20 Task-0009 filter-only rules become runnable;
- the one `RussianSuppressMisspelledSuggestionsFilter` rule moves to Task 0012;
- the 3 Task-0009 multi-blocker rules lose their filter blocker but retain their Task-0012 blocker, therefore become ordinary `DEFERRED_0012_SPELLING_OR_SUPPRESSION` rules;
- no Task-0010 filter blocker remains after this task;
- no `MULTI_BLOCKER` remains solely because of Task-0010 filters.

Add an explicit execution state:

```text
FILTER_0010_RUNNABLE
```

Do not flatten prior provenance states into one generic `RUNNABLE` state.

If exact pinned-source inventory disproves any numeric assumption above, STOP before changing classification, record the discrepancy with exact rule IDs/source evidence, and resolve it against the pinned source rather than silently editing the expected numbers.

---

# 6. Non-goals

Task 0010 does NOT implement:

- Java rules registered by `Russian.java` — Task 0011;
- Russian spellchecker / Morfologik spelling — Task 0012;
- `suppress_misspelled` message/suggestion semantics requiring spelling — Task 0012;
- compounds / replace / repetition rule families scheduled later;
- LanguageTool server or Java production runtime;
- a generic third-party Python plugin API;
- remote filters;
- filters for non-Russian languages;
- NLP replacement libraries.

Do not start Task 0011/0012 merely to make a deferred rule green.

---

# 7. Pinned upstream sources that must be audited

Use only the pinned LT commit. Narrowly vendor missing source/test files needed for implementation/conformance, byte-exact, with provenance/SHA/license metadata.

At minimum audit and, when not already vendored, vendor the exact relevant pinned files:

```text
languagetool-core/src/main/java/org/languagetool/rules/patterns/RuleFilter.java
languagetool-core/src/main/java/org/languagetool/rules/patterns/RuleFilterEvaluator.java
languagetool-core/src/main/java/org/languagetool/rules/AbstractAdvancedSynthesizerFilter.java
languagetool-core/src/main/java/org/languagetool/rules/AbstractDateCheckFilter.java
languagetool-core/src/main/java/org/languagetool/rules/AbstractFutureDateFilter.java
languagetool-core/src/main/java/org/languagetool/rules/PartialPosTagFilter.java
languagetool-core/src/main/java/org/languagetool/rules/AbstractSuppressMisspelledSuggestionsFilter.java

languagetool-core/src/test/java/org/languagetool/rules/patterns/RuleFilterEvaluatorTest.java

languagetool-language-modules/ru/src/test/java/org/languagetool/rules/ru/DateCheckFilterTest.java
```

Already-vendored Russian implementations to use as canonical references:

```text
AdvancedSynthesizerFilter.java
DateCheckFilter.java
DateFilterHelper.java
FutureDateFilter.java
INNNumberFilter.java
RussianPartialPosTagFilter.java
RussianSuppressMisspelledSuggestionsFilter.java
NoDisambiguationRussianPartialPosTagFilter.java
```

Also audit the exact filter call site in pinned:

```text
PatternRuleMatcher.createRuleMatch(...)
```

Do not rely on documentation/Javadocs when implementation differs. Pinned Java code wins.

Vendored files are under the repository-wide byte-preservation policy:

```text
third_party/languagetool/** -text
```

Do not normalize line endings or silently regenerate upstream source files.

---

# 8. Core filter architecture

Implement a native Python filter subsystem under the grammar package, recommended shape:

```text
src/pylat_ru/grammar/filters/
  base.py
  evaluator.py
  registry.py
  advanced_synthesizer.py
  date_check.py
  future_date.py
  inn.py
  partial_pos.py
```

Exact file layout may differ, but responsibilities must remain explicit.

Required concepts:

```text
RuleFilter
RuleFilterEvaluator
FilterRegistry
FilterContext / equivalent match-local input
```

The production registry must map **exact pinned class names** to native implementations.

Unknown class names must fail closed with the existing structured compatibility error. Never silently pass through an unknown filter.

Do not dynamically import arbitrary Python based on XML `class` values.

---

# 9. Exact filter execution point

Pinned `PatternRuleMatcher` applies a filter only after a provisional rule match has been created.

Python must mirror this order:

1. pattern candidate succeeds;
2. advanced matching/unification succeeds;
3. marker and full pattern spans are known;
4. message, short message, and suggestions are formatted;
5. provisional match is created;
6. `filter@args` are resolved against matched pattern tokens/token positions;
7. concrete filter executes;
8. filter may:
   - return `None` / reject the finding;
   - return the original finding;
   - return a modified finding;
9. only then expose the final `RuleMatchResult`.

Do not run filters before formatting merely because that is architecturally convenient. `AdvancedSynthesizerFilter` operates on existing suggestions and date filters modify an already-formatted message.

Do not mutate the shared analyzed sentence or compiled rule.

---

# 10. Match-local filter context

A filter needs the pinned-equivalent inputs:

```text
provisional rule match
resolved args
patternTokenPos / first matched token position
patternTokens covering firstMatchToken..lastMatchToken inclusive
tokenPositions from the physical pattern match
rule/language access needed for tagger/synthesizer
```

Preserve:

- source token text;
- lexical readings and order;
- start/end offsets;
- whitespace-before state;
- chunk tags;
- sentence-start/end metadata;
- original marker span;
- full-pattern span;
- physical tokenPositions including skip/min/max effects.

A filter must not receive a re-tokenized substring when pinned Java receives the actual matched ATR slice.

---

# 11. RuleFilterEvaluator argument resolution

Port pinned `RuleFilterEvaluator.getResolvedArguments()` semantics exactly.

`filter@args` behavior:

- split arguments on Java-equivalent `\s+`;
- each argument must contain `:`;
- key = text before the first `:`;
- value = remaining text after the first `:`;
- literal values remain literal;
- values beginning with `\` are token backreferences;
- backreferences are 1-based XML pattern references;
- references are corrected through `tokenPositions` for skipped/optional/repeated elements exactly as pinned Java;
- out-of-range references throw the pinned-equivalent explicit error;
- duplicate backreference keys follow pinned Java failure behavior;
- literal duplicate keys follow pinned Java `Map.put` behavior, not an invented stricter rule;
- no URL-decoding, shell parsing, quote parsing, escaping heuristics, or whitespace normalization not present upstream.

Port all applicable assertions from pinned `RuleFilterEvaluatorTest.java` and report source-method → Python-test → assertion counts separately.

Required synthetic cases include:

- one literal arg;
- multiple literal args;
- value containing additional `:`;
- direct `\1`, `\2`, etc.;
- skipped token reference;
- optional token present/absent reference;
- repeated token reference;
- reference exactly at last pattern element;
- too-large reference;
- malformed no-colon argument;
- duplicate backref key;
- literal duplicate key;
- non-BMP token used by a resolved backreference.

---

# 12. Base RuleFilter utility semantics

Port only the generic helper behavior actually required by Russian filters, but do so exactly.

Cover at minimum:

```text
getRequired
getOptional(key)
getOptional(key, default)
getPosition
getSkipCorrectedReference
isMatchAtSentenceStart   if used by any pinned Russian filter path
```

`getPosition` must support pinned numeric and `marker...` forms, including exact bounds/error behavior.

Do not simplify marker-based positions to the rule's XML token number. They are calculated against matched tokens and provisional marker offsets.

---

# 13. Finding mutation model

Pinned filters may return a modified `RuleMatch`.

Python must support match-local modification without losing accepted finding fields.

A filter modification must preserve unless pinned filter changes it:

- `rule_id`;
- `full_rule_id`;
- category;
- description;
- marker codepoint offsets;
- marker UTF-16 offsets;
- full-pattern codepoint offsets;
- full-pattern UTF-16 offsets;
- matched token indices;
- marker token indices;
- rule type;
- source order.

Filters may modify:

- message;
- short message where upstream does;
- suggestions and order;
- URL if the public result model exposes it / must expose it for parity;
- match retention/rejection.

If `RuleMatchResult` needs a new optional field such as `url`, add it in a backward-compatible deterministic way and update exact tests. Do not discard a Java-visible field solely because the current Python dataclass did not previously model it.

---

# 14. `AdvancedSynthesizerFilter`

Implement the behavior of pinned Russian `AdvancedSynthesizerFilter` through pinned `AbstractAdvancedSynthesizerFilter` using the already accepted native `RussianSynthesizer`.

Required args:

```text
postagSelect
lemmaSelect
postagFrom
lemmaFrom
```

Optional args:

```text
newLemma      default ""
postagReplace
```

Required exact semantics:

- `postagFrom` and `lemmaFrom` accept numeric or marker-based positions;
- bounds errors match pinned behavior;
- select the **first ATR reading whose POS fully matches** the selector regex;
- if no reading matches, pinned helper falls back to the first reading — preserve this odd behavior;
- desired lemma comes from `lemmaFrom` reading;
- desired POS comes from `postagFrom` reading;
- null desired lemma rejects the match;
- null desired POS raises the pinned-equivalent explicit error;
- `postagReplace` combines capture groups from the two selector matches using `\aN` / `\bN` replacement semantics;
- synthesis uses native `RussianSynthesizer` with pinned regular-expression mode equivalent to Java's call;
- capitalization is derived from the lemma-source surface token;
- all-uppercase behavior is preserved;
- placeholders are supported exactly:
  - `{suggestion}`
  - `{Suggestion}`
  - `{SUGGESTION}`
- existing suggestion templates are expanded in pinned nested-loop order;
- replacements are deduplicated in first-occurrence order exactly where Java deduplicates;
- if no placeholder is present, synthesized forms are appended as pinned Java does;
- if synthesis yields no forms, return the original provisional match;
- Russian subclass does not override `getNewLemma`; therefore an underscore-prefixed `newLemma` must follow the pinned inherited behavior, not an invented implementation.

Add direct Java differential tests for the filter itself and full real-rule execution.

Mandatory discriminating cases:

- distinct lemma and POS source tokens;
- multiple readings where selector chooses a non-first reading;
- no selector match → first-reading fallback;
- marker position;
- marker offset position where present;
- numeric position;
- `postagReplace` with both `\a1` and `\b1` groups;
- lower-case lemma source;
- capitalized source;
- all-uppercase source;
- each suggestion placeholder casing;
- no suggestion placeholder;
- duplicate synthesized outputs/order;
- no synthesis output;
- null lemma;
- null POS;
- invalid source index.

The 4 previously `unify + AdvancedSynthesizerFilter` / filter-bearing rules must execute through the accepted unifier and then this filter without any separate special-case path.

---

# 15. `DateCheckFilter`

Port pinned Russian `DateCheckFilter` plus the required generic `AbstractDateCheckFilter` behavior.

Russian weekday mapping must follow code, including abbreviations/prefix behavior.

Russian month mapping must follow code exactly, including:

- Russian nominative/genitive forms used upstream;
- abbreviations;
- Roman numerals `I`..`XII`;
- pinned odd abbreviations such as the exact June/July forms present in source.

Generic args:

```text
weekDay   required
month     required
day       required
year      optional
```

Required behavior:

- remove soft hyphen from `weekDay` as pinned;
- parse numeric or localized months as pinned;
- parse numerical prefix of day strings using pinned `(\d+).*` semantics;
- construct a strict/non-lenient date;
- invalid dates do not create a finding;
- if claimed weekday matches actual weekday: reject finding;
- if it differs: return modified finding;
- replace in message:
  - `{realDay}`
  - `{day}`
  - `{currentYear}`
- preserve short message and rule type;
- preserve offsets;
- expose/set the pinned calendar URL if it is an observable LT field supported by our result boundary.

Translate every active assertion from pinned Russian `DateCheckFilterTest.java`.

## 15.1 Time determinism

Pinned date code has behavior depending on current year when `year` is omitted.

Production default must follow pinned runtime current-calendar semantics, but tests/fixtures must not become wall-clock flaky.

Provide an explicit internal clock/date provider or equivalent injection boundary used by tests.

Do not globally monkeypatch Python's datetime module.

For differential fixtures:

- prefer cases with explicit year for stable Java/Python comparison;
- if testing omitted-year behavior, pin the Java side and Python side to an equivalent controlled date or explicitly use pinned LT test-mode semantics and record that mode in fixture metadata;
- do not commit fixtures whose expected answer changes next January.

---

# 16. `FutureDateFilter`

Port pinned Russian `FutureDateFilter`, `DateFilterHelper`, and required generic `AbstractFutureDateFilter` behavior.

Required args:

```text
year
month
day
```

Required behavior:

- localized month parsing via pinned Russian `DateFilterHelper`;
- exact trimming of special characters where pinned helper does it;
- strict date validation;
- future date → keep original provisional match;
- current/past date → reject match;
- invalid date → pinned-equivalent rejection/error behavior;
- exact year/month/day boundaries.

Use the same deterministic clock abstraction as DateCheckFilter.

Mandatory controlled cases:

- yesterday;
- today;
- tomorrow;
- leap-day valid/invalid;
- year boundary;
- Russian full month;
- Russian abbreviation;
- numeric month;
- special-character-trimmed month;
- impossible date.

Do not use fixture generation time as implicit expected state.

---

# 17. `INNNumberFilter`

Port pinned algorithm exactly.

Required arg:

```text
inn
```

Pinned behavior:

- input must match the pinned digit regex fully;
- 10-digit INN:
  - weights: `2,4,10,3,5,9,4,6,8`
  - modulo 11
  - result > 9 is reduced by 10
  - valid checksum → reject finding
  - invalid checksum → keep finding;
- 12-digit INN:
  - first checksum weights: `7,2,4,10,3,5,9,4,6,8`
  - second checksum weights: `3,7,2,4,10,3,5,9,4,6,8`
  - same modulo/reduction behavior
  - both valid → reject finding
  - otherwise keep finding;
- any other digit length → reject finding;
- malformed/non-digit input follows pinned behavior.

Mandatory Java differential cases:

- valid 10-digit;
- invalid 10-digit;
- valid 12-digit;
- first checksum wrong;
- second checksum wrong;
- both wrong;
- leading zero cases;
- empty string;
- 9/11/13 digits;
- ASCII non-digit;
- whitespace;
- Unicode digit characters that distinguish Java regex / numeric-value semantics if applicable.

Do not silently replace Java regex semantics with `str.isdigit()`.

---

# 18. `RussianPartialPosTagFilter`

Port pinned generic `PartialPosTagFilter` plus the Russian subclass behavior.

Required args:

```text
no
regexp
postag_regexp
```

Optional/presence-based args:

```text
negate_pos
two_groups_regexp
prefix
suffix
```

Important: follow **implementation**, not the stale Javadoc spelling. The pinned Java code checks `negate_pos` by key presence.

Required semantics:

- select matched `patternTokens[no - 1]`;
- prepend/append prefix/suffix before applying partial regexp;
- Java-equivalent full regex match;
- regexp must contain exactly 1 capture group unless `two_groups_regexp` key is present;
- with two groups, concatenate group 1 + group 2;
- tag the resulting partial token using the accepted native `RussianTagger`;
- then run the accepted native Russian disambiguator on a **single-token AnalyzedSentence**, matching the pinned Russian subclass;
- do not shortcut to raw Morfologik lookup;
- do not substitute the already accepted `NoDisambiguationRussianPartialPosTagFilter`, because that intentionally has different semantics;
- without `negate_pos`: keep match if any non-null POS reading fully matches `postag_regexp`;
- with `negate_pos` present: require at least one non-null POS and none may match;
- null POS readings are ignored exactly as pinned;
- zero non-null POS readings under negation do not pass.

Mandatory discriminating cases:

- one-group extraction positive/negative;
- two-group extraction;
- wrong capture-group count;
- prefix;
- suffix;
- prefix + suffix;
- `negate_pos` key present with value `yes`;
- `negate_pos` key present with some other literal value to prove presence semantics;
- positive POS among multiple readings;
- no matching POS;
- all POS nonmatching under negation;
- one POS matching under negation;
- null POS only;
- case where single-token Russian disambiguation changes the outcome relative to raw tagger output;
- regex Unicode/case behavior used by actual Russian XML.

Run every real grammar rule using this filter through end-to-end Java/Python parity.

---

# 19. `RussianSuppressMisspelledSuggestionsFilter` audit-only behavior

Parse and preserve this class and its args, but do not mark it production-supported in Task 0010.

Create an explicit registry state such as:

```text
RECOGNIZED_DEFERRED_0012
```

or equivalent structured blocker, rather than pretending the class is unknown.

Its exact future behavior should be documented from pinned `AbstractSuppressMisspelledSuggestionsFilter`, including:

```text
suppressMatch       required
SuppressPostag      optional, exact capitalization
```

and the dependency on:

```text
language.getDefaultSpellingRule()
```

The affected rule transitions to `DEFERRED_0012_SPELLING_OR_SUPPRESSION`.

Calling `check_rule()` for it in Task 0010 must raise the normal structured unsupported-feature error naming the remaining Task-0012 spelling dependency.

---

# 20. Filter registry and loader/classifier integration

The grammar loader already preserves `FilterConfig(class_name, args)`.

Task 0010 must:

- preserve exact source order and class strings;
- reject malformed `<filter>` structures as pinned/our strict loader policy requires;
- classify supported filter-bearing rules as `FILTER_0010_RUNNABLE` only when **all** remaining blockers are implemented;
- remove only the filter blocker from the three prior `MULTI_BLOCKER` rules, leaving their Task-0012 blocker;
- move the spelling-filter rule to Task 0012 rather than runnable;
- leave 0007/0008/0009 states unchanged for their accepted rules;
- ensure no unknown filter class is silently accepted.

`RussianGrammarEngine.get_runnable_rules()` and `check_sentence()` must execute:

```text
CORE_0007_RUNNABLE
ADVANCED_0008_RUNNABLE
UNIFICATION_0009_RUNNABLE
FILTER_0010_RUNNABLE
```

---

# 21. Interactions with advanced matching and unification

Filters receive the result of accepted Task-0008/0009 matching. Add exact integration coverage with all constructs that overlap real filtered rules, plus synthetic cases where needed:

- finite skip;
- `skip=-1`;
- optional `min=0`;
- finite/unlimited max;
- OR physical variants;
- exceptions;
- marker spans;
- match references;
- antipatterns;
- `raw_pos` where overlap exists;
- unification;
- `unify-ignore`;
- multiple suggestions;
- UTF-16/codepoint span conversion.

The 4 filter-bearing rules that also use unification are an especially important regression boundary: the filter must not re-run or mutate unification state.

No filter state may leak between:

- candidates;
- variants;
- rules;
- sentences;
- repeated engine calls.

---

# 22. Java differential oracle for filters

Extend the trusted dev-only Java oracle with dedicated filter operations.

Recommended canonical fixtures:

```text
tests/fixtures/oracle_filters_synthetic.json
tests/fixtures/oracle_filters_russian_rules.json
```

All fixtures must bind through `compat/oracle_manifest.json` to:

```text
LT version:       6.8
LT commit:        e807fcde6a6506191e1470744d2345da28c26be6
oracle build ID:  lt_6.8_source_build_jdk17_stefan
oracle JAR SHA:   b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc
```

Production runtime must not import/invoke Java or oracle code.

## 22.1 Low-level filter oracle

The Java helper must be capable of exercising a filter with controlled:

- provisional RuleMatch fields;
- ATR readings;
- patternTokens;
- tokenPositions;
- filter args;
- marker/pattern offsets;
- suggestion list;
- controlled current date where date semantics are tested.

Do not rely only on natural Russian text when a controlled ATR/tokenPositions case is needed to distinguish semantics.

## 22.2 Synthetic corpus

Create at least **120 distinct discriminating trusted-Java cases** across the executable Task-0010 filter surface.

Machine-readable coverage must map:

```text
feature_dimension -> case IDs
```

At minimum cover all mandatory cases listed in Sections 11–18.

Each case must carry an explicit semantic expectation such as:

```text
kept / rejected
expected suggestion count
expected message mutation
expected resolved args
```

where applicable.

Generator must fail if a case labeled as a positive modification/keep case actually produces no Java match. Do not repeat the Task-0009 mistake of treating labels as proof.

## 22.3 Real Russian rules

For all 19 expected newly runnable rules:

- run every embedded grammar example through Java and Python where the pinned oracle can execute it deterministically;
- compare exact target-rule findings;
- include at least one filter-pass and one filter-reject case per filter class where practical;
- record exact filter class and raw/resolved args;
- record whether the filter kept, rejected, or modified the provisional match.

For the one spelling-filter rule and three Task-0012-only rules:

- retain explicit deferred evidence;
- do not count them as Task-0010 runnable parity.

---

# 23. Exact fields to compare

For real end-to-end filter findings compare, where applicable:

- finding count and order;
- rule ID;
- full rule ID;
- category;
- marker codepoint offsets;
- marker UTF-16 offsets;
- full-pattern codepoint offsets;
- full-pattern UTF-16 offsets;
- exact marker source slice;
- exact pattern source slice;
- message;
- short message;
- suggestions including order and duplicates/deduplication behavior;
- URL when filter changes it and it is exposed;
- rule type;
- filter keep/reject/modify state in dedicated oracle evidence.

For low-level evaluator/filter cases also compare:

- resolved args map;
- selected token/reference index;
- selected ATR reading signature where relevant;
- post-filter suggestions;
- post-filter message.

Comparing only finding existence is insufficient for `AdvancedSynthesizerFilter` and `DateCheckFilter`.

---

# 24. Grammar embedded examples

After Task-0010 reclassification:

- all previously runnable 1,954 Task-0009 examples must remain passing;
- all examples belonging to the 19 newly runnable filter rules must be added to the runnable grammar-example suite;
- examples belonging to the spelling-filter rule and remaining Task-0012 rules stay deferred;
- regenerate exact runnable/deferred incorrect/correct totals from the pinned XML;
- record those exact totals in the Task-0010 inventory and `compat/compatibility.json`.

Do not guess or hand-maintain example totals independently in multiple places. Generate from canonical rule classification and assert arithmetic invariants.

Correct examples must produce zero target-rule findings.

Incorrect examples must validate target-rule behavior, exact marker span, and exact correction/suggestion behavior where the embedded example supplies such expectations.

---

# 25. Dedicated Task-0010 compatibility inventory

Create a deterministic generated artifact, recommended:

```text
compat/russian_grammar_filter_inventory.json
```

It must include at least:

```text
schema_version
pinned LT version/commit
grammar path/size/SHA
accepted Task-0009 baseline commit
source rules total = 892
raw filter elements = 23
raw class refs = 23
raw args attrs = 23
per-class reference counts
per-class affected full rule IDs
per-rule raw args
per-rule prior state
per-rule prior blockers
per-rule Task-0010 state
per-rule remaining blockers
per-rule example incorrect/correct counts
filter + unification overlap
filter + spelling/suppression overlap
filter + skip/min/max/marker/etc overlap
runnable/deferred totals
runnable/deferred example totals
unknown filter class count
spelling-dependent recognized-deferred count
synthetic oracle case count
real oracle case count
```

Required arithmetic invariants:

```text
filter refs by class sum to 23
filter-bearing source rules = 23
19 FILTER_0010_RUNNABLE
4 filter-bearing rules remain/move to Task 0012
Task-0010 runnable total = 778
Task-0010 deferred total = 114
778 + 114 = 892
UNKNOWN = 0
DEFERRED_0010_FILTER = 0
MULTI_BLOCKER = 0
```

If exact inventory proves a different rule relationship, fail the test and resolve against pinned source before proceeding.

---

# 26. `compat/compatibility.json`

Update compatibility metadata with explicit Task-0010 units, not only a vague `filters: supported` flag.

Record at minimum:

```text
grammar filter refs total = 23
grammar filter classes total = 6
Task-0005 disambiguation filter class = already supported
Task-0010 executable grammar filter classes = 5
Task-0012 spelling-dependent grammar filter classes = 1
FILTER_0010_RUNNABLE source rules = 19
total runnable source rules = 778
remaining deferred source rules = 114
DEFERRED_0010_FILTER = 0
DEFERRED_0012 = 114
MULTI_BLOCKER = 0
UNKNOWN = 0
runnable/deferred example incorrect/correct totals
per-filter real oracle case counts
synthetic filter oracle case count
real filter oracle case count
RuleFilterEvaluator translated source methods/functions/assertions
DateCheckFilterTest translated source methods/functions/assertions
wheel proof status
```

Keep Task-0007/0008/0009 historical evidence separately; do not overwrite prior milestone counts as though they never existed.

---

# 27. Error and fail-closed behavior

Add typed regressions for at least:

- unknown filter class;
- recognized but Task-0012-deferred spelling filter;
- missing `filter@class` if schema/parser can encounter it;
- missing/empty required args;
- malformed key/value arg;
- bad integer arg;
- bad token reference;
- marker source position out of bounds;
- bad partial-pos capture group count;
- invalid partial-pos regex;
- missing required partial-pos args;
- null POS source for advanced synthesizer;
- invalid advanced synthesizer source position;
- malformed `postagReplace` capture behavior;
- invalid date;
- unknown weekday/month behavior exactly as pinned;
- malformed INN;
- unsupported filter dependency.

No exception may be swallowed into an ordinary finding unless pinned Java explicitly swallows that class of failure.

No unknown behavior may silently return the original provisional match.

---

# 28. Time/locale correctness

Do not let host locale or timezone accidentally define Russian filter semantics.

Requirements:

- Russian weekday/month names are explicit and pinned;
- date arithmetic is deterministic under controlled tests;
- production current-date semantics are isolated behind one provider;
- CI in Ubuntu and local Windows must agree on deterministic fixtures;
- do not rely on OS Russian locale being installed;
- do not localize output using host locale APIs when pinned strings can be mapped exactly from source behavior.

Record the chosen timezone/date interpretation for controlled fixtures.

---

# 29. Performance and caching

Correctness first, but avoid obvious repeated work:

- filter class registry built once, not per finding;
- regexes that are static can be compiled once;
- do not reload morphology dictionaries per partial-pos filter invocation;
- use accepted singleton/cache lifecycle of RussianTagger/Disambiguator/Synthesizer;
- do not parse XML args at import if rule has not been loaded;
- do not invoke the full grammar engine recursively from a filter;
- do not copy the complete sentence when only a match-local token slice is needed.

Do not add caching that changes state isolation or ordering.

---

# 30. State isolation and concurrency

Filters must be safe across repeated calls and concurrent independent rule evaluations under the project's existing expectations.

Add regressions proving no state leakage across:

- keep → reject;
- reject → keep;
- modified suggestions → unmodified next match;
- modified message → next match;
- two rules using the same filter singleton/registry entry;
- two physical variants;
- two sentences;
- repeated engine singleton calls;
- AdvancedSynthesizerFilter after a unification-filtered candidate;
- PartialPosTagFilter after another call with a different extracted partial token;
- date filter calls with different injected clocks in isolated test instances.

Do not store current match args, tokens, suggestions, or clock state in shared filter class globals.

---

# 31. Real wheel / production-boundary proof

Extend the isolated wheel test.

Build/install the real wheel in a clean environment and execute at least:

- one `AdvancedSynthesizerFilter` real rule;
- one `RussianPartialPosTagFilter` real rule;
- one deterministic date/INN filter rule where practical;
- one previously accepted 0009 unification rule.

Guard production execution against:

```text
socket.socket
subprocess.Popen
subprocess.run
Java/JRE invocation
LanguageTool server/network
repository source import leakage
```

For at least one newly runnable filter finding assert exact:

- rule ID/full ID;
- codepoint offsets;
- UTF-16 offsets;
- full-pattern offsets;
- message;
- short message;
- suggestions and order.

Wheel must not contain oracle JARs, `.oracle_cache`, Java source build products, or temporary fixtures beyond canonical committed test assets.

---

# 32. Test execution and CI

Before completion run focused tests for:

```text
RuleFilterEvaluator
filter registry/classification
AdvancedSynthesizerFilter
DateCheckFilter
FutureDateFilter
INNNumberFilter
RussianPartialPosTagFilter
filter state isolation
filter inventory
real Russian filter oracle parity
synthetic filter oracle parity
all runnable grammar examples
variant inventory
real isolated wheel
```

Then run the complete repository suite for Tasks 0001–0010.

Local trusted-oracle conformance completion requires:

```text
failed  = 0
errors  = 0
skipped = 0
```

After pushing the task commit:

1. verify exact remote SHA on `origin/main`;
2. verify automatic GitHub Actions `CI` is green for that exact SHA on Python 3.10 and 3.12;
3. record the CI run/check result in the completion report;
4. if the manual `Oracle Conformance` workflow is run for milestone closure, record its exact run ID/result separately.

Do not claim GitHub CI success before the pushed SHA actually has green checks.

---

# 33. Completion report

Create:

```text
reports/0010_xml_filters.md
```

Required sections:

## 33.1 Baseline

- pinned LT tag/commit;
- grammar path/size/SHA;
- accepted Task-0009 baseline commit;
- actual starting repository HEAD;
- Task-0009 state/example totals.

## 33.2 Raw filter inventory

- 23 filter refs;
- six grammar filter classes;
- exact per-class counts;
- affected full rule IDs;
- exact args distributions;
- overlap with unification / advanced constructs / Task-0012 blockers.

## 33.3 Upstream provenance

For every newly vendored/critical source:

```text
path
bytes
SHA-256
license/provenance
Task-0010 purpose
```

## 33.4 Implementation semantics

Document:

- filter execution ordering;
- argument resolution;
- match mutation model;
- each native filter;
- clock strategy;
- explicit spelling-filter deferral.

## 33.5 State transitions

Exact Task-0009 → Task-0010 table for all 892 rules.

Expected key transition:

```text
DEFERRED_0010_FILTER -> FILTER_0010_RUNNABLE       19
DEFERRED_0010_FILTER -> DEFERRED_0012               1
MULTI_BLOCKER        -> DEFERRED_0012               3
```

plus unchanged accepted states.

## 33.6 Oracle provenance

- oracle manifest binding;
- build ID;
- JAR SHA;
- synthetic case count;
- real case count;
- controlled clock/corpus version;
- exact compared fields.

## 33.7 Upstream test translation accounting

For each applicable source test:

```text
Java source method
source assertion count
Python test function
translated assertion count
deferred assertion count/reason
```

Do not mix method/function/assertion counts.

## 33.8 Full tests

Exact final:

```text
passed
failed
errors
skipped
runtime
```

Separate normal fixture-only CI from zero-skip trusted-oracle run.

## 33.9 Compatibility totals

- runnable/deferred source rules;
- runnable/deferred examples incorrect/correct;
- executable filter class/rule counts;
- spelling-dependent deferred class/rule counts;
- UNKNOWN count;
- wheel result.

## 33.10 Known limitations

Must explicitly retain:

```text
0011 Java rules
0012 spelling/suppression/etc.
```

Do not claim `RussianSuppressMisspelledSuggestionsFilter` production support before Task 0012.

## 33.11 Git/CI completion

- implementation commit SHA;
- push target `origin/main`;
- exact remote verification SHA;
- automatic CI run/check result for exact SHA;
- Oracle Conformance run ID/result if run.

---

# 34. Acceptance criteria

Task 0010 is accepted only if ALL applicable criteria below are satisfied.

1. Pinned LT remains `v6.8` / `e807fcde...`.
2. Canonical grammar SHA remains `e9bfa390...`.
3. Raw grammar filter count remains exactly 23.
4. Per-class raw filter counts reconcile to 23.
5. All exact raw `filter@args` values are inventoried.
6. Missing upstream generic filter sources needed for parity are vendored byte-exact with provenance.
7. No vendored source line endings are normalized.
8. Native production runtime invokes no Java/server/network.
9. `RuleFilterEvaluator` argument splitting matches pinned Java.
10. Literal key/value parsing matches pinned Java.
11. Backreference resolution matches pinned Java.
12. Skip-corrected references match pinned Java.
13. Optional/repeated token reference behavior is differential-tested.
14. Invalid arg syntax fails explicitly.
15. Duplicate-key behavior matches pinned Java.
16. Unknown filter class fails closed.
17. Filter execution occurs after provisional match formatting.
18. Pattern token slice is pinned-equivalent.
19. tokenPositions are pinned-equivalent.
20. Filters can reject a provisional finding.
21. Filters can preserve a provisional finding.
22. Filters can modify message/suggestions without corrupting spans/IDs.
23. `AdvancedSynthesizerFilter` required args match pinned semantics.
24. Numeric source positions match Java.
25. Marker source positions match Java.
26. Reading selector uses first matching POS reading.
27. No-selector-match first-reading fallback matches Java.
28. `postagReplace` `\aN` semantics match Java.
29. `postagReplace` `\bN` semantics match Java.
30. Native RussianSynthesizer is used, not Java/runtime substitute.
31. Suggestion placeholder lowercase behavior matches Java.
32. Suggestion placeholder capitalized behavior matches Java.
33. Suggestion placeholder uppercase behavior matches Java.
34. No-placeholder synthesis behavior matches Java.
35. Replacement deduplication/order matches Java.
36. Capitalized lemma-source behavior matches Java.
37. All-uppercase behavior matches Java.
38. No-synthesis-result behavior matches Java.
39. `DateCheckFilter` weekday mapping matches pinned Russian code.
40. Date month mapping matches pinned Russian code.
41. Roman month forms are covered.
42. Soft-hyphen weekday handling is covered.
43. Strict invalid-date behavior matches Java.
44. Correct weekday rejects finding.
45. Incorrect weekday keeps/modifies finding.
46. `{realDay}` replacement matches Java.
47. `{day}` replacement matches Java.
48. `{currentYear}` behavior is deterministic in tests and pinned in runtime semantics.
49. Date URL behavior is preserved if exposed.
50. Date tests are not wall-clock flaky.
51. `FutureDateFilter` future/current/past boundary matches Java.
52. `DateFilterHelper` localized month/special-char behavior matches Java.
53. Leap-date behavior is covered.
54. `INNNumberFilter` valid 10-digit case matches Java.
55. Invalid 10-digit case matches Java.
56. Valid 12-digit case matches Java.
57. Invalid first/second checksum cases match Java.
58. Non-10/12 lengths match Java.
59. Non-digit/Unicode edge behavior is Java-differential tested.
60. `RussianPartialPosTagFilter` required args are enforced.
61. Partial regex uses Java-equivalent full-match behavior.
62. One-group semantics match Java.
63. Two-group semantics match Java.
64. Capture-group-count errors match pinned behavior.
65. prefix behavior matches Java.
66. suffix behavior matches Java.
67. `negate_pos` is presence-based exactly as pinned implementation.
68. Native RussianTagger is used.
69. Native single-token RussianDisambiguator is run after tagging.
70. A discriminating case proves disambiguation is not skipped.
71. Null-POS semantics match Java.
72. `NoDisambiguationRussianPartialPosTagFilter` accepted Task-0005 behavior remains unchanged.
73. `RussianSuppressMisspelledSuggestionsFilter` is recognized but not falsely marked supported.
74. Its exact Task-0012 spelling dependency is machine-readable.
75. No fake spelling approximation is introduced.
76. Execution state `FILTER_0010_RUNNABLE` exists.
77. 19 expected filter-only rules are promoted.
78. One spelling-filter rule transitions to Task 0012.
79. Three former multi-blockers transition to Task 0012.
80. `DEFERRED_0010_FILTER` count becomes 0.
81. `MULTI_BLOCKER` count becomes 0 for this baseline.
82. Total runnable source rules become 778.
83. Total deferred source rules become 114.
84. All 892 rules reconcile exactly.
85. UNKNOWN remains 0.
86. Existing 506 core rules remain runnable.
87. Existing 229 advanced rules remain runnable.
88. Existing 24 unification rules remain runnable.
89. Filter+unification rules preserve accepted unifier behavior.
90. Filter state does not leak across candidates/rules/sentences.
91. Dedicated deterministic filter inventory exists and regenerates byte-exact.
92. Inventory records affected full rule IDs and raw args.
93. Inventory records runnable/deferred example inc/correct totals.
94. Inventory arithmetic has explicit tests.
95. `compat/compatibility.json` records Task-0010 units explicitly.
96. Historical Task-0007/0008/0009 evidence is preserved.
97. At least 120 discriminating trusted-Java synthetic cases exist.
98. Synthetic coverage mapping is machine-readable and asserted.
99. Synthetic semantic expectations prevent label-only false coverage.
100. Real oracle covers every newly runnable filter rule.
101. Real Java/Python finding count/order parity is exact.
102. Marker UTF-16 offsets are exact.
103. Full-pattern UTF-16 offsets are exact.
104. Python codepoint offsets are independently correct.
105. Exact messages are compared for filters that modify messages.
106. Exact short messages are compared where applicable.
107. Exact suggestions/order are compared for synthesizer filters.
108. Exact URL is compared if represented.
109. All prior 1,954 runnable grammar examples still pass.
110. All newly runnable rule examples are executed.
111. Deferred spelling-dependent examples are not falsely counted runnable.
112. Embedded-example totals are generated from canonical classification.
113. Real isolated wheel executes Task-0010 filter rules.
114. Wheel makes no Java/network/subprocess calls during production execution.
115. Wheel exact finding proof includes ID/spans/message/suggestions.
116. Complete Tasks 0001–0010 pytest suite passes.
117. Trusted-oracle local completion has 0 failed, 0 errors, 0 skips.
118. Automatic GitHub CI is green on Python 3.10 for the exact pushed SHA.
119. Automatic GitHub CI is green on Python 3.12 for the exact pushed SHA.
120. Completion report contains every section required by §33.
121. Report distinguishes committed-fixture CI from live-oracle conformance.
122. Report does not claim spelling filter support.
123. One intentional Task-0010 implementation commit is created unless review-fix commits are later required.
124. Commit is pushed to `origin/main` without force/history rewrite.
125. Exact remote SHA is verified.
126. Task 0011 is not started.
127. Task 0012 is not started.

---

# 35. Required final workflow

Follow `AGENTS.md` exactly:

```text
read task + handoff + pinned sources
→ inspect current repo
→ implement Task 0010 only
→ focused tests
→ trusted Java differential fixtures/tests
→ all newly runnable grammar examples
→ inventory/compat regeneration
→ real wheel proof
→ full pytest with trusted oracle (0 skips)
→ completion report
→ review git diff/status
→ one intentional commit
→ push current main to origin/main
→ verify remote SHA
→ verify automatic GitHub CI green on that SHA
→ STOP
```

Do not begin Task 0011 automatically.

---

# 36. Completion definition

Task 0010 is complete when the project has a native, deterministic, Java-free production implementation of every Russian grammar XML filter that can be implemented exactly from already-accepted 0001–0009 components, all 19 such filter-only rules are executable with pinned Java parity, the spelling-dependent filter is explicitly and correctly deferred to 0012, all old behavior remains green, compatibility inventories reconcile exactly, the real wheel proves production isolation, and GitHub CI is green on the exact pushed commit.

Anything less is partial implementation and must be reported as such rather than declared complete.
