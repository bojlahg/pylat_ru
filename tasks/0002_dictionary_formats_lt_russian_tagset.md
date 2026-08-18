# Task 0002 — Native Morfologik Dictionary Reader + LT Russian Tagset

## Status

READY

## Goal

Implement the Python-native foundation required to read and understand the pinned Russian LanguageTool morphological and synthesis dictionaries **without Java and without replacing LanguageTool semantics with another NLP library**.

Task 0002 must establish, with tests and machine-readable evidence:

- the exact Morfologik binary FSA format(s) used by the pinned `russian.dict` and `russian_synth.dict`;
- a native Python reader/traversal implementation for those actual format(s);
- parsing of the accompanying `.info` metadata;
- correct `SUFFIX` sequence decoding and KOI8-R handling used by the pinned Russian dictionaries;
- low-level lookup returning the same lemma/tag or synthesized-form data as the pinned LanguageTool/Morfologik stack;
- an exact inventory and lossless representation of the Russian LT POS/tag vocabulary from `tags_russian.txt` and `tagset.txt`;
- explicit failure for unsupported/corrupt formats instead of silent fallback.

This task is deliberately below the full Russian tagger and synthesizer layers. It provides the dictionary and tagset primitives they will depend on.

## Pinned compatibility references

The LanguageTool compatibility target remains the exact Task 0001 pin:

```text
LanguageTool tag:    v6.8
LanguageTool commit: e807fcde6a6506191e1470744d2345da28c26be6
```

Do not change this pin in Task 0002.

Relevant vendored Russian assets include:

```text
third_party/languagetool/languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/
  russian.dict
  russian.info
  russian_synth.dict
  russian_synth.info
  tags_russian.txt
  tagset.txt
```

Relevant vendored Russian implementation/tests include:

```text
.../src/main/java/org/languagetool/tagging/ru/RussianTagger.java
.../src/main/java/org/languagetool/synthesis/ru/RussianSynthesizer.java
.../src/test/java/org/languagetool/tagging/ru/RussianTaggerTest.java
.../src/test/java/org/languagetool/synthesis/ru/RussianSynthesizerTest.java
```

Relevant pinned LanguageTool core behavior to inspect/reference includes at minimum:

```text
languagetool-core/.../tagging/BaseTagger.java
languagetool-core/.../tagging/MorfologikTagger.java
languagetool-core/.../synthesis/BaseSynthesizer.java
```

LanguageTool v6.8 declares Morfologik version `2.1.9`. Use the **2.1.9 behavior/source** as the reference for the Morfologik structures actually needed here. Do not silently target current Morfologik `master` if it differs.

The pinned Russian metadata currently declares for both morphological and synthesis dictionaries:

```text
fsa.dict.separator=+
fsa.dict.encoding=koi8-r
fsa.dict.encoder=SUFFIX
```

These facts must be verified from the vendored files by tests/tooling rather than merely hard-coded as assumptions.

## Mandatory architectural constraints

Read and obey:

```text
AGENTS.md
docs/Handoff_pylat_ru.md
reports/0001_project_foundation_upstream_inventory.md
```

In particular:

- production Python must not invoke Java/JRE or LanguageTool Server;
- Java/Morfologik tools may be used only as an optional development/test oracle;
- do not use Natasha, pymorphy, pymorphy2/3, spaCy, NLTK morphology, or another semantic replacement;
- do not convert the entire Russian dictionary into millions of heavyweight Python objects at import/startup;
- preserve upstream observable behavior and result ordering unless evidence proves ordering irrelevant;
- unknown binary format/version, unsupported metadata, corrupt FSA data, or undecodable content must fail explicitly;
- all persisted paths must remain portable POSIX `/` paths;
- no network downloads during `import pylat_ru`, dictionary load, or lookup.

## Scope boundary

### In scope

- `.info` metadata parsing;
- detection and reading of the **actual FSA binary format(s)** used by pinned `russian.dict` and `russian_synth.dict`;
- FSA traversal required for exact lookup;
- decoding the dictionary's Morfologik sequence encoding used by the pinned Russian files (`SUFFIX`);
- dictionary charset handling (`koi8-r` for the pinned Russian files);
- low-level morphological dictionary lookup;
- low-level synthesis dictionary lookup;
- lossless LT Russian POS-tag representation;
- machine-readable tagset inventory;
- parity fixtures/probes against pinned upstream behavior;
- focused performance/memory sanity checks.

