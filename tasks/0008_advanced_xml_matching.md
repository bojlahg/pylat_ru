# Task 0008 — Advanced XML Pattern Matching

**Status:** READY  
**Baseline:** Task 0007 accepted at `b75bc4dfa84c1549d22f83388785dd9b2988f6de`  
**Target branch:** `main`  
**Pinned LanguageTool:** `v6.8`, commit `e807fcde6a6506191e1470744d2345da28c26be6`

---

# 1. Goal

Extend the native Python XML grammar engine from the proven Task-0007 core subset to the complete **advanced pattern-matching surface used by the pinned Russian `grammar.xml`**, while preserving exact observable LanguageTool behavior.

Task 0008 is not “add a few matcher options”. It must replace the current fixed-width `CompiledPattern.match_at()` assumption with a LanguageTool-compatible pattern matching state machine capable of representing skipped tokens, optional/repeated pattern elements, advanced exceptions, logical groups, phrase expansion/reference behavior, antipattern suppression, chunk predicates, raw/pre-disambiguation POS matching, and generic `<match>`/`MatchState` transformations.

The target is:

```text
Task-0007 runnable XML rules
        +
all source rules blocked only by Task-0008 matcher features
        ↓
Task-0008 advanced-runnable XML rules
```

Task 0008 must make **all rules whose only remaining blockers belong to the 0008 feature surface executable**. Rules still requiring Task 0009 unification, Task 0010 Java/XML filters, or Task 0012 spelling/suppression remain explicitly deferred.

The implementation must remain:

- Russian-only for the production surface;
- native Python at runtime;
- deterministic;
- pinned to LT v6.8;
- fail-closed for unknown or only partially implemented behavior;
- differential-oracle tested against the trusted Java build;
- based on the original pinned `grammar.xml`, not rewritten rule data.

---

# 2. Why Task 0008 exists

Task 0007 deliberately proved a restricted core matcher. Its accepted matcher is essentially a fixed-width sequence matcher:

```text
pattern token 1 -> source token N
pattern token 2 -> source token N+1
...
```

That model is insufficient once the pattern contains any of the following:

- `skip`;
- `min="0"`;
- `max="N"` or `max="-1"`;
- `<and>`;
- `<or>`;
- phrase definitions/references;
- `scope="previous"` / `scope="next"` exceptions;
- advanced whitespace constraints;
- `<antipattern>`;
- token references with `<match>`;
- `<match include_skipped="...">`;
- rule variants created by OR/phrase expansion.

Pinned LT does not model these as a generic regex over token strings. The behavior is encoded in `AbstractPatternRulePerformer`, `PatternToken`, `PatternTokenMatcher`, `PatternRuleHandler`, `PatternRuleMatcher`, `Match`, `MatchState`, and related classes.

Task 0008 must preserve those semantics rather than replace them with a simpler “equivalent-looking” matcher unless differential proof establishes equivalence for the complete pinned Russian surface.

---

# 3. Accepted Task-0007 baseline

Do not regress the accepted Task-0007 behavior.

Baseline facts from the accepted Task-0007 report:

```text
source XML categories:                   8
source XML rulegroups:                 297
source XML rule elements:              892
embedded examples:                   2,446

CORE_0007_RUNNABLE:                    506
DEFERRED_0008_ADVANCED_MATCHING:       157
DEFERRED_0009_UNIFICATION:               8
DEFERRED_0010_FILTER:                   64
MULTI_BLOCKER:                         157
UNRECOGNIZED_CONSTRUCT:                  0

task-0007 runnable examples:           988
deferred examples:                   1,458

accepted full pytest suite:            248 passed
required skips:                          0
```

Task-0007 blocker occurrences recorded in the report include:

```text
filter                              178
skip                                144
unification                          85
or                                   44
and                                  40
phrase                               30
exception_scope                      28
token_match                          24
min_max                              10
spacebefore                           6
```

These counts are a baseline, **not a substitute for regenerating the Task-0008 inventory**. The Task-0008 inventory must derive the exact current counts from pinned source/XML and explain any discrepancy with the Task-0007 report.

The accepted 0007 fixtures/tests remain mandatory regressions:

- 34 RussianChunker oracle cases;
- 62 grammar-core oracle cases;
- 6 `PatternToken` inflected oracle cases;
- 988 core `grammar.xml` examples;
- real-wheel grammar smoke;
- all tests from Tasks 0001–0006.

---

# 4. Source of truth

Read these before changing matcher semantics.

## 4.1 Project files

- `AGENTS.md`
- `docs/Handoff_pylat_ru.md`
- `tasks/0007_xml_grammar_engine_core.md`
- `reports/0007_xml_grammar_engine_core.md`
- `compat/russian_grammar_core_inventory.json`
- `compat/compatibility.json`
- `compat/oracle_manifest.json`
- `src/pylat_ru/grammar/model.py`
- `src/pylat_ru/grammar/loader.py`
- `src/pylat_ru/grammar/classifier.py`
- `src/pylat_ru/grammar/matcher.py`
- `src/pylat_ru/grammar/formatter.py`
- `src/pylat_ru/grammar/engine.py`
- `src/pylat_ru/analysis.py`
- `src/pylat_ru/chunking/`
- `src/pylat_ru/synthesis/`

## 4.2 Pinned upstream implementation

At minimum inspect the exact vendored/pinned versions of:

- `PatternRuleLoader.java`
- `PatternRuleHandler.java`
- `AbstractPatternRule.java`
- `PatternRule.java`
- `PatternRuleMatcher.java`
- `AbstractPatternRulePerformer.java`
- `PatternToken.java`
- `PatternTokenMatcher.java`
- `Match.java`
- `MatchState.java`
- `CaseConversionHelper.java` if required by the pinned implementation;
- `RuleMatch.java`
- the class implementing LT post-match max/overlap filtering (`RuleWithMaxFilter` or the exact pinned equivalent);
- the exact classes responsible for applying rule antipatterns/immunization;
- the exact source that applies `minprevmatches` / `distancetokens` if those attributes occur in pinned Russian rules;
- any directly called helper needed to reproduce the advanced feature surface.

If a required upstream source file is not yet vendored:

1. vendor only the exact pinned file needed;
2. record upstream path, byte size, SHA-256, commit and license;
3. update `third_party/languagetool/UPSTREAM.json`;
4. update `third_party/languagetool/license_inventory.json`;
5. do not vendor a broad LT subtree merely for convenience.

## 4.3 Pinned upstream tests

Inspect and inventory advanced-matching assertions from at least:

- `PatternRuleMatcherTest.java`
- `PatternRuleLoaderTest.java`
- `PatternRuleTest.java`
- `RussianPatternRuleTest.java`

Also include any additional pinned test class that directly covers:

- antipatterns;
- phrase references;
- `MatchState` / `include_skipped`;
- case conversion;
- token references;
- skip and optional/repeated tokens;
- chunk matching;
- exception scopes.

Do not count a source test file as “ported” merely because one unrelated assertion from the same class was translated in Task 0007.

---

# 5. Critical scope correction from the provisional Task-0007 classifier

