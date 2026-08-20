# Task 0012 — Russian Spelling, Compounds, Replace, Coherency, Repetitions, and Final XML Filter

## 1. Identity

| Field | Value |
| --- | --- |
| Baseline SHA (Task 0011 accepted) | `663ca3e222d694b92074f0b87da86c5e566f4bd4` |
| Final implementation SHA | single implementation commit on `main`; the exact SHA is recorded in the Task-0012 handoff (a commit cannot contain its own hash) |
| Pinned LanguageTool commit | `e807fcde6a6506191e1470744d2345da28c26be6` (v6.8) |
| Pinned Morfologik | `morfologik-stemming` 2.1.9 |
| Trusted Java oracle build | `lt_6.8_source_build_jdk17_stefan` (`b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc`) |

Production execution remains fully Python-native: no JRE, no LanguageTool server,
no Java subprocess, no localhost oracle, no runtime download, no external spell
service, no Natasha/pymorphy substitution. Java LanguageTool is used only as a
development/test oracle behind `tools/`.

---

## 2. Rule inventory and accounting

```text
ordinary relevant Java rules total               23
implemented                                      23
deferred ordinary Java rules                      0

generic                                          10 / 10
Russian-specific                                 13 / 13

language-model rules implemented                  0 / 1
RussianConfusionProbabilityRule = LANGUAGE_MODEL_DEFERRED

Russian XML filters                               7 / 7
recognized deferred XML filters                   0
```

The eight rules implemented by this task:

| Registration order | Class | Rule ID | Category | Default |
| ---: | --- | --- | --- | --- |
| 2 | `MorfologikRussianSpellerRule` | `MORFOLOGIK_RULE_RU_RU` | TYPOS | ON |
| 12 | `MorfologikRussianYOSpellerRule` | `MORFOLOGIK_RULE_RU_RU_YO` | TYPOS | OFF |
| 14 | `RussianCompoundRule` | `RU_COMPOUNDS` | MISC | ON |
| 15 | `RussianSimpleReplaceRule` | `RU_SIMPLE_REPLACE` | MISC | ON |
| 16 | `RussianSimpleWordRepeatRule` | `WORD_REPEAT_RULE` | MISC | ON |
| 17 | `RussianWordCoherencyRule` | `RU_WORD_COHERENCY` | MISC | ON |
| 18 | `RussianWordRepeatRule` | `RU_WORD_REPEAT` | MISC | OFF |
| 19 | `RussianWordRootRepeatRule` | `RU_WORD_ROOT_REPEAT` | MISC | OFF |

`RUSSIAN_RULE_CLASSES` in `src/pylat_ru/native_rules.py` now reproduces the exact
23-entry order of `Russian.getRelevantRules()`; registration order, category id,
category name, description and default state were re-read from the pinned source
and re-verified against `JavaRulesOracle0012 --metadata`.

### 2.1 Effective priority table

| Rule ID | Configured key in `Russian.java` | Configured value | Effective priority | Binding |
| --- | --- | ---: | ---: | --- |
| `RU_DASH_RULE` | `RU_DASH_RULE` | 12 | 12 | BOUND |
| `RU_COMPOUNDS` | `RU_COMPOUNDS` | 11 | 11 | BOUND |
| `RU_SIMPLE_REPLACE` | `RUSSIAN_SIMPLE_REPLACE_RULE` | 10 | 0 | ORPHAN_OVERRIDE_ID |
| `RU_SPECIFIC_CASE` | `RUSSIAN_SPECIFIC_CASE` | 9 | 0 | ORPHAN_OVERRIDE_ID |
| `MORFOLOGIK_RULE_RU_RU_YO` | `MORFOLOGIC_RULE_RU_RU_YO` | 2 | 0 | ORPHAN_OVERRIDE_ID |
| `MORFOLOGIK_RULE_RU_RU` | `MORFOLOGIC_RULE_RU_RU` | 1 | 0 | ORPHAN_OVERRIDE_ID |
| `RU_WORD_ROOT_REPEAT` | `Word_root_repeat` | -1 | 0 | ORPHAN_OVERRIDE_ID |
| `PUNCTUATION_PARAGRAPH_END2` | `PUNCT_DPT_2` | -2 | 0 | ORPHAN_OVERRIDE_ID |
| `TOO_LONG_PARAGRAPH` | `TOO_LONG_PARAGRAPH` | -15 | -15 | BOUND |

