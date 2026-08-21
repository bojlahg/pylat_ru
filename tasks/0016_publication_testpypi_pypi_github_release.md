# Task 0016 — TestPyPI, PyPI Trusted Publishing and GitHub Release

## Status

`ACTIVE TASK SPECIFICATION`

Repository: `bojlahg/pylat_ru`
Branch: `main`
Accepted Task-0015 baseline: `996c9579d9d4c961c38982653f85d16dc6d05dbf`

Current package:

- distribution name: `pylat_ru`
- import package: `pylat_ru`
- version: `0.1.0a0`
- Python: `>=3.10`
- runtime dependency: `regex` only

Pinned LanguageTool:

- version: `6.8`
- commit: `e807fcde6a6506191e1470744d2345da28c26be6`

Accepted compatibility state:

- ordinary/non-LM Russian compatibility: PASS
- ordinary unexplained discrepancies: `0`
- `RussianConfusionProbabilityRule`: `LANGUAGE_MODEL_DEFERRED`

Task 0015 already proved wheel/sdist build, clean installation, metadata validation, `pip check`, Linux/Windows smoke, Python 3.10/3.11/3.12 support, licensing/provenance and release-preflight CI.

---

## 1. Goal

Publish the first public alpha release safely and reproducibly.

Target release:

`0.1.0a0`

Required destinations:

1. TestPyPI
2. PyPI
3. GitHub Release

Intended final installation command:

```bash
pip install pylat-ru==0.1.0a0
```

Python import remains:

```python
from pylat_ru import LanguageToolRU
```

Use GitHub Actions + PyPI Trusted Publishing/OIDC. Do not introduce a permanent PyPI token unless Trusted Publishing is genuinely unavailable and the user explicitly approves a fallback.

---

## 2. Human prerequisites

Before publication, determine what already exists:

- PyPI account
- TestPyPI account
- GitHub repository admin access
- 2FA where required

Never request passwords, 2FA secrets or recovery codes.

If an external account setting cannot be changed automatically, stop at the smallest manual step and return exact UI instructions rather than vague text such as “configure PyPI”.

---

## 3. Verify package-name availability

Before creating a public project, verify the normalized project namespace on both PyPI and TestPyPI.

Remember that Python package indexes normalize punctuation, so names like:

- `pylat_ru`
- `pylat-ru`
- `pylat.ru`

share the same normalized distribution namespace.

Preferred spelling in user-facing installation docs: `pylat-ru`.

Do not rename the Python import package.

If the normalized name is already owned by another project/user, STOP and return a short list of alternatives for explicit user approval. Do not silently publish under another name.

---

## 4. Keep version `0.1.0a0`

Do not promote this first public release to `0.1.0` or `1.0.0`.

Target remains:

`0.1.0a0`

If this exact version already exists on PyPI for this project, do not overwrite or silently bump it. STOP and propose `0.1.0a1` for explicit approval.

---

## 5. No LanguageTool semantic changes

Task 0016 is publication infrastructure only.

Do not change:

- grammar behavior
- spelling behavior
- RuleMatch semantics
- checking levels
- resource data
- LanguageTool pin
- ordinary rule inventory

Do not implement `RussianConfusionProbabilityRule`.

If publication work unexpectedly requires a semantic production change under `src/pylat_ru/`, STOP and explain why before mixing it into the release task.

---

## 6. Release workflow

Add a dedicated workflow, preferably:

`.github/workflows/release.yml`

Do not overload normal CI with automatic package publication.

Preferred production trigger:

```yaml
on:
  push:
    tags:
      - "v*"
```

For this release the production tag is:

`v0.1.0a0`

The workflow must validate that:

- tag version
- `pyproject.toml` project version
- `pylat_ru.__version__`
- wheel metadata version
- sdist metadata version

all equal `0.1.0a0`.

The workflow must build from the tag's exact `GITHUB_SHA`, not switch back to `main`.

---

## 7. Publication workflow stages

Required logical order:

1. verify source/tag/version
2. build wheel + sdist
3. validate metadata/artifact contents
4. install artifacts in clean environments and smoke-test them
5. publish to the selected index
6. for production, create/complete GitHub prerelease

Publication must never happen before validation.

---

## 8. Build release artifacts from scratch

Build in a clean GitHub runner with:

```bash
python -m build
```

Do not upload files copied from an old `dist/` directory or developer machine.

Build both:

- wheel
- sdist

Reuse the Task-0015 release-preflight tooling rather than creating a second weaker implementation.

---

## 9. Mandatory pre-publication checks

Before any upload require:

- `twine check`: PASS
- wheel forbidden-content audit: PASS
- sdist forbidden-content audit: PASS
- version consistency: PASS
- clean wheel install outside repository: PASS
- clean sdist install outside repository: PASS
- `pip check`: PASS
- installed functional smoke: PASS

The wheel must remain pure Python, expected tag class `py3-none-any`.

If it unexpectedly becomes platform-specific, STOP and investigate.

---

## 10. Release artifact manifest

During CI generate an uploaded artifact manifest containing at least:

- source SHA
- tag
- package version
- wheel filename, size, SHA-256
- sdist filename, size, SHA-256
- metadata validation result
- wheel audit result
- sdist audit result
- clean wheel install result
- clean sdist install result

Do not commit run-specific hashes or run IDs after CI.

---

## 11. GitHub Environments

Use protected GitHub Environments:

- `testpypi`
- `pypi`

For the production `pypi` environment, configure manual approval if supported.

A tag should not produce an irreversible production upload without a visible release gate.

Do not fake a manual gate in YAML if it provides no actual protection.

---

## 12. Trusted Publishing — TestPyPI

Configure TestPyPI Trusted Publishing using the actual implementation values, expected approximately:

- owner: `bojlahg`
- repository: `pylat_ru`
- workflow: `release.yml`
- environment: `testpypi`

Use exact values from the final workflow.

Do not store TestPyPI passwords/tokens when OIDC works.

---

## 13. Trusted Publishing — PyPI

Configure PyPI Trusted Publishing using:

- owner: `bojlahg`
- repository: `pylat_ru`
- workflow: `release.yml`
- environment: `pypi`

Use minimum required permissions, including:

```yaml
permissions:
  id-token: write
```

Do not use `write-all`.

Prefer the official PyPI publishing action/mechanism. Do not use a random third-party uploader.

---

## 14. TestPyPI first

The first live publication path must be TestPyPI, not production PyPI.

Required sequence:

1. publish `0.1.0a0` to TestPyPI
2. confirm package page renders correctly
3. install exact version into a fresh environment
4. run functional smoke
5. run `pip check`
6. only after this passes, continue to production PyPI

TestPyPI and PyPI are independent indexes, so using `0.1.0a0` on TestPyPI does not consume that version on PyPI.

---

## 15. TestPyPI install must really use TestPyPI

Use an install strategy where `pylat-ru==0.1.0a0` comes from TestPyPI while runtime dependencies may come from ordinary PyPI if necessary.

Verify the installed package origin/version so the smoke cannot accidentally test a production PyPI copy or source checkout.

Run from outside the repository with no repo path on `PYTHONPATH`.

---

## 16. TestPyPI functional smoke

At minimum test:

- `import pylat_ru`
- `LanguageToolRU()` construction
- XML grammar finding
- native rule finding
- spelling finding
- DEFAULT/PICKY behavior
- `rule_config`
- non-BMP UTF-16 offset
- no Java/runtime subprocess/network dependency
- `pylat_ru.__version__ == "0.1.0a0"`

TestPyPI acceptance gate requires all of:

- project page visible
- exact version visible
- wheel visible
- sdist visible
- README/description renders
- fresh install succeeds
- functional smoke succeeds
- `pip check` succeeds

If any fail, do not publish to production PyPI.

---

## 17. Production PyPI publication

After TestPyPI acceptance, publish the same release source/version to production PyPI through GitHub Actions + Trusted Publishing.

Do not rebuild from modified source between TestPyPI and production.

Ideally reuse the same exact artifact bytes. If separate workflow executions rebuild, verify reproducibility before upload.

---

## 18. Production PyPI smoke

After publication, create a fresh environment and run:

```bash
pip install pylat-ru==0.1.0a0
```

Then verify:

- installed version is `0.1.0a0`
- import path points to site-packages
- XML rule smoke: PASS
- native rule smoke: PASS
- spelling smoke: PASS
- DEFAULT/PICKY: PASS
- non-BMP offsets: PASS
- `pip check`: PASS

