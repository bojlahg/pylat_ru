# Task 0006 — Russian Synthesizer Parity (`RussianSynthesizer` / `BaseSynthesizer`)

## Status

READY

## Goal

Implement the next native Python stage of the pinned LanguageTool Russian pipeline: **`RussianSynthesizer`**.

The task must reproduce the observable behavior of the pinned LanguageTool `v6.8` Russian synthesizer without Java/JRE at production runtime.

The primary transformation is:

```text
AnalyzedToken(lemma=...)
      +
exact LT POS tag / POS-tag regexp
      ↓
RussianSynthesizer
  ├─ russian_synth.dict
  ├─ added.txt
  ├─ removed.txt
  ├─ tags_russian.txt
  └─ BaseSynthesizer semantics
      ↓
ordered synthesized word forms
```

This stage will later be used by grammar suggestions, XML `<match>`/synthesizer features and Java-rule ports. Exact ordering and exact LT tag semantics therefore matter.

This is **not** a generic Russian inflector and must not use pymorphy, Natasha, spaCy, Stanza, neural morphology, heuristics, or a different morphological dictionary as a semantic substitute.

---

# Pinned compatibility target

The compatibility pin remains unchanged:

```text
LanguageTool tag:    v6.8
LanguageTool commit: e807fcde6a6506191e1470744d2345da28c26be6
Morfologik version:  2.1.9
```

Do not update the LanguageTool pin in Task 0006.

Relevant pinned sources/resources include:

```text
languagetool-language-modules/ru/
  src/main/java/org/languagetool/synthesis/ru/RussianSynthesizer.java
  src/test/java/org/languagetool/synthesis/ru/RussianSynthesizerTest.java
  src/main/resources/org/languagetool/resource/ru/
    russian_synth.dict
    russian_synth.info
    tags_russian.txt
    added.txt
    removed.txt

languagetool-core/
  src/main/java/org/languagetool/synthesis/
    Synthesizer.java
    BaseSynthesizer.java
    ManualSynthesizer.java
    SynthesizerTools.java
```

The already accepted Task 0002 implementation provides the native Morfologik CFSA2 reader and `MorfologikDictionary.synthesize(lemma, pos_tag)` primitive. **Reuse it. Do not implement a second FSA reader.**

Task 0002 verified at least:

```text
russian_synth.dict
  size:      1,489,459 bytes
  FSA:       CFSA2 0xC6
  flags:     0x0007
  separator: +
  encoding:  koi8-r
  encoder:   SUFFIX
```

Representative already-proven raw synthesis-dictionary lookups include:

```text
семья|NN:Inanim:Fem:Sin:Nom -> семья
семья|NN:Inanim:Fem:Sin:R   -> семьи
дом|NN:Inanim:Masc:PL:Nom   -> дома
```

These are dictionary-foundation proofs only. Task 0006 must implement the **actual LanguageTool synthesizer layer around the dictionary**.

---

# Verified upstream behavior

## `RussianSynthesizer`

Pinned `RussianSynthesizer.java` is intentionally thin:

```text
RESOURCE_FILENAME = /ru/russian_synth.dict
TAGS_FILE_NAME    = /ru/tags_russian.txt
INSTANCE          = singleton

constructor:
  super(RESOURCE_FILENAME, TAGS_FILE_NAME, "ru")
```

Therefore most semantics come from pinned `BaseSynthesizer`.

## Exact `BaseSynthesizer.lookup()` order

For Russian, the effective lookup order is:

```text
1. russian_synth.dict lookup for key lemma + "|" + posTag
2. append forms from /ru/added.txt via ManualSynthesizer
3. remove every form listed for the same lemma+posTag in /ru/removed.txt
4. if /ru/do-not-synthesize.txt exists, remove those forms too
```

At the pinned Russian resource tree, Task 0006 must independently verify whether `/ru/do-not-synthesize.txt` exists. Current repository inspection indicates it is absent; inventory wins.

### Critical scope detail

Pinned `BaseSynthesizer` loads:

```text
/ru/added.txt
/ru/removed.txt
/ru/do-not-synthesize.txt (only if present)
```

It does **not** automatically load:

```text
/ru/added_custom.txt
/ru/removed_custom.txt
```

