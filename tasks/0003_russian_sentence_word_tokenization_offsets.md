# Task 0003 — Russian Sentence + Word Tokenization with Exact Offsets

## Status

READY

## Goal

Implement the native Python Russian tokenization layer required by the pinned LanguageTool pipeline:

```text
raw text
  ↓
RussianSentenceTokenizer (SRX, ru_two / ru_one)
  ↓
RussianWordTokenizer
  ↓
lossless sentence/token spans with exact source offsets
```

Task 0003 must reproduce the observable tokenization behavior of pinned LanguageTool `v6.8` for Russian without Java at production runtime.

This task covers **sentence segmentation, word tokenization, exact text preservation, and offset accounting only**. It must not implement the Russian tagger, disambiguator, chunker, synthesizer, or grammar engine.

The resulting primitives must be trustworthy enough that later layers can attach morphology and rule matches without re-tokenizing or guessing offsets.

---

## Pinned compatibility target

The compatibility pin remains unchanged:

```text
LanguageTool tag:    v6.8
LanguageTool commit: e807fcde6a6506191e1470744d2345da28c26be6
```

Do not change the LanguageTool pin in Task 0003.

Task 0002 established the native Morfologik dictionary foundation and is a prerequisite, but Task 0003 must not depend on dictionary lookup for tokenization.

### Relevant pinned upstream implementation

Inspect and use as compatibility references at minimum:

```text
languagetool-language-modules/ru/src/main/java/org/languagetool/language/Russian.java
languagetool-language-modules/ru/src/main/java/org/languagetool/tokenizers/ru/RussianWordTokenizer.java

languagetool-core/src/main/java/org/languagetool/tokenizers/WordTokenizer.java
languagetool-core/src/main/java/org/languagetool/tokenizers/SRXSentenceTokenizer.java
languagetool-core/src/main/java/org/languagetool/tokenizers/SrxTools.java
languagetool-core/src/main/resources/org/languagetool/resource/segment.srx

languagetool-language-modules/ru/src/test/java/org/languagetool/tokenizers/ru/RussianSRXSentenceTokenizerTest.java
languagetool-core/src/test/java/org/languagetool/tokenizers/WordTokenizerTest.java
languagetool-core/src/test/java/org/languagetool/TestTools.java
```

Pinned `segment.srx` at `v6.8` is:

```text
Git blob SHA: a30c04400bdadd4eaf339ce6a202a424db5beeae
size:         213633 bytes
```

LanguageTool `v6.8` declares:

```text
net.loomchild.segment.version = 2.0.3
```

The relevant SRX behavior must therefore be compared against **net.loomchild.segment 2.0.3**, not a current/floating implementation.

### Important upstream facts already established

`Russian.java` selects:

```java
new SRXSentenceTokenizer(this)
new RussianWordTokenizer()
```

`SRXSentenceTokenizer` defaults to:

```text
singleLineBreaksMarksParagraph = false
language code passed to SRX = ru_two
```

and when single-line paragraph mode is enabled:

```text
language code passed to SRX = ru_one
```

`RussianWordTokenizer` inherits the generic `WordTokenizer`, adds its Russian-specific preprocessing and then calls `joinEMailsAndUrls(...)`.

The generic `WordTokenizer` preserves punctuation and whitespace as tokens, with URL/e-mail rejoining after the initial character split.

---

## Mandatory project constraints

Read and obey:

```text
AGENTS.md
docs/Handoff_pylat_ru.md
reports/0001_project_foundation_upstream_inventory.md
reports/0002_dictionary_formats_lt_russian_tagset.md
```

In particular:

- production Python must not launch Java/JRE or LanguageTool Server;
- Java may be used only as a development/test oracle;
- no Natasha, pymorphy, spaCy tokenizer, NLTK tokenizer, razdel, or other semantic/tokenization replacement;
- do not replace pinned SRX behavior with a generic sentence splitter;
- do not silently drop or normalize whitespace/punctuation;
- unknown/unsupported SRX or regex features must fail explicitly;
- no network access during import or tokenization;
- exact upstream behavior is more important than a tokenizer that merely “looks reasonable”.

---

# Scope boundary