No repository path may leak into the environment.

---

## 19. Git tag

The release tag is:

`v0.1.0a0`

Tag only an already accepted, clean, exact-SHA-tested release commit.

Verify:

`tag target SHA == intended release source SHA`

Do not tag an unverified commit.

---

## 20. GitHub Release

Create GitHub Release for `v0.1.0a0` and mark it as:

`pre-release`

Do not mark alpha as latest stable.

Attach exactly:

- wheel
- sdist

Prefer the same bytes published to PyPI.

Include SHA-256 values in release notes or attached manifest.

Do not attach oracle, corpus or development artifacts.

---

## 21. GitHub Release notes

Keep notes concise and accurate. Include:

- first public alpha
- native Python Russian LanguageTool-compatible checker
- no Java/JRE required at runtime
- Python `>=3.10`
- pinned LanguageTool version/commit
- ordinary/non-LM compatibility status
- `RussianConfusionProbabilityRule` limitation
- installation command
- PyPI link

Do not claim full parity with LanguageTool's language-model subsystem.

---

## 22. README publication state

Before creating the release tag, ensure README contains the intended real install command:

```bash
pip install pylat-ru==0.1.0a0
```

It may also mention:

```bash
pip install --pre pylat-ru
```

Do not require a post-publication docs commit just to switch wording from “not published” to “published”. Prepare final release docs before tagging.

---

## 23. Avoid post-release SHA recursion

Correct order:

1. prepare workflow/docs
2. commit final release source
3. run normal CI + release preflight on exact SHA
4. verify green
5. tag that exact SHA
6. publish
7. do not create a docs-only commit containing run IDs

Actual publication URLs/run IDs belong in the final handoff.

---

## 24. Static tests for release workflow

Before live use, add tests/checks proving:

- tag/version validation exists
- OIDC permission is scoped
- production environment is `pypi`
- TestPyPI path cannot publish to PyPI
- production path cannot accidentally target TestPyPI
- build happens before publish
- artifact validation happens before publish

Do not make these tests depend on irrelevant YAML formatting.

---

## 25. Security rules

Never:

- commit `.pypirc` credentials
- commit passwords/tokens
- print OIDC tokens
- print PyPI credentials
- disable 2FA for convenience
- automatically fall back to a permanent API token

If Trusted Publishing fails due to external configuration, stop and return exact manual setup steps.

---

## 26. Idempotency

Release workflow must fail safely if the target version already exists.

Do not:

- delete an existing PyPI version
- replace existing files
- silently bump the version

If `0.1.0a0` is already consumed, stop for user decision.

---

## 27. Publication evidence files

Add static/reproducible publication infrastructure evidence, for example:

`compat/publication_0016.json`

Include:

- schema version
- task
- distribution name
- release version
- release tag
- workflow path(s)
- expected GitHub environments
- Trusted Publishing configuration identity
- artifact policy
- publication state model

Never include credentials.

Create:

`reports/0016_publication.md`

It should describe the release architecture and prerequisites. Do not create a post-release commit solely to add run IDs.

---

## 28. Pre-tag acceptance CI

The final release source SHA must already have successful:

- normal CI
- Release Preflight

Existing accepted gates remain:

- Python 3.10 full tests
- Python 3.12 full tests
- Python 3.11 artifact smoke
- Linux release preflight
- Windows wheel smoke
- zero failures/errors/skips

Do not create the tag before these exact-SHA checks pass.

---

## 29. Do not rerun full Task-0014 Java campaign

Task 0016 should not change production semantics, so the full live Java differential campaign is not required.

Keep Task-0014/0015 committed compatibility tests green.

If any semantic production code changes unexpectedly, stop and determine whether differential rerun is required.

---

## 30. Full local tests

Before final release source commit:

```bash
python -m pytest
```

Required:

- 0 failed
- 0 errors
- 0 skipped

Task 0015 had `1152 passed`; Task 0016 may add infrastructure tests, so do not hard-code that final count.

---

## 31. Final artifact identity

Final evidence must connect:

`Git tag → source SHA → wheel/sdist → PyPI → GitHub Release`

Verify SHA-256 of public PyPI files and GitHub Release assets.

Required outcome:

- PyPI wheel hash == GitHub Release wheel hash
- PyPI sdist hash == GitHub Release sdist hash