Task 0007 used a provisional ownership split for complex `<match>` attributes. That split must be corrected in Task 0008 according to pinned upstream architecture.

Pinned LT generic `<match>` behavior lives in:

```text
Match
MatchState
PatternToken.compile()
PatternTokenMatcher.resolveReference()
PatternRuleMatcher.formatMatches()
```

It is **not** a Java `RuleFilterEvaluator` feature merely because it is complex.

Therefore Task 0008 owns the generic matcher/formatter behavior for `<match>` attributes used by pinned Russian grammar, including as applicable:

- `case_conversion`;
- `include_skipped`;
- `regexp_match`;
- `regexp_replace`;
- `postag`;
- `postag_regexp`;
- `postag_replace`;
- `setpos`;
- token-level `<match>` references;
- static lemma text inside `<match>`.

Task 0010 remains responsible for actual XML/Java filters configured as:

```xml
<filter class="..." args="..."/>
```

Task 0012 remains responsible for spelling-dependent suppression such as `suppress_misspelled` / `PLEASE_SPELL_ME` behavior.

If source audit proves a specific `<match>` attribute has a different owner, record the exact source path/method and classify it explicitly. Do not preserve a stale Task-0007 classification merely because it already exists in JSON.

---

# 6. Explicit non-goals

Task 0008 must **not** implement:

- unification semantics (`<unification>`, `<unify>`, `<unify-ignore>`, agreement features) beyond preserving their already parsed structure — Task 0009;
- Java/XML rule filter classes — Task 0010;
- Russian Java rules — Task 0011;
- spelling, compound, replace, coherency, repetition Java-rule families — Task 0012;
- `suppress_misspelled` spelling decisions — Task 0012;
- semantic/NLP substitutes;
- an LT server or Java runtime dependency;
- unrelated TextQA features;
- an upstream LT version change;
- generalized support for all languages.

Task 0008 may refactor Task-0007 matcher internals as much as necessary, but accepted public behavior from 0001–0007 must remain compatible.

---

# 7. Compatibility principles

## 7.1 Source semantics beat intuitive semantics

Do not infer what `skip`, `min`, `<and>`, `<or>`, or `include_skipped` “should” mean.

Use the pinned Java implementation and tests.

For example, pinned `PatternToken` establishes constraints such as:

```text
skip:        -1 .. 127
min:         only 0 or 1
max:         -1 or 1 .. 127; 0 invalid
```

These validation rules are part of compatibility.

## 7.2 Do not replace the LT state machine with naive backtracking

Pinned `AbstractPatternRulePerformer` keeps state including:

- pattern element index;
- source token index;
- `tokenPositions`;
- accumulated skip shift;
- previous `skip` allowance;
- optional-element correction;
- first/last matched token;
- first/last marker token;
- greedy max-occurrence extension;
- exception interactions;
- unification state (still deferred in 0008).

A Python implementation may use different internal code, but observable behavior must match that algorithm exactly for the supported surface.

## 7.3 No silent partial advanced rule execution

A source rule is runnable only when **every** behavior it requires is implemented for this stage.

A rule with:

```text
skip + filter
```

may gain working skip support in 0008, but must remain deferred because its filter is still unsupported.

Likewise:

```text
or + unification
```

must remain deferred to 0009 after 0008 removes the OR blocker.

## 7.4 Distinguish feature usage from blockers

Task 0008 should stop using `blockers` as the only record of feature presence.

Machine-readable compatibility data must be able to say both:

```text
rule uses skip = true
skip is supported = true
rule has remaining filter blocker = true
```

Recommended model:

```text
feature_usage[]
remaining_blockers[]
execution_state
```

Equivalent structure is acceptable, but supported feature usage must not disappear from the inventory simply because it is no longer a blocker.

## 7.5 Source rule count and executable variant count are different concepts

The pinned XML contains 892 source `<rule>` elements.

Pinned `PatternRuleHandler.createRules()` may create multiple physical matcher rules from one source rule because of `<or>` and phrase expansion.

Task 0008 must track separately:

```text
source XML rule elements
logical pylat_ru rules
compiled/executable variants
```

Do not overwrite variants in a dictionary merely because they share `full_id`.

---

# 8. Phase 0 — Build the Task-0008 advanced-matching inventory

Before implementing advanced execution, create a deterministic inventory generator, for example:

```text
tools/russian_grammar_advanced_inventory.py
```

and committed artifact:

```text
compat/russian_grammar_advanced_inventory.json
```

Keep `compat/russian_grammar_core_inventory.json` as the historical Task-0007 baseline. Do not rewrite it into a Task-0008 artifact.

## 8.1 Required top-level inventory metadata

Record:

```text
schema_version
pinned_lt_version
pinned_lt_commit
grammar_xml_path
grammar_xml_size
grammar_xml_sha256
baseline_task_0007_commit
generator_path
generator_sha256 or reproducibility version
```

## 8.2 Required source-rule totals

Recompute and assert:

- categories;
- rulegroups;
- source rule elements;
- examples total;
- Task-0007 execution-state counts;
- blocker combinations;
- examples by execution state.

If they differ from the accepted 0007 baseline, fail the inventory test until the discrepancy is explained.

## 8.3 Advanced feature occurrence inventory

For every candidate advanced feature, record:

- number of source rules using it;
- number of occurrences;
- distinct attribute values;
- representative rule IDs;
- representative XML snippets or structural descriptors;
- number of embedded examples attached to those rules;
- overlap with other advanced features;
- overlap with 0009/0010/0012 blockers.

At minimum inventory:

```text
pattern@raw_pos
token@raw_pos
token@chunk
token@spacebefore
exception@spacebefore
pattern:and
pattern:or
phrase / phraseref / includephrases surface actually present
token@skip
token@min
token@max
exception@scope=current
exception@scope=previous
exception@scope=next
antipattern at rule level
antipattern inherited from rulegroup
token-level <match>
message/suggestion <match>
match@case_conversion
match@include_skipped
match@regexp_match
match@regexp_replace
match@postag
match@postag_regexp
match@postag_replace
match@setpos
static lemma <match> text
rule@minprevmatches
rule@distancetokens
rulegroup@minprevmatches
rulegroup@distancetokens
```

For any item with count zero in pinned Russian `grammar.xml`, record `count: 0`. Do not invent production behavior and claim it as Russian parity solely because generic LT supports it.

## 8.4 Exact value distributions

Record exact observed distributions for bounded/enum features, especially:

```text
skip values
min values
max values
spacebefore values
exception scope values
chunk regexp/literal forms if distinguishable
include_skipped values
case_conversion values
setpos values
raw_pos values
```

The implementation scope is the full generic pinned semantics needed by observed Russian values plus required upstream differential boundary tests.

## 8.5 Blocker transition matrix

For all 892 source rules, produce a deterministic before/after target matrix:

```text
full_id
source_order
Task-0007 state
feature_usage
Task-0007 blockers
blockers removed by 0008
remaining blockers after 0008
expected Task-0008 execution state
```

The target is:

- all 506 Task-0007 core rules remain runnable;
- all 157 rules whose baseline state is `DEFERRED_0008_ADVANCED_MATCHING` become runnable, unless Phase 0 proves that the old classifier incorrectly hid a non-0008 dependency;
- any such old-classifier error must be documented and corrected from pinned source, never silently used to shrink Task-0008 scope;
- multi-blocker rules lose only their implemented 0008 blockers and remain deferred when 0009/0010/0012 blockers remain;
- unknown/unclassified disposition remains zero.

## 8.6 Java loader expansion inventory

Using the trusted Java oracle, inventory advanced loader behavior for the pinned Russian file:

- source rule count;
- physical Java `AbstractPatternRule` count after OR/phrase expansion;
- number of source rules producing >1 executable variant;
- variant count distribution;
- output ordering;
- IDs/full IDs/sub IDs of expanded variants;
- phrase definitions/references and expansion multiplicity;
- whether multiple physical variants share the same `full_id`.

This artifact is required before choosing the Python representation of OR/phrase alternatives.

---

# 9. Phase 1 — Execution-state and compiled-variant model

## 9.1 Add an explicit Task-0008 runnable state

Preserve provenance of what Task introduced a rule’s capability.

Recommended execution states:

```text
CORE_0007_RUNNABLE
ADVANCED_0008_RUNNABLE
DEFERRED_0009_UNIFICATION
DEFERRED_0010_FILTER
DEFERRED_0012_SPELLING_OR_SUPPRESSION
MULTI_BLOCKER
UNKNOWN
```

Equivalent naming is acceptable if compatibility output distinguishes Task-0007-core rules from rules newly promoted in 0008.

`RussianGrammarEngine.get_runnable_rules()` and `check_sentence()` must execute both 0007 and 0008 runnable states.

## 9.2 Do not collapse executable variants

Current Task-0007 engine indexes compiled rules by `full_id`. That is insufficient if OR/phrase expansion creates multiple executable variants sharing the public ID.

Choose an internal identity such as:

```text
(full_id, variant_index)
```

or an equivalent stable key.

Requirements:

- no executable variant is overwritten;
- variant order matches pinned Java loader/matcher order;
- public findings still expose the upstream-visible rule ID/full ID;
- repeated public IDs do not create accidental deduplication;
- `check_rule()` executes all variants belonging to the requested logical rule when Java does so;
- `check_sentence()` preserves deterministic rule/variant/finding ordering.

If Python chooses not to physically expand OR/phrases, prove exact equivalence against Java for variant ordering, duplicates, match ordering, spans, messages, and suggestions.

## 9.3 Separate source model from match state

Do not mutate shared `GrammarRule` / `PatternToken` objects while matching a sentence.

Create a per-attempt/per-match state structure containing at minimum:

```text
source pattern element -> matched source token range
source pattern element -> position delta/tokenPositions equivalent
optional element present/absent
skipped token ranges
repeated token ranges
first matched token
last matched token
first marker token
last marker token
full pattern span
marker/error span
```

The state must be sufficient for exact `<match no="...">` formatting after skip/min/max/phrase expansion.

---

# 10. Phase 2 — Port the pinned advanced matcher state machine

Use `AbstractPatternRulePerformer` as the primary behavioral reference.

Do not implement each advanced feature as a separate patch over the old fixed-width loop if doing so loses the shared `tokenPositions`/skip/optional semantics.

## 10.1 Start-position search

Match Java behavior for:

- scan start limits;
- sentence-start anchored patterns;
- optional-element correction to start limits;
- token arrays without whitespace;
- pre-disambiguation token selection for raw-pos rules;
- source ordering of matches.

## 10.2 `tokenPositions` equivalent

Pinned formatter behavior relies on the relative-position array created during matching.

Python must retain equivalent information.

In particular:

- a present ordinary element contributes a positive offset;
- an omitted `min="0"` element is represented as absent rather than silently renumbering later references;
- skipped tokens change the delta to the next matched element;
- repeated/max occurrences change the extent represented by that element;
- phrase expansion affects logical element numbering;
- formatter references must resolve through this state, not through `matched_tokens[no-1]`.

## 10.3 Greediness and overlap

Pinned `skipMaxTokens()` greedily extends the current pattern token up to its max occurrence while each subsequent occurrence matches.

Implement exact behavior for:

- `max=2`, `max=3`;
- `max=-1` unlimited;
- multiple repeated elements in one pattern;
- repeated “any token” elements;
- repetition next to optional elements;
- repeated elements inside markers;
- longest-match behavior when multiple possible extents exist.

Do not add regex-style backtracking that Java does not perform.

## 10.4 Post-match filtering

Pinned `PatternRuleMatcher.match()` applies the pinned max/overlap filter after collecting raw matches.

Port or reproduce the exact pinned behavior required for advanced patterns.

Test:

- overlapping candidate matches;
- same-start different-length matches;
- repeated-element longest match;
- adjacent matches;
- variant-generated matches;
- stable result ordering.

---

# 11. Phase 3 — `skip`

Implement exact pinned `PatternToken.setSkipNext()` and matcher semantics.

## 11.1 Validation

Accepted:

```text
-1 .. 127
```

Reject explicitly:

```text
< -1
> 127
non-integer
```

## 11.2 Matching semantics

Prove at least:

- default/no skip;
- finite skip allowing zero skipped tokens;
- finite skip allowing one/multiple skipped tokens;
- finite skip exhaustion;
- `skip="-1"` search to sentence end;
- no valid later token;
- source end boundary;
- skip followed by optional element;
- skip followed by repeated element;
- skip inside/outside marker;
- multiple skip-bearing elements;
- interaction with `scope="next"` exception;
- `<match include_skipped>` formatting.

## 11.3 No whitespace-token confusion

The matcher works over the exact LT token array used by `PatternRuleMatcher`, while `MatchState` reconstructs skipped text using whitespace metadata.

Do not implement `skip=N` as “skip N Python string tokens including whitespace”.

---

# 12. Phase 4 — `min` / `max`

## 12.1 Exact validation

Pinned `PatternToken` supports:

```text
min: 0 or 1
max: -1 or 1..127
```

`max=0` is invalid.

Any unsupported integer must raise a typed grammar-format/compatibility error at load time, not be clamped.

## 12.2 Optional element semantics

Port the Java `min="0"` behavior, including look-ahead over subsequent optional elements.

Required cases:

- optional token present;
- optional token absent;
- optional first element;
- optional middle element;
- optional last element if accepted by pinned loader/runtime;
- two adjacent optional elements;
- optional any-token element;
- optional element inside marker;
- omitted optional element referenced from suggestion/message;
- omitted optional element before/after a skip;
- match spans when optional element is absent.

The exact behavior demonstrated by pinned `PatternRuleMatcherTest.testZeroMinOccurrences*` and related tests must be translated where applicable.

## 12.3 Max occurrence semantics

Required cases:

- max 2;
- max 3;
- unlimited `-1`;
- max over literal token;
- max over any-token predicate;
- `min=0,max=2`;
- two repeated elements next to each other;
- source text containing one extra matching token beyond max;
- marker span through repeated tokens;
- `<match>` reference to a repeated element.

---

# 13. Phase 5 — advanced exception scopes

Implement the exact pinned behavior for:

```text
scope="current"
scope="previous"
scope="next"
```

Current-scope behavior from 0007 remains regression-covered.

## 13.1 Previous scope

Prove:

- previous token matches exception -> pattern token rejected;
- previous token does not match -> allowed;
- multiple readings in previous token;
- sentence boundary;
- interaction with optional tokens;
- interaction with skip/repetition;
- previous exception inherited through AND-group structures if pinned source supports it.

## 13.2 Next scope

Pinned `AbstractPatternRulePerformer` contains special handling for scope-next exceptions, including a workaround when there is no skip and the next token is the sentence’s last token.

Port the source behavior exactly.

Prove:

- next token blocks current element;
- next token does not block;
- skip allowance >0;
- skip=0 special case;
- sentence-end boundary;
- multiple token readings;
- repeated/optional neighboring elements.

## 13.3 Exception `spacebefore`

Implement only according to pinned `PatternToken` behavior and observed Russian values.

Do not infer whitespace from source string slicing when LT stores a dedicated whitespace-before flag.

---

# 14. Phase 6 — token `spacebefore`

Implement exact `PatternToken` whitespace-before testing.

Required coverage:

- `spacebefore="yes"`;
- `spacebefore="no"`;
- ordinary ASCII space;
- no space;
- punctuation boundaries;
- non-breaking/narrow-space cases if they are observable in LT analysis;
- sentence start;
- interaction with token negation;
- interaction with optional/skip elements;
- exception `spacebefore`.

Validate accepted XML values exactly. Unknown values must fail closed.

---

# 15. Phase 7 — chunk predicates

Task 0007 already implemented `RussianChunker`; Task 0008 must make `token@chunk` executable.

Port pinned `AbstractPatternRulePerformer.testAllReadings()` chunk semantics.

Required behavior:

- exact chunk tag match;
- regexp chunk tag match when supported by pinned XML representation;
- chunk negation;
- token with multiple chunk tags;
- token with no chunk tags;
- chunk condition combined with text/POS;
- chunk condition inside AND group;
- chunk condition after raw-pos selection if such a combination exists;
- exact order/identity of chunk tags is not altered by grammar matching.

Do not rerun/rewrite chunking inside individual rule matching.

---

# 16. Phase 8 — `<and>` groups

Pinned LT AND semantics are **reading-aware**, not equivalent to applying every condition to one arbitrary selected reading.

`PatternTokenMatcher` accumulates matches for group members while iterating readings.

The implementation must preserve this behavior.

Required coverage:

- base token + one AND member;
- multiple AND members;
- all predicates satisfied by the same reading;
- different predicates satisfied by different readings of one `AnalyzedTokenReadings`;
- one missing member -> no match;
- text + POS combinations;
- chunk condition in AND group;
- negation in group member;
- exceptions associated with AND-group structures;
- token-level match reference inside a group if pinned Russian XML uses it;
- marker behavior around an AND element.

Do not flatten `<and>` into sequential source tokens. It represents one logical pattern position.

---

# 17. Phase 9 — `<or>` groups

Pinned `PatternRuleHandler.createRules()` expands OR alternatives recursively into executable rule variants.

Task 0008 must reproduce the observable result of that expansion.

Required coverage:

- two alternatives;
- three alternatives;
- OR at first/middle/last pattern position;
- OR inside marker;
- alternatives with different text/POS constraints;
- OR combined with AND where accepted by pinned schema;
- OR variant ordering;
- multiple OR groups causing Cartesian expansion;
- IDs/full IDs/sub IDs;
- messages/suggestions associated with all variants;
- duplicate public full IDs without loss;
- source-order interaction with neighboring rules.

If Python implements runtime alternation instead of physical variant expansion, the Java oracle must prove equivalent match count/order/spans/messages/suggestions for all relevant cases.

---

# 18. Phase 10 — phrases / phrase references

Do not assume the current Task-0007 `PatternPhrase` representation exactly matches pinned SAX loader semantics.

First inventory the actual pinned Russian surface and reconcile it with `PatternRuleHandler` concepts such as:

```text
<phrases>
<phrase ...>
<phraseref ...>
<includephrases>
```

Only implement constructs present in the pinned source or required by translated upstream tests, but all present Russian constructs must be handled.

Required semantics when present:

- phrase definition parsing;
- phrase reference resolution;
- multiple alternatives under one phrase ID;
- recursive/invalid references fail closed according to pinned behavior;
- marker state is determined by the **reference location**, not blindly copied from definition;
- phrase expansion order;
- logical element numbering;
- `PatternRuleMatcher.translateElementNo()` equivalent;
- `<match no>` after phrase expansion;
- source/full pattern spans;
- OR + phrase combinations;
- no variant loss when multiple phrase expansions share public IDs.

If pinned Russian `grammar.xml` has zero occurrences of a generic LT phrase feature, record the zero count and keep it outside the production compatibility claim.

---

# 19. Phase 11 — `pattern@raw_pos`

Pinned `PatternRuleMatcher` chooses:

```text
sentence.getPreDisambigTokensWithoutWhitespace()
```

when the rule requests pre-disambiguation POS interpretation, otherwise:

```text
sentence.getTokensWithoutWhitespace()
```

Task 0008 must make this distinction observable and exact.

Requirements:

- use the exact Task-0005 pre-disambiguation snapshot already preserved by the analysis pipeline;
- do not retag the sentence;
- do not reverse disambiguation mutations heuristically;
- offsets remain tied to the same source text;
- raw-pos rule does not accidentally consume post-chunker mutated readings unless pinned Java does;
- ordinary rules remain on post-disambiguation readings.

Add at least one direct Java differential sentence where pre- and post-disambiguation readings differ and the rule result changes because of `raw_pos`.

---

# 20. Phase 12 — rule antipatterns

Implement exact pinned antipattern suppression for advanced-runnable rules.

Before coding, identify the exact pinned classes/methods that apply antipatterns to `PatternRule` execution. Vendor missing source files if necessary.

Required semantics:

- rule-local antipattern;
- rulegroup-inherited antipattern;
- multiple antipatterns;
- antipattern with explicit marker;
- antipattern without marker and pinned artificial-marker behavior;
- antipattern that overlaps the main pattern fully;
- partial overlap on left/right;
- adjacent non-overlapping antipattern;
- multiple possible main-rule matches where only one is suppressed;
- optional/skip constructs inside antipattern when present in Russian data;
- source offsets and non-BMP characters;
- no persistent immunization leakage into subsequent unrelated rule execution unless pinned Java intentionally mutates sentence state that way.

Do not implement antipattern as a simple “if antipattern occurs anywhere in sentence, suppress the rule”.

---

# 21. Phase 13 — token-level `<match>` references

Pinned `PatternTokenMatcher.resolveReference()` and `PatternToken.compile()` allow a pattern token to be dynamically compiled from a previously matched token.

This is matcher behavior and belongs to Task 0008.

Required semantics as applicable to pinned Russian rules:

- reference resolution relative to first matched source token;
- interaction with skipped/optional elements;
- text reference replacement;
- POS-setting reference (`setpos`);
- POS regexp/replace;
- static lemma text;
- use of native `RussianSynthesizer` from Task 0006;
- multiple synthesis forms;
- no synthesis form;
- reference beyond available token range;
- phrase-expanded logical numbering;
- no reference-recursion bug when source token text itself contains backslashes/digits.

Task 0008 must not call Java synthesis in production.

---

# 22. Phase 14 — generic `<match>` / `MatchState` formatting

Refactor `TemplateFormatter` as necessary so it consumes the advanced match state rather than assuming:

```python
matched_tokens[ref.no - 1]
```

That assumption is invalid after skip/min/max/phrases.

## 22.1 `include_skipped`

Implement the pinned `Match.IncludeRange` behavior exactly.

Inventory accepted XML values and map them to the pinned enum semantics (`NONE`, `FOLLOWING`, `ALL` or exact pinned naming).

Preserve whitespace exactly as `MatchState.setToken(tokens, index, next)` does.

Required tests:

- no skipped tokens;
- one skipped token;
- multiple skipped tokens;
- skipped token with whitespace-before;
- FOLLOWING behavior;
- ALL behavior;
- include-skipped on optional/repeated element;
- suggestion and message contexts.

## 22.2 Case conversion

Implement exact pinned case conversion for every value used by Russian rules and every generic boundary required by upstream tests.

Potential pinned enum values include:

```text
NONE
STARTLOWER
STARTUPPER
ALLLOWER
ALLUPPER
PRESERVE
FIRSTUPPER
NOTASHKEEL
```

Do not claim unsupported-language-specific conversion when Russian data never uses it; record zero usage instead.

Case conversion must match Java Unicode behavior for the tested Russian surface.

## 22.3 Regex transform semantics

Current Task-0007 formatter must not silently swallow invalid regex/replacement errors.

Implement Java-compatible:

- regexp matching;
- replacement syntax including Java `$1`, `$2`, ... group references;
- escaping rules needed by pinned Russian expressions;
- replacement ordering relative to case conversion;
- explicit typed failure for malformed patterns/replacements that pinned loader/runtime rejects.

Do not pass Java replacement strings directly to Python `regex.sub()` and assume `$1` means the same thing.

## 22.4 POS transform and synthesis

Implement generic `MatchState` behavior needed by pinned Russian XML:

- literal target POS;
- POS regexp matching;
- POS replacement;
- `setpos` behavior;
- target POS selection;
- synthesis via native `RussianSynthesizer`;
- deterministic output ordering matching Java (`TreeSet`/upstream behavior where applicable);
- no forms / fallback behavior;
- sentence/paragraph pseudo-tag handling when relevant.

Anything that requires spelling validation remains blocked by Task 0012.

---

# 23. Phase 15 — rule-level advanced matching modifiers

Inventory the pinned Russian use of:

```text
minprevmatches
distancetokens
```

at rule and rulegroup levels.

If count is zero:

- record zero usage;
- preserve metadata;
- do not claim production support merely from loader parsing.

If count is nonzero and the pinned execution path belongs to XML pattern-rule matching rather than another planned task:

- vendor/inspect the responsible source;
- implement it in 0008;
- add direct Java oracle cases;
- add it to the feature/blocker transition inventory.

If source proves it belongs elsewhere, document the exact target task and source evidence.

---

# 24. Phase 16 — marker/full-pattern spans under advanced matching

`RuleMatchResult` must continue exposing separately:

- marker/error span in Python codepoints;
- marker/error span in Java UTF-16 units;
- full-pattern span in Python codepoints;
- full-pattern span in Java UTF-16 units.

Advanced matching must derive these spans from actual matched source tokens, not from fixed pattern indices.

Required cases:

- skipped tokens inside full pattern but outside marker;
- marker containing skipped tokens;
- omitted optional token inside marker;
- repeated token inside marker;
- marker beginning/ending on OR/AND logical element;
- phrase expansion inside marker;
- `skip=-1` where final expected token is absent/non-matched boundary if pinned Java produces no RuleMatch;
- comma-prepended suggestion whitespace correction from Task 0007;
- emoji/non-BMP before the match;
- emoji/non-BMP inside skipped region;
- emoji/non-BMP inside repeated/marker region.

For every finding:

```python
text[from_pos:to_pos]
text[pattern_from_pos:pattern_to_pos]
```

must correspond exactly to the intended source slices.

---

# 25. Phase 17 — Java differential oracle

Task 0008 requires a dedicated trusted Java differential surface.

Extend `tools/differential_lt.py` or add a narrowly scoped helper, but preserve the dev-only boundary.

Recommended committed fixtures:

```text
tests/fixtures/oracle_advanced_pattern_matching.json
tests/fixtures/oracle_advanced_russian_rules.json
```

Additional focused fixtures are acceptable when they improve auditability.

## 25.1 Fixture provenance

Every fixture must contain:

```text
schema_version
pinned_lt_version
pinned_lt_commit
oracle_build_id
oracle_jar_sha256
generator_operation/corpus version
case_count
```

Tests must resolve `oracle_build_id` through `compat/oracle_manifest.json` and require exact version/commit/JAR SHA equality.

No hard-coded “trusted” SHA disconnected from the manifest.

## 25.2 Synthetic feature matrix

Create Java-generated discriminating cases for all implemented feature families.

Minimum target: **at least 100 distinct synthetic oracle cases**, with combinations, not 100 trivial permutations.

Cover at minimum:

- finite skip;
- infinite skip;
- skip failure/boundaries;
- min=0 present/absent;
- adjacent optional elements;
- max=2/max=3/max=-1;
- repeated any token;
- skip + min/max;
- previous/next exceptions;
- exception + skip;
- spacebefore token/exception;
- chunk exact/negated/multiple chunks;
- AND same-reading and cross-reading behavior;
- OR expansion/order;
- phrase/ref behavior when applicable;
- raw-pos behavior;
- antipattern overlap variants;
- token-level `<match>` references;
- include-skipped;
- case conversion;
- regexp replacement with capture groups;
- POS transform/synthesis as applicable;
- marker/full-span edge cases;
- non-BMP offsets.

## 25.3 Real Russian advanced-rule corpus

Automatically derive representative real rules from the Task-0008 inventory.

The corpus must include at least one real pinned Russian rule for every advanced feature family with nonzero Russian occurrence count, unless no single rule can isolate that family; in that case record the reason and use a combination case.

For each selected rule, generate Java oracle output over:

- at least one matching input;
- at least one near-miss/non-matching input where practical;
- embedded `grammar.xml` examples when available.

Do not handwrite Java expected output into the fixture.

## 25.4 Exact finding parity fields

For every real-rule oracle case compare, where Java exposes them:

- rule ID;
- full rule ID/sub ID;
- category ID/name;
- description;
- default/enabled state metadata used by Python;
- finding count;
- finding order;
- marker/error from/to UTF-16;
- full-pattern from/to UTF-16;
- Python codepoint conversion and source slice;
- message;
- short message;
- suggestions exact strings and order.

Do not reduce an oracle fixture to `len(matches) > 0`.

---

# 26. Phase 18 — Translate upstream advanced matcher tests

