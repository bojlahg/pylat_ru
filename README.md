# pylat_ru

Native Python reimplementation of the Russian LanguageTool pipeline and rule engine.

> **Disclaimer**: `pylat_ru` is an independent project and is not affiliated with or endorsed by LanguageTool.

## Project Purpose & Scope

The goal of `pylat_ru` is to provide a reproducible, 100% native Python implementation of the Russian language checking pipeline used by LanguageTool.

- **Russian only**: Currently targets Russian (`ru-RU`).
- **No Java in production**: Does not require Java, JRE, LanguageTool CLI, or LanguageTool HTTP server in production.
- **No NLP shortcuts**: Does not substitute Natasha, pymorphy, or generic NLP models for LanguageTool's morphological dictionary, POS tagger, disambiguator, chunker, or synthesizer.
- **Upstream compatibility**: Rules and resources are executed with semantics matching LanguageTool at a pinned upstream revision.

## Status

`pylat_ru` is currently under active foundational development (Task 0001 complete).
**Parity status is incomplete** until the implementation milestones in the project roadmap are fulfilled and proven by conformance tests.

- Pinned upstream LanguageTool revision: `v6.8` (`e807fcde6a6506191e1470744d2345da28c26be6`).
- Working license: `LGPL-2.1-or-later`.

## Architecture Overview

```text
Input text
   ↓
RussianSentenceTokenizer (SRX segmentation)
   ↓
RussianWordTokenizer
   ↓
RussianTagger (Morfologik FSA / dictionary)
   ↓
RussianDisambiguator (disambiguation.xml)
   ↓
RussianChunker
   ↓
RussianRuleEngine
   ├─ grammar.xml pattern rules
   ├─ XML filters
   ├─ Java rule ports
   ├─ Spelling & compounds
   └─ Repetition / replace / coherency rules
   ↓
RussianSynthesizer (russian_synth.dict)
   ↓
Findings (rule_id, category, message, offset, length, suggestions)
```

## Installation (Development)

```bash
pip install -e ".[dev]"
```

## License

This project is licensed under the [GNU Lesser General Public License v2.1 or later (LGPL-2.1-or-later)](LICENSE).
Vendored upstream LanguageTool assets and dictionary data are documented in [LICENSES.md](third_party/languagetool/LICENSES.md) and [license_inventory.json](third_party/languagetool/license_inventory.json).
