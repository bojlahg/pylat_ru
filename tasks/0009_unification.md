# Task 0009 — Unification Engine

**Status:** READY  
**Baseline:** Task 0008 accepted at `5a2f4c032609ee2ce371ca5bb886883a186a3d83`  
**Target branch:** `main`  
**Pinned LanguageTool:** `v6.8`, commit `e807fcde6a6506191e1470744d2345da28c26be6`

---

# 1. Goal

Implement native Python LanguageTool-compatible **pattern unification** for the pinned Russian grammar, preserving the exact observable semantics of the pinned Java implementation while keeping the production runtime Java-free.

Task 0009 owns the semantics of:

```text
<unification feature="..."> ... </unification>
<equivalence type="..."> ... </equivalence>
<unify ...> ... </unify>
<unify-ignore> ... </unify-ignore>
feature/type restrictions attached to a unify block
positive unification
negated unification
neutral elements inside unify-ignore
final unified-reading filtering
```

The target transition is:

```text
Task-0008 runnable rules
        +
all rules blocked only by unification
        ↓
Task-0009 runnable rules
```

Rules that still require a true XML/Java filter after their unification blocker is removed remain deferred to Task 0010.

Task 0009 is **not** merely a post-match agreement check. Pinned LanguageTool unification participates in the pattern-matching state machine, operates on the subset of readings that matched each pattern token, intersects configured equivalence features, and can return filtered `AnalyzedTokenReadings` that affect later `<match>`/suggestion formatting.

---

# 2. Accepted Task-0008 baseline

Do not regress the accepted Task-0008 implementation.

Accepted baseline commit:

```text
5a2f4c032609ee2ce371ca5bb886883a186a3d83
```

Accepted source-rule disposition:

```text
source XML rules total:                        892

CORE_0007_RUNNABLE:                            506
ADVANCED_0008_RUNNABLE:                        229
DEFERRED_0009_UNIFICATION:                      24
DEFERRED_0010_FILTER:                           16
DEFERRED_0012_SPELLING_OR_SUPPRESSION:         110
MULTI_BLOCKER:                                   7
UNKNOWN:                                         0

runnable source rules:                         735
deferred source rules:                         157
```

Accepted embedded-example totals, using runtime `GrammarLoader` semantics:

```text
total examples:                               2446
incorrect:                                    1039
correct:                                      1407

runnable 0007+0008 examples:                  1738
  incorrect:                                   837
  correct:                                     901

deferred examples:                             708
  incorrect:                                   202
  correct:                                     506

DEFERRED_0009_UNIFICATION examples:             216
  incorrect:                                    41
  correct:                                     175
```

Accepted advanced matcher evidence:

```text
Java physical pattern rules:                   907
Python physical/compiled variants:             907
exact ordered token-signature parity:          yes
runnable Python variants:                      747
synthetic advanced Java-oracle cases:           141
real Russian advanced-rule oracle cases:        750
accepted full suite:                            302 passed
required skips:                                   0
```

The accepted Task-0008 inventory currently records these remaining blocker combinations relevant to 0009:

```text
pattern:unify                                             24 rules
filter:AdvancedSynthesizerFilter + pattern:unify           4 rules
```

Therefore the current source evidence implies **28 source rules use a remaining unification blocker**:

- 24 are pure Task-0009 rules and should become runnable in 0009;
- 4 also require `org.languagetool.rules.ru.AdvancedSynthesizerFilter` and must remain deferred to Task 0010 after their unification blocker is removed.

Any discrepancy discovered by the dedicated Task-0009 inventory must be explained from pinned source before changing these expectations.

---

# 3. Expected post-0009 disposition

If the dedicated pinned-source audit confirms the accepted Task-0008 classifier, Task 0009 should end with:

```text
CORE_0007_RUNNABLE:                            506
ADVANCED_0008_RUNNABLE:                        229
UNIFICATION_0009_RUNNABLE:                      24
DEFERRED_0010_FILTER:                           20
DEFERRED_0012_SPELLING_OR_SUPPRESSION:         110
MULTI_BLOCKER:                                   3
UNKNOWN:                                         0

runnable source rules:                         759
deferred source rules:                         133
```

The 4 `unify + AdvancedSynthesizerFilter` rules are expected to transition from `MULTI_BLOCKER` to `DEFERRED_0010_FILTER`.

If the 24 pure-unification rules and their accepted 216 examples promote exactly, expected global runtime-example totals become:

```text
runnable examples:                            1954
  incorrect:                                   878
  correct:                                    1076

deferred examples:                             492
  incorrect:                                   161
  correct:                                     331
```

These are **expected invariants, not hand-written replacement truth**. The Task-0009 inventory must derive the exact transition from the pinned grammar and fail if the source proves otherwise without a documented classifier correction.

---

# 4. Raw pinned Russian unification surface known at baseline

The accepted canonical Task-0008 raw XML inventory records:

```text
<unification> elements:                          8
unification@feature attributes:                  8
<equivalence> elements:                         26
<feature> elements:                             38
<unify> elements:                               28
<unify-ignore> elements:                        12
unify@negate attributes:                        27
```

Task 0009 must regenerate and **context-split** these counts rather than relying on this summary alone.

At minimum distinguish:

- global/root/ruleset unification definitions from rule-local match structures;
- equivalence definitions by feature and type;
- local `<feature>` restrictions inside `<unify>`;
- all feature/type values actually present;
- positive versus negated unify blocks;
- explicit versus default values;
- `<unify-ignore>` positions and contained structures;
- per-rule counts;
- overlap with Task-0008 features (`skip`, min/max, AND/OR, exceptions, raw-pos, antipatterns, token-level match, marker spans);
- overlap with remaining Task-0010/0012 blockers.

Zero-occurrence generic constructs must be recorded as zero. Do not manufacture a Russian production compatibility claim from generic Java support alone.

---

# 5. Source of truth

Read these before changing production semantics.

## 5.1 Project files