Port all assertions from pinned upstream tests that belong to the Task-0008 feature surface.

At minimum translate the relevant portions of `PatternRuleMatcherTest`, including behavior equivalent to:

- zero min occurrence tests;
- multiple zero-min elements;
- optional any-token element;
- optional element with suggestion reference;
- max 2/max 3/unlimited;
- combined max occurrences;
- explicit marker with optional elements;
- infinite skip;
- infinite skip + match reference;
- no recursive interpretation of backreference-looking source text;
- longest-match/overlap behavior.

Also translate applicable loader tests for:

- chunk attributes;
- OR rule expansion;
- phrase handling;
- advanced match attributes;
- advanced validation boundaries.

For each upstream source test file, report separately:

```text
assertions relevant to 0008
translated assertions
intentionally deferred assertions
deferred target task + reason
```

Do not mix source-file counts and Python-test-function counts.

---

# 27. Phase 19 — Execute all newly runnable `grammar.xml` examples

After implementation/reclassification:

1. identify every source rule runnable after Task 0008;
2. execute every embedded example attached to those rules;
3. retain all 988 accepted Task-0007 examples as mandatory regressions;
4. add every example belonging to newly promoted 0008 rules.

Report separately:

```text
Task-0007 core source rules/examples
newly promoted Task-0008 source rules/examples
total runnable source rules/examples
still-deferred source rules/examples
```

## 27.1 Correct examples

A correct example must produce no finding from the target rule/variant according to pinned Java semantics.

## 27.2 Incorrect examples

Validate as applicable:

- target rule fires;
- exact finding count when source semantics require it;
- exact marker offsets;
- exact corrections/suggestions and order;
- exact message fields for oracle-backed examples.

## 27.3 Antipattern examples

Where upstream embeds antipattern examples, treat them as first-class conformance cases rather than folding them into a generic “correct” bucket without provenance.

## 27.4 No normalization cheats

Do not make parity pass by silently:

- stripping expected/actual strings;
- replacing NBSP with ordinary space;
- collapsing whitespace;
- case-folding suggestions;
- accepting any span that points to the same stripped text.

Any normalization must be proven as part of pinned observable semantics.

---

# 28. Phase 20 — Classifier and compatibility update

Refactor `src/pylat_ru/grammar/classifier.py` so classification reflects **current implementation capability**, not historical task ownership guesses.

## 28.1 After Task 0008

A rule using only 0007+0008 supported features must be runnable.

A rule with residual features must remain blocked:

```text
unification          -> 0009
<filter class=...>   -> 0010
suppress_misspelled  -> 0012
```

## 28.2 Generic `<match>` ownership

Do not classify generic `Match`/`MatchState` attributes as 0010 merely because they are complex.

Only actual Java/XML filter classes belong to Task 0010 unless source proves otherwise.

## 28.3 Zero unknowns

For all 892 source rules:

```text
UNKNOWN == 0
unclassified construct == 0
silently ignored construct == 0
```

## 28.4 Compatibility metrics

Update `compat/compatibility.json` with exact current counts and explicit units:

- source XML rules total;
- Task-0007 core runnable;
- Task-0008 newly runnable;
- total native XML runnable;
- remaining rules by target task/blocker combination;
- executable variant total;
- runnable examples total;
- deferred examples total;
- advanced oracle case counts;
- translated upstream assertion counts;
- wheel result;
- parity metrics only for fields actually asserted.

Do not overwrite Task-0007 historical artifact counts to make Task-0008 totals look cleaner.

---

# 29. Phase 21 — API and engine behavior

## 29.1 `get_runnable_rules()`

Must return all source/logical rules executable by 0007+0008.

## 29.2 `check_rule()`

For a logical rule with multiple internal variants:

- execute all applicable variants;
- preserve Java result order;
- do not lose a variant through `_rules_by_full_id` overwrite;
- preserve public `rule_id` / `full_rule_id` values.

If a user supplies a still-deferred rule, raise `UnsupportedGrammarFeatureError` with **all remaining blockers** available in structured data/message.

## 29.3 `check_sentence()`

Execute runnable rules in deterministic pinned-equivalent source/variant order.

Do not deduplicate findings by ID alone.

## 29.4 Reentrancy/state isolation

Per-match mutable state must not leak between:

- two start positions;
- two variants;
- two rules;
- two sentences;
- two repeated calls to the same singleton engine.

Add regressions for repeated calls and interleaved rules.

---

# 30. Phase 22 — Real wheel proof

Extend the automated wheel test.

The test must:

1. build a real wheel;
2. verify all required grammar resources are packaged;
3. install the wheel to an isolated target;
4. ensure repository `src/` and `third_party/` are not importable as accidental fallbacks;
5. run the complete Python-only pipeline:

```text
raw text
-> tokenize
-> tag
-> disambiguate
-> chunk
-> advanced XML grammar engine
```

6. execute at least:
   - one accepted Task-0007 core rule;
   - one real newly promoted Task-0008 Russian rule that uses a genuinely advanced feature such as skip/min-max/antipattern/OR/advanced match behavior;
7. assert exact rule ID, offsets, message and suggestions for those smoke cases;
8. prove no Java executable/server is invoked by production runtime.

---

# 31. Phase 23 — Failure behavior

Add typed/fail-closed regressions for malformed advanced XML.

At minimum:

- skip below -1;
- skip above 127;
- non-integer skip;
- min other than 0/1;
- max 0;
- max below -1;
- max above 127;
- invalid `spacebefore`;
- invalid exception scope;
- invalid `case_conversion`;
- invalid `include_skipped`;
- malformed regex;
- invalid Java-style replacement syntax as pinned runtime rejects it;
- invalid phrase reference;
- unsupported recursive phrase form if pinned loader rejects it;
- token reference to impossible/invalid logical element where pinned loader rejects it;
- any still-unsupported advanced construct discovered by inventory.

Never silently coerce invalid values to defaults.

---

# 32. Phase 24 — Performance and caching boundaries

Correctness comes first, but Task 0008 must avoid obvious pathological behavior.

Requirements:

- parse grammar XML once per engine/resource load, not per sentence;
- compile text/POS/chunk regexes once per compiled rule/variant where possible;
- do not invoke synthesizer for `<match>` paths that do not require synthesis;
- do not reconstruct all variants on every match attempt;
- do not copy the full sentence token graph for every pattern element;
- no Java subprocess in normal tests/runtime paths except explicit oracle generation.

Record rough full-grammar advanced test runtime in the completion report for regression visibility. No hard performance SLA is required in 0008.

---

# 33. Required files/artifacts

Expected additions/changes include, naming may vary when justified:

```text
tasks/0008_advanced_xml_matching.md
reports/0008_advanced_xml_matching.md
compat/russian_grammar_advanced_inventory.json
compat/compatibility.json
src/pylat_ru/grammar/model.py
src/pylat_ru/grammar/loader.py
src/pylat_ru/grammar/classifier.py
src/pylat_ru/grammar/matcher.py
src/pylat_ru/grammar/formatter.py
src/pylat_ru/grammar/engine.py
tools/russian_grammar_advanced_inventory.py
tools/differential_lt.py
tests/fixtures/oracle_advanced_pattern_matching.json
tests/fixtures/oracle_advanced_russian_rules.json
tests/unit/test_advanced_grammar_matcher.py
tests/upstream/test_advanced_pattern_oracle_parity.py
tests/upstream/test_advanced_russian_rule_oracle_parity.py
tests/upstream/test_russian_grammar_examples.py
tests/upstream/test_upstream_pattern_rules.py
tests/unit/test_real_wheel_grammar.py
```