## In scope

- exact Russian sentence segmentation based on pinned `segment.srx`;
- effective SRX rule mapping for `ru_two` and `ru_one`;
- required subset of SRX 2.0 / loomchild 2.0.3 semantics used by those Russian mappings;
- Russian word tokenization matching `RussianWordTokenizer` + relevant `WordTokenizer` behavior;
- exact whitespace/punctuation preservation;
- URL and e-mail joining used by `RussianWordTokenizer`;
- Russian special cases in `RussianWordTokenizer` (`б/у`, `б/н`, dot-space sentinel behavior);
- deterministic token/sentence ordering;
- source spans and offset accounting;
- Java UTF-16 offset compatibility alongside Python code-point offsets;
- committed oracle fixtures generated from pinned LT v6.8;
- deterministic SRX inventory/derived runtime resource if used;
- compatibility matrix update.

## Explicitly out of scope

Do not implement yet:

- `RussianTagger`;
- dictionary case fallback / accent normalization / `ё` behavior;
- ignored-character removal from `Russian.getIgnoredCharactersRegex()`;
- `AnalyzedToken` / `AnalyzedTokenReadings` morphology objects beyond minimal tokenizer span types;
- disambiguation;
- chunking;
- synthesis;
- XML grammar rules;
- spelling;
- sentence-start POS pseudo-token semantics beyond reserving clean integration points;
- currency-expression splitting unless it is proven to be invoked by the Russian `tokenize()` path at the pinned version;
- emoji replacement helpers unless they are proven to be invoked by the Russian `tokenize()` path at the pinned version.

Do not implement generic multilingual SRX support beyond what is necessary for the exact Russian `ru_two` / `ru_one` behavior.

---

# Deliverables

## 1. Inventory the exact Russian SRX compatibility surface

Before implementing sentence segmentation, analyze the pinned `segment.srx` and loomchild segment `2.0.3` behavior.

Determine and record at minimum:

- SRX header options relevant to tokenization;
- `cascade` behavior;
- exact map rules matching `ru_two`;
- exact map rules matching `ru_one`;
- effective language-rule groups selected for each code, in order;
- count of effective `break="yes"` and `break="no"` rules;
- exact order of rules after mapping/cascade;
- `beforebreak` / `afterbreak` matching semantics;
- rule precedence when several rules match one boundary;
- whitespace ownership at a sentence boundary;
- paragraph boundary behavior for `ru_two` and `ru_one`;
- Java-regex constructs used by the effective Russian rules;
- which SRX/Okapi extensions in the file are actually relevant to the Russian path;
- unsupported SRX features, if any, that are not needed by the pinned Russian path.

Create deterministic machine-readable inventory, for example:

```text
compat/russian_srx_inventory.json
```

It should contain enough source/provenance information to detect accidental drift, including at least:

```text
LT pin
segment.srx path
segment.srx blob/hash
loomchild version
ru_two mappings/rule counts
ru_one mappings/rule counts
regex feature inventory
unsupported/unparsed items
```

Also create a concise implementation document, for example:

```text
docs/russian_tokenization.md
```

Do not hand-write a list of Russian abbreviations and call it SRX compatibility.

---

## 2. Decide and implement the runtime SRX resource strategy

Production tokenization must not require a source checkout layout such as `third_party/...` forever.

Use one of these approaches, with justification:

### Preferred approach

Generate a deterministic runtime resource from the pinned `segment.srx`, containing exactly the effective rules/mappings required for `ru_two` and `ru_one`, e.g.:

```text
src/pylat_ru/resources/russian_srx_rules.json
```

Requirements:

- generated from the pinned original, not manually duplicated;
- preserves rule order and exact regex strings;
- includes source blob/hash/pin metadata;
- regeneration is deterministic;
- committed generated artifact exactly matches regeneration in tests;
- included in package data;
- upstream source remains the provenance/source of truth.

### Acceptable alternative

Package/read the original pinned SRX resource directly, if the implementation makes standalone package installation reliable and does not depend on repository-relative paths.

Whichever approach is chosen, a normal installed package must eventually be able to tokenize without locating `third_party/` by walking the current Git checkout.