Those custom files are relevant to the Russian tagger path but must not be silently added to synthesizer semantics unless pinned upstream source proves otherwise.

## Exact result semantics

Preserve these observable rules:

- binary forms come first;
- manual-added forms are appended after binary forms;
- generic deduplication is not performed;
- removals behave like Java `List.removeAll(...)`: all matching occurrences are removed;
- unknown lemma/tag returns an empty result;
- lookup is exact and case-sensitive unless the pinned upstream code/oracle proves otherwise;
- raw LT tag strings are authoritative, including trailing empty components such as `VB:INF:`;
- do not normalize/canonicalize POS tags before lookup;
- do not sort synthesized forms unless the pinned implementation does so.

## `ManualSynthesizer` parsing semantics

Pinned `ManualSynthesizer` reads UTF-8 text with the format:

```text
fullform<TAB>lemma<TAB>postag
```

It also supports:

```text
#separatorRegExp=<regex>
```

and:

- trims each input line;
- ignores blank/comment lines;
- strips inline text after `#` before splitting data lines;
- requires exactly 3 fields;
- preserves multiple forms for the same `(lemma, posTag)` in encounter order;
- returns no result for null/unknown `(lemma, posTag)`;
- exposes the set of possible tags found in the manual file.

A Python implementation does not need to port Java's hash-compressed internal storage. It must reproduce observable behavior and fail explicitly on malformed directives/lines/regexes.

## Exact `synthesize()` behavior

Pinned `BaseSynthesizer` exposes the conceptual calls:

```text
synthesize(token, posTag)
synthesize(token, posTag, posTagRegExp)
synthesizeForPosTags(lemma, predicate)
getPosTagCorrection(posTag)
getTargetPosTag(posTags, targetPosTag)
```

For normal exact synthesis:

```text
lemma = token.lemma
results = lookup(lemma, posTag)
removeExceptions(results)
```

`RussianSynthesizer` does not override `isException()`, so `removeExceptions()` is effectively a no-op for Russian at this pin.

## POS-tag regexp synthesis

When `posTagRegExp=true`, pinned `BaseSynthesizer`:

1. compiles the supplied expression as a Java regex;
2. lazily loads possible tags from `tags_russian.txt`;
3. appends any tags from manual `added.txt` not already present;
4. iterates possible tags in the resulting order;
5. uses full-match semantics (`Pattern.matcher(tag).matches()`);
6. calls normal `lookup(lemma, matchedTag)` for each matched tag;
7. concatenates results in tag order;
8. does not generically deduplicate results.

Task 0006 must prove whether `added.txt` actually contributes any tags not already present in pinned `tags_russian.txt`. If it contributes none, record that fact rather than emulating irrelevant Java hash-set iteration behavior.

Invalid POS-tag regex must fail explicitly. Do not silently treat an invalid regexp as a literal tag.

## `tags_russian.txt` loading

Pinned `SynthesizerTools.loadWords()`:

- reads UTF-8;
- trims each line;
- skips blank lines;
- skips lines whose first non-whitespace character is `#`;
- otherwise keeps the entire trimmed line as a possible tag;
- preserves file order.

Task 0002 found 1,201 non-normalized/raw tag lines and 1,200 normalized unique tags, including a real trailing-whitespace anomaly in the source/tag dictionary area. Task 0006 must derive the exact list seen by **`SynthesizerTools.loadWords()`**, which trims each line, rather than reusing a differently normalized tag inventory by assumption.

## `getPosTagCorrection()`

Pinned `BaseSynthesizer` returns the input tag unchanged.

Russian does not override it.

## `getTargetPosTag()`

Pinned behavior:

```text
if posTags is empty:
    return targetPosTag
else:
    return the LAST element of posTags
```

Preserve this exactly.

## Special number tags

Pinned `BaseSynthesizer` recognizes:

```text
_spell_number_
_spell_number_:feminine
_spell_number_:Roman
```

Russian constructs `BaseSynthesizer` without a Russian Soros number-spelling file, while BaseSynthesizer separately attempts to initialize Roman-number support.

Do **not guess** the observable Russian behavior of these three tags. Phase 0/Java oracle must record it at the pinned build. Implement exactly what the oracle proves, including fallback behavior if a number-speller resource is absent.