### Explicitly out of scope

Do **not** implement Task 0003/0004/0006 behavior prematurely.

Specifically, do not implement yet:

- Russian sentence tokenization;
- Russian word tokenization;
- full `RussianTagger.tag()`;
- `BaseTagger` case fallback behavior;
- accent normalization from `RussianTagger.java`;
- `ё` / `MayMissingYO` behavior;
- manual additions/removals (`added.txt`, `added_custom.txt`, `removed.txt`, `removed_custom.txt`) as a tagger overlay;
- creation of final `AnalyzedToken` / `AnalyzedTokenReadings` pipeline objects;
- disambiguation;
- chunking;
- full `RussianSynthesizer.synthesize()`;
- regex synthesis over all possible tags;
- manual synthesis additions/removals;
- grammar rules or spelling rules.

A raw synthesis-dictionary probe such as:

```text
lookup("семья|NN:Inanim:Fem:Sin:R") -> "семьи"
```

is in scope because it proves dictionary-format correctness. Building the public synthesizer layer around it is Task 0006.

---

## Deliverables

## 1. Record exact Morfologik compatibility surface

Before writing the binary reader, inspect the actual pinned dictionaries and the Morfologik 2.1.9 implementation used by LanguageTool v6.8.

Determine and document at minimum:

- binary header/magic;
- actual FSA implementation/version used by `russian.dict`;
- actual FSA implementation/version used by `russian_synth.dict`;
- arc/node encoding required to traverse them;
- root-node discovery;
- final-arc/final-state semantics;
- label representation;
- how byte sequences are enumerated after the matched input prefix;
- dictionary separator handling;
- metadata charset handling;
- sequence encoder behavior;
- whether frequency bytes are present in either dictionary;
- any input/output conversion metadata actually present;
- whether both Russian dictionaries use the same FSA variant.

Create a concise technical document, for example:

```text
docs/morfologik_dictionary_format.md
```

The document must clearly distinguish:

1. facts observed in the pinned Russian files;
2. behavior required from Morfologik 2.1.9;
3. format features not needed by this pin and therefore intentionally unsupported.

Do not claim support for every Morfologik format just because the upstream Java library supports it.

If the two pinned dictionaries use only one FSA variant, implementing exactly that variant is acceptable and preferable to speculative support for unused variants.

Unsupported variants must raise an explicit compatibility error.

## 2. `.info` metadata parser

Implement a small native parser for Morfologik dictionary metadata, under a sensible internal package such as:

```text
src/pylat_ru/morfologik/
  metadata.py
```

Exact layout may improve if justified.

The parser must:

- parse comments, blank lines and `key=value` properties correctly;
- preserve raw property values where compatibility-sensitive;
- expose typed/validated values needed by the reader;
- support the metadata actually used by the pinned Russian files;
- reject missing required compatibility-critical fields;
- reject invalid separator definitions;
- reject unsupported encodings/encoder modes explicitly;
- retain unknown properties in a visible structure or reject them explicitly, but never silently discard them as if understood.

At minimum prove that both pinned metadata files resolve to:

```text
separator: +
encoding:  koi8-r
encoder:   SUFFIX
```

Do not hard-code these values in the lookup implementation instead of parsing the files.

## 3. Native FSA reader/traversal

Implement a Python-native binary FSA reader for the exact format(s) discovered in section 1.

Suggested internal shape:

```text
src/pylat_ru/morfologik/
  errors.py
  fsa.py
  metadata.py
  sequence_encoder.py
  dictionary.py
```

Names are not mandatory; responsibilities are.

Requirements:

- no Java/JNI/subprocess bridge;
- no pre-expansion of the entire dictionary into a Python `dict`/list of all entries;
- compact immutable binary representation or equivalent low-overhead structure;
- exact root traversal by encoded input bytes;
- ability to follow the separator arc after an exact input match;
- enumerate all final suffix sequences for that input;
- preserve deterministic/on-disk traversal order;
- bounds checking on offsets and arc/node references;
- corrupt/truncated files must raise an explicit format/corruption error, not `IndexError`, infinite loop, empty lookup, or undefined behavior;
- unsupported FSA version/header must raise `UnsupportedFSAFormatError` or equivalent explicit project exception.

The implementation must not rely on machine endianness or Windows-only behavior.

## 4. Morfologik sequence decoding

Implement the sequence decoding required by the pinned Russian dictionaries.

For the pinned metadata this means `SUFFIX` decoding.

The implementation must reproduce the relevant Morfologik 2.1.9 semantics for:

```text
input word bytes
+ encoded transformation bytes
→ decoded stem/output bytes
```

Then decode text with the metadata-specified charset.

Requirements:

- exact byte-level behavior;
- correct handling of empty/no-op transformation where present;
- no Unicode-first approximation that loses KOI8-R byte semantics;
- malformed transformation sequences fail explicitly;
- tests must include synthetic tiny examples in addition to the real Russian dictionary.

Do not implement PREFIX/INFIX/NONE encoders unless the pinned Russian files actually require them. If not implemented, parsing metadata that requests them must fail clearly as unsupported.

## 5. Low-level dictionary API

Provide an internal reusable lookup abstraction suitable for later tagger and synthesizer tasks.

Conceptually:

```python
@dataclass(frozen=True)
class DictionaryEntry:
    stem: str | None
    tag: str | None

class MorfologikDictionary:
    @classmethod
    def open(cls, dict_path: Path, info_path: Path | None = None) -> "MorfologikDictionary": ...

    def lookup(self, key: str) -> tuple[DictionaryEntry, ...]: ...
```

Exact names are flexible.

Required semantics:

- dictionary metadata is loaded once per dictionary instance;
- dictionary bytes/FSA are loaded or mapped once per instance;
- repeated lookups do not reparse metadata/FSA;
- lookup is exact and deterministic;
- missing key returns an empty result collection at this low level;
- result ordering follows upstream/Morfologik traversal behavior;
- stem/tag strings are decoded exactly;
- if the metadata indicates frequency information, strip/preserve it in the same layer and manner required to later reproduce LanguageTool behavior, and document the choice;
- the API must be usable by both `russian.dict` and `russian_synth.dict`.

Do not expose this low-level type as the final public `pylat_ru` API yet unless there is a strong reason.

## 6. Prove morphological dictionary parity on real pinned data

Use the actual vendored `russian.dict` in focused tests.

At minimum cover:

- a word with several readings;
- a word with one reading;
- noun lemma/case variation;
- verb/infinitive;
- an unknown word;
- Cyrillic data that proves KOI8-R decoding;
- stable repeated lookup order.

Use pinned `RussianTaggerTest.java` as a source of expected linguistic readings, but test **low-level dictionary semantics**, not yet full `RussianTagger` case/accent/ё behavior.

Good candidate words from the pinned upstream test include lowercase forms corresponding to:

```text
все
счастливые
семьи
смешалось
дом
блукать
```

Do not blindly assert a guessed result set. Derive the exact low-level expected output from the pinned dictionary/Morfologik oracle and commit the fixed expected fixture.

For a bounded fixed sample, compare:

```text
input
ordered [(stem, tag), ...]
```

against Morfologik/LanguageTool v6.8 development-oracle output.

The committed test suite itself must run without Java.

## 7. Prove synthesis dictionary low-level compatibility

Open the actual pinned:

```text
russian_synth.dict
russian_synth.info
```

and prove that the same reader can perform raw synthesis-key lookup.

LanguageTool's `BaseSynthesizer` constructs synthesis lookup keys as:

```text
lemma + "|" + posTag
```

At minimum reproduce the pinned Russian upstream examples:

```text
семья|NN:Inanim:Fem:Sin:Nom -> семья
семья|NN:Inanim:Fem:Sin:R   -> семьи
```

and an unknown lookup returning no result.

This is a binary dictionary compatibility proof only. Do not implement the full synthesizer yet.