Task 0015 remains responsible for final packaging/release hardening, but Task 0003 must not knowingly create an unpackageable runtime dependency.

---

## 3. Native Russian sentence tokenizer

Implement a native Python sentence tokenizer matching the pinned Russian `SRXSentenceTokenizer` behavior.

Suggested conceptual interface:

```python
class RussianSentenceTokenizer:
    def __init__(self, single_line_breaks_marks_paragraph: bool = False): ...
    def tokenize(self, text: str) -> tuple[str, ...]: ...
    def tokenize_spans(self, text: str) -> tuple[SentenceSpan, ...]: ...
```

Exact names may improve, but observable behavior must remain clear.

Requirements:

- default mode matches `ru_two`;
- optional single-line paragraph mode matches `ru_one`;
- uses pinned SRX rules, not heuristic sentence punctuation splitting;
- exact returned sentence text must match LT, including whitespace attached to sentence segments;
- empty input behavior must match oracle;
- no hidden trimming;
- no newline normalization (`\r\n` must not silently become `\n`);
- deterministic output;
- malformed runtime SRX resource must fail explicitly;
- unsupported effective SRX feature must raise an explicit compatibility error rather than silently ignoring the rule.

### SRX regex engine

Pinned SRX uses Java regex (`useJavaRegex="yes"`) and effective rules may contain constructs such as Unicode properties (`\p{Lu}`, `\p{Ll}`, `\p{L}`, `\p{Pe}`, etc.).

Do not approximate these with ASCII regexes.

Acceptable implementation choices include:

1. use a Python regex engine/library that supports the required Unicode-property semantics; or
2. implement a narrowly scoped translation/evaluation layer for all constructs actually used by the effective Russian rules.

If a third-party Python regex package is introduced:

- inspect and document its license;
- add the minimal dependency intentionally;
- do not add a broad NLP stack;
- test every effective Russian SRX regex for successful compilation;
- document known Java-vs-Python regex semantic differences;
- prove representative behavior against the pinned Java oracle.

If an effective pattern cannot be represented faithfully, stop with an explicit compatibility failure rather than changing the pattern’s meaning.

---

## 4. Port the upstream Russian sentence tests exactly

The pinned upstream Russian test contains abbreviation cases that must not be split incorrectly. Port all examples from:

```text
RussianSRXSentenceTokenizerTest.java
```

including at least the cases around:

```text
млрд.
г.
гг.
тыс.
руб.
шт.
т.к.
```

The test helper in upstream concatenates expected sentence strings and asserts exact equality with tokenizer output. Preserve that spirit: test exact returned strings, not merely sentence counts.

Add additional pinned-oracle cases for:

- ordinary multi-sentence Russian prose;
- quotes around sentence endings;
- brackets around sentence endings;
- `!`, `?`, `.`, ellipsis / Unicode ellipsis where applicable;
- initials and abbreviations represented in effective SRX rules;
- decimal/numeric punctuation if covered by effective rules;
- paragraph boundaries;
- `\n`, `\r\n`, blank lines;
- `ru_two` vs `ru_one` behavior;
- leading/trailing whitespace;
- empty text;
- URLs/e-mails containing periods where sentence segmentation behavior matters.

Expected results must come from the pinned Java oracle, not intuition.

---

## 5. Native Russian word tokenizer

Implement the observable behavior of pinned:

```text
RussianWordTokenizer
  + relevant inherited WordTokenizer behavior
```

Suggested conceptual interface:

```python
class RussianWordTokenizer:
    def tokenize(self, text: str) -> tuple[str, ...]: ...
    def tokenize_spans(self, text: str, *, base_offset: int = 0) -> tuple[TokenSpan, ...]: ...
```

### Exact base split behavior

Reproduce the pinned `WordTokenizer.TOKENIZING_CHARACTERS` set that is relevant to `RussianWordTokenizer`.

Important behavior:

- punctuation delimiters are returned as tokens;
- whitespace delimiters are returned as tokens;
- consecutive delimiters remain separate tokens exactly as Java `StringTokenizer(..., returnDelims=true)` produces them;
- runs of non-delimiter characters remain one token before URL/e-mail joining;
- ordinary hyphen-minus (`-`) is deliberately not a generic splitting character in pinned `WordTokenizer`;
- en/em dashes and the other explicit dash characters in the upstream delimiter set are splitting characters;
- NBSP and the full upstream whitespace/control delimiter set must not be reduced to plain ASCII space handling.

Do not replace the delimiter set with `\s` or `string.punctuation`.

### Russian-specific behavior

Reproduce the exact Russian preprocessing/restoration path from `RussianWordTokenizer.java`, including:

```text
б/у
б/н
" .. "
" . "
" ."
```

Do not “clean up” the sentinel logic because it appears odd. Observable output parity is the criterion.

Sentinel/internal placeholder values must never leak into returned tokens.

### URL and e-mail joining

Port the relevant inherited behavior from pinned `WordTokenizer`:

- e-mail recognition and joining;
- `http://`, `https://`, `ftp://` URL joining;
- `www.` URL handling;
- no-protocol domain-with-slash handling used by upstream;
- punctuation termination around URLs;
- quote/bracket termination around URLs;
- incomplete URL behavior as tested upstream.

Do not use a modern URL parser that changes LanguageTool’s quirks. We are reproducing the pinned tokenizer, including its limitations.

Port the relevant cases from pinned `WordTokenizerTest.java` that exercise behavior actually inherited by Russian tokenization.

---

## 6. Preserve exact source text

For every sentence and word tokenization result, enforce this invariant:

```python
"".join(span.text for span in spans) == original_text
```

For word-tokenizing a sentence span:

```python
"".join(token.text for token in tokens) == sentence.text
```

No character may be:

- deleted;
- normalized;
- NFC/NFD converted;
- case-folded;
- whitespace-collapsed;
- quote-normalized;
- dash-normalized;
- silently replaced.

This includes control/Unicode whitespace tokens supported by upstream.

The later LanguageTool pipeline may ignore some characters for linguistic analysis, but Task 0003 must preserve source text exactly.

---

## 7. Implement explicit span objects and offset accounting

Introduce minimal immutable span types suitable for later morphology/rule integration.

Conceptually:

```python
@dataclass(frozen=True)
class TextSpan:
    text: str
    start: int
    end: int
    utf16_start: int
    utf16_end: int

@dataclass(frozen=True)
class SentenceSpan(TextSpan):
    ...

@dataclass(frozen=True)
class TokenSpan(TextSpan):
    ...
```

Exact class hierarchy is flexible.

### Python offsets

`start` / `end` should be Python code-point indices so that:

```python
source[start:end] == text
```

for every span.

### LanguageTool-compatible offsets

Java `String.length()` and LanguageTool internal positions count UTF-16 code units. Therefore also retain explicit UTF-16 offsets:

```text
utf16_start
utf16_end
```

Requirements:

- BMP Russian text has identical code-point and UTF-16 positions;
- non-BMP text (e.g. emoji) intentionally diverges;
- conversion is deterministic and tested;
- later rule-engine code must not have to rediscover this distinction;
- do not label UTF-16 offsets simply `start` and then use them for Python slicing.

Add a utility for code-point ↔ UTF-16 boundary mapping that operates linearly over the source, not `encode('utf-16-le')` repeatedly for every token in an O(n²) manner.

### Span invariants

For every segmentation/tokenization result:

- spans are ordered;
- no overlaps;
- no gaps if the returned pieces cover the full input;
- `span.end == next_span.start` for contiguous pieces;
- first span starts at 0 (or explicit `base_offset` for nested tokenization);
- final span ends at `len(text)`;
- UTF-16 positions are monotonic and correspond to the same boundaries.

---

## 8. Do not derive offsets by searching token text

Repeated tokens make `text.find(token)` unsafe.

Offsets should come from deterministic cumulative source coverage or directly from the segmentation algorithm.

For word tokens, because the final token sequence must exactly concatenate to the original sentence, cumulative lengths are sufficient after final URL/e-mail joining.

For sentence spans, boundaries must come directly from the SRX segmentation process.

Add regression tests containing repeated identical words/punctuation to prove offsets do not depend on substring search.

---

## 9. Java oracle fixtures

