# morfologik-stemming Upstream License & Provenance Inventory

## Pinned Upstream Reference

- **Repository:** `https://github.com/morfologik/morfologik-stemming.git`
- **Pinned Tag:** `2.1.9`
- **Metadata File:** [UPSTREAM.json](UPSTREAM.json)
- **Machine-Readable Inventory:** [license_inventory.json](license_inventory.json)

`morfologik-stemming` 2.1.9 is the version LanguageTool 6.8 depends on. Its
`Speller` is what `org.languagetool.rules.spelling.morfologik.MorfologikSpeller`
delegates to, so it defines the observable Russian spelling verdicts, suggestion
set and suggestion ordering that `pylat_ru` must reproduce.

## License Overview

All vendored files are licensed under the **BSD 3-Clause License**, which is a
different license from the LGPL-2.1-or-later material under
[`third_party/languagetool/`](../languagetool/) and is therefore recorded
separately.

| Component | Provenance | License | Status | Notes |
|---|---|---|---|---|
| `morfologik-speller/src/main/java/morfologik/speller/` | Dawid Weiss, Marcin Miłkowski | BSD-3-Clause | `VERIFIED_BSD_3_CLAUSE` | `Speller` (Oflazer error-tolerant FSA search) and `HMatrix` |
| `morfologik-stemming/src/main/java/morfologik/stemming/` | Dawid Weiss, Marcin Miłkowski | BSD-3-Clause | `VERIFIED_BSD_3_CLAUSE` | `DictionaryMetadata`, `DictionaryAttribute`, `DictionaryLookup` |
| `LICENSE.txt` | Dawid Weiss, Marcin Miłkowski | BSD-3-Clause | `VERIFIED_BSD_3_CLAUSE` | Upstream license text |

## Review & Verification Findings

- Total vendored files: **6**
- Verified BSD-3-Clause files: **6**
- Files with unclear license / blocked items: **0** (`BLOCKED_LICENSE_REVIEW` count: 0)

These files are development/reference material only. No morfologik code is
executed by `pylat_ru`; `src/pylat_ru/morfologik/speller.py` is an independent
Python implementation whose behaviour is verified against the pinned Java oracle.
