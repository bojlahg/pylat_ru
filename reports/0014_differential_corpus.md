# Task 0014 — Differential Corpus and Full-Pipeline Compatibility Audit

## 0. Required elements

Where each of the twenty-five elements required by section 24 of the task
specification is answered. Some are subsections of section 16 rather than top-level
sections, which is why the top-level numbering skips 17 to 19.

| # | Required element | Section |
| --- | --- | --- |
| 1 | Task title and baseline SHA | 1 |
| 2 | Pinned LT commit | 2 |
| 3 | Trusted oracle build ID and SHA | 3 |
| 4 | Exact files changed | 4 |
| 5 | Comparator defects found/fixed | 5, 14 |
| 6 | Batch-oracle architecture | 7 |
| 7 | Corpus strata and provenance | 8 |
| 8 | Exact corpus counts | 10 |
| 9 | Exact profile counts | 11 |
| 10 | Exact initial mismatch count | 12 |
| 11 | Mismatch categories | 12 |
| 12 | Minimized mismatch count | 12 |
| 13 | Production bugs discovered | 13 |
| 14 | Harness/comparator bugs discovered | 14 |
| 15 | Fixes made | 13, 14 |
| 16 | Final differential metrics | 16 |
| 17 | Suggestion-order metrics | 16.2 |
| 18 | UTF-16/non-BMP metrics | 6, 16.3 |
| 19 | Rule-ID occurrence/mismatch summary | 16.4 |
| 20 | External corpus hash/provenance | 9 |
| 21 | Regression fixture count/hash | 16.6 |
| 22 | Full pytest result | 22 |
| 23 | Wheel-isolation result | 21 |
| 24 | Known differences | 15 |
| 25 | Task 0015 not started | 24 |

## 1. Task and baseline

| Item | Value |
| --- | --- |
| Task | 0014 — Differential Corpus and Full-Pipeline Compatibility Audit |
| Baseline SHA | `abe5290d5c2e8e613937e180c7669638ff56b6af` (accepted Task-0013 final) |
| Working tree at start | clean except the untracked task specification |

## 2. Pinned upstream

| Item | Value |
| --- | --- |
| Repository | `https://github.com/languagetool-org/languagetool.git` |
| Tag | `v6.8` |
| Commit | `e807fcde6a6506191e1470744d2345da28c26be6` |

## 3. Trusted Java oracle

| Item | Value |
| --- | --- |
| Build id | `lt_6.8_source_build_jdk17_stefan` |
| Jar | `languagetool-commandline.jar` |
| SHA-256 | `b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc` |
| Binding | `compat/oracle_manifest.json` |

The jar SHA-256 was re-verified before every campaign run; `BatchJavaOracle.start()`
calls `JavaLanguageToolOracle.validate_oracle()` and refuses to run otherwise.

## 4. Files changed

| Status | Path |
| --- | --- |
| modified | `compat/compatibility.json` |
| modified | `compat/oracle_manifest.json` |
| modified | `src/pylat_ru/__init__.py` |
| modified | `src/pylat_ru/disambiguation/pattern_matcher.py` |
| modified | `src/pylat_ru/grammar/engine.py` |
| modified | `src/pylat_ru/grammar/formatter.py` |
| modified | `src/pylat_ru/grammar/loader.py` |
| modified | `src/pylat_ru/match_filters.py` |
| modified | `src/pylat_ru/native_rules.py` |
| modified | `src/pylat_ru/tagging/string_tools.py` |
| modified | `src/pylat_ru/tokenization/srx.py` |
| modified | `tests/unit/test_disambiguation_rules.py` |
| modified | `tests/unit/test_java_rules_0011.py` |
| modified | `tools/differential_lt.py` |
| added | `compat/differential_allowlist_0014.json` |
| added | `compat/differential_corpus_0014_manifest.json` |
| added | `compat/differential_state_isolation_0014.json` |
| added | `compat/differential_summary_0014.json` |
| added | `compat/differential_upstream_defects_0014.json` |
| added | `reports/0014_differential_corpus.md` |
| added | `tasks/0014_differential_corpus.md` |
| added | `tests/fixtures/differential_regressions_0014.json` |
| added | `tests/fixtures/oracle_utf16_calibration_0014.json` |
| added | `tests/unit/test_differential_boundary_0014.py` |
| added | `tests/unit/test_differential_comparator_0014.py` |
| added | `tests/unit/test_differential_corpus_generator_0014.py` |
| added | `tests/unit/test_differential_manifest_0014.py` |
| added | `tests/unit/test_differential_regressions_0014.py` |
| added | `tests/unit/test_pattern_token_whitespace_0014.py` |
| added | `tests/unit/test_picky_level_filter_0014.py` |
| added | `tools/DifferentialCorpusOracle0014.java` |
| added | `tools/differential_batch_oracle_0014.py` |
| added | `tools/differential_corpus_0014.py` |
| added | `tools/fetch_natural_corpus_0014.py` |

## 5. Comparator defects found and fixed

`compare_findings()` in `tools/differential_lt.py` was not strong enough to support a
corpus-level compatibility claim. Every weakness listed in the task specification was
present and has been repaired.

| Defect | Before | After |
| --- | --- | --- |
| Suggestion comparison | `set(a) == set(b)` — order and duplicates invisible | ordered list equality, duplicates preserved |
| Repeated findings | matched by first same-rule-id hit, `break` after one | multiplicity-aware pairing over progressively weaker keys |
| `missing_in_pylat` / `extra_in_pylat` | rule-id set membership | multiset difference of rule-id occurrences |
| `is_exact_match` | count + rule ids + spans only | full equality of every comparable field |
| Message / category / short message / URL | never compared | compared exactly, no normalisation |
| Finding order | not a parity dimension | `FINDING_ORDER_MISMATCH`, ordered sequence equality |

`Finding` now carries `short_message`, `url` and the code-point span alongside the
UTF-16 span, and `Finding.comparable()` is the single definition of "exact". Diagnostic
pairing produces the twelve classifications the specification requires plus
`URL_MISMATCH`; pairing never influences the exact/non-exact verdict.

Regression tests: `tests/unit/test_differential_comparator_0014.py` (22 tests).

## 6. UTF-16 offset domain

Java `RuleMatch` positions index a UTF-16 `String`. That was proven rather than
assumed. `tests/fixtures/oracle_utf16_calibration_0014.json` records, for 154 targeted
Unicode inputs, the pinned Java findings together with the Python code-point spans and
both text lengths. A non-BMP prefix shifts the recorded Java offset by exactly one code
unit per supplementary character, which the Java-free test
`test_recorded_java_offsets_are_utf16_not_code_points` asserts case by case.

`RuleMatch.utf16_offset`/`utf16_length` are also checked against a conversion of the
match's own code-point span for every case in the campaign; a disagreement inside
Python's dual offset representation is itself a campaign failure
(`utf16_parity_failures`).

## 7. Batch oracle architecture

`tools/DifferentialCorpusOracle0014.java` plus the Python wrapper
`tools/differential_batch_oracle_0014.py`:

* validates the trusted pinned jar before anything runs;
* compiles the helper once into the oracle cache, keyed by source hash;
* starts **one** JVM and reuses it for the whole campaign;
* builds one `JLanguageTool` per configuration profile, once;
* speaks a line-oriented, tab-separated, base64-framed protocol over stdin/stdout;
* echoes the case id in `RESULT` and `END`, so a desynchronised stream, a dead JVM or a
  Java-side exception is detected and reported rather than silently misattributed;
* serialises `RuleMatch` fields directly — no CLI scraping, no post-processing of Java
  results to make them resemble Python.

`RussianConfusionProbabilityRule` (`CONFUSION_RULE`) is disabled in every profile and
its matches are dropped before serialisation, so both sides compare the same intended
ordinary/non-LM surface.

## 8. Corpus strata and provenance

| Stratum | Content | Source |
| --- | --- | --- |
| A | accepted pinned/upstream text evidence | `compat/extracted_grammar_examples.json` (all 2446 examples) and the whole-text cases of the Task-0011/0012/0013 oracle fixtures |
| B | deterministic mutations | 39 mutation kinds across 7 families, seeded from Stratum A |
| C | spelling / suggestion stress | controlled misspellings of frequent Russian words drawn from pinned resources |
| D | natural Russian prose | Russian Wikipedia and Russian Wikisource, local only |
| E | targeted Unicode / offset cases | 20 decorations over 8 base sentences |

`direct_speller` fixture cases are deliberately excluded from Stratum A: they probe the
speller API with bare words, not whole-text grammar-check inputs.

Mutation families: case, composition, punctuation, repetition, spelling, unicode,
whitespace. Fixed seed `140014`, recorded in the manifest. Selection uses
`random.Random` seeded with a string, never Python's process-randomised `hash()`;
`test_generation_does_not_depend_on_process_randomised_hash` runs the generator in two
subprocesses with opposing `PYTHONHASHSEED` values and compares signatures.

## 9. External corpus (Stratum D)

The natural corpus is development evidence only. It lives under the git-ignored `corpora/` directory and is not committed; only its identity is recorded here and in the manifest.

### ru_wikipedia

| Item | Value |
| --- | --- |
| Source | ru.wikipedia.org |
| API | `https://ru.wikipedia.org/w/api.php` |
| License | CC BY-SA 4.0 |
| License URL | https://creativecommons.org/licenses/by-sa/4.0/ |
| Retrieval date | 2026-08-21 |
| Selection method | deterministic seeded PRNG draws two-letter Cyrillic start points; each start point walks namespace 0 with generator=allpages; plain text from prop=extracts explaintext=1 |
| Selection seed | `140014` |
| Local filename | `corpora/natural_ru_wikipedia_0014.jsonl` |
| Bytes | 1979945 |
| SHA-256 | `7b2e8816890aaf8a1f0d977bab85b8327be1a074f0a62250ed7d41b566f80101` |
| Pages visited | 460 |
| Pages contributing blocks | 460 |
| Raw block count | 1609 |
| Retained block count | 1605 |
| Block unit | blank-line separated block of the plain-text extract |
| Markup removal | none; the API returns plain text |
| Filters | min 80 chars, max 3000 chars, min Cyrillic letter ratio 0.5, max 6 blocks per page, headings rejected |
| Text edits | none; blocks are accepted or rejected verbatim. No spelling, case, punctuation, typography, ё/е or whitespace normalisation is applied. |

### ru_wikisource

| Item | Value |
| --- | --- |
| Source | ru.wikisource.org |
| API | `https://ru.wikisource.org/w/api.php` |
| License | CC BY-SA 4.0 (wiki layer); underlying works public domain |
| License URL | https://creativecommons.org/licenses/by-sa/4.0/ |
| Retrieval date | 2026-08-20 |
| Selection method | fixed sorted prose categories walked with list=categorymembers (cmsort=sortkey); plain text from action=parse rendered <p> elements, because Wikisource articles are transclusions the extracts API does not resolve |
| Categories | Категория:Повести, Категория:Проза, Категория:Рассказы, Категория:Романы |
| Local filename | `corpora/natural_ru_wikisource_0014.jsonl` |
| Bytes | 881701 |
| SHA-256 | `5aa2e247c8e31be22e8749c36f75a216841f5e25d1ffbc58f8ffb2d6565c9df5` |
| Pages visited | 183 |
| Pages contributing blocks | 181 |
| Raw block count | 1068 |
| Retained block count | 800 |
| Block unit | one rendered <p> element |
| Markup removal | <sup> reference markers dropped, remaining tags removed, HTML entities decoded |
| Filters | min 80 chars, max 3000 chars, min Cyrillic letter ratio 0.5, max 6 blocks per page, headings rejected |
| Text edits | none; blocks are accepted or rejected verbatim. No spelling, case, punctuation, typography, ё/е or whitespace normalisation is applied. |

Total retained blocks: **2405**, of which **2405** are unique and non-empty.

## 10. Corpus counts

| Metric | Value |
| --- | --- |
| Unique texts | **9615** (minimum 8000) |
| Text/profile executions | **17425** (minimum 12000) |
| Semantic duplicates skipped | 422 |
| Non-BMP executions | 638 (minimum 500) |
| Combining-mark executions | 459 |
| Soft-hyphen executions | 178 |

### By stratum

| Stratum | Name | Source texts | Unique texts | Executions | Exact | Non-exact | Java findings | Python findings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | accepted_upstream_evidence | 2713 | 2514 | 5028 | 5028 | 0 | 2813 | 2813 |
| B | deterministic_mutations | 2354 | 2342 | 4996 | 4959 | 37 | 5314 | 5400 |
| C | spelling_stress | 2200 | 2200 | 4400 | 4400 | 0 | 2793 | 2793 |
| D | natural_russian_prose | 2405 | 2405 | 2693 | 2693 | 0 | 14582 | 14582 |
| E | unicode_offset_targeted | 154 | 154 | 308 | 308 | 0 | 405 | 405 |

Field mismatch counts by stratum are all empty; the machine-readable form is `counts_by_stratum.<stratum>.mismatch_counts_by_kind` in the summary.

## 11. Configuration profiles

| Profile | Definition | Executions | Exact | Non-exact | Java findings | Python findings |
| --- | --- | --- | --- | --- | --- | --- |
| `all_ordinary_enabled` | every registered default-off ordinary non-LM rule enabled on both sides | 5010 | 4973 | 37 | 4989 | 5075 |
| `cfg_filler_words_2` | `FILLER_WORDS_RU` enabled, `minPercent = 2`, `excludeDirectSpeech = false` | 200 | 200 | 0 | 498 | 498 |
| `cfg_long_paragraph_30` | `TOO_LONG_PARAGRAPH` enabled, `maxWords = 30` | 200 | 200 | 0 | 498 | 498 |
| `cfg_long_sentence_15` | `TOO_LONG_SENTENCE.maxWords = 15` | 200 | 200 | 0 | 498 | 498 |
| `cfg_speller_yo` | `MORFOLOGIK_RULE_RU_RU_YO` enabled, `MORFOLOGIK_RULE_RU_RU` disabled | 2200 | 2200 | 0 | 1399 | 1399 |
| `default` | plain `LanguageToolRU()` and pinned Russian defaults | 9615 | 9615 | 0 | 18025 | 18025 |