If a different structure is cleaner, use it, but all required evidence must remain auditable.

---

# 34. Completion report requirements

Create:

```text
reports/0008_advanced_xml_matching.md
```

The report must contain at minimum:

## 34.1 Baseline

- Task-0007 accepted commit;
- pinned LT version/commit;
- pre-0008 rule state counts;
- pre-0008 example counts.

## 34.2 Upstream source provenance

For every new/critical advanced-matcher source:

```text
path
byte size
SHA-256
license/provenance
purpose in 0008
```

## 34.3 Feature inventory

Exact occurrence counts and observed values for every Phase-0 feature family.

## 34.4 Rule transition table

Report exact counts for:

```text
remained CORE_0007_RUNNABLE
promoted ADVANCED_0008_RUNNABLE
remaining 0009-only
remaining 0010-only
remaining 0012-only
remaining multi-blocker
unknown
```

Explain any source rule whose expected transition differs from the Task-0007 baseline classifier.

## 34.5 Variant inventory

- source rule count;
- Java physical advanced rule/variant count;
- Python compiled variant count;
- OR expansion count;
- phrase expansion count;
- duplicate public full-ID count;
- exact parity result.

## 34.6 Tests

- focused unit tests;
- translated upstream assertions;
- synthetic advanced Java oracle cases;
- real Russian advanced-rule oracle cases;
- embedded example totals;
- wheel tests;
- complete repository pytest total;
- failures/skips.

## 34.7 Oracle provenance

- build ID;
- JAR SHA-256;
- manifest binding result.

## 34.8 Known limitations

List only deliberately deferred features and target task:

```text
0009 unification
0010 Java/XML filters
0011 Java rules
0012 spelling/suppression/etc.
```

Do not list an unimplemented 0008 feature as a harmless limitation while claiming Task 0008 complete.

## 34.9 Git completion

Record:

```text
implementation commit SHA
push target branch
remote verification result
```

---

# 35. Acceptance criteria

Task 0008 is accepted only if **all** applicable criteria below are true.

## Pin/runtime

1. LT pin remains exactly v6.8 / `e807fcde6a6506191e1470744d2345da28c26be6`.
2. Production runtime remains Java-free.
3. No LT server/runtime dependency is added.
4. No alternative NLP engine is used as a semantic shortcut.
5. Task-0007 accepted behavior remains regression-covered.
6. No unrelated TextQA work is included.

## Inventory/classification

7. A deterministic Task-0008 advanced inventory exists.
8. The Task-0007 core inventory remains preserved as historical baseline.
9. Source categories/rulegroups/rules/examples totals are revalidated.
10. Every advanced feature family has exact occurrence counts.
11. Every bounded/enum attribute has exact observed-value distribution.
12. Every source rule has feature usage independent of remaining blockers.
13. Every source rule has a deterministic post-0008 disposition.
14. Unknown/unclassified source rules equal zero.
15. All 506 accepted Task-0007 source rules remain runnable.
16. All 157 baseline pure-0008-deferred rules are promoted unless a pinned-source classifier error is explicitly proven and documented.
17. Multi-blocker rules lose implemented 0008 blockers but retain real 0009/0010/0012 blockers.
18. Generic `<match>` behavior is no longer incorrectly assigned wholesale to Task 0010.
19. Actual `<filter class>` rules remain deferred to 0010.
20. `suppress_misspelled` remains deferred to 0012.

## Variant model

21. Java physical rule/variant count after OR/phrase expansion is inventoried.
22. Python does not collapse multiple executable variants sharing a public full ID.
23. Internal variant identity is stable and deterministic.
24. Variant execution order matches Java for oracle cases.
25. Public findings preserve upstream rule/full IDs.
26. `check_rule()` covers every applicable variant of a logical rule.
27. `check_sentence()` does not deduplicate findings by ID alone.

## Matcher state machine

28. Fixed-width Task-0007 matching is replaced/refactored sufficiently for advanced state.
29. Per-attempt state records pattern-element/source-token mapping.
30. Optional absent elements are represented explicitly.
31. Skipped ranges are represented explicitly.
32. Repeated ranges are represented explicitly.
33. Marker span is derived from actual matched state.
34. Full-pattern span is derived from actual matched state.
35. State does not leak between attempts/rules/sentences.
36. Start-position behavior matches pinned Java oracle.
37. Post-match overlap/max filtering matches pinned Java oracle.

## Skip

38. `skip=-1` is supported exactly.
39. Finite skip values used by Russian rules are supported exactly.
40. Invalid skip ranges fail closed.
41. Skip operates on the correct LT token array, not whitespace string tokens.
42. Skip + marker spans match Java.
43. Skip + optional/repetition interactions match Java.
44. Skip + scope-next exception behavior matches Java.
45. Skip + match formatting retains exact skipped text when requested.

## Min/max

46. `min=0` is supported exactly.
47. `min=1` behavior remains correct.
48. Other min values fail as pinned Java does.
49. `max=2`, larger observed finite values, and `max=-1` are supported.
50. `max=0` fails.
51. Out-of-range max fails.
52. Adjacent optional elements match Java.
53. Optional any-token behavior matches Java.
54. Greedy repeated-element extent matches Java.
55. Multiple repeated elements match Java.
56. Omitted optional suggestion references match Java.
57. Optional/repeated marker spans match Java.

## Exceptions/whitespace/chunks

58. `scope=current` remains correct.
59. `scope=previous` matches Java.
60. `scope=next` matches Java.
61. Scope-next sentence-end workaround matches Java.
62. Previous/next exceptions work across multiple readings.
63. Exception `spacebefore` matches Java for observed values.
64. Token `spacebefore` matches Java for observed values.
65. Invalid whitespace enum values fail closed.
66. Literal chunk matching is supported.
67. Chunk regex behavior is supported when present/required.
68. Chunk negation matches Java.
69. Multiple/no-chunk-tag cases are tested.
70. Matching does not mutate chunk tags.

## AND/OR/phrases

71. `<and>` is one logical source-token position, not sequential tokens.
72. AND conditions may be satisfied across different readings exactly as Java allows.
73. Missing AND member prevents a match.
74. AND chunk conditions match Java.
75. AND exceptions match pinned behavior.
76. `<or>` alternatives execute without variant loss.
77. Multiple OR groups preserve Java expansion/order semantics.
78. OR marker spans match Java.
79. OR variants keep public rule identity correctly.
80. Actual pinned Russian phrase/ref constructs are inventoried.
81. Every nonzero pinned Russian phrase/ref construct is implemented.
82. Phrase expansion/reference order matches Java.
83. Phrase logical element numbering matches Java.
84. `<match no>` through phrase expansion matches Java.
85. Marker state at phrase reference location matches Java.
86. Unsupported/invalid phrase references fail closed.