The upstream key/ID mismatches are preserved, not "fixed". Verified against
`language.getRulePriority(rule)` for all 23 rules through the Java probe.

---

## 3. Spelling architecture

```text
resources/ru/hunspell/ru_RU.dict + .info
              │
      morfologik CFSA2 reader (existing Task-0002 FSA infrastructure)
              │
  pylat_ru.morfologik.speller.Speller     ← port of morfologik.speller.Speller 2.1.9
   (Oflazer error-tolerant FSA search, cut-off edit distance band,
    replacement pairs, run-on words, frequency-weighted candidate order)
              │
  pylat_ru.spelling.MorfologikSpeller     ← LT MorfologikSpeller (case normalisation)
              │
  pylat_ru.spelling.MorfologikMultiSpeller← binary dict + runtime plain-text dict
              │
  pylat_ru.spelling.RussianSpellerRuleBase← SpellingCheckRule + MorfologikSpellerRule
              │
  RussianSpeller / RussianYoSpeller       ← the two registered Russian leaf rules
```

Key points:

* No `word not in dictionary` shortcut and no Levenshtein loop over the dictionary.
  Candidates come from a depth-first FSA walk bounded by Oflazer's cut-off edit
  distance, exactly as in the pinned `Speller.findRepl`.
* The existing Morfologik FSA reader, metadata parser and sequence decoder are
  reused; no second FSA implementation was introduced for the binary dictionary.
* `spelling.txt` + `spelling_global.txt` are compiled into a deterministic trie
  automaton (`TrieFSA`) whose arcs are in ascending unsigned-label order, which is
  the traversal order the serialized automaton built by `FSABuilder` from lexically
  sorted input exposes.
* Dictionaries are read once per process and shared between rule instances; the
  decoded per-node arc table is cached on the dictionary object, so LanguageTool's
  "fresh `Speller` per suggestion request" behaviour is preserved without re-decoding
  the automaton.
* Speller edit distances 1/2/3 are separate `MorfologikMultiSpeller` instances,
  invoked under the pinned escalation rule (distance 2 only when the distance-1
  result is empty or differs only in case, distance 3 only for words of length ≥ 5
  with no result at all).

### 3.1 Dictionary metadata

`src/pylat_ru/morfologik/metadata.py` previously used non-upstream attribute names.
It now reads the exact Morfologik property names, including the speller namespace:

```text
fsa.dict.separator, fsa.dict.encoding, fsa.dict.encoder, fsa.dict.frequency-included,
fsa.dict.speller.ignore-punctuation, fsa.dict.speller.ignore-numbers,
fsa.dict.speller.ignore-camel-case, fsa.dict.speller.ignore-all-uppercase,
fsa.dict.speller.ignore-diacritics, fsa.dict.speller.convert-case,
fsa.dict.speller.runon-words, fsa.dict.speller.locale,
fsa.dict.speller.replacement-pairs, fsa.dict.speller.equivalent-chars,
fsa.dict.input-conversion, fsa.dict.output-conversion
```

Effective state for `ru_RU.info` / `ru_RU_yo.info`:

| Attribute | Value | Source |
| --- | --- | --- |
| encoding | `koi8-r` | declared |
| separator | `+` | declared |
| encoder | `SUFFIX` | declared |
| frequency-included | true | declared |
| speller.runon-words | true | declared |
| speller.ignore-diacritics | false | declared |
| speller.replacement-pairs | 19 source keys / 22 pairs | declared |
| speller.convert-case | true | Morfologik default |
| speller.ignore-punctuation / -numbers / -camel-case / -all-uppercase | true | Morfologik default |
| speller.equivalent-chars | empty | Morfologik default |

### 3.2 `conf_ru_Value` semantics

`MorfologikRussianSpellerRule` and the YO rule both read a single integer
`UserConfig` value, default `0`, exposed publicly as
`rule_config={"MORFOLOGIK_RULE_RU_RU": {"conf_ru_Value": n}}`.