- `AGENTS.md`
- `docs/Handoff_pylat_ru.md`
- `tasks/0008_advanced_xml_matching.md`
- `reports/0008_advanced_xml_matching.md`
- `compat/russian_grammar_advanced_inventory.json`
- `compat/rule_variant_inventory.json`
- `compat/compatibility.json`
- `compat/oracle_manifest.json`
- `src/pylat_ru/grammar/model.py`
- `src/pylat_ru/grammar/loader.py`
- `src/pylat_ru/grammar/classifier.py`
- `src/pylat_ru/grammar/matcher.py`
- `src/pylat_ru/grammar/formatter.py`
- `src/pylat_ru/grammar/engine.py`
- `src/pylat_ru/analysis.py`

## 5.2 Pinned upstream implementation

Inspect the exact pinned sources for at least:

- `languagetool-core/src/main/java/org/languagetool/rules/patterns/Unifier.java`
- `.../UnifierConfiguration.java`
- `.../EquivalenceTypeLocator.java`
- `.../XMLRuleHandler.java`
- `.../PatternRuleHandler.java`
- `.../PatternToken.java`
- `.../PatternTokenMatcher.java`
- `.../AbstractPatternRulePerformer.java`
- `.../PatternRuleMatcher.java`
- `.../Match.java`
- `.../MatchState.java`
- any directly called helper required for exact unification behavior.

Do not infer unification semantics from XML names such as `feature`, `type`, or `negate`.

## 5.3 Missing pinned sources must be vendored narrowly

At the accepted 0008 baseline, the repository does not contain every unification-specific core source required for a self-contained audit.

If still absent, vendor the exact pinned versions of the required files, expected to include at least:

```text
Unifier.java
UnifierConfiguration.java
EquivalenceTypeLocator.java
XMLRuleHandler.java
```

For every newly vendored source:

1. use exactly commit `e807fcde6a6506191e1470744d2345da28c26be6`;
2. record upstream path;
3. record byte size;
4. record SHA-256;
5. record license/provenance;
6. update `third_party/languagetool/UPSTREAM.json`;
7. update `third_party/languagetool/license_inventory.json`;
8. vendor no broader subtree than required.

Do not implement from a web snippet while leaving the audited source absent from the project.

## 5.4 Pinned upstream tests

Inspect and inventory at minimum:

- `UnifierTest.java`;
- relevant unification assertions/resources from `PatternRuleLoaderTest.java`;
- relevant XML handler tests/resources;
- any direct upstream test for `UnifierConfiguration` / equivalence lookup;
- any applicable matcher test involving unification state.

The pinned `UnifierTest.java` includes at least behavior equivalent to:

```text
testUnificationCase
testUnificationNumber
testUnificationNumberGender
testUnificationMultipleFeats
testUnificationMultipleFeatsWithMultipleTypes
testUnificationNegation
testUnificationAddNeutralElement
```

Port assertions, not merely source test-file names.

Do not falsely claim `PatternRuleMatcherTest` contains dedicated unification coverage if the pinned file does not.

---

# 6. Critical semantic model

## 6.1 Unification is reading-aware

Pinned unification operates on `AnalyzedTokenReadings`, not on one arbitrarily selected POS tag.

For each source token participating in a unify block:

1. normal pattern matching first determines which readings satisfy the pattern token;
2. only those matching readings participate in unification;
3. configured equivalence predicates map each reading to feature/type values;
4. compatible feature values are intersected across participating tokens;
5. the candidate match fails if the required common feature set becomes empty;
6. on success, final readings may be filtered to those compatible with the surviving common feature values.

A design such as:

```python
if gender(token1) == gender(token2):
    pass
```

is not acceptable.

## 6.2 Unification is part of the match attempt

Do not implement unification as:

```text
advanced matcher returns RuleMatch
→ run agreement check afterward
→ discard if incompatible
```

Pinned `AbstractPatternRulePerformer` threads one unifier through the match attempt and can use final filtered readings before message/suggestion formatting.

Python must integrate unification state with the Task-0008 per-attempt match state.

## 6.3 Configuration and selection are different concepts

Preserve the distinction between:

- global unification/equivalence definitions mapping a feature/type to a `PatternToken`-like predicate;
- local feature/type restrictions on a `<unify>` block;
- actual pattern elements that consume source-token positions.

Do not conflate an equivalence-definition token with a source-consuming pattern token.

## 6.4 `<unify>` is a structural scope, not a synthetic source token

Pinned `PatternRuleHandler` uses internal placeholder/token state while parsing but applies unification metadata to the real contained pattern tokens and removes the placeholder from the final consuming pattern sequence.

Python must preserve the observable result:

- a `<unify>` wrapper itself does not consume a source token;
- its contained elements retain normal Task-0008 logical positions;
- marker and `<match no>` numbering remain pinned-equivalent;
- OR/phrase expansion remains pinned-equivalent;
- unification metadata is attached to the correct compiled positions.

## 6.5 `<unify-ignore>` is neutral, not absent

Tokens inside `<unify-ignore>` still participate in ordinary pattern matching and span/numbering state, but they must not constrain the feature intersection.

Pinned neutral-element handling must be preserved across skip/min/max state where applicable.

---

# 7. Audit and correct the provisional Python loader model

Task 0008 intentionally preserved deferred unification structure without executing it. Task 0009 must now prove that the preserved model is semantically exact enough for execution.

The current Python model/loader is provisional and must not be treated as source truth merely because it parses all 892 rules.

Audit at minimum:

```text
FeatureDef
EquivalenceDef
UnificationDef
PatternUnify
PatternUnifyIgnore
ALLOWED_UNIFICATION_*
ALLOWED_EQUIVALENCE_*
ALLOWED_UNIFY_*
ALLOWED_FEATURE_*
_parse_unifications()
_parse_unify()
_parse_feature()
_parse_equivalence()
_parse_unify_ignore()
```

Pinned `PatternRuleHandler` has generic feature/type-selection behavior within unify scopes. Reconcile this with the current Python `<feature>` representation.

