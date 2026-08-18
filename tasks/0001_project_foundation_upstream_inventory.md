# Task 0001 — Project Foundation, Pinned Upstream, License Inventory, Russian Feature Inventory, Upstream Test Extraction, Conformance Harness

## Status

READY

## Goal

Create the reproducible foundation for `pylat_ru` before implementing the Russian grammar engine.

This task must answer, with machine-readable evidence:

- exactly which LanguageTool revision is the compatibility target;
- which Russian resources/rules/tests are part of that target;
- which XML constructs and filters the pinned Russian rules actually use;
- which Java/generic rules are enabled for Russian;
- what the license/provenance status of every vendored upstream file is;
- how future tasks will run extracted upstream tests and differential checks.

**Do not implement the grammar engine, tagger, disambiguator, synthesizer, spelling engine, or Russian Java-rule ports in this task.**

## Mandatory architectural constraints

Read and obey `AGENTS.md` and `docs/Handoff_pylat_ru.md`.

In particular:

- production runtime must not depend on Java/JRE or LanguageTool Server;
- Java is allowed only as an optional dev/test oracle;
- do not use Natasha or pymorphy as replacements for LT Russian semantics;
- unknown/unsupported constructs must never be silently ignored;
- Russian only for now;
- compatibility target must be an exact upstream commit, never floating `master`/`main`.

## Deliverables

### 1. Python project foundation

Create a minimal installable project skeleton suitable for later implementation, including at least:

```text
pyproject.toml
README.md
LICENSE
src/pylat_ru/__init__.py
tests/
tools/
third_party/languagetool/
```

Keep the public API intentionally minimal at this stage. A placeholder package import/version is enough; do not fake a working checker.

README must state clearly that:

- this is an independent project;
- it is not affiliated with or endorsed by LanguageTool;
- goal is a native Python reimplementation of the Russian LanguageTool pipeline/rule engine;
- Java/LanguageTool Server/Natasha/pymorphy are not production requirements;
- currently only Russian is targeted;
- parity status is incomplete until later tasks prove otherwise.

Use `LGPL-2.1-or-later` as the project working license unless the license inventory uncovers a concrete blocker that requires stopping and documenting the issue.

### 2. Select and pin one exact LanguageTool upstream revision

Determine a suitable current LanguageTool revision and pin its **exact commit SHA**.

Create:

```text
third_party/languagetool/UPSTREAM.json
```

It must include at minimum:

- upstream repository URL/identifier;
- exact commit SHA;
- retrieval timestamp/date;
- relevant Russian source/resource paths;
- SHA-256 for every vendored upstream file;
- tool/schema version for this metadata if useful.

Do not track a branch name as the compatibility identity.

Document why the selected revision was chosen.

### 3. License/provenance inventory before mass vendoring

Create a machine-readable license inventory plus a readable summary, for example:

```text
third_party/languagetool/LICENSES.md
third_party/languagetool/license_inventory.json
```

Inventory at minimum the Russian assets needed/planned by the handoff, including where present in the pinned revision:

- `grammar.xml`
- `disambiguation.xml`
- `russian.dict`
- `russian.info`
- `russian_synth.dict`
- `russian_synth.info`
- Hunspell/Morfologik Russian spelling resources
- `compounds.txt`
- `wordrootrep.txt`
- `replace.txt`
- `coherency.txt`
- `bitext.xml`
- tagset/tag description files
- manual add/remove lists and related Russian dictionary source lists
- relevant upstream Java source files that will be functionally ported or used for inventory/reference

Each item should carry fields equivalent to:

```text
path
upstream origin
copyright/license source
license
included/vendored?
status
notes
```

If license/provenance is not clear, mark:

```text
BLOCKED_LICENSE_REVIEW
```

Do not guess.

Avoid mass-vendoring questionable assets before this inventory exists.

### 4. Complete Russian module/resource inventory

Build tooling that derives the Russian compatibility surface from the **pinned revision**, rather than relying on the handoff's illustrative lists.

Create a tool such as:

```text
tools/upstream_inventory.py
```

It must produce deterministic machine-readable output under a sensible path such as:

```text
compat/inventory.json
```

Inventory at minimum:

#### Russian rule/resource files

- rule files in the Russian rule directory;
- important files under Russian resources;
- sizes/hashes where useful.

#### `grammar.xml` constructs

Extract the actual set/count/locations of:

- element names;
- attributes;
- filter classes;
- rule/category/rulegroup counts;
- examples and example types;
- any other compatibility-significant construct discovered.

Do not hard-code only the expected list from the handoff.

#### `disambiguation.xml` constructs

Extract actual elements/attributes/actions/features used by the pinned Russian disambiguation rules.

#### Russian Java rule set

Inspect pinned `Russian.java` and relevant registration/configuration code if needed and produce the actual set of enabled:

- Russian-specific Java rule classes;
- generic/shared LanguageTool rules activated for Russian;
- spelling/compound/repetition/etc. rule classes.

The handoff list is a lead, not source-of-truth.

#### XML filter classes

Extract the complete set of filter classes referenced by pinned Russian `grammar.xml`, with references to their upstream source files/classes where resolvable.

Unknown/unresolved classes must be reported explicitly.

### 5. Upstream Russian test inventory and extraction layer

Find the actual Russian LanguageTool upstream tests on the pinned revision.

Create tooling such as:

```text
tools/extract_upstream_tests.py
```

The task does **not** need to manually rewrite every JUnit test into Python yet.

It must, however:

- inventory relevant Russian JUnit/test sources;
- identify executable examples embedded in `grammar.xml`;
- extract `grammar.xml` examples into a stable machine-readable fixture format;
- produce counts and source references;
- distinguish tests that can be translated mechanically from those requiring semantic/manual ports;
- establish a location/schema for future pytest-compatible translated fixtures.

The extraction must be deterministic and rerunnable from the pinned upstream tree/resources.

### 6. Compatibility matrix/report schema

Create a machine-readable compatibility status artifact/schema that future tasks can update.

It should be able to represent at least:

```text
upstream revision
Russian rule count
XML constructs: supported / unsupported / partial
filters: implemented / total
Java rules: implemented / total
upstream tests: pass / fail / skipped / not-yet-ported
grammar.xml examples: pass / fail / not-yet-runnable
finding parity
span parity
suggestion parity
known differences
```

At Task 0001 most implementation-related entries will honestly be zero / not-yet-implemented. That is correct. Do not manufacture green metrics.

### 7. Optional Java oracle boundary

Create the scaffolding/documentation for an optional differential oracle, for example:

```text
tools/differential_lt.py
```

Requirements:

- oracle is development/test-only;
- absence of Java must not break `import pylat_ru`;
- oracle must target the same exact pinned LanguageTool revision;
- oracle setup/downloads should live in ignored local directories unless vendoring is explicitly licensed and intentional;
- no automatic LanguageTool download during library import/check;
- future output format should support structured comparison of findings, spans, messages, suggestions and rule IDs.

A full corpus campaign is **not** required in Task 0001.

### 8. Upstream drift detector

Create an initial tool such as:

```text
tools/upstream_diff.py
```

It must be designed to compare the pinned compatibility surface with another LT revision and report at least:

- added/removed/changed Russian rules/resources;
- new/removed XML elements/attributes;
- filter-class changes;
- `Russian.java` rule-set changes;
- dictionary/resource hash changes;
- test inventory changes where practical.

Do not automatically upgrade the pin.

### 9. Tests for Task 0001 tooling

Add focused tests proving that foundation/inventory tooling itself works.

At minimum cover:

- deterministic parsing/inventory on fixture XML;
- XML element/attribute/filter extraction;
- grammar example extraction;
- unsupported/unknown data is surfaced rather than silently discarded;
- metadata schema validation or equivalent structural checks;
- production package import succeeds without Java installed/running;
- dev-oracle code is not imported as a production dependency.

Tests may use tiny project fixtures instead of requiring a full Java oracle run.

## Expected repository shape after Task 0001

Exact layout may improve during implementation, but should be roughly:

```text
pylat_ru/
├─ pyproject.toml
├─ README.md
├─ LICENSE
├─ AGENTS.md
├─ .gitignore
├─ docs/
│  └─ Handoff_pylat_ru.md
├─ src/
│  └─ pylat_ru/
│     └─ __init__.py
├─ tests/
│  ├─ unit/
│  ├─ upstream/
│  ├─ conformance/
│  ├─ differential/
│  └─ fixtures/
├─ tools/
│  ├─ upstream_inventory.py
│  ├─ extract_upstream_tests.py
│  ├─ differential_lt.py
│  └─ upstream_diff.py
├─ compat/
│  ├─ inventory.json
│  └─ compatibility.json
├─ tasks/
│  └─ 0001_project_foundation_upstream_inventory.md
├─ reports/
└─ third_party/
   └─ languagetool/
      ├─ UPSTREAM.json
      ├─ LICENSES.md
      ├─ license_inventory.json
      └─ ... reviewed/pinned assets as appropriate
```

Do not create empty architectural theatre purely to satisfy this tree. Every committed directory/file should have a purpose.

## Acceptance criteria

Task 0001 is complete only if all are true:

1. Project is installable/importable as a minimal Python package.
2. Exact LanguageTool upstream commit is recorded.
3. Every vendored upstream file has SHA-256 and provenance/license status.
4. Russian rule/resource inventory is generated from pinned upstream, not copied manually from the handoff.
5. Actual `grammar.xml` elements/attributes/filter classes are inventoried.
6. Actual `disambiguation.xml` compatibility surface is inventoried.
7. Actual Russian-specific and relevant generic rule classes enabled by pinned Russian configuration are inventoried.
8. Relevant upstream Russian test sources are inventoried.
9. `grammar.xml` examples are extracted to deterministic fixtures.
10. A machine-readable compatibility matrix exists and honestly reports unimplemented areas.
11. Optional Java oracle is cleanly separated from production imports/runtime.
12. Initial upstream drift detection exists and has focused tests/proofs.
13. Unknown/unresolved inventory items are explicit; nothing significant is silently skipped.
14. License/provenance uncertainties are explicitly marked `BLOCKED_LICENSE_REVIEW`.
15. Focused test suite for Task 0001 passes.
16. Completion report is written under `reports/`.
17. `git diff` is reviewed.
18. Task is committed.
19. No push is performed by the coding agent.
20. Task 0002 is **not** started.

## Completion report

Create:

```text
reports/0001_project_foundation_upstream_inventory.md
```

Include:

- exact pinned LT commit;
- files/resources vendored and why;
- license inventory summary and blockers;
- counts of Russian rules/resources/tests/examples;
- discovered XML/disambiguation constructs;
- discovered filter classes;
- discovered Russian/generic Java rule classes;
- tooling created;
- tests run and results;
- known unsupported/unknown items;
- deviations from this task and rationale;
- next-task prerequisites, but do not implement Task 0002.