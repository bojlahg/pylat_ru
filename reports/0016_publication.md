# Task 0016 — TestPyPI, PyPI Trusted Publishing, and GitHub Release

## Baseline and scope

Baseline: `996c9579d9d4c961c38982653f85d16dc6d05dbf`.

This task adds publication infrastructure for `pylat-ru 0.1.0a0`. It does not change
production code, Russian checking semantics, packaged resources, or the LanguageTool
6.8 pin (`e807fcde6a6506191e1470744d2345da28c26be6`). The ordinary compatibility result
remains zero unexplained discrepancies, and `RussianConfusionProbabilityRule` remains
`LANGUAGE_MODEL_DEFERRED`.

## Release architecture

`.github/workflows/release.yml` is isolated from normal CI and normally runs for `v*` tag
pushes. A recovery-only manual dispatch requires both an existing immutable tag and its
exact accepted source SHA; the workflow checks out the tag and proves that both identities
match before continuing. It verifies the source versions and refuses an occupied index
namespace or immutable version. It then reuses the Task-0015 preflight to build wheel and
sdist once, run Twine validation and content audits, clean-install both artifacts, run
`pip check`, and execute the installed functional smoke. The resulting manifest binds the
tag and source SHA to filenames, sizes, hashes, and individual validation results.

The same uploaded workflow artifact proceeds through TestPyPI publication, TestPyPI page
and hash validation, exact wheel download and isolated smoke, a protected production
`pypi` environment, PyPI publication, equivalent production validation, and finally a
GitHub prerelease. The release receives exactly the validated wheel and sdist; notes are
rendered from the manifest and include both SHA-256 values. Publication jobs alone receive
`id-token: write`; only the final GitHub release job receives `contents: write`.

## Important files

- `.github/workflows/release.yml`: ordered Trusted Publishing and prerelease workflow.
- `tools/verify_release_0016.py`: source/tag/wheel/sdist/manifest version contract.
- `tools/check_index_availability_0016.py`: normalized namespace and immutable-version guard.
- `tools/verify_published_0016.py`: public metadata/hash, clean install, `pip check`, and smoke gate.
- `tools/render_release_notes_0016.py`: deterministic release notes with artifact hashes.
- `compat/publication_0016.json`: reproducible publisher identity, artifact policy, and state model.
- `tests/unit/test_publication_workflow_0016.py`: formatting-independent YAML contract tests.
- `README.md`: final public-alpha installation command prepared before tagging.

## External prerequisites and live evidence policy

The GitHub environments must exist as `testpypi` and `pypi`; `pypi` must have a required
reviewer protection rule. Pending Trusted Publishers on TestPyPI and PyPI must use owner
`bojlahg`, repository `pylat_ru`, workflow `release.yml`, and their matching environment.
No password, API token, `.pypirc`, or OIDC token is stored or printed.

The release tag can only be created after the final committed SHA has green normal CI and
Release Preflight. Run IDs, public URLs, and live artifact hashes are intentionally not
committed because doing so would create post-release SHA recursion; they belong in the
final handoff. The public namespace/version check is repeated immediately in the tag run.

## Tests and proofs

Local Python 3.10 proofs:

- authoritative TestPyPI and PyPI JSON endpoints: normalized `pylat-ru` namespace
  unoccupied and `0.1.0a0` available;
- focused publication/README/release-evidence tests: 11 passed;
- `python -m pytest`: 1,156 passed in 228.24 seconds, 0 failed, 0 errors, 0 skipped;
- two clean artifact builds: PASS;
- `twine check` for wheel and sdist: PASS;
- wheel and sdist forbidden-content audits: PASS;
- clean wheel install, `pip check`, and installed functional smoke: PASS;
- clean sdist install, `pip check`, and installed functional smoke: PASS;
- source/tag/wheel/sdist/manifest version consistency and pure-wheel tag: PASS.

Exact-SHA CI results, live TestPyPI/PyPI smokes, tag identity, GitHub prerelease state,
and cross-destination hashes are recorded in the final handoff. The full Task-0014 Java
campaign is intentionally not rerun because no semantic production code changed.

## Compatibility and limitations

Task-0014/0015 compatibility evidence is preserved. Language-model parity is not claimed.
Publication fails closed on an occupied namespace/version, incomplete index artifacts,
hash drift, smoke failure, missing Trusted Publisher configuration, or a rejected GitHub
environment gate. It never falls back to a permanent PyPI token or silently increments
the version.
