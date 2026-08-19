# Task 0004 — Russian Tagger Parity (`RussianTagger` + `BaseTagger` Overlays)

## Status

READY

## Goal

Implement the native Python Russian morphological tagger required by the pinned LanguageTool pipeline:

```text
word tokens
  ↓
RussianTagger-compatible normalization
  ↓
BaseTagger-compatible case fallback
  ↓
combined word tagger
    ├─ added.txt / added_custom.txt
    ├─ russian.dict
    └─ removed.txt / removed_custom.txt
  ↓
AnalyzedTokenReadings-compatible morphology
    ├─ surface token
    ├─ lemma
    ├─ exact LT POS tag
    ├─ deterministic reading order
    └─ MayMissingYO chunk tag
```

Task 0004 must reproduce the observable behavior of pinned LanguageTool `v6.8` Russian tagging without Java at production runtime.

Task 0002 already provides the native Morfologik reader and lossless Russian tag representation. Task 0003 provides the tokenizer and source-offset layer. Task 0004 connects those foundations into the first real LT-compatible morphology stage.

This task covers the **Russian tagger only**. Do not implement disambiguation, chunking beyond the `MayMissingYO` marker emitted directly by `RussianTagger`, synthesis, grammar rules, spelling, or full `JLanguageTool` sentence assembly.

---

## Pinned compatibility target

The compatibility pin remains unchanged:

```text
LanguageTool tag:    v6.8
LanguageTool commit: e807fcde6a6506191e1470744d2345da28c26be6
Morfologik version:  2.1.9
```

Do not change the LanguageTool pin in Task 0004.

### Relevant pinned upstream implementation

Inspect and use as compatibility references at minimum:

```text
languagetool-language-modules/ru/src/main/java/org/languagetool/tagging/ru/RussianTagger.java
languagetool-language-modules/ru/src/test/java/org/languagetool/tagging/ru/RussianTaggerTest.java

languagetool-core/src/main/java/org/languagetool/tagging/BaseTagger.java
languagetool-core/src/main/java/org/languagetool/tagging/MorfologikTagger.java
languagetool-core/src/main/java/org/languagetool/tagging/ManualTagger.java
languagetool-core/src/main/java/org/languagetool/tagging/CombiningTagger.java
languagetool-core/src/main/java/org/languagetool/tagging/TaggedWord.java
languagetool-core/src/main/java/org/languagetool/AnalyzedToken.java
languagetool-core/src/main/java/org/languagetool/AnalyzedTokenReadings.java
languagetool-core/src/main/java/org/languagetool/chunking/ChunkTag.java
languagetool-core/src/main/java/org/languagetool/tools/StringTools.java
languagetool-core/src/test/java/org/languagetool/TestTools.java
```

Relevant pinned Russian resources:

```text
resource/ru/russian.dict
resource/ru/russian.info
resource/ru/added.txt
resource/ru/added_custom.txt
resource/ru/removed.txt
resource/ru/removed_custom.txt
resource/ru/tags_russian.txt
resource/ru/tagset.txt
```

Pinned `UPSTREAM.json` is the hash/provenance source of truth. At Task 0004 start it records, among other files:

```text
russian.dict       size 2322253  sha256 387f9fcf652a574c9d361397c30aa87ef6f7397a76d3d51cd04c94e8dcbc4015
added.txt          size   92745  sha256 4748f15da5cf97095e4d96dda3a3431028c660ff2456c30f143162616d0d8b40
added_custom.txt   size     260  sha256 30c7602fe9a69730e194dbe5f5b332fba6adf00f49af85d8c5358055c17d339b
removed.txt        size    3205  sha256 193c3174a137a5343b1dd7ad5a0314716c3e4023f75f57e161d6f99e2c7baff5
removed_custom.txt size     223  sha256 b840a31465a40eaf6401e4262db9d9980cd81246e7ef23357cbc54bb6e8da31c
```

If repository state differs, derive the values from the current pinned `UPSTREAM.json`; do not silently update the upstream pin.