If the pinned Russian file has zero occurrences of a generic `<type>` form, record that zero separately; nevertheless translate the upstream generic loader/unifier cases needed to prove the implementation architecture.

No accepted XML child or attribute may be silently ignored.

Unknown or malformed unification XML must fail closed with `GrammarFormatError` or the project’s typed compatibility error.

---

# 8. Phase 0 — Dedicated Task-0009 inventory

Create a deterministic generator, for example:

```text
tools/russian_grammar_unification_inventory.py
```

and committed artifact:

```text
compat/russian_grammar_unification_inventory.json
```

Do not overwrite the Task-0008 advanced inventory; it remains the accepted historical baseline.

## 8.1 Required provenance

Record and test:

```text
schema_version
pinned_lt_version
pinned_lt_commit
grammar_xml_path
grammar_xml_size_bytes
grammar_xml_sha256
baseline_task_0008_commit
generator_path
generator_sha256
oracle_manifest_path
```

Baseline commit must equal:

```text
5a2f4c032609ee2ce371ca5bb886883a186a3d83
```

Regeneration must be byte-exact.

## 8.2 Raw XML inventory

Record exact physical counts and distributions for:

```text
unification elements
unification@feature
equivalence elements
equivalence@type
feature elements
feature@id
type elements/type@id if present
unify elements
unify@negate
unify-ignore elements
pattern tokens inside unify
pattern tokens inside unify-ignore
AND/OR/phrase/ref inside unify if present
exceptions inside unify tokens
markers containing/intersecting unify scopes
```

Reconcile raw counts against `compat/inventory.json` / accepted raw Task-0008 inventory wherever the same unit already exists.

## 8.3 Configuration inventory

For every unification definition record:

```text
source order
feature ID
number of equivalence types
equivalence type names
normalized equivalence predicate structure
representative raw XML descriptor
```

Record duplicate `(feature,type)` definitions, if any, and prove the exact pinned duplicate policy.

Pinned `UnifierConfiguration.setEquivalence()` uses first-definition-wins behavior. If duplicates are absent from Russian data, still add a direct upstream/synthetic regression for the generic policy.

## 8.4 Rule-local inventory

For every source rule using unification record:

```text
full_id
source_order
Task-0008 state
number of unify scopes
positive/negated scopes
number of unify-ignore scopes
selected features
selected equivalence types per feature
contained logical pattern positions
advanced-feature overlaps
remaining non-0009 blockers
embedded example counts
physical variant count
```

## 8.5 Transition matrix

For all 892 rules produce:

```text
full_id
Task-0008 state
uses_unification
unification blocker removed by 0009
remaining blockers
Task-0009 expected state
```

Expected transitions, subject only to pinned-source correction:

```text
506 CORE_0007_RUNNABLE -> CORE_0007_RUNNABLE
229 ADVANCED_0008_RUNNABLE -> ADVANCED_0008_RUNNABLE
24 DEFERRED_0009_UNIFICATION -> UNIFICATION_0009_RUNNABLE
4 MULTI_BLOCKER(unify+AdvancedSynthesizerFilter) -> DEFERRED_0010_FILTER
all other deferred rules retain their real remaining blockers
UNKNOWN -> 0
```

Do not claim the 4 filter-dependent rules runnable merely because unification now works.

---

# 9. Native unification configuration

Implement a native structure equivalent to the pinned `UnifierConfiguration` behavior.

Recommended conceptual model:

```python
feature_id
  -> equivalence_type
       -> compiled PatternToken predicate
```

Requirements:

- deterministic insertion/source order;
- first definition wins for duplicate `(feature,type)` if pinned Java does so;
- equivalence predicate keeps full matching semantics needed by pinned definitions;
- no Java regex/parser/runtime dependency;
- config is immutable/read-only after grammar compilation;
- config is not rebuilt per sentence;
- unknown feature/type handling matches pinned Java/loader behavior;
- source provenance remains traceable for diagnostics/tests.

Do not reduce equivalence predicates to ad-hoc string parsing if pinned Java evaluates them with `PatternTokenMatcher` semantics.

---

# 10. EquivalenceTypeLocator equivalent

Implement the exact native behavior required to map a source token reading to an equivalence type for a requested feature.

Use the pinned `EquivalenceTypeLocator` and `PatternTokenMatcher` semantics as source of truth.

Required cases:

- one matching equivalence type;
- no matching type;
- multiple configured types;
- regex/POS-based equivalence predicates;
- text-based predicates if used/supported;
- ambiguous source ATR with multiple readings;
- null/unknown POS reading;
- pseudo/SENT tags where relevant;
- deterministic result ordering;
- duplicate definitions;
- no exception semantics accidentally introduced when pinned locator uses no-exception matching.

Do not derive Russian grammatical features by parsing tag substrings unless that is exactly what the pinned configured equivalence predicates produce.

---

# 11. Per-attempt native Unifier state

Create a native per-match-attempt state object equivalent to pinned `Unifier` behavior.

It must not be shared mutable state between rules/sentences.

Track at minimum:

```text
state: INIT / UNIFYING / NEUTRAL or exact equivalent
unified boolean/current feasibility
matched-reading groups by participating logical token
initial-group boundary for multiple scopes
selected feature/type restrictions
neutral elements
final feature intersection
final filtered ATRs
```

Required lifecycle equivalents:

```text
startUnify()
stopUnify()
reset()
addNeutralElement(...)
isUnified(...)
testUnification()
getFinalUnified() or equivalent
```

Different internal names are fine. Observable behavior is not.

---

# 12. Positive unification semantics

Port exact positive unification behavior.

Required synthetic cases:

- two tokens sharing one feature value -> success;
- two tokens with disjoint feature values -> failure;
- first token ambiguous, second disambiguates to one common value;
- both tokens ambiguous with one common value;
- both ambiguous with multiple common values;
- three-token intersection;
- one participating token with no equivalence value;
- one ATR with multiple readings where only some matched the base PatternToken;
- base pattern match succeeds but matching-reading subset has no common unify value -> fail;
- common value exists only in a reading that did **not** match the base PatternToken -> fail;
- no stale reading from an earlier start position participates.