The `all_ordinary_enabled` enablement list has 23 rule ids, derived from the pinned Java-rule inventory and the pinned `grammar.xml`, never hand written, and applied identically to both sides.

## 12. Mismatch triage

The first full campaign, run against the Task-0013 baseline implementation, produced **2116** non-exact cases out of 17425 executions, spanning **238** distinct mismatch fingerprints.

Initial mismatch classifications:

| Classification | Occurrences |
| --- | --- |
| `CATEGORY_MISMATCH` | 4 |
| `EXTRA_FINDING` | 1785 |
| `FINDING_ORDER_MISMATCH` | 4 |
| `MESSAGE_MISMATCH` | 25 |
| `MISSING_FINDING` | 199 |
| `RULE_ID_MISMATCH` | 5 |
| `SHORT_MESSAGE_MISMATCH` | 5 |
| `SPAN_MISMATCH` | 180 |
| `SUGGESTION_CONTENT_MISMATCH` | 174 |

| Triage outcome | Count |
| --- | --- |
| Unique mismatch fingerprints | 238 |
| Minimized | 238 |
| Caused production fixes | 18 |
| Caused harness/comparator fixes | 6 |
| Remaining accepted / out of scope | 37 (pinned-upstream defect, section 15) |

Every mismatch was reproduced independently against the trusted oracle, minimized while preserving its discrepancy fingerprint, traced to pinned upstream source or to the constant pool and bytecode of the trusted jar, fixed, covered by a test, and re-run. No expected Java output was edited by hand at any point.

## 13. Production compatibility defects found and fixed

Every defect below was found by the differential campaign, confirmed against the trusted
oracle, traced to pinned upstream source or bytecode, fixed, and covered by a test.

### 13.1 Picky rules ran at the default checking level

`JLanguageTool.check(text)` runs at `Level.DEFAULT`. Pinned
`isRuleActiveForLevelAndToneTags` returns `false` for any rule tagged `picky` at that
level, and `filterMatches` applies that predicate *before* `SameRuleGroupFilter` and
`CleanOverlappingFilter`. `pylat_ru` treated `picky` only as an overlap-priority
penalty, so 30 XML rule ids and the two picky native rules could reach a default check.

Fix: `pylat_ru.match_filters.level_filter`, applied first in `filter_rule_matches`.
Tests: `tests/unit/test_picky_level_filter_0014.py`.

A Task-0011 assertion that expected `TOO_LONG_SENTENCE` from a whole-pipeline check was
corrected: the trusted oracle returns nothing for that text, and the configured
threshold is now asserted on the rule surface where it is observable.

### 13.2 `ParagraphRepeatBeginningRule` spans

The port used paragraph ranges and a one-codepoint fudge factor. The pinned rule walks
*sentences*, uses `Tools.isParagraphEnd`, and computes both spans from
`numCharEqualBeginning`, which returns the sentence-local end offset of the matching
token in the **previous** paragraph — an upstream quirk that makes the second span as
long as the first paragraph's leading token, not its own.

Fix: faithful port including `_is_paragraph_end`, `_num_char_equal_beginning` and the
`startPos < lastPos + endPos` guard.

### 13.3 Synthesised forms were neither deduplicated nor sorted

`MatchState.toFinalString` collects synthesised word forms in a `TreeSet` in both of its
branches. The Python static-lemma branch returned the synthesiser's list unchanged, so a
token whose readings all map to the same target tag produced the same form several times
(`Имелось в виду <suggestion>водным спортом</suggestion>, <suggestion>водным
спортом</suggestion>, …`).

Fix: `sorted(set(...))` in `pylat_ru.grammar.formatter`.

### 13.4 `MatchState` one-form pre-pass was missing

Before synthesising, the pinned method scans the lemma-less readings: a reading with
neither lemma nor POS tag contributes the surface token and sets `oneForm`, after which
synthesis is skipped entirely. That is what a token carrying a combining mark keeps
alongside its tagged reading, so pinned LanguageTool suggests the original surface where
`pylat_ru` synthesised a new form.

Fix: the pre-pass is now part of the regexp-postag branch in
`pylat_ru.grammar.formatter`.

### 13.5 `RussianUnpairedBracketsRule` was an approximation

Rewritten as a faithful port of `GenericUnpairedBracketsRule`. Three observable defects
were removed:

* the numeral exception for `)` ignored the pinned `!(stack.peek() == "(")` guard, so an
  enumerator such as `(а)` left its opening parenthesis dangling;
* symmetric symbols were popped when the stack top matched, where the pinned rule always
  *pushes* a symmetric symbol preceded by whitespace;
* the `ruleMatchStack` cancellation pass in `createMatch`, the odd-symmetric-stack rule
  and the `endsLikeRealSentence` condition were missing entirely.