Do not broaden Task 0006 into a generic Soros engine unless the pinned Russian synthesizer actually requires it for observable parity.

---

# Mandatory project constraints

Read and obey:

```text
AGENTS.md
docs/Handoff_pylat_ru.md
reports/0002_dictionary_formats_lt_russian_tagset.md
reports/0003_russian_sentence_word_tokenization_offsets.md
reports/0004_russian_tagger.md
reports/0005_russian_hybrid_disambiguator.md
compat/compatibility.json
compat/oracle_manifest.json
compat/russian_tagset.json
```

Requirements:

- Python-only production runtime;
- no Java/JRE/server/network dependency in package/runtime API;
- Java allowed only in development/conformance oracle tooling;
- reuse accepted Morfologik implementation;
- preserve exact output order;
- preserve exact raw LT POS strings;
- no silent resource fallback from an invalid packaged resource to checkout files;
- malformed resources/unsupported behavior must fail explicitly;
- parse/load resources once per long-lived synthesizer;
- package must work from an installed wheel without repository-relative `third_party/` paths;
- do not start Task 0007 automatically.

---

# Scope

## In scope

1. Native `RussianSynthesizer` implementation.
2. Exact binary `russian_synth.dict` lookup through the existing Task 0002 Morfologik reader.
3. Package-safe `russian_synth.dict` and `russian_synth.info`.
4. Package-safe `tags_russian.txt`.
5. Manual synthesizer behavior for pinned `/ru/added.txt` and `/ru/removed.txt`.
6. Explicit inventory/handling of `/ru/do-not-synthesize.txt` if present.
7. Exact output order and duplicate/removal behavior.
8. Exact literal POS synthesis.
9. POS-tag regexp synthesis over exact possible-tag order.
10. Invalid regexp failure semantics.
11. `getPosTagCorrection()` parity.
12. `getTargetPosTag()` parity.
13. Special `_spell_number_...` behavior proven by oracle.
14. Exact Java differential oracle fixtures for synthesis.
15. Deterministic synthesizer compatibility inventory.
16. Real installed-wheel smoke test.
17. Compatibility/report updates.

## Explicitly out of scope

Do not implement in Task 0006:

- `RussianChunker`;
- `grammar.xml` execution;
- XML grammar `<suggestion>` engine;
- `AdvancedSynthesizerFilter` or other grammar XML filters;
- Russian Java grammar rules;
- spelling/compound/repetition engines;
- `LanguageToolRU.check()`;
- general multilingual synthesizer architecture;
- pymorphy/Natasha-based inflection;
- a generic Soros interpreter unless required by proven RussianSynthesizer behavior;
- speculative case-restoration/suggestion formatting that belongs to grammar rules/filters.

`RussianChunker` remains a separate missing pipeline component. Do not mark it supported as a side effect of Task 0006.

---

# Phase 0 — Deterministic synthesizer inventory

Before writing the high-level synthesizer, create:

```text
tools/russian_synthesizer_inventory.py
compat/russian_synthesizer_inventory.json
```

Derive from pinned upstream/repository resources, never hardcode, at least:

```text
pinned LT tag/commit
Morfologik version

RussianSynthesizer.java:
  path
  size
  sha256

RussianSynthesizerTest.java:
  path
  size
  sha256
  number of @Test methods
  explicit synthesis assertions/cases

russian_synth.dict:
  path
  size
  sha256
  CFSA format/version
  flags
  encoding
  separator
  sequence encoder

russian_synth.info:
  path
  size
  sha256
  parsed metadata

tags_russian.txt:
  path
  size
  sha256
  raw line count
  SynthesizerTools-loaded tag count
  unique loaded tag count
  duplicate tags
  first/last tags in exact loaded order
  tags with trailing-empty colon components

added.txt:
  path
  size
  sha256
  data-row count
  separator directives
  distinct lemma+tag keys
  distinct tags
  duplicate forms per key
  tags absent from tags_russian.txt

removed.txt:
  same relevant statistics

added_custom.txt / removed_custom.txt:
  prove presence if present
  explicitly record used_by_pinned_russian_synthesizer = false unless source proves otherwise

do-not-synthesize.txt:
  exists true/false
  if true: hash/size/counts

BaseSynthesizer observable feature surface:
  exact synthesis
  regexp synthesis
  possible tags
  manual additions
  removals
  getPosTagCorrection
  getTargetPosTag
  special number tags
```

