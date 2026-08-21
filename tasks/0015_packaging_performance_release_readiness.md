# Task 0015 — Packaging, Performance, Release Readiness and Stable Public API

## Status

```text
ACTIVE TASK SPECIFICATION
```

Repository:

```text
bojlahg/pylat_ru
```

Branch:

```text
main
```

Task baseline / accepted Task-0014 final evidence SHA:

```text
a80dfcfe019ee1cd6ffd26feee2a9313f60c195f
```

Task-0014 reviewed campaign implementation SHA:

```text
931d3aaf76b37138fef63dee11e8bb3cd51b0634
```

Pinned LanguageTool:

```text
version: 6.8
commit: e807fcde6a6506191e1470744d2345da28c26be6
```

Trusted Task-0014 Java oracle identity remains unchanged:

```text
build id:
lt_6.8_source_build_jdk17_stefan

JAR SHA-256:
b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc
```

---

# 1. Purpose

Tasks 0001–0014 established the Python-native Russian LanguageTool implementation and
compatibility evidence.

Task 0015 is the **release-readiness / packaging / performance stabilization milestone**.

The task does **not** add another LanguageTool rule family and does **not** change the
pinned upstream version.

The goal is to make the already compatibility-proven implementation usable as a
well-defined distributable Python package:

```text
correct package metadata
+ stable primary public API
+ clean wheel/sdist
+ clean-install verification
+ explicit licensing/provenance
+ realistic performance baseline
+ long-lived/runtime safety checks
+ current user documentation
+ release-preflight CI
```

This task is about making `pylat_ru` something a developer can install and use without
knowing the history of fourteen implementation tasks.

---

# 2. Critical project invariants

These are non-negotiable.

## 2.1. Production stays Python-native

The installed package must not require or invoke:

```text
Java
JRE/JDK
LanguageTool CLI
LanguageTool HTTP server
a locally running oracle
network access
Natasha
pymorphy
another NLP backend
```

Java remains development/test oracle machinery only.

---

## 2.2. Compatibility semantics must not regress

Preserve the accepted Task-0014 state:

```text
Russian XML source rules:       892 / 892 runnable
grammar examples:               2446 / 2446 runnable
compiled XML variants:          907 / 907
ordinary Java-rule ports:       23 / 23
XML filters:                    7 / 7

Task-0014 unique texts:          9637
Task-0014 profile executions:   16871
Task-0014 comparable cases:     16834
Task-0014 exact comparable:     16834
ordinary unexplained mismatch:  0
ordinary allowlist entries:     0
```

The 37 non-comparable Java cases are the already documented pinned
`ParagraphRepeatBeginningRule` upstream defect.

Do not reinterpret them as Python failures.

---

## 2.3. Language-model rule remains deferred

Do not implement this rule in Task 0015:

```text
RussianConfusionProbabilityRule
```

Its status remains:

```text
LANGUAGE_MODEL_DEFERRED
```

Do not advertise the project as reproducing this LM rule.

---

## 2.4. Do not update the LanguageTool pin

Do not move from:

```text
e807fcde6a6506191e1470744d2345da28c26be6
```

Task 0015 may document the future update process, but it must not perform an upstream
upgrade.

---

# 3. Current package state at the baseline

At the Task-0015 baseline, `pyproject.toml` contains approximately:

```toml
[project]
name = "pylat_ru"
version = "0.1.0a0"
description = "Native Python reimplementation of the Russian LanguageTool pipeline and rule engine"
readme = "README.md"
license = { text = "LGPL-2.1-or-later" }
requires-python = ">=3.10"

dependencies = [
    "regex>=2024.5.15,<=2026.7.19",
]
```

Current classifiers claim:

```text
Python 3.10
Python 3.11
Python 3.12
Operating System :: OS Independent
```

Current package version is also exposed in:

```python
pylat_ru.__version__ == "0.1.0a0"
```

Do not blindly change the version number just because this task is called
"release readiness".

A version change is allowed only if the repository already has an explicit release
policy requiring it or the task implementation introduces a documented,
well-justified release-candidate version.

The default safe choice is:

```text
keep 0.1.0a0
```

while making the package release-ready.

---

# 4. Current documentation problem

`README.md` is stale.

It still says roughly:

```text
Task 0001 complete
parity incomplete
active foundational development
```

That is no longer true.

Task 0015 must make the README accurately describe the accepted Task-0014 state without
overclaiming.

It should distinguish:

```text
ordinary/non-LM Russian compatibility
vs
the deferred language-model rule
```

---

# 5. Task completion philosophy

Do not turn this into a redesign.

The project has already spent substantial effort proving exact behavior.

Task 0015 should prefer:

```text
audit
document
package
measure
stabilize
test
```

over:

```text
refactor everything because a cleaner abstraction occurred to the executor
```

Production code changes are allowed when required for:

- packaging correctness;
- public API stability;
- cross-platform correctness;
- reproducible initialization/resource access;
- measured pathological performance issue;
- clear installation failure.

Every production behavior change must retain all previous parity tests.

---

# 6. Primary public API

The primary user-facing API for the first release-readiness milestone is:

```python
from pylat_ru import LanguageToolRU, RuleMatch, __version__
```

and especially:

```python
tool = LanguageToolRU()
matches = tool.check("Текст.")
```

Task 0015 must explicitly stabilize and document this surface.

---

# 7. Current LanguageToolRU API to preserve

At the baseline:

```python
LanguageToolRU(
    disabled_rules: Sequence[str] | None = None,
    enabled_rules: Sequence[str] | None = None,
    rule_config: Mapping[str, Mapping[str, Any]] | None = None,
)
```

and:

```python
LanguageToolRU.check(
    text: str,
    level: str = LEVEL_DEFAULT,
) -> List[RuleMatch]
```

Task 0014 added actual:

```text
DEFAULT
PICKY
```

checking-level semantics.

Do not remove this behavior.

---

# 8. RuleMatch public contract

Current `RuleMatch` fields include:

```text
rule_id
category_id
message
offset
length
replacements
short_message
source
category_name
url
priority
full_rule_id
tags
registration_order
included_in_errors_corrected_all_at_once
original_error
utf16_offset
utf16_length
```

Task 0015 must document which of these are primary user-facing fields and what their
coordinate domains mean.

At minimum clearly document:

```text
offset / length:
Python Unicode code-point indices into the original input text

utf16_offset / utf16_length:
UTF-16 code-unit positions compatible with Java LanguageTool indexing

replacements:
ordered suggestions; order and duplicates are meaningful

rule_id:
base LanguageTool rule ID

full_rule_id:
physical/full rule ID when the upstream rule surface provides one
```

Do not silently rename existing fields.

---

# 9. Stable API vs advanced API

The current `pylat_ru.__all__` exposes many lower-level classes:

```text
AnalyzedSentence
AnalyzedToken
MorfologikDictionary
RussianHybridDisambiguator
RussianJavaRulesEngine
RussianSentenceAnalyzer
RussianSentenceTokenizer
RussianSynthesizer
RussianTag
RussianTagger
RussianWordTokenizer
...
```

Do **not** remove them in Task 0015.

Removing exports at this point would create an unnecessary breaking change.

Instead document two levels:

## Stable primary surface

```text
LanguageToolRU
RuleMatch
__version__
```

## Advanced/provisional surface

The existing analysis/tokenization/tagging/synthesis classes remain available, but their
API stability is not yet promised at the same level.

This distinction belongs in README/API documentation.

---

# 10. Public API snapshot

Create a machine-readable committed snapshot:

```text
compat/public_api_0015.json
```

It must record at least:

```text
schema_version
task
package_name
package_version
primary_public_symbols
all_exported_symbols
LanguageToolRU.__init__ signature
LanguageToolRU.check signature
RuleMatch ordered field list
RuleMatch field defaults where applicable
checking levels
offset-domain description
```

Do not snapshot internal private functions.

Add Java-free tests proving the implementation still conforms to this snapshot.

The test should fail if somebody accidentally:

- removes a primary symbol;
- changes positional/keyword API unexpectedly;
- removes a RuleMatch field;
- changes default checking level;
- changes DEFAULT/PICKY names.

Do not overconstrain implementation-only annotations or source line numbers.

---

# 11. Checking-level constants

Audit how `DEFAULT` and `PICKY` are currently exposed.

The user should not have to rely on a magic string with no documentation.

Acceptable outcomes include:

1. documented strings:
   ```python
   tool.check(text, level="PICKY")
   ```

2. documented exported constants:
   ```python
   LEVEL_DEFAULT
   LEVEL_PICKY
   ```

3. a backwards-compatible enum plus string support.

Prefer the **smallest backwards-compatible change**.

Do not introduce an enum only for aesthetic reasons if constants already solve the
problem cleanly.

Unknown levels must continue to fail explicitly rather than silently becoming DEFAULT.

---

# 12. Version-source audit

Currently version information exists in at least:

```text
pyproject.toml
pylat_ru.__version__
```

Task 0015 must ensure these cannot silently drift.

Two acceptable approaches:

## Preferred if clean

Create one version source of truth that both packaging and runtime expose.

## Acceptable minimal solution

Keep both declarations but add a fail-closed packaging test proving:

```text
built distribution metadata version
==
pyproject version
==
pylat_ru.__version__
```

Do not add a heavy versioning dependency merely to remove one duplicate literal.

---

# 13. Package metadata audit

Review `pyproject.toml`.

Verify and correct as appropriate:

```text
name
version
description
readme
requires-python
license metadata
authors
classifiers
dependencies
optional dev/release dependencies
project URLs
```

Add useful project URLs if they can be resolved from the repository:

```text
Repository
Issues
```

Do not invent a homepage or documentation site that does not exist.

---

# 14. Python support policy

The package currently claims:

```text
Python >= 3.10
Python 3.10
Python 3.11
Python 3.12
```

Task 0015 must mechanically validate all explicitly claimed minor versions.

Minimum release-preflight expectation:

```text
Linux Python 3.10
Linux Python 3.11
Linux Python 3.12
```

The full ordinary test suite may continue to run on 3.10 and 3.12 if CI runtime is a
concern, but Python 3.11 must at minimum receive a clean-artifact install + public API
smoke.

Preferred:

```text
full tests on 3.10 and 3.12
artifact smoke on 3.11
```

If adding full 3.11 is cheap enough, that is better.

Do not claim a Python version that is not exercised anywhere.

---

# 15. Operating-system claim

`pyproject.toml` currently says:

```text
Operating System :: OS Independent
```

The package is pure Python, but resource paths and packaged dictionaries make a
cross-platform smoke valuable.

Add a Windows release-preflight smoke, preferably:

```text
windows-latest
Python 3.12
```

It does not need to run the entire expensive parity suite.

It must:

1. install the **built wheel**, not editable source;
2. import `pylat_ru`;
3. construct `LanguageToolRU`;
4. run representative checks;
5. load runtime dictionary/XML resources;
6. verify no Java;
7. verify non-BMP offsets;
8. verify DEFAULT and PICKY public calls.

If the existing package fails on Windows due to an actual path/packaging issue, fix it.

Do not add OS-specific behavior merely to make a test green.

---

# 16. Build tooling