The pinned ASCII `\p{Punct}` classes and `NUMERALS_RU` are now spelled out exactly;
`Pattern.CASE_INSENSITIVE` without `UNICODE_CASE` folds ASCII only, which is why the
pinned pattern lists the Cyrillic cases separately.

### 13.6 `CleanOverlappingFilter` duplicate-suggestion test

The pinned filter tests `suggestion.indexOf(" ") > 0`, not `contains(" ")`. A
single-space suggestion — exactly what `WHITESPACE_RULE` produces — has its only space at
index 0 and is therefore not a two-word suggestion. `pylat_ru` used `in`, so two adjacent
whitespace repetitions were collapsed and one match was lost. `String.split` semantics
(trailing empties discarded) are now reproduced as well.

### 13.7 `WHITESPACE_RULE` crossed sentence boundaries

The pinned rule walks each sentence's own token array. `pylat_ru` walked one flat token
list for the whole text, so a run of spaces split across a sentence boundary was reported
as a repetition that pinned LanguageTool does not report.

### 13.8 The three paragraph rules used paragraph ranges

`WhiteSpaceBeforeParagraphEnd`, `WhiteSpaceAtBeginOfParagraph` and
`PunctuationMarkAtParagraphEnd2` are now faithful ports.
`WhiteSpaceAtBeginOfParagraph` in particular is a **sentence-level** rule upstream, not a
paragraph-level one, so a sentence that merely follows another on the same line and
starts with whitespace is reported. `PunctuationMarkAtParagraphEnd2` accumulates its word
count across the sentences of a paragraph and resets only at a paragraph end.

`setSuggestedReplacement("")` leaves a match with no suggestion at all rather than one
empty replacement.

### 13.9 `isNonWord` was a Unicode approximation

`AnalyzedTokenReadings.NON_WORD_REGEX` is a fixed single-character class, copied verbatim
from the constant pool of the trusted jar. `pylat_ru` used "contains no letters or
digits", which wrongly classified `{` and `}` as non-words and suppressed
`PUNCTUATION_PARAGRAPH_END2`.

### 13.10 Suggestion case adaptation and deduplication

`PatternRuleMatcher` derives two independent case flags from the *pattern* match tokens,
anchored at `firstMatchToken + correctedStPos` so the tokens before `<marker>` never
decide a suggestion's case, and `RuleMatch` applies them while extracting `<suggestion>`
spans into a `LinkedHashSet`. `pylat_ru` only uppercased the first character at a
sentence start and never deduplicated, producing `['по', 'по']` where pinned
LanguageTool produces `['по']`, and `'ученик'` where it produces `'Ученик'`.

### 13.11 `scope="next"` exceptions under `skip`

Pinned `AbstractPatternRulePerformer.testAllReadings` tests the *previous* element's
next-scope exception against the readings of the token currently being considered
whenever that previous element carried a `skip`. The grammar matcher already did this;
the **disambiguation** matcher only ever looked at the literal next token. The pinned
disambiguation rule `NOUN_R` therefore fired in `pylat_ru` where it does not fire
upstream, dropped an accusative reading, and made `Unify_Adj_NN_case` match a sentence
pinned LanguageTool leaves alone.

### 13.12 Token-hint fast reject was missing

Pinned `AbstractTokenBasedRule.canBeIgnoredFor` skips a rule outright unless every
required literal string occurs in the sentence's token index — an index built from the
**surface** tokens. A token carrying a combining mark therefore does not satisfy a
literal hint, and rules such as `Frazeologizm_nevernij` do not run at all on
`… в одну дуду́`. `pylat_ru` had no equivalent and matched.

### 13.13 Soft hyphens were not removed before the rules ran

The largest single family. Pinned `JLanguageTool.getRawAnalyzedSentence` calls
`replaceSoftHyphens` on the token list before tagging, and the sentence the rules see
carries the **cleaned** tokens; only the reported positions are mapped back onto the
original text. The public `analyzeText`/`getAnalyzedSentence` API restores the original
surface in an extra untagged reading, which is why a rule-level check and a
whole-pipeline check legitimately disagree on such text.

This was established by running a probe rule inside `JLanguageTool.check()`: the sentence
it receives is `Ёмкость большая.` with two readings, while `analyzeText` returns
`Ё<U+00AD>мкость большая.` with three. The same probe shows that a combining acute is
**not** removed, so the cleaning is applied to the soft hyphen only.

Fix: `LanguageToolRU.check()` strips U+00AD, runs the whole pipeline on the cleaned text,
and maps every reported span back onto the original — counting removed characters that
sat inside a match back into its length.

### 13.14 Degenerate `PARAGRAPH_REPEAT_BEGINNING_RULE` span

See section 15: pinned LanguageTool raises here. `pylat_ru` skips the empty span instead
of emitting a zero-length match.

