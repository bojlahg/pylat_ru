# GitHub Actions / Checks setup for `pylat_ru`

This repository contains two GitHub Actions workflows:

- `.github/workflows/ci.yml` — automatic Python/committed-fixture CI on every push to `main` and every pull request targeting `main`.
- `.github/workflows/oracle-conformance.yml` — manually triggered full conformance run that builds the pinned LanguageTool 6.8 Java oracle, validates it against `compat/oracle_manifest.json`, and then requires the complete pytest suite to finish with **0 failures / 0 errors / 0 skips**.

No repository secrets are required by either workflow.

## 1. Enable GitHub Actions

Open the repository on GitHub and go to:

`Settings -> Actions -> General`

Under **Actions permissions**, allow GitHub Actions for the repository. The default GitHub actions used here are:

- `actions/checkout`
- `actions/setup-python`
- `actions/setup-java`
- `actions/upload-artifact`

The workflows only request:

```text
contents: read
```

They do not need write access to the repository.

## 2. Automatic CI

No extra setup is needed after Actions are enabled.

Every push to `main` starts the `CI` workflow with two checks:

```text
CI / Python 3.10
CI / Python 3.12
```

The job installs:

```bash
python -m pip install -e '.[dev]'
```

and runs:

```bash
python -m pytest --junitxml=pytest-results.xml
```

The JUnit XML report is uploaded as an Actions artifact for 14 days.

The automatic job intentionally relies on committed oracle fixtures. A development-only test that generates fresh Java fixtures may be skipped when a live oracle JAR is not present. The manual `Oracle Conformance` workflow below is the authoritative zero-skip check.

## 3. Run the full trusted-oracle conformance check

Open:

`Actions -> Oracle Conformance -> Run workflow`

Choose branch `main` and start the run.

The workflow will:

1. install Python 3.12;
2. install JDK 17;
3. install Maven 3.9.12;
4. fetch the exact LanguageTool commit:

   ```text
   e807fcde6a6506191e1470744d2345da28c26be6
   ```

5. build LanguageTool with:

   ```bash
   mvn clean package -DskipTests
   ```

6. copy the resulting JAR to:

   ```text
   .oracle_cache/LanguageTool-6.8/languagetool-commandline.jar
   ```

7. call `JavaLanguageToolOracle.validate_oracle()`;
8. require the generated JAR to match one of the trusted build records in `compat/oracle_manifest.json`;
9. run the complete pytest suite;
10. parse the JUnit result and fail unless failures, errors, and skips are all zero.

### If the oracle build fails SHA validation

Do **not** weaken or remove the SHA check just to make CI green.

A different JDK/Maven/build environment may produce a byte-different JAR. In that case either:

- reproduce one of the already trusted builds exactly; or
- create a new trusted build record only after verifying its LanguageTool commit, version, JDK/Maven provenance, artifact path, and SHA-256.

The manifest is deliberately fail-closed.

## 4. Where the checks appear

After the first workflow run, open any commit on GitHub. The commit should show checks such as:

```text
CI / Python 3.10
CI / Python 3.12
```

The manual run appears as:

```text
Oracle Conformance / LT 6.8 trusted oracle + full pytest
```

The same results are visible under the repository **Actions** tab.

## 5. Branch protection / required checks

For the current workflow, agents commit and push directly to `main` and review happens afterward. Therefore **do not enable required status checks on `main` yet**: required pre-merge checks fit a branch/PR workflow, not direct pushes to the protected branch.

If the project later switches to:

```text
agent branch -> pull request -> CI -> review -> merge main
```

then configure a branch ruleset:

`Settings -> Rules -> Rulesets -> New branch ruleset`

Target `main`, then enable **Require status checks to pass** and select at least:

```text
CI / Python 3.10
CI / Python 3.12
```

The manual oracle job is deliberately not required for every ordinary commit because rebuilding LanguageTool is much heavier. Run it for milestone/conformance closure or make it required later if build time is acceptable.

## 6. Recommended review policy

For normal implementation commits:

```text
push main
-> automatic CI must be green
-> review code/diff/evidence
```

For milestone acceptance such as grammar-engine tasks:

```text
push main
-> automatic CI green
-> run Oracle Conformance
-> Oracle Conformance green with 0 skips
-> review and accept milestone
```

This keeps the fast check cheap while retaining an independently reproducible Java differential gate when exact LanguageTool parity matters.