Also derive representative corpus candidates automatically:

- at least 10 simple exact binary synthesis keys;
- at least one key with multiple binary output forms if any exists;
- at least 3 manual-added forms that materially change result compared with binary-only lookup;
- at least 3 removed forms that materially change result compared with binary+added lookup;
- at least one exact trailing-empty-component tag such as `VB:INF:`;
- at least 5 regexp queries spanning noun/adjective/verb tags;
- at least one case-sensitive lemma difference;
- one unknown lemma;
- one unknown tag;
- special number-tag inputs.

If a requested category has zero real examples, record `count=0` and explain it. Do not manufacture data to satisfy the requested number.

The inventory artifact must have a byte-exact deterministic regeneration test.

---

# Phase 1 — Package synthesis resources

Task 0006 must add package-runtime copies of all resources actually required by the pinned Russian synthesizer.

Expected minimum:

```text
src/pylat_ru/resources/ru/
  russian_synth.dict
  russian_synth.info
  tags_russian.txt
```

`added.txt` and `removed.txt` already exist as packaged resources from Task 0004; reuse those exact copies if hashes match upstream.

Requirements:

- packaged `russian_synth.dict` byte-for-byte matches pinned upstream;
- packaged `russian_synth.info` byte-for-byte matches pinned upstream;
- packaged `tags_russian.txt` byte-for-byte matches pinned upstream;
- existing `added.txt` and `removed.txt` remain byte-for-byte pinned;
- package loaders use `importlib.resources` or equivalent package-safe access;
- a present-but-corrupt packaged file fails explicitly;
- production must not silently fall back to `third_party/...` after a packaged-resource parse/hash/format failure.

Repository checkout fallbacks, if retained for development, must only be used when the packaged resource is genuinely unavailable in a development context, not as corruption recovery.

---

# Phase 2 — Manual synthesizer

Implement an internal component such as:

```text
src/pylat_ru/synthesis/manual.py
```

with project-specific typed errors, for example:

```text
SynthesisError
SynthesisResourceError
ManualSynthesizerFormatError
SynthesisPatternError
```

The exact class names may differ, but callers must be able to distinguish resource/format/regexp failures from a legitimate empty synthesis result.

Required observable API can resemble:

```python
manual.lookup(lemma, pos_tag) -> tuple[str, ...]
manual.possible_tags -> tuple[str, ...] or deterministic read-only equivalent
```

Required semantics:

- UTF-8 input;
- default separator regex is tab;
- support `#separatorRegExp=`;
- trim input lines;
- ignore blank/comment lines;
- strip inline `#...` after recognizing a data line exactly as pinned Java does;
- require exactly 3 split fields;
- preserve form text/lemma/tag exactly after Java-equivalent trimming/splitting behavior;
- preserve forms for a `(lemma, tag)` in encounter order;
- no generic dedupe;
- unknown lookup returns empty tuple/list at the Python API boundary;
- malformed separator regexp raises explicit project error with source + line number;
- malformed row raises explicit project error with source + line number;
- no `except Exception: pass` around parser/resource loading.

The Java internal `+` suffix-compression optimization is not observable and need not be copied. A compact direct mapping is acceptable.

Add synthetic tests for:

- default tab separator;
- custom separator;
- inline comments;
- duplicate forms;
- multiple forms same key;
- different tags same lemma;
- malformed row;
- invalid separator regex;
- literal form beginning with `+` if relevant to pinned Java restriction;
- deterministic order.

---

# Phase 3 — Native `RussianSynthesizer`

Implement under a clear package, for example:

```text
src/pylat_ru/synthesis/
  __init__.py
  errors.py
  manual.py
  russian.py
```

Recommended public object:

```python
from pylat_ru.synthesis import RussianSynthesizer
```

A singleton/get-instance convenience is acceptable and useful because resources should be loaded once, but do not make tests impossible to isolate with injected resources.

## Exact synthesis API

Provide an API semantically equivalent to:

```python
synth.synthesize(token, pos_tag, pos_tag_regexp=False) -> tuple[str, ...]
```

where `token` is this project's `AnalyzedToken`.

Also provide a minimal internal/direct helper if useful:

```python
synth.lookup(lemma, pos_tag) -> tuple[str, ...]
```

Do not invent a large public API surface.

### Literal lookup

For normal tags:

```text
binary = russian_synth.dict synthesize(lemma, posTag)
manual = added.txt lookup(lemma, posTag)
results = binary + manual
results -= every string contained in removed.txt lookup(lemma, posTag)
results -= do-not-synthesize lookup if that resource exists
return results in remaining order
```

Use exact string equality for removals.

Do not sort or dedupe.

### `token.lemma`

The LanguageTool API synthesizes using `AnalyzedToken.getLemma()`, not the token surface.

Add tests proving token surface and lemma can differ and that lookup is driven by lemma.

For `lemma=None`, reproduce the observable pinned Java result proven by the oracle. Do not accidentally synthesize using the token surface as a fallback unless Java does so.

### Literal POS tag

Do not normalize:

```text
VB:INF:
```

into:

```text
VB:INF
```

Do not strip internal/trailing colon components.

### Regexp POS tag

Implement:

```python
synth.synthesize(token, pattern, pos_tag_regexp=True)
```

with semantics equivalent to Java `Pattern.matcher(tag).matches()`.

Important:

- compile once per call/pattern, not once per possible tag;
- invalid regex -> explicit `SynthesisPatternError` or equivalent;
- iterate `possible_tags` in exact derived order;
- invoke normal lookup for each matching tag;
- concatenate outputs in matched-tag order;
- do not dedupe across tags.

Python `re.fullmatch()` is acceptable only for regex syntax/features used by the pinned Russian grammar/oracle surface and after differential proof. If Java/Python regex dialect differences matter for actual pinned patterns, fail explicitly or implement compatibility for the active subset. Do not silently approximate.

### Possible tags initialization

Load once lazily or at construction:

```text
tags = SynthesizerTools-style tags_russian.txt list
for manual-added possible tag:
  if tag not already present:
    append it
```

Inventory must prove whether manual-only tags exist at this pin.

### `get_pos_tag_correction`

Return input tag unchanged.

### `get_target_pos_tag`

Exact behavior:

```python
if not pos_tags:
    return target_pos_tag
return pos_tags[-1]
```

### Special number tags

Expose/recognize exact constants equivalent to:

```text
_spell_number_
_spell_number_:feminine
_spell_number_:Roman
```

Implement only after differential oracle proves pinned Russian behavior for representative inputs:

```text
0
1
4
9
12
42
1999
2026
invalid/non-number input where meaningful
```

Do not infer from English/German behavior.

---

# Phase 4 — Differential Java oracle for synthesis

Extend the existing trusted Java oracle harness in:

```text
tools/differential_lt.py
```

Do not create a second unrelated provenance system.

Use the accepted immutable oracle manifest/build binding from Task 0005.

Add a synthesis fixture generator, for example:

```text
--generate-synthesizer-fixtures
```

Committed fixture:

```text
tests/fixtures/oracle_russian_synthesizer.json
```

Fixture metadata must include:

```text
schema_version
pinned_lt_version
pinned_lt_commit
oracle_build_id
oracle_jar_sha256
case_count
```

The fixture integrity test must resolve `oracle_build_id` through `compat/oracle_manifest.json` and require exact build SHA/version/commit equality. Do not accept a loose set of trusted hashes.

## Java oracle implementation

The Java fixture generator must instantiate/use:

```text
RussianSynthesizer.INSTANCE
AnalyzedToken
```

directly.

Do not use grammar rules as an indirect synthesis oracle.

Capture for every case:

```text
case id/category
input token surface
input lemma
input source pos tag if supplied
requested pos tag or regexp
pos_tag_regexp flag
exact output array in exact order
exception type/message for intentionally invalid regexp cases if represented
```

Also capture separate method cases for:

```text
getPosTagCorrection
getTargetPosTag
special number tags
```

## Minimum oracle corpus

Build at least ~50 meaningful cases, including:

1. Upstream `RussianSynthesizerTest.java` cases exactly.
2. Unknown lemma/tag.
3. Noun singular/plural and all represented cases.
4. Adjective gender/number/case forms.
5. Verb infinitive/past/present/imperative where dictionary entries exist.
6. `VB:INF:` trailing-empty tag.
7. At least one key with multiple output forms if present.
8. Binary-only forms.
9. Manual-added forms that are absent from binary synthesis if present.
10. Removed forms whose pre-removal source exists if present.
11. Duplicate-preservation case if real resource data produces one; otherwise synthetic unit proof.
12. Case-sensitive lemma behavior.
13. Token surface != lemma.
14. `lemma=None` behavior.
15. Exact tag vs regexp tag behavior.
16. Narrow regexp matching one tag.
17. Broad regexp matching several tags, with exact aggregate ordering.
18. Regex matching zero tags.
19. Invalid regex.
20. Special number tags.
21. `getTargetPosTag([], target)`.
22. `getTargetPosTag([one], target)`.
23. `getTargetPosTag([a,b,c], target)` returns last.
24. `getPosTagCorrection` identity for simple and odd tags.

Do not fill the fixture with dozens of trivial variants of the same lookup merely to reach a number. Feature coverage matters more than count.

Python parity tests must compare exact arrays/order against this Java-generated fixture.

---

# Phase 5 — Real-resource semantic tests

In addition to Java fixture parity, write focused tests proving why the high-level synthesizer differs from raw `MorfologikDictionary.synthesize()`.

Required categories:

### Binary synthesis

At minimum retain upstream-known assertions:

```text
семья + NN:Inanim:Fem:Sin:Nom -> [семья]
семья + NN:Inanim:Fem:Sin:R   -> [семьи]
unknown                       -> []
```

### Manual additions

Inventory real `added.txt` and find real `(lemma, tag, form)` rows where:

```text
raw binary result does not contain form
high-level RussianSynthesizer does contain form
```

Assert both sides.

If zero such entries exist, record that rather than inventing a case.

### Removals

Find real `removed.txt` rows where the form would otherwise be returned by binary/manual synthesis and prove high-level synthesizer removes it.

If no material removal rows exist for synthesis, prove/count that fact.

### Custom overlays excluded

If `added_custom.txt` or `removed_custom.txt` contain entries that could affect synthesis, add a focused test showing pinned `RussianSynthesizer` does **not** consume them unless Java oracle says otherwise.

This prevents accidental reuse of the Task 0004 tagger's overlay bundle.

### Exact order

For every found multi-form or regexp case, compare exact output order, not sets.

---

# Phase 6 — Wheel/package proof

Extend package tests so they build the actual wheel and inspect/install it.

The wheel must include at least the required synthesis resources:

```text
pylat_ru/resources/ru/russian_synth.dict
pylat_ru/resources/ru/russian_synth.info
pylat_ru/resources/ru/tags_russian.txt
pylat_ru/resources/ru/added.txt
pylat_ru/resources/ru/removed.txt
```

plus any additional resource proven necessary by Phase 0.

The installed-distribution subprocess must run with repository `src/` and `third_party/` unavailable from `sys.path` and perform real calls such as:

```python
RussianSynthesizer().synthesize(... семья ..., "NN:Inanim:Fem:Sin:R")
RussianSynthesizer().synthesize(..., r"NN:Inanim:Fem:Sin:.*", pos_tag_regexp=True)
```

Assert the module/resource paths come from the isolated installed target.

A `PYTHONPATH=src` smoke test is not an installed-package proof.

---

# Phase 7 — Compatibility and documentation

Update:

```text
compat/compatibility.json
reports/0006_russian_synthesizer.md
```

Add/update machine-readable fields for at least:

```text
RussianSynthesizer: SUPPORTED / PARTIAL / ...
exact lookup parity
regexp lookup parity
manual additions parity
removals parity
possible-tag ordering
special-number-tag parity
oracle case count/pass count
packaged resources/hash verification
known differences
```

Do not mark unrelated layers supported:

```text
RussianChunker          still not implemented unless already separately proven
XML grammar engine      not implemented by this task
XML filters             not implemented by this task
full rule checking      not implemented by this task
```

Report exact local test command(s) and results.

---

