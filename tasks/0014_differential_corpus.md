# Task 0014 — Differential Corpus and Full-Pipeline Compatibility Audit

## Status

**ACTIVE TASK SPECIFICATION**

Task 0013 is accepted as the baseline for this task.

Do not start Task 0015, packaging/release work, upstream-version upgrades, language-model work, or unrelated refactors while implementing this task.

---

# 1. Goal

Run a **large, strict, reproducible differential campaign** between:

```text
pylat_ru
```

and the official pinned Java LanguageTool Russian pipeline at:

```text
LanguageTool v6.8
commit e807fcde6a6506191e1470744d2345da28c26be6
```

The purpose of Task 0014 is not to produce an attractive percentage. The purpose is to discover real remaining compatibility defects that were not exercised by the pinned upstream test suite, minimize them, fix them, and leave behind a reusable differential-testing system.

At completion:

```text
ordinary/non-language-model Russian surface:
zero unexplained differential discrepancies
```

Production must remain:

```text
100% Python-native
NO Java/JRE
NO LanguageTool server
NO Java subprocesses
NO localhost dependency
NO runtime downloads
NO external NLP runtime
```

Java LanguageTool is allowed **only** as a development/test oracle.

---

# 2. Exact baseline

Repository:

```text
bojlahg/pylat_ru
branch: main
```

Task-0013 accepted final repository baseline:

```text
abe5290d5c2e8e613937e180c7669638ff56b6af
```

Before editing, verify:

```bash
git rev-parse HEAD
git status --short
git log -1 --oneline
```

The working tree must be clean and `HEAD` must be the accepted Task-0013 baseline or a later explicitly accepted review-fix SHA.

Pinned upstream remains:

```text
repository: https://github.com/languagetool-org/languagetool.git
tag:        v6.8
commit:     e807fcde6a6506191e1470744d2345da28c26be6
```

Trusted Java oracle identity remains bound by:

```text
compat/oracle_manifest.json
```

Current default trusted build:

```text
build_id:
lt_6.8_source_build_jdk17_stefan

jar_sha256:
b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc
```

Accepted functional accounting entering this task:

```text
Russian XML source rules                  892 / 892 runnable
compiled physical variants                907 / 907 runnable
Russian XML examples                     2446 / 2446 runnable

ordinary relevant Java rules               23 / 23
Russian XML filters                          7 / 7

pinned Russian upstream test files          18 / 18 accounted
executable upstream test methods            24 / 24 mapped
ordinary/non-LM upstream contracts           90 / 90
ordinary/non-LM scenario units              260 / 260

language-model rules                          0 / 1
RussianConfusionProbabilityRule = LANGUAGE_MODEL_DEFERRED
```

Task 0014 must preserve all accepted behavior from Tasks 0001–0013.

---

# 3. Existing differential infrastructure must be reused, not duplicated blindly

The repository already contains:

```text
tools/differential_lt.py
compat/oracle_manifest.json
tests/unit/test_differential_boundary.py
```

and many committed Java-oracle fixtures from previous tasks.

`tools/differential_lt.py` already provides pinned-oracle validation, JAR SHA validation, Java/Russian pipeline probes, subsystem helpers, a `Finding` schema, and `compare_findings()`.

Task 0014 must build on this infrastructure where sensible. Do **not** create a completely separate oracle stack merely because writing another one is easier.

However, the current whole-finding comparator is not strong enough for Task 0014 and must be corrected.

---

# 4. Mandatory comparator audit and repair

The current `compare_findings()` behavior is insufficient for a corpus-level compatibility claim.

Known weaknesses entering Task 0014 include:

1. suggestion comparison uses set semantics rather than exact ordered-list semantics;
2. repeated findings with the same `rule_id` are not matched robustly;
3. `missing_in_pylat` / `extra_in_pylat` are based on rule-ID membership, not finding multiplicity;
4. `is_exact_match` does not require full equality of every relevant observable field;
5. message/category differences can therefore be hidden by an apparently exact result;
6. finding order is not a first-class parity dimension.

Fix this before trusting any corpus percentage.

## 4.1 Strict canonical finding representation

For whole-pipeline differential comparison, derive the intersection of stable observable fields exposed by Java `JLanguageTool` `RuleMatch` and Python `pylat_ru.RuleMatch`.

At minimum compare exactly:

```text
rule_id
category_id
message
short_message              when Java exposes it
UTF-16 start offset
UTF-16 length
suggestions/replacements   exact order, exact duplicates
finding order
```

Also retain Python code-point offset/length for diagnostics.

If the Java oracle exposes another stable field that has a direct Python equivalent, include it where practical, for example URL.

Do not compare implementation-only Python fields that have no public Java equivalent merely to inflate the schema.

## 4.2 Offset domain must be proven, not assumed

Java `String` positions are UTF-16 based.

Before the main corpus campaign, add calibration tests containing non-BMP characters:

```text
emoji before finding
emoji inside surrounding context
multiple non-BMP characters
BMP + non-BMP mixtures
```

Prove exactly how Java oracle positions are serialized.

For every Python finding used by the differential comparator:

```text
RuleMatch.utf16_offset
RuleMatch.utf16_length
```

must agree with conversion from its code-point span.

A disagreement inside Python's own dual offset representation is itself a test failure.

## 4.3 Exact means exact

For the strict comparator:

```text
is_exact_match = True
```

only when the ordered Java and Python finding sequences are exactly equivalent on all mandatory comparable fields.

In particular:

```text
["a", "b"] != ["b", "a"]
["a", "a"] != ["a"]
```

No suggestion set conversion. No message whitespace normalization. No case folding. No punctuation normalization. No rule-ID-only approximation. No "same count therefore same result".

## 4.4 Diagnostic pairing

When output is not exact, produce deterministic diagnostic pairing so a mismatch can be classified usefully.

At minimum distinguish:

```text
MISSING_FINDING
EXTRA_FINDING
RULE_ID_MISMATCH
CATEGORY_MISMATCH
SPAN_MISMATCH
MESSAGE_MISMATCH
SHORT_MESSAGE_MISMATCH
SUGGESTION_CONTENT_MISMATCH
SUGGESTION_ORDER_MISMATCH
FINDING_ORDER_MISMATCH
JAVA_ORACLE_ERROR
PYTHON_ERROR
```

A single case may have more than one field mismatch. Diagnostic pairing must never alter the strict exact/non-exact result.

## 4.5 Comparator regression tests

Add focused unit tests proving at least:

- repeated same-rule findings are handled by multiplicity;
- two findings with same rule but different spans do not collapse;
- category mismatch fails;
- message mismatch fails;
- short-message mismatch fails when applicable;
- suggestion-order mismatch fails;
- duplicate-suggestion mismatch fails;
- finding-order mismatch fails;
- non-BMP span mismatch fails;
- exact repeated findings pass.

---

# 5. Whole-pipeline Java oracle for large campaigns

The existing `JavaLanguageToolOracle.check()` invokes Java per check and is not suitable as the only mechanism for thousands of corpus cases.

Task 0014 must provide an efficient development-only batch oracle.

Recommended shape:

```text
tools/DifferentialCorpusOracle0014.java
```

plus a Python wrapper in `tools/`. Equivalent architecture is acceptable if it preserves the same boundary.

## 5.1 Persistent Java process

The batch oracle should:

1. validate against the trusted pinned JAR before execution;
2. start one Java process;
3. create the Russian `JLanguageTool` instance once per configuration profile;
4. accept framed/NDJSON-style input cases over stdin;
5. emit one structured result per case over stdout;
6. reuse the Java process across many cases;
7. preserve deterministic case/result ordering;
8. fail explicitly if the stream desynchronizes or the Java process dies.

Do not start a JVM for each of ten thousand inputs. Humans have already invented enough slow software.

## 5.2 Java oracle semantics

The Java helper must use the actual pinned Russian pipeline, equivalent to:

```java
Russian.getInstance()
new JLanguageTool(...)
check(...)
```

and serialize direct `RuleMatch` information rather than scraping human-readable CLI output.

Use the direct Java rule-match fields needed by section 4. Do not post-process Java results to make them resemble Python.

## 5.3 Language-model exclusion

Task 0014 is still ordinary/non-LM parity.

`RussianConfusionProbabilityRule` remains:

```text
LANGUAGE_MODEL_DEFERRED
```

The Java differential surface must explicitly exclude/disable that rule so both systems are comparing the same intended scope.

Do not count an LM-only difference as an ordinary parity failure. Do not begin implementing the language model in Task 0014.