Task 0015 must establish a reproducible release-preflight build command.

Recommended:

```bash
python -m build
```

If required, add development/release dependencies such as:

```text
build
twine
```

Keep them out of runtime dependencies.

The runtime dependency surface should remain minimal.

---

# 17. Wheel and sdist

Build both:

```text
wheel
sdist
```

Do not publish either artifact.

Expected filenames depend on retained version.

If version remains `0.1.0a0`, conceptually:

```text
pylat_ru-0.1.0a0-py3-none-any.whl
pylat_ru-0.1.0a0.tar.gz
```

Use actual filenames from the build.

---

# 18. Wheel-content policy

The wheel is the production artifact.

It must contain only what production needs plus standard distribution metadata.

It must contain:

```text
pylat_ru Python modules
py.typed
required runtime JSON/XML/TXT resources
required dictionaries/FSA data
required package metadata/license files
```

It must **not** contain:

```text
tools/
tasks/
reports/
tests/
corpora/
test_corpora/
.oracle_cache/
oracle/
oracle_downloads/
Java source
.class files
.jar files
campaign JSONL
Git metadata
temporary build files
```

A machine-readable wheel audit must enforce this.

---

# 19. Sdist-content policy

An sdist may legitimately include developer source/test material.

Therefore do not impose wheel rules blindly on the sdist.

However the sdist must not accidentally contain:

```text
external natural corpora
oracle JARs
oracle cache/downloads
local differential campaign results
virtual environments
pytest caches
build output
secrets
credentials
```

Explicitly audit this.

---

# 20. Package-content inventory

Create:

```text
compat/package_contents_0015.json
```

Record from a clean build:

```text
schema_version
task
package_version

wheel:
  filename
  size_bytes
  file_count
  package_files
  largest_files
  forbidden_file_matches

sdist:
  filename
  size_bytes
  file_count
  forbidden_file_matches

runtime_resource_totals
```

Do not commit the actual `dist/` artifacts unless the repository already has a policy
requiring it.

Normally:

```text
dist/
```

remains generated/uncommitted.

Hashes of post-final-commit CI artifacts belong in the final handoff/CI artifact
manifest, not in a recursive post-CI docs commit.

---

# 21. Clean wheel installation test

A real wheel install is mandatory.

Do not accept:

```bash
pip install -e .
```

as release evidence.

Create a temporary clean environment and install the built wheel.

Then run a script equivalent to:

```python
from pylat_ru import LanguageToolRU, RuleMatch, __version__

tool = LanguageToolRU()
matches = tool.check("Это тест.")

assert isinstance(matches, list)
assert all(isinstance(item, RuleMatch) for item in matches)
```

Also execute an input that produces at least one finding, so successful import alone
cannot pass the smoke.

---

# 22. Required installed-wheel smoke cases

Use representative cases covering distinct runtime resources.

At minimum:

## XML grammar

A text known to produce a Russian XML grammar finding.

## Native Java-rule port

A text known to trigger one ordinary native rule.

## Spelling

A controlled misspelling with a pinned stable finding.

## DEFAULT/PICKY

One controlled text proving:

```text
DEFAULT excludes a picky result
PICKY exposes it
```

## Non-BMP

One text with emoji or supplementary Unicode before a match, validating both:

```text
offset
utf16_offset
```

## Config

At least one `rule_config` example.

These are smoke tests, not replacements for Task-0014 differential evidence.

---

# 23. Sdist installation test

Build an sdist and install it into another fresh environment.

Verify:

```text
build succeeds
installation succeeds
pip check succeeds
same primary API smoke succeeds
```

This catches missing package-data declarations that a local editable install conveniently
hides, because editable installs are extremely polite about concealing packaging mistakes.

---

# 24. Metadata validation

Run an artifact metadata validator.

Recommended:

```bash
python -m twine check dist/*
```

or a comparably standard mechanism.

Required:

```text
wheel metadata: PASS
sdist metadata: PASS
README rendering metadata validation: PASS
```

Warnings that indicate malformed metadata must be fixed.

Do not publish to TestPyPI/PyPI in this task.

---

# 25. Runtime dependency audit

Create a release check proving the installed wheel's runtime dependency set is exactly
intentional.

At the current baseline the only declared runtime dependency is:

```text
regex
```

If another runtime dependency is added, it must have an explicit reason in the report.

Forbidden production dependencies include:

```text
pytest
pytest-cov
build
twine
Java bridges
requests solely for oracle/network access
Natasha
pymorphy
```

Development dependencies may include build/test tools.

---

# 26. No-runtime-network proof

Retain the existing no-subprocess/no-socket evidence and extend the installed-wheel smoke
where practical.

A normal:

```python
LanguageToolRU().check(...)
```

must not require:

```text
socket
HTTP
subprocess
Java
external service
```

Do not monkeypatch so broadly that unrelated standard-library internals fail.

Use a focused fail-closed proof around the checker call.

---

# 27. Licensing and provenance audit

The package uses LanguageTool-derived/vendored resources.

The repository already contains license/provenance material under areas such as:

```text
LICENSE
third_party/languagetool/LICENSES.md
third_party/languagetool/license_inventory.json
```

Task 0015 must audit these rather than invent a new legal model.

Verify:

1. root license exists;
2. package metadata license agrees with repository policy;
3. every shipped upstream-derived runtime resource class is represented by provenance;
4. wheel contains the license material required for distribution;
5. no resource with unresolved/blocked licensing state is shipped;
6. generated package-content audit can trace shipped major data files to the existing
   license inventory.

Do not make legal claims beyond the repository evidence.

If an ambiguity is found, report it explicitly rather than guessing.

---

