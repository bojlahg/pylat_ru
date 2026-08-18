# Morfologik FSA Binary Format & Russian Dictionary Specification

## 1. Overview

LanguageTool uses the [Morfologik](https://github.com/morfologik/morfologik-stemming) library for morphological dictionary compression, tag lookup, and word form synthesis. At LanguageTool `v6.8` (commit `e807fcde6a6506191e1470744d2345da28c26be6`), the Morfologik version is pinned to **`2.1.9`**.

This document specifies the exact binary structures, sequence encoding, character sets, and metadata conventions used by the pinned Russian LanguageTool dictionaries (`russian.dict` and `russian_synth.dict`).

---

## 2. Pinned Russian Dictionaries Analysis

Inspection of the vendored Russian dictionaries in `third_party/languagetool/.../resource/ru/` yields the following verified facts:

| Property | `russian.dict` | `russian_synth.dict` |
| :--- | :--- | :--- |
| **Magic Header** | `\fsa` (`0x5C 0x66 0x73 0x61`) | `\fsa` (`0x5C 0x66 0x73 0x61`) |
| **FSA Version** | `0xC6` (**CFSA2** — Compact FSA v2) | `0xC6` (**CFSA2** — Compact FSA v2) |
| **Flags Byte** | `0x0007` (`FLEXIBLE`, `STOPBIT`, `NEXTBIT`) | `0x0007` (`FLEXIBLE`, `STOPBIT`, `NEXTBIT`) |
| **Has Numbers** | `False` (no perfect hashing / count prepended) | `False` (no perfect hashing / count prepended) |
| **Label Mapping Size** | 32 (31 indexed single-byte labels) | 32 (31 indexed single-byte labels) |
| **File Size** | 2,322,253 bytes (~2.3 MB) | 1,489,459 bytes (~1.5 MB) |
| **Separator** | `+` (`0x2B` in KOI8-R) | `+` (`0x2B` in KOI8-R) |
| **Encoding** | `koi8-r` | `koi8-r` |
| **Sequence Encoder** | `SUFFIX` (`TrimSuffixEncoder`) | `SUFFIX` (`TrimSuffixEncoder`) |
| **Frequency Bytes** | None (`frequency-included=false`) | None (`frequency-included=false`) |
| **Conversion Pairs** | None | None |

Both Russian dictionaries share the identical FSA format (**CFSA2**), encoding (**KOI8-R**), separator (**`+`**), and sequence encoder (**`SUFFIX`**).

---

## 3. CFSA2 Binary Layout

A CFSA2 file consists of a header block followed by serialized arc transitions.

### 3.1 Header Structure

```text
Byte 0..3:  Magic signature "\fsa" (0x5C 0x66 0x73 0x61)
Byte 4:     Version byte (0xC6 for CFSA2)
Byte 5..6:  Flags (16-bit big-endian integer, 0x0007)
            - Bit 0 (0x0001): FLEXIBLE
            - Bit 1 (0x0002): STOPBIT
            - Bit 2 (0x0004): NEXTBIT
            - Bit 3 (0x0008): NUMBERS (absent in Russian dicts)
Byte 7:     Label mapping table size M (typically 32)
Byte 8..8+M-1: Label mapping table (M bytes, index 1..M-1 map to frequent byte labels)
Byte 8+M..EOF: Graph arc data
```

### 3.2 Arc Encoding

Each arc is encoded as a variable-length byte sequence starting with a flags byte:

```text
Bit 7 (0x80): BIT_TARGET_NEXT — target node immediately follows the last arc of this state
Bit 6 (0x40): BIT_LAST_ARC    — this is the last arc leaving the current state
Bit 5 (0x20): BIT_FINAL_ARC   — this arc leads to an accepting/final state
Bits 4..0 (0x1F): LABEL_INDEX_MASK (5 bits, values 0..31)
```

1. **Arc Label**:
   - If `flag & 0x1F > 0`: Label is `label_mapping[flag & 0x1F]`.
   - If `flag & 0x1F == 0`: Label is stored explicitly in the byte immediately following the flag byte.

2. **Destination Node Address (Goto)**:
   - If `BIT_TARGET_NEXT` (`0x80`) is set: No explicit address. The destination node follows immediately after the last arc of the current node.
   - If `BIT_TARGET_NEXT` is not set: The destination node offset is variable-byte integer (v-int) encoded starting after the label (offset + 1 if label is indexed, or offset + 2 if label is explicit).

3. **Variable-Byte Integer (v-int) Encoding**:
   - 7 bits of data per byte; MSB (`0x80`) set indicates continuation bytes.
   - Decoded as: `val = (b0 & 0x7F) | ((b1 & 0x7F) << 7) | ((b2 & 0x7F) << 14) ...`

### 3.3 Automaton Traversal & Root Discovery

- **Epsilon / Initial State**: The root node is discovered by reading the epsilon arc at offset 0 and resolving its destination node: `root_node = get_destination_node_offset(0)`.
- **Matching a Word**:
  - Encode input word into KOI8-R bytes.
  - Starting at `root_node`, find matching arcs for each byte sequentially.
  - After matching all input word bytes, look for an arc with the separator byte (`+`, `0x2B`).
  - Follow the separator arc to its destination node.
  - Perform depth-first traversal of all paths reaching `BIT_FINAL_ARC` states to enumerate all suffix sequences.

---

## 4. Morfologik SUFFIX Sequence Encoding

In Morfologik dictionaries, entries are stored in prefix-compressed form:

```text
{inflected_word} + {stem_transformation_code} + {tag}
```

For the `SUFFIX` encoder (`TrimSuffixEncoder`):

- The stem transformation code starts with a single trim byte `K`.
- `truncate_bytes = (K - 'A') & 0xFF`.
- If `truncate_bytes == 255`: Truncate the entire source word (`truncate_bytes = len(source)`).
- The decoded stem is:
  ```python
  keep_len = len(source_bytes) - truncate_bytes
  stem_bytes = source_bytes[:keep_len] + suffix_bytes
  ```

### Example:
- Input word: `семьи` (KOI8-R bytes length 5)
- Suffix sequence: `Aя+NN:Inanim:Fem:Sin:R`
- Trim code `K = 'A' (0x41)` -> `cut = 0`.
- Stem suffix: `я` (`0xD1`).
- `stem_bytes = 'семьи'[:5-0] + 'я' = 'семья'`.
- Tag: `NN:Inanim:Fem:Sin:R`.

---

## 5. Synthesis Dictionary Lookup Semantics

The synthesis dictionary `russian_synth.dict` uses the identical CFSA2 format with keys constructed as:

```text
{lemma} | {pos_tag}
```

Looking up `семья|NN:Inanim:Fem:Sin:Nom` (length 27 bytes):
- FSA matches the prefix and finds separator `+`.
- Suffix sequence is `b'W'` (`0x57`).
- Trim code `'W' - 'A' = 87 - 65 = 22`.
- Keep length: `27 - 22 = 5` bytes (`семья`).
- Suffix bytes after trim code: empty `b""`.
- Decoded synthesized form: `семья`.

Looking up `семья|NN:Inanim:Fem:Sin:R` (length 25 bytes):
- Suffix sequence is `b'V\xc9'`.
- Trim code `'V' - 'A' = 86 - 65 = 21`.
- Keep length: `25 - 21 = 4` bytes (`семь`).
- Suffix byte: `\xc9` (`и` in KOI8-R).
- Decoded synthesized form: `семьи`.

---

## 6. Supported vs Intentionally Unsupported Features

### Supported in `pylat_ru`:
- `CFSA2` binary format (version `0xC6`).
- `SUFFIX` sequence encoder (`TrimSuffixEncoder`).
- `KOI8-R` character encoding.
- Single-byte separator validation.
- Traversal bounds checking and explicit corruption errors (`CorruptedFSAError`).
- Deterministic traversal order matching upstream Morfologik.

### Intentionally Unsupported (Explicit Errors):
- `FSA5` (version `0x05`) — raises `UnsupportedFSAFormatError`.
- `CFSA` v1 (version `0xC5`) — raises `UnsupportedFSAFormatError`.
- `NUMBERS` / perfect hashing — raises `UnsupportedFSAFormatError` / `CorruptedFSAError`.
- `PREFIX` and `INFIX` sequence encoders — raises `UnsupportedEncoderError`.
- Non-standard encodings — raises `UnsupportedEncodingError`.