## 5.4 Long-lived state

Run the large corpus with long-lived Java and Python tool instances.

Also add a deterministic state-isolation proof on a representative subset:

```text
fresh Python instance vs shared Python instance
fresh Java profile/tool vs shared Java profile/tool
forward case order vs reverse/permuted deterministic order
```

The result for a text/profile must not depend on which unrelated text was checked before it.

Task 0013 fixed real state bugs; Task 0014 must ensure the corpus runner does not reintroduce or conceal this class of failure.

---

# 6. Corpus case schema

Create a deterministic machine-readable case schema.

A case must include at least:

```json
{
  "case_id": "...",
  "source_stratum": "...",
  "text": "...",
  "profile": "default",
  "provenance": {}
}
```

Where relevant it may include:

```text
enabled_rules
disabled_rules
rule_config
mutation_parent_id
mutation_kind
seed
external_source_hash
```

Case IDs must be deterministic and unique. The semantic identity must not depend on expected Java output.

Do not build case IDs from "what Java returned", because that makes drift and accidental duplication harder to detect.

---

# 7. Corpus strata

Task 0014 must not rely on one homogeneous corpus.

## 7.1 Stratum A — accepted pinned/upstream text evidence

Include all suitable whole-text inputs already present in accepted project evidence, including at minimum:

```text
2446 grammar.xml example texts
ordinary Task-0013 upstream scenario texts where a full-pipeline check is meaningful
Task-0011 whole-rule / combined texts
Task-0012 whole-rule / combined texts
Task-0013 whole-pipeline oracle texts
```

Do not blindly force low-level synthetic inputs into `LanguageToolRU.check()` if they test APIs that are not whole-text grammar-check inputs.

Record exact source fixture/inventory paths.

Deduplicate only when cases are semantically identical:

```text
same text
same profile
same enable/disable/config state
```

Do not deduplicate two identical strings with different rule profiles.

## 7.2 Stratum B — deterministic text mutation corpus

Generate deterministic mutations from accepted Russian seed texts.

Mutation families must cover at least:

### whitespace / boundaries

```text
space insertion/deletion around punctuation
multiple spaces
tabs
NBSP
line breaks
paragraph breaks
leading/trailing whitespace
```

### case

```text
sentence-start lowercasing
title-case variants
ALL CAPS
mixed-case perturbations
```

### punctuation / typography

```text
hyphen
en dash
em dash
straight quotes
Russian quotes
nested quotes
brackets
ellipsis
comma/period/question/exclamation variants
```

### Russian spelling/orthography

```text
е ↔ ё where meaningful
single-character deletion
single-character insertion
adjacent transposition
Cyrillic substitution
hyphenation perturbation
```

### repetitions

```text
word duplication
short-range repeated roots/words
paragraph-beginning repetition
```

### Unicode / offsets

```text
combining acute
combining grave
soft hyphen
non-BMP prefix
non-BMP infix
multiple emoji
```

### sentence/paragraph composition

```text
concatenate two seed sentences
split one text at deterministic boundaries
insert quote/bracket boundaries
repeat a sentence across paragraphs
```

Use a committed fixed seed, for example:

```text
140014
```

or another explicitly recorded fixed integer.

Mutation selection must be deterministic across runs and Python 3.10/3.12. Do not use Python's process-randomized `hash()` for persistent case selection/order.

## 7.3 Stratum C — spelling/suggestion stress corpus

Suggestion parity is important enough to get its own stratum.

Derive a deterministic sample of valid Russian words from pinned accepted resources, preferring ordinary/frequent words rather than millions of arbitrary rare dictionary entries.

Generate controlled misspellings including:

```text
deletion
insertion
substitution
transposition
case variants
е/ё variants
hyphen variants
```

Require at least:

```text
2000 unique spelling-stress texts
```

unless a source-bound technical reason makes that impossible, in which case document the exact count and reason rather than silently lowering it.

The campaign must compare suggestions as an exact ordered list with duplicates preserved.

## 7.4 Stratum D — natural Russian development corpus

Run against natural Russian prose that was **not designed around LanguageTool rules**.

This corpus is development evidence and must not become a production dependency.

Requirements:

```text
at least 2000 unique non-empty text blocks
at least one clearly identified Russian source
preferably more than one source/domain
```

Acceptable examples include:

- a clearly licensed Russian Wikipedia sample;
- public-domain Russian prose;
- another local/user-provided Russian corpus with explicit provenance and license.

Do not use a corpus with unclear redistribution/license status.

External corpus content must live under an ignored local path such as:

```text
corpora/
test_corpora/
```

and must **not** be committed.

Record in the completion report:

```text
source
URL or source identifier
license/status
retrieval date
local filename
bytes
SHA-256
text-block count
preprocessing rules
```

If an external source cannot legally be redistributed, record its identity/hash and keep it local.

If a discovered bug needs a committed regression test, create a small synthetic/minimized reproduction rather than copying a copyrighted paragraph into the repository.

---

# 8. Minimum campaign size

After semantic deduplication, the final Task-0014 campaign must contain at least:

```text
8000 unique text inputs
12000 text/profile executions
```

and must include all mandatory strata above.

Minimum included sub-counts:

```text
grammar.xml example inputs: all suitable 2446
spelling stress:            >= 2000 unique texts
natural corpus:             >= 2000 unique text blocks
Unicode/non-BMP targeted:   >= 500 executions
```

If the same text is checked under multiple profiles, that increases execution count but not unique-text count.

Report both values explicitly. Do not meet the threshold by repeating identical cases.

---

# 9. Configuration profiles

At minimum run these whole-pipeline profiles.

## 9.1 `default`

Equivalent to normal:

```python
LanguageToolRU()
```

and normal pinned Java Russian defaults, with the LM rule excluded from Java.

## 9.2 `all_ordinary_enabled`

Enable all ordinary non-LM Russian rules that are registered but default-off at the pinned revision.

The exact list must be derived from the existing pinned Java-rule inventory. Do not invent it manually.

The same exact enablement must be applied to Java and Python.

## 9.3 targeted non-default configuration evidence

Include a bounded targeted set of cases for configurable rules whose configuration parity was previously established, including where applicable:

```text
long sentence threshold
long paragraph threshold
Russian filler threshold
spelling-related user configuration
```

This does not need to multiply the entire 8000-text corpus by every configuration. It must, however, exercise the whole combined pipeline with non-default configuration, not only isolated rule methods.

---

# 10. Deterministic corpus manifest

Create a committed manifest, for example:

```text
compat/differential_corpus_0014_manifest.json
```

It must contain enough information to reproduce every **committed/internal/generated** stratum exactly.

At minimum:

```text
schema_version
task
pinned_lt_version
pinned_lt_commit
oracle_build_id
oracle_jar_sha256
generator_version
fixed_seed
source inventory/fixture paths
source SHA-256 values
mutation families
profile definitions
case counts by stratum
unique-text count
execution count
external-corpus metadata/hash
```

The external natural corpus itself is not committed, but its exact completion-run identity must be recorded.

Add fail-closed tests for the manifest.

Regenerating internal/generated strata from the same baseline must produce byte-identical or semantic-signature-identical results according to the documented format.

---

# 11. Differential result format

Do not commit one gigantic JSON object containing thousands of redundant exact matches unless there is a strong reason.

Prefer:

```text
summary + hashes + mismatch details + minimized regressions
```

Create a committed machine-readable summary, for example:

```text
compat/differential_summary_0014.json
```

It must contain at least:

```text
campaign identity
input manifest hash
oracle identity
Python/task SHA used for the campaign
cases total
unique texts total
profile executions total

exact cases
non-exact cases
Java errors
Python errors

Java findings total
Python findings total

finding-sequence exact parity
rule-id parity
category parity
span parity
message parity
short-message parity where applicable
suggestion content parity
suggestion order parity

counts by stratum
counts by profile
mismatch counts by type
mismatch counts by rule ID
known/accepted discrepancy count
unexplained discrepancy count
```

Rates must be derived from integer counts and not hand-entered.

If a metric denominator is zero, report the explicit numerator/denominator and a meaningful state rather than pretending `1.0`.

---

# 12. No broad allowlists

The ordinary/non-LM target for this task is:

```text
zero unexplained discrepancies
```

A mismatch may not be hidden by:

```text
ignore this rule ID
ignore all spelling differences
ignore messages
ignore suggestions
ignore ordering
ignore Unicode cases
```

If a genuine intentionally out-of-scope difference exists, it must be represented by a **narrow machine-readable classification** with:

```text
case/fingerprint scope
exact field(s)
reason
upstream source evidence
project scope reason
```

For Task 0014, `RussianConfusionProbabilityRule` should normally be excluded before comparison, so the ordinary differential allowlist should ideally be empty.

Any non-empty ordinary allowlist requires explicit justification in the report and is a review hotspot.

---

# 13. Mismatch triage workflow

For every initial differential mismatch:

1. preserve the raw Java and Python result;
2. classify the mismatch type;
3. reproduce it independently;
4. determine whether the bug is production Python behavior, comparator/oracle behavior, case/profile construction, misunderstood pinned Java behavior, or intentionally excluded LM behavior;
5. minimize the text while preserving the same discrepancy fingerprint;
6. inspect pinned Java source/resources relevant to the mismatch;
7. fix the Python implementation or differential tooling as appropriate;
8. add a regression test;
9. rerun the minimized case;
10. rerun the affected corpus stratum;
11. rerun the full campaign before completion.

Do not change expected Java output by hand to make a mismatch disappear.

---

# 14. Automatic mismatch minimization

Provide a development utility that can minimize a failing corpus text while preserving a selected discrepancy fingerprint.

It does not need to be a perfect general-purpose delta debugger, but it must make a serious deterministic attempt to reduce:

```text
paragraphs
sentences
tokens
whitespace/punctuation fragments
```

while preserving:

```text
mismatch category
and relevant rule/span identity where possible
```

The minimizer must never mutate the trusted Java result directly.

The completion report must show:

```text
initial mismatch count
unique mismatch fingerprints
how many were minimized
how many caused production fixes
how many caused harness fixes
how many remained accepted/out-of-scope
```

---

# 15. Committed regression corpus

For every unique ordinary compatibility bug discovered and fixed in Task 0014, add a minimized committed regression case.

Recommended location:

```text
tests/fixtures/differential_regressions_0014.json
```

Each regression should record:

```text
case_id
discovered_in_stratum
original_mismatch_type
minimized_text
profile
expected pinned-Java findings
relevant upstream source/proof
```

Expected Java findings must be generated by the trusted oracle, not typed from memory.

Bind the fixture in:

```text
compat/oracle_manifest.json
```

with:

```text
size_bytes
SHA-256
oracle_build_id
case_count
```

Add Java-free pytest parity tests against the committed fixture.

If Task 0014 discovers zero new compatibility bugs, commit an explicit empty regression fixture or equivalent machine-readable proof rather than inventing fake cases.

---

# 16. Required coverage/report views

The final report must include tables or machine-readable equivalents for:

## 16.1 By corpus stratum

```text
cases
exact
non-exact
Java findings
Python findings
field mismatch counts
```

## 16.2 By configuration profile

Same metrics for:

```text
default
all_ordinary_enabled
targeted config profiles
```

## 16.3 By rule ID

For every rule ID actually observed in Java findings:

```text
Java occurrence count
Python occurrence count
exact matched count
mismatch count
```

Sort deterministically.

## 16.4 Unicode/offset coverage

Report:

```text
non-BMP cases
combining-mark cases
soft-hyphen cases
UTF-16 parity failures
```

## 16.5 Suggestions

Report:

```text
findings with suggestions
exact ordered suggestion matches
content mismatches
order-only mismatches
duplicate-preservation mismatches
```

---

# 17. Reproducibility and determinism

Task 0014 must prove:

1. internal/generated corpus regeneration is deterministic;
2. case IDs are stable;
3. corpus order is stable;
4. summary generation is stable;
5. mismatch fingerprinting is stable;
6. running a deterministic representative subset twice gives identical Java/Python outputs;
7. checking a representative subset in reverse/permuted order does not change per-case results.

Use cryptographic hashes for committed/generated artifact identity.

Do not use timestamps inside semantic hashes. If timestamps are included for audit metadata, keep them outside reproducibility comparisons.

---

# 18. Production-boundary proof

The differential campaign may use Java. The installed library may not.

Preserve and extend existing boundary tests to prove:

```text
src/pylat_ru/**
```

does not import:

```text
tools.differential_lt
Task-0014 corpus runner
Java helper code
subprocess for Java
socket/HTTP oracle clients
corpora
```

Build a real wheel and verify:

```text
no tools/ oracle helpers in the wheel
no corpus data in the wheel
no Java classes/sources in the wheel
no external corpus paths/resources in the wheel
```