### 13.15 Pattern-token text was not whitespace-normalised

`PatternToken.setStringElement` runs every pattern-token string through
`StringTools.trimWhitespace`, which trims the ends, collapses runs of characters at or
below U+0020 and drops line feeds, tabs and carriage returns. That is what lets a rule
write a long alternation across several indented XML lines, as `OPREDELENIA` does:

```xml
<token skip="-1" regexp="yes">который|которого|которому|
    котором|которая|которой|...</token>
```

`pylat_ru` kept the raw text, so every alternative that began a line carried the
indentation into the pattern and could never match a token. `OPREDELENIA` therefore
missed any sentence whose second relative pronoun was one of those alternatives.

Fix: faithful `trim_whitespace` and `java_trim` ports in
`pylat_ru.tagging.string_tools`, applied to token and exception text in the grammar
loader. `java_trim` is needed separately because Java's `String.trim` cuts at U+0020
while Python's `str.strip()` also removes NBSP and other Unicode spaces.
Tests: `tests/unit/test_pattern_token_whitespace_0014.py`.

### 13.16 Text-level rules were not evaluated first

`JLanguageTool.check` runs every `TextLevelRule` over the whole analysed text before it
runs the sentence-level rules, so text-level matches enter `filterMatches` ahead of
sentence-level ones. That order is not cosmetic: `SameRuleGroupFilter` and
`CleanOverlappingFilter` both resolve a same-span tie in favour of whichever match they
see first, and `Many_PNN` (a text-level style rule) shares spans with sentence-level
rules on long narrative paragraphs. `pylat_ru` emitted native rules in registration
order, so the sentence-level match won the tie and `Many_PNN` was filtered away.

Fix: `NativeRule` carries an explicit `text_level` class attribute — set on all eleven
text-level rules — and `NativeRuleEngine.check_context` runs the text-level pass before
the sentence-level pass.

### 13.17 SRX shorthand classes used Unicode semantics

`java.util.regex` resolves `\s`, `\S`, `\d`, `\D`, `\w` and `\W` against ASCII
unless the pattern asks for `UNICODE_CHARACTER_CLASS`; Python resolves them against
Unicode. None of the pinned Russian SRX break rules asks for it, so `[.!?…][…]*\s` must
break only at U+0020, U+0009, U+000A, U+000B, U+000C and U+000D. `pylat_ru` split a
sentence at every Unicode space as well, so text using a narrow no-break space before a
dash — ordinary in the Wikisource prose of stratum D — was segmented differently from
pinned LanguageTool, which changed `SENTENCE_WHITESPACE`, the speller's
sentence-start capitalisation and every rule anchored at a sentence boundary.

The fix is a textual expansion, not the global `regex.ASCII` flag: Java's `\p{...}`
properties stay Unicode whether or not `UNICODE_CHARACTER_CLASS` is set, while
`regex.ASCII` would restrict them too and stop rule 4 (`after='\p{Lu}[^\p{Lu}]'`) from
splitting `Первое.Второе.`. `pylat_ru.tokenization.srx.asciify_java_shorthands` therefore
rewrites only the shorthands, and only outside a character class, in patterns that carry
no Java Unicode flag.

### 13.18 Rule messages had their whitespace collapsed

`PatternRuleMatcher` builds a message by deleting the `PLEASE_SPELL_ME` and mistake
markers from the template; it never collapses whitespace. `pylat_ru` ran the finished
message through a `" {2,}" -> " "` substitution, so a template whose `<suggestion>` block
was dropped kept one space where pinned LanguageTool keeps two. `PREP_U_and_Noun`
produced `…в родительном падеже: или <suggestion>миледи</suggestion>` where pinned
LanguageTool produces `…в родительном падеже:  или <suggestion>миледи</suggestion>`.

Fix: the collapse is gone; the message is the concatenation of its chunks.

## 14. Harness and comparator defects found and fixed

These were defects in the differential machinery itself, not in `pylat_ru`. Each one
could have hidden a real compatibility failure, so all were repaired before any corpus
percentage was trusted.

| # | Defect | Consequence if left |
| --- | --- | --- |
| 1 | Suggestions compared as sets | `['a','b']` and `['b','a']` looked identical |
| 2 | Findings matched by first same-rule-id hit | repeated findings of one rule collapsed |
| 3 | `missing_in_pylat`/`extra_in_pylat` from rule-id membership | a rule seen twice in Java and once in Python looked complete |
| 4 | `is_exact_match` ignored message, category, short message and URL | a wrong message passed as an exact match |
| 5 | Finding order was not a parity dimension | a reordered result set passed |
| 6 | `JavaLanguageToolOracle.check()` left short message and URL empty | every comparison through the CLI path would fail on fields the CLI does report |