Observed Java behaviour (probed with -1, 0, 1, 2):

* `conf_ru_Value != 1` → tokens that do not fully match the Russian-letter pattern
  are skipped by `ignoreToken`.
* `conf_ru_Value == 1` → those tokens are checked.
* `-1` and `2` are accepted at construction time and behave like `0`; the
  `RuleOption(0, 1)` bounds are UI metadata only and are **not** runtime validation.
  This was measured, not inferred.
* The config only affects `ignoreToken`; the direct `isMisspelled(String)` query is
  unaffected by it, which the direct-speller oracle cases record explicitly.

The Russian-letter pattern was traced character by character out of the pinned
source. Its members are: `-`, `а-я`, `ё`, U+0301 combining acute, U+0300 combining
grave, `ѝ` (U+045D), `ʼ` (U+02BC), `А-Я`, `Ё`.

### 3.3 NOSUGGEST filtering

`filterNoSuggestWords` removes replacements whose lowercase form is in the leaf
rule's set. This is *suggestion* filtering only and is deliberately distinct from
"the dictionary accepts this word":

| Rule | Never-suggest set | `isMisspelled("блогер")` |
| --- | --- | --- |
| `MORFOLOGIK_RULE_RU_RU` | блоггер, дрочим, анальный, орочем | false (accepted) |
| `MORFOLOGIK_RULE_RU_RU_YO` | блоггер, елка, дрочим, анальный, орочем | — |

Both facts are asserted by fixtures generated from Java.

### 3.4 YO speller

Uses `/ru/hunspell/ru_RU_yo.dict`, is `setDefaultOff()`, carries its own
description ("Проверка орфографии. Только «Ё» (экспериментальное правило).") and
its own never-suggest set. The dictionary difference is real and observable:
`ежик` is accepted by the ordinary speller and rejected by the YO speller, while
`Ростов-на-дону` is rejected by the ordinary speller and *accepted* by the YO
dictionary (the upstream test documents this as a dictionary mistake and disables
that assertion). No `е → ё` rewriting is applied; everything is dictionary-driven.

### 3.5 Transitive resource discovery

The leaf inventory was not sufficient. `SpellingCheckRule.getAdditionalSpellingFileNames()`
reaches `spelling_global.txt`, which ships in `languagetool-core.jar`, not in the
Russian module. Without it, Java suggests `Ford`/`Word` for `wordd` and Python
suggested nothing. It is now vendored and packaged.

`spelling_global.txt` also changes rule behaviour in a second way: every accepted
line the Russian word tokenizer splits into more than one token becomes an
`IGNORE_SPELLING` disambiguation antipattern (`SpellingCheckRule.addIgnoreWords`).
8 898 such phrase patterns exist at the pin (e.g. `Microsoft Entra`, and `log4j`,
which the tokenizer splits into `log` `4` `j`). `SpellerAntiPatternIndex` matches
them on the whitespace-free token list and marks the covered tokens as ignored by
the speller, which is what `Rule.getSentenceWithImmunization` achieves upstream.

---

## 4. Compound, replace, repetition and coherency behaviour

* **`RU_COMPOUNDS`** — full port of `AbstractCompoundRule` + `CompoundRuleData`.
  `/ru/compounds.txt` loads to 26 472 incorrect compounds, 26 463 dash suggestions,
  10 joined suggestions, 0 lowercase-joined entries, no digit patterns. The rule
  sets `sentenceStartsWithUpperCase = true`, so a sentence-initial token is
  uncapitalized (`StringUtils.uncapitalize`) before lookup. All three message forms
  are produced. `isMisspelled` is not overridden by the Russian leaf, so
  `filterReplacements` only drops a replacement identical to the original text.
  `RussianDashRule`'s canonicalization is not reused.
* **`RU_SIMPLE_REPLACE`** — full port of `AbstractSimpleReplaceRule2`
  (case-insensitive, phrase-capable, longest-match-wins, `$match`/`$suggestions`
  message expansion, sentence-start and ALL-CAPS suggestion adaptation, tab-separated
  per-entry messages, `|`-separated alternatives). `/ru/replace.txt` is parsed with
  the upstream format checks, not turned into a `str.replace()` map.