---

## Mandatory project constraints

Read and obey:

```text
AGENTS.md
docs/Handoff_pylat_ru.md
reports/0002_dictionary_formats_lt_russian_tagset.md
reports/0003_russian_sentence_word_tokenization_offsets.md
compat/compatibility.json
compat/oracle_manifest.json
```

In particular:

- production Python must not launch Java/JRE or LanguageTool Server;
- Java is allowed only as a development/test oracle;
- no Natasha, pymorphy, spaCy morphology, Mystem, Stanza, neural tagger, or other semantic replacement;
- use the pinned LT Russian dictionary and manual overlay files as source of truth;
- preserve exact LT POS tag strings, including trailing/empty colon components such as `VB:INF:`;
- do not silently deduplicate readings;
- do not silently normalize Unicode beyond transformations explicitly performed by pinned `RussianTagger`;
- malformed manual-tagger resources must fail explicitly;
- dictionary/manual resources must be loaded once per long-lived tagger, not per token;
- exact compatibility is more important than improving morphology.

---

# Scope boundary

## In scope

- Python-native equivalent of Russian `RussianTagger` behavior;
- relevant `BaseTagger` behavior used by Russian;
- native `MorfologikTagger` wrapper over Task 0002 dictionary lookup;
- `ManualTagger` parsing semantics needed by pinned Russian `added*.txt` / `removed*.txt`;
- `CombiningTagger` merge/removal semantics;
- exact case fallback behavior used by `BaseTagger`;
- exact Russian acute/grave accent handling and modifier-apostrophe replacement;
- exact `MayMissingYO` detection and chunk tag;
- unknown-token fallback `(surface, null, null)`;
- minimal immutable Python morphology objects equivalent in observable fields to `AnalyzedToken` / `AnalyzedTokenReadings`;
- raw tagger start-position behavior where meaningful;
- development-only Java oracle generation for tagger fixtures;
- deterministic tagger/resource inventory;
- installed-package resource availability for runtime tagging;
- compatibility matrix update.

## Explicitly out of scope

Do not implement yet:

- `RussianHybridDisambiguator` / `disambiguation.xml`;
- generic chunker or `RussianChunker`;
- `RussianSynthesizer`;
- sentence-start pseudo-token insertion (`SENT_START`) as a full pipeline stage;
- whitespace/null-token reinsertion for a complete `AnalyzedSentence` pipeline;
- XML grammar matching;
- spelling rules, including `MorfologikRussianSpellerRule` and YO spelling rule;
- compounds/replacements/coherency/repetition rules;
- public `LanguageToolRU.check()` behavior;
- speculative multilingual tagger framework.

Task 0004 may add small reusable primitives where they are direct translations of LT tagging semantics, but must not start Task 0005.

---

# Upstream behavior that must be reproduced

## 1. RussianTagger normalization is literal, not generic Unicode normalization

Pinned `RussianTagger.tag()` mutates each input word before dictionary analysis.

For tokens whose Java `String.length() > 1`, it performs literal replacements equivalent to:

```text
о́ → о
а́ → а
е́ → е
у́ → у
и́ → и
ы́ → ы
э́ → э
ю́ → ю
я́ → я

о̀ → о
а̀ → а
ѐ → е
у̀ → у
ѝ  → и
ы̀ → ы
э̀ → э
ю̀ → ю
я̀ → я

ʼ → ъ
```

Important:

- do **not** replace this with NFC/NFD normalization or generic diacritic stripping;
- preserve exact upstream omissions/quirks;
- the surface stored in resulting `AnalyzedToken` readings is the **normalized word passed to `getAnalyzedTokens()`**, matching Java behavior;
- oracle-test accented words and modifier-apostrophe cases explicitly.

## 2. `MayMissingYO` semantics

Before the literal normalization above, pinned Russian code sets a candidate flag only when all relevant conditions hold:

- token length > 1;
- token contains neither `ё` nor `Ё`;
- token contains `е` or `Е`;
- token does not contain any of the explicitly checked acute-accented vowel sequences used by upstream.

After normalization and normal tagging it computes conceptually:

```text
wordLc = normalized_word.toLowerCase(ru).replace("е", "ё")
```

and asks the **combined word tagger** whether `wordLc` has at least one reading.

Important:

- upstream replaces **all** lowercase `е` characters with `ё` in one variant; it does not enumerate combinations;
- lookup includes manual additions/removals as part of the same combined word tagger;
- if the all-`е`→`ё` variant has no reading, clear the candidate flag;
- if it has a reading, add exactly one chunk tag named:

```text
MayMissingYO
```

- this marker belongs to the `AnalyzedTokenReadings` object, not to each morphology reading;
- do not infer `MayMissingYO` from spelling logic or heuristics.

## 3. BaseTagger case fallback order

Port the exact Russian-relevant `BaseTagger.getAnalyzedTokens()` behavior.

For normalized `word`:

```text
lowerWord = word.toLowerCase(Locale("ru"))
isLowercase = (word == lowerWord)
isMixedCase = StringTools.isMixedCase(word)
```

Then preserve this lookup/order behavior:

1. exact-case combined-tagger readings for `word`;
2. if the token is not lowercase and is not mixed-case, append readings for `lowerWord`;
3. if `tagLowercaseWithUppercase == true` (Russian uses the default `true`), exact/lower readings are both empty, and the input is lowercase, lookup `StringTools.uppercaseFirstChar(word)` and append those readings;
4. Russian has no `additionalTags()` override, so no language-dependent fallback is added here;
5. if still empty, return one unknown reading:

```text
AnalyzedToken(token=word, lemma=None, pos_tag=None)
```

Important:

- preserve order and duplicates;
- do not merge readings into a set;
- do not casefold; use behavior equivalent to Java lowercasing and `StringTools.isMixedCase` / `uppercaseFirstChar` for the relevant input surface;
- `uppercaseFirstChar` searches for the first alphabetic character rather than blindly uppercasing byte/character zero; port the relevant `StringTools` behavior instead of Python `word.capitalize()`;
- add regression cases for lowercase, initial-capitalized, ALL CAPS, mixedCase, unknown words, and lowercase words whose only reading exists under initial uppercase.

## 4. ManualTagger parsing

Pinned `BaseTagger` loads Russian manual additions/removals using `ManualTagger`.

Required source order:

```text
additions:
  ru/added.txt
  ru/added_custom.txt

removals:
  ru/removed.txt
  ru/removed_custom.txt
```

The current custom files may contain comments only, but they remain part of the compatibility surface and must not be hardcoded away.

Port the relevant parsing semantics:

- UTF-8 input;
- default separator is tab;
- trim the whole line first;
- support `#separatorRegExp=...` if encountered because it is part of the parser contract used by these resources;
- skip empty lines and lines beginning with `#`;
- reject an actual NBSP in a data line as upstream does;
- remove inline content beginning with `#`, then trim;
- require exactly three fields:

```text
fullform<TAB>baseform<TAB>postag
```

- trim the POS tag exactly as upstream does;
- retain repeated readings and source order for each form;
- malformed data must raise a project-specific resource/format error with path/line context.

Do not parse `added.txt` as a generic CSV and hope for the best.

## 5. CombiningTagger ordering/removal semantics

Pinned Russian uses `overwriteWithManualTagger() == false`.

Therefore a word lookup must behave as:

```text
result = manual_additions(word)
result += morfologik_dictionary(word)
result -= every exact reading present in removal_tagger(word)
```

The removal comparison is exact `(lemma, pos_tag)` equality equivalent to `TaggedWord.equals()` semantics.

Requirements:

- manual readings come before binary readings;
- binary readings keep Task 0002 Morfologik order;
- removal entries can remove readings originating from either source;
- removal means remove all matching entries as Java `List.removeAll()` would;
- no automatic deduplication after merging;
- test at least one real `added.txt`-only/overlay reading and at least one real `removed.txt` reading against the Java oracle.