The final intersection must be based on readings accepted by the pattern matcher, not all original readings.

---

# 13. Multiple features and local type restrictions

Implement exact behavior for multiple simultaneously unified features.

Required cases:

- one feature only;
- two features, both compatible;
- first feature compatible, second incompatible;
- independent ambiguous alternatives;
- multiple allowed types for one feature;
- restricted allowed type excludes otherwise compatible reading;
- empty type selection semantics exactly as pinned Java;
- multiple local `<feature>` selectors;
- unknown feature/type behavior;
- deterministic feature iteration where it can affect filtered output.

Translate all applicable assertions from pinned `UnifierTest.testUnificationNumberGender`, `testUnificationMultipleFeats`, and `testUnificationMultipleFeatsWithMultipleTypes`.

---

# 14. Negated unification

`<unify negate="yes">` must follow pinned Java semantics.

Do **not** implement it as simply:

```python
return not positive_unification_result
```

Pinned negation interacts with per-token matching and feature availability.

Required differential cases:

- ordinary positive-compatible sequence under negated unify;
- ordinary incompatible sequence under negated unify;
- ambiguous readings where at least one combination would unify;
- ambiguous readings where no combination unifies;
- missing equivalence feature on one token;
- selected feature/type restriction under negation;
- more than two tokens;
- negated scope with neutral element;
- negated scope with skip/min/max where allowed;
- repeated execution to prove no stale state.

Port every relevant assertion from `testUnificationNegation`.

---

# 15. `<unify-ignore>` neutral semantics

Implement exact neutral-element behavior.

A neutral element:

- must still satisfy its normal pattern predicate;
- still contributes to source span/tokenPositions/marker state;
- does not constrain the unification feature intersection;
- must not disappear from `<match>` numbering;
- must not mutate the final common feature set;
- must preserve pinned behavior when skip/min/max changes source positions.

Required cases:

- one neutral middle token;
- neutral first/last contained element if schema allows;
- multiple neutral elements;
- neutral element with multiple ATR readings;
- neutral element that fails its ordinary pattern predicate -> whole match fails;
- neutral element inside marker;
- neutral element adjacent to optional token;
- neutral element adjacent to finite/infinite skip;
- neutral repeated element where accepted;
- two unify blocks separated by neutral/non-unified pattern positions.

Translate pinned `testUnificationAddNeutralElement` and any additional indexed-neutral behavior required by `AbstractPatternRulePerformer`.

---

# 16. Multiple unify scopes in one rule

Audit whether pinned Russian rules contain multiple unify scopes in one source pattern and cover generic source behavior regardless when upstream tests require it.

Preserve the pinned semantics of `initialListSize` / equivalent boundary management so that:

- completing one unify scope does not contaminate the next;
- prior token groups are not accidentally re-intersected;
- neutral elements belong to the correct scope;
- final filtered readings correspond to the correct logical positions;
- reset/start/stop sequencing matches Java.

Add synthetic Java differentials for at least two successive unify scopes even if Russian occurrence is zero, because the native state architecture must not accidentally make one global intersection for the entire rule.

---

# 17. Integration with Task-0008 advanced matcher state

Unification must work with existing accepted advanced matching semantics without reimplementing them inconsistently.

Audit and differential-test combinations with:

- finite `skip`;
- `skip=-1`;
- `min=0` optional token present/absent;
- finite `max` repetition;
- unlimited `max=-1` where meaningful;
- AND groups;
- OR-expanded variants;
- `scope=previous` / `scope=next` exceptions;
- token/exception `spacebefore`;
- chunk predicates;
- `pattern@raw_pos`;
- rule/rulegroup antipatterns;
- explicit markers;
- token-level `<match>` references;
- generic message/suggestion `<match>` formatting.

Do not change accepted 0008 semantics merely to simplify unification.

---

# 18. Matched-reading subset integration

Task-0008 pattern predicates may accept only a subset of an ATR’s readings.

The unifier must receive the pinned-equivalent subset.

Required controlled-reading cases:

```text
ATR readings: [A, B]
pattern token accepts only A
unification value exists only on B
=> must NOT unify through B
```

and converse cases where only the accepted reading carries the common value.

This is mandatory Java differential coverage because a naive implementation over the original full ATR can look correct on ordinary Russian words while being semantically wrong.

---

# 19. Final unified-reading filtering

Pinned `Unifier.testUnification()` can return filtered ATRs containing only readings consistent with the final common feature intersection.

Python must preserve this behavior wherever it is observable.

Requirements:

- preserve source token text;
- preserve start/end offsets;
- preserve whitespace metadata;
- preserve chunk tags;
- preserve only compatible lexical readings;
- preserve deterministic reading order matching pinned Java;
- do not mutate the shared analyzed sentence globally unless pinned behavior requires a match-local view;
- formatting sees the correct filtered view for the current candidate;
- subsequent rule execution cannot observe accidental mutation from a previous rule.

Prefer a match-local overlay/view rather than mutating shared `AnalyzedTokenReadings` objects.

---

# 20. `<match>` / suggestion interaction

Because final unified readings can influence `MatchState` and synthesis, add direct parity cases where unification changes observable formatted output.

Cover where applicable:

- `<match no>` reads a token whose ATR was filtered by unification;
- POS replacement/synthesis receives the filtered reading set;
- multiple original readings collapse to one final form;
- multiple surviving readings preserve Java suggestion order;
- no synthesis result;
- skipped/optional token references;
- marker span remains unchanged while suggestion output changes.

The 4 rules requiring `AdvancedSynthesizerFilter` remain deferred to Task 0010. Do not implement that filter inside formatter/unifier merely to make those rules pass.

---

# 21. Raw-pos and disambiguation boundaries

If a unify rule is also `pattern@raw_pos`, unification must operate on the exact pre-disambiguation token stream selected by the accepted Task-0008 matcher.