* **`WORD_REPEAT_RULE`** — port of `WordRepeatRule` plus the Russian `ignore()`
  overrides (`-`, `и`, `по`, `ПО по`, `по ПО`, `что`, single-letter spelling, and the
  inherited proper-name list).
* **`RU_WORD_COHERENCY`** / **`RU_WORD_ROOT_REPEAT`** — text-level ports of
  `AbstractWordCoherencyRule` + `WordCoherencyDataLoader` over `/ru/coherency.txt`
  and `/ru/wordrootrep.txt`. `AbstractWordCoherencyRule` iterates a
  `Collectors.toSet()` result, so which base form is inspected first depends on
  `java.util.HashSet` bucket order; `java_hash_set_order()` reproduces that order
  from `String.hashCode`, the HashMap hash spread and the table capacity rather than
  guessing insertion order.
* **`RU_WORD_REPEAT`** — port of `AdvancedWordRepeatRule` with the Russian excluded
  word set, excluded POS pattern and excluded non-word pattern. It is not collapsed
  into `WORD_REPEAT_RULE`.

---

## 5. Final XML filter and `suppress_misspelled`

`RussianSuppressMisspelledSuggestionsFilter` is implemented on
`AbstractSuppressMisspelledSuggestionsFilter` semantics:

1. required `suppressMatch` argument, optional `SuppressPostag` (exact spelling and
   case — `suppresspostag` is *not* read, which is asserted);
2. each replacement is tokenized with the Russian word tokenizer and is misspelled
   if **any** token is misspelled by the language's default spelling rule;
3. misspelled replacements are discarded; with `SuppressPostag` the replacements
   whose tag matches the regex are discarded as well;
4. suppression is active unless `suppressMatch` equals `false` ignoring case;
5. when nothing survives and suppression is active the whole match is dropped,
   otherwise the match is returned with the filtered replacement list.

The filter uses the native Task-0012 default speller
(`pylat_ru.spelling.get_default_spelling_rule()`), which is the equivalent of
`Russian.getDefaultSpellingRule()`: a `MorfologikRussianSpellerRule` built with a
null `UserConfig`, therefore always `conf_ru_Value = 0`. It is a single shared
instance over immutable dictionaries, so no per-suggestion speller is constructed
and no mutable state leaks between checks.

The `suppress_misspelled` attribute on `<message>`/`<suggestion>` is a **separate**
mechanism: `PatternRuleHandler` injects `<pleasespellme/>` markers, `MatchState`
replaces a synthesized form the *tagger* does not recognise with `<mistake/>` (or
`(token)` when synthesis produced nothing), and
`PatternRuleMatcher.removeSuppressMisspelled` deletes the affected
`<suggestion>…</suggestion>` blocks. If a rule-level suppressed message ends up with
no suggestion at all, no rule match is created. All of this is now implemented in
`TemplateFormatter.format_message` and `RussianGrammarEngine._execute_rule`.

While wiring this up, `MatchState.getTargetPosTag` turned out to be mis-ported in
the Task-0008 formatter: it used `search`-or-`fullmatch` against a reading's POS tag
where Java uses `Matcher.matches()`, took only the first matching reading, and did
not synthesize over all readings into a sorted set. That is now a faithful port
(full match only, `getTargetPosTag` fallback, `|`-joined replaced tags,
`setpos` correction, `TreeSet` result). All 2 446 grammar examples pass with the
corrected implementation.

---

## 6. XML grammar promotion

Baseline blockers, re-derived from the pinned grammar:

```text
message@suppress_misspelled                      111 rules
suggestion@suppress_misspelled                     2 rules
filter:RussianSuppressMisspelledSuggestionsFilter   1 rule
                                                 ---
deferred source rules                            114
deferred embedded examples                       327
```

Every one of them was blocked solely by a Task-0012 dependency, so implementing the
filter, the `suppress_misspelled` markup and native spelling promotes all of them.

Accepted Task-0012 accounting:

```text
grammar source rules total                       892
runnable source rules                            892
deferred source rules                              0
unknown source rules                               0

grammar examples total                          2446
runnable examples                               2446
deferred examples                                  0

compiled physical variants total                 907
runnable compiled variants                       907
```

Execution is proven, not asserted: `tests/upstream/test_russian_grammar_examples.py`
runs every incorrect example (must trigger) and every correct example (must not
trigger) across all 892 runnable rules.

Post-promotion classification: 506 core, 339 advanced, 24 unification, 23 filter.

---

## 7. Upstream test inventory

| Test file | `@Test` methods | Use |
| --- | ---: | --- |
| `MorfologikRussianSpellerRuleTest.java` | 1 | translated (7 assertions) |
| `MorfologikRussianYOSpellerRuleTest.java` | 1 | translated (6 assertions; 1 upstream assertion is commented out as a dictionary mistake) |
| `RussianCompoundRuleTest.java` | 2 | translated (19 `check()` scenarios) |
| `RussianSimpleReplaceRuleTest.java` | 1 | translated (5 assertions) |
| `RussianWordCoherencyRuleTest.java` | 3 | translated (8 assertions incl. full-pipeline texts) |
| `RussianWordRepeatRuleTest.java` | 1 | translated (2 assertions) |
| `LanguageSpecificSpellcheckerTest.java` | 1 | inspected — generic, no Russian-specific assertions |

Inherited base classes inspected and bound (vendored with hashes in
`third_party/languagetool/UPSTREAM.json`): `MorfologikSpellerRule`,
`MorfologikMultiSpeller`, `MorfologikSpeller`, `WeightedSuggestion`,
`SpellingCheckRule`, `CachingWordListLoader`, `SuggestedReplacement`,
`AbstractCompoundRule`, `CompoundRuleData`, `AbstractSimpleReplaceRule2`,
`WordRepeatRule`, `AdvancedWordRepeatRule`, `AbstractWordCoherencyRule`,
`WordCoherencyDataLoader`, `AbstractSuppressMisspelledSuggestionsFilter`, plus
`morfologik.speller.Speller`, `morfologik.speller.HMatrix`,
`morfologik.stemming.DictionaryMetadata`, `DictionaryAttribute` and
`DictionaryLookup`.

```text
upstream test files inventoried                   18
Task-0012 direct test files                        6
@Test methods in those files                       9
direct assertions translated                      47
oracle-only controlled scenarios                 104
rules without a dedicated upstream test            2
  RussianSimpleWordRepeatRule  (WORD_REPEAT_RULE)
  RussianWordRootRepeatRule    (RU_WORD_ROOT_REPEAT)
```

Both rules without a dedicated upstream test are covered exclusively by controlled
Java-oracle scenarios (15 and 5 cases respectively), never by locally invented
expectations.

---

## 8. Java oracle evidence

| Fixture | Cases | Mode |
| --- | ---: | --- |
| `tests/fixtures/oracle_java_rules_0012_spelling.json` | 59 | 41 direct speller queries + 18 single-rule checks |
| `tests/fixtures/oracle_java_rules_0012_rules.json` | 67 | single-rule checks for the six non-spelling classes |
| `tests/fixtures/oracle_java_rules_0012_filter.json` | 10 | real `grammar.xml` rules using the filter / `suppress_misspelled` |
| `tests/fixtures/oracle_java_rules_0012_combined.json` | 15 | full `JLanguageTool.check` with all 23 ordinary rules at pinned defaults |
| **Total** | **151** | |

```text
semantic signatures            151 / 151 unique
coverage metadata              fail-closed, validated against the Java result
LF-only deterministic bytes    yes
manifest size/sha bindings     exact (compat/oracle_manifest.json)
```

Semantic signatures depend only on execution mode, rule class, rule id, text,
config, explicit enable/disable state and raw-query mode — never on case id,
coverage labels, expected result, finding count or the stored signature.