# Error handling / fail-closed requirements

Legitimate "no synthesized form" is an empty tuple/list and is **not an exception**.

These must be explicit errors, not empty results:

- missing required packaged synthesis dictionary;
- malformed `.info` metadata;
- unsupported FSA flags/format;
- malformed manual synthesis row;
- invalid `#separatorRegExp`;
- invalid POS-tag regexp requested with `pos_tag_regexp=True`;
- unsupported special behavior discovered in pinned upstream that has not been ported;
- fixture generation with unverified Java oracle build.

Never use broad exception suppression such as:

```python
try:
    ...
except Exception:
    pass
```

for compatibility/resource boundaries.

---

# Performance requirements

Parity first, but avoid obvious waste:

- `russian_synth.dict` loaded once per synthesizer instance/singleton;
- manual `added.txt`/`removed.txt` parsed once;
- `tags_russian.txt` loaded once;
- no full FSA expansion into millions of Python objects;
- regex possible-tag scan may be linear over ~1.2k tags, which is acceptable;
- exact synthesis should remain on-demand FSA lookup;
- no Java subprocess or network calls in production.

Add lightweight sanity timing only if useful; do not turn Task 0006 into a benchmark project.

---

# Required test structure

Use focused files, for example:

```text
tests/unit/test_manual_synthesizer.py
tests/unit/test_russian_synthesizer.py
tests/unit/test_synthesizer_inventory.py
tests/unit/test_synthesizer_resources.py
tests/upstream/test_russian_synthesizer_parity.py
tests/fixtures/oracle_russian_synthesizer.json
```

Names may differ, behavior requirements may not.

The complete Task 0001–0006 suite must pass.

Do not weaken/remove prior tests merely to make Task 0006 green.

---

# Acceptance criteria

Task 0006 is accepted only if all applicable criteria below are true.

1. Pinned LT version/commit remain unchanged.
2. Production Russian synthesis has no Java/JRE dependency.
3. Existing Task 0002 Morfologik implementation is reused.
4. `RussianSynthesizer` uses `russian_synth.dict` + pinned metadata.
5. `russian_synth.dict` is packaged in the wheel.
6. `russian_synth.info` is packaged in the wheel.
7. `tags_russian.txt` is packaged in the wheel.
8. Packaged files byte-match pinned upstream.
9. Exact synthesis uses `token.lemma`, not token surface fallback unless Java proves otherwise.
10. Exact POS tags are not normalized.
11. `VB:INF:`-style trailing components are preserved.
12. Binary result order matches Java.
13. Manual `added.txt` forms are appended after binary forms.
14. Manual forms preserve encounter order per key.
15. No generic result deduplication is introduced.
16. `removed.txt` removes all matching forms as Java `removeAll` does.
17. `/ru/do-not-synthesize.txt` presence/absence is inventoried and handled correctly.
18. `added_custom.txt` is not silently included in synthesizer semantics.
19. `removed_custom.txt` is not silently included in synthesizer semantics.
20. Unknown lemma returns empty output.
21. Unknown exact POS tag returns empty output.
22. Case-sensitive lemma behavior matches Java.
23. `lemma=None` behavior matches Java oracle.
24. `ManualSynthesizer` default separator behavior matches pinned Java for active resources.
25. `#separatorRegExp=` is supported.
26. Invalid manual separator regex fails explicitly.
27. Malformed manual rows fail explicitly with source/line context.
28. Inline-comment handling matches pinned Java.
29. `tags_russian.txt` possible tags preserve `SynthesizerTools.loadWords()` order.
30. Manual-only possible tags are appended only if they actually exist.
31. Regexp synthesis uses full-match tag semantics.
32. Regexp synthesis iterates tags in exact possible-tag order.
33. Regexp synthesis concatenates lookup results without generic dedupe.
34. Invalid regexp fails explicitly rather than falling back to literal lookup.
35. Regex matching no tags returns empty output.
36. At least one broad regexp oracle case verifies exact aggregate order.
37. `getPosTagCorrection()` is identity.
38. `getTargetPosTag([], target)` returns target.
39. `getTargetPosTag(nonempty, target)` returns last source tag.
40. Special `_spell_number_` behavior is oracle-proven and implemented.
41. Special feminine number-tag behavior is oracle-proven and implemented.
42. Special Roman number-tag behavior is oracle-proven and implemented.
43. No generic Soros framework is introduced without a demonstrated need.
44. Upstream `RussianSynthesizerTest.java` cases pass.
45. A Java synthesis oracle fixture exists.
46. Fixture metadata contains exact pinned version/commit.
47. Fixture metadata contains exact `oracle_build_id` and JAR SHA.
48. Fixture integrity resolves exact build record through `oracle_manifest.json`.
49. Fixture was generated from `RussianSynthesizer.INSTANCE`, not Python expectations.
50. Oracle corpus covers literal synthesis.
51. Oracle corpus covers regexp synthesis.
52. Oracle corpus covers manual additions/removals where materially applicable.
53. Oracle corpus covers unknown/case/null-lemma edge cases.
54. Oracle corpus covers special number tags.
55. Exact output sequence is compared, not sets.
56. `compat/russian_synthesizer_inventory.json` is generated deterministically.
57. Inventory byte-exact regeneration test passes.
58. Inventory records relevant source/resource hashes.
59. Inventory records actual manual overlay statistics.
60. Inventory records possible-tag ordering/statistics.
61. Inventory explicitly records custom-overlay exclusion.
62. Resource errors fail closed.
63. Corrupt packaged resource does not silently fall back to checkout source.
64. Actual wheel is built in tests.
65. Required synthesis resources are verified inside the wheel.
66. Isolated installed-wheel synthesis succeeds without repository paths.
67. Existing 0001–0005 tests continue to pass.
68. Full 0001–0006 suite passes with no hidden skips for required parity tests.
69. Completion report states exact test counts and known differences honestly.
70. `compat/compatibility.json` marks only actually proven synthesizer features supported.
71. `RussianChunker` is not falsely marked supported.
72. XML grammar engine is not started as part of Task 0006.
73. Task 0007 is not started automatically.
74. Completion diff is reviewed for unrelated changes.
75. Task completion is committed.
76. Current branch is pushed to `origin`.
77. Remote commit is verified after push.