## 6. Dictionary frequency behavior

Pinned `MorfologikTagger` strips the last byte from a POS tag only when dictionary metadata says frequency data is included.

Task 0002 established that pinned `russian.info` has no frequency bytes (`frequency-included=false`). Preserve the generic branch in a sensible layer if already supported, but do not fabricate/strip bytes from Russian tags.

---

# Deliverables

## 1. Deterministic Russian tagger compatibility inventory

Create a machine-readable inventory, for example:

```text
compat/russian_tagger_inventory.json
```

It must be deterministically generated from pinned sources/resources and include at minimum:

```text
LT tag/commit
Morfologik version
RussianTagger.java source hash/path
russian.dict path/hash/size
russian.info path/hash
added.txt path/hash + parsed data-line count + distinct forms + reading count
added_custom.txt path/hash + counts
removed.txt path/hash + counts
removed_custom.txt path/hash + counts
manual parser separator semantics
manual merge order
case-fallback policy
normalization replacement table
MayMissingYO conditions
unknown-token behavior
runtime resource strategy
unsupported/known differences
```

The test suite must regenerate the complete inventory and compare its deterministic serialized contents with the committed artifact, not just check summary counters.

## 2. Runtime resource strategy suitable for an installed package

A production `RussianTagger` must not depend on finding `third_party/languagetool/...` by walking a Git checkout.

Implement a package-safe resource strategy now.

### Preferred

Package byte-identical pinned runtime assets under a package resource location such as:

```text
src/pylat_ru/resources/ru/
  russian.dict
  russian.info
  added.txt
  added_custom.txt
  removed.txt
  removed_custom.txt
```

with a deterministic sync/verification tool that proves each packaged asset is byte-identical to its pinned upstream source/hash.

### Acceptable alternative

Use a deterministic generated runtime representation for manual overlays and a package-data/build strategy for the binary dictionary, provided:

- normal installed-package tagging does not require the Git repository layout;
- provenance/hash binding remains exact;
- no network download is required;
- wheel/sdist smoke tests can find the resources;
- generated assets are completely reproducible from pinned sources.

Do not commit an opaque re-encoded morphology database unless its generation is deterministic and parity-proven.

Update `pyproject.toml` package-data rules as necessary.

Add an isolated install smoke test/proof (temporary venv or equivalent) showing that an installed `pylat_ru` can instantiate and use `RussianTagger` without accessing `third_party/`.

Task 0015 will do final packaging hardening, but Task 0004 must not knowingly create a tagger that works only from the repository root.

## 3. Minimal morphology data model

Implement immutable Python types representing the observable fields required by downstream LT-compatible stages.

Conceptually:

```python
@dataclass(frozen=True)
class AnalyzedToken:
    token: str
    lemma: str | None
    pos_tag: str | None

@dataclass(frozen=True)
class AnalyzedTokenReadings:
    readings: tuple[AnalyzedToken, ...]
    start_pos: int
    utf16_start_pos: int
    chunk_tags: tuple[str, ...] = ()
```

Exact names/module layout may improve.

Requirements:

- preserve raw LT POS tag strings unchanged;
- preserve multiple readings and duplicates;
- preserve reading order;
- expose enough structure for Task 0005 disambiguation without changing the public data model again;
- unknown reading is representable explicitly with `lemma=None` and `pos_tag=None`;
- chunk tags are immutable/deterministic;
- do not prematurely add grammar-rule or synthesizer fields.

### Position semantics

Be explicit. Java `RussianTagger.tag(List<String>)` initializes `pos=0`, constructs each `AnalyzedTokenReadings` at that position, then increments by the **normalized word's Java UTF-16 length**.

For raw direct-tagger parity, preserve this observable behavior as a dedicated LT-compatible position field.

Do not confuse it with Task 0003 source offsets. If a span-aware helper is added, keep source code-point/UTF-16 offsets separately and never overwrite the raw LT tagger semantics silently.

