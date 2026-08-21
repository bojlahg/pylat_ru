# pylat_ru

`pylat_ru` is a native Python implementation of the Russian checking pipeline and
rule engine used by LanguageTool. Production use requires no Java/JRE, LanguageTool
server, network service, Natasha, or pymorphy.

The ordinary (non-language-model) Russian pipeline has full observable parity on the
committed upstream and differential evidence suites for LanguageTool 6.8, pinned at
`e807fcde6a6506191e1470744d2345da28c26be6`. This is deliberately narrower than a
claim of compatibility with every LanguageTool feature:
`RussianConfusionProbabilityRule` remains `LANGUAGE_MODEL_DEFERRED` because it depends
on LanguageTool's language-model subsystem.

`pylat_ru` is an independent project and is not affiliated with or endorsed by
LanguageTool.

## Installation

Install the first public alpha from PyPI:

```bash
python -m pip install pylat-ru==0.1.0a0
```

To opt into the newest prerelease, use `python -m pip install --pre pylat-ru`.
For source development, use `python -m pip install -e ".[dev,release]"`. The only
production dependency is `regex`; build, test, and release tools are optional.

## Basic usage

```python
from pylat_ru import LanguageToolRU

tool = LanguageToolRU()
for match in tool.check("Ученик решил задать тест учителю."):
    print(match.rule_id, match.message)
    print(match.offset, match.length, list(match.replacements))
```

The stable primary API is `LanguageToolRU`, `RuleMatch`, and `__version__`.
`LEVEL_DEFAULT` and `LEVEL_PICKY` are stable convenience constants. Existing exported
tokenization, analysis, tagging, disambiguation, and synthesis classes remain available
as an advanced/provisional surface; they do not yet carry the same stability promise.

## Checking levels and rule control

`check()` uses `DEFAULT` unless asked for `PICKY`. Unknown levels fail explicitly.

```python
from pylat_ru import LanguageToolRU, LEVEL_DEFAULT, LEVEL_PICKY

tool = LanguageToolRU(rule_config={"TOO_LONG_SENTENCE": {"maxWords": 4}})
text = "Один два три четыре пять."
assert not tool.check(text, level=LEVEL_DEFAULT)
assert any(m.rule_id == "TOO_LONG_SENTENCE" for m in tool.check(text, level=LEVEL_PICKY))
```

Rules can be enabled or disabled by their LanguageTool ID:

```python
from pylat_ru import LanguageToolRU

enabled = LanguageToolRU(enabled_rules=["MORFOLOGIK_RULE_RU_RU_YO"])
assert any(m.rule_id == "MORFOLOGIK_RULE_RU_RU_YO" for m in enabled.check("Ежик и елка."))

disabled = LanguageToolRU(disabled_rules=["zadat_test"])
assert not any(m.rule_id == "zadat_test" for m in disabled.check("Ученик решил задать тест учителю."))
```

`rule_config` is validated and unknown rule IDs or option names fail explicitly. A
supported spelling example is
`{"MORFOLOGIK_RULE_RU_RU": {"conf_ru_Value": 1}}`; a supported length example is
shown above.

## Match fields and offsets

The primary `RuleMatch` fields are `rule_id`, `category_id`, `message`, `offset`,
`length`, and `replacements`. Suggestions are ordered and both order and duplicates
are meaningful. `rule_id` is the base upstream ID; `full_rule_id` identifies the
physical variant where upstream exposes one. Additional metadata fields are retained
in the [public API snapshot](compat/public_api_0015.json).

`offset` and `length` are Python Unicode code-point indices into the original input and
can be used for normal Python slicing. `utf16_offset` and `utf16_length` are UTF-16
code-unit coordinates for interoperability with Java LanguageTool and UTF-16 clients.

## Errors, compatibility, and updating upstream

Missing or corrupt packaged resources fail during initialization/use; there is no
network or repository fallback for an installed wheel. Unknown checking levels and
configuration keys raise explicit exceptions. Compatibility evidence lives under
`compat/`, and the controlled pin update process is documented in
[docs/upstream_update.md](docs/upstream_update.md).

## License and provenance

Project code is licensed under [LGPL-2.1-or-later](LICENSE). Shipped LanguageTool-derived
rules, dictionaries, and other resources retain their upstream attribution. See
[LICENSES.md](third_party/languagetool/LICENSES.md) and
[license_inventory.json](third_party/languagetool/license_inventory.json) for the
recorded evidence; no unresolved `BLOCKED_LICENSE_REVIEW` resource is intentionally
shipped.