## 8. Lossless Russian LT tag representation

Implement a minimal tag representation that preserves LanguageTool's raw POS strings exactly.

A safe conceptual model is:

```python
@dataclass(frozen=True)
class RussianTag:
    raw: str
    parts: tuple[str, ...]

    @property
    def pos(self) -> str: ...
```

with helpers only where they are unambiguous.

Important rules:

- `raw` is authoritative;
- splitting by `:` must preserve empty components where they occur;
- do not reorder features;
- do not rewrite abbreviations into a new tag vocabulary;
- do not "correct" odd upstream spellings or legacy tags;
- do not force all tags into one rigid positional schema if the pinned LT tag vocabulary does not support that model;
- later grammar matching must be able to see the exact original LT tag string.

Examples showing why losslessness matters include forms such as:

```text
VB:INF:
DPT:Past:
NN:Inanim:Masc:Sin:Nom
ADJ:MPR:PL:V
```

A typed semantic view may be added for known atoms (`Masc`, `Fem`, `Sin`, `PL`, cases, person, tense, aspect, transitivity, etc.), but it must remain a view over the raw LT tag, not a replacement encoding.

## 9. Russian tagset inventory

Build deterministic tooling or library code that reads the pinned:

```text
tags_russian.txt
tagset.txt
```

and creates a machine-readable artifact, for example:

```text
compat/russian_tagset.json
```

Inventory at minimum:

- exact tag strings from `tags_russian.txt`;
- total raw lines and effective tag count;
- duplicates if any;
- blank/whitespace anomalies if any;
- tags containing empty components/trailing separators;
- coarse POS prefixes observed;
- feature atoms observed after splitting while preserving empties;
- descriptive feature vocabulary documented in `tagset.txt`;
- AOT→LT mappings present in `tagset.txt` where they can be parsed reliably;
- lines that cannot be parsed mechanically, marked explicitly rather than dropped.

Do not silently trim/correct compatibility-significant data. If trailing whitespace in the source is judged non-semantic, document and test that normalization decision explicitly.

Create a readable companion document, for example:

```text
docs/russian_tagset.md
```

that explains the LT Russian tag vocabulary in implementation terms without inventing a new morphology standard.

## 10. Cross-check dictionary tags against tag inventory

Where practical, add a deterministic validation/probe that enumerates dictionary data sufficiently to answer:

- which distinct tags actually occur in `russian.dict`;
- whether every actual binary-dictionary tag is represented in `tags_russian.txt` after the exact normalization rules chosen above;
- whether `tags_russian.txt` contains tags not observed in the binary morphological dictionary;
- whether any raw/odd tags need explicit compatibility treatment.

If full FSA enumeration is implemented, use it.

If full enumeration is not necessary for lookup architecture and would significantly inflate Task 0002, a bounded development tool may perform this validation, but the report must state the exact coverage and limitation. Do not claim full tagset parity from a small sample.

Persist deterministic counts/differences under `compat/` if useful.

## 11. Explicit compatibility errors

Introduce project-specific exceptions or equivalent explicit statuses for at least:

```text
unsupported FSA format/version
corrupt/truncated FSA
invalid dictionary metadata
unsupported dictionary encoder
unsupported dictionary charset
invalid separator
malformed encoded stem/output sequence
```

Do not collapse all failures into a generic `ValueError` with no context.

Error messages should include enough information to diagnose the file and unsupported feature.

## 12. Development oracle boundary

Task 0001 already established an optional Java oracle boundary. Extend it only as needed to generate fixed dictionary parity fixtures.

Acceptable development-only use:

```text
LanguageTool v6.8 / Morfologik 2.1.9
→ query a bounded word list
→ emit deterministic JSON [(input, stem, tag), ...]
→ compare Python reader
```

Requirements:

- Java/Morfologik is never imported/invoked by production library code;
- Java absence does not break Python tests that use committed fixtures;
- no network download during normal tests;
- oracle output must record the LT/Morfologik version/pin used;
- fixture generation is deterministic.

Do not make the Java oracle a hidden runtime dependency just because it is convenient.

## 13. Performance and memory sanity