Do not:

- retag;
- reconstruct removed readings heuristically;
- mix pre-disambiguation ATRs for one token with post-disambiguation ATRs for another;
- mutate the canonical pre/post snapshots.

Inventory actual Russian overlap and add direct controlled parity when nonzero.

---

# 22. OR/variant semantics

Task 0008 already proves Java/Python physical variant count and order parity.

Unification must not disturb variant identity/order.

Required cases:

- unify inside an OR-expanded rule;
- OR alternative changes which readings participate;
- one variant unifies and another does not;
- both variants unify with distinct findings;
- public full ID remains upstream-equivalent;
- finding order remains deterministic;
- no cross-variant unifier state leakage.

If pinned Russian overlap is zero, retain generic synthetic coverage and record zero real-rule occurrence.

---

# 23. Antipattern interaction

Unification is not an excuse to bypass accepted Task-0008 antipattern suppression.

Where combinations occur or synthetic coverage is useful, verify:

- main pattern unifies then is suppressed by antipattern;
- candidate fails unification before antipattern result becomes relevant;
- antipattern execution does not mutate unifier state;
- multiple candidate matches with only one unifying/suppressed;
- no immunization/state leak to following rules.

Do not duplicate the entire antipattern engine in the unifier.

---

# 24. Error and fail-closed behavior

Audit exact pinned loader/runtime behavior and add typed regressions for malformed/unresolvable unification structures.

At minimum cover:

- missing `unification@feature`;
- missing `equivalence@type`;
- equivalence without valid token predicate if pinned schema rejects it;
- duplicate feature/type definition behavior;
- malformed local feature selector;
- malformed/unknown local type selector;
- invalid `unify@negate` value;
- illegal child in `<unify>`;
- illegal child in `<unify-ignore>`;
- unresolved feature reference;
- unresolved equivalence type;
- structurally empty unify block if pinned loader/runtime has defined behavior;
- unsupported recursive/nested unify form;
- any construct accepted by schema but still unsupported by Python.

No silent defaulting, skipping, placeholder `Pattern()` replacement, or “best effort” agreement.

---

# 25. Dedicated Java differential oracle

Create a trusted Java differential operation specifically for unification.

Recommended fixtures:

```text
tests/fixtures/oracle_unification_synthetic.json
tests/fixtures/oracle_unification_russian_rules.json
```

The Java oracle may use controlled `AnalyzedTokenReadings` injection to create reading combinations that ordinary Russian text cannot reliably force through the full tagger.

Production runtime must remain Java-free.

## 25.1 Fixture provenance

Every new fixture must contain and tests must validate through `compat/oracle_manifest.json`:

```text
schema_version
pinned_lt_version
pinned_lt_commit
oracle_build_id
oracle_jar_sha256
generator operation/corpus version
case_count
```

No hard-coded trusted JAR SHA detached from the manifest.

## 25.2 Synthetic corpus

Create at least **100 distinct discriminating Java-generated unification cases**.

The matrix must cover at minimum:

- one-feature success/failure;
- two-feature success/failure;
- multiple allowed types;
- ambiguous readings;
- matched-reading subset vs full ATR;
- no equivalence value;
- positive unification;
- negated unification;
- neutral elements;
- multiple neutral elements;
- multiple unify scopes;
- duplicate configuration definitions;
- type restrictions;
- exceptions inside participating token predicates;
- skip;
- optional elements;
- repetition;
- AND/OR combinations;
- markers/full spans;
- filtered final ATR output;
- `<match>`/suggestion formatting affected by filtered readings;
- repeated calls/interleaved rules;
- non-BMP source offsets where spans are exposed.

Cases must be genuinely distinct, not duplicate real grammar examples relabeled synthetic.

Create machine-readable coverage mapping:

```text
feature_dimension -> synthetic case IDs
```

and assert all required dimensions are covered.

## 25.3 Real Russian corpus

For all 24 newly runnable pure-unification source rules:

- include every embedded example in Java/Python parity, or prove the dedicated grammar-example suite supplies exact equivalent coverage;
- include at least one matching case and one near-miss where practical;
- record rule ID/full ID;
- record source execution state;
- record which unification definitions/features/types are exercised.

For the 4 `unify + AdvancedSynthesizerFilter` rules:

- prove unification-stage behavior with a focused pre-filter oracle if possible;
- keep public full-rule execution deferred to 0010;
- do not fake final finding parity by skipping the filter.

---

# 26. Exact oracle fields

Compare every observable field applicable to unification cases:

- rule ID/full ID/sub ID;
- finding count/order;
- marker UTF-16 offsets;
- full-pattern UTF-16 offsets;
- independently derived Python codepoint offsets;
- exact source slices;
- message;
- short message;
- suggestions and order;
- selected/final unified reading signatures when using controlled low-level oracle;
- final common feature/type set where exposed by the dedicated harness;
- success/failure reason/state for low-level synthetic cases where useful.

A fixture asserting only `matched: true` is insufficient for cases whose purpose is reading filtering.

---

# 27. Translate upstream Unifier tests

Port all applicable assertions from pinned `UnifierTest.java`.

Report separately:

```text
upstream test method
number of relevant source assertions
number translated
number intentionally deferred
deferred target task/reason
```

At minimum cover the behavior represented by:

```text
testUnificationCase
testUnificationNumber
testUnificationNumberGender
testUnificationMultipleFeats
testUnificationMultipleFeatsWithMultipleTypes
testUnificationNegation
testUnificationAddNeutralElement
```

Also inspect loader/XML handler tests for configuration definition and feature/type parsing.

Do not mix Java source-method counts, Python test-function counts, and assertion counts into one number.

---

# 28. Execute newly runnable grammar examples

After reclassification:

1. retain all 988 accepted Task-0007 core examples;
2. retain all 750 accepted Task-0008 advanced examples;
3. execute all 216 examples belonging to the 24 pure unification rules;
4. keep examples of still-filter-dependent rules deferred from public final-rule assertions;
5. run the complete repository grammar example suite.