---

# Suggested implementation sequence

```text
1. Read AGENTS + accepted reports
2. Phase-0 inventory pinned Russian synthesizer surface
3. Verify/package synth dict/info/tags resources
4. Implement ManualSynthesizer parity
5. Implement exact lookup composition
6. Implement possible-tags + regexp synthesis
7. Implement helper methods / special tags from oracle evidence
8. Extend trusted Java oracle
9. Generate committed synthesis fixture
10. Add exact differential parity tests
11. Add wheel/install proof
12. Regenerate compatibility inventory
13. Run focused tests
14. Run complete 0001–0006 suite
15. Update report + compatibility.json
16. git diff/status review
17. commit
18. push current branch
19. verify remote commit
20. stop; do not start 0007
```

---

# Completion report requirements

Create:

```text
reports/0006_russian_synthesizer.md
```

Include:

- exact implementation summary;
- pinned source/resource hashes;
- binary/manual/removal lookup ordering;
- possible-tag count/order findings;
- material manual-addition/removal examples or explicit zero-count result;
- special-number-tag oracle result;
- oracle build ID + SHA used;
- oracle case count;
- exact parity results;
- wheel resource verification;
- full test totals;
- known differences/unsupported behavior;
- commit SHA;
- push/remote verification result.

Do not claim Task 0006 complete until the remote commit is verified.

---

# Final scope boundary

At the end of Task 0006, the implemented project pipeline should conceptually contain:

```text
RussianSentenceTokenizer      ✅
RussianWordTokenizer          ✅
RussianTagger                 ✅
RussianHybridDisambiguator    ✅
RussianSynthesizer            ✅ Task 0006

RussianChunker                ⛔ still separate / not proven by this task
XML grammar engine            ⛔ Task 0007+
full Russian checking         ⛔ later tasks
```

The important result of Task 0006 is not merely that `семья` can become `семьи`. Task 0002 already proved that raw dictionary lookup.

The Task 0006 result is that **the Python-native synthesizer behaves like pinned LanguageTool's RussianSynthesizer at the API/ordering/overlay/regexp boundary that later grammar rules depend on**.