Because accent stripping can shorten the normalized token, add a regression case proving the distinction.

## 4. Native manual/combined word taggers

Implement internal components equivalent to the Russian-relevant behavior of:

```text
MorfologikTagger
ManualTagger
CombiningTagger
```

Suggested internal API:

```python
@dataclass(frozen=True)
class TaggedWord:
    lemma: str | None
    pos_tag: str | None

class WordTagger:
    def tag(self, word: str) -> tuple[TaggedWord, ...]: ...
```

Names may differ.

Requirements:

- `MorfologikTagger` delegates to Task 0002 `MorfologikDictionary.lookup()`;
- manual files are parsed once during tagger construction/resource initialization;
- no dictionary reopening per token;
- combined order matches upstream exactly;
- removals match exact lemma/tag pairs;
- source resource failures are explicit;
- no mutation of global process locale.

## 5. Native `RussianTagger`

Implement a production class conceptually resembling:

```python
class RussianTagger:
    def tag(self, sentence_tokens: Sequence[str]) -> tuple[AnalyzedTokenReadings, ...]: ...
    def tag_word(self, word: str) -> AnalyzedTokenReadings: ...  # optional convenience
```

Requirements:

- default resources are pinned Russian package resources;
- injectable resource paths may be supported for tests, but defaults must be package-safe;
- exact normalization/replacement order from `RussianTagger.java`;
- exact BaseTagger case fallback;
- exact combined manual/dictionary/removal behavior;
- exact unknown reading behavior;
- exact `MayMissingYO` behavior;
- deterministic reading/chunk-tag ordering;
- no Java, subprocess, server, HTTP, or network runtime dependency.

## 6. Port upstream `RussianTaggerTest` semantics

Port all observable cases from pinned `RussianTaggerTest.java`.

At minimum the upstream examples include:

```text
Все счастливые семьи похожи друг на друга, каждая несчастливая семья несчастлива по-своему.
Все смешалось в доме Облонских.
Абдуллаевы
блукать
```

and verify readings corresponding to examples such as:

```text
Все → весь / все readings
семьи → 3 readings
смешалось → смешаться + VB:Past:INTR:PFV:Neut
Облонских → unknown reading
Абдуллаевы → абдуллаев + NN:Fam:PL:Nom
блукать → VB:INF:   # trailing colon must survive
```

Note that upstream `TestTools.myAssert()` sorts display strings only for the JUnit assertion because lexicon order can vary across versions. For this project the upstream revision is pinned, so additionally capture **raw Java reading order** in differential fixtures and compare it exactly where the official pinned oracle exposes it deterministically.

Do not weaken raw-order tests into sets just because the human-readable upstream assertion sorts output.

## 7. Add Java tagger oracle fixture generation

Extend the development-only, hash-verified Java oracle boundary from Task 0003.

Add deterministic fixture generation, for example:

```text
python tools/differential_lt.py --generate-tagger-fixtures
```

The generator must use the already fail-closed verified LT `6.8` oracle from `compat/oracle_manifest.json`.

Create a fixture such as:

```text
tests/fixtures/oracle_russian_tagger.json
```

For each token sequence capture at minimum:

```json
{
  "input_tokens": ["..."],
  "tokens": [
    {
      "start_pos_utf16": 0,
      "readings": [
        {"token": "...", "lemma": "...", "pos_tag": "..."}
      ],
      "chunk_tags": ["MayMissingYO"]
    }
  ]
}
```

Fixture metadata must bind:

```text
LT v6.8
pinned commit
verified oracle JAR SHA-256
RussianTagger source/hash if practical
resource hashes
fixture generator schema/version
```

Fixture expected output must come from Java, never from the Python implementation.

Add oracle cases for:

- all upstream RussianTaggerTest examples;
- exact lowercase word;
- initial uppercase fallback;
- ALL CAPS fallback;
- mixed-case word;
- unknown token;
- punctuation/digit-containing direct tokens where relevant to BaseTagger semantics;
- manual addition lookup;
- manual removal effect;
- acute accent normalization;
- grave accent normalization;
- `ʼ → ъ` normalization;
- word containing `ё` (must not receive `MayMissingYO` from this path);
- word with `е` whose all-`е`→`ё` variant exists;
- word with `е` whose YO variant does not exist;
- multiple `е` characters, proving all-at-once replacement behavior;
- at least one normalized token whose raw direct-tagger position differs from original source-token length;
- ambiguous dictionary word preserving multiple readings;
- `VB:INF:` trailing empty feature.

## 8. Manual overlay parity proofs

Add focused tests that prove the complete overlay pipeline, not merely the parser.

The suite must identify real pinned examples by inspecting the resources, then prove against Java:

1. a word/readings contributed by `added.txt`;
2. a binary reading removed by `removed.txt`;
3. a word with both manual and binary readings if such an example exists;
4. an exact `(lemma, pos_tag)` removal leaving other readings intact;
5. custom-file handling even if current custom files contain only comments;
6. no accidental deduplication.

If no real pinned example exists for one requested merge shape, use a synthetic isolated `ManualTagger`/`CombiningTagger` regression fixture for that shape and state that fact explicitly in the report.

## 9. Case fallback parity proofs

Do not assume Python string methods are automatically Java `StringTools` parity.

Port/test the relevant logic from pinned `StringTools` for:

```text
isAllUppercase
isCapitalizedWord
isNotAllLowercase
isMixedCase
uppercaseFirstChar/changeFirstCharCase
```

Only the subset required by `BaseTagger` is needed.

Add synthetic unit tests and Java oracle cases around:

```text
слово
Слово
СЛОВО
mixedCase / MixedCase-style tokens
leading quote/parenthesis before the first letter
ASCII Latin mixed with Russian where representable/relevant
```

Document any Java UTF-16/code-point caveat explicitly rather than hiding it.

## 10. Resource/license/provenance checks

Task 0001 already licensed/vendored these upstream Russian assets. Task 0004 must preserve that chain when introducing package-runtime copies/generated artifacts.

Requirements:

- package copies/generated resources reference original pinned source path/hash;
- byte-identical copies are verified automatically;
- generated artifacts state derivation inputs;
- no new external morphology dependency;
- any new Python dependency requires explicit license/provenance review;
- do not commit the Java oracle distribution/JAR.

## 11. Performance sanity

Parity first, but the architecture must avoid obvious pathological behavior.

At minimum measure/report:

- `RussianTagger` initialization time;
- memory implication of loading 2.3 MB `russian.dict` plus manual overlays;
- throughput for a representative batch of at least 10,000 token lookups;
- repeated tagging using one long-lived tagger instance.

Do not optimize by dropping manual overlays, caching only one reading, or changing fallback semantics.

A reasonable target is that dictionary/manual resources are loaded once and per-token tagging is on the order of existing Task 0002 lookup cost plus small overlay/case logic.

---

# Suggested implementation layout

One reasonable layout is:

```text
src/pylat_ru/
  analysis.py                 # AnalyzedToken / AnalyzedTokenReadings / ChunkTag-like types
  tagging/
    __init__.py
    errors.py
    word_tagger.py            # TaggedWord + Morfologik/Manual/Combining components
    russian.py                # RussianTagger
    string_tools.py           # only exact BaseTagger-required StringTools subset
  resources/
    ru/
      russian.dict
      russian.info
      added.txt
      added_custom.txt
      removed.txt
      removed_custom.txt
```

Exact filenames may differ if a cleaner design emerges. Keep Russian-specific behavior obvious and keep generic abstractions narrow.

---

# Error handling requirements

Add explicit project errors for tagger/resource failures. Examples:

```text
TaggerError
TaggerResourceError
ManualTaggerFormatError
TaggerCompatibilityError
```

Exact names may differ.

Fail explicitly on:

- missing default runtime dictionary/info;
- hash/provenance mismatch when validating synced runtime resources;
- malformed manual resource line;
- invalid manual separator directive;
- actual NBSP in a manual data line, matching upstream rejection;
- unsupported parser behavior encountered in pinned resources;
- impossible/invalid internal reading data.

Do not convert resource corruption into "unknown word".

Unknown **input words** are normal and must produce the LT null reading; broken **resources** are errors.

---

# Tests

Create/extend focused tests under appropriate locations, for example:

```text
tests/unit/test_manual_tagger.py
tests/unit/test_combining_tagger.py
tests/unit/test_russian_tagger_case.py
tests/unit/test_russian_tagger_normalization.py
tests/unit/test_russian_tagger_resources.py
tests/upstream/test_russian_tagger_parity.py
tests/fixtures/oracle_russian_tagger.json
```

The exact split may improve.

Mandatory test categories:

1. manual parser comments/inline comments/three-field format/order;
2. manual parser malformed line/NBSP errors;
3. combining order: manual first, binary second;
4. removals exact pair semantics;
5. dictionary reading order preserved;
6. unknown reading `(token, None, None)`;
7. BaseTagger lowercase/capitalized/all-uppercase/mixed-case behavior;
8. `uppercaseFirstChar` punctuation-leading case;
9. all literal accent replacements;
10. modifier apostrophe `ʼ → ъ`;
11. `MayMissingYO` positive/negative/multiple-`е` cases;
12. chunk tag attached at readings level;
13. upstream RussianTaggerTest examples;
14. raw UTF-16 direct-tagger start positions;
15. deterministic oracle fixture metadata;
16. deterministic complete tagger inventory regeneration;
17. package-runtime resource hash parity;
18. isolated installed-package smoke tagging;
19. Java oracle absent → normal production tests/import still work;
20. complete previous Task 0001–0003 suite remains green.

---

# Compatibility matrix update

On successful completion update `compat/compatibility.json` honestly.

Expected direction:

```json
{
  "pipeline_components": {
    "RussianSentenceTokenizer": "SUPPORTED",
    "RussianWordTokenizer": "SUPPORTED",
    "RussianTagger": "SUPPORTED",
    "RussianDisambiguator": "NOT_YET_IMPLEMENTED",
    "RussianChunker": "NOT_YET_IMPLEMENTED",
    "RussianSynthesizer": "NOT_YET_IMPLEMENTED",
    "XMLRuleEngine": "NOT_YET_IMPLEMENTED"
  }
}
```

Add explicit tagger sub-status fields if useful, for example:

```text
MorfologikTagger lookup
ManualTagger additions
ManualTagger removals
CombiningTagger
BaseTagger case fallback
Russian accent normalization
MayMissingYO
unknown-token fallback
runtime resource packaging
Java tagger oracle parity
```

Do not mark disambiguation or chunking as implemented merely because `MayMissingYO` uses a `ChunkTag` container.

---

# Completion report

Create:

```text
reports/0004_russian_tagger.md
```

Include at minimum:

- exact upstream references/pin;
- implemented architecture;
- manual overlay counts and source hashes;
- runtime resource strategy and hash proof;
- case fallback behavior;
- accent/apostrophe normalization behavior;
- `MayMissingYO` semantics;
- upstream/oracle parity cases;
- reading-order results;
- package-install smoke proof;
- performance sanity measurements;
- full test command(s) and exact pass/fail counts;
- known differences, if any;
- anything deliberately deferred to Task 0005.

If any parity case fails or any pinned resource behavior remains unsupported, do not report the component as fully `SUPPORTED`.

---

# Acceptance criteria

Task 0004 is complete only when all of the following are true:

1. Production `RussianTagger` is Python-native and does not invoke Java/server/network.
2. Pinned `russian.dict` is used through the native Task 0002 Morfologik reader.
3. `added.txt` and `added_custom.txt` are loaded with pinned ManualTagger-compatible semantics.
4. `removed.txt` and `removed_custom.txt` are loaded and applied.
5. Combined reading order is manual additions first, then binary dictionary, followed by exact removals.
6. No readings are silently deduplicated.
7. BaseTagger exact/lowercase/uppercase-first fallback behavior is implemented for Russian.
8. Relevant `StringTools.isMixedCase`/`uppercaseFirstChar` semantics are parity-tested.
9. Unknown words produce exactly one null morphology reading.
10. All RussianTagger literal acute accent replacements are implemented exactly.
11. All RussianTagger literal grave accent replacements are implemented exactly, including upstream's `ѝ` handling.
12. `ʼ → ъ` behavior is implemented exactly.
13. `MayMissingYO` candidate conditions match upstream.
14. `MayMissingYO` uses combined-tagger lookup of the all-`е`→`ё` lowercase variant.
15. `MayMissingYO` is emitted as a readings-level chunk tag named exactly `MayMissingYO`.
16. Raw direct-tagger start positions reproduce Java UTF-16 accumulation over normalized words.
17. Source-offset fields, if exposed, remain distinct from raw tagger positions.
18. Minimal analyzed-token/readings objects preserve token, lemma, raw POS tag, reading order and chunk tags.
19. All pinned upstream `RussianTaggerTest` examples are ported.
20. Raw Java oracle tagger fixtures are generated using the fail-closed LT v6.8 oracle.
21. Oracle fixture metadata contains the verified oracle JAR SHA-256 and upstream pin.
22. Manual-addition behavior is proven against a real pinned resource example.
23. Manual-removal behavior is proven against a real pinned resource example.
24. Ambiguous words preserve all expected readings.
25. `VB:INF:` and other tags with empty components remain byte/string exact.
26. Runtime tagger resources are package-safe and do not require repository-relative `third_party/` lookup.
27. Packaged/synced runtime resources are deterministically hash-verified against pinned upstream.
28. An isolated installed-package smoke test can tag Russian text without Java and without repository-relative resource lookup.
29. `compat/russian_tagger_inventory.json` is generated deterministically and complete regeneration is tested byte-for-byte.
30. Malformed manual resources fail explicitly with path/line context.
31. Broken/missing dictionary resources fail explicitly rather than becoming unknown words.
32. No new semantic NLP replacement dependency is introduced.
33. Performance sanity proves resources are not reloaded per token.
34. `compat/compatibility.json` marks `RussianTagger` supported only if all required parity behavior passes.
35. The entire Task 0001 + 0002 + 0003 + 0004 focused/full pytest suite passes.
36. Completion report is written and honest about any remaining differences.
37. Diff/status is reviewed for accidental files, caches, oracle JARs or unrelated changes.
38. Task 0004 result is committed intentionally.
39. The committed current branch is pushed to `origin` immediately.
40. The remote commit is verified visible.
41. Task 0005 is **not** started automatically.

---

# Expected final state after Task 0004

The project pipeline should have a trustworthy native morphology stage:

```text
raw text
  ↓
RussianSentenceTokenizer                 ✅
  ↓
RussianWordTokenizer                     ✅
  ↓
RussianTagger                            ✅
  ├─ russian.dict                        ✅
  ├─ added*.txt                          ✅
  ├─ removed*.txt                        ✅
  ├─ BaseTagger case fallback            ✅
  ├─ accent/apostrophe normalization     ✅
  └─ MayMissingYO                        ✅
  ↓
RussianDisambiguator                     ⛔ Task 0005
  ↓
RussianChunker                           ⛔ later
  ↓
RussianSynthesizer                       ⛔ Task 0006
  ↓
RussianRuleEngine                        ⛔ later
```

The key result is not merely that `книга` receives a noun tag. The result must be that downstream LanguageTool Russian rules see the **same morphology surface** they would have seen from the pinned Java `RussianTagger`, including overlays, removals, case fallback, unknowns, accents, `ё` behavior, tag strings, multiplicity, and ordering.
