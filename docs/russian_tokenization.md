# Russian Sentence and Word Tokenization Architecture

## 1. Overview

`pylat_ru` implements the native Python Russian tokenization layer required by the pinned LanguageTool `v6.8` pipeline:

```text
raw text
  ↓
RussianSentenceTokenizer (SRX 2.0, dynamic ru_two / ru_one map resolution)
  ↓
RussianWordTokenizer (delim split + Russian sentinels + URL/email join)
  ↓
lossless SentenceSpan & TokenSpan with exact source offsets
```

All operations execute in native Python with **zero Java/JRE, zero daemon/server, and zero third-party NLP tokenization dependencies** (such as Natasha, pymorphy, or razdel).

---

## 2. Upstream Target & Reference Versions

- **LanguageTool Tag**: `v6.8` (commit `e807fcde6a6506191e1470744d2345da28c26be6`).
- **SRX Specification & Reference Implementation**: SRX 2.0 / `net.loomchild.segment 2.0.3`.
- **SRX Rules Source**: `languagetool-core/src/main/resources/org/languagetool/resource/segment.srx` (SHA-256: `746cd57ee0be4a962875d4d3855f29cb1c3ab5daca5641de25d599ea055d64da`).
- **Word Tokenizer Sources**:
  - `RussianWordTokenizer.java` (Russian-specific sentinel rules and extra delimiter characters).
  - `WordTokenizer.java` (Generic delimiter set, email joining, and URL joining heuristics).

---

## 3. Sentence Segmentation (SRX 2.0)

### 3.1 Dynamic `<languagemap>` Resolution & Rule Sets

Pinned `segment.srx` specifies `cascade="yes"`. When a language code is requested, `<languagemap>` entries are evaluated dynamically in XML document order against `languagepattern`:

#### Default Mode: `ru_two` (45 rules total: 12 break, 33 exception)
Resolved groups in order:
1. `GeneralImportant` (7 rules: 0 break, 7 exception) — URL/email protection, abbreviations (`A.aegypti`, `.NET`, `FRITZ!Box`).
2. `ByTwoLineBreaks` (2 rules: 2 break, 0 exception) — Two consecutive newlines mark paragraph boundary (`\r?\n\s*\r?\n[\t]*`).
3. `Russian` (30 rules: 4 break, 26 exception) — Russian abbreviations (`млрд.`, `г.`, `гг.`, `тыс.`, `руб.`, `шт.`, `т.к.`, initials, etc.).
4. `Default` (6 rules: 6 break, 0 exception) — Generic fallback break rules.

#### Single-Line Mode: `ru_one` (44 rules total: 11 break, 33 exception)
Replaces `ByTwoLineBreaks` with `ByLineBreak` (1 rule: 1 break, 0 exception: `\r?\n`).

### 3.2 Segmentation State Machine (loomchild 2.0.3 Algorithm)

1. **Lookbehind Finitization**: In accordance with `net.loomchild.segment.util.Util.finitize()` (`maxLookbehindConstructLength = 100`):
   - Block quotes `\Q...\E` are converted to escaped literal characters.
   - Unescaped `*` is replaced by `{0,100}`.
   - Unescaped `+` is replaced by `{1,100}`.
   - Unescaped `{n,}` is replaced by `{n,100}`.
2. **Compilation**: Each break rule (`break="yes"`) is paired with an `exceptionPattern` created by joining all finitized exception rules (`break="no"`) preceding it with lookbehinds and lookaheads:
   $$\text{exception\_pattern} = \bigvee_{\text{rule } \in \text{preceding exceptions}} \left( (?<=\text{beforebreak}_{\text{finitized}}) (?=\text{afterbreak}) \right)$$
3. **Matching & Advancement (`SRXRuleMatcher`)**: Matches `beforebreak` followed immediately by `afterbreak`. When advancing the search position across successive iterations, Java `Matcher.find()` advancement semantics are preserved:
   - after a non-empty match (`bb_end > bb_start`): continues from `bb_end`;
   - after a zero-width match (`bb_end == bb_start`): advances by 1 code point (`bb_start + 1`).
4. **Selection**: The active matcher with the lowest `break_pos` is selected.
5. **Exception Evaluation**: The cumulative `exceptionPattern` is tested at `break_pos`. If it does not match, the split boundary is confirmed.
6. **Advancement**: Active matchers starting before the split boundary are reset to search from the boundary, while matchers positioned $\le \text{boundary}$ advance.

### 3.3 Java Regex Flag & Unicode Adaptation

- Java's `(?U)` flag (`Pattern.UNICODE_CHARACTER_CLASS`) enables Unicode-aware word boundaries `\b` and character classes. In Python, this is mapped to `(?u)` using the `regex` engine.
- Unicode character classes used in Russian rules (`\p{Ll}`, `\p{Lu}`, `\p{L}`, `\p{Pe}`) are natively supported by `regex`.

---

## 4. Word Tokenization (`RussianWordTokenizer`)

### 4.1 Delimiter Set & Base Splitting