Expected, subject to inventory confirmation:

```text
runnable source rules:       759
runnable examples:          1954
incorrect:                   878
correct:                    1076
```

Correct examples must produce zero target-rule findings.

Incorrect examples must validate exact target-rule behavior, marker spans, and corrections/suggestions where provided. Do not normalize whitespace/NBSP or trim strings to fake parity.

---

# 29. Execution-state model

Add an explicit provenance-preserving Task-0009 runnable state, recommended:

```text
UNIFICATION_0009_RUNNABLE
```

`RussianGrammarEngine.get_runnable_rules()` and `check_sentence()` must execute:

```text
CORE_0007_RUNNABLE
ADVANCED_0008_RUNNABLE
UNIFICATION_0009_RUNNABLE
```

Rules retaining filters/spelling blockers remain non-runnable.

`check_rule()` on a still-deferred rule must raise the existing structured unsupported-feature error with all remaining blockers after removing the implemented unification blocker.

---

# 30. State isolation and reentrancy

Add regressions proving unification state cannot leak across:

- two start positions in one rule;
- two physical variants;
- two logical rules;
- two unify scopes;
- two sentences;
- repeated calls to one singleton engine;
- successful candidate followed by failed candidate;
- failed candidate followed by successful candidate;
- rule execution after a rule that filtered its match-local ATRs.

No mutation of compiled grammar/configuration objects is allowed during matching.

---

# 31. Performance/caching boundaries

Correctness dominates, but avoid obvious pathological work.

Requirements:

- compile global equivalence predicates once per grammar load;
- do not parse unification XML per sentence;
- do not rebuild the whole equivalence map per match attempt;
- per-attempt state should contain only dynamic candidate data;
- do not deep-copy the complete sentence graph for every unify token;
- prefer match-local filtered ATR views/overlays;
- no Java subprocess in production or normal runtime tests;
- record rough full grammar Task-0009 test runtime in completion report.

No hard performance SLA is required.

---

# 32. Real wheel proof

Extend the isolated real-wheel test.

The wheel proof must:

1. build a real wheel;
2. install it to an isolated target;
3. ensure repository `src/` / `third_party/` are not accidental import fallbacks;
4. execute the Python-only pipeline:

```text
raw text
→ sentence/word tokenization
→ RussianTagger
→ RussianDisambiguator
→ RussianChunker
→ XML grammar engine
→ unification-enabled rule
```

5. run at least:
   - one accepted 0007 core rule;
   - one accepted 0008 advanced rule;
   - one newly runnable real 0009 unification rule;
6. assert exact rule ID, offsets, message and suggestions for the unification smoke;
7. prove no Java executable/server is invoked by production runtime.

---

# 33. Compatibility artifacts

Update `compat/compatibility.json` with explicit units.

At minimum record:

```text
source XML rules total
CORE_0007 source rules
ADVANCED_0008 source rules
UNIFICATION_0009 source rules
total runnable source rules
deferred 0010 source rules
deferred 0012 source rules
remaining multi-blocker rules
UNKNOWN count

runnable/deferred example totals
runnable/deferred incorrect/correct totals

raw unification element counts
unification rule count
negated-unify rule/count
unify-ignore count
configuration feature count
equivalence type count

synthetic unification oracle cases
real Russian unification oracle cases
translated upstream assertions
wheel proof result
```

Do not overwrite historical 0007/0008 evidence with unlabeled new values.

Do not set parity metric to `1.0` for a field that is not actually asserted.

---

# 34. Completion report

Create:

```text
reports/0009_unification.md
```

The report must contain at minimum:

## 34.1 Baseline

- accepted Task-0008 commit;
- pinned LT version/commit;
- exact pre-0009 states;
- exact pre-0009 example totals.

## 34.2 Upstream provenance

For every newly vendored/critical unification source:

```text
path
byte size
SHA-256
license/provenance
purpose in Task 0009
```

## 34.3 Raw/configuration inventory

- raw `<unification>`, `<equivalence>`, `<feature>`, `<type>`, `<unify>`, `<unify-ignore>` counts;
- observed values/distributions;
- feature/type/equivalence mapping;
- duplicate policy/results;
- real Russian rule overlap.

## 34.4 Rule transition table

Report exact counts for:

```text
remained CORE_0007
remained ADVANCED_0008
promoted UNIFICATION_0009
moved unify+filter to 0010-only
remaining 0010
remaining 0012
remaining multi-blocker
unknown
```

## 34.5 Semantic implementation

Describe native equivalents of:

```text
UnifierConfiguration
EquivalenceTypeLocator
Unifier per-attempt state
neutral element handling
negation
final reading filtering
```

State any internal differences that are proven behaviorally equivalent.

## 34.6 Tests

- focused unit tests;
- translated upstream assertions;
- synthetic Java oracle count;
- real Russian unification oracle count;
- all newly runnable grammar examples;
- old 0001–0008 regressions;
- wheel test;
- complete pytest total/failures/errors/skips.

## 34.7 Oracle provenance

- build ID;
- JAR SHA-256;
- manifest binding result.

## 34.8 Known limitations

Only deliberate later-task limitations:

```text
0010 Java/XML filters
0011 Java rules
0012 spelling/suppression/etc.
```

Do not list an unimplemented 0009 unification behavior as a harmless limitation while claiming completion.

## 34.9 Git completion

Record concrete prior implementation/review commits, push target `origin/main`, and remote verification result.

Do not attempt the impossible self-referential exercise of embedding the SHA of the commit being created inside itself.

---

# 35. Required files/artifacts

Expected additions/changes include, naming may vary when justified:

```text
tasks/0009_unification.md
reports/0009_unification.md
compat/russian_grammar_unification_inventory.json
compat/compatibility.json
third_party/languagetool/UPSTREAM.json
third_party/languagetool/license_inventory.json

src/pylat_ru/grammar/unification.py        # recommended
src/pylat_ru/grammar/model.py
src/pylat_ru/grammar/loader.py
src/pylat_ru/grammar/classifier.py
src/pylat_ru/grammar/matcher.py
src/pylat_ru/grammar/engine.py
src/pylat_ru/grammar/formatter.py          # only if match-local filtered ATR integration requires it

tools/russian_grammar_unification_inventory.py
tools/differential_lt.py or focused oracle helper

tests/fixtures/oracle_unification_synthetic.json
tests/fixtures/oracle_unification_russian_rules.json

tests/unit/test_unification.py
tests/unit/test_grammar_unification_inventory.py
tests/upstream/test_unifier_oracle_parity.py
tests/upstream/test_unification_russian_rule_oracle_parity.py
tests/upstream/test_russian_grammar_examples.py
tests/unit/test_real_wheel_grammar.py
```

If a different layout is cleaner, use it, but all evidence must remain auditable and deterministic.

---

# 36. Acceptance criteria

Task 0009 is accepted only if all applicable criteria below are true.

## Pin/runtime

1. LT pin remains exactly v6.8 / `e807fcde6a6506191e1470744d2345da28c26be6`.
2. Production runtime remains Java-free.
3. No LT server/runtime/network dependency is added.
4. No substitute NLP/morphology engine is introduced.
5. Accepted Tasks 0001–0008 behavior remains regression-covered.
6. No unrelated TextQA work is included.

## Inventory/provenance

7. Deterministic Task-0009 inventory exists.
8. Baseline Task-0008 inventory remains preserved.
9. Inventory baseline commit equals `5a2f4c032609ee2ce371ca5bb886883a186a3d83`.
10. Grammar XML path/size/SHA are recorded and asserted.
11. Generator path/SHA are recorded and byte-exact regeneration passes.
12. Raw unification-related XML counts are exact.
13. Raw counts are context-split rather than conflating definitions and rule-local constructs.
14. Every feature/type/equivalence definition is inventoried.
15. Every unification-using source rule is inventoried independently from remaining blockers.
16. Unknown/unclassified source rules equal zero.
17. Every newly vendored source is exact-pinned and licensed/provenanced.
18. Missing/unknown upstream provenance fails closed.

## Loader/configuration

19. Global unification definitions parse according to pinned `XMLRuleHandler` semantics.
20. Equivalence type definitions preserve full predicate semantics.
21. Duplicate `(feature,type)` policy matches pinned `UnifierConfiguration`.
22. Local unify feature/type restrictions parse according to pinned `PatternRuleHandler` semantics.
23. `<unify>` wrapper consumes no extra logical source-token position.
24. `<unify-ignore>` structure is preserved and executable.
25. No accepted child/attribute is silently ignored.
26. Malformed unification XML fails with typed error.
27. Current provisional `FeatureDef`/loader model is corrected where source audit proves mismatch.
28. Zero-occurrence generic Russian constructs are reported as zero rather than falsely claimed supported by Russian evidence.

## Equivalence lookup

29. Native equivalence lookup matches pinned `EquivalenceTypeLocator` behavior.
30. Lookup operates on exact ATR readings.
31. Pattern-token predicate semantics used by equivalence definitions match pinned behavior.
32. Missing feature value behavior matches Java.
33. Multiple configured types behave deterministically.
34. Unknown/malformed feature/type behavior is explicit.
35. No heuristic Russian-tag substring parser replaces configured equivalence predicates without exact proof.

## Unifier state

36. Unifier state is per match attempt.
37. Reset/start/stop lifecycle matches pinned behavior.
38. State does not leak between start positions.
39. State does not leak between variants.
40. State does not leak between rules.
41. State does not leak between sentences/repeated calls.
42. Multiple unify scopes do not contaminate one another.
43. Compiled configuration objects remain immutable during matching.

## Positive unification

44. One-feature compatible readings unify.
45. One-feature incompatible readings reject candidate.
46. Ambiguous readings preserve possible common feature values.
47. Three-or-more participating tokens intersect correctly.
48. Only base-pattern-matching readings participate.
49. A nonmatching reading cannot rescue unification.
50. No-equivalence-value behavior matches Java.
51. Final common feature intersection matches Java.
52. Positive unification matches direct controlled-reading Java differential cases.

## Multiple features/types

53. Two-feature agreement works.
54. One compatible and one incompatible feature rejects candidate.
55. Multiple allowed equivalence types per feature work.
56. Local type restriction filters possible readings exactly.
57. Empty/default selection semantics match Java.
58. Multiple local feature selectors match Java.
59. Upstream multiple-feature assertions are translated.

## Negation

60. Negated unification is implemented from pinned semantics, not `not positive_result`.
61. Compatible sequence under negation matches Java result.
62. Incompatible sequence under negation matches Java result.
63. Ambiguous reading negation matches Java.
64. Missing equivalence-value negation matches Java.
65. Multi-token negation matches Java.
66. Negation state does not leak.
67. Pinned `testUnificationNegation` assertions are translated.

## Neutral/unify-ignore

68. Neutral token still performs ordinary pattern matching.
69. Neutral token does not constrain common feature set.
70. Neutral token remains in spans/token numbering.
71. Multiple neutral tokens work.
72. Neutral failure of ordinary predicate fails whole candidate.
73. Neutral interaction with skip works.
74. Neutral interaction with optional/repeated elements works where applicable.
75. Pinned neutral-element assertions are translated.

## Task-0008 integration

76. Finite skip + unify matches Java.
77. Infinite skip + unify matches Java where applicable.
78. Optional token + unify matches Java.
79. Repeated token + unify matches Java.
80. AND + unify matches Java.
81. OR variant + unify matches Java.
82. Previous/next exception + unify matches Java where applicable.
83. spacebefore + unify preserves accepted semantics.
84. chunk + unify preserves accepted semantics.
85. raw-pos + unify uses the correct pre/post token stream.
86. antipattern + unify preserves accepted suppression behavior.
87. marker/full-pattern spans remain exact.
88. Variant ordering/identity remains exact.