The spelling corpus covers correct/misspelled Cyrillic, multiple misspellings,
sentence-start capitalization, title case, ALL CAPS, mixed case, ё/е, combining
acute, combining grave, modifier apostrophe, hyphenated forms, digits, punctuation,
Latin and mixed-script tokens at `conf_ru_Value` 0/1/-1/2, URLs, e-mails,
`spelling.txt` additions, `spelling_global.txt` phrases, ignore/prohibit resources,
NOSUGGEST filtering, empty and multi-suggestion results with exact ordering, and a
non-BMP prefix before the error.

Beyond the committed fixtures, the port was validated during development against
720 additional Java speller queries (dictionary samples plus systematic
substitution/deletion/insertion/transposition corruptions) with **0** mismatches in
both the misspelled verdict and the full ordered suggestion list.

---

## 9. Combined pipeline

The Task-0011 cleanup sequence is unchanged:

```text
SameRuleGroupFilter → Russian language-dependent match filter
                    → CleanOverlappingFilter → Russian post-overlap filter
```

The 15 combined cases exercise `RU_COMPOUNDS` priority 11 against overlapping
matches, spelling versus XML grammar overlap, simple-replace versus spelling,
word-repeat versus spelling, default-off YO versus the ordinary speller, the two
default-off repetition rules with and without explicit enablement, a
filter-suppressed XML match beside a surviving spelling finding, dash priority
versus spelling at the same offset, and non-BMP offsets. Each case compares the
final ordered findings, the pre-overlap findings, and the per-rule raw findings.

Java oracle runs for the combined fixtures disable nothing — the language-model rule
is simply not part of `getRelevantRules()`.

---

## 10. Resource integrity and provenance

All runtime resources are byte-identical to the pinned upstream files, and the
packaged copy is verified against the vendored copy by test:

| upstream path | bytes | SHA-256 | packaged as |
| --- | ---: | --- | --- |
| `/ru/hunspell/ru_RU.dict` | 1889147 | `10c3acd195935a589d3baebe8de4a829def7d19ee4d0613664196795fe91403f` | `resources/ru/hunspell/ru_RU.dict` |
| `/ru/hunspell/ru_RU.info` | 1078 | `1d6a66af2b3c1812c44d03d2b8d27e6f407e8c99b071956a82296c600679f6a4` | `resources/ru/hunspell/ru_RU.info` |
| `/ru/hunspell/ru_RU_yo.dict` | 1783672 | `215cc717920e814a40702f65c2aa3c8e4598fd8f41004140aa00cf1a4893434b` | `resources/ru/hunspell/ru_RU_yo.dict` |
| `/ru/hunspell/ru_RU_yo.info` | 1086 | `956e5db4022ffe4b989ac841ab30b33781867b6a1f20905e40bca83c81650573` | `resources/ru/hunspell/ru_RU_yo.info` |
| `/ru/hunspell/spelling.txt` | 39687 | `964c4bb256ebe8170c4df7e91cea6c66a5717a3ad984debe321f4d65f6a268d7` | `resources/ru/hunspell/spelling.txt` |
| `/ru/hunspell/ignore.txt` | 72 | `0561df4242ce2d6c6768cb57a0be7822ffda7c3e5991c8664aef7da05351f616` | `resources/ru/hunspell/ignore.txt` |
| `/ru/hunspell/prohibit.txt` | 868 | `fb56a59b07d43fc0543e6e39d845cfc0d2674438bde628efca7fba93b4f1bcae` | `resources/ru/hunspell/prohibit.txt` |
| `spelling_global.txt` | 454892 | `5d60620185f07c751eff8dfcee31ebc7071fbb945fdb0d4502594de21ca4a4df` | `resources/spelling_global.txt` |
| `/ru/compounds.txt` | 899551 | `71b4217689cf83c07eb88b4f4b5c9c5e482171a053b48fa93e1cd1c14e8e720a` | `resources/ru/compounds.txt` |
| `/ru/replace.txt` | 13485 | `38bfd8fc096dd0581d4213847c39ee51bc9b5ef3f63b9663900de8da2b091829` | `resources/rules/ru/replace.txt` |
| `/ru/coherency.txt` | 987 | `f6b282c5da932fc5025ce068ba96261c24255d7b1cc8c95dd56d6dd400167bd2` | `resources/rules/ru/coherency.txt` |
| `/ru/wordrootrep.txt` | 565589 | `a6c59703ddf81ae0bb8b1525455e48b055ca4865b351f279a7bb324499a239d5` | `resources/rules/ru/wordrootrep.txt` |
| `/ru/specific_case.txt` | 915 | `c35d08b0909b45acf242621961e2dbf0148792b70e4696be40248ad952c50966` | `resources/ru/specific_case.txt` |

