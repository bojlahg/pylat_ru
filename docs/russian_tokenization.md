# Russian Sentence and Word Tokenization Architecture

## 1. Overview

`pylat_ru` implements the native Python Russian tokenization layer required by the pinned LanguageTool `v6.8` pipeline:

```text
raw text
  ↓
RussianSentenceTokenizer (SRX 2.0, ru_two / ru_one)
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

### 3.1 Cascade Resolution & Rule Sets

Pinned `segment.srx` specifies `cascade="yes"`. When a language code is requested, matching `<languagemap>` entries are evaluated in file order:

#### Default Mode: `ru_two` (45 rules total: 12 break, 33 exception)
Evaluates rules in the following order:
1. `GeneralImportant` (7 rules: 0 break, 7 exception) — URL/email protection, abbreviations (`A.aegypti`, `.NET`, `FRITZ!Box`).
2. `ByTwoLineBreaks` (2 rules: 2 break, 0 exception) — Two consecutive newlines mark paragraph boundary (`\r?\n\s*\r?\n[\t]*`).
3. `Russian` (30 rules: 4 break, 26 exception) — Russian abbreviations (`млрд.`, `г.`, `гг.`, `тыс.`, `руб.`, `шт.`, `т.к.`, initials, etc.).
4. `Default` (6 rules: 6 break, 0 exception) — Generic fallback break rules.

#### Single-Line Mode: `ru_one` (44 rules total: 11 break, 33 exception)
Replaces `ByTwoLineBreaks` with `ByLineBreak` (1 rule: 1 break, 0 exception: `\r?\n`).

### 3.2 Segmentation State Machine (loomchild 2.0.3 Algorithm)

1. **Compilation**: Each break rule (`break="yes"`) is paired with an `exceptionPattern` created by joining all exception rules (`break="no"`) preceding it with lookbehinds and lookaheads:
   $$\text{exception\_pattern} = \bigvee_{\text{rule } \in \text{preceding exceptions}} \left( (?<=\text{beforebreak}) (?=\text{afterbreak}) \right)$$
2. **Matching**: For each active break rule, an `SRXRuleMatcher` matches `beforebreak` followed immediately by `afterbreak`.
3. **Selection**: The matcher with the lowest `break_pos` is selected.
4. **Exception Evaluation**: The cumulative `exceptionPattern` is tested at `break_pos`. If it does not match, the split boundary is confirmed.
5. **Advancement**: Active matchers starting before the split boundary are reset to search from the boundary, while matchers positioned $\le \text{boundary}$ advance.

### 3.3 Java Regex Flag & Unicode Adaptation

- Java's `(?U)` flag (`Pattern.UNICODE_CHARACTER_CLASS`) enables Unicode-aware word boundaries `\b` and character classes. In Python, this is mapped to `(?u)` using the `regex` engine.
- Unicode character classes used in Russian rules (`\p{Ll}`, `\p{Lu}`, `\p{L}`, `\p{Pe}`) are fully supported by `regex`.

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

- **E-mails**: Matched with regex `E_MAIL` and rejoined from constituent delimiter-split tokens.
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

## 6. Runtime Performance

Measured on standard single-threaded Python runtime:
- Sentence tokenizer initialization: **~0.13 ms** (rules compiled and cached in singleton manager).
- Word tokenizer initialization: **~0.00 ms**.
- Sentence tokenization of 37.6 KB text (22,175 chars, 400 sentences): **~12.8 ms** (~2.8 MB/s).
- Word tokenization of 37.6 KB text (7,775 tokens): **~3.7 ms** (~9.7 MB/s).
- Code-point $\leftrightarrow$ UTF-16 mapper construction: **~1.45 ms**.