## Final reading filtering/formatting

89. Successful unification can return filtered ATR readings as pinned Java does.
90. Filtered ATR preserves token text/offset/whitespace/chunks.
91. Only compatible lexical readings survive.
92. Shared sentence ATRs are not accidentally mutated across rules.
93. `<match>` formatting uses the match-local filtered view where Java does.
94. POS replacement/synthesis sees pinned-equivalent filtered readings.
95. Suggestion strings/order match Java for filtering-sensitive cases.
96. No `AdvancedSynthesizerFilter` behavior is smuggled into 0009.

## Rule disposition

97. All 506 core rules remain runnable.
98. All 229 Task-0008 advanced rules remain runnable.
99. All 24 pure-unification rules become `UNIFICATION_0009_RUNNABLE`, unless pinned audit proves and documents a classifier error.
100. The 4 unify+AdvancedSynthesizerFilter rules remove only the unification blocker and remain deferred to 0010.
101. Expected runnable source total is 759 if baseline audit is confirmed.
102. Expected deferred source total is 133 if baseline audit is confirmed.
103. Remaining true filter blockers stay in 0010.
104. Spelling/suppression blockers stay in 0012.
105. UNKNOWN remains zero.

## Grammar examples

106. All 988 Task-0007 core examples remain passing.
107. All 750 Task-0008 advanced examples remain passing.
108. All 216 examples on the 24 pure unification rules are executed.
109. Newly runnable correct examples produce zero target-rule findings.
110. Newly runnable incorrect examples validate target finding/spans/corrections exactly where supplied.
111. Expected runnable example total is 1954 if the baseline transition is confirmed.
112. Expected runnable incorrect/correct totals are 878/1076 if confirmed by generated inventory.
113. No strip/NBSP/whitespace normalization fakes parity.

## Oracle

114. Every new fixture resolves oracle provenance through `compat/oracle_manifest.json`.
115. Fixture version equals LT 6.8.
116. Fixture commit equals the pinned commit.
117. Fixture JAR SHA equals the exact trusted build record.
118. Synthetic unification corpus contains at least 100 distinct discriminating cases.
119. Synthetic feature coverage map has no required missing dimension.
120. Controlled ATR cases prove matched-reading-subset semantics.
121. Controlled cases prove final filtered-reading semantics.
122. Controlled cases prove negation semantics.
123. Controlled cases prove neutral-element semantics.
124. Real Russian corpus covers every newly runnable unification rule or records an explicit justified combination strategy.
125. The 4 filter-dependent unification rules are not falsely reported as final finding parity.
126. Java expected output is generated by trusted Java, not Python.

## Upstream tests

127. Relevant assertions from `UnifierTest.java` are inventoried.
128. All applicable `UnifierTest` assertions are translated.
129. Relevant loader/XML handler assertions are translated or explicitly deferred with reason.
130. Source test methods, Python test functions and assertion counts use separate units.
131. No upstream test file is called “ported” merely because one unrelated assertion was copied.

## Packaging/report

132. Isolated wheel still builds and installs.
133. Wheel production path is Java-free.
134. Wheel runs one real newly promoted 0009 unification rule exactly.
135. `compat/compatibility.json` records post-0009 source-rule counts with explicit units.
136. Compatibility records runnable/deferred example counts.
137. Compatibility records unification oracle counts.
138. Compatibility parity metrics are only 1.0 where actually asserted.
139. Completion report contains exact raw/configuration inventory.
140. Completion report contains exact 0008→0009 transition table.
141. Completion report contains upstream source provenance.
142. Completion report contains translated assertion accounting.
143. Completion report contains oracle build ID/JAR SHA/manifest binding result.
144. Completion report contains exact final pytest/failure/error/skip totals.
145. Completion report lists only genuine later-task limitations.

## Final completion

146. Complete Tasks 0001–0009 pytest suite passes.
147. Required skips equal zero.
148. No accepted 0001–0008 oracle fixture regresses.
149. No unrelated files are changed.
150. Task completion is intentionally committed.
151. Current branch is pushed to `origin/main`.
152. Exact remote completion commit is verified.
153. Task 0010 is not started automatically.

---

# 37. Suggested implementation sequence

```text
1. Read Task 0009, accepted 0008 report/inventories, AGENTS.md and handoff.
2. Vendor only missing exact-pinned unification source files and record provenance.
3. Build deterministic unification inventory before changing execution states.
4. Audit current FeatureDef/UnificationDef/PatternUnify loader model against XMLRuleHandler/PatternRuleHandler.
5. Correct loader/model schema fail-closed.
6. Implement native immutable UnifierConfiguration equivalent.
7. Implement native EquivalenceTypeLocator equivalent.
8. Implement per-attempt Unifier state and direct low-level translated upstream tests.
9. Integrate positive unification into advanced matcher using only matched ATR readings.
10. Implement final common-feature intersection and match-local filtered ATR output.
11. Implement negated unification.
12. Implement unify-ignore neutral semantics.
13. Prove multiple unify scopes and state isolation.
14. Differential-test skip/min/max/AND/OR/marker/match-reference combinations.
15. Build >=100 controlled synthetic trusted-Java cases.
16. Build real Russian unification oracle corpus.
17. Reclassify exactly the rules whose unification blocker is removed.
18. Execute all newly runnable grammar examples.
19. Extend isolated wheel proof with a real 0009 rule.
20. Reconcile compatibility.json and write completion report.
21. Run full Tasks 0001–0009 suite with zero required skips.
22. Review diff/status, commit intentionally, push origin/main, verify remote.
23. Stop. Do NOT start Task 0010.
```

---

# 38. Explicit stop condition

Task 0009 is complete only when native Python unification is proven against the pinned Java semantics and all pure-unification Russian rules are correctly promoted.

After completion:

```text
commit
push origin/main
verify remote
stop
```

Do **not** begin Task 0010, do not implement `AdvancedSynthesizerFilter`, and do not turn still-deferred filter rules runnable merely to improve coverage statistics.