Defects 1-5 are the weaknesses the task specification predicted; all were present.
Defect 6 was found while extending `Finding`: the legacy CLI-based oracle path did not
populate the two fields the strict comparator had just started comparing.

## 15. Known differences

There is exactly one known difference on the ordinary/non-LM Russian surface, and it is a defect in pinned LanguageTool 6.8 rather than a compatibility gap.

### PARAGRAPH_REPEAT_BEGINNING_RULE_EMPTY_SECOND_SPAN

* **Rule**: `PARAGRAPH_REPEAT_BEGINNING_RULE`
* **Profiles**: all_ordinary_enabled
* **Exception**: `IllegalArgumentException: fromPos`
* **Trigger**: A paragraph whose opening token repeats the previous paragraph's opening token, where that token is a single character and the following sentence begins with the paragraph line break, for example "В адрес организацией мы направили письмо.\n\nВ адрес организацией мы направили письмо."
* **Upstream source**: `languagetool-core/src/main/java/org/languagetool/rules/ParagraphRepeatBeginningRule.java`
* **Upstream evidence**: match(List<AnalyzedSentence>) guards only the first RuleMatch with `if (startPos < lastPos+endPos)`. The second RuleMatch is built unguarded from `nextPos + nextTokens[1].getStartPos()` to `nextPos + endPos`, so when those coincide the RuleMatch constructor throws IllegalArgumentException and JLanguageTool.check() abandons the whole text.
* **pylat_ru behaviour**: RussianUnpairedBracketsRule is unaffected; ParagraphRepeatBeginningRule skips the degenerate empty span instead of raising, so the remaining findings for the text are returned normally. An empty span is not a reportable match in either implementation.
* **Scope reason**: Reproducing a crash is not a compatibility goal: the installed library must return results for ordinary Russian text. The difference is confined to the default-off PARAGRAPH_REPEAT_BEGINNING_RULE and only to inputs the pinned pipeline cannot process at all.
* **Cases affected**: 37 of 17425 executions

The pinned oracle answered 17388 of 17425 executions; those are the cases a parity claim can be made about, and every one of them matches exactly. The remaining executions are the ones above, where pinned LanguageTool raises and produces no result to compare with.

Ordinary differential allowlist entries: **0**. No rule id, field, category or Unicode class is suppressed anywhere.

`RussianConfusionProbabilityRule` (`CONFUSION_RULE`) remains `LANGUAGE_MODEL_DEFERRED`, is disabled in every Java profile and is dropped before serialisation, so it never contributed to or masked an ordinary comparison.

## 16. Final differential metrics

| Metric | Value |
| --- | --- |
| Executions | 17425 |
| Comparable executions (oracle answered) | 17388 |
| Unique texts | 9615 |
| Exact cases | **17388** |
| Non-exact cases | **0** |
| Java findings (all executions) | 25907 |
| Python findings (all executions) | 25993 |
| Java findings (comparable executions) | **25907** |
| Python findings (comparable executions) | **25907** |
| Java oracle errors | 37 (all explained, section 15) |
| Python errors | 0 |
| Unexplained ordinary discrepancies | **0** |
| Ordinary allowlist entries | **0** |

### 16.1 Field parity

| Dimension | Parity |
| --- | --- |
| Finding-sequence exact | 17388/17388 = 100.0000% |
| Rule id | 17388/17388 = 100.0000% |
| Category | 17388/17388 = 100.0000% |
| Span (UTF-16) | 17388/17388 = 100.0000% |
| Message | 17388/17388 = 100.0000% |
| Short message | 17388/17388 = 100.0000% |
| Suggestion content | 17388/17388 = 100.0000% |
| Suggestion order | 17388/17388 = 100.0000% |
| Finding order | 17388/17388 = 100.0000% |
| URL | 17388/17388 = 100.0000% |
| Full observable field | 17388/17388 = 100.0000% |

### 16.2 Suggestions

| Metric | Value |
| --- | --- |
| Java findings offering suggestions | 22687 |
| Exact ordered suggestion matches | 22687 |
| Suggestion content mismatches | 0 |
| Suggestion order-only mismatches | 0 |
| Duplicate-preservation mismatches | 0 |

### 16.3 UTF-16 and Unicode coverage

| Metric | Value |
| --- | --- |
| Non-BMP executions | 638 |
| Non-BMP exact | 638 |
| Combining-mark executions | 459 |
| Combining-mark exact | 459 |
| Soft-hyphen executions | 178 |
| Soft-hyphen exact | 178 |
| UTF-16 parity failures | 0 |

### 16.4 Rule-id occurrences

460 distinct rule ids were observed. Every one has a mismatch count of zero; the full sorted table is `by_rule_id` in the committed summary. The twenty most frequent:

| Rule id | Java occurrences | Python occurrences | Mismatches |
| --- | --- | --- | --- |
| `MORFOLOGIK_RULE_RU_RU` | 15539 | 15539 | 0 |
| `MORFOLOGIK_RULE_RU_RU_YO` | 1959 | 1962 | 0 |
| `COMMA_PARENTHESIS_WHITESPACE` | 742 | 742 | 0 |
| `RU_WORD_REPEAT` | 682 | 685 | 0 |
| `UPPERCASE_SENTENCE_START` | 558 | 558 | 0 |
| `WHITESPACE_RULE` | 421 | 421 | 0 |
| `PARAGRAPH_REPEAT_BEGINNING_RULE` | 308 | 357 | 0 |
| `WORD_REPEAT_RULE` | 265 | 265 | 0 |
| `MissingYO` | 236 | 236 | 0 |
| `RU_UNPAIRED_BRACKETS` | 203 | 204 | 0 |
| `DotOrCase` | 162 | 162 | 0 |
| `WHITESPACE_PARAGRAPH` | 132 | 133 | 0 |
| `Latin_letters` | 114 | 114 | 0 |
| `Three_dot` | 103 | 103 | 0 |
| `RU_COMPOUNDS` | 93 | 93 | 0 |
| `KAVITCHKI` | 88 | 88 | 0 |
| `Com_Num` | 83 | 89 | 0 |
| `Unify_Adj_NN_gender` | 76 | 76 | 0 |
| `Frazeologizm_nevernij` | 68 | 68 | 0 |
| `Pravopisanie_po-prezhnemu` | 68 | 68 | 0 |

### 16.5 State and order invariance

| Check | Result |
| --- | --- |
| Sample size | 299 |
| Fresh Java profile matches shared | True |
| Reverse Java order matches forward | True |
| Fresh Python instance matches shared | True |
| Reverse Python order matches forward | True |
| Divergent cases | 0 |

### 16.6 Committed regression fixture

| Item | Value |
| --- | --- |
| Path | `tests/fixtures/differential_regressions_0014.json` |
| Cases | 238 |
| Oracle build | `lt_6.8_source_build_jdk17_stefan` |

## 20. Reproducibility

* Internal strata regenerate deterministically from the committed seed and generator
  version; `corpus_signature` and the per-stratum signatures are content hashes over
  case identity, order, text hash and profile.
* Case ids are `f"{stratum}{index:06d}_{identity[:12]}"` where the identity is the
  SHA-256 of the case text plus the complete profile state. Nothing in a case identity
  depends on what Java returned.
* Semantic deduplication collapses only identical `(text, profile state)` pairs; the same
  text under two profiles remains two cases.
* No timestamp participates in any reproducibility hash.

## 21. Production boundary

`src/pylat_ru/**` imports none of the Task-0014 tooling, names none of its artefacts, and
reaches no corpus path. A real wheel is built, inspected for Java sources, class files,
jars, JSONL, `tools/`, corpora and campaign artefacts, installed into an isolated target,
and exercised from an interpreter whose `PATH` contains neither `java` nor `javac`.

`corpora/`, `test_corpora/` and `.oracle_cache/` remain git-ignored and a test asserts
that no tracked path falls under them.

## 22. Full pytest result

The whole suite, run from a clean working tree with no Java on `PATH`:

```bash
python -m pytest --junitxml=pytest-results.xml
```

| Outcome | Count |
| --- | --- |
| Passed | **1120** |
| Failed | **0** |
| Errors | **0** |
| Skipped | **0** |
| Collected | 1120 |
| Wall time | 150.1 s |

No test is skipped, xfailed or conditionally disabled: the Definition of Done requires `failures=0, errors=0, skipped=0`, and the CI job re-checks the same three numbers from this JUnit report on Python 3.10 and 3.12.

## 23. Development commands

```bash
python -m tools.differential_corpus_0014 validate-oracle
python -m tools.fetch_natural_corpus_0014 --wikipedia-target 1600 --wikisource-target 800
python -m tools.differential_corpus_0014 build
python -m tools.differential_corpus_0014 run
python -m tools.differential_corpus_0014 run --stratum B
python -m tools.differential_corpus_0014 run --profile all_ordinary_enabled
python -m tools.differential_corpus_0014 run --shard 1/4 --resume
python -m tools.differential_corpus_0014 summarize
python -m tools.differential_corpus_0014 minimize --limit 50
python -m tools.differential_corpus_0014 calibrate-utf16
python -m tools.differential_corpus_0014 build-regressions
python -m tools.differential_corpus_0014 bind-fixtures
python -m tools.differential_corpus_0014 verify-regressions
python -m tools.differential_corpus_0014 state-isolation --sample 300
```

## 24. Task 0015

Task 0015 was not started. No packaging or release work, no upstream-version upgrade and
no language-model work was carried out. `RussianConfusionProbabilityRule` remains
`LANGUAGE_MODEL_DEFERRED` and is excluded from the Java differential surface.