No dictionary was regenerated; the pinned `.dict` bytes are used as shipped.

Licensing/provenance:

* `third_party/languagetool/UPSTREAM.json` — 155 vendored files (was 140); all new
  Java sources and resources recorded with size and SHA-256.
* `third_party/languagetool/license_inventory.json` — 155 items, all
  `VERIFIED_LGPL`, `BLOCKED_LICENSE_REVIEW = 0`.
* `third_party/morfologik/` — new tree with `UPSTREAM.json` and
  `license_inventory.json` for the 6 vendored `morfologik-stemming` 2.1.9 files
  (BSD-3-Clause, recorded separately from the LGPL LanguageTool material).

---

## 11. Public configuration surface

```python
LanguageToolRU(rule_config={"MORFOLOGIK_RULE_RU_RU": {"conf_ru_Value": 1}})
```

* Public keys are the **actual** rule IDs.
* Unknown rule IDs and unknown option keys raise `KeyError`; a non-integer value
  raises `TypeError`.
* Configuration for one rule never reaches another (asserted for the two spellers).
* `AbstractCompoundRule` reads `UserConfig.getLinguServices()` only, which is a
  LibreOffice/OpenOffice extension hook with no reachable equivalent here, so
  `RU_COMPOUNDS` exposes no configuration. No other Task-0012 rule reads `UserConfig`.

---

## 12. Performance and memory

| Scenario | Measurement |
| --- | --- |
| Speller initialisation (dictionaries + word lists + antipatterns) | ~0.6 s, once per process |
| 400 correct words | ~0.01 s |
| Repeated identical check | cached, sub-millisecond |
| Suggestion generation, distance 1 | ~0.02 s |
| Suggestion generation, distance 2 | ~0.1–0.3 s |
| Suggestion generation, distance 3 (worst case) | ~0.8–1.4 s |
| Full `LanguageToolRU.check` of a 5-sentence paragraph | ~0.3 s |

Guarantees asserted by `tests/unit/test_spelling_performance.py`: the binary
dictionary is loaded once and shared, there is no dictionary scan per token, the
default-suggestion cache is capped at 2 000 entries, per-rule speller state does not
leak across configurations, and `check()` runs without touching `subprocess` or
`socket`. Observable suggestion semantics were not traded for speed — the optimized
run reproduces the same 720/720 Java results as the unoptimized one.

---

## 13. Tests

New:

* `tests/unit/test_morfologik_speller.py` — Speller/TrieFSA/HMatrix/metadata port
* `tests/unit/test_java_rules_0012.py` — registration, defaults, config, rule behaviour
* `tests/unit/test_java_rules_0012_inventory.py` — accounting, resource hashes, fixture integrity
* `tests/unit/test_grammar_promotion_0012.py` — deferred-XML promotion accounting
* `tests/unit/test_suppress_misspelled_filter.py` — filter + `suppress_misspelled` markup
* `tests/unit/test_spelling_performance.py` — performance/resource-safety guards
* `tests/upstream/test_java_rules_0012_oracle_parity.py` — 136 oracle parity cases
* `tests/upstream/test_java_rules_0012_combined_oracle_parity.py` — 15 combined cases
* `tests/upstream/test_java_rules_0012_upstream_tests.py` — translated JUnit tests

Extended: `tests/unit/test_real_wheel_grammar.py` (wheel contents + Task-0012
execution from the installed wheel).

Accounting assertions updated to the Task-0012 state (no test was weakened or
removed): grammar classification counts, runnable rule/variant/example counts,
vendored-file counts, the Task-0011 inventory accounting slice, and the Task-0011
combined-pipeline parity test, which now explicitly disables the eight rules that
were disabled in Java when its fixture was generated.

```text
python -m pytest -q
760 passed / 0 failed / 0 errors / 0 skipped
```

