# AGENTS.md — pylat_ru

## 1. Mission

`pylat_ru` is a native Python reimplementation of the Russian-language pipeline and rule engine used by LanguageTool.

The project goal is **upstream compatibility**, not merely "a good Russian grammar checker".

Current scope:

- Russian only.
- Python production runtime only.
- No Java/JRE, LanguageTool server, Natasha, pymorphy, or another external NLP runtime as a semantic replacement for the LanguageTool Russian pipeline.

Java LanguageTool is allowed only as an optional **development/test oracle** for conformance and differential testing.

## 2. Source of truth

Read before implementation:

1. the active numbered task in `tasks/`;
2. `docs/Handoff_pylat_ru.md`;
3. relevant pinned upstream LanguageTool sources/resources once Task 0001 establishes them.

If sources disagree, do not silently invent a resolution. Record the conflict in the completion report and choose the least destructive path consistent with the active task.

## 3. Execution policy

For every numbered task:

1. Read the complete task and relevant project docs.
2. Inspect the current repository state before editing.
3. Implement **only the active numbered task** and directly necessary supporting work.
4. Run focused tests/proofs appropriate to that task.
5. Review `git diff` and remove accidental/unrelated changes.
6. Write a completion report in `reports/`.
7. Commit the completed task yourself.
8. **Do not push.**
9. **Do not begin the next numbered task automatically.**

A task is not complete merely because code exists. Its acceptance criteria and report must be satisfied.

## 4. Commit policy

- One intentional commit per completed numbered task unless the task explicitly requires otherwise.
- Commit message should identify the task, for example `chore: complete task 0001 project foundation`.
- Do not leave the task completed but uncommitted.
- Do not push, create a PR, merge, tag, or publish unless explicitly requested.

## 5. Compatibility rules

### 5.1 No silent unsupported behavior

Unknown or unsupported LanguageTool behavior must be explicit.

Examples:

- unknown XML element;
- unknown XML attribute;
- unknown filter class;
- unsupported rule type;
- unsupported morphology/tag feature;
- partially implemented behavior.

Do **not** silently ignore such cases. Fail clearly or mark them in a machine-readable compatibility inventory/report, according to the active task.

### 5.2 Upstream semantics first

Do not replace LanguageTool Russian semantics with a different NLP model just because it is easier.

In particular, do not use Natasha/pymorphy as an implementation shortcut for tokenization semantics, LT morphological analyses, LT POS/tag strings, disambiguation, or synthesis.

The Russian LanguageTool resources and pinned implementation are the behavioral reference.

### 5.3 Original rule/resource data

Prefer executing original pinned upstream Russian rule/resource data over manually rewriting thousands of rules into Python.

Vendored upstream files must have recorded provenance, exact revision, hashes, and license status.

A file with unclear license/provenance is `BLOCKED_LICENSE_REVIEW`, not "probably fine".

## 6. Production/runtime boundary

Production library code must not:

- invoke Java;
- invoke LanguageTool CLI;
- connect to a LanguageTool server;
- depend on localhost HTTP services;
- download LanguageTool during `check()` or import;
- require development oracle assets;
- depend on local corpora.

Development tooling may use a pinned official Java LanguageTool oracle, but it must live behind an explicit dev/test boundary and remain optional.

## 7. Testing policy

Prefer evidence in this order:

1. translated/upstream LanguageTool Russian tests;
2. `grammar.xml` executable examples;
3. direct pinned-upstream fixtures;
4. differential comparison against the optional Java oracle;
5. project-specific regression tests.

Do not substitute a few hand-written happy-path tests for upstream conformance.

When parity is measurable, compare as many of these as applicable: rule id, category, finding count/existence, offset, length, message, suggestions/replacements, enabled/disabled behavior.

## 8. Upstream pinning

Never use floating `master`/`main` as the compatibility target.

Upstream updates are controlled operations. Do not silently refresh vendored files or change the pinned revision while implementing an unrelated task.

Any intentional upstream upgrade must include drift analysis and a full relevant conformance run.

## 9. Repository hygiene

- Keep implementation under `src/pylat_ru/` once created.
- Keep tests under `tests/`.
- Keep development tools under `tools/`.
- Keep pinned upstream material/metadata under `third_party/languagetool/`.
- Keep numbered task specifications under `tasks/`.
- Keep completion reports under `reports/`.
- Do not commit local corpora, caches, downloaded oracle distributions, virtual environments, secrets, or generated bulk artifacts unless a task explicitly says they are canonical repository assets.

## 10. Performance

Correctness and parity come before optimization.

Still avoid obviously pathological architecture: do not parse all XML on every `check()`, reload large dictionaries per token/sentence, or build giant per-entry Python object graphs without need.

Do not trade away observable LT behavior for speed without explicit approval and documented compatibility impact.

## 11. Scope control

Do not add unrelated TextQA features such as AI detector, neural GEC models, humanizer, character voice, continuity analysis, or browser UI.

`pylat_ru` is the rule-based Russian LanguageTool-compatible library. TextQA is a consumer.

## 12. Completion report

Each completed task must create a Markdown report in `reports/`, including at minimum:

- task number/title;
- summary of implementation;
- important files added/changed;
- tests/proofs run and results;
- compatibility/inventory changes;
- known limitations or blocked items;
- license/provenance findings when relevant.

Do not hide failures behind wording like "mostly complete". State exactly what passed, failed, was skipped, or remains unsupported.