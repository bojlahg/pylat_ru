# LanguageTool Upstream License & Provenance Inventory

## Pinned Upstream Reference

- **Repository:** `https://github.com/languagetool-org/languagetool.git`
- **Pinned Tag:** `v6.8`
- **Pinned Commit:** `e807fcde6a6506191e1470744d2345da28c26be6`
- **Commit Date:** `2026-05-05T15:03:23Z`
- **Metadata File:** [UPSTREAM.json](UPSTREAM.json)
- **Machine-Readable Inventory:** [license_inventory.json](license_inventory.json)

## License Overview

All vendored upstream assets for the Russian language module in LanguageTool are licensed under the **GNU Lesser General Public License v2.1 or later (LGPL-2.1-or-later)**.

### Component Breakdown

| Component / Subdirectory | Provenance / Upstream Origin | License | Status | Notes |
|---|---|---|---|---|
| `languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/` (`grammar.xml`, `bitext.xml`, etc.) | LanguageTool Project / Yakov Reztsov | LGPL-2.1-or-later | `VERIFIED_LGPL` | XML pattern rules and text replacement lists |
| `languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/` (`russian.dict`, `russian_synth.dict`, `tagset.txt`, wordlists, etc.) | AOT.ru (Alexey Sokirko) / Yakov Reztsov / LanguageTool | LGPL-2.1-or-later | `VERIFIED_LGPL` | Morfologik FSA dictionaries and Russian linguistic data |
| `languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/hunspell/` (`ru_RU.dict`, `ru_RU_yo.dict`, wordlists) | AOT.ru / Yakov Reztsov | LGPL-2.1-or-later | `VERIFIED_LGPL` | Russian spell-checking Morfologik dictionaries and frequency data |
| `languagetool-language-modules/ru/src/main/java/` (Java rules, filters, tokenizers, taggers) | LanguageTool Project | LGPL-2.1-or-later | `VERIFIED_LGPL` | Reference Java implementations for Russian rules & filters |
| `languagetool-language-modules/ru/src/test/java/` (JUnit tests) | LanguageTool Project | LGPL-2.1-or-later | `VERIFIED_LGPL` | Upstream test cases for conformance verification |
| `languagetool-core/src/main/resources/org/languagetool/resource/segment.srx` | LanguageTool Project | LGPL-2.1-or-later | `VERIFIED_LGPL` | SRX sentence segmentation definitions |
| `languagetool-core/src/main/resources/org/languagetool/resource/spelling_global.txt` | LanguageTool Project | LGPL-2.1-or-later | `VERIFIED_LGPL` | Globally accepted spellings loaded by `SpellingCheckRule` for every language |
| `languagetool-core/src/main/java/org/languagetool/rules/` and `.../rules/spelling/` | LanguageTool Project | LGPL-2.1-or-later | `VERIFIED_LGPL` | Generic rule and spelling base classes inherited by the Russian rules |
| `COPYING.txt` | Free Software Foundation | LGPL-2.1 | `VERIFIED_LGPL` | Upstream license text |

## Review & Verification Findings

- Total vendored files: **155**
- Verified LGPL files: **155**
- Files with unclear license / blocked items: **0** (`BLOCKED_LICENSE_REVIEW` count: 0)

All Russian dictionary files include explicit upstream provenance declarations (`README.txt` files citing `www.aot.ru` / `github.com/sokirko74/aot` under LGPL).
All Java source files include standard LGPL v2.1+ license headers.
XML rule files are covered under the overall LanguageTool LGPL-2.1-or-later distribution license.

## Related Third-Party Trees

`morfologik-stemming` 2.1.9 — the speller and dictionary-metadata implementation
LanguageTool 6.8 depends on — is vendored separately under
[`third_party/morfologik/`](../morfologik/) because it is **BSD-3-Clause**, not LGPL.
See `third_party/morfologik/UPSTREAM.json` and
`third_party/morfologik/license_inventory.json`.