From a clean temporary environment with no Java dependency, verify:

```python
from pylat_ru import LanguageToolRU
LanguageToolRU().check("Это тест.")
```

works.

---

# 19. External corpus hygiene

The existing `.gitignore` already excludes:

```text
corpora/
test_corpora/
.oracle_cache/
```

Preserve that behavior.

Add tests or a completion check proving no accidental external corpus blobs were committed.

Do not commit:

```text
Wikipedia dumps
books
large local text files
downloaded LanguageTool distributions
raw differential campaign logs
temporary mismatch dumps
oracle caches
```

Only commit the small deterministic metadata/summary/regression artifacts required by this task.

---

# 20. Compatibility metadata update

Update:

```text
compat/compatibility.json
```

to a Task-0014 milestone.

Do not simply set another hand-entered:

```json
"finding_parity": 1.0
```

The Task-0014 parity section must be traceable to the committed differential summary.

Add a dedicated section equivalent to:

```json
"task_0014_differential_corpus": {
  "status": "...",
  "manifest": "...",
  "summary": "...",
  "unique_texts": 0,
  "profile_executions": 0,
  "exact_cases": 0,
  "non_exact_cases": 0,
  "unexplained_discrepancies": 0,
  "ordinary_allowlist_entries": 0,
  "full_observable_field_parity": 0.0
}
```

Use real final counts.

Do not disturb accepted Task-0011/0012/0013 evidence. Do not claim the LM rule is implemented.

---

# 21. Tests required

Add focused tests for all Task-0014 infrastructure.

## Comparator

```text
exact repeated findings
multiplicity
same ID / different span
category mismatch
message mismatch
short-message mismatch
suggestion content mismatch
suggestion order mismatch
duplicate suggestions
finding order mismatch
UTF-16/non-BMP mismatch
```

## Corpus generator

```text
deterministic seed
stable case IDs
semantic deduplication
profile-sensitive identity
mutation-family coverage
minimum internal counts
non-BMP quota
no process-randomized hash dependence
```

## Manifest/summary

```text
schema validation
pinned upstream identity
oracle SHA identity
source hashes
count arithmetic
rate arithmetic
zero-unexplained gate
regeneration consistency
```

## Regression fixture

```text
oracle-manifest binding
semantic uniqueness
exact Python parity
```

## Production boundary

```text
no dev/oracle imports from src/
wheel isolation
no corpus material in wheel
normal no-Java execution
```

---

# 22. Full validation

Before final commit run:

```bash
python -m pytest
```

Requirements:

```text
0 failed
0 errors
0 skipped
```

No Task-0014 test may be silently skipped because Java is absent in ordinary pytest.

Live Java differential execution belongs to an explicit development command.

Committed fixture/summary integrity must remain testable without Java.

Also run focused deterministic checks for:

```text
corpus regeneration
summary regeneration
regression fixture parity
wheel isolation
```

---

# 23. Required development commands

Provide clear documented commands for at least:

```text
validate trusted oracle
build/regenerate internal corpus
run differential campaign
run only one stratum
run only one profile
resume or shard a campaign if supported
summarize results
minimize mismatches
verify committed regressions
```

Exact CLI names are implementation choices.

A good target shape is something like:

```bash
python -m tools.differential_corpus_0014 build ...
python -m tools.differential_corpus_0014 run ...
python -m tools.differential_corpus_0014 summarize ...
python -m tools.differential_corpus_0014 minimize ...
```

but reuse/extension of `tools/differential_lt.py` is preferred where clean.

---

# 24. Completion report

Create:

```text
reports/0014_differential_corpus.md
```

It must include:

1. Task title and baseline SHA.
2. Pinned LT commit.
3. Trusted oracle build ID and SHA.
4. Exact files changed.
5. Comparator defects found/fixed.
6. Batch-oracle architecture.
7. Corpus strata and provenance.
8. Exact corpus counts.
9. Exact profile counts.
10. Exact initial mismatch count.
11. Mismatch categories.
12. Minimized mismatch count.
13. Production bugs discovered.
14. Harness/comparator bugs discovered.
15. Fixes made.
16. Final differential metrics.
17. Suggestion-order metrics.
18. UTF-16/non-BMP metrics.
19. Rule-ID occurrence/mismatch summary.
20. External corpus hash/provenance.
21. Regression fixture count/hash.
22. Full pytest result.
23. Wheel-isolation result.
24. Known differences.
25. Explicit statement that Task 0015 was not started.