# 28. README rewrite

Update README from implementation-history documentation into usable package documentation.

It should contain at least:

## What it is

Native Python implementation of pinned Russian LanguageTool behavior.

## Current compatibility statement

Accurately state:

```text
ordinary/non-LM Russian pipeline parity was demonstrated against pinned LT 6.8
commit e807fc...
```

Do not merely say "100% LanguageTool compatible".

Explicitly mention:

```text
RussianConfusionProbabilityRule is not implemented
```

## Installation

For the current repository state:

```bash
pip install ...
```

If the package is not actually published on PyPI, do **not** falsely tell users:

```bash
pip install pylat_ru
```

as though PyPI publication already exists.

Instead distinguish:

```text
install from built wheel
install from source/repository
future PyPI command, only when published
```

## Basic usage

```python
from pylat_ru import LanguageToolRU

tool = LanguageToolRU()
for match in tool.check("..."):
    ...
```

## Rule control

Examples for:

```text
enabled_rules
disabled_rules
rule_config
```

## DEFAULT / PICKY

Show public syntax.

## Match fields and offsets

Explain code-point and UTF-16 coordinates.

## Production dependencies

State that Java/server is not required.

## Known limitation

LM rule deferred.

## Compatibility pin

State exact LT version/commit.

## License/provenance

Link to repository files.

---

# 29. README examples must be executable

Do not let README become another untested mythology layer.

Add Java-free tests for the important code examples.

Acceptable approaches:

- dedicated tests that execute equivalent snippets;
- doctest only if it fits cleanly;
- a small example script imported/tested by CI.

At minimum verify:

```text
basic check
DEFAULT/PICKY example
rule enable/disable example
rule_config example
```

---

# 30. Release notes / known limitations

Create or update a compact release-readiness section, preferably in:

```text
reports/0015_release_readiness.md
```

Do not manufacture a long CHANGELOG unless the repository already wants one.

The report must clearly list:

```text
Pinned LanguageTool version
ordinary parity status
LM deferral
Python support
platform smoke
runtime dependency set
artifact status
```

---

# 31. Performance objective

Task 0015 must establish a reproducible Python-native performance baseline.

This is a measurement/stability task, not a contest to produce suspiciously tiny numbers.

Do not optimize before measuring.

---

# 32. Benchmark tool

Create a development-only tool such as:

```text
tools/benchmark_0015.py
```

It must not be imported by production.

It should support a deterministic command such as:

```bash
python -m tools.benchmark_0015
```

Prefer optional arguments for:

```text
repeat count
warmup count
JSON output path
```

No external corpus download.

Use committed synthetic/short benchmark inputs so another checkout can reproduce the
suite.

---

# 33. Benchmark dimensions

Measure separately:

## Construction / cold initialization

Time:

```python
LanguageToolRU()
```

Record cold process construction separately from already-imported construction if practical.

## Warm check

Reuse one constructed instance.

Required text classes:

```text
short clean Russian
short text with grammar/punctuation errors
short spelling-heavy text
medium naturalistic/synthetic Russian
long Russian text
PICKY case
configured speller/rule case
```

Do not benchmark a single toy sentence and call the package characterized.

---

# 34. Benchmark sizes

Use explicit code-point/byte sizes in the output.

Recommended approximate classes:

```text
short:   ~100–300 chars
medium:  ~1–3 KiB
long:    ~10–30 KiB
```

Exact committed text is more important than these approximate ranges.

Keep the suite short enough to be practical locally.

---

# 35. Benchmark statistics

For repeated measurements record at least:

```text
iterations
warmups
median
min
max
p95 or nearest deterministic percentile
characters_per_second where meaningful
```

Do not report only one wall-clock sample.

---

# 36. Memory baseline

Record memory behavior using a portable or clearly platform-scoped method.

At minimum measure:

```text
process RSS before checker construction
RSS after construction
RSS after warmup
RSS after repeated checks
```

If RSS collection is Linux-specific, say so explicitly.

Do not claim cross-platform memory parity from Linux-only measurements.

---

# 37. Long-lived stability

Add a bounded soak-style benchmark/test.

For example:

```text
construct one LanguageToolRU
run a deterministic mixed workload repeatedly
record time and RSS at intervals
```

The purpose is to detect:

- dictionaries being reloaded repeatedly;
- unbounded suggestion cache growth;
- per-check accumulation;
- mutable cross-document leakage.

Do not run a multi-hour soak in ordinary CI.

A few hundred or low-thousands of checks is sufficient for a bounded release-preflight.

---

# 38. Performance gates must not be flaky

Do **not** add strict CI assertions like:

```text
must finish in 0.137 seconds
```

Shared GitHub runners make such gates nonsense.

Use two types of protection:

## Structural/non-flaky tests

Examples:

```text
binary dictionaries loaded once/shared as designed
suggestion cache remains bounded
checker does not rebuild grammar resources every check
no subprocess/socket
state does not leak
```

## Recorded benchmark baseline

Store measured values for human comparison, but do not fail ordinary CI on a small
wall-clock fluctuation.

A very broad pathological guardrail is acceptable only if it catches orders-of-magnitude
regressions and has generous headroom.

---

# 39. Performance artifact

Create:

```text
compat/performance_baseline_0015.json
```

It must contain:

```text
schema_version
task
Python version
platform
benchmark suite version
input IDs and sizes
warmup/repeat counts
construction timing
per-case timings
memory measurements
long-lived workload measurements
notes on measurement limitations
```

Do not hand-enter measured timings.

Generate them from the benchmark tool.

---

# 40. Performance report interpretation

`reports/0015_release_readiness.md` must summarize the baseline.