Extend the existing development-only oracle boundary to produce deterministic tokenization fixtures from pinned LT v6.8.

Commit fixtures for both sentence and word tokenization, for example:

```text
tests/fixtures/oracle_russian_sentence_tokenization.json
tests/fixtures/oracle_russian_word_tokenization.json
```

Each fixture should record:

```text
LT tag/commit
loomchild segment version (sentence fixture)
input string
mode (ru_two / ru_one where relevant)
ordered output strings
UTF-16 boundaries if generated directly from Java
```

The Python tests must run without Java using the committed fixtures.

The oracle generator must be deterministic and development-only.

Do not create a test that compares Python output against a fixture generated by the same Python implementation.

---

## 10. Word-tokenizer parity corpus

The committed word-tokenizer fixture must cover at minimum:

### Russian/basic

- ordinary Cyrillic words and spaces;
- punctuation;
- hyphen-minus inside a word;
- en dash / em dash separators;
- apostrophe and period behavior;
- `б/у`;
- `б/н`;
- the Russian dot-space sentinel edge cases from source;
- leading/trailing whitespace;
- repeated whitespace;
- tab, CR, LF;
- NBSP;
- empty input.

### URL/e-mail inherited behavior

Port representative exact expectations from pinned `WordTokenizerTest`, including:

```text
dev.all@languagetool.org
dev.all@languagetool.org.
http://foo.org
http://foo.org.
ftp://bla.com
www.languagetool.org
languagetool.org/foo
sub.languagetool.org/foo
URLs followed by comma/period/colon/question/exclamation
quoted URLs
parenthesized URLs
incomplete http:/ / http:// cases
```

Include Russian surrounding text around several URLs/e-mails to prove inherited joining is not accidentally ASCII-sentence-specific.

### Unicode/offset safety

Include:

- emoji before/inside/after ordinary text;
- combining acute/grave marks;
- Cyrillic + emoji + punctuation;
- repeated identical tokens.

The token strings must match LT. The Python code-point spans and Java UTF-16 spans must both be validated.

---

## 11. Sentence-tokenizer parity corpus

Create a bounded but representative sentence fixture that includes:

- all pinned `RussianSRXSentenceTokenizerTest` examples;
- at least several genuine multi-sentence inputs so splitting is actually exercised;
- abbreviation followed by lowercase continuation;
- abbreviation followed by uppercase text where SRX still suppresses a break;
- ordinary sentence break after punctuation;
- closing quotes/brackets after terminal punctuation;
- paragraph boundary behavior;
- `ru_two` and `ru_one` contrast;
- leading/trailing whitespace;
- CRLF;
- empty text;
- emoji/non-BMP text to validate offsets.

For every case, assert exact ordered strings and spans.

---

## 12. SRX/parser errors must be explicit

Introduce project-specific errors or equivalent explicit failures for at least:

```text
invalid/malformed SRX runtime resource
missing ru_two mapping
missing ru_one mapping
unsupported effective SRX feature
unsupported effective SRX regex construct
regex compilation failure
inconsistent generated SRX metadata/hash
```

Do not silently skip a rule that failed to compile.

A tokenizer that returns “mostly correct” sentences after dropping unsupported rules is not acceptable.

---

## 13. Runtime performance sanity

Correctness is primary, but avoid pathological architecture.

Record focused measurements for at least:

- sentence tokenizer initialization / effective-rule load;
- sentence tokenization of a representative 10–50 KB Russian text;
- word tokenization of the same text sentence by sentence;
- span/UTF-16 mapping overhead.

No hard performance target is required yet.

However:

- do not reparse SRX XML for every sentence;
- do not recompile every regex for every call;
- do not recompute a full UTF-16 prefix map separately for every token;
- do not launch subprocesses.

Compiled rules/resources should be reused by tokenizer instances.

---

## 14. Compatibility matrix update

Update:

```text
compat/compatibility.json
```

After successful completion, add/mark explicit statuses for at least:

```text
RussianSentenceTokenizer
RussianSentenceTokenizer_ru_two
RussianSentenceTokenizer_ru_one
RussianWordTokenizer
token_spans_codepoint_offsets
token_spans_utf16_offsets
russian_srx_inventory
```