This task is correctness-first, but the dictionary architecture must not make later use impossible.

Add a small deterministic benchmark/probe or report measurement for at least:

- opening `russian.dict`;
- first lookup;
- repeated lookups over a fixed small word set;
- approximate memory strategy/footprint.

Hard performance gates are not required yet, but flag obviously pathological behavior.

Specifically avoid an implementation that eagerly turns the full dictionary into millions of Python strings/objects at load time.

## 14. Compatibility matrix update

Update:

```text
compat/compatibility.json
```

Add/extend explicit statuses for Task 0002, for example:

```text
dictionary_metadata
morfologik_fsa_reader
sequence_decoder
tag_dictionary_low_level_lookup
synthesis_dictionary_low_level_lookup
russian_tagset_inventory
russian_tag_representation
```

Keep later layers honest:

```text
RussianTagger           NOT_YET_IMPLEMENTED
RussianDisambiguator    NOT_YET_IMPLEMENTED
RussianSynthesizer      NOT_YET_IMPLEMENTED
XML grammar engine      NOT_YET_IMPLEMENTED
```

Do not mark the tagger or synthesizer complete merely because their binary dictionaries can now be read.

## 15. Tests

Add focused pytest coverage under sensible paths such as:

```text
tests/unit/test_morfologik_metadata.py
tests/unit/test_morfologik_fsa.py
tests/unit/test_morfologik_dictionary.py
tests/unit/test_russian_tagset.py
tests/upstream/test_russian_dictionary_lookup.py
tests/upstream/test_russian_synth_dictionary_lookup.py
```

Exact file split is flexible.

Required coverage includes at minimum:

### Metadata

- parse pinned `russian.info`;
- parse pinned `russian_synth.info`;
- missing required key;
- invalid separator;
- unsupported encoder;
- unsupported encoding;
- unknown metadata property is visible/not silently lost.

### FSA/decoder

- actual pinned FSA header detected correctly;
- tiny synthetic FSA/decoder fixtures where practical;
- malformed/truncated binary rejected explicitly;
- unsupported FSA version rejected explicitly;
- SUFFIX decode normal case;
- SUFFIX decode boundary/no-op cases;
- malformed transform rejected.

### Morphological dictionary

- exact known lookup with multiple readings;
- exact known lookup with one reading;
- unknown word -> empty result;
- KOI8-R Cyrillic round-trip;
- deterministic result ordering;
- repeated lookup stability;
- committed oracle fixture parity for a bounded representative sample.

### Synthesis dictionary

- `семья|NN:Inanim:Fem:Sin:Nom` returns `семья`;
- `семья|NN:Inanim:Fem:Sin:R` returns `семьи`;
- unknown lemma/tag key -> empty result.

### Tagset

- deterministic loading of `tags_russian.txt`;
- lossless preservation of exact tag strings;
- empty colon components preserved;
- no invented feature reordering;
- duplicate/anomaly reporting deterministic;
- generated `compat/russian_tagset.json` exactly matches regeneration;
- persisted paths use POSIX `/`.

### Runtime boundary

- package import and dictionary lookup work with no Java process/server;
- production package has no dependency on Morfologik Java jars;
- no external NLP runtime dependency introduced.

Run the complete Task 0001 + Task 0002 focused pytest suite before completion.

## 16. Documentation/provenance/licensing

If Morfologik 2.1.9 source is copied, adapted, or vendored beyond minimal behavioral reference:

- determine and record its exact upstream revision/tag;
- record its exact license and attribution;
- update project third-party/license documentation as needed;
- do not copy source without provenance because it is "only a few methods".

Prefer a clean-room-ish Python implementation informed by documented/observable format behavior where practical, but exact compatibility is more important than pretending no reference source was consulted.

Any new vendored third-party file must receive the same SHA-256/provenance/license treatment established in Task 0001.

## 17. Expected repository shape

Exact layout may improve, but a reasonable result is:

```text
src/pylat_ru/
  morfologik/
    __init__.py
    errors.py
    metadata.py
    fsa.py
    sequence_encoder.py
    dictionary.py
  tagset.py

docs/
  morfologik_dictionary_format.md
  russian_tagset.md

compat/
  compatibility.json
  russian_tagset.json
  # optional deterministic oracle/tag inventory artifacts

tests/
  unit/
  upstream/
  fixtures/

tools/
  # optional deterministic dictionary oracle / tagset inventory helpers

reports/
  0002_dictionary_formats_lt_russian_tagset.md
```

Do not create empty architectural theatre. Use fewer files if the implementation is clearer that way.

---

## Acceptance criteria

Task 0002 is complete only if all are true:

1. The exact pinned LanguageTool v6.8 commit remains unchanged.
2. The Morfologik version relevant to LT v6.8 is identified and recorded.
3. The actual FSA format/version used by `russian.dict` is identified from the binary, not guessed.
4. The actual FSA format/version used by `russian_synth.dict` is identified from the binary, not guessed.
5. `.info` metadata is parsed from files and validated.
6. KOI8-R dictionary encoding works natively in Python.
7. `SUFFIX` sequence decoding reproduces the required Morfologik semantics.
8. Python can open and traverse the real pinned `russian.dict` without Java.
9. Python can open and traverse the real pinned `russian_synth.dict` without Java.
10. Morphological low-level lookups reproduce committed pinned-oracle `(stem, tag)` results for a representative bounded sample.
11. Lookup result ordering is deterministic and consistent with upstream behavior for that sample.
12. Unknown morphological lookup returns an empty low-level result, not a fabricated tag.
13. Raw synthesis lookup reproduces the pinned `семья` examples.
14. Unsupported FSA versions fail explicitly.
15. Corrupt/truncated FSA data fails explicitly.
16. Unsupported encoder/charset metadata fails explicitly.
17. The implementation does not eagerly expand the entire dictionary into heavyweight Python objects.
18. `RussianTag` or equivalent preserves the exact raw LT POS tag string.
19. Empty/legacy/odd tag components are not silently normalized away.
20. `tags_russian.txt` is inventoried deterministically.
21. `tagset.txt` semantics/mappings are documented or machine-inventoried with unparsed lines explicit.
22. A deterministic machine-readable Russian tagset artifact exists.
23. Dictionary/tagset validation coverage and any discrepancies are reported honestly.
24. Production code has no Java/JRE/server dependency.
25. No Natasha/pymorphy/other semantic morphology replacement is introduced.
26. Full Russian tagger behavior is **not** prematurely claimed implemented.
27. Full Russian synthesizer behavior is **not** prematurely claimed implemented.
28. `compat/compatibility.json` is updated honestly.
29. Focused Task 0001 + 0002 tests pass.
30. Completion report is written.
31. `git diff` is reviewed and unrelated changes removed.
32. The task is committed by the coding agent.
33. The committed current branch is pushed to `origin` and remote visibility is verified.
34. No force-push/history rewrite is used.
35. Task 0003 is **not** started automatically.

## Completion report

Create:

```text
reports/0002_dictionary_formats_lt_russian_tagset.md
```

Include at minimum:

- exact LT pin;
- Morfologik version/reference used;
- actual FSA format(s) detected in both Russian dictionaries;
- metadata values parsed from both `.info` files;
- implementation architecture;
- supported and explicitly unsupported FSA/encoder features;
- exact representative morphological parity cases;
- exact synthesis-dictionary parity cases;
- tagset counts/POS prefixes/features/anomalies;
- dictionary-vs-tagset validation results;
- tests run and results;
- performance/memory sanity observations;
- any license/provenance updates;
- known limitations;
- prerequisites for Task 0003, without implementing it.

## Key principle

Task 0002 should leave us with this trustworthy primitive:

```text
pinned LT Russian .dict + .info
        ↓
native Python FSA/Morfologik reader
        ↓
exact ordered stem/tag or synthesis-form results
        ↓
lossless LT Russian tag representation
```

Not this tempting shortcut:

```text
Russian word
→ some other Python morphology library
→ roughly similar POS tags
```

The whole point of `pylat_ru` is that later `grammar.xml`, disambiguation and synthesis operate on **LanguageTool-compatible data**, not merely linguistically plausible data.