Tokens are segmented character-by-character according to `WordTokenizer.TOKENIZING_CHARACTERS + ".'"`.
- Punctuation delimiters (e.g. `,`, `.`, `!`, `?`, `(`, `)`, `"`, `«`, `»`, `–`, `—`) are emitted as individual single-character tokens.
- Whitespace delimiters (spaces, tabs, newlines, NBSP `\u00A0`, Unicode spaces) are emitted as individual single-character tokens.
- Consecutive delimiters remain separate individual tokens matching Java `StringTokenizer(text, delim, true)`.
- Hyphen-minus (`-`) is deliberately **not** in the delimiter set, preserving compound words such as `русско-английский` as single tokens.

### 4.2 Russian Sentinel Replacements

`RussianWordTokenizer` applies exact placeholder substitutions before delimiter splitting and restores them afterwards:
- `б/у` $\to$ `\u0001\u0001SOCR_BU\u0001\u0001` (prevents slash splitting).
- `б/н` $\to$ `\u0001\u0001SOCR_BN\u0001\u0001` (prevents slash splitting).
- ` .. ` $\to$ `\u0001\u0001SP_DDOT_SP\u0001\u0001` $\to$ preserved.
- ` . ` $\to$ `\u0001\u0001SP_DOT_SP\u0001\u0001` $\to$ preserved.
- ` .` $\to$ ` \u0001\u0001SP_DOT\u0001\u0001` $\to$ ` .`.

### 4.3 URL & E-Mail Rejoining

- **E-mails**: Matched with regex `E_MAIL` and rejoined from constituent delimiter-split tokens. `is_email()` uses `fullmatch()` matching Java `Matcher.matches()`.
- **URLs**: Supports `http://`, `https://`, `ftp://`, `www.`, and domain/path heuristics with quote tracking and trailing punctuation exclusion (matching upstream LanguageTool quirks).

---

## 5. Offset Accounting & Span Model

### 5.1 Span Objects

```python
@dataclass(frozen=True)
class TextSpan:
    text: str
    start: int          # Python code-point start index
    end: int            # Python code-point end index
    utf16_start: int    # Java UTF-16 code unit start offset
    utf16_end: int      # Java UTF-16 code unit end offset

@dataclass(frozen=True)
class SentenceSpan(TextSpan):
    ...

@dataclass(frozen=True)
class TokenSpan(TextSpan):
    ...
```

### 5.2 Python Code Points vs Java UTF-16 Offsets

- **Python code-point offsets** (`start`, `end`): Slices Python strings directly with `source[start:end] == span.text`.
- **Java UTF-16 offsets** (`utf16_start`, `utf16_end`): Matches Java `String.length()` and LanguageTool error match positions.
- **Non-BMP characters** (e.g. emoji $> \text{U+FFFF}$): Take 1 Python code point, but 2 Java UTF-16 code units (surrogate pair). `Utf16CodePointMapper` provides an $O(N)$ prefix array conversion.

### 5.3 Invariant Guarantees

For any input text:
1. Exact reconstruction:
   $$\text{text} == \sum_{\text{sent} \in \text{spans}} \text{sent.text} == \sum_{\text{tok} \in \text{tokens}} \text{tok.text}$$
2. Contiguous coverage:
   $$\text{span}_{i+1}.\text{start} == \text{span}_i.\text{end}$$
3. No substring searches (`find()`) are used to derive offsets; offsets are computed cumulatively during the tokenization pass.

---

## 6. Runtime Performance & Dependency Bounds

### 6.1 Performance Benchmarks
Measured on standard single-threaded Python runtime:
- Sentence tokenizer initialization: **~0.13 ms** (rules compiled and cached in singleton manager).
- Word tokenizer initialization: **~0.00 ms**.
- Sentence tokenization of 37.6 KB text (22,175 chars, 400 sentences): **~12.8 ms** (~2.8 MB/s).
- Word tokenization of 37.6 KB text (7,775 tokens): **~3.7 ms** (~9.7 MB/s).
- Code-point $\leftrightarrow$ UTF-16 mapper construction: **~1.45 ms**.

### 6.2 Regex Engine Dependency
- Declared dependency: `regex>=2024.5.15,<=2026.7.19` (Apache-2.0 / Python Software Foundation License).
- Required for Java `(?U)` flag support, Unicode properties (`\p{Ll}`, `\p{Lu}`, `\p{L}`, `\p{Pe}`), and lookbehind execution.

---

## 7. Java Oracle Generator Command & Provenance

To regenerate the sentence and word tokenization oracle fixtures directly from the pinned official Java LanguageTool standalone distribution:

```bash
python tools/differential_lt.py --generate-tokenization-fixtures
```

This compiles and runs lightweight Java harnesses against `org.languagetool.language.Russian` in `LanguageTool-6.8/languagetool-commandline.jar` to populate:
- `tests/fixtures/oracle_russian_sentence_tokenization.json`
- `tests/fixtures/oracle_russian_word_tokenization.json`