Keep later layers honest:

```text
RussianTagger           NOT_YET_IMPLEMENTED
RussianDisambiguator    NOT_YET_IMPLEMENTED
RussianChunker          NOT_YET_IMPLEMENTED
RussianSynthesizer      NOT_YET_IMPLEMENTED
XMLRuleEngine           NOT_YET_IMPLEMENTED
```

Do not mark the full LanguageTool pipeline implemented merely because tokenization now works.

---

## 15. Tests

Add focused tests under a clear layout, for example:

```text
tests/unit/test_offsets.py
tests/unit/test_srx_rules.py
tests/unit/test_russian_sentence_tokenizer.py
tests/unit/test_russian_word_tokenizer.py
tests/upstream/test_russian_sentence_tokenizer_parity.py
tests/upstream/test_russian_word_tokenizer_parity.py
```

Exact split is flexible.

### Required sentence coverage

- pinned `segment.srx` source/hash or generated-runtime-resource provenance verified;
- `ru_two` effective mapping resolved deterministically;
- `ru_one` effective mapping resolved deterministically;
- all effective regex patterns compile;
- unsupported/unparsed effective feature count is zero, or task fails;
- complete deterministic regeneration of SRX inventory/resource;
- exact upstream Russian abbreviation examples;
- multi-sentence splitting;
- paragraph/newline modes;
- quote/bracket punctuation;
- empty input;
- oracle fixture parity;
- exact source reconstruction.

### Required word coverage

- exact upstream delimiter-set behavior for representative characters;
- punctuation/whitespace retained;
- multiple delimiters remain separate;
- `б/у` and `б/н` preserved as required;
- Russian dot sentinel cases;
- e-mail joining;
- URL joining and termination;
- incomplete URL quirks;
- NBSP/control whitespace;
- ordinary hyphen-minus not split by generic base behavior;
- dashes that are upstream delimiters are split;
- oracle fixture parity;
- exact source reconstruction.

### Required offsets coverage

- every span slices the source correctly by code-point offsets;
- UTF-16 offset helper agrees with Java-style length on fixture boundaries;
- BMP-only Russian case;
- non-BMP emoji case;
- repeated text case;
- nested sentence → word spans use correct absolute offsets;
- no gap/overlap invariants.

### Runtime boundary

- tests pass with Java absent;
- no Java process/server is launched by production tokenizer code;
- no external NLP package is introduced as a semantic substitute;
- no network access occurs.

Run the complete Task 0001 + 0002 + 0003 focused pytest suite before completion.

---

## 16. Provenance and licensing

If source or data from loomchild segment 2.0.3 is copied/adapted:

- record exact version/revision;
- record exact license;
- add attribution/provenance under the project’s existing third-party policy;
- do not copy implementation code without attribution just because it is small.

If a new Python regex dependency is added:

- record why it is required;
- record its license;
- add only the dependency actually needed;
- avoid floating/unbounded behavior where compatibility would be affected.

If new upstream LT files must be vendored because Task 0001 did not include them, use the existing SHA-256/provenance/license workflow and the exact pinned LT commit.

---

## 17. Expected repository shape

A reasonable result may look like:

```text
src/pylat_ru/
  tokenization/
    __init__.py
    offsets.py
    sentence.py
    word.py
    srx.py
  resources/
    russian_srx_rules.json        # if generated-resource approach is used

compat/
  compatibility.json
  russian_srx_inventory.json

docs/
  russian_tokenization.md

tests/
  fixtures/
    oracle_russian_sentence_tokenization.json
    oracle_russian_word_tokenization.json
  unit/
  upstream/

tools/
  russian_srx_inventory.py
  # optional dev-only tokenization oracle helper

reports/
  0003_russian_sentence_word_tokenization_offsets.md
```

Do not create empty files merely to imitate this tree.

---

# Acceptance criteria

Task 0003 is complete only if all are true:

1. The LT pin remains exactly `v6.8` / `e807fcde6a6506191e1470744d2345da28c26be6`.
2. `segment.srx` provenance/hash is verified against the pinned source.
3. loomchild segment reference version `2.0.3` is recorded.
4. Effective `ru_two` SRX mappings/rules are inventoried in deterministic order.
5. Effective `ru_one` SRX mappings/rules are inventoried in deterministic order.
6. No effective Russian SRX rule is silently skipped.
7. Every effective Russian SRX regex compiles in the chosen native implementation or the task fails explicitly.
8. Sentence tokenization runs in Python with no Java runtime.
9. Default sentence mode reproduces pinned `ru_two` behavior.
10. Optional single-line paragraph mode reproduces pinned `ru_one` behavior.
11. All examples from pinned `RussianSRXSentenceTokenizerTest` pass exactly.
12. A committed pinned-Java sentence oracle fixture passes exactly.
13. Returned sentence strings preserve exact whitespace and punctuation.
14. Concatenated sentence strings exactly reconstruct source text.
15. Russian word tokenization runs in Python with no Java runtime.
16. Base delimiter behavior relevant to Russian matches pinned `WordTokenizer`.
17. Russian `б/у` behavior matches pinned `RussianWordTokenizer`.
18. Russian `б/н` behavior matches pinned `RussianWordTokenizer`.
19. Russian dot-space/sentinel edge behavior matches pinned oracle.
20. E-mail joining matches pinned inherited behavior for representative tests.
21. URL joining/termination matches pinned inherited behavior for representative tests.
22. A committed pinned-Java word oracle fixture passes exactly.
23. Concatenated word tokens exactly reconstruct the input sentence/text.
24. Word-token offsets are not derived with substring search.
25. Sentence spans preserve exact Python code-point source boundaries.
26. Word spans preserve exact Python code-point source boundaries.
27. UTF-16 offsets are retained and match Java-style boundaries.
28. Non-BMP/emoji tests prove code-point vs UTF-16 distinction correctly.
29. Sentence → word absolute nested offsets are correct.
30. Span ordering/gap/overlap invariants are tested.
31. SRX/generated runtime resource regeneration is deterministic and compared completely, not only by summary counters.
32. Production tokenization does not rely on repository-relative `third_party` paths without a packaging strategy.
33. `compat/compatibility.json` is updated honestly.
34. `RussianTagger` remains `NOT_YET_IMPLEMENTED`.
35. `RussianDisambiguator` remains `NOT_YET_IMPLEMENTED`.
36. `RussianSynthesizer` remains `NOT_YET_IMPLEMENTED`.
37. No unrelated NLP tokenizer library is used as a behavioral substitute.
38. Complete Task 0001 + 0002 + 0003 focused tests pass.
39. Completion report is written.
40. `git diff` / `git status` are reviewed and unrelated changes removed.
41. The task is committed by the coding agent.
42. The committed current branch is pushed to `origin`.
43. Remote visibility of the pushed commit is verified.
44. No force-push/history rewrite is used.
45. Task 0004 is not started automatically.

---

## Completion report

Create:

```text
reports/0003_russian_sentence_word_tokenization_offsets.md
```

Include at minimum:

- exact LT pin;
- exact `segment.srx` hash/blob;
- loomchild segment reference version;
- effective `ru_two` and `ru_one` rule/mapping counts;
- SRX implementation strategy;
- regex engine/translation strategy and compatibility limitations;
- word-tokenizer implementation strategy;
- exact Russian special cases reproduced;
- URL/e-mail behavior covered;
- sentence oracle case count/results;
- word oracle case count/results;
- code-point vs UTF-16 offset design;
- representative offset examples including a non-BMP character;
- exact source-reconstruction proof;
- tests run and results;
- performance sanity measurements;
- dependencies/licenses/provenance added;
- known limitations;
- prerequisites for Task 0004 without implementing it.

---

## Key principle

Task 0003 should leave us with this invariant:

```text
original text
  == concatenate(sentence.text)
  == concatenate(all token.text in source order)
```

while simultaneously reproducing pinned LanguageTool sentence/token boundaries and retaining both Python-safe and LT-compatible offsets.

The correct outcome is not “good Russian tokenization”. The correct outcome is **the same Russian tokenization LanguageTool v6.8 performs, expressed natively and losslessly in Python**.