## Raw POS / antipattern

87. `pattern@raw_pos` uses exact pre-disambiguation token state.
88. Ordinary patterns continue using post-disambiguation state.
89. At least one Java differential case distinguishes raw vs post-disambiguation behavior.
90. Rule-local antipatterns are executed.
91. Rulegroup antipattern inheritance is executed.
92. Antipattern marker/artificial-marker behavior matches pinned Java.
93. Partial/full overlap suppression matches Java.
94. One antipattern match does not suppress unrelated main-rule matches incorrectly.
95. Antipattern state does not leak between rules.

## Generic `<match>` / formatting

96. Token-level `<match>` references resolve through advanced match state.
97. Token-level references with skip work.
98. Token-level references with optional elements work.
99. Native `RussianSynthesizer` is used where pinned MatchState requires synthesis.
100. `include_skipped` values used by Russian rules are implemented exactly.
101. Skipped whitespace reconstruction matches Java.
102. Case-conversion values used by Russian rules are implemented exactly.
103. Java-style regex replacement capture syntax is reproduced correctly.
104. Invalid regex/replacement behavior is explicit, not silently swallowed.
105. POS regexp/replace behavior used by Russian rules is implemented.
106. `setpos` behavior used by Russian rules is implemented.
107. Static lemma `<match>` behavior used by Russian rules is implemented.
108. Multi-form synthesis output order matches Java.
109. Backreference-looking source token text does not recurse into formatter parsing.
110. Spelling-dependent suppression is not falsely claimed by 0008.

## Offsets/results

111. Marker UTF-16 offsets match Java.
112. Full-pattern UTF-16 offsets match Java.
113. Python codepoint offsets are derived separately and correctly.
114. Non-BMP-before-match case is covered.
115. Non-BMP-inside-skipped/repeated region is covered.
116. Exact source slicing is asserted.
117. Message strings match Java for oracle cases.
118. Short messages match Java for oracle cases.
119. Suggestions and order match Java for oracle cases.
120. Finding order matches Java for oracle cases.

## Oracle/upstream tests/examples

121. Every new oracle fixture resolves build provenance via `oracle_manifest.json`.
122. Fixture LT version equals the project pin.
123. Fixture LT commit equals the project pin.
124. Fixture JAR SHA equals the trusted manifest build record.
125. Synthetic advanced oracle corpus contains at least 100 discriminating cases.
126. Every implemented advanced feature family has Java differential coverage.
127. Every nonzero Russian advanced feature family has at least one real-rule oracle case or documented combination coverage.
128. Relevant `PatternRuleMatcherTest` advanced assertions are translated.
129. Relevant `PatternRuleLoaderTest` advanced assertions are translated.
130. Additional relevant upstream assertions are translated or explicitly deferred with target task.
131. Upstream source-file counts and Python-test counts use separate units.
132. All 988 Task-0007 embedded examples still pass exactly.
133. Every example for newly promoted 0008 rules is executed.
134. Correct examples have zero target-rule findings.
135. Incorrect examples validate exact marker/correction semantics where provided.
136. No whitespace/NBSP/strip normalization is used to fake exact parity.

## Packaging/compat/report

137. Real wheel test still builds and installs an isolated wheel.
138. Wheel contains the required grammar resources.
139. Wheel smoke executes at least one core-0007 rule.
140. Wheel smoke executes at least one genuinely advanced newly promoted 0008 rule.
141. Wheel smoke does not import repository `src/` or `third_party/` accidentally.
142. Wheel production smoke does not invoke Java.
143. `compat/compatibility.json` contains exact post-0008 source-rule counts.
144. Compatibility records executable variant count separately from source-rule count.
145. Compatibility records exact runnable/deferred example counts.
146. Compatibility records advanced oracle counts.
147. Compatibility parity metrics are only 1.0 for fields actually asserted.
148. Completion report contains exact advanced feature counts.
149. Completion report contains before/after blocker transition counts.
150. Completion report contains source vs variant counts.
151. Completion report contains oracle build ID and JAR SHA.
152. Completion report contains exact full-suite test totals and required skips.
153. Completion report contains all deliberate remaining target-task limitations.
154. Full Tasks 0001–0008 pytest suite passes.
155. Required skips equal zero.
156. No regression in accepted 0001–0007 oracle fixtures.
157. No unrelated files are changed.
158. Task completion is committed.
159. Current branch is pushed to origin.
160. Remote completion commit is verified.
161. Task 0009 is not started automatically.

---

# 36. Suggested implementation sequence

```text
1. Read Task 0008 + accepted 0007 report/handoff.
2. Regenerate advanced feature inventory from pinned grammar.xml.
3. Inspect exact pinned Java advanced matcher sources/tests.
4. Build Java loader variant inventory before choosing Python OR/phrase representation.
5. Separate feature_usage from remaining blockers/classification.
6. Introduce advanced match-state/tokenPositions-equivalent model.
7. Port skip + min/max + post-match longest/overlap behavior.
8. Port previous/next exceptions + spacebefore + chunk predicates.
9. Port AND semantics.
10. Port OR/phrase expansion/variant identity.
11. Port raw_pos token-source selection.
12. Port antipattern suppression.
13. Port token-level Match references and generic MatchState formatting.
14. Reclassify all 892 source rules.
15. Generate trusted synthetic Java advanced oracle fixture.
16. Generate trusted real-Russian advanced-rule oracle fixture.
17. Port relevant upstream PatternRule tests.
18. Execute all examples for 0007+0008 runnable rules.
19. Extend isolated wheel smoke with a real advanced rule.
20. Reconcile compatibility/report.
21. Run complete 0001–0008 suite.
22. Review git diff/status and remove unrelated changes.
23. Commit Task 0008.
24. Push current branch to origin.
25. Verify remote commit.
26. Stop. Do not start Task 0009.
```

---

# 37. Completion command discipline

The coding agent must follow `AGENTS.md`:

```text
implement
-> focused tests
-> full 0001-0008 tests
-> completion report
-> git diff/status review
-> one intentional task commit
-> push current branch to origin
-> verify remote commit
-> stop
```

No force push.  
No history rewrite.  
No PR/merge/tag/release unless explicitly requested.  
No automatic Task 0009 implementation.

---

# 38. Definition of done

Task 0008 is done when the native Python engine no longer treats the pinned Russian advanced matcher surface as a collection of opaque blockers.

At completion:

- all accepted Task-0007 core rules still behave identically;
- every pure Task-0008-deferred Russian source rule is executable or a previously hidden non-0008 dependency is proven from pinned source and explicitly reclassified;
- advanced rule variants are not lost;
- skip/min/max/advanced exceptions/chunks/AND/OR/phrases/raw-pos/antipattern/generic MatchState behavior used by Russian grammar has trusted Java differential evidence;
- all newly runnable embedded examples are exercised;
- remaining deferred rules are deferred only for clearly named future-task dependencies;
- runtime remains Python-only;
- the final pushed commit is visible on the remote branch.

Only then proceed to Task 0009 — Unification.