If artifacts differ, investigate before declaring release complete.

---

## 32. Failure handling

If TestPyPI fails: do not publish to PyPI.

If Trusted Publishing is misconfigured: do not silently use a permanent token.

If version already exists: do not overwrite or silently increment.

If GitHub Release succeeds but PyPI fails: report partial state and do not declare success.

---

## 33. Acceptance criteria

Task 0016 is complete only if all are true.

### Release source

- immutable source SHA
- exact-SHA normal CI success
- exact-SHA release-preflight success
- version `0.1.0a0`
- tag `v0.1.0a0` points to that SHA

### Trusted Publishing

- TestPyPI Trusted Publishing: PASS
- PyPI Trusted Publishing: PASS
- no permanent PyPI token required

### TestPyPI

- package visible
- version visible
- wheel visible
- sdist visible
- README renders
- fresh install succeeds
- `pip check` succeeds
- functional smoke succeeds

### PyPI

- package visible
- version visible
- wheel visible
- sdist visible
- README renders
- normal `pip install pylat-ru==0.1.0a0` succeeds
- `pip check` succeeds
- functional smoke succeeds

### GitHub Release

- tag `v0.1.0a0`
- marked prerelease
- correct source SHA
- wheel attached
- sdist attached
- hashes match PyPI
- release notes accurate

### Compatibility

- Task-0015 tests green
- Task-0014 compatibility preserved
- LanguageTool pin unchanged
- `RussianConfusionProbabilityRule = LANGUAGE_MODEL_DEFERRED`

### Security

- no credentials committed
- OIDC Trusted Publishing used
- production publish uses explicit environment gate

---

## 34. Required final handoff

Return concrete evidence in this form:

```text
Task 0016 final verification

baseline:
996c9579d9d4c961c38982653f85d16dc6d05dbf

release source SHA:
<SHA>

remote main:
<SHA>

package:
distribution: pylat-ru
import package: pylat_ru
version: 0.1.0a0

Pinned LanguageTool:
6.8
e807fcde6a6506191e1470744d2345da28c26be6

normal CI:
run ID: <ID>
URL: <URL>
head SHA: <SHA>
result: success
tests: <N> passed / 0 failed / 0 errors / 0 skipped

release preflight:
run ID: <ID>
URL: <URL>
head SHA: <SHA>
result: success

TestPyPI:
Trusted Publishing: PASS
project URL: <URL>
release URL: <URL>
publish run ID: <ID>

wheel:
filename: <filename>
SHA-256: <hash>

sdist:
filename: <filename>
SHA-256: <hash>

fresh TestPyPI install: PASS
TestPyPI functional smoke: PASS

PyPI:
Trusted Publishing: PASS
project URL: <URL>
release URL: <URL>
publish run ID: <ID>

fresh PyPI install:
pip install pylat-ru==0.1.0a0
PASS

PyPI functional smoke: PASS

Git:
tag: v0.1.0a0
tag target SHA: <SHA>

GitHub Release:
URL: <URL>
prerelease: yes
wheel attached: PASS
sdist attached: PASS
artifact hashes match PyPI: PASS

Wheel:
filename: <filename>
size: <bytes>
SHA-256: <hash>

Sdist:
filename: <filename>
size: <bytes>
SHA-256: <hash>

Task-0014 compatibility:
preserved: PASS
ordinary unexplained discrepancies: 0

RussianConfusionProbabilityRule:
LANGUAGE_MODEL_DEFERRED

Repository changes after publication:
none

Publication:
PUBLIC ALPHA RELEASED

FINAL:
READY FOR REVIEW
```

---

## 35. Stop condition

After the public alpha is verified, STOP.

Do not:

- publish `0.1.0a1`
- promote to `0.1.0`
- create another release
- change LanguageTool pin
- implement LM rule
- start an unrequested Task 0017

The next milestone should be driven by real downstream usage, especially TextQA integration and any real compatibility/performance problems it exposes.

---

## Definition of Done

Task 0016 is done when the same verified `pylat_ru 0.1.0a0` artifacts are publicly available through PyPI and GitHub Release, TestPyPI has already validated the publication path, a clean machine can install the package with `pip` and use it without Java, and the entire release is traceable to one immutable Git tag and source SHA.