Do not describe `99.9%` as completion if the remaining `0.1%` is unexplained. List every remaining mismatch explicitly.

---

# 25. Definition of Done

Task 0014 is complete only if all of the following are true.

## Infrastructure

- [ ] Existing trusted oracle infrastructure is reused.
- [ ] Whole-finding comparator is strict.
- [ ] Suggestion order and duplicates are compared exactly.
- [ ] Finding multiplicity/order are compared exactly.
- [ ] UTF-16 offset domain is calibrated and tested.
- [ ] Persistent/batched Java oracle exists for large campaigns.
- [ ] Long-lived state/order invariance is tested.

## Corpus

- [ ] All suitable accepted upstream/fixture texts are included.
- [ ] Deterministic mutation stratum exists.
- [ ] At least 2000 spelling-stress texts exist.
- [ ] At least 2000 natural Russian text blocks are run.
- [ ] At least 8000 unique texts are run.
- [ ] At least 12000 text/profile executions are run.
- [ ] At least 500 Unicode/non-BMP targeted executions are run.
- [ ] External corpus is not committed.

## Differential result

- [ ] Every case has a deterministic identity.
- [ ] Java/Python output uses strict field comparison.
- [ ] Initial mismatches are triaged.
- [ ] Ordinary production defects are fixed.
- [ ] Unique fixed defects have minimized regression cases.
- [ ] Final unexplained ordinary/non-LM discrepancies = 0.
- [ ] No broad allowlist hides failures.
- [ ] `RussianConfusionProbabilityRule` remains explicitly LM-deferred.

## Evidence

- [ ] Corpus manifest is committed and reproducible.
- [ ] Differential summary is committed and arithmetically validated.
- [ ] Regression fixture is bound to trusted oracle identity.
- [ ] Compatibility metadata points to Task-0014 evidence.
- [ ] Full pytest has 0 failed / 0 errors / 0 skipped.
- [ ] Real wheel isolation passes.
- [ ] Production remains Java-free.

---

# 26. Commit, push, CI, and exact-final-SHA gate

After all Task-0014 work and the completion report are finished:

1. review `git diff`;
2. remove unrelated changes;
3. run final local tests;
4. commit Task 0014;
5. push `main`;
6. verify remote `main` is exactly that commit;
7. run/observe GitHub Actions on that exact final SHA;
8. verify Python 3.10 and Python 3.12 jobs both pass;
9. verify both jobs checked out the exact final SHA;
10. verify JUnit reports:

```text
0 failed
0 errors
0 skipped
```

Do **not** make a later docs-only commit merely to write the CI run ID into the report.

That creates a new SHA and invalidates the exact-final-SHA proof.

The CI run ID/URL belongs in the final handoff message, not necessarily in a post-CI repository commit.

If any follow-up commit is made after the verified CI run, CI must be rerun on that new final SHA.

---

# 27. Final handoff format

Return a concise final handoff containing:

```text
Task 0014 implementation SHA
final main SHA
GitHub Actions run ID
GitHub Actions run URL

Python 3.10:
<passed> passed / 0 failed / 0 errors / 0 skipped
checkout SHA: <final SHA>

Python 3.12:
<passed> passed / 0 failed / 0 errors / 0 skipped
checkout SHA: <final SHA>

Differential corpus:
unique texts: <N>
profile executions: <N>
Java findings: <N>
Python findings: <N>
exact cases: <N>
non-exact cases: 0
unexplained ordinary discrepancies: 0

Initial mismatches:
<N>

Production compatibility bugs fixed:
<N>

Harness/comparator bugs fixed:
<N>

Committed minimized regressions:
<N>

ordinary allowlist entries:
<N>

RussianConfusionProbabilityRule:
LANGUAGE_MODEL_DEFERRED

Task 0015:
not started

FINAL:
READY FOR REVIEW
```

If any ordinary/non-LM discrepancy remains unexplained, do not claim `READY FOR REVIEW`.

---

# 28. Stop condition

After Task 0014 is committed, pushed, and exact-final-SHA CI evidence is available:

```text
STOP
```

Do not begin Task 0015 automatically.