---

## 14. Wheel isolation

`pip wheel` → `pip install --target` → clean subprocess with the repository `src`
removed from `sys.path`, `JAVA_HOME` unset, `PATH` reduced to an empty directory,
and `socket.socket` / `subprocess.run` / `subprocess.Popen` replaced by raising
stubs. From the installed wheel only, the test proves:

* an ordinary Russian spelling error with the exact offset, length, message, short
  message and ordered suggestion list;
* a correct sentence producing no spelling finding;
* the YO speller silent by default and active when explicitly enabled;
* `RU_COMPOUNDS`, `RU_SIMPLE_REPLACE`, `WORD_REPEAT_RULE`, `RU_WORD_COHERENCY`;
* the `grammar.xml` rule that uses `RussianSuppressMisspelledSuggestionsFilter`;
* the Task-0011 Java rules and the existing XML grammar rules;
* every packaged spelling resource present in the wheel archive.

Result: **PASS**.

---

## 15. Known differences

1. **Dictionary locale.** `ru_RU.info` declares no `fsa.dict.speller.locale`, so
   Morfologik uses `Locale.getDefault()` for its case conversions. The port uses
   Python's default (root) casing. For the Cyrillic and Latin ranges present in the
   Russian dictionaries the two agree; a JVM running under a Turkish or Azeri locale
   would differ from both upstream-on-другой-locale and this port. No observable
   difference was found in any oracle case.
2. **Dictionary charset support.** The speller port implements the single-byte
   decoder path only. A dictionary declaring a multi-byte or partially mapped
   charset is refused with `UnsupportedEncodingError` instead of being approximated.
   Both pinned Russian dictionaries are `koi8-r`, so this is fail-closed, not a gap.
3. **Language-model rule.** `RussianConfusionProbabilityRule` remains explicitly
   deferred (0 / 1, `LANGUAGE_MODEL_DEFERRED`). It is not implemented or approximated.

No other differences from the pinned Java behaviour are known on the surfaces
covered above.

---

## 16. Definition of Done

| # | Requirement | Status |
| ---: | --- | --- |
| 1 | 8 remaining ordinary Java rules implemented natively | PASS |
| 2 | Ordinary relevant Java rules 23/23 | PASS |
| 3 | Russian-specific 13/13 | PASS |
| 4 | Generic 10/10 | PASS |
| 5 | `RussianSuppressMisspelledSuggestionsFilter` implemented | PASS |
| 6 | Russian XML filters 7/7 | PASS |
| 7 | Default Russian native speller available to XML filters | PASS |
| 8 | Pinned-compatible Morfologik spelling semantics | PASS |
| 9 | Suggestion order/filtering Java-oracle verified | PASS |
| 10 | YO speller semantics and default-off state verified | PASS |
| 11 | `RU_COMPOUNDS` effective priority 11 | PASS |
| 12 | Orphan priority-key mismatches faithfully represented | PASS |
| 13 | Positive/negative oracle coverage for all six non-spelling rules | PASS |
| 14 | Rules without upstream tests identified and oracle-covered | PASS |
| 15 | Task-0012 semantic queries unique | PASS (151/151) |
| 16 | Coverage metadata fail-closed and consistent with Java | PASS |
| 17 | All required resources packaged and hash-bound | PASS |
| 18 | Installed wheel runs spelling and the final XML filter with no Java/network/subprocess | PASS |
| 19 | 114 deferred XML source rules reconciled | PASS |
| 20 | Grammar rules 892/892 runnable | PASS |
| 21 | Examples 2446/2446 runnable | PASS |
| 22 | Compiled variants 907/907 runnable | PASS |
| 23 | Task-0011 oracle/combined tests green | PASS |
| 24 | Full pytest 0 failed / 0 errors / 0 skipped | PASS |
| 25 | Exact final SHA CI green on Python 3.10 and 3.12 | PASS — run ID, run URL, head SHA and per-job results are recorded in the Task-0012 handoff |
| 26 | `RussianConfusionProbabilityRule` deferred 0/1 | PASS |
| 27 | No Task 0013 work started | PASS |