State clearly what is and is not proven.

For example:

```text
Measured on Linux/Python 3.12
not a cross-machine SLA
useful as a regression baseline
```

Do not write marketing claims such as "10x faster" unless actually compared through a fair,
documented benchmark.

Java-vs-Python speed comparison is **not required** for Task 0015.

---

# 41. Resource initialization audit

Inspect construction and repeated check behavior.

Verify expensive immutable resources are not needlessly reparsed/reloaded every check.

Examples include:

```text
Morfologik dictionaries
grammar XML/compiled rules
tagger data
synthesis data
disambiguation data
spelling resources
```

Do not globally singleton-ize mutable objects just to improve timing.

Preserve state isolation.

If caching is changed, add tests for:

```text
configuration isolation
thread/concurrency behavior
fresh-instance semantics
```

---

# 42. Concurrency smoke

Task 0013 already established important concurrency evidence.

Task 0015 should preserve it and add an installed-wheel concurrency smoke if cheap.

At minimum:

```text
separate LanguageToolRU instances in parallel
```

If shared-instance thread safety is already accepted and tested, retain that evidence.

Do not introduce a new public thread-safety promise beyond what tests actually prove.

Document the tested behavior precisely.

---

# 43. Package size audit

Russian dictionaries may make the wheel non-trivial.

Record:

```text
wheel total size
sdist total size
largest 20 files
runtime resource subtotal
Python source subtotal if practical
```

Do not set an arbitrary tiny size limit.

Instead identify accidental bloat:

- duplicate dictionaries;
- duplicated grammar assets;
- oracle fixtures;
- external corpora;
- cached/generated files.

Any unexpected duplicate multi-megabyte payload should be investigated.

---

# 44. Reproducible-build audit

Perform at least two clean builds from the same source state.

Compare:

```text
member names
member sizes
member content hashes
metadata
```

Byte-identical ZIP/TAR artifacts are desirable but not mandatory because timestamps/build
metadata can differ.

If `SOURCE_DATE_EPOCH` makes byte-identical builds straightforward, use it.

Otherwise record:

```text
SEMANTICALLY_REPRODUCIBLE
```

only when extracted member content is identical.

Do not claim byte reproducibility when only filenames match.

---

# 45. Reproducibility artifact

Add machine-readable evidence to:

```text
compat/package_contents_0015.json
```

or a separate:

```text
compat/build_reproducibility_0015.json
```

Record:

```text
two-build comparison mode
byte-identical yes/no
member-set-identical
member-content-identical
differences if any
```

Fail if runtime member content differs between two clean builds from the same source.

---

# 46. Installed artifact must not depend on repository cwd

Run smoke tests from a temporary directory outside the repository.

For example:

```text
cwd = tempdir
```

Then import and check text.

This catches accidental relative-path resource access.

The test must not have the repository root on `PYTHONPATH`.

---

# 47. Installed artifact must not see source tree accidentally

When testing wheel/sdist installation:

- create fresh venv;
- change cwd outside repo;
- remove/avoid repo from `PYTHONPATH`;
- verify `pylat_ru.__file__` points into the venv installation.

Print the path in release-preflight logs.

---

# 48. `pip check`

After each clean artifact install:

```bash
python -m pip check
```

must succeed.

---

# 49. Import-time sanity

Audit import behavior.

Basic:

```python
import pylat_ru
```

should not:

- start Java;
- spawn subprocesses;
- open sockets;
- perform network access;
- eagerly execute the entire grammar checker;
- emit warnings/errors in a normal environment.

Do not micro-optimize import time unless measurements show a real problem.

---

# 50. Error behavior documentation

Document expected failures for obvious misuse:

```text
unknown checking level
unknown rule_config key
missing/corrupt runtime resource
```

Do not silently swallow these.

Existing fail-closed behavior should remain.

---

# 51. Upstream update/runbook

Document how a future maintainer moves from the current LT pin to another upstream commit.

Create something like:

```text
docs/upstream_update.md
```

or an appropriately named repository document.

It should describe the real existing tooling rather than invent new commands.

At minimum:

1. update pinned upstream source;
2. regenerate source inventories;
3. run upstream drift detection;
4. regenerate affected oracle fixtures;
5. rerun grammar/rule parity;
6. rerun upstream-test parity;
7. rerun Task-0014 differential campaign;
8. inspect new/deleted rules/resources;
9. update licensing/provenance if files change;
10. only then claim compatibility with the new pin.

Do not update the pin in Task 0015 itself.

---

# 52. Existing upstream drift tool

The repository already contains upstream-diff tests/tooling.

Audit it and document the actual invocation.

If a small missing CLI wrapper prevents a maintainer from using it, adding one is acceptable.

Do not build an entirely new updater when the existing machinery is sufficient.

---

# 53. Compatibility statement artifact

Create:

```text
compat/release_readiness_0015.json
```

Suggested structure:

```json
{
  "schema_version": "...",
  "task": "0015",
  "baseline": "...",
  "package_version": "...",
  "primary_api": "...",
  "python_support": {...},
  "platform_smoke": {...},
  "artifact_build": {...},
  "metadata_validation": {...},
  "wheel_audit": {...},
  "sdist_audit": {...},
  "clean_install": {...},
  "licensing": {...},
  "performance": {...},
  "task_0014_compatibility_preserved": true,
  "language_model_rule": {
    "status": "LANGUAGE_MODEL_DEFERRED"
  }
}
```

Values must come from tests/build evidence.

Do not fill PASS fields before proving them.

---

# 54. Avoid the commit-SHA recursion problem

Task 0014 already demonstrated how humans can create an infinite sequence of:

```text
commit
CI
docs commit recording CI
new SHA
CI no longer exact
```

Do not repeat it.

Committed release-readiness evidence may identify the Task-0015 implementation source in a
non-recursive way, but **GitHub Actions run IDs and final built-artifact hashes from the
exact final commit belong in the final handoff only**.

Do not create a post-CI documentation commit.

---

# 55. Release-preflight CI

Extend CI or add a separate workflow/job for release readiness.

The existing ordinary test suite must remain.

Recommended structure:

## Existing full tests

```text
Ubuntu
Python 3.10
Python 3.12
0 failed / 0 errors / 0 skipped
```

## Python 3.11 artifact smoke

Build/install or reuse exact artifacts.

## Linux release-preflight

On a supported Python version, preferably 3.12:

```text
build wheel + sdist
metadata validation
wheel content audit
sdist content audit
clean wheel install
clean sdist install
pip check
README/API smoke
no-Java/no-network smoke
artifact manifest generation
```

## Windows artifact smoke

```text
windows-latest
Python 3.12
install wheel
run primary API/resource smoke
```

Do not require Java for any release-preflight job.

---

# 56. Build once where practical

For one CI run, prefer building release artifacts once and reusing/uploading them rather
than independently producing subtly different wheels in every job.

However do not create a complicated workflow dependency graph if simpler independent builds
are more robust.

At minimum every artifact-smoke job must prove exactly what artifact/source it tested.

---

# 57. CI artifact manifest

During exact-final-SHA CI, generate a machine-readable manifest as an uploaded CI artifact,
not a post-CI repository commit.

Include:

```text
source SHA
package version
wheel filename
wheel SHA-256
wheel size
sdist filename
sdist SHA-256
sdist size
metadata validation result
content-audit result
```

This provides release artifact identity without changing the repository after CI.

---

# 58. No publication

Task 0015 explicitly stops before:

```text
PyPI upload
TestPyPI upload
GitHub Release publication
tag creation
version release tag
```

Do not publish anything unless separately instructed after Task 0015 is accepted.

---

# 59. Required tests

Add focused Java-free tests for at least:

## API

- primary symbols exist;
- public API snapshot matches;
- `LanguageToolRU.__init__` signature;
- `LanguageToolRU.check` signature/default;
- RuleMatch field order;
- checking levels;
- package metadata/runtime version agree.

## README/examples

- basic example works;
- DEFAULT/PICKY example works;
- enable/disable example works;
- rule_config example works.

## Packaging

- wheel contains required resources;
- wheel contains no forbidden dev/oracle/corpus material;
- sdist contains no forbidden local/corpus/oracle cache;
- installed wheel works outside repository;
- installed sdist works outside repository;
- `pip check` passes;
- distribution metadata version matches runtime.

## Licensing

- license files present;
- shipped major resource inventory reconciles with provenance;
- no blocked license entry shipped.

## Performance structure

- expensive dictionary/resource loading is reused where designed;
- bounded caches remain bounded;
- repeated checks do not spawn subprocesses/open sockets;
- benchmark suite inputs are deterministic.

## Release metadata

- `compat/public_api_0015.json` integrity;
- `compat/package_contents_0015.json` integrity;
- `compat/performance_baseline_0015.json` structure;
- `compat/release_readiness_0015.json` arithmetic/status consistency.

---

# 60. Full regression

After focused tests:

```bash
python -m pytest
```

Required:

```text
0 failed
0 errors
0 skipped
```

Task-0014 final exact-SHA CI had:

```text
1139 passed
```

Task 0015 will add tests, so do not hard-code 1139 as the new target.

---

# 61. Do not rerun the full 16k Java differential campaign unnecessarily

Task 0015 is not a semantic LanguageTool implementation milestone.

If Task 0015 changes only:

```text
packaging
docs
tests
CI
benchmark tooling
```

do not burn time rerunning the full live Java Task-0014 campaign.

The committed Task-0014 regression/parity evidence must remain green.

However, if Task 0015 makes a production semantic change under:

```text
src/pylat_ru/
```

that could alter checking output, then run the relevant differential subset and, if the
change is broad, rerun the full Task-0014 campaign.

Document why.

---

# 62. Performance changes require parity discipline

If benchmarking uncovers a performance issue and production code is optimized:

1. preserve exact output;
2. add targeted parity regression;
3. run full ordinary pytest;
4. run relevant Task-0014 regression fixture;
5. run state/concurrency tests;
6. if the optimization affects grammar/tagging/spelling semantics broadly, rerun live
   differential evidence.

Never trade exact LanguageTool compatibility for a prettier benchmark number.

---

# 63. Report

Create:

```text
reports/0015_release_readiness.md
```

It must include:

1. baseline SHA;
2. task scope;
3. package version decision;
4. primary stable API;
5. advanced/provisional API policy;
6. Python version support;
7. OS/platform test coverage;
8. wheel build result;
9. sdist build result;
10. wheel size/file count;
11. sdist size/file count;
12. largest packaged runtime files;
13. forbidden-content audit;
14. clean wheel install result;
15. clean sdist install result;
16. `pip check`;
17. metadata validation;
18. licensing/provenance status;
19. README/API documentation status;
20. benchmark environment;
21. construction timing;
22. warm-check timing table;
23. memory baseline;
24. bounded soak result;
25. reproducible-build result;
26. Task-0014 compatibility preservation;
27. known limitations;
28. LM rule status;
29. publication status = NOT PUBLISHED;
30. exact-SHA CI intentionally recorded only in final handoff.

---

# 64. README compatibility wording

Use precise wording.

Good style:

```text
pylat_ru reproduces the ordinary/non-language-model Russian checking pipeline of
LanguageTool 6.8 at pinned commit e807fc..., with full observable parity on the
committed upstream and differential evidence suites.
```

Then immediately state:

```text
RussianConfusionProbabilityRule is intentionally not implemented because it depends on
LanguageTool's language-model subsystem.
```

Avoid:

```text
100% identical to all of LanguageTool
```

because that would be false.

---

# 65. Package usage example

README should contain a useful minimal example approximately like:

```python
from pylat_ru import LanguageToolRU

tool = LanguageToolRU()

for match in tool.check("Пример текста"):
    print(match.rule_id)
    print(match.message)
    print(match.offset, match.length)
    print(match.replacements)
```

Use a concrete Russian text whose behavior is stable under tests.

---

# 66. Picky example

Document a deterministic example such as:

```python
tool.check(text, level="DEFAULT")
tool.check(text, level="PICKY")
```

The example must be tested and must actually demonstrate an observable difference.

Do not use an example where both outputs are accidentally empty.

---

# 67. Rule-config example

Show an actual supported configuration from the implementation, for example a proven
Task-0014 configuration.

Possible examples include:

```text
TOO_LONG_SENTENCE maxWords
MORFOLOGIK_RULE_RU_RU conf_ru_Value
```

Use the least confusing user-facing example.

The README example must match actual accepted key spelling exactly.

---

# 68. Offset example

Include one short explanation or example showing:

```text
offset / length
```

are Python indices while:

```text
utf16_offset / utf16_length
```

are useful when interoperating with Java/UTF-16 clients.

Do not tell users to use UTF-16 offsets for Python slicing.

---

# 69. Resource provenance

The package contains large upstream-derived data.

The documentation should not pretend these are authored from scratch by `pylat_ru`.

Preserve attribution and point to the existing third-party inventory.

---

# 70. Build cleanliness

Before final commit:

```bash
git status --short
```

must not show accidental:

```text
dist/
build/
*.egg-info/
coverage files
benchmark temp files
campaign results
venvs
downloaded corpora
oracle artifacts
```

Update `.gitignore` if a normal release workflow creates legitimate generated paths that are
currently unignored.

Do not ignore source evidence just to hide dirt.

---

# 71. Suggested new files

A clean implementation will likely add something like:

```text
compat/public_api_0015.json
compat/package_contents_0015.json
compat/performance_baseline_0015.json
compat/release_readiness_0015.json

reports/0015_release_readiness.md

tools/benchmark_0015.py
tools/release_preflight_0015.py   # optional if it keeps audit logic clean

docs/upstream_update.md            # or equivalent

tests/unit/test_public_api_0015.py
tests/unit/test_packaging_0015.py
tests/unit/test_release_readiness_0015.py
tests/unit/test_readme_examples_0015.py
tests/unit/test_performance_evidence_0015.py
```

Exact decomposition is up to the implementation.

Do not create five tiny tools where one clear module is enough.

---

# 72. Existing files likely to change

Likely:

```text
README.md
pyproject.toml
.gitignore
.github/workflows/ci.yml
src/pylat_ru/__init__.py   # only if API constants/version exposure requires a small change
```

Possibly:

```text
third_party licensing metadata
```

only if the audit finds a real omission.

Avoid unrelated production refactors.

---

# 73. Machine-readable evidence arithmetic

Tests must cross-check generated evidence.

Examples:

```text
wheel file_count == number of audited wheel members
largest files are sorted by size
forbidden matches list is empty
package version matches runtime
performance case IDs are unique
release-readiness PASS values correspond to underlying evidence
```

Do not permit manually edited "PASS" values to contradict machine evidence.

---

# 74. Performance baseline source binding

Performance varies by machine and does not need the Task-0014 immutable-campaign SHA
ceremony.

The committed performance JSON should record:

```text
source tree/task baseline
Python version
platform
CPU/environment description if available
```

Do not present its exact timings as universal thresholds.

The final exact-SHA CI artifact manifest can additionally record final source SHA.

---

# 75. Security / supply-chain sanity

This is not a full security audit, but release-preflight should verify obvious packaging
properties:

- runtime has the expected dependency list;
- no credentials/tokens are packaged;
- no local absolute paths appear in normal package metadata/evidence where avoidable;
- no oracle JAR/corpus accidentally ships;
- sdist/wheel file names do not contain temp directories;
- package imports from installed artifact, not repo checkout.

Do not add a large third-party vulnerability scanner unless already used by the project.

---

# 76. Runtime resource integrity

Existing resource hash tests should remain.

Task 0015 should ensure the real built wheel still contains those exact runtime resource
bytes.

A source-tree resource test is not enough.

At least one installed-wheel audit must hash/reconcile critical resource classes.

---

# 77. Package data fail-closed behavior

If a required resource is absent from the built wheel, tests must fail.

Do not allow source-tree fallback paths that make a broken wheel appear healthy.

---

# 78. Type metadata

The wheel currently includes:

```text
py.typed
```

Verify it is actually present in the real wheel.

If type hints are intentionally supported, preserve this marker.

Do not make a broad promise of complete static typing unless the project actually provides
it.

---

# 79. Installation documentation before publication

Because Task 0015 does not publish the project, README should be honest.

Good:

```bash
python -m build
pip install dist/pylat_ru-...
```

or installation from the repository if appropriate.

Do not imply an existing PyPI release if none exists.

---

# 80. Release artifact names and normalized project name

Audit the actual wheel/sdist names emitted by the build backend.

Document the real result rather than guessing how underscores/hyphens normalize.

Tests may derive expected names from distribution metadata rather than hard-coding an
assumption.

---

# 81. Acceptance criteria

Task 0015 is complete only when all of the following are true.

## Compatibility

```text
Task-0014 committed parity tests remain green
ordinary unexplained discrepancies remain 0
LM rule remains deferred
pin unchanged
```

## Public API

```text
LanguageToolRU documented
RuleMatch documented
__version__ documented
public API snapshot committed
DEFAULT/PICKY documented and tested
offset domains documented
```

## Packaging

```text
wheel builds
sdist builds
metadata validation passes
wheel forbidden-content audit passes
sdist forbidden-content audit passes
real wheel install passes outside repo
real sdist install passes outside repo
pip check passes
```

## Python/platform

```text
3.10 covered
3.11 covered
3.12 covered
Linux covered
Windows wheel smoke covered
```

## Licensing

```text
distribution license metadata coherent
required license files present
shipped resource provenance reconciled
no blocked/unresolved resource shipped silently
```

## Performance

```text
deterministic benchmark suite exists
performance baseline committed
construction measured
warm checks measured
memory measured
bounded long-lived workload measured
no flaky micro-timing CI gates
```

## Documentation

```text
README no longer says Task 0001/incomplete parity
basic usage works
rule control documented
PICKY documented
config documented
offsets documented
LM limitation documented
upstream pin documented
future upstream-update runbook exists
```

## CI

```text
all required jobs success
ordinary full pytest has 0 failed / 0 errors / 0 skipped
release-preflight succeeds
Windows smoke succeeds
exact final SHA proved
```

## Publication

```text
NOT PUBLISHED
```

---

# 82. Exact-final-SHA workflow

When implementation is complete:

1. run focused tests;
2. run full local pytest;
3. run local release-preflight;
4. inspect `git diff`;
5. ensure report/evidence are final;
6. create the final Task-0015 commit;
7. push to `main`;
8. record `FINAL_SHA`;
9. do not modify repository afterward;
10. wait for all exact-SHA CI/release-preflight jobs;
11. verify every required job used `FINAL_SHA`;
12. do not commit CI run IDs afterward.

If any repository file changes after the verified run:

```text
the old run is no longer final-SHA evidence
```

Run CI again on the new final SHA.

---

# 83. Required final handoff

Return concrete values, not prose like "everything passed".

Use this structure:

```text
Task 0015 final verification

baseline:
a80dfcfe019ee1cd6ffd26feee2a9313f60c195f

final main SHA:
<SHA>

package:
name: <name>
version: <version>
requires-python: <value>

Pinned LanguageTool:
version: 6.8
commit:
e807fcde6a6506191e1470744d2345da28c26be6

Primary stable API:
LanguageToolRU: PASS
RuleMatch: PASS
__version__: PASS
DEFAULT/PICKY: PASS

Task-0014 compatibility:
preserved: PASS
ordinary unexplained discrepancies: 0
RussianConfusionProbabilityRule:
LANGUAGE_MODEL_DEFERRED

Wheel:
filename: <filename>
size: <bytes>
SHA-256 from exact-final-SHA CI: <hash>
forbidden production files: 0
metadata validation: PASS
clean install outside repo: PASS
pip check: PASS

sdist:
filename: <filename>
size: <bytes>
SHA-256 from exact-final-SHA CI: <hash>
forbidden local/corpus/oracle files: 0
metadata validation: PASS
clean install outside repo: PASS
pip check: PASS

Python:
3.10: PASS
3.11: PASS
3.12: PASS

Platforms:
Linux: PASS
Windows artifact smoke: PASS

Licensing/provenance:
PASS
<notes if any>

Build reproducibility:
byte identical: <yes/no>
member set identical: <yes/no>
member content identical: <yes/no>

Performance environment:
Python: <version>
platform: <platform>

Construction:
median: <value>
p95: <value>

Warm checks:
<case>: median <value>, p95 <value>, throughput <value>
...

Memory:
before construction: <value>
after construction: <value>
after warmup: <value>
after bounded soak: <value>

Bounded soak:
iterations: <N>
result: PASS

Full pytest local:
<N> passed
0 failed
0 errors
0 skipped

Actions run ID:
<ID>

Actions run URL:
<URL>

Actions event:
push

Actions head_sha:
<FINAL_SHA>

Python 3.10 full tests:
job ID: <ID>
<N> passed / 0 failed / 0 errors / 0 skipped
checkout SHA: <FINAL_SHA>
conclusion: success

Python 3.12 full tests:
job ID: <ID>
<N> passed / 0 failed / 0 errors / 0 skipped
checkout SHA: <FINAL_SHA>
conclusion: success

Python 3.11 artifact smoke:
job ID: <ID>
checkout SHA: <FINAL_SHA>
conclusion: success

Linux release-preflight:
job ID: <ID>
checkout SHA: <FINAL_SHA>
conclusion: success

Windows wheel smoke:
job ID: <ID>
checkout SHA: <FINAL_SHA>
conclusion: success

Repository changes after verified CI:
none

Publication:
NOT PUBLISHED

FINAL:
READY FOR REVIEW
```

---

# 84. Stop condition

After completing Task 0015 and exact-SHA CI:

```text
STOP
```

Do not:

```text
publish to PyPI
publish to TestPyPI
create a GitHub Release
create a release tag
upgrade LanguageTool
implement the LM rule
start an unrequested Task 0016
```

The next step after review is a separate human decision about publication/versioning.

---

# 85. Definition of Done in one line

Task 0015 is done when a developer can take the exact final commit, build a clean
wheel/sdist, install them on supported Python versions without Java or repository
fallbacks, use a documented stable primary API, and inspect reproducible compatibility,
licensing, package-content and performance evidence, while all previously accepted
LanguageTool parity remains intact.